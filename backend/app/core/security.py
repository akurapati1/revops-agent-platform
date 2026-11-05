"""Password hashing and JWT helpers."""
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import get_settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def _encode(claims: dict[str, Any], ttl: timedelta) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: str, org_id: str | None) -> str:
    s = get_settings()
    return _encode({"sub": user_id, "org": org_id, "typ": "access"}, timedelta(minutes=s.access_token_minutes))


def create_refresh_token(user_id: str, org_id: str | None) -> str:
    s = get_settings()
    return _encode({"sub": user_id, "org": org_id, "typ": "refresh"}, timedelta(days=s.refresh_token_days))


def create_state_token(data: dict[str, Any]) -> str:
    return _encode({**data, "typ": "oauth_state"}, timedelta(minutes=10))


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    if payload.get("typ") != expected_type:
        raise ValueError("wrong token type")
    return payload


def random_token(n: int = 24) -> str:
    return secrets.token_urlsafe(n)
