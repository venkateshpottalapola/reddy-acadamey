import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Admin, AdminSession


password_hasher = PasswordHasher()
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 5


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cookie_options() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.session_cookie_secure or settings.environment == "production",
        "samesite": "strict",
        "path": "/",
    }


def set_admin_cookies(response: Response, session_token: str, csrf_token: str, max_age: int) -> None:
    options = _cookie_options()
    response.set_cookie("reddy_admin_session", session_token, max_age=max_age, **options)
    response.set_cookie(
        "reddy_admin_csrf",
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=options["secure"],
        samesite=options["samesite"],
        path=options["path"],
    )


def clear_admin_cookies(response: Response) -> None:
    response.delete_cookie("reddy_admin_session", path="/", secure=_cookie_options()["secure"], httponly=True, samesite="strict")
    response.delete_cookie("reddy_admin_csrf", path="/", secure=_cookie_options()["secure"], samesite="strict")


def issue_csrf_cookie(response: Response) -> str:
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        "reddy_admin_csrf",
        csrf_token,
        max_age=900,
        httponly=False,
        secure=_cookie_options()["secure"],
        samesite="strict",
        path="/",
    )
    return csrf_token


def check_login_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _login_attempts[client_host]
    while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 15 minutes.")
    attempts.append(now)


def reset_login_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    _login_attempts.pop(client_host, None)


def require_login_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("reddy_admin_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed. Reload the admin page and try again.")


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> Admin:
    raw_token = request.cookies.get("reddy_admin_session")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Administrator login required.")
    stored_session = db.scalar(
        select(AdminSession).where(AdminSession.token_hash == _digest(raw_token))
    )
    now = datetime.now(timezone.utc)
    if stored_session is None or stored_session.expires_at.replace(tzinfo=timezone.utc) <= now:
        if stored_session is not None:
            db.delete(stored_session)
            db.commit()
        raise HTTPException(status_code=401, detail="Administrator session expired. Please log in again.")
    admin = db.get(Admin, stored_session.admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Administrator account is inactive.")
    request.state.admin_session = stored_session
    return admin


def require_admin_csrf(request: Request, admin: Admin = Depends(get_current_admin)) -> Admin:
    require_login_csrf(request)
    stored_session: AdminSession = request.state.admin_session
    header_token = request.headers.get("X-CSRF-Token", "")
    if not secrets.compare_digest(stored_session.csrf_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed. Reload the admin page and try again.")
    return admin


def make_admin_session(db: Session, admin: Admin) -> tuple[str, str, int]:
    settings = get_settings()
    ttl = settings.session_ttl_hours * 60 * 60
    raw_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        AdminSession(
            admin_id=admin.id,
            token_hash=_digest(raw_token),
            csrf_token=csrf_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
        )
    )
    admin.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return raw_token, csrf_token, ttl


def revoke_admin_session(db: Session, raw_token: str | None) -> None:
    if raw_token:
        stored_session = db.scalar(select(AdminSession).where(AdminSession.token_hash == _digest(raw_token)))
        if stored_session:
            db.delete(stored_session)
            db.commit()


def get_session_csrf_for_request(request: Request) -> str | None:
    stored_session = getattr(request.state, "admin_session", None)
    return stored_session.csrf_token if stored_session else None
