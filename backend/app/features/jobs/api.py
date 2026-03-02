from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.features.jobs.repository import JobsRepository
from app.features.jobs.schemas import JobOut, JobPatch, JobRunOut
from app.features.jobs.service import JobsService

router = APIRouter(tags=["jobs"])


def get_service() -> JobsService:
    return JobsService(JobsRepository())


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    service: JobsService = Depends(get_service),
) -> list[JobOut]:
    return await service.list_jobs(session)


@router.patch("/jobs/{job_key}", response_model=JobOut)
async def patch_job(
    job_key: str,
    payload: JobPatch,
    session: AsyncSession = Depends(get_session),
    service: JobsService = Depends(get_service),
) -> JobOut:
    job = await service.get_job(session, job_key)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    return await service.patch_job(session, job, payload)


@router.get("/jobs/{job_key}/runs", response_model=list[JobRunOut])
async def list_job_runs(
    job_key: str,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    service: JobsService = Depends(get_service),
) -> list[JobRunOut]:
    job = await service.get_job(session, job_key)
    if job is None:
        raise HTTPException(status_code=404, detail="not_found")
    return await service.list_runs(session, job, limit)


@router.post("/jobs/{job_key}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_job_now(
    job_key: str,
    session: AsyncSession = Depends(get_session),
    service: JobsService = Depends(get_service),
) -> dict[str, str]:
    try:
        await service.execute(session, job_key)
        return {"status": "queued"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))