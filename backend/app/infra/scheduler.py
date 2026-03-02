from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.features.jobs.service import JobsService
from app.features.jobs.workers import JOB_SPECS


class AppScheduler:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], jobs: JobsService) -> None:
        self._sessionmaker = sessionmaker
        self._jobs = jobs
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        for spec in JOB_SPECS:
            self._scheduler.add_job(
                self._run_job,
                trigger="interval",
                seconds=spec.interval_seconds,
                id=spec.job_key,
                args=[spec.job_key],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        self._scheduler.start()

    async def _run_job(self, job_key: str) -> None:
        async with self._sessionmaker() as session:
            await self._jobs.execute(session, job_key)

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)