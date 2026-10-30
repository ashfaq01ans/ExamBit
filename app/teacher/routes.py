from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app import db
from app.decorators import role_required
from app.models import Exam, Option, Question
from app.timeutil import local_input, parse_local

bp = Blueprint("teacher", __name__, url_prefix="/teacher")

QUESTION_TYPES = {
    "single": "Single choice",
    "multiple": "Multiple correct",
    "truefalse": "True / False",
    "short": "Short answer",
}

EXAM_FIELDS = ("title", "instructions", "duration_minutes", "start_time", "end_time")


# ---------- helpers ----------

def get_exam(exam_id):
    """Fetch an exam owned by the logged-in teacher, or 404."""
    exam = db.session.get(Exam, exam_id)
    if exam is None or exam.teacher_id != current_user.id:
        abort(404)
    return exam


def blank_values():
    return {field: "" for field in EXAM_FIELDS}


def values_from_exam(exam):
    return {
        "title": exam.title,
        "instructions": exam.instructions or "",
        "duration_minutes": exam.duration_minutes,
        "start_time": local_input(exam.start_time),
        "end_time": local_input(exam.end_time),
    }


def values_from_form(form):
    return {field: form.get(field, "").strip() for field in EXAM_FIELDS}


def validate_exam(values):
    """Return (parsed_fields, errors) for the exam form values."""
    errors = []

    title = values["title"]
    if not title:
        errors.append("Title is required.")

    try:
        duration = int(values["duration_minutes"])
        if not 1 <= duration <= 300:
            raise ValueError
    except (ValueError, TypeError):
        duration = None
        errors.append("Duration must be a whole number from 1 to 300 minutes.")

    start = parse_local(values["start_time"])
    end = parse_local(values["end_time"])
    if start is None or end is None:
        errors.append("Enter a valid start and end time.")
    elif end <= start:
        errors.append("End time must be after start time.")
    elif duration and (end - start) < timedelta(minutes=duration):
        errors.append("The time window must be at least as long as the duration.")

    parsed = {
        "title": title,
        "instructions": values["instructions"],
        "duration_minutes": duration,
        "start_time": start,
        "end_time": end,
    }
    return parsed, errors


def locked_redirect(exam):
    """Exams with attempts cannot be changed. Returns a redirect, or None."""
    if exam.attempts:
        flash("This exam already has attempts, so it can no longer be changed.", "error")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
    return None


# ---------- dashboard and exams ----------

@bp.route("/")
@role_required("teacher")
def dashboard():
    exams = db.session.execute(
        db.select(Exam).filter_by(teacher_id=current_user.id).order_by(Exam.created_at.desc())
    ).scalars().all()
    return render_template("teacher/dashboard.html", exams=exams)


@bp.route("/exams/new", methods=["GET", "POST"])
@role_required("teacher")
def exam_new():
    if request.method == "POST":
        values = values_from_form(request.form)
        parsed, errors = validate_exam(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("teacher/exam_form.html", values=values, exam=None)

        exam = Exam(teacher_id=current_user.id, **parsed)
        db.session.add(exam)
        db.session.commit()
        flash("Exam created. Now add questions.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))

    return render_template("teacher/exam_form.html", values=blank_values(), exam=None)


@bp.route("/exams/<int:exam_id>")
@role_required("teacher")
def exam_detail(exam_id):
    exam = get_exam(exam_id)
    return render_template(
        "teacher/exam_detail.html",
        exam=exam,
        locked=bool(exam.attempts),
        types=QUESTION_TYPES,
    )


@bp.route("/exams/<int:exam_id>/edit", methods=["GET", "POST"])
@role_required("teacher")
def exam_edit(exam_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    if request.method == "POST":
        values = values_from_form(request.form)
        parsed, errors = validate_exam(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("teacher/exam_form.html", values=values, exam=exam)

        for key, value in parsed.items():
            setattr(exam, key, value)
        db.session.commit()
        flash("Exam updated.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))

    return render_template("teacher/exam_form.html", values=values_from_exam(exam), exam=exam)


@bp.route("/exams/<int:exam_id>/delete", methods=["POST"])
@role_required("teacher")
def exam_delete(exam_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    db.session.delete(exam)
    db.session.commit()
    flash("Exam deleted.", "success")
    return redirect(url_for("teacher.dashboard"))


@bp.route("/exams/<int:exam_id>/publish", methods=["POST"])
@role_required("teacher")
def exam_publish(exam_id):
    exam = get_exam(exam_id)
    if not exam.questions:
        flash("Add at least one question before publishing.", "error")
    elif exam.end_time <= datetime.now(timezone.utc):
        flash("The end time is in the past. Edit the exam window first.", "error")
    else:
        exam.is_published = True
        db.session.commit()
        flash("Exam published. Students can now see it.", "success")
    return redirect(url_for("teacher.exam_detail", exam_id=exam.id))


@bp.route("/exams/<int:exam_id>/unpublish", methods=["POST"])
@role_required("teacher")
def exam_unpublish(exam_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    exam.is_published = False
    db.session.commit()
    flash("Exam unpublished. It is a draft again.", "success")
    return redirect(url_for("teacher.exam_detail", exam_id=exam.id))


# ---------- questions ----------

@bp.route("/exams/<int:exam_id>/questions/new", methods=["GET", "POST"])
@role_required("teacher")
def question_new(exam_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    qtype = request.values.get("type", "")
    if qtype not in QUESTION_TYPES:
        return render_template("teacher/question_type.html", exam=exam, types=QUESTION_TYPES)

    if request.method == "POST":
        text = request.form.get("text", "").strip()
        errors = []
        if not text:
            errors.append("Question text is required.")

        try:
            marks = int(request.form.get("marks", "").strip())
            if not 1 <= marks <= 100:
                raise ValueError
        except ValueError:
            marks = None
            errors.append("Marks must be a whole number from 1 to 100.")

        options = []  # list of (text, is_correct)
        if qtype in ("single", "multiple"):
            correct_values = set(request.form.getlist("correct"))
            for i in range(1, 5):
                option_text = request.form.get(f"option_{i}", "").strip()
                if option_text:
                    options.append((option_text, str(i) in correct_values))
            correct_count = sum(1 for _, is_correct in options if is_correct)
            if len(options) < 2:
                errors.append("Enter at least two options.")
            if qtype == "single" and correct_count != 1:
                errors.append("Choose exactly one correct option.")
            if qtype == "multiple" and correct_count < 1:
                errors.append("Choose at least one correct option.")
        elif qtype == "truefalse":
            answer = request.form.get("tf_answer")
            if answer not in ("true", "false"):
                errors.append("Choose the correct answer: True or False.")
            else:
                options = [("True", answer == "true"), ("False", answer == "false")]

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "teacher/question_form.html",
                exam=exam, qtype=qtype, type_label=QUESTION_TYPES[qtype], form=request.form,
            )

        question = Question(exam_id=exam.id, text=text, qtype=qtype, marks=marks)
        question.options = [Option(text=t, is_correct=c) for t, c in options]
        db.session.add(question)
        db.session.commit()
        flash("Question added.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))

    return render_template(
        "teacher/question_form.html",
        exam=exam, qtype=qtype, type_label=QUESTION_TYPES[qtype], form=request.form,
    )


@bp.route("/exams/<int:exam_id>/questions/<int:question_id>/delete", methods=["POST"])
@role_required("teacher")
def question_delete(exam_id, question_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    question = db.session.get(Question, question_id)
    if question is None or question.exam_id != exam.id:
        abort(404)

    db.session.delete(question)
    db.session.commit()
    flash("Question deleted.", "success")
    return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
