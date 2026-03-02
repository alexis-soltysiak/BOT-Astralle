from __future__ import annotations

from datetime import timedelta


def compute_backoff_seconds(attempts: int) -> int:
    a = max(1, attempts)
    s = 2 ** min(8, a)
    return min(900, s)


def next_available_delta(attempts: int) -> timedelta:
    return timedelta(seconds=compute_backoff_seconds(attempts))