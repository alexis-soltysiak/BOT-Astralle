from __future__ import annotations

import httpx

from .types import Binding, BindingKey, LeaderboardMode


class BindingsClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    async def list_bindings(self, *, guild_id: str) -> list[Binding]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(f"{self._base_url}/api/discord-bindings", params={"guild_id": guild_id})
            r.raise_for_status()
            data = r.json()
        return [
            Binding(
                guild_id=x["guild_id"],
                binding_key=x["binding_key"],
                channel_id=x["channel_id"],
                message_id=x.get("message_id"),
                leaderboard_mode=x.get("leaderboard_mode"),
                is_enabled=bool(x["is_enabled"]),
                last_error=x.get("last_error"),
            )
            for x in data
        ]

    async def upsert_binding(
        self,
        *,
        binding_key: BindingKey,
        guild_id: str,
        channel_id: str,
        message_id: str | None,
        leaderboard_mode: LeaderboardMode | None,
        is_enabled: bool = True,
        last_error: str | None = None,
    ) -> Binding:
        payload = {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "leaderboard_mode": leaderboard_mode,
            "is_enabled": is_enabled,
            "last_error": last_error,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.put(f"{self._base_url}/api/discord-bindings/{binding_key}", json=payload)
            r.raise_for_status()
            x = r.json()
        return Binding(
            guild_id=x["guild_id"],
            binding_key=x["binding_key"],
            channel_id=x["channel_id"],
            message_id=x.get("message_id"),
            leaderboard_mode=x.get("leaderboard_mode"),
            is_enabled=bool(x["is_enabled"]),
            last_error=x.get("last_error"),
        )

    async def patch_binding(
        self,
        *,
        binding_key: BindingKey,
        guild_id: str,
        channel_id: str | None = None,
        message_id: str | None = None,
        leaderboard_mode: LeaderboardMode | None = None,
        is_enabled: bool | None = None,
        last_error: str | None = None,
    ) -> Binding:
        payload = {
            "channel_id": channel_id,
            "message_id": message_id,
            "leaderboard_mode": leaderboard_mode,
            "is_enabled": is_enabled,
            "last_error": last_error,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.patch(
                f"{self._base_url}/api/discord-bindings/{binding_key}",
                params={"guild_id": guild_id},
                json=payload,
            )
            r.raise_for_status()
            x = r.json()
        return Binding(
            guild_id=x["guild_id"],
            binding_key=x["binding_key"],
            channel_id=x["channel_id"],
            message_id=x.get("message_id"),
            leaderboard_mode=x.get("leaderboard_mode"),
            is_enabled=bool(x["is_enabled"]),
            last_error=x.get("last_error"),
        )