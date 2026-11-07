"""Shared fixtures.

Integration tests use a real PostgreSQL database and Redis (see tests/README.md). The schema
is created with the real Alembic migrations, so migrations are tested on every run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[1]
TEST_DB = os.environ.get(
    "AKSHARA_TEST_DATABASE_URL", "postgresql+asyncpg://akshara@localhost:5432/akshara_test"
)
TEST_REDIS = os.environ.get("AKSHARA_TEST_REDIS_URL", "redis://localhost:6379/15")
TABLES = "audit_events, refresh_tokens, jobs, document_versions, documents, blobs, users"


@pytest.fixture(scope="session")
def migrated_db() -> str:
    env = {**os.environ, "AKSHARA_DATABASE_URL": TEST_DB}
    reset = "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

    async def _reset() -> None:
        engine = create_async_engine(TEST_DB)
        async with engine.begin() as conn:
            for stmt in reset.split(";"):
                if stmt.strip():
                    await conn.execute(text(stmt))
        await engine.dispose()

    import asyncio

    asyncio.run(_reset())
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
    )
    return TEST_DB


@pytest.fixture
def settings(migrated_db: str, tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=migrated_db,
        redis_url=TEST_REDIS,
        jwt_secret="test-secret-" + "x" * 32,  # type: ignore[arg-type]
        cookie_secure=False,
        storage_root=tmp_path / "blobs",
        max_upload_bytes=5 * 1024 * 1024,
        login_rate_limit_per_minute=1000,
        rate_limit_backend="memory",
        log_level="WARNING",
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    await engine.dispose()

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            c.app = app  # type: ignore[attr-defined]
            yield c


async def register_and_login(
    client: httpx.AsyncClient, email: str = "ada@example.com", password: str = "Analytical-1843"
) -> dict[str, str]:
    r = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
