"""Password hashing and token primitives.

* Passwords: Argon2id (argon2-cffi defaults follow RFC 9106 recommendations).
* Access tokens: short-lived JWTs signed with ``AKSHARA_JWT_SECRET``.
* Refresh tokens: opaque random strings. Only their SHA-256 is stored, so a database leak
  does not leak usable tokens. Rotation and reuse detection live in ``services.auth``.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_hasher = PasswordHasher()

# Used to equalise timing when the e-mail address does not exist.
_DUMMY_HASH = _hasher.hash("akshara-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = settings.access_token_ttl_seconds
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "typ": "access",
        "iss": "akshara",
    }
    token = jwt.encode(
        claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, ttl


def decode_access_token(token: str, settings: Settings) -> uuid.UUID | None:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer="akshara",
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "access":
        return None
    try:
        return uuid.UUID(claims["sub"])
    except (ValueError, KeyError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
