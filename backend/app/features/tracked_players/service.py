from __future__ import annotations

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.matches.repository import MatchesRepository
from app.features.publications.repository import PublicationsRepository
from app.features.tracked_players.models import TrackedPlayer
from app.features.tracked_players.repository import TrackedPlayersRepository
from app.features.tracked_players.schemas import TrackedPlayerCreate, TrackedPlayerPatch
from app.infra.riot_client import RiotClient


class TrackedPlayersService:
    def __init__(
        self,
        repo: TrackedPlayersRepository,
        matches_repo: MatchesRepository | None = None,
        publications_repo: PublicationsRepository | None = None,
    ) -> None:
        self._repo = repo
        self._matches_repo = matches_repo or MatchesRepository()
        self._publications_repo = publications_repo or PublicationsRepository()

    async def list(self, session: AsyncSession) -> list[TrackedPlayer]:
        return await self._repo.get_all(session)

    async def get(self, session: AsyncSession, player_id: uuid.UUID) -> TrackedPlayer | None:
        return await self._repo.get_by_id(session, player_id)

    async def create(self, session: AsyncSession, payload: TrackedPlayerCreate) -> TrackedPlayer:
        existing = await self._repo.get_by_riot_id(
            session, payload.region, payload.game_name, payload.tag_line
        )
        if existing is not None:
            changed = False
            if existing.discord_user_id != payload.discord_user_id:
                existing.discord_user_id = payload.discord_user_id
                changed = True
            if existing.discord_display_name != payload.discord_display_name:
                existing.discord_display_name = payload.discord_display_name
                changed = True
            if payload.platform is not None and existing.platform != payload.platform:
                existing.platform = payload.platform
                changed = True
            if existing.active != payload.active:
                existing.active = payload.active
                changed = True
            if changed:
                await session.commit()
                await session.refresh(existing)
            return existing

        puuid = payload.puuid
        if puuid is None:
            settings = get_settings()
            if not settings.riot_api_key.strip():
                raise ValueError("missing_riot_api_key")
            client = RiotClient(settings.riot_api_key)
            try:
                data = await client.get_account_by_riot_id(payload.region, payload.game_name, payload.tag_line)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 404:
                    raise ValueError("riot_account_not_found")
                if status in (401, 403):
                    raise ValueError("riot_auth_failed")
                raise ValueError("riot_request_failed")
            finally:
                await client.aclose()
            puuid = data.get("puuid")

        player = TrackedPlayer(
            region=payload.region,
            platform=payload.platform,
            discord_user_id=payload.discord_user_id,
            discord_display_name=payload.discord_display_name,
            game_name=payload.game_name,
            tag_line=payload.tag_line,
            puuid=puuid,
            active=payload.active,
        )
        return await self._repo.create(session, player)

    async def patch(
        self, session: AsyncSession, player: TrackedPlayer, payload: TrackedPlayerPatch
    ) -> TrackedPlayer:
        changed = False
        if payload.active is not None:
            player.active = payload.active
            changed = True
        if payload.platform is not None:
            player.platform = payload.platform
            changed = True
        if payload.discord_user_id is not None:
            player.discord_user_id = payload.discord_user_id
            changed = True
        if payload.discord_display_name is not None:
            player.discord_display_name = payload.discord_display_name
            changed = True
        if changed:
            await session.commit()
            await session.refresh(player)
        return player

    async def delete(self, session: AsyncSession, player_id: uuid.UUID) -> None:
        player = await self._repo.get_by_id(session, player_id)
        if player is not None and player.puuid:
            players = await self._repo.get_all(session)
            other_tracked_puuids = {
                str(p.puuid)
                for p in players
                if p.id != player_id and p.active and p.puuid
            }

            player_matches = await self._matches_repo.list_matches_by_participant_puuid(session, player.puuid)
            match_ids_to_delete: list[uuid.UUID] = []
            dedupe_keys_to_delete: list[str] = []

            for match in player_matches:
                participants = await self._matches_repo.list_participants(session, match.id)
                participant_puuids = {str(part.puuid) for part in participants if part.puuid}
                if participant_puuids.intersection(other_tracked_puuids):
                    continue
                match_ids_to_delete.append(match.id)
                dedupe_keys_to_delete.append(f"match_finished:{match.riot_match_id}")

            await self._publications_repo.delete_by_dedupe_keys(session, dedupe_keys_to_delete)
            await self._matches_repo.delete_matches(session, match_ids_to_delete)

        await self._repo.delete(session, player_id)
