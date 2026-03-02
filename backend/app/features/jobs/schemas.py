from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JobOut(BaseModel):
    id: uuid.UUID
    job_key: str
    description: str
    interval_seconds: int
    enabled: bool
    last_status: str | None
    last_error: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobPatch(BaseModel):
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    description: str | None = None


class JobRunOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: str
    error: str | None
    started_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True