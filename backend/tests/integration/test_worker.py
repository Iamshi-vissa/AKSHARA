"""Starts a real Celery worker against Redis and runs the ping task end to end."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_celery_worker_roundtrip() -> None:
    redis_url = os.environ.get("AKSHARA_TEST_REDIS_URL", "redis://localhost:6379/15")
    env = {**os.environ, "AKSHARA_REDIS_URL": redis_url}
    backend = Path(__file__).resolve().parents[2]
    worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.workers.celery_app",
            "worker",
            "--pool=solo",
            "--loglevel=WARNING",
            "-n",
            "pytest@%h",
        ],
        cwd=backend,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        code = (
            "from app.workers.celery_app import celery_app;"
            "r = celery_app.send_task('system.ping');"
            "print(r.get(timeout=30))"
        )
        deadline = time.time() + 60
        out = ""
        while time.time() < deadline:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=backend,
                env=env,
                capture_output=True,
                text=True,
                timeout=45,
            )
            out = proc.stdout.strip()
            if out == "pong":
                break
        assert out == "pong"
    finally:
        worker.terminate()
        worker.wait(timeout=20)
