from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models  # noqa: F401  (registers tables with SQLAlchemy)

    from app.auth.routes import bp as auth_bp
    from app.teacher.routes import bp as teacher_bp
    from app.student.routes import bp as student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for(f"{current_user.role}.dashboard"))
        return redirect(url_for("auth.login"))

    return app
