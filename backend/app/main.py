"""AKSHARA API application factory."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis

from app import __version__
from app.adapters.storage import LocalBlobStorage
from app.api.deps import AppState
from app.api.v1 import auth, documents, jobs, system
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.ids import uuid7
from app.core.logging import configure_logging, request_id_var
from app.core.ratelimit import MemoryRateLimiter, RateLimiter, RedisRateLimiter
from app.db.session import make_engine, make_sessionmaker

_RID_RE = re.compile(r"[A-Za-z0-9._-]{8,64}")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings)
        redis: Redis | None = None
        limiter: RateLimiter
        if settings.rate_limit_backend == "redis":
            redis = Redis.from_url(settings.redis_url)
            limiter = RedisRateLimiter(redis)
        else:
            limiter = MemoryRateLimiter()
        app.state.akshara = AppState(
            settings=settings,
            sessionmaker=make_sessionmaker(engine),
            storage=LocalBlobStorage(settings.storage_root),
            rate_limiter=limiter,
            redis=redis,
        )
        try:
            yield
        finally:
            if redis is not None:
                await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="AKSHARA API",
        version=__version__,
        description="AKSHARA — Intelligence Behind Every Document.",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _RID_RE.fullmatch(incoming) else str(uuid7())
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    for router in (system.router, auth.router, documents.router, jobs.router):
        app.include_router(router, prefix="/api/v1")
    return app
