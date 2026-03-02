from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.leaderboards.models import RankedSnapshot
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.leaderboards.schemas import RankedStateOut
from app.features.live_games.local_champion_map import load_local_champion_map
from app.features.live_games.repository import LiveGamesRepository
from app.features.live_games.schemas import LiveGameOut
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.infra.riot_client import RiotClient

QUEUE_SOLO = "RANKED_SOLO_5x5"
QUEUE_FLEX = "RANKED_FLEX_SR"
QUEUE_BY_ID = {
    420: QUEUE_SOLO,
    440: QUEUE_FLEX,
}
CHAMPION_SUMMARY_URL = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/en_us/v1/champion-summary.json"
)
_LOCAL_CHAMPION_MAP = load_local_champion_map()
_CHAMPION_CACHE: dict[int, dict[str, str]] = {}
_CHAMPION_CACHE_EXPIRES_AT: datetime | None = None


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


def _safe_int(value) -> int | None:  # type: ignore[no-untyped-def]
    try:
        return int(value)
    except Exception:
        return None


def _ranked_state_from_entry(queue_type: str, entry: dict | None) -> dict:
    if not isinstance(entry, dict):
        return {
            "queue_type": queue_type,
            "tier": None,
            "division": None,
            "league_points": None,
            "wins": None,
            "losses": None,
        }
    return {
        "queue_type": queue_type,
        "tier": entry.get("tier"),
        "division": entry.get("rank"),
        "league_points": entry.get("leaguePoints"),
        "wins": entry.get("wins"),
        "losses": entry.get("losses"),
    }


def _select_ranked_state(entries: list[dict], queue_id: int | None) -> dict:
    by_queue = {str(entry.get("queueType") or ""): entry for entry in entries if isinstance(entry, dict)}
    preferred_queue = QUEUE_BY_ID.get(queue_id)
    if preferred_queue:
        return _ranked_state_from_entry(preferred_queue, by_queue.get(preferred_queue))
    if QUEUE_SOLO in by_queue:
        return _ranked_state_from_entry(QUEUE_SOLO, by_queue.get(QUEUE_SOLO))
    if QUEUE_FLEX in by_queue:
        return _ranked_state_from_entry(QUEUE_FLEX, by_queue.get(QUEUE_FLEX))
    return _ranked_state_from_entry(preferred_queue or QUEUE_SOLO, None)


async def _get_champion_name_map() -> dict[int, dict[str, str]]:
    global _CHAMPION_CACHE, _CHAMPION_CACHE_EXPIRES_AT

    now = datetime.now(timezone.utc)
    if _CHAMPION_CACHE and _CHAMPION_CACHE_EXPIRES_AT is not None and now < _CHAMPION_CACHE_EXPIRES_AT:
        return _CHAMPION_CACHE

    mapping: dict[int, dict[str, str]] = dict(_LOCAL_CHAMPION_MAP)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(CHAMPION_SUMMARY_URL)
            res.raise_for_status()
            data = res.json()
    except Exception:
        _CHAMPION_CACHE = mapping
        _CHAMPION_CACHE_EXPIRES_AT = now + timedelta(hours=6)
        return _CHAMPION_CACHE

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            champion_id = _safe_int(item.get("id"))
            alias = str(item.get("alias") or "").strip()
            name = str(item.get("name") or "").strip()
            if champion_id is None or not alias:
                continue
            mapping[champion_id] = {
                "key": alias,
                "name": name or alias,
            }

    _CHAMPION_CACHE = mapping
    _CHAMPION_CACHE_EXPIRES_AT = now + timedelta(hours=6)
    return _CHAMPION_CACHE


class LiveGamesService:
    def __init__(
        self,
        repo: LiveGamesRepository,
        players_repo: TrackedPlayersRepository,
        leaderboards_repo: LeaderboardsRepository | None = None,
    ) -> None:
        self._repo = repo
        self._players_repo = players_repo
        self._leaderboards_repo = leaderboards_repo or LeaderboardsRepository()
        self._log = structlog.get_logger("live_games")

    async def _fetch_active_game_with_fallback(
        self,
        *,
        client: RiotClient,
        platform: str,
        puuid: str,
        player_id: str,
    ) -> dict | None:
        try:
            summoner = await client.get_summoner_by_puuid(platform, puuid)
        except Exception:
            self._log.exception(
                "live_game_summoner_lookup_failed",
                player_id=player_id,
                platform=platform,
            )
            raise

        summoner_id = str(summoner.get("id") or "").strip()
        if summoner_id:
            try:
                return await client.get_active_game(platform, summoner_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

        self._log.warning(
            "live_game_missing_summoner_id_using_puuid_fallback",
            player_id=player_id,
            platform=platform,
        )
        try:
            game = await client.get_active_game(platform, puuid)
            self._log.warning(
                "live_game_puuid_fallback_succeeded",
                player_id=player_id,
                platform=platform,
            )
            return game
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self._log.info(
                    "live_game_puuid_fallback_not_found",
                    player_id=player_id,
                    platform=platform,
                )
                return None
            raise

    async def _enrich_live_game_payload(
        self,
        *,
        game: dict,
        platform: str,
        client: RiotClient,
    ) -> dict:
        payload = dict(game)
        participants = payload.get("participants")
        if not isinstance(participants, list):
            return payload

        queue_id = _safe_int(payload.get("gameQueueConfigId") or payload.get("queueId"))
        try:
            champion_name_map = await _get_champion_name_map()
        except Exception:
            champion_name_map = dict(_CHAMPION_CACHE)
            if champion_name_map:
                self._log.warning(
                    "live_game_champion_map_fetch_failed_using_stale_cache",
                    champions=len(champion_name_map),
                )
            else:
                self._log.exception("live_game_champion_map_fetch_failed")

        entries_by_puuid: dict[str, list[dict]] = {}
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            puuid = str(participant.get("puuid") or "").strip()
            if not puuid or puuid in entries_by_puuid:
                continue
            try:
                entries = await client.get_league_entries_by_puuid(platform, puuid)
            except httpx.HTTPStatusError as e:
                self._log.warning(
                    "live_game_participant_rank_http_error",
                    status=e.response.status_code,
                    puuid=puuid,
                    platform=platform,
                )
                entries = []
            except Exception:
                self._log.exception(
                    "live_game_participant_rank_fetch_failed",
                    puuid=puuid,
                    platform=platform,
                )
                entries = []
            entries_by_puuid[puuid] = [entry for entry in entries if isinstance(entry, dict)]

        enriched_participants: list[dict] = []
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            row = dict(participant)
            champion_id = _safe_int(row.get("championId"))
            if champion_id is not None:
                champion_meta = champion_name_map.get(champion_id) or {}
                champion_key = str(champion_meta.get("key") or "").strip()
                champion_name = str(champion_meta.get("name") or "").strip()
                if champion_key:
                    row["championKey"] = champion_key
                if champion_name and not row.get("championName"):
                    row["championName"] = champion_name

            puuid = str(row.get("puuid") or "").strip()
            participant_entries = entries_by_puuid.get(puuid, [])
            row["soloRankedState"] = _ranked_state_from_entry(
                QUEUE_SOLO,
                next((entry for entry in participant_entries if str(entry.get("queueType") or "") == QUEUE_SOLO), None),
            )
            row["flexRankedState"] = _ranked_state_from_entry(
                QUEUE_FLEX,
                next((entry for entry in participant_entries if str(entry.get("queueType") or "") == QUEUE_FLEX), None),
            )
            row["rankedState"] = _select_ranked_state(participant_entries, queue_id)
            enriched_participants.append(row)

        payload["participants"] = enriched_participants
        return payload

    async def refresh(self, session: AsyncSession) -> dict[str, int]:
        settings = get_settings()
        if not settings.riot_api_key.strip():
            raise ValueError("missing_riot_api_key")

        players = await self._players_repo.get_all(session)
        targets = [p for p in players if p.active and p.puuid and p.platform]

        client = RiotClient(settings.riot_api_key)
        updated = 0
        skipped = 0
        errors = 0
        enriched_games_by_id: dict[str, dict] = {}

        try:
            for p in players:
                if not (p.active and p.puuid and p.platform):
                    skipped += 1
                    await self._repo.upsert_state(
                        session,
                        tracked_player_id=p.id,
                        platform=p.platform,
                        status="none",
                        game_id=None,
                        payload=None,
                    )
                    updated += 1
                    continue

                try:
                    game = await self._fetch_active_game_with_fallback(
                        client=client,
                        p.platform,  # type: ignore[arg-type]
                        p.puuid,
                        str(p.id),
                    )
                    if game is None:
                        await self._repo.upsert_state(
                            session,
                            tracked_player_id=p.id,
                            platform=p.platform,
                            status="none",
                            game_id=None,
                            payload=None,
                        )
                        updated += 1
                        continue

                    game_id = str(game.get("gameId") or "")
                    payload = game
                    if game_id:
                        cached = enriched_games_by_id.get(game_id)
                        if cached is None:
                            cached = await self._enrich_live_game_payload(
                                game=game,
                                platform=p.platform,  # type: ignore[arg-type]
                                client=client,
                            )
                            enriched_games_by_id[game_id] = cached
                        payload = cached
                    await self._repo.upsert_state(
                        session,
                        tracked_player_id=p.id,
                        platform=p.platform,
                        status="live",
                        game_id=game_id if game_id else None,
                        payload=payload,
                    )
                    updated += 1
                except httpx.HTTPStatusError as e:
                    errors += 1
                    self._log.error(
                        "live_game_fetch_http_error",
                        status=e.response.status_code,
                        player_id=str(p.id),
                        platform=p.platform,
                    )
                except Exception:
                    errors += 1
                    self._log.exception(
                        "live_game_refresh_failed",
                        player_id=str(p.id),
                        platform=p.platform,
                    )

            return {"updated": updated, "skipped": skipped, "errors": errors, "targets": len(targets)}
        finally:
            await client.aclose()

    async def list(self, session: AsyncSession, only_active: bool) -> list[LiveGameOut]:
        players = await self._players_repo.get_all(session)
        players_by_id = {str(p.id): p for p in players}
        latest = await self._leaderboards_repo.get_latest_snapshots(session)
        snaps_by_player: dict[str, dict[str, RankedSnapshot]] = {}
        for snapshot in latest:
            player_snapshots = snaps_by_player.setdefault(str(snapshot.tracked_player_id), {})
            player_snapshots[snapshot.queue_type] = snapshot

        states = await self._repo.list_states(session)
        out: list[LiveGameOut] = []
        for s in states:
            p = players_by_id.get(str(s.tracked_player_id))
            if p is None:
                continue
            if only_active and s.status != "live":
                continue
            player_snaps = snaps_by_player.get(str(p.id), {})
            out.append(
                LiveGameOut(
                    tracked_player_id=p.id,
                    puuid=p.puuid,
                    discord_display_name=p.discord_display_name,
                    game_name=p.game_name,
                    tag_line=p.tag_line,
                    platform=p.platform,
                    status=s.status,
                    game_id=s.game_id,
                    payload=s.payload,
                    fetched_at=s.fetched_at,
                    solo=_state_from_snapshot(QUEUE_SOLO, player_snaps.get(QUEUE_SOLO)),
                    flex=_state_from_snapshot(QUEUE_FLEX, player_snaps.get(QUEUE_FLEX)),
                )
            )
        return out
