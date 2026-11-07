from __future__ import annotations

from typing import Literal

from app.schemas.common import ApiModel


class Capability(ApiModel):
    key: str
    label: str
    available: bool
    phase: int
    note: str


class CapabilitiesOut(ApiModel):
    product: Literal["AKSHARA"] = "AKSHARA"
    version: str
    capabilities: list[Capability]


class ReadyOut(ApiModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, str]
