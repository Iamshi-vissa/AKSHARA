from __future__ import annotations

import httpx
import pytest

from tests.conftest import register_and_login

pytestmark = pytest.mark.integration


async def test_health_ready_capabilities(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/health")).json() == {"status": "ok"}
    ready = (await client.get("/api/v1/ready")).json()
    assert ready["checks"]["database"] == "ok" and ready["checks"]["storage"] == "ok"
    caps = (await client.get("/api/v1/capabilities")).json()
    assert caps["product"] == "AKSHARA"
    available = {c["key"] for c in caps["capabilities"] if c["available"]}
    assert available == {"upload", "versions"}  # nothing beyond Phase 1 claims to work


async def test_error_envelope_and_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/nope", headers={"X-Request-ID": "trace-12345678"})
    assert r.status_code == 404
    assert r.headers["x-request-id"] == "trace-12345678"
    assert r.json()["error"]["request_id"] == "trace-12345678"
    bad = await client.get("/api/v1/health", headers={"X-Request-ID": "bad id\twith tab"})
    assert bad.headers["x-request-id"] != "bad id\twith tab"


async def test_jobs_empty_and_scoped(client: httpx.AsyncClient) -> None:
    headers = await register_and_login(client)
    assert (await client.get("/api/v1/jobs", headers=headers)).json() == []
    r = await client.get("/api/v1/jobs/0190f1b0-0000-7000-8000-000000000000", headers=headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "JOB_NOT_FOUND"


async def test_security_headers(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
