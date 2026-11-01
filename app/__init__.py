import os

from flask import Flask, Response, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."

ERROR_TEXT = {
    403: ("Access denied", "You do not have permission to open this page."),
    404: ("Page not found", "This page does not exist, or you cannot open it."),
    500: ("Something went wrong", "An unexpected error happened. Please try again."),
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    if app.config.get("BEHIND_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (registers tables with SQLAlchemy)
    from app.timeutil import local_display, local_input

    app.add_template_filter(local_display, "localdt")
    app.add_template_filter(local_input, "localinput")

    from app.classes import COURSES, session_options
    from app.cli import reset_data

    app.jinja_env.globals["COURSES"] = COURSES
    app.jinja_env.globals["session_options"] = session_options
    app.cli.add_command(reset_data)

    def static_v(filename):
        """Static file URL with a version that changes when the file changes,
        so browsers can cache it for a long time and still get updates."""
        try:
            version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
        except OSError:
            version = 0
        return url_for("static", filename=filename, v=version)

    app.jinja_env.globals["static_v"] = static_v

    from app.auth.routes import bp as auth_bp
    from app.teacher.routes import bp as teacher_bp
    from app.teacher import reports  # noqa: F401  (adds report routes to the teacher blueprint)
    from app.student.routes import bp as student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    def render_error(error):
        code = getattr(error, "code", 500)
        title, message = ERROR_TEXT.get(code, ERROR_TEXT[500])
        return render_template("errors/error.html", code=code, title=title, message=message), code

    for code in ERROR_TEXT:
        app.register_error_handler(code, render_error)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for(f"{current_user.role}.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/favicon.ico")
    def favicon():
        return redirect(url_for("static", filename="img/favicon.ico"), code=301)

    @app.route("/robots.txt")
    def robots():
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")

    return app
