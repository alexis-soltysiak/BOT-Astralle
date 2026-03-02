from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.features.leaderboards.schemas import RankedStateOut


class LiveGameOut(BaseModel):
    tracked_player_id: uuid.UUID
    puuid: str | None = None
    discord_display_name: str | None = None
    game_name: str
    tag_line: str
    platform: str | None

    status: str
    game_id: str | None
    payload: dict | None
    fetched_at: datetime | None
    solo: RankedStateOut
    flex: RankedStateOut
