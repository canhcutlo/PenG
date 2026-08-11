"""Authentication and authorization service."""
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from fastapi import Request, HTTPException, Depends
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings
from app.db import auth_store
from app.db.auth_store import hash_token, get_session_by_hash
from app.models.schemas import UserRegister, UserLogin


ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,32}$")


class RateLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(status_code=429, detail="Too many attempts. Please try again later.")


class AuthError(HTTPException):
    pass


class CSRFError(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail="Invalid or missing CSRF token.")


def _validate_username(username: str):
    if not _USERNAME_RE.match(username):
        raise AuthError(
            status_code=400,
            detail="Username must be 3-32 alphanumeric/underscore/dash characters.",
        )


def _rate_limit_key(request: Request, username: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{client}:{username}"


_login_attempts: dict[str, list[float]] = {}


def check_login_rate_limit(request: Request, username: str):
    key = _rate_limit_key(request, username)
    now = time.time()
    window = settings.auth_rate_limit_window_seconds
    attempts = _login_attempts.get(key, [])
    attempts = [t for t in attempts if now - t < window]
    if len(attempts) >= settings.auth_rate_limit_login_attempts:
        raise RateLimitExceeded()
    attempts.append(now)
    _login_attempts[key] = attempts


def register_user(data: UserRegister) -> dict:
    _validate_username(data.username)
    if data.username.lower() == settings.auth_system_user_username.lower():
        raise AuthError(status_code=409, detail="Username already exists.")
    if len(data.password) < 8:
        raise AuthError(status_code=400, detail="Password must be at least 8 characters.")

    existing = auth_store.get_user_by_username(data.username)
    if existing:
        raise AuthError(status_code=409, detail="Username already exists.")

    user_id = uuid.uuid4().hex[:12]
    password_hash = ph.hash(data.password)
    return auth_store.create_user(user_id, data.username, password_hash)


def login_user(data: UserLogin, request: Request) -> tuple[str, dict]:
    _validate_username(data.username)
    check_login_rate_limit(request, data.username)

    user = auth_store.get_user_by_username(data.username)
    if not user:
        raise AuthError(status_code=401, detail="Invalid username or password.")

    try:
        ph.verify(user["password_hash"], data.password)
    except VerifyMismatchError:
        raise AuthError(status_code=401, detail="Invalid username or password.")

    token = auth_store.create_session(user["user_id"])
    return token, {"user_id": user["user_id"], "username": user["username"]}


def logout_user(token: str):
    auth_store.delete_session(hash_token(token))


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise AuthError(status_code=401, detail="Not authenticated.")

    session = get_session_by_hash(hash_token(token))
    if not session:
        raise AuthError(status_code=401, detail="Session expired or invalid.")

    user = auth_store.get_user_by_id(session["user_id"])
    if not user:
        raise AuthError(status_code=401, detail="User not found.")

    return user


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    return user


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookie(response, token: str):
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_cookie_max_age_seconds,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
        secure=settings.auth_cookie_secure,
        path="/",
    )


def set_csrf_cookie(response, csrf_token: str):
    response.set_cookie(
        key=settings.auth_csrf_cookie_name,
        value=csrf_token,
        max_age=settings.auth_cookie_max_age_seconds,
        httponly=False,
        samesite=settings.auth_cookie_samesite,
        secure=settings.auth_cookie_secure,
        path="/",
    )


def clear_auth_cookies(response):
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.auth_csrf_cookie_name, path="/")


def verify_csrf(request: Request):
    cookie_token = request.cookies.get(settings.auth_csrf_cookie_name)
    header_token = request.headers.get(settings.auth_csrf_header_name)
    if not cookie_token or not header_token:
        raise CSRFError()
    if not secrets.compare_digest(cookie_token, header_token):
        raise CSRFError()


def require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


def create_test_user(username: str = "testuser", password: str = "testpass123") -> dict:
    """Create a test user; used by unit tests and bootstrap helpers."""
    from app.db.auth_store import get_user_by_username
    existing = get_user_by_username(username)
    if existing:
        return existing
    user_id = uuid.uuid4().hex[:12]
    return auth_store.create_user(user_id, username, ph.hash(password))


def create_test_session(user_id: str) -> str:
    return auth_store.create_session(user_id)
