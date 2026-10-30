from flask import Blueprint, render_template

from app.decorators import role_required

bp = Blueprint("teacher", __name__, url_prefix="/teacher")


@bp.route("/")
@role_required("teacher")
def dashboard():
    return render_template("teacher/dashboard.html")
