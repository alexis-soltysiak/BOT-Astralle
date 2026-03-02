import { apiGet, apiPost } from "@/features/api/client";
import type { MatchRow, MatchSummary } from "./types";

export function listMatches(limit = 50) {
  return apiGet<MatchRow[]>(`/api/matches?limit=${limit}`);
}

export function ingestMatches() {
  return apiPost("/api/matches/ingest", {});
}

export function getMatchSummary(riotMatchId: string) {
  return apiGet<MatchSummary>(`/api/matches/${encodeURIComponent(riotMatchId)}/summary`);
}