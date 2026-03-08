export type LiveGamePredictionPlayer = {
  puuid: string;
  player_name: string;
  team_id: number;
  is_tracked?: boolean;
  history_source?: "local" | "riot" | "none";
  games_count: number | null;
  recent_scores: number[];
  weighted_recent_score: number | null;
  elo_lp_total: number | null;
  elo_component: number | null;
  skill_value: number;
};

export type LiveGameWinPrediction = {
  model_version: string;
  computed_at: string;
  cache_ttl_seconds: number;
  formula: string;
  weights: {
    recent_scores: number[];
    last3_multiplier: number;
    score_component_weight: number;
    elo_component_weight: number;
  };
  team_blue: {
    team_id: number;
    strength: number;
    win_probability: number;
    players_count: number;
  };
  team_red: {
    team_id: number;
    strength: number;
    win_probability: number;
    players_count: number;
  };
  players: LiveGamePredictionPlayer[];
};

export type LiveGame = {
  tracked_player_id: string;
  game_name: string;
  tag_line: string;
  platform: string | null;
  status: string;
  game_id: string | null;
  payload: Record<string, unknown> | null;
  fetched_at: string | null;
  win_prediction?: LiveGameWinPrediction | null;
};
