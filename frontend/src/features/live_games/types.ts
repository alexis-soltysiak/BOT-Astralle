export type LiveGame = {
  tracked_player_id: string;
  game_name: string;
  tag_line: string;
  platform: string | null;
  status: string;
  game_id: string | null;
  payload: Record<string, unknown> | null;
  fetched_at: string | null;
};