import os
from dotenv import load_dotenv

load_dotenv()

ON_RENDER = bool(os.environ.get("RENDER"))  # Render sets RENDER=true on its servers


def _database_url():
    """Accept the connection string exactly as Neon or Render shows it."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url or None


def _secret_key():
    key = os.environ.get("SECRET_KEY")
    if not key and ON_RENDER:
        raise RuntimeError("SECRET_KEY must be set in the hosting environment.")
    return key or "dev-only-secret"


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # check a connection before using it: free hosted databases close idle connections
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # reject uploads over 1 MB (snapshots are tiny)
    SESSION_COOKIE_SECURE = ON_RENDER      # send the login cookie over HTTPS only when hosted
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
