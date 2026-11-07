from __future__ import annotations

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import register_and_login

pytestmark = pytest.mark.integration


async def test_register_login_me(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "ada@example.com"
    assert body["allow_external_llm"] is False  # D8: consent is off by default
    assert "password_hash" not in body


async def test_duplicate_email_case_insensitive(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    r = await client.post(
        "/api/v1/auth/register", json={"email": "ADA@example.com", "password": "Another-pass-9"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "EMAIL_TAKEN"


@pytest.mark.parametrize("password", ["short1", "onlyletterslongenough", " padded-pass-1 "])
async def test_weak_passwords_rejected(client: httpx.AsyncClient, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/register", json={"email": "b@example.com", "password": password}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_wrong_password_and_unknown_user_look_identical(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    a = await client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope"}
    )
    b = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


async def test_password_is_hashed_at_rest(client: httpx.AsyncClient, settings) -> None:
    await register_and_login(client)
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        stored = (await conn.execute(text("select password_hash from users"))).scalar_one()
    await engine.dispose()
    assert stored.startswith("$argon2id$") and "Analytical-1843" not in stored


async def test_protected_routes_require_token(client: httpx.AsyncClient) -> None:
    for path in ("/api/v1/auth/me", "/api/v1/documents", "/api/v1/jobs"):
        r = await client.get(path)
        assert r.status_code == 401, path
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_refresh_rotation_and_reuse_detection(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    first_cookie = client.cookies.get("akshara_refresh")
    assert first_cookie

    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    second_cookie = client.cookies.get("akshara_refresh")
    assert second_cookie and second_cookie != first_cookie

    # Replaying the old (rotated) token is treated as theft: the whole family is revoked.
    client.cookies.set("akshara_refresh", first_cookie, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401 and r.json()["error"]["code"] == "REFRESH_REUSED"

    client.cookies.set("akshara_refresh", second_cookie, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_refresh_cookie_flags(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register", json={"email": "c@example.com", "password": "Cookie-check-1"}
    )
    r = await client.post(
        "/api/v1/auth/login", json={"email": "c@example.com", "password": "Cookie-check-1"}
    )
    header = r.headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=strict" in header and "path=/api/v1/auth" in header


async def test_logout_revokes_session(client: httpx.AsyncClient) -> None:
    await register_and_login(client)
    cookie = client.cookies.get("akshara_refresh")
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    client.cookies.set("akshara_refresh", cookie, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


async def test_update_profile(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    r = await client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"display_name": "Ada", "preferred_unit": "mm", "allow_external_llm": True},
    )
    assert r.status_code == 200
    assert r.json()["preferred_unit"] == "mm" and r.json()["allow_external_llm"] is True
    r = await client.patch("/api/v1/auth/me", headers=headers, json={"preferred_unit": "cm"})
    assert r.status_code == 422


async def test_login_rate_limit(client: httpx.AsyncClient) -> None:
    client.app.state.akshara.settings.login_rate_limit_per_minute = 3  # type: ignore[attr-defined]
    codes = [
        (
            await client.post(
                "/api/v1/auth/login", json={"email": "x@example.com", "password": "p"}
            )
        ).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
