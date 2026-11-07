from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


def record(
    session: AsyncSession,
    action: str,
    *,
    owner_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    ip: str | None = None,
    **metadata: Any,
) -> None:
    """Add an audit row to the current transaction (committed with the business change)."""
    session.add(
        AuditEvent(
            owner_id=owner_id,
            actor_id=actor_id or owner_id,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            event_metadata=metadata,
            ip=ip,
        )
    )
