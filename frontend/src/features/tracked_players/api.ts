import { apiGet, apiPatch, apiPost } from "@/features/api/client";
import type { TrackedPlayer, TrackedPlayerCreate, TrackedPlayerPatch } from "./types";

export function listTrackedPlayers() {
  return apiGet<TrackedPlayer[]>("/api/tracked-players");
}

export function createTrackedPlayer(payload: TrackedPlayerCreate) {
  return apiPost<TrackedPlayer>("/api/tracked-players", payload);
}

export async function patchTrackedPlayer(id: string, payload: TrackedPlayerPatch) {
  return apiPatch<TrackedPlayer>(`/api/tracked-players/${id}`, payload);
}
