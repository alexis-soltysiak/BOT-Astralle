from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.matches.daily_lp_recap import enqueue_daily_lp_recap_event


async def ingest_daily_lp_recap_job(session: AsyncSession) -> None:
    await enqueue_daily_lp_recap_event(session)
