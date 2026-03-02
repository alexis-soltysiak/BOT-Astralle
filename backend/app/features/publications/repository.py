from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.publications.models import PublicationEvent
from app.features.publications.service import next_available_delta


class PublicationsRepository:
    async def try_create_event(
        self,
        session: AsyncSession,
        event_type: str,
        dedupe_key: str,
        payload: dict,
        max_attempts: int,
    ) -> bool:
        stmt = (
            insert(PublicationEvent)
            .values(
                event_type=event_type,
                dedupe_key=dedupe_key,
                status="pending",
                attempts=0,
                max_attempts=max_attempts,
                payload=payload,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(PublicationEvent.id)
        )
        res = await session.execute(stmt)
        return res.first() is not None

    async def list_events(
        self, session: AsyncSession, status: str | None, limit: int
    ) -> list[PublicationEvent]:
        stmt = select(PublicationEvent).order_by(PublicationEvent.created_at.desc()).limit(limit)
        if status is not None:
            stmt = stmt.where(PublicationEvent.status == status)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def claim(
        self,
        session: AsyncSession,
        consumer_id: str,
        limit: int,
        lease_seconds: int,
    ) -> list[PublicationEvent]:
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(seconds=lease_seconds)

        stmt = (
            select(PublicationEvent)
            .where(
                PublicationEvent.available_at <= now,
                PublicationEvent.status.in_(["pending", "retry", "claimed"]),
                or_(PublicationEvent.claimed_until.is_(None), PublicationEvent.claimed_until < now),
                PublicationEvent.attempts < PublicationEvent.max_attempts,
            )
            .order_by(PublicationEvent.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )

        res = await session.execute(stmt)
        rows = list(res.scalars().all())
        if not rows:
            return []

        for r in rows:
            r.status = "claimed"
            r.claimed_by = consumer_id
            r.claimed_until = lease_until
            r.attempts += 1

        await session.commit()

        for r in rows:
            await session.refresh(r)

        return rows

    async def ack(
        self, session: AsyncSession, event_id: uuid.UUID, ok: bool, error: str | None
    ) -> PublicationEvent | None:
        res = await session.execute(select(PublicationEvent).where(PublicationEvent.id == event_id))
        ev = res.scalar_one_or_none()
        if ev is None:
            return None

        now = datetime.now(timezone.utc)

        ev.claimed_by = None
        ev.claimed_until = None

        if ok:
            ev.status = "sent"
            ev.last_error = None
            ev.available_at = now
            await session.commit()
            await session.refresh(ev)
            return ev

        ev.last_error = error or "unknown_error"
        if ev.attempts >= ev.max_attempts:
            ev.status = "dead"
            ev.available_at = now
            await session.commit()
            await session.refresh(ev)
            return ev

        ev.status = "retry"
        ev.available_at = now + next_available_delta(ev.attempts)
        await session.commit()
        await session.refresh(ev)
        return ev

    async def delete_by_dedupe_keys(self, session: AsyncSession, dedupe_keys: list[str]) -> None:
        if not dedupe_keys:
            return
        await session.execute(delete(PublicationEvent).where(PublicationEvent.dedupe_key.in_(dedupe_keys)))
        await session.commit()
