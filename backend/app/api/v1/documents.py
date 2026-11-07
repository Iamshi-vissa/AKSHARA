from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    ClientDep,
    CurrentUser,
    LimitsDep,
    SessionDep,
    StorageDep,
    parse_uuid,
)
from app.core.errors import AppError, FileTooLargeError
from app.schemas.common import Page
from app.schemas.documents import DocumentOut, DocumentStats, DocumentUpdate, VersionOut
from app.services.documents.service import DocumentService, DocumentView, VersionView

router = APIRouter(tags=["documents"])

_CHUNK = 1024 * 1024


def version_out(view: VersionView) -> VersionOut:
    v, b = view.version, view.blob
    return VersionOut(
        id=v.id,
        document_id=v.document_id,
        number=v.number,
        parent_version_id=v.parent_version_id,
        created_by=v.created_by,
        size_bytes=b.size_bytes,
        sha256=b.sha256,
        summary=v.summary,
        created_at=v.created_at,
    )


def document_out(view: DocumentView) -> DocumentOut:
    d = view.document
    return DocumentOut(
        id=d.id,
        title=d.title,
        original_filename=d.original_filename,
        kind=d.kind,
        origin=d.origin,
        status=d.status,
        safety_warnings=list(d.safety_warnings or []),
        current_version=version_out(view.current) if view.current else None,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


async def _spool(upload: UploadFile, max_bytes: int) -> Path:
    """Copy the upload to a private temp file, aborting as soon as the size limit is passed."""
    fd, name = tempfile.mkstemp(prefix="akshara-upload-")
    written = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await upload.read(_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise FileTooLargeError(
                        f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.",
                    )
                out.write(chunk)
    except BaseException:
        os.unlink(name)
        raise
    return Path(name)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
    client: ClientDep,
    file: Annotated[UploadFile, File(description="A .docx, .pdf or .pptx file")],
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> DocumentOut:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limits.max_bytes + 64 * 1024:
        raise FileTooLargeError(
            f"The file is larger than the {limits.max_bytes // (1024 * 1024)} MB limit."
        )
    if not file.filename:
        raise AppError("A file name is required.", code="MISSING_FILENAME")
    temp = await _spool(file, limits.max_bytes)
    try:
        view = await DocumentService(session, storage, limits).upload(
            user.id, temp, file.filename, title, ip=client.ip
        )
    finally:
        temp.unlink(missing_ok=True)
    return document_out(view)


@router.get("/documents", response_model=Page[DocumentOut])
async def list_documents(
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
    kind: Literal["docx", "pdf", "pptx"] | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Page[DocumentOut]:
    views, next_cursor = await DocumentService(session, storage, limits).list_documents(
        user.id, kind=kind, q=q, cursor=parse_uuid(cursor), limit=limit
    )
    return Page(
        items=[document_out(v) for v in views],
        next_cursor=str(next_cursor) if next_cursor else None,
    )


@router.get("/documents/stats", response_model=DocumentStats)
async def document_stats(
    user: CurrentUser, session: SessionDep, storage: StorageDep, limits: LimitsDep
) -> DocumentStats:
    return DocumentStats.model_validate(
        await DocumentService(session, storage, limits).stats(user.id)
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
) -> DocumentOut:
    return document_out(await DocumentService(session, storage, limits).get(user.id, document_id))


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def rename_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
) -> DocumentOut:
    view = await DocumentService(session, storage, limits).rename(user.id, document_id, body.title)
    return document_out(view)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
    client: ClientDep,
) -> Response:
    await DocumentService(session, storage, limits).soft_delete(user.id, document_id, client.ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/documents/{document_id}/versions", response_model=list[VersionOut])
async def list_versions(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
) -> list[VersionOut]:
    views = await DocumentService(session, storage, limits).versions(user.id, document_id)
    return [version_out(v) for v in views]


@router.get("/versions/{version_id}/file")
async def download_version(
    version_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    limits: LimitsDep,
    client: ClientDep,
) -> StreamingResponse:
    dl = await DocumentService(session, storage, limits).download(user.id, version_id, client.ip)
    ascii_name = dl.filename.encode("ascii", "ignore").decode().replace('"', "") or "document"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(dl.filename)}"
    return StreamingResponse(
        dl.chunks,
        media_type=dl.mime_type,
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(dl.size_bytes),
            "ETag": f'"{dl.sha256}"',
            "X-Content-SHA256": dl.sha256,
            "Cache-Control": "private, no-store",
        },
    )
