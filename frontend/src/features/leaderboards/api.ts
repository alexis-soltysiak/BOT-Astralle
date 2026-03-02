import { apiGet, apiPost } from "@/features/api/client";
import type { LeaderboardRow } from "./types";

export function getLeaderboards(sort: "solo" | "flex") {
  return apiGet<LeaderboardRow[]>(`/api/leaderboards?sort=${sort}`);
}

export function refreshLeaderboards() {
  return apiPost<{ created: number; skipped: number; errors: number; targets?: number }>(
    "/api/leaderboards/refresh",
    {}
  );
}