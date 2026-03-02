from __future__ import annotations

from datetime import UTC, datetime, timedelta


def _last_sunday(year: int, month: int) -> datetime:
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=UTC)
    day = next_month - timedelta(days=1)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def _france_offset_and_name(dt_utc: datetime) -> tuple[timedelta, str]:
    year = dt_utc.year
    dst_start = _last_sunday(year, 3).replace(hour=1, minute=0, second=0, microsecond=0)
    dst_end = _last_sunday(year, 10).replace(hour=1, minute=0, second=0, microsecond=0)
    if dst_start <= dt_utc < dst_end:
        return timedelta(hours=2), "CEST"
    return timedelta(hours=1), "CET"


def format_france_datetime(value: str | datetime | None, *, with_seconds: bool) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt_utc = dt.astimezone(UTC)
    offset, tz_name = _france_offset_and_name(dt_utc)
    local_dt = dt_utc + offset
    fmt = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return f"{local_dt.strftime(fmt)} {tz_name}"
