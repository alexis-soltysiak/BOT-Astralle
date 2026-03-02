from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RankedStateOut(BaseModel):
    queue_type: str
    tier: str | None
    division: str | None
    league_points: int | None
    wins: int | None
    losses: int | None
    fetched_at: datetime | None


class LeaderboardEntryOut(BaseModel):
    tracked_player_id: uuid.UUID
    discord_display_name: str | None = None
    game_name: str
    tag_line: str
    platform: str | None

    solo: RankedStateOut
    flex: RankedStateOut
