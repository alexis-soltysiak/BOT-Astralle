from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.jobs.models import Job, JobRun
from app.features.jobs.repository import JobsRepository
from app.features.jobs.schemas import JobPatch
from app.features.jobs.workers import JOB_SPECS, get_spec


class JobsService:
    def __init__(self, repo: JobsRepository) -> None:
        self._repo = repo

    async def sync_definitions(self, session: AsyncSession) -> list[Job]:
        jobs: list[Job] = []
        for spec in JOB_SPECS:
            job = await self._repo.upsert_definition(
                session=session,
                job_key=spec.job_key,
                description=spec.description,
                interval_seconds=spec.interval_seconds,
            )
            if job.next_run_at is None:
                await self._repo.set_next_run(session, job, datetime.now(timezone.utc))
            jobs.append(job)
        return jobs

    async def list_jobs(self, session: AsyncSession) -> list[Job]:
        return await self._repo.list_jobs(session)

    async def get_job(self, session: AsyncSession, job_key: str) -> Job | None:
        return await self._repo.get_job_by_key(session, job_key)

    async def patch_job(self, session: AsyncSession, job: Job, payload: JobPatch) -> Job:
        return await self._repo.patch_job(
            session=session,
            job=job,
            enabled=payload.enabled,
            interval_seconds=payload.interval_seconds,
            description=payload.description,
        )

    async def list_runs(self, session: AsyncSession, job: Job, limit: int) -> list[JobRun]:
        return await self._repo.list_runs(session, job.id, limit)

    async def execute(self, session: AsyncSession, job_key: str) -> None:
        spec = get_spec(job_key)
        if spec is None:
            raise ValueError("unknown_job")

        job = await self._repo.get_job_by_key(session, job_key)
        if job is None:
            job = await self._repo.upsert_definition(session, spec.job_key, spec.description, spec.interval_seconds)

        if not job.enabled:
            next_run = datetime.now(timezone.utc) + timedelta(seconds=job.interval_seconds)
            await self._repo.set_next_run(session, job, next_run)
            return

        run = await self._repo.create_run(session, job)
        try:
            await spec.fn(session)
        except Exception as e:
            await self._repo.finish_run_error(session, job, run, str(e))
            next_run = datetime.now(timezone.utc) + timedelta(seconds=job.interval_seconds)
            await self._repo.set_next_run(session, job, next_run)
            return

        await self._repo.finish_run_success(session, job, run)
        next_run = datetime.now(timezone.utc) + timedelta(seconds=job.interval_seconds)
        await self._repo.set_next_run(session, job, next_run)