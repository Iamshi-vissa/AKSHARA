from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import StateDep
from app.schemas.system import CapabilitiesOut, ReadyOut
from app.services.capabilities import CAPABILITIES

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadyOut)
async def ready(state: StateDep) -> ReadyOut:
    checks: dict[str, str] = {}
    try:
        async with state.sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    if state.redis is not None:
        try:
            await state.redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
    else:
        checks["redis"] = "not_configured"
    checks["storage"] = "ok" if state.storage.healthy() else "unavailable"
    degraded = any(v == "unavailable" for v in checks.values())
    return ReadyOut(status="degraded" if degraded else "ready", checks=checks)


@router.get("/capabilities", response_model=CapabilitiesOut)
async def capabilities() -> CapabilitiesOut:
    return CapabilitiesOut(version=__version__, capabilities=CAPABILITIES)
