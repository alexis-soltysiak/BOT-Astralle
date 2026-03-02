export type RankedState = {
  queue_type: string;
  tier: string | null;
  division: string | null;
  league_points: number | null;
  wins: number | null;
  losses: number | null;
  fetched_at: string | null;
};

export type LeaderboardRow = {
  tracked_player_id: string;
  game_name: string;
  tag_line: string;
  platform: string | null;
  solo: RankedState;
  flex: RankedState;
};