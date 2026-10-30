from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import User

bp = Blueprint("auth", __name__)

ROLES = ("teacher", "student")


def home_for(user):
    return url_for(f"{user.role}.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        role = request.form.get("role", "")

        errors = []
        if not name:
            errors.append("Name is required.")
        if "@" not in email or "." not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if role not in ROLES:
            errors.append("Choose a role.")
        if not errors:
            existing = db.session.execute(
                db.select(User).filter_by(email=email)
            ).scalar_one_or_none()
            if existing:
                errors.append("This email is already registered.")

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("auth/register.html", name=name, email=email, role=role)

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_for(current_user))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        # same message for wrong email and wrong password
        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", email=email)

        login_user(user)
        return redirect(home_for(user))

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
