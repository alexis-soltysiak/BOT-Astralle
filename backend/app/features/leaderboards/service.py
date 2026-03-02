from __future__ import annotations

from collections import defaultdict

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.leaderboards.models import RankedSnapshot
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.leaderboards.schemas import LeaderboardEntryOut, RankedStateOut
from app.features.leaderboards.selectors import rank_sort_key
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.infra.riot_client import RiotClient


QUEUE_SOLO = "RANKED_SOLO_5x5"
QUEUE_FLEX = "RANKED_FLEX_SR"


def _state_from_snapshot(queue_type: str, snapshot: RankedSnapshot | None) -> RankedStateOut:
    return RankedStateOut(
        queue_type=queue_type,
        tier=None if snapshot is None else snapshot.tier,
        division=None if snapshot is None else snapshot.division,
        league_points=None if snapshot is None else snapshot.league_points,
        wins=None if snapshot is None else snapshot.wins,
        losses=None if snapshot is None else snapshot.losses,
        fetched_at=None if snapshot is None else snapshot.fetched_at,
    )


def _state_sort_key(state: RankedStateOut) -> tuple[int, int, int]:
    return rank_sort_key(state.tier, state.division, state.league_points)


def _row_sort_key(row: LeaderboardEntryOut, sort: str) -> tuple[int, int, int]:
    return _state_sort_key(row.flex if sort == "flex" else row.solo)


class LeaderboardsService:
    def __init__(self, repo: LeaderboardsRepository, players_repo: TrackedPlayersRepository) -> None:
        self._repo = repo
        self._players_repo = players_repo
        self._log = structlog.get_logger("leaderboards")

    async def refresh(self, session: AsyncSession) -> dict[str, int]:
        settings = get_settings()
        if not settings.riot_api_key.strip():
            raise ValueError("missing_riot_api_key")

        players = await self._players_repo.get_all(session)
        targets = [p for p in players if p.active and p.puuid and p.platform]

        client = RiotClient(settings.riot_api_key)
        created = 0
        errors = 0

        try:
            for p in targets:
                try:
                    entries = await client.get_league_entries_by_puuid(p.platform, p.puuid)  # type: ignore[arg-type]
                    by_queue: dict[str, dict] = {e.get("queueType"): e for e in entries if "queueType" in e}

                    snapshots: list[RankedSnapshot] = []
                    for q in (QUEUE_SOLO, QUEUE_FLEX):
                        e = by_queue.get(q)
                        if e is None:
                            snapshots.append(
                                RankedSnapshot(
                                    tracked_player_id=p.id,
                                    platform=p.platform,  # type: ignore[arg-type]
                                    summoner_id=None,
                                    queue_type=q,
                                    tier=None,
                                    division=None,
                                    league_points=None,
                                    wins=None,
                                    losses=None,
                                )
                            )
                            continue

                        snapshots.append(
                            RankedSnapshot(
                                tracked_player_id=p.id,
                                platform=p.platform,  # type: ignore[arg-type]
                                summoner_id=None,
                                queue_type=q,
                                tier=e.get("tier"),
                                division=e.get("rank"),
                                league_points=e.get("leaguePoints"),
                                wins=e.get("wins"),
                                losses=e.get("losses"),
                            )
                        )

                    await self._repo.insert_snapshots(session, snapshots)
                    created += len(snapshots)

                except httpx.HTTPStatusError as e:
                    errors += 1
                    self._log.error("riot_http_error", status=e.response.status_code, player_id=str(p.id))
                except Exception:
                    errors += 1
                    self._log.exception("leaderboard_refresh_failed", player_id=str(p.id))

            skipped = len(players) - len(targets)
            return {"created": created, "skipped": skipped, "errors": errors, "targets": len(targets)}
        finally:
            await client.aclose()

    async def get_leaderboard(self, session: AsyncSession, sort: str) -> list[LeaderboardEntryOut]:
        players = await self._players_repo.get_all(session)
        players = [p for p in players if p.active]

        latest = await self._repo.get_latest_snapshots(session)
        snap_by_player: dict[str, dict[str, RankedSnapshot]] = defaultdict(dict)
        for s in latest:
            snap_by_player[str(s.tracked_player_id)][s.queue_type] = s

        rows_by_owner: dict[str, LeaderboardEntryOut] = {}
        for p in players:
            solo = snap_by_player.get(str(p.id), {}).get(QUEUE_SOLO)
            flex = snap_by_player.get(str(p.id), {}).get(QUEUE_FLEX)

            row = LeaderboardEntryOut(
                tracked_player_id=p.id,
                discord_display_name=p.discord_display_name,
                game_name=p.game_name,
                tag_line=p.tag_line,
                platform=p.platform,
                solo=_state_from_snapshot(QUEUE_SOLO, solo),
                flex=_state_from_snapshot(QUEUE_FLEX, flex),
            )
            owner_key = p.discord_user_id or str(p.id)
            current = rows_by_owner.get(owner_key)
            if current is None:
                rows_by_owner[owner_key] = row
                continue

            best_solo = row.solo if _state_sort_key(row.solo) > _state_sort_key(current.solo) else current.solo
            best_flex = row.flex if _state_sort_key(row.flex) > _state_sort_key(current.flex) else current.flex

            if _row_sort_key(row, sort) > _row_sort_key(current, sort):
                rows_by_owner[owner_key] = LeaderboardEntryOut(
                    tracked_player_id=row.tracked_player_id,
                    discord_display_name=row.discord_display_name,
                    game_name=row.game_name,
                    tag_line=row.tag_line,
                    platform=row.platform,
                    solo=best_solo,
                    flex=best_flex,
                )
            else:
                rows_by_owner[owner_key] = LeaderboardEntryOut(
                    tracked_player_id=current.tracked_player_id,
                    discord_display_name=current.discord_display_name,
                    game_name=current.game_name,
                    tag_line=current.tag_line,
                    platform=current.platform,
                    solo=best_solo,
                    flex=best_flex,
                )

        rows = list(rows_by_owner.values())

        if sort == "flex":
            rows.sort(
                key=lambda r: rank_sort_key(r.flex.tier, r.flex.division, r.flex.league_points),
                reverse=True,
            )
            return rows

        rows.sort(
            key=lambda r: rank_sort_key(r.solo.tier, r.solo.division, r.solo.league_points),
            reverse=True,
        )
        return rows
