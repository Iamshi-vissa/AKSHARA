from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="system.ping")  # type: ignore[untyped-decorator]
def ping() -> str:
    return "pong"
