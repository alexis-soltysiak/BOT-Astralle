from __future__ import annotations

from app.core.backend_client import BackendClient


async def bootstrap_bindings(
    *,
    backend: BackendClient,
    guild_id: int,
    leaderboard_channel_id: int,
    live_channel_id: int,
    finished_channel_id: int,
) -> None:
    await backend.upsert_discord_binding(
        "LEADERBOARD_MESSAGE",
        {
            "guild_id": str(guild_id),
            "channel_id": str(leaderboard_channel_id),
            "message_id": None,
            "leaderboard_mode": "solo",
            "is_enabled": True,
            "last_error": None,
        },
    )
    await backend.upsert_discord_binding(
        "LIVE_GAMES_MESSAGE",
        {
            "guild_id": str(guild_id),
            "channel_id": str(live_channel_id),
            "message_id": None,
            "leaderboard_mode": None,
            "is_enabled": True,
            "last_error": None,
        },
    )
    await backend.upsert_discord_binding(
        "FINISHED_GAMES_CHANNEL",
        {
            "guild_id": str(guild_id),
            "channel_id": str(finished_channel_id),
            "message_id": None,
            "leaderboard_mode": None,
            "is_enabled": True,
            "last_error": None,
        },
    )
