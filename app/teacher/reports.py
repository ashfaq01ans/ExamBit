from flask import Response, abort, render_template
from flask_login import current_user

from app import db
from app.decorators import role_required
from app.models import Attempt, Snapshot
from app.proctoring import MAX_VIOLATIONS, VIOLATION_LABELS
from app.teacher.routes import bp, get_exam


@bp.route("/exams/<int:exam_id>/attempts")
@role_required("teacher")
def exam_attempts(exam_id):
    exam = get_exam(exam_id)
    attempts = sorted(exam.attempts, key=lambda a: a.started_at)
    return render_template("teacher/attempts.html", exam=exam, attempts=attempts)


@bp.route("/attempts/<int:attempt_id>")
@role_required("teacher")
def attempt_detail(attempt_id):
    attempt = db.session.get(Attempt, attempt_id)
    if attempt is None or attempt.exam.teacher_id != current_user.id:
        abort(404)

    violations = sorted(attempt.violations, key=lambda v: v.occurred_at)
    # only ids and times here, so the image bytes are not loaded for the list
    snapshots = db.session.execute(
        db.select(Snapshot.id, Snapshot.taken_at)
        .where(Snapshot.attempt_id == attempt.id)
        .order_by(Snapshot.taken_at)
    ).all()
    return render_template(
        "teacher/attempt_detail.html",
        attempt=attempt, exam=attempt.exam, violations=violations,
        snapshots=snapshots, labels=VIOLATION_LABELS, max_violations=MAX_VIOLATIONS,
    )


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
