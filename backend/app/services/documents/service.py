"""Document library use-cases.

Every query is scoped to the requesting user. A document owned by someone else is reported
as *not found* (never "forbidden"), so its existence is not revealed.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from anyio.to_thread import run_sync as run_in_threadpool
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage import BlobStorage
from app.core.errors import AppError, NotFoundError, UnsupportedFileError
from app.core.filesafety import FileRejected, SafetyLimits, inspect_file
from app.core.ids import uuid7
from app.db.models import Blob, Document, DocumentVersion
from app.services import audit

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean_filename(name: str) -> str:
    """Keep only the final path component, normalise Unicode, drop control characters."""
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = unicodedata.normalize("NFC", _CONTROL_RE.sub("", base)).strip()
    return base[:300] or "document"


@dataclass(frozen=True)
class VersionView:
    version: DocumentVersion
    blob: Blob


@dataclass(frozen=True)
class DocumentView:
    document: Document
    current: VersionView | None


@dataclass(frozen=True)
class Download:
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    chunks: Iterator[bytes]


class DocumentService:
    def __init__(self, session: AsyncSession, storage: BlobStorage, limits: SafetyLimits) -> None:
        self.session = session
        self.storage = storage
        self.limits = limits

    # --- create ---------------------------------------------------------------------------
    async def upload(
        self,
        owner_id: uuid.UUID,
        temp_path: Path,
        filename: str,
        title: str | None,
        ip: str | None = None,
    ) -> DocumentView:
        filename = clean_filename(filename)
        try:
            inspection = await run_in_threadpool(inspect_file, temp_path, filename, self.limits)
        except FileRejected as exc:
            audit.record(
                self.session, "document.upload_rejected", owner_id=owner_id, ip=ip, reason=exc.code
            )
            await self.session.commit()
            status = 413 if exc.code == "FILE_TOO_LARGE" else 415
            raise UnsupportedFileError(exc.message, code=exc.code, status_code=status) from exc

        stored = await run_in_threadpool(self.storage.put_file, temp_path)
        await self.session.execute(
            pg_insert(Blob)
            .values(
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                mime_type=inspection.mime_type,
                storage_key=stored.storage_key,
            )
            .on_conflict_do_nothing(index_elements=["sha256"])
        )

        doc_id, version_id = uuid7(), uuid7()
        title_clean = (title or "").strip()[:300] or PurePosixPath(filename).stem or filename
        document = Document(
            id=doc_id,
            owner_id=owner_id,
            title=title_clean,
            original_filename=filename,
            kind=inspection.kind,
            origin="uploaded",
            status="ready",
            safety_warnings=inspection.warnings,
        )
        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            number=1,
            source_blob=stored.sha256,
            created_by="upload",
            # Parsing into the canonical model arrives in Phase 2; record that honestly.
            summary={"analysis": "not_available", "reason": "Document analysis ships in Phase 2."},
        )
        self.session.add(document)
        await self.session.flush()
        self.session.add(version)
        await self.session.flush()
        document.current_version_id = version_id
        audit.record(
            self.session,
            "document.uploaded",
            owner_id=owner_id,
            subject_type="document",
            subject_id=doc_id,
            ip=ip,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            kind=inspection.kind,
            warnings=inspection.warnings,
        )
        await self.session.commit()
        return await self.get(owner_id, doc_id)

    # --- read -----------------------------------------------------------------------------
    def _owned(self, owner_id: uuid.UUID) -> Select[Document]:
        return select(Document).where(Document.owner_id == owner_id, Document.deleted_at.is_(None))

    async def _load(self, owner_id: uuid.UUID, document_id: uuid.UUID) -> Document:
        doc = await self.session.scalar(self._owned(owner_id).where(Document.id == document_id))
        if doc is None:
            raise NotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")
        return doc

    async def _version_views(self, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, VersionView]:
        if not version_ids:
            return {}
        rows = await self.session.execute(
            select(DocumentVersion, Blob)
            .join(Blob, Blob.sha256 == DocumentVersion.source_blob)
            .where(DocumentVersion.id.in_(version_ids))
        )
        return {v.id: VersionView(v, b) for v, b in rows}

    async def get(self, owner_id: uuid.UUID, document_id: uuid.UUID) -> DocumentView:
        doc = await self._load(owner_id, document_id)
        views = await self._version_views(
            [doc.current_version_id] if doc.current_version_id else []
        )
        return DocumentView(
            doc, views.get(doc.current_version_id) if doc.current_version_id else None
        )

    async def list_documents(
        self,
        owner_id: uuid.UUID,
        *,
        kind: str | None = None,
        q: str | None = None,
        cursor: uuid.UUID | None = None,
        limit: int = 25,
    ) -> tuple[list[DocumentView], uuid.UUID | None]:
        stmt = self._owned(owner_id)
        if kind:
            stmt = stmt.where(Document.kind == kind)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(Document.title.ilike(f"%{escaped}%", escape="\\"))
        if cursor:
            stmt = stmt.where(Document.id < cursor)  # UUIDv7 ids are time-ordered
        docs = list(
            (await self.session.scalars(stmt.order_by(Document.id.desc()).limit(limit + 1))).all()
        )
        next_cursor = docs[limit - 1].id if len(docs) > limit else None
        docs = docs[:limit]
        views = await self._version_views(
            [d.current_version_id for d in docs if d.current_version_id]
        )
        return [
            DocumentView(d, views.get(d.current_version_id) if d.current_version_id else None)
            for d in docs
        ], next_cursor

    async def stats(self, owner_id: uuid.UUID) -> dict[str, object]:
        owned = self._owned(owner_id).subquery()
        by_kind_rows = await self.session.execute(
            select(owned.c.kind, func.count()).group_by(owned.c.kind)
        )
        by_kind = {k: int(n) for k, n in by_kind_rows}
        versions = await self.session.scalar(
            select(func.count(DocumentVersion.id)).join(
                owned, owned.c.id == DocumentVersion.document_id
            )
        )
        distinct_blobs = (
            select(DocumentVersion.source_blob)
            .join(owned, owned.c.id == DocumentVersion.document_id)
            .distinct()
            .subquery()
        )
        stored = await self.session.scalar(
            select(func.coalesce(func.sum(Blob.size_bytes), 0)).where(
                Blob.sha256.in_(select(distinct_blobs.c.source_blob))
            )
        )
        return {
            "documents": sum(by_kind.values()),
            "versions": int(versions or 0),
            "stored_bytes": int(stored or 0),
            "by_kind": by_kind,
        }

    async def versions(self, owner_id: uuid.UUID, document_id: uuid.UUID) -> list[VersionView]:
        await self._load(owner_id, document_id)
        rows = await self.session.execute(
            select(DocumentVersion, Blob)
            .join(Blob, Blob.sha256 == DocumentVersion.source_blob)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.number.desc())
        )
        return [VersionView(v, b) for v, b in rows]

    async def download(
        self, owner_id: uuid.UUID, version_id: uuid.UUID, ip: str | None = None
    ) -> Download:
        row = (
            await self.session.execute(
                select(DocumentVersion, Document, Blob)
                .join(Document, Document.id == DocumentVersion.document_id)
                .join(Blob, Blob.sha256 == DocumentVersion.source_blob)
                .where(
                    DocumentVersion.id == version_id,
                    Document.owner_id == owner_id,
                    Document.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            raise NotFoundError("Version not found.", code="VERSION_NOT_FOUND")
        version, doc, blob = row
        if not self.storage.exists(blob.storage_key):
            raise AppError("The stored file is unavailable.", code="BLOB_MISSING", status_code=500)
        audit.record(
            self.session,
            "document.downloaded",
            owner_id=owner_id,
            subject_type="document_version",
            subject_id=version.id,
            ip=ip,
        )
        await self.session.commit()
        stem = PurePosixPath(doc.original_filename).stem
        suffix = f".{doc.kind}"
        filename = (
            doc.original_filename if version.number == 1 else f"{stem}.v{version.number}{suffix}"
        )
        return Download(
            filename=filename,
            mime_type=blob.mime_type,
            size_bytes=blob.size_bytes,
            sha256=blob.sha256,
            chunks=self.storage.open(blob.storage_key),
        )

    # --- update / delete ---------------------------------------------------------------------
    async def rename(self, owner_id: uuid.UUID, document_id: uuid.UUID, title: str) -> DocumentView:
        doc = await self._load(owner_id, document_id)
        doc.title = title.strip()[:300]
        await self.session.commit()
        return await self.get(owner_id, document_id)

    async def soft_delete(
        self, owner_id: uuid.UUID, document_id: uuid.UUID, ip: str | None = None
    ) -> None:
        """Hide the document. Blobs and versions are retained (originals are never destroyed)."""
        doc = await self._load(owner_id, document_id)
        doc.deleted_at = datetime.now(UTC)
        audit.record(
            self.session,
            "document.deleted",
            owner_id=owner_id,
            subject_type="document",
            subject_id=doc.id,
            ip=ip,
        )
        await self.session.commit()
