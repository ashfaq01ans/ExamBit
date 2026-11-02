"""Security helpers: CSRF protection and a few safe response headers.

CSRF (cross-site request forgery): another website could make a logged-in user's
browser send a POST to ExamBit, because the browser attaches the login cookie
automatically. To stop that, every POST must carry a secret token that only pages
served by ExamBit know. The token lives in the signed session cookie. Forms send it
as a hidden field and background requests send it in the X-CSRFToken header.
"""
import hmac
import secrets

from flask import abort, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SESSION_KEY = "_csrf_token"
FIELD_NAME = "csrf_token"
HEADER_NAME = "X-CSRFToken"


def get_token():
    """Return this session's token, creating it the first time it is needed."""
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def check_request():
    """Reject any POST, PUT, PATCH or DELETE that does not carry the session's token."""
    if request.method in SAFE_METHODS:
        return
    expected = session.get(SESSION_KEY, "")
    sent = request.headers.get(HEADER_NAME) or request.form.get(FIELD_NAME) or ""
    # compare_digest takes the same time however many characters match
    if not expected or not hmac.compare_digest(expected.encode("utf-8"), sent.encode("utf-8")):
        abort(400)


def add_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")  # no content-type guessing
    response.headers.setdefault("X-Frame-Options", "DENY")            # no embedding in other sites
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"  # pages hold personal data: do not cache
    return response


def init_security(app):
    app.jinja_env.globals["csrf_token"] = get_token
    app.before_request(check_request)
    app.after_request(add_headers)
