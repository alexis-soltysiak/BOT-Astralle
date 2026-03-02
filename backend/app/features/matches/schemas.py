from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MatchOut(BaseModel):
    riot_match_id: str
    region: str
    queue_id: int | None
    game_mode: str | None
    game_start_ts: int | None
    game_end_ts: int | None
    game_duration: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchParticipantOut(BaseModel):
    puuid: str
    team_id: int | None
    riot_id_game_name: str | None
    riot_id_tag_line: str | None
    champion_name: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    win: bool | None
    payload: dict | None = None

    class Config:
        from_attributes = True


class MatchSummaryOut(BaseModel):
    riot_match_id: str
    region: str
    queue_id: int | None
    game_mode: str | None
    ranked_queue_type: str | None = None
    game_start_ts: int | None
    game_end_ts: int | None
    game_duration: int | None
    participants: list[MatchParticipantOut]
    scores: list[dict] = Field(default_factory=list)
