export type MatchRow = {
  riot_match_id: string;
  region: string;
  queue_id: number | null;
  game_mode: string | null;
  game_start_ts: number | null;
  game_end_ts: number | null;
  game_duration: number | null;
  created_at: string;
};

export type MatchParticipant = {
  puuid: string;
  team_id: number | null;
  riot_id_game_name: string | null;
  riot_id_tag_line: string | null;
  champion_name: string | null;
  kills: number | null;
  deaths: number | null;
  assists: number | null;
  win: boolean | null;
};

export type MatchSummary = {
  riot_match_id: string;
  region: string;
  queue_id: number | null;
  game_mode: string | null;
  game_start_ts: number | null;
  game_end_ts: number | null;
  game_duration: number | null;
  participants: MatchParticipant[];
};