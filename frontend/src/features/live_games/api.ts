import { apiGet, apiPost } from "@/features/api/client";
import type { LiveGame } from "./types";

export function listLiveGames(activeOnly: boolean) {
  const q = activeOnly ? "/api/live-games/active" : "/api/live-games?active_only=false";
  return apiGet<LiveGame[]>(q);
}

export function refreshLiveGames() {
  return apiPost<{ updated: number; skipped: number; errors: number; targets?: number }>(
    "/api/live-games/refresh",
    {}
  );
}