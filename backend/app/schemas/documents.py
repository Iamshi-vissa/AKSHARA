from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import ApiModel

DocumentKind = Literal["docx", "pdf", "pptx"]


class VersionOut(ApiModel):
    id: uuid.UUID
    document_id: uuid.UUID
    number: int
    parent_version_id: uuid.UUID | None
    created_by: str
    size_bytes: int
    sha256: str
    summary: dict[str, Any]
    created_at: datetime


class DocumentOut(ApiModel):
    id: uuid.UUID
    title: str
    original_filename: str
    kind: DocumentKind
    origin: str
    status: str
    safety_warnings: list[str]
    current_version: VersionOut | None
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(ApiModel):
    title: str = Field(min_length=1, max_length=300)


class DocumentStats(ApiModel):
    documents: int
    versions: int
    stored_bytes: int
    by_kind: dict[str, int]
