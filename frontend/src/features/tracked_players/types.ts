export type TrackedPlayer = {
  id: string;
  region: string;
  platform: string | null;
  discord_user_id: string | null;
  discord_display_name: string | null;
  game_name: string;
  tag_line: string;
  puuid: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type TrackedPlayerCreate = {
  discord_user_id: string;
  discord_display_name?: string | null;
  game_name: string;
  tag_line: string;
  region: string;
  platform?: string | null;
  puuid?: string | null;
  active?: boolean;
};

export type TrackedPlayerPatch = {
  active?: boolean | null;
  platform?: string | null;
  discord_user_id?: string | null;
  discord_display_name?: string | null;
};
