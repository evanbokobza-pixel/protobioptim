from __future__ import annotations

import secrets
from datetime import datetime, timezone

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def password_is_valid(password: str) -> bool:
    return len(password) >= 8 and any(char.isdigit() for char in password)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_reference(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def ensure_csrf_token(session: dict) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(24)
        session["csrf_token"] = token
    return token


def csrf_is_valid(session: dict, submitted_token: str) -> bool:
    expected = session.get("csrf_token")
    return bool(expected and submitted_token and secrets.compare_digest(expected, submitted_token))
