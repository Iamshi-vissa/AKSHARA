"""Celery application. Workers run the same codebase as the API (decision D1).

Queues (from Phase 2 on): parse, render, inspect, llm, export, research. Phase 1 ships only a
``system.ping`` task used to verify the broker and worker wiring end to end.
"""

from __future__ import annotations

import os

from celery import Celery

broker = os.environ.get("AKSHARA_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("akshara", broker=broker, backend=broker, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    task_default_queue="default",
    broker_connection_retry_on_startup=True,
)
