from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.leaderboards.models import RankedSnapshot
from app.features.leaderboards.repository import LeaderboardsRepository
from app.features.live_games.repository import LiveGamesRepository
from app.features.matches.models import Match, MatchParticipant
from app.features.matches.repository import MatchesRepository
from app.features.publications.repository import PublicationsRepository
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.infra.riot_client import RiotClient
from app.features.matches.schemas import MatchSummaryOut, MatchParticipantOut
from app.features.scoring.engine import compute_match_scoring
from app.features.scoring.models import MatchScore
from sqlalchemy import select

QUEUE_SOLO = "RANKED_SOLO_5x5"
QUEUE_FLEX = "RANKED_FLEX_SR"
RANKED_QUEUE_BY_ID = {
    420: QUEUE_SOLO,
    440: QUEUE_FLEX,
}
TIER_ORDER = [
    "IRON",
    "BRONZE",
    "SILVER",
    "GOLD",
    "PLATINUM",
    "EMERALD",
    "DIAMOND",
    "MASTER",
    "GRANDMASTER",
    "CHALLENGER",
]
DIVISION_ORDER = {
    "IV": 0,
    "III": 1,
    "II": 2,
    "I": 3,
}


def _is_remake_match_payload(match_payload: dict) -> bool:
    info = match_payload.get("info")
    if not isinstance(info, dict):
        return False

    participants = info.get("participants")
    if not isinstance(participants, list):
        return False

    for participant in participants:
        if isinstance(participant, dict) and participant.get("gameEndedInEarlySurrender") is True:
            return True
    return False


def _ranked_queue_type_for_queue_id(queue_id: int | None) -> str | None:
    if queue_id is None:
        return None
    return RANKED_QUEUE_BY_ID.get(queue_id)


def _match_game_id(match_payload: dict, riot_match_id: str | None = None) -> str | None:
    info = match_payload.get("info")
    if isinstance(info, dict):
        raw_game_id = info.get("gameId")
        if raw_game_id is not None:
            return str(raw_game_id).strip() or None

    raw_match_id = str((match_payload.get("metadata") or {}).get("matchId") or riot_match_id or "").strip()
    if "_" not in raw_match_id:
        return None
    _, _, suffix = raw_match_id.rpartition("_")
    return suffix or None


def _snapshot_rank_label(snapshot: Any | None) -> str | None:
    if snapshot is None or not getattr(snapshot, "tier", None):
        return None
    tier = str(getattr(snapshot, "tier", "") or "")
    division = getattr(snapshot, "division", None)
    lp = getattr(snapshot, "league_points", None)
    lp_value = lp if lp is not None else 0
    if division:
        return f"{tier.title()} {division} - {lp_value} LP"
    return f"{tier.title()} - {lp_value} LP"


def _snapshot_total_lp(snapshot: Any | None) -> int | None:
    if snapshot is None or not getattr(snapshot, "tier", None) or getattr(snapshot, "league_points", None) is None:
        return None

    tier = str(getattr(snapshot, "tier")).upper().strip()
    if tier not in TIER_ORDER:
        return None
    tier_index = TIER_ORDER.index(tier)

    if tier in {"MASTER", "GRANDMASTER", "CHALLENGER"}:
        return tier_index * 400 + int(getattr(snapshot, "league_points"))

    division = str(getattr(snapshot, "division", None) or "").upper().strip()
    if division not in DIVISION_ORDER:
        return None
    division_index = DIVISION_ORDER[division]
    return tier_index * 400 + division_index * 100 + int(getattr(snapshot, "league_points"))


def _snapshot_from_league_entry(
    *,
    tracked_player_id,
    platform: str,
    queue_type: str,
    entry: dict,
) -> RankedSnapshot | None:
    if not isinstance(entry, dict):
        return None
    if str(entry.get("queueType") or "").strip() != queue_type:
        return None
    return RankedSnapshot(
        tracked_player_id=tracked_player_id,
        platform=platform,
        summoner_id=None,
        queue_type=queue_type,
        tier=entry.get("tier"),
        division=entry.get("rank"),
        league_points=entry.get("leaguePoints"),
        wins=entry.get("wins"),
        losses=entry.get("losses"),
        fetched_at=datetime.now(timezone.utc),
    )


async def _ranked_context_for_player(
    session: AsyncSession,
    leaderboards_repo: LeaderboardsRepository,
    tracked_player_id,
    queue_type: str,
    match_end_ts_ms: int | None,
    before_snapshot: Any | None = None,
    current_snapshot: RankedSnapshot | None = None,
) -> dict[str, object]:
    if match_end_ts_ms is None or match_end_ts_ms <= 0:
        return {"queue_type": queue_type}

    match_end = datetime.fromtimestamp(match_end_ts_ms / 1000, tz=timezone.utc)
    before = before_snapshot
    if before is None:
        before = await leaderboards_repo.get_latest_snapshot_before(session, tracked_player_id, queue_type, match_end)
    after = await leaderboards_repo.get_earliest_snapshot_after(session, tracked_player_id, queue_type, match_end)
    if after is None and current_snapshot is not None and current_snapshot.fetched_at >= match_end:
        after = current_snapshot
    if after is None:
        latest = await leaderboards_repo.get_latest_snapshot(session, tracked_player_id, queue_type)
        if latest is not None and latest.fetched_at >= match_end:
            after = latest

    before_total_lp = _snapshot_total_lp(before)
    after_total_lp = _snapshot_total_lp(after)
    rank_delta_lp = None
    if before_total_lp is not None and after_total_lp is not None:
        rank_delta_lp = after_total_lp - before_total_lp

    return {
        "queue_type": queue_type,
        "rank_before": _snapshot_rank_label(before),
        "rank_after": _snapshot_rank_label(after),
        "rank_delta_lp": rank_delta_lp,
    }


def _payload_has_ranked_context(payload: dict) -> bool:
    return any(key in payload for key in ("rank_before", "rank_after", "rank_delta_lp"))


class MatchesService:
    def __init__(
        self,
        repo: MatchesRepository,
        players_repo: TrackedPlayersRepository,
        publications_repo: PublicationsRepository,
        leaderboards_repo: LeaderboardsRepository,
        live_games_repo: LiveGamesRepository,
    ) -> None:
        self._repo = repo
        self._players_repo = players_repo
        self._publications_repo = publications_repo
        self._leaderboards_repo = leaderboards_repo
        self._live_games_repo = live_games_repo
        self._log = structlog.get_logger("matches")

    async def list(self, session: AsyncSession, limit: int) -> list[Match]:
        return await self._repo.list_matches(session, limit)

    async def get(self, session: AsyncSession, riot_match_id: str) -> Match | None:
        return await self._repo.get_by_riot_id(session, riot_match_id)

    async def _current_rank_snapshot(
        self,
        *,
        settings,
        riot_client: RiotClient | None,
        tracked_player,
        queue_type: str,
    ) -> tuple[RankedSnapshot | None, RiotClient | None]:
        current_snapshot = None
        if not (settings.riot_api_key.strip() and tracked_player.platform and tracked_player.puuid):
            return current_snapshot, riot_client

        if riot_client is None:
            riot_client = RiotClient(settings.riot_api_key)
        entries = await riot_client.get_league_entries_by_puuid(tracked_player.platform, tracked_player.puuid)
        for entry in entries:
            current_snapshot = _snapshot_from_league_entry(
                tracked_player_id=tracked_player.id,
                platform=tracked_player.platform,
                queue_type=queue_type,
                entry=entry,
            )
            if current_snapshot is not None:
                break
        return current_snapshot, riot_client

    async def _enrich_ranked_scores_for_match(
        self,
        *,
        session: AsyncSession,
        settings,
        riot_client: RiotClient | None,
        match_payload: dict,
        riot_match_id: str,
        ranked_queue_type: str | None,
        scores: list[dict],
        tracked_by_puuid: dict[str, object],
        match_end_ts_ms: int | None,
    ) -> tuple[list[dict], RiotClient | None]:
        if ranked_queue_type is None:
            return scores, riot_client

        game_id = _match_game_id(match_payload, riot_match_id)
        enriched_scores: list[dict] = []
        for score in scores:
            payload = dict(score or {})
            puuid = str(payload.get("puuid") or "")
            tracked = tracked_by_puuid.get(puuid)
            if tracked is None:
                enriched_scores.append(payload)
                continue

            before_snapshot = None
            if game_id:
                before_snapshot = await self._live_games_repo.get_ranked_snapshot(
                    session,
                    tracked_player_id=tracked.id,
                    game_id=game_id,
                    queue_type=ranked_queue_type,
                )

            current_snapshot = None
            try:
                current_snapshot, riot_client = await self._current_rank_snapshot(
                    settings=settings,
                    riot_client=riot_client,
                    tracked_player=tracked,
                    queue_type=ranked_queue_type,
                )
            except httpx.HTTPStatusError as e:
                self._log.warning(
                    "ranked_context_live_fetch_http_error",
                    status=e.response.status_code,
                    tracked_player_id=str(tracked.id),
                    queue_type=ranked_queue_type,
                )
            except Exception:
                self._log.exception(
                    "ranked_context_live_fetch_failed",
                    tracked_player_id=str(tracked.id),
                    queue_type=ranked_queue_type,
                )

            payload.update(
                await _ranked_context_for_player(
                    session,
                    self._leaderboards_repo,
                    tracked.id,
                    ranked_queue_type,
                    match_end_ts_ms,
                    before_snapshot=before_snapshot,
                    current_snapshot=current_snapshot,
                )
            )
            enriched_scores.append(payload)

        return enriched_scores, riot_client

    async def ingest(self, session: AsyncSession) -> dict:
        settings = get_settings()
        if not settings.riot_api_key.strip():
            raise ValueError("missing_riot_api_key")

        players = await self._players_repo.get_all(session)
        targets = [p for p in players if p.active and p.puuid and p.region]
        tracked_by_puuid = {
            str(player.puuid): player
            for player in players
            if player.active and player.puuid
        }

        client = RiotClient(settings.riot_api_key)
        rank_client: RiotClient | None = None

        created_matches = 0
        created_events = 0
        skipped_existing = 0
        skipped_remakes = 0
        errors = 0
        last_error: dict | None = None

        try:
            for p in targets:
                try:
                    ids = await client.get_match_ids_by_puuid(
                        p.region,
                        p.puuid,
                        start=0,
                        count=settings.matches_ingest_count,
                    )

                    for riot_match_id in ids:
                        if await self._repo.exists(session, riot_match_id):
                            skipped_existing += 1
                            continue

                        match_payload = await client.get_match(p.region, riot_match_id)
                        info = match_payload.get("info") or {}
                        meta = match_payload.get("metadata") or {}
                        participants = info.get("participants") or []

                        async with session.begin_nested():
                            m = Match(
                                riot_match_id=str(meta.get("matchId") or riot_match_id),
                                region=p.region,
                                queue_id=info.get("queueId"),
                                game_mode=info.get("gameMode"),
                                game_start_ts=info.get("gameStartTimestamp"),
                                game_end_ts=info.get("gameEndTimestamp"),
                                game_duration=info.get("gameDuration"),
                                payload=match_payload,
                            )
                            session.add(m)
                            await session.flush()

                            rows: list[MatchParticipant] = []
                            for part in participants:
                                puuid = str(part.get("puuid") or "")
                                if not puuid:
                                    continue
                                rows.append(
                                    MatchParticipant(
                                        match_id=m.id,
                                        puuid=puuid,
                                        team_id=part.get("teamId"),
                                        riot_id_game_name=part.get("riotIdGameName"),
                                        riot_id_tag_line=part.get("riotIdTagline"),
                                        champion_name=part.get("championName"),
                                        kills=part.get("kills"),
                                        deaths=part.get("deaths"),
                                        assists=part.get("assists"),
                                        win=part.get("win"),
                                        payload=part,
                                    )
                                )
                            session.add_all(rows)

                            scores = await compute_match_scoring(match_payload)
                            scores, rank_client = await self._enrich_ranked_scores_for_match(
                                session=session,
                                settings=settings,
                                riot_client=rank_client,
                                match_payload=match_payload,
                                riot_match_id=str(meta.get("matchId") or riot_match_id),
                                ranked_queue_type=_ranked_queue_type_for_queue_id(info.get("queueId")),
                                scores=scores,
                                tracked_by_puuid=tracked_by_puuid,
                                match_end_ts_ms=info.get("gameEndTimestamp") or info.get("gameStartTimestamp"),
                            )
                            score_rows = [
                                MatchScore(
                                    match_id=m.id,
                                    puuid=str(s.get("puuid") or ""),
                                    role=str(s.get("role") or "UNKNOWN"),
                                    final_score=float(s.get("final_score") or 0.0),
                                    final_grade=str(s.get("final_grade") or "F"),
                                    payload=s,
                                )
                                for s in scores
                                if str(s.get("puuid") or "")
                            ]
                            session.add_all(score_rows)

                            ok = False
                            is_remake = _is_remake_match_payload(match_payload)
                            if not is_remake:
                                dedupe_key = f"match_finished:{m.riot_match_id}"
                                payload = {"riot_match_id": m.riot_match_id, "region": m.region}
                                ok = await self._publications_repo.try_create_event(
                                    session=session,
                                    event_type="match_finished",
                                    dedupe_key=dedupe_key,
                                    payload=payload,
                                    max_attempts=settings.publication_max_attempts,
                                )

                        await session.commit()

                        created_matches += 1
                        if ok:
                            created_events += 1
                        elif is_remake:
                            skipped_remakes += 1

                except httpx.HTTPStatusError as e:
                    errors += 1
                    last_error = {
                        "type": "http",
                        "status": e.response.status_code,
                        "url": str(e.request.url),
                        "body": e.response.text[:500],
                        "player_id": str(p.id),
                    }
                    self._log.error("riot_http_error", **last_error)
                except Exception as e:
                    errors += 1
                    last_error = {"type": "exception", "error": str(e), "player_id": str(p.id)}
                    self._log.exception("matches_ingest_failed", **last_error)
                    await session.rollback()

            skipped_ineligible = len(players) - len(targets)
            return {
                "created_matches": created_matches,
                "created_events": created_events,
                "skipped_existing": skipped_existing,
                "skipped_remakes": skipped_remakes,
                "skipped_ineligible": skipped_ineligible,
                "errors": errors,
                "targets": len(targets),
                "last_error": last_error,
            }
        finally:
            await client.aclose()
            if rank_client is not None:
                await rank_client.aclose()

    async def get_summary(self, session: AsyncSession, riot_match_id: str) -> MatchSummaryOut | None:
        m = await self._repo.get_by_riot_id(session, riot_match_id)
        if m is None:
            return None
        parts = await self._repo.list_participants(session, m.id)
        res = await session.execute(select(MatchScore).where(MatchScore.match_id == m.id))
        scores = list(res.scalars().all())
        ranked_queue_type = _ranked_queue_type_for_queue_id(m.queue_id)
        players = await self._players_repo.get_all(session)
        tracked_by_puuid = {
            str(player.puuid): player
            for player in players
            if player.active and player.puuid
        }
        settings = get_settings()
        riot_client: RiotClient | None = None

        try:
            score_payloads: list[dict] = []
            for score in scores:
                payload = dict(score.payload or {})
                payload["role"] = payload.get("role") or score.role
                payload["final_score"] = payload.get("final_score", float(score.final_score))
                payload["final_grade"] = payload.get("final_grade") or score.final_grade

                tracked = tracked_by_puuid.get(str(score.puuid))
                if ranked_queue_type and tracked is not None and not _payload_has_ranked_context(payload):
                    before_snapshot = None
                    game_id = _match_game_id(m.payload or {}, m.riot_match_id)
                    if game_id:
                        before_snapshot = await self._live_games_repo.get_ranked_snapshot(
                            session,
                            tracked_player_id=tracked.id,
                            game_id=game_id,
                            queue_type=ranked_queue_type,
                        )

                    current_snapshot = None
                    try:
                        current_snapshot, riot_client = await self._current_rank_snapshot(
                            settings=settings,
                            riot_client=riot_client,
                            tracked_player=tracked,
                            queue_type=ranked_queue_type,
                        )
                    except httpx.HTTPStatusError as e:
                        self._log.warning(
                            "ranked_context_live_fetch_http_error",
                            status=e.response.status_code,
                            tracked_player_id=str(tracked.id),
                            queue_type=ranked_queue_type,
                        )
                    except Exception:
                        self._log.exception(
                            "ranked_context_live_fetch_failed",
                            tracked_player_id=str(tracked.id),
                            queue_type=ranked_queue_type,
                        )

                    payload.update(
                        await _ranked_context_for_player(
                            session,
                            self._leaderboards_repo,
                            tracked.id,
                            ranked_queue_type,
                            m.game_end_ts or m.game_start_ts,
                            before_snapshot=before_snapshot,
                            current_snapshot=current_snapshot,
                        )
                    )
                score_payloads.append(payload)
        finally:
            if riot_client is not None:
                await riot_client.aclose()

        return MatchSummaryOut(
            riot_match_id=m.riot_match_id,
            region=m.region,
            queue_id=m.queue_id,
            game_mode=m.game_mode,
            ranked_queue_type=ranked_queue_type,
            game_start_ts=m.game_start_ts,
            game_end_ts=m.game_end_ts,
            game_duration=m.game_duration,
            participants=[
                MatchParticipantOut(
                    puuid=p.puuid,
                    team_id=p.team_id,
                    riot_id_game_name=p.riot_id_game_name,
                    riot_id_tag_line=p.riot_id_tag_line,
                    champion_name=p.champion_name,
                    kills=p.kills,
                    deaths=p.deaths,
                    assists=p.assists,
                    win=p.win,
                    payload=p.payload,
                )
                for p in parts
            ],
            scores=score_payloads,
        )
