from functools import wraps

from flask import abort, current_app
from flask_login import current_user


def role_required(role):
    """Allow only logged-in users with the given role ('teacher' or 'student')."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
