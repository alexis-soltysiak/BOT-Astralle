export type PublicationEvent = {
  id: string;
  event_type: string;
  dedupe_key: string;
  status: string;
  attempts: number;
  max_attempts: number;
  available_at: string;
  claimed_by: string | null;
  claimed_until: string | null;
  last_error: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};