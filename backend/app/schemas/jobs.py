from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ApiModel


class JobOut(ApiModel):
    id: uuid.UUID
    type: str
    status: str
    progress: float
    subject_type: str | None
    subject_id: uuid.UUID | None
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
