from __future__ import annotations

import httpx

DISCORD_BINDINGS_PREFIX = "/api/discord-bindings"


class BackendClient:
    def __init__(
        self,
        base_url: str,
        proxy_secret: str = "",
        discord_service_token: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        headers = {}
        if proxy_secret:
            headers["X-Backend-Proxy-Secret"] = proxy_secret
        if discord_service_token:
            headers["X-Discord-Service-Token"] = discord_service_token
        self._client = httpx.AsyncClient(timeout=25.0, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> dict | list:
        res = await self._client.get(f"{self._base_url}{path}")
        res.raise_for_status()
        return res.json()

    async def _post(self, path: str, payload: dict) -> dict | list:
        res = await self._client.post(f"{self._base_url}{path}", json=payload)
        res.raise_for_status()
        return res.json()

    async def _delete(self, path: str) -> None:
        res = await self._client.delete(f"{self._base_url}{path}")
        res.raise_for_status()

    async def health(self) -> dict:
        data = await self._get("/")
        return data  # type: ignore[return-value]

    async def list_tracked_players(self) -> list[dict]:
        data = await self._get("/api/tracked-players")
        return data  # type: ignore[return-value]

    async def create_tracked_player(self, payload: dict) -> dict:
        data = await self._post("/api/tracked-players", payload)
        return data  # type: ignore[return-value]

    async def delete_tracked_player(self, player_id: str) -> None:
        await self._delete(f"/api/tracked-players/{player_id}")

    async def list_leaderboards(self, sort: str) -> list[dict]:
        data = await self._get(f"/api/leaderboards?sort={sort}")
        return data  # type: ignore[return-value]

    async def refresh_leaderboards(self) -> dict:
        data = await self._post("/api/leaderboards/refresh", {})
        return data  # type: ignore[return-value]

    async def list_live_games_active(self) -> list[dict]:
        data = await self._get("/api/live-games/active")
        return data  # type: ignore[return-value]

    async def list_matches(self, limit: int) -> list[dict]:
        data = await self._get(f"/api/matches?limit={limit}")
        return data  # type: ignore[return-value]

    async def get_match_summary(self, riot_match_id: str) -> dict:
        data = await self._get(f"/api/matches/{riot_match_id}/summary")
        return data  # type: ignore[return-value]

    async def get_recent_player_analysis(self, puuid: str, limit: int = 20) -> dict:
        data = await self._get(f"/api/matches/players/{puuid}/recent-analysis?limit={limit}")
        return data  # type: ignore[return-value]

    async def claim_publication_events(self, consumer_id: str, limit: int) -> list[dict]:
        data = await self._post("/api/publication-events/claim", {"consumer_id": consumer_id, "limit": limit})
        return data  # type: ignore[return-value]

    async def ack_publication_event(self, event_id: str, ok: bool, error: str | None = None) -> dict:
        payload = {"ok": ok, "error": error}
        data = await self._post(f"/api/publication-events/{event_id}/ack", payload)
        return data  # type: ignore[return-value]

    async def list_discord_bindings(self, guild_id: int) -> list[dict]:
        res = await self._client.get(
            f"{self._base_url}{DISCORD_BINDINGS_PREFIX}",
            params={"guild_id": str(guild_id)},
        )
        res.raise_for_status()
        data = res.json()
        return list(data) if isinstance(data, list) else []

    async def upsert_discord_binding(self, binding_key: str, payload: dict) -> dict:
        res = await self._client.put(
            f"{self._base_url}{DISCORD_BINDINGS_PREFIX}/{binding_key}",
            json=payload,
        )
        res.raise_for_status()
        return res.json()

    async def patch_discord_binding(self, binding_key: str, guild_id: int, payload: dict) -> dict:
        res = await self._client.patch(
            f"{self._base_url}{DISCORD_BINDINGS_PREFIX}/{binding_key}",
            params={"guild_id": str(guild_id)},
            json=payload,
        )
        res.raise_for_status()
        return res.json()
