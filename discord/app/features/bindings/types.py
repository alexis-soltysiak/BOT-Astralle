from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BindingKey = Literal["LEADERBOARD_MESSAGE", "LIVE_GAMES_MESSAGE", "FINISHED_GAMES_CHANNEL"]
LeaderboardMode = Literal["solo", "flex"]


@dataclass(frozen=True)
class Binding:
    guild_id: str
    binding_key: BindingKey
    channel_id: str
    message_id: str | None
    leaderboard_mode: LeaderboardMode | None
    is_enabled: bool
    last_error: str | None