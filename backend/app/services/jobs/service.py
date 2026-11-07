"""Background job tracking.

Phase 1 provides the job table and read API. The first jobs (parse and render) are created in
Phase 2; until then the list is honestly empty.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Job


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_jobs(
        self, owner_id: uuid.UUID, *, status: str | None = None, limit: int = 50
    ) -> list[Job]:
        stmt = select(Job).where(Job.owner_id == owner_id)
        if status:
            stmt = stmt.where(Job.status == status)
        return list((await self.session.scalars(stmt.order_by(Job.id.desc()).limit(limit))).all())

    async def get(self, owner_id: uuid.UUID, job_id: uuid.UUID) -> Job:
        job = await self.session.scalar(
            select(Job).where(Job.id == job_id, Job.owner_id == owner_id)
        )
        if job is None:
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        return job
