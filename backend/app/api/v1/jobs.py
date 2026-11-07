from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.jobs import JobOut
from app.services.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@router.get("", response_model=list[JobOut])
async def list_jobs(
    user: CurrentUser,
    session: SessionDep,
    status: JobStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[JobOut]:
    jobs = await JobService(session).list_jobs(user.id, status=status, limit=limit)
    return [JobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> JobOut:
    return JobOut.model_validate(await JobService(session).get(user.id, job_id))
