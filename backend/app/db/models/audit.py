from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    """Append-only security and data-access log. Never stores document content."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_owner_created", "owner_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column()
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID | None] = mapped_column()
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
