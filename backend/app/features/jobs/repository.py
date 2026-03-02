from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.jobs.models import Job, JobRun


class JobsRepository:
    async def list_jobs(self, session: AsyncSession) -> list[Job]:
        res = await session.execute(select(Job).order_by(Job.job_key.asc()))
        return list(res.scalars().all())

    async def get_job_by_key(self, session: AsyncSession, job_key: str) -> Job | None:
        res = await session.execute(select(Job).where(Job.job_key == job_key))
        return res.scalar_one_or_none()

    async def upsert_definition(
        self,
        session: AsyncSession,
        job_key: str,
        description: str,
        interval_seconds: int,
    ) -> Job:
        job = await self.get_job_by_key(session, job_key)
        if job is None:
            job = Job(
                job_key=job_key,
                description=description,
                interval_seconds=interval_seconds,
                enabled=True,
                last_status=None,
                last_error=None,
                last_run_at=None,
                next_run_at=datetime.now(timezone.utc),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

        changed = False
        if job.description != description:
            job.description = description
            changed = True
        if job.interval_seconds != interval_seconds:
            job.interval_seconds = interval_seconds
            changed = True
        if changed:
            await session.commit()
            await session.refresh(job)
        return job

    async def patch_job(
        self,
        session: AsyncSession,
        job: Job,
        enabled: bool | None,
        interval_seconds: int | None,
        description: str | None,
    ) -> Job:
        changed = False
        if enabled is not None and job.enabled != enabled:
            job.enabled = enabled
            changed = True
        if interval_seconds is not None and job.interval_seconds != interval_seconds:
            job.interval_seconds = interval_seconds
            changed = True
        if description is not None and job.description != description:
            job.description = description
            changed = True
        if changed:
            await session.commit()
            await session.refresh(job)
        return job

    async def create_run(self, session: AsyncSession, job: Job) -> JobRun:
        run = JobRun(job_id=job.id, status="running", error=None)
        session.add(run)
        job.last_status = "running"
        job.last_error = None
        job.last_run_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(run)
        await session.refresh(job)
        return run

    async def finish_run_success(self, session: AsyncSession, job: Job, run: JobRun) -> None:
        now = datetime.now(timezone.utc)
        run.status = "success"
        run.finished_at = now
        job.last_status = "success"
        job.last_error = None
        job.next_run_at = now.replace(microsecond=0) + (now - now)  # noop, recalculé dans service
        await session.commit()

    async def finish_run_error(self, session: AsyncSession, job: Job, run: JobRun, error: str) -> None:
        now = datetime.now(timezone.utc)
        run.status = "error"
        run.error = error
        run.finished_at = now
        job.last_status = "error"
        job.last_error = error
        await session.commit()

    async def set_next_run(self, session: AsyncSession, job: Job, next_run_at: datetime) -> None:
        job.next_run_at = next_run_at
        await session.commit()

    async def list_runs(self, session: AsyncSession, job_id: uuid.UUID, limit: int) -> list[JobRun]:
        stmt = select(JobRun).where(JobRun.job_id == job_id).order_by(desc(JobRun.started_at)).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())