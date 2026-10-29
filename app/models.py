from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'teacher' or 'student'
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    exams = db.relationship("Exam", backref="teacher", lazy=True)
    attempts = db.relationship("Attempt", backref="student", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    questions = db.relationship(
        "Question", backref="exam", lazy=True, cascade="all, delete-orphan"
    )
    attempts = db.relationship("Attempt", backref="exam", lazy=True)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # 'single', 'multiple', 'truefalse', 'short'
    qtype = db.Column(db.String(12), nullable=False)
    marks = db.Column(db.Integer, default=1, nullable=False)

    options = db.relationship(
        "Option", backref="question", lazy=True, cascade="all, delete-orphan"
    )


class Option(db.Model):
    __tablename__ = "options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)


class Attempt(db.Model):
    __tablename__ = "attempts"
    __table_args__ = (
        db.UniqueConstraint("exam_id", "student_id", name="one_attempt_per_student"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True))
    # 'in_progress', 'submitted', 'auto_submitted'
    status = db.Column(db.String(15), default="in_progress", nullable=False)
    score = db.Column(db.Float)

    answers = db.relationship(
        "Answer", backref="attempt", lazy=True, cascade="all, delete-orphan"
    )
    violations = db.relationship(
        "Violation", backref="attempt", lazy=True, cascade="all, delete-orphan"
    )
    snapshots = db.relationship(
        "Snapshot", backref="attempt", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def integrity_score(self):
        # starts at 100, minus 10 per violation, never below 0
        return max(0, 100 - 10 * len(self.violations))


class Answer(db.Model):
    __tablename__ = "answers"
    __table_args__ = (
        db.UniqueConstraint("attempt_id", "question_id", name="one_answer_per_question"),
    )

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    selected_option_ids = db.Column(db.JSON)  # list of option ids, e.g. [3, 5]
    text_answer = db.Column(db.Text)  # for short-answer questions
    marked_for_review = db.Column(db.Boolean, default=False, nullable=False)
    marks_awarded = db.Column(db.Float)  # null until graded


class Violation(db.Model):
    __tablename__ = "violations"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False)
    # 'tab_switch', 'fullscreen_exit', 'screen_share_stopped'
    kind = db.Column(db.String(30), nullable=False)
    occurred_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Snapshot(db.Model):
    __tablename__ = "snapshots"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("attempts.id"), nullable=False)
    image_data = db.Column(db.LargeBinary, nullable=False)  # small JPEG bytes
    taken_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
