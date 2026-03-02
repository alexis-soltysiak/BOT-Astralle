import { apiGet, apiPost } from "@/features/api/client";
import type { TrackedPlayer, TrackedPlayerCreate, TrackedPlayerPatch } from "./types";

export function listTrackedPlayers() {
  return apiGet<TrackedPlayer[]>("/api/tracked-players");
}

export function createTrackedPlayer(payload: TrackedPlayerCreate) {
  return apiPost<TrackedPlayer>("/api/tracked-players", payload);
}

export async function patchTrackedPlayer(id: string, payload: TrackedPlayerPatch) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_BASE_URL || "http://localhost:8000"}/api/tracked-players/${id}`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) throw new Error(`PATCH /tracked-players/${id} -> ${res.status}`);
  return (await res.json()) as TrackedPlayer;
}