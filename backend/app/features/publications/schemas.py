from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PublicationEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    dedupe_key: str
    status: str
    attempts: int
    max_attempts: int
    available_at: datetime
    claimed_by: str | None
    claimed_until: datetime | None
    last_error: str | None
    payload: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClaimRequest(BaseModel):
    consumer_id: str = Field(min_length=1, max_length=64)
    limit: int = Field(default=10, ge=1, le=50)


class AckRequest(BaseModel):
    ok: bool
    error: str | None = None