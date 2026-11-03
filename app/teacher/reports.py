import csv
import io

from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.decorators import role_required
from app.grading import compute_totals, ensure_graded, refresh_score
from app.models import Attempt, Snapshot
from app.proctoring import MAX_VIOLATIONS, VIOLATION_LABELS
from app.teacher.routes import QUESTION_TYPES, bp, get_exam
from app.timeutil import local_display


def fmt(value):
    return format(value, "g")


SNAPSHOT_GAP_SECONDS = 150  # snapshots come every 30 seconds, so this is five missed ones


def find_snapshot_gaps(started_at, ended_at, taken_times):
    """Stretches with no webcam snapshot for longer than SNAPSHOT_GAP_SECONDS.
    A refresh, a blocked camera or a throttled background tab can cause one, and so
    can someone blocking the page's background requests, so the teacher decides."""
    if not taken_times or ended_at is None:
        return []  # nothing stored (for example deleted) or the attempt is still running
    points = [started_at] + sorted(taken_times) + [ended_at]
    gaps = []
    for before, after in zip(points, points[1:]):
        seconds = (after - before).total_seconds()
        if seconds > SNAPSHOT_GAP_SECONDS:
            gaps.append({"start": before, "end": after, "minutes": round(seconds / 60, 1)})
    return gaps


def csv_safe(value):
    """Stop spreadsheet programs from running text that starts like a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def get_owned_attempt(attempt_id):
    attempt = db.session.get(Attempt, attempt_id)
    if attempt is None or attempt.exam.teacher_id != current_user.id:
        abort(404)
    return attempt


def status_label(attempt):
    return {"in_progress": "In progress", "submitted": "Submitted"}.get(
        attempt.status, "Auto-submitted"
    )


# ---------- attempts list and results ----------

SCORE_BANDS = [("0-19%", 0, 20), ("20-39%", 20, 40), ("40-59%", 40, 60), ("60-79%", 60, 80), ("80-100%", 80, 101)]


def score_summary(rows, total):
    """Average, highest, lowest and a count per score band, for finished and fully
    graded attempts. Returns None when there is nothing to show yet."""
    percents = [
        100 * row["earned"] / total
        for row in rows
        if total and row["attempt"].status != "in_progress" and not row["pending"]
    ]
    if not percents:
        return None
    counts = [sum(1 for p in percents if low <= p < high) for _, low, high in SCORE_BANDS]
    peak = max(counts) or 1
    return {
        "graded": len(percents),
        "average": round(sum(percents) / len(percents), 1),
        "highest": round(max(percents), 1),
        "lowest": round(min(percents), 1),
        "bands": [
            {"label": label, "count": count, "width": round(100 * count / peak)}
            for (label, _, _), count in zip(SCORE_BANDS, counts)
        ],
    }

@bp.route("/exams/<int:exam_id>/attempts")
@role_required("teacher")
def exam_attempts(exam_id):
    exam = get_exam(exam_id)
    total = sum(q.marks for q in exam.questions)
    rows = []
    for attempt in sorted(exam.attempts, key=lambda a: a.started_at):
        ensure_graded(attempt)
        earned, pending = compute_totals(attempt)
        rows.append({"attempt": attempt, "earned": earned, "pending": pending})
    return render_template(
        "teacher/attempts.html", exam=exam, rows=rows, total=total, summary=score_summary(rows, total)
    )


@bp.route("/exams/<int:exam_id>/results.csv")
@role_required("teacher")
def exam_results_csv(exam_id):
    exam = get_exam(exam_id)
    total = sum(q.marks for q in exam.questions)

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Name", "Email", "Course", "Session", "Status", "Marks", "Total marks",
        "Percentage", "Needs grading", "Violations", "Integrity score", "Started", "Ended",
    ])
    for attempt in sorted(exam.attempts, key=lambda a: a.started_at):
        ensure_graded(attempt)
        earned, pending = compute_totals(attempt)
        finished = attempt.status != "in_progress"
        percent = round(100 * earned / total, 1) if total else 0
        student = attempt.student
        writer.writerow([csv_safe(v) for v in (
            student.name, student.email, student.course, student.admission_session,
            status_label(attempt),
            fmt(earned) if finished and not pending else "",
            fmt(total),
            percent if finished and not pending else "",
            pending,
            len(attempt.violations), attempt.integrity_score,
            local_display(attempt.started_at), local_display(attempt.submitted_at),
        )])

    body = out.getvalue().encode("utf-8-sig")  # BOM so Excel reads names correctly
    return Response(
        body,
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="results_exam_{exam.id}.csv"'},
    )


# ---------- one attempt: answers, grading, proctoring ----------

def render_attempt(attempt, form=None):
    exam = attempt.exam
    answers = {a.question_id: a for a in attempt.answers}
    rows = []
    has_manual = False
    for question in sorted(exam.questions, key=lambda q: q.id):
        answer = answers.get(question.id)
        row = {"question": question, "answer": answer}
        if question.qtype == "short":
            text = answer.text_answer if answer and answer.text_answer and answer.text_answer.strip() else None
            row["text"] = text
            if text:
                has_manual = True
                if form is not None:
                    row["marks_value"] = form.get(f"marks_{answer.id}", "")
                elif answer.marks_awarded is not None:
                    row["marks_value"] = fmt(answer.marks_awarded)
                else:
                    row["marks_value"] = ""
        else:
            chosen_ids = set(answer.selected_option_ids or []) if answer else set()
            options = sorted(question.options, key=lambda o: o.id)
            row["chosen"] = [o.text for o in options if o.id in chosen_ids]
            row["correct"] = [o.text for o in options if o.is_correct]
            row["awarded"] = answer.marks_awarded if answer and answer.marks_awarded is not None else 0
        rows.append(row)

    violations = sorted(attempt.violations, key=lambda v: v.occurred_at)
    # only ids and times here, so the image bytes are not loaded for the list
    snapshots = db.session.execute(
        db.select(Snapshot.id, Snapshot.taken_at)
        .where(Snapshot.attempt_id == attempt.id)
        .order_by(Snapshot.taken_at)
    ).all()
    snapshot_gaps = find_snapshot_gaps(
        attempt.started_at, attempt.submitted_at, [s.taken_at for s in snapshots]
    )
    earned, pending = compute_totals(attempt)
    return render_template(
        "teacher/attempt_detail.html",
        attempt=attempt, exam=exam, rows=rows, has_manual=has_manual,
        violations=violations, snapshots=snapshots, snapshot_gaps=snapshot_gaps,
        labels=VIOLATION_LABELS, max_violations=MAX_VIOLATIONS, types=QUESTION_TYPES,
        earned=earned, pending=pending, total=sum(q.marks for q in exam.questions),
    )


@bp.route("/attempts/<int:attempt_id>")
@role_required("teacher")
def attempt_detail(attempt_id):
    attempt = get_owned_attempt(attempt_id)
    ensure_graded(attempt)
    return render_attempt(attempt)


@bp.route("/attempts/<int:attempt_id>/grade", methods=["POST"])
@role_required("teacher")
def attempt_grade(attempt_id):
    attempt = get_owned_attempt(attempt_id)
    if attempt.status == "in_progress":
        flash("The student is still taking the exam.", "error")
        return redirect(url_for("teacher.attempt_detail", attempt_id=attempt.id))

    questions = {q.id: q for q in attempt.exam.questions}
    errors = []
    updates = []
    for answer in attempt.answers:
        question = questions.get(answer.question_id)
        if question is None or question.qtype != "short":
            continue
        if not (answer.text_answer and answer.text_answer.strip()):
            continue
        raw = request.form.get(f"marks_{answer.id}", "").strip()
        if raw == "":
            continue  # left ungraded for now
        try:
            value = float(raw)
        except ValueError:
            errors.append("Marks must be numbers.")
            continue
        if not 0 <= value <= question.marks:  # also rejects nan and inf
            errors.append(f"Marks for a short answer must be between 0 and {question.marks}.")
            continue
        updates.append((answer, value))

    if errors:
        for message in dict.fromkeys(errors):
            flash(message, "error")
        return render_attempt(attempt, form=request.form)

    for answer, value in updates:
        answer.marks_awarded = value
    refresh_score(attempt)
    db.session.commit()
    flash("Marks saved.", "success")
    return redirect(url_for("teacher.attempt_detail", attempt_id=attempt.id))


@bp.route("/attempts/<int:attempt_id>/snapshots/delete", methods=["POST"])
@role_required("teacher")
def snapshots_delete(attempt_id):
    attempt = get_owned_attempt(attempt_id)
    if attempt.status == "in_progress":
        flash("Wait until the attempt has ended.", "error")
    else:
        db.session.execute(db.delete(Snapshot).where(Snapshot.attempt_id == attempt.id))
        db.session.commit()
        flash("Snapshots deleted. The violation record is kept.", "success")
    return redirect(url_for("teacher.attempt_detail", attempt_id=attempt.id))


@bp.route("/snapshots/<int:snapshot_id>")
@role_required("teacher")
def snapshot_image(snapshot_id):
    snapshot = db.session.get(Snapshot, snapshot_id)
    if snapshot is None or snapshot.attempt.exam.teacher_id != current_user.id:
        abort(404)
    return Response(
        snapshot.image_data,
        mimetype="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )
