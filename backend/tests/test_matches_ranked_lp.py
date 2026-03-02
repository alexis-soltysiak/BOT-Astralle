from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.features.leaderboards.models import RankedSnapshot
from app.features.matches.service import (
    QUEUE_FLEX,
    QUEUE_SOLO,
    _ranked_context_for_player,
    _ranked_queue_type_for_queue_id,
)


class FakeLeaderboardsRepository:
    def __init__(self, before: RankedSnapshot | None, after: RankedSnapshot | None) -> None:
        self.before = before
        self.after = after

    async def get_latest_snapshot_before(self, session, tracked_player_id, queue_type, fetched_at):
        _ = (session, tracked_player_id, queue_type, fetched_at)
        return self.before

    async def get_earliest_snapshot_after(self, session, tracked_player_id, queue_type, fetched_at):
        _ = (session, tracked_player_id, queue_type, fetched_at)
        return self.after

    async def get_latest_snapshot(self, session, tracked_player_id, queue_type):
        _ = (session, tracked_player_id, queue_type)
        return self.after


def _snapshot(*, tier: str, division: str | None, lp: int, fetched_at: datetime) -> RankedSnapshot:
    return RankedSnapshot(
        tracked_player_id=uuid.uuid4(),
        platform="euw1",
        summoner_id=None,
        queue_type=QUEUE_SOLO,
        tier=tier,
        division=division,
        league_points=lp,
        wins=10,
        losses=8,
        fetched_at=fetched_at,
    )


def test_ranked_queue_type_detects_solo_and_flex() -> None:
    assert _ranked_queue_type_for_queue_id(420) == QUEUE_SOLO
    assert _ranked_queue_type_for_queue_id(440) == QUEUE_FLEX
    assert _ranked_queue_type_for_queue_id(450) is None


@pytest.mark.asyncio
async def test_ranked_context_computes_lp_delta_across_promotion() -> None:
    match_end = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    before = _snapshot(tier="GOLD", division="II", lp=80, fetched_at=match_end - timedelta(minutes=3))
    after = _snapshot(tier="GOLD", division="I", lp=15, fetched_at=match_end + timedelta(minutes=4))
    repo = FakeLeaderboardsRepository(before, after)

    ctx = await _ranked_context_for_player(
        session=None,
        leaderboards_repo=repo,
        tracked_player_id=uuid.uuid4(),
        queue_type=QUEUE_SOLO,
        match_end_ts_ms=int(match_end.timestamp() * 1000),
    )

    assert ctx["queue_type"] == QUEUE_SOLO
    assert ctx["rank_before"] == "Gold II - 80 LP"
    assert ctx["rank_after"] == "Gold I - 15 LP"
    assert ctx["rank_delta_lp"] == 35


@pytest.mark.asyncio
async def test_ranked_context_falls_back_to_latest_snapshot_when_after_is_missing() -> None:
    match_end = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    before = _snapshot(tier="GOLD", division="II", lp=80, fetched_at=match_end - timedelta(minutes=3))
    latest = _snapshot(tier="GOLD", division="I", lp=15, fetched_at=match_end + timedelta(minutes=20))
    repo = FakeLeaderboardsRepository(before, None)
    repo.after = latest

    ctx = await _ranked_context_for_player(
        session=None,
        leaderboards_repo=repo,
        tracked_player_id=uuid.uuid4(),
        queue_type=QUEUE_SOLO,
        match_end_ts_ms=int(match_end.timestamp() * 1000),
    )

    assert ctx["rank_after"] == "Gold I - 15 LP"
    assert ctx["rank_delta_lp"] == 35


@pytest.mark.asyncio
async def test_ranked_context_uses_current_snapshot_when_available() -> None:
    match_end = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    before = _snapshot(tier="GOLD", division="II", lp=80, fetched_at=match_end - timedelta(minutes=3))
    current = _snapshot(tier="GOLD", division="I", lp=15, fetched_at=match_end + timedelta(minutes=2))
    repo = FakeLeaderboardsRepository(before, None)

    ctx = await _ranked_context_for_player(
        session=None,
        leaderboards_repo=repo,
        tracked_player_id=uuid.uuid4(),
        queue_type=QUEUE_SOLO,
        match_end_ts_ms=int(match_end.timestamp() * 1000),
        current_snapshot=current,
    )

    assert ctx["rank_after"] == "Gold I - 15 LP"
    assert ctx["rank_delta_lp"] == 35
