from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.ids import uuid7
from app.core.ratelimit import MemoryRateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)

SECRET = "x" * 40


def settings(**kw: object) -> Settings:
    return Settings(database_url="postgresql+asyncpg://u@h/d", jwt_secret=SECRET, **kw)  # type: ignore[arg-type]


def test_short_secret_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(database_url="x", jwt_secret="short")  # type: ignore[arg-type]


def test_password_hash_roundtrip() -> None:
    h = hash_password("correct horse 1")
    assert h.startswith("$argon2id$")
    assert verify_password("correct horse 1", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)


def test_access_token_roundtrip() -> None:
    s = settings()
    uid = uuid.uuid4()
    token, ttl = create_access_token(uid, s)
    assert ttl == s.access_token_ttl_seconds
    assert decode_access_token(token, s) == uid


def test_expired_token_rejected() -> None:
    s = settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": past, "exp": past, "typ": "access", "iss": "akshara"},
        SECRET,
        algorithm="HS256",
    )
    assert decode_access_token(token, s) is None


def test_wrong_signature_and_alg_none_rejected() -> None:
    s = settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "typ": "access",
        "iss": "akshara",
    }
    assert decode_access_token(jwt.encode(claims, "y" * 40, algorithm="HS256"), s) is None
    assert decode_access_token(jwt.encode(claims, None, algorithm="none"), s) is None  # type: ignore[arg-type]


def test_refresh_typ_rejected_as_access() -> None:
    s = settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "typ": "refresh",
        "iss": "akshara",
    }
    assert decode_access_token(jwt.encode(claims, SECRET, algorithm="HS256"), s) is None


def test_refresh_tokens_random_and_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b and len(a) >= 60
    assert hash_token(a) == hash_token(a) and len(hash_token(a)) == 64


def test_uuid7_is_time_ordered_and_versioned() -> None:
    ids = [uuid7() for _ in range(200)]
    assert all(i.version == 7 for i in ids)
    assert [i.int >> 80 for i in ids] == sorted(i.int >> 80 for i in ids)


async def test_memory_rate_limiter() -> None:
    rl = MemoryRateLimiter()
    results = [await rl.hit("k", 3, 60) for _ in range(5)]
    assert results == [True, True, True, False, False]
