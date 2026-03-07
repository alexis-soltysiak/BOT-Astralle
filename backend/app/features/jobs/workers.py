from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.leaderboards.ingest import refresh_leaderboards_job
from app.features.live_games.ingest import refresh_live_games_job
from app.features.matches.ingest import ingest_matches_job
from app.features.matches.recap_ingest import ingest_daily_lp_recap_job
JobFn = Callable[[AsyncSession], Awaitable[None]]


@dataclass(frozen=True)
class JobSpec:
    job_key: str
    description: str
    interval_seconds: int
    fn: JobFn
    trigger: str = "interval"
    hour: int | None = None
    minute: int | None = None


async def heartbeat(_: AsyncSession) -> None:
    return


JOB_SPECS: list[JobSpec] = [
    JobSpec(
        job_key="heartbeat",
        description="Internal heartbeat to validate scheduler loop",
        interval_seconds=60,
        fn=heartbeat,
    ),
    JobSpec(
        job_key="leaderboards_refresh",
        description="Refresh ranked snapshots (SoloQ + Flex) for tracked players",
        interval_seconds=3600,
        fn=refresh_leaderboards_job,
    ),
    JobSpec(
        job_key="live_games_refresh",
        description="Refresh live game states for tracked players",
        interval_seconds=60,
        fn=refresh_live_games_job,
    ),
    JobSpec(
        job_key="matches_ingest",
        description="Ingest latest completed matches and create publication events",
        interval_seconds=60,
        fn=ingest_matches_job,
    ),
    JobSpec(
        job_key="daily_lp_recap",
        description="Publish daily LP recap at 23:00 local scheduler time",
        interval_seconds=86400,
        fn=ingest_daily_lp_recap_job,
        trigger="cron",
        hour=23,
        minute=0,
    ),
]


def get_spec(job_key: str) -> JobSpec | None:
    for spec in JOB_SPECS:
        if spec.job_key == job_key:
            return spec
    return None
