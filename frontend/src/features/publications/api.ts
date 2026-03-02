import { apiGet } from "@/features/api/client";
import type { PublicationEvent } from "./types";

export function listPublicationEvents(status?: string) {
  const q = status ? `?status_filter=${encodeURIComponent(status)}` : "";
  return apiGet<PublicationEvent[]>(`/api/publication-events${q}`);
}