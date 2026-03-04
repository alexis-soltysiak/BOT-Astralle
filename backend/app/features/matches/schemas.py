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


class RecentPlayerMatchOut(BaseModel):
    riot_match_id: str
    queue_label: str
    champion_name: str | None = None
    role: str | None = None
    result: str
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    kda: str
    kill_participation: float | None = None
    cs_per_min: float | None = None
    final_score: float | None = None
    final_rank: int | None = None
    rank_delta_lp: int | None = None
    rank_after: str | None = None
    game_end_ts: int | None = None


class RecentPlayerAggregatesOut(BaseModel):
    matches_count: int
    wins: int
    losses: int
    win_rate: float
    avg_final_score: float | None = None
    avg_final_rank: float | None = None
    avg_kills: float | None = None
    avg_deaths: float | None = None
    avg_assists: float | None = None
    avg_kp: float | None = None
    avg_cs_per_min: float | None = None
    avg_game_duration_minutes: float | None = None
    avg_rank_delta_lp: float | None = None
    total_rank_delta_lp: int | None = None
    last5_avg_score: float | None = None
    previous5_avg_score: float | None = None
    score_trend_delta: float | None = None
    top_champions: list[str] = Field(default_factory=list)
    role_distribution: dict[str, int] = Field(default_factory=dict)
    queue_distribution: dict[str, int] = Field(default_factory=dict)


class RecentPlayerAnalysisOut(BaseModel):
    player: dict
    aggregates: RecentPlayerAggregatesOut
    matches: list[RecentPlayerMatchOut] = Field(default_factory=list)
