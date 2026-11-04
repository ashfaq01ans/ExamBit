from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app import db
from app.decorators import role_required
from app.classes import COURSES, session_options
from app.models import Answer, Attempt, Exam, Option, Question
from app.timeutil import local_input, parse_local, to_local

bp = Blueprint("teacher", __name__, url_prefix="/teacher")

QUESTION_TYPES = {
    "single": "Single choice",
    "multiple": "Multiple correct",
    "truefalse": "True / False",
    "short": "Short answer",
}

EXAM_FIELDS = (
    "title", "instructions", "duration_minutes", "start_time", "end_time",
    "course", "admission_session", "show_answers",
)


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
        "course": exam.course or "",
        "admission_session": exam.admission_session or "",
        "show_answers": "1" if exam.show_answers else "",
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
    elif end <= datetime.now(timezone.utc):
        errors.append("The closing time must be in the future.")
    elif end <= start:
        errors.append("End time must be after start time.")
    elif duration and (end - start) < timedelta(minutes=duration):
        errors.append("The time window must be at least as long as the duration.")

    course = values["course"] or None
    if course is not None and course not in COURSES:
        errors.append("Choose a valid course.")
    admission_session = values["admission_session"] or None
    if admission_session is not None and admission_session not in session_options():
        errors.append("Choose a valid admission session.")

    parsed = {
        "title": title,
        "instructions": values["instructions"],
        "duration_minutes": duration,
        "start_time": start,
        "end_time": end,
        "course": course,
        "admission_session": admission_session,
        "show_answers": values["show_answers"] == "1",
    }
    return parsed, errors


def locked_redirect(exam):
    """Exams with attempts cannot be changed. Returns a redirect, or None."""
    if exam.attempts:
        flash("This exam already has attempts, so it can no longer be changed.", "error")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))
    return None


# ---------- dashboard and exams ----------

def build_dashboard(exams, pending, now, selected_course="", selected_month=""):
    """Sort a teacher's exams into groups and apply the course and month filters.
    exams: newest created first. pending: exam id -> short answers waiting for grading."""
    items = []
    months = {}
    for exam in exams:
        start = to_local(exam.start_time)
        month_key = start.strftime("%Y-%m")
        months[month_key] = start.strftime("%b %Y")
        if not exam.is_published:
            state = "draft"
        elif exam.end_time <= now:
            state = "closed"
        elif exam.start_time > now:
            state = "upcoming"
        else:
            state = "live"
        items.append({"exam": exam, "state": state, "month": month_key, "pending": pending.get(exam.id, 0)})

    def wanted(item):
        exam = item["exam"]
        if selected_course == "none":
            course_ok = exam.course is None
        else:
            course_ok = not selected_course or exam.course == selected_course
        return course_ok and (not selected_month or item["month"] == selected_month)

    groups = {"drafts": [], "grading": [], "active": [], "past": []}
    for item in filter(wanted, items):
        if item["state"] == "draft":
            groups["drafts"].append(item)
        elif item["pending"]:
            groups["grading"].append(item)
        elif item["state"] in ("live", "upcoming"):
            groups["active"].append(item)
        else:
            groups["past"].append(item)

    groups["grading"].sort(key=lambda i: i["exam"].end_time, reverse=True)
    groups["active"].sort(key=lambda i: i["exam"].start_time)          # soonest first
    groups["past"].sort(key=lambda i: i["exam"].start_time, reverse=True)  # newest first

    return {
        "groups": groups,
        # every course the university offers, like the register page, plus any old one still on an exam
        "course_options": list(COURSES) + sorted({e.course for e in exams if e.course and e.course not in COURSES}),
        "has_open": any(e.course is None for e in exams),
        "month_options": sorted(months.items(), reverse=True),
    }


@bp.route("/")
@role_required("teacher")
def dashboard():
    now = datetime.now(timezone.utc)
    exams = db.session.execute(
        db.select(Exam)
        .filter_by(teacher_id=current_user.id)
        .order_by(Exam.created_at.desc())
        .options(selectinload(Exam.questions), selectinload(Exam.attempts))
    ).scalars().all()

    # short answers waiting for this teacher, counted per exam in one query
    pending_rows = db.session.execute(
        db.select(Attempt.exam_id, func.count(Answer.id))
        .select_from(Attempt)
        .join(Answer, Answer.attempt_id == Attempt.id)
        .join(Question, Question.id == Answer.question_id)
        .where(
            Attempt.exam_id.in_([exam.id for exam in exams]),
            Attempt.status != "in_progress",
            Question.qtype == "short",
            Answer.marks_awarded.is_(None),
            Answer.text_answer.is_not(None),
        )
        .group_by(Attempt.exam_id)
    ).all()
    pending = {exam_id: count for exam_id, count in pending_rows}

    selected_course = request.args.get("course", "")
    selected_month = request.args.get("month", "")
    view = build_dashboard(exams, pending, now, selected_course, selected_month)
    return render_template(
        "teacher/dashboard.html",
        total_exams=len(exams), total_pending=sum(pending.values()), pending_exams=len(pending),
        selected_course=selected_course, selected_month=selected_month, **view,
    )


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

def parse_question_form(qtype, form):
    """Read and check the question form. Returns (text, marks, options, errors).
    options is a list of (text, is_correct)."""
    errors = []
    text = form.get("text", "").strip()
    if not text:
        errors.append("Question text is required.")

    try:
        marks = int(form.get("marks", "").strip())
        if not 1 <= marks <= 100:
            raise ValueError
    except ValueError:
        marks = None
        errors.append("Marks must be a whole number from 1 to 100.")

    options = []
    if qtype in ("single", "multiple"):
        correct_values = set(form.getlist("correct"))
        for i in range(1, 5):
            option_text = form.get(f"option_{i}", "").strip()
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
        answer = form.get("tf_answer")
        if answer not in ("true", "false"):
            errors.append("Choose the correct answer: True or False.")
        else:
            options = [("True", answer == "true"), ("False", answer == "false")]
    return text, marks, options, errors


class Prefill:
    """Looks like request.form, so one template can show a saved question."""

    def __init__(self, data):
        self.data = data

    def get(self, key, default=""):
        return self.data.get(key, default)

    def getlist(self, key):
        return self.data.get(key, [])


def prefill_from_question(question, qtype):
    """Fill the form from a saved question. Options carry over only between
    single choice and multiple correct. Text and marks always carry over."""
    data = {"text": question.text, "marks": str(question.marks)}
    options = sorted(question.options, key=lambda o: o.id)
    if qtype in ("single", "multiple") and question.qtype in ("single", "multiple"):
        correct = []
        for i, option in enumerate(options[:4], start=1):
            data[f"option_{i}"] = option.text
            if option.is_correct:
                correct.append(str(i))
        data["correct"] = correct
    elif qtype == "truefalse" and question.qtype == "truefalse":
        for option in options:
            if option.is_correct:
                data["tf_answer"] = option.text.lower()
    return data


def render_question_form(exam, qtype, form, question=None):
    return render_template(
        "teacher/question_form.html",
        exam=exam, qtype=qtype, type_label=QUESTION_TYPES[qtype], types=QUESTION_TYPES,
        form=form, question=question,
    )


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
        text, marks, options, errors = parse_question_form(qtype, request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_question_form(exam, qtype, request.form)

        question = Question(exam_id=exam.id, text=text, qtype=qtype, marks=marks)
        question.options = [Option(text=t, is_correct=c) for t, c in options]
        db.session.add(question)
        db.session.commit()
        flash("Question added.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))

    return render_question_form(exam, qtype, request.form)


@bp.route("/exams/<int:exam_id>/questions/<int:question_id>/edit", methods=["GET", "POST"])
@role_required("teacher")
def question_edit(exam_id, question_id):
    exam = get_exam(exam_id)
    blocked = locked_redirect(exam)
    if blocked:
        return blocked

    question = db.session.get(Question, question_id)
    if question is None or question.exam_id != exam.id:
        abort(404)

    qtype = request.values.get("type", question.qtype)
    if qtype not in QUESTION_TYPES:
        abort(404)

    if request.method == "POST":
        text, marks, options, errors = parse_question_form(qtype, request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_question_form(exam, qtype, request.form, question)

        question.text = text
        question.marks = marks
        question.qtype = qtype
        question.options = [Option(text=t, is_correct=c) for t, c in options]  # old ones are removed
        db.session.commit()
        flash("Question updated.", "success")
        return redirect(url_for("teacher.exam_detail", exam_id=exam.id))

    return render_question_form(exam, qtype, Prefill(prefill_from_question(question, qtype)), question)


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
