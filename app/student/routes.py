import random
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for,
)
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.decorators import role_required
from app.models import Answer, Attempt, Exam, Question, Snapshot, Violation
from app.proctoring import (
    MAX_SNAPSHOT_BYTES, MAX_SNAPSHOTS_PER_ATTEMPT, MAX_VIOLATIONS,
    SNAPSHOT_INTERVAL_SECONDS, VIOLATION_LABELS,
)

bp = Blueprint("student", __name__, url_prefix="/student")

# An answer sent a few seconds after the deadline (network delay) is still saved.
GRACE_SECONDS = 10


# ---------- helpers ----------

def now_utc():
    return datetime.now(timezone.utc)


def get_published_exam(exam_id):
    exam = db.session.get(Exam, exam_id)
    if exam is None or not exam.is_published:
        abort(404)
    return exam


def get_attempt(attempt_id):
    """Fetch an attempt that belongs to the logged-in student, or 404."""
    attempt = db.session.get(Attempt, attempt_id)
    if attempt is None or attempt.student_id != current_user.id:
        abort(404)
    return attempt


def find_attempt(exam_id):
    return db.session.execute(
        db.select(Attempt).filter_by(exam_id=exam_id, student_id=current_user.id)
    ).scalar_one_or_none()


def deadline_for(attempt):
    """Server-side deadline: start + duration, but never after the exam window closes."""
    by_duration = attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)
    return min(by_duration, attempt.exam.end_time)


def remaining_seconds(deadline, now):
    return max(0, int((deadline - now).total_seconds()))


def finalize(attempt, status, when):
    if attempt.status != "in_progress":
        return
    attempt.status = status
    attempt.submitted_at = when
    db.session.commit()


def expire_if_needed(attempt):
    """Auto-submit an in-progress attempt whose time is over. True if it did."""
    if attempt.status == "in_progress":
        deadline = deadline_for(attempt)
        if now_utc() > deadline:
            finalize(attempt, "auto_submitted", deadline)
            return True
    return False


def time_up_redirect(attempt, deadline):
    finalize(attempt, "auto_submitted", deadline)
    flash("Time is up. Your exam was submitted automatically.", "error")
    return redirect(url_for("student.result", attempt_id=attempt.id))


def count_violations(attempt):
    return db.session.scalar(
        db.select(func.count(Violation.id)).where(Violation.attempt_id == attempt.id)
    )


def ordered_questions(attempt):
    """Objective questions first, short-answer questions last. Each group is shuffled
    on its own. Seeding with the attempt id keeps the order stable on refresh without
    storing it, and gives each student a different order."""
    questions = sorted(attempt.exam.questions, key=lambda q: q.id)
    objective = [q for q in questions if q.qtype != "short"]
    subjective = [q for q in questions if q.qtype == "short"]
    random.Random(attempt.id).shuffle(objective)
    random.Random(attempt.id + 7919).shuffle(subjective)
    return objective + subjective


def ordered_options(attempt, question):
    options = sorted(question.options, key=lambda o: o.id)
    if question.qtype in ("single", "multiple"):  # True/False keeps its natural order
        random.Random(attempt.id * 100000 + question.id).shuffle(options)
    return options


def save_answer(attempt, question, option_ids, text, marked):
    answer = next((a for a in attempt.answers if a.question_id == question.id), None)
    if answer is None:
        answer = Answer(attempt_id=attempt.id, question_id=question.id)
        db.session.add(answer)

    if question.qtype == "short":
        cleaned = text.strip()[:5000] if isinstance(text, str) else ""
        answer.text_answer = cleaned or None
        answer.selected_option_ids = None
    else:
        valid_ids = {option.id for option in question.options}
        chosen = []
        if isinstance(option_ids, list):
            for value in option_ids:
                is_int = isinstance(value, int) and not isinstance(value, bool)
                if is_int and value in valid_ids and value not in chosen:  # ignore tampering
                    chosen.append(value)
        if question.qtype != "multiple":
            chosen = chosen[:1]
        answer.selected_option_ids = chosen
        answer.text_answer = None

    answer.marked_for_review = bool(marked)


def build_payload(attempt):
    deadline = deadline_for(attempt)
    now = now_utc()
    return {
        "attemptId": attempt.id,
        "remaining": remaining_seconds(deadline, now),
        "violationCount": count_violations(attempt),
        "maxViolations": MAX_VIOLATIONS,
        "urls": {
            "answer": url_for("student.answer_api", attempt_id=attempt.id),
            "submit": url_for("student.submit", attempt_id=attempt.id),
            "result": url_for("student.result", attempt_id=attempt.id),
            "violation": url_for("student.violation_api", attempt_id=attempt.id),
            "snapshot": url_for("student.snapshot_api", attempt_id=attempt.id),
        },
        # correct answers are never sent to the browser
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "type": q.qtype,
                "marks": q.marks,
                "options": [{"id": o.id, "text": o.text} for o in ordered_options(attempt, q)],
            }
            for q in ordered_questions(attempt)
        ],
        "answers": {
            str(a.question_id): {
                "options": a.selected_option_ids or [],
                "text": a.text_answer or "",
                "marked": a.marked_for_review,
            }
            for a in attempt.answers
        },
    }


# ---------- dashboard and exam info ----------

@bp.route("/")
@role_required("student")
def dashboard():
    now = now_utc()
    exams = db.session.execute(
        db.select(Exam).filter_by(is_published=True).order_by(Exam.start_time)
    ).scalars().all()
    attempts = {a.exam_id: a for a in current_user.attempts}
    for attempt in attempts.values():
        expire_if_needed(attempt)  # finalize attempts whose time ran out

    in_progress, live, upcoming, past = [], [], [], []
    for exam in exams:
        attempt = attempts.get(exam.id)
        if attempt:
            (in_progress if attempt.status == "in_progress" else past).append((exam, attempt))
        elif exam.start_time > now:
            upcoming.append((exam, None))
        elif exam.end_time > now:
            live.append((exam, None))
        else:
            past.append((exam, None))  # never attempted: missed

    return render_template(
        "student/dashboard.html",
        in_progress=in_progress, live=live, upcoming=upcoming, past=past,
    )


@bp.route("/exams/<int:exam_id>")
@role_required("student")
def exam_detail(exam_id):
    exam = get_published_exam(exam_id)
    attempt = find_attempt(exam.id)
    if attempt:
        expire_if_needed(attempt)

    now = now_utc()
    if attempt:
        state = "in_progress" if attempt.status == "in_progress" else "finished"
    elif now < exam.start_time:
        state = "upcoming"
    elif now >= exam.end_time:
        state = "missed"
    else:
        state = "live"
    return render_template("student/exam_detail.html", exam=exam, attempt=attempt, state=state)


# ---------- system check, then the exam (one page) ----------

@bp.route("/exams/<int:exam_id>/take")
@role_required("student")
def exam_take(exam_id):
    """The exam page. It starts with a system check. No questions and no timer
    start until the student passes it and clicks Begin."""
    exam = get_published_exam(exam_id)
    attempt = find_attempt(exam.id)
    if attempt:
        expire_if_needed(attempt)
        if attempt.status != "in_progress":
            return redirect(url_for("student.result", attempt_id=attempt.id))
    else:
        now = now_utc()
        if not (exam.start_time <= now < exam.end_time):
            flash("This exam is not open right now.", "error")
            return redirect(url_for("student.exam_detail", exam_id=exam.id))

    boot = {
        "urls": {"begin": url_for("student.exam_begin", exam_id=exam.id)},
        "snapshotInterval": SNAPSHOT_INTERVAL_SECONDS,
        "labels": VIOLATION_LABELS,
    }
    return render_template("student/exam.html", exam=exam, resume=bool(attempt), boot=boot)


@bp.route("/exams/<int:exam_id>/begin", methods=["POST"])
@role_required("student")
def exam_begin(exam_id):
    """Called after the system check. Creates the attempt (this is when the timer
    starts) or returns the existing one."""
    exam = get_published_exam(exam_id)
    data = request.get_json(silent=True) or {}
    attempt = find_attempt(exam.id)

    if attempt:
        expire_if_needed(attempt)
        if attempt.status != "in_progress":
            return jsonify(
                ok=False, error="This exam is already finished.",
                result_url=url_for("student.result", attempt_id=attempt.id),
            ), 409
    else:
        now = now_utc()
        if not (exam.start_time <= now < exam.end_time):
            return jsonify(ok=False, error="This exam is not open right now."), 400
        if not exam.questions:
            return jsonify(ok=False, error="This exam has no questions yet."), 400
        if data.get("consent") is not True:
            return jsonify(ok=False, error="You must accept the exam rules to start."), 400

        attempt = Attempt(exam_id=exam.id, student_id=current_user.id, started_at=now)
        db.session.add(attempt)
        try:
            db.session.commit()
        except IntegrityError:  # double click: the attempt already exists
            db.session.rollback()
            attempt = find_attempt(exam.id)

    return jsonify(ok=True, payload=build_payload(attempt))


# ---------- calls made by the exam page ----------

@bp.route("/attempts/<int:attempt_id>/answer", methods=["POST"])
@role_required("student")
def answer_api(attempt_id):
    attempt = get_attempt(attempt_id)
    result_url = url_for("student.result", attempt_id=attempt.id)
    if attempt.status != "in_progress":
        return jsonify(ok=False, finished=True, result_url=result_url)

    deadline = deadline_for(attempt)
    now = now_utc()
    if now > deadline + timedelta(seconds=GRACE_SECONDS):
        finalize(attempt, "auto_submitted", deadline)
        return jsonify(ok=False, finished=True, result_url=result_url)

    data = request.get_json(silent=True) or {}
    question_id = data.get("question_id")
    if not isinstance(question_id, int):
        return jsonify(ok=False, error="bad request"), 400
    question = db.session.get(Question, question_id)
    if question is None or question.exam_id != attempt.exam_id:
        return jsonify(ok=False, error="bad request"), 400

    args = (attempt, question, data.get("options"), data.get("text"), data.get("marked"))
    try:
        save_answer(*args)
        db.session.commit()
    except IntegrityError:  # two quick saves created the same answer row: retry once
        db.session.rollback()
        save_answer(*args)
        db.session.commit()

    finished = False
    if now > deadline:  # answer arrived inside the grace window, then close the attempt
        finalize(attempt, "auto_submitted", deadline)
        finished = True
    return jsonify(ok=True, finished=finished, result_url=result_url)


@bp.route("/attempts/<int:attempt_id>/violation", methods=["POST"])
@role_required("student")
def violation_api(attempt_id):
    attempt = get_attempt(attempt_id)
    result_url = url_for("student.result", attempt_id=attempt.id)
    if attempt.status != "in_progress":
        return jsonify(ok=False, finished=True, result_url=result_url)

    deadline = deadline_for(attempt)
    now = now_utc()
    if now > deadline + timedelta(seconds=GRACE_SECONDS):
        finalize(attempt, "auto_submitted", deadline)
        return jsonify(ok=False, finished=True, result_url=result_url)

    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    if kind not in VIOLATION_LABELS:
        return jsonify(ok=False, error="bad request"), 400

    db.session.add(Violation(attempt_id=attempt.id, kind=kind))
    db.session.commit()

    count = count_violations(attempt)
    finished = count >= MAX_VIOLATIONS
    if finished:
        finalize(attempt, "auto_submitted", now)
        flash(f"Your exam was submitted automatically after {MAX_VIOLATIONS} violations.", "error")

    return jsonify(
        ok=True, finished=finished, count=count, max=MAX_VIOLATIONS,
        integrity=max(0, 100 - 10 * count), result_url=result_url,
    )


@bp.route("/attempts/<int:attempt_id>/snapshot", methods=["POST"])
@role_required("student")
def snapshot_api(attempt_id):
    attempt = get_attempt(attempt_id)
    result_url = url_for("student.result", attempt_id=attempt.id)
    if attempt.status != "in_progress":
        return jsonify(ok=False, finished=True, result_url=result_url)

    upload = request.files.get("image")
    if upload is None:
        return jsonify(ok=False, error="bad request"), 400
    image = upload.read(MAX_SNAPSHOT_BYTES + 1)
    if len(image) > MAX_SNAPSHOT_BYTES or not image.startswith(b"\xff\xd8\xff"):  # JPEG only
        return jsonify(ok=False, error="bad request"), 400

    stored = db.session.scalar(
        db.select(func.count(Snapshot.id)).where(Snapshot.attempt_id == attempt.id)
    )
    if stored >= MAX_SNAPSHOTS_PER_ATTEMPT:
        return jsonify(ok=True, skipped=True)

    db.session.add(Snapshot(attempt_id=attempt.id, image_data=image))
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/attempts/<int:attempt_id>/submit", methods=["POST"])
@role_required("student")
def submit(attempt_id):
    attempt = get_attempt(attempt_id)
    if attempt.status == "in_progress":
        deadline = deadline_for(attempt)
        now = now_utc()
        if now > deadline:
            finalize(attempt, "auto_submitted", deadline)
            flash("Time was up, so your exam was submitted automatically.", "error")
        else:
            finalize(attempt, "submitted", now)
            flash("Exam submitted successfully.", "success")

    result_url = url_for("student.result", attempt_id=attempt.id)
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, result_url=result_url)
    return redirect(result_url)


@bp.route("/attempts/<int:attempt_id>/result")
@role_required("student")
def result(attempt_id):
    attempt = get_attempt(attempt_id)
    if attempt.status == "in_progress" and not expire_if_needed(attempt):
        return redirect(url_for("student.exam_take", exam_id=attempt.exam_id))
    return render_template("student/result.html", attempt=attempt, exam=attempt.exam)
