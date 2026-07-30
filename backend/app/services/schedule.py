"""Timezone-aware schedule helpers for twice-daily discovery runs."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_hhmm(value: str) -> time:
    """Parse HH:MM into a time. Raises ValueError on bad input."""
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time '{value}', expected HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time '{value}', expected HH:MM")
    return time(hour=hour, minute=minute)


def parse_discovery_times(raw: str) -> list[time]:
    """Parse a comma-separated HH:MM list into unique sorted times."""
    times: list[time] = []
    seen: set[tuple[int, int]] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parsed = parse_hhmm(chunk)
        key = (parsed.hour, parsed.minute)
        if key not in seen:
            seen.add(key)
            times.append(parsed)
    if not times:
        raise ValueError("At least one discovery time is required")
    return sorted(times)


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{name}'") from exc


def next_run_after(
    now: datetime,
    times: list[time],
    tz_name: str,
) -> datetime:
    """Return the next scheduled run strictly after `now` in the given timezone."""
    if not times:
        raise ValueError("times must not be empty")
    tz = resolve_timezone(tz_name)
    local_now = now.astimezone(tz)
    today = local_now.date()

    for scheduled in times:
        candidate = datetime.combine(today, scheduled, tzinfo=tz)
        if candidate > local_now:
            return candidate

    tomorrow = today + timedelta(days=1)
    return datetime.combine(tomorrow, times[0], tzinfo=tz)


def seconds_until(target: datetime, now: datetime | None = None) -> float:
    """Seconds from now until target. Always returns a positive value >= 1."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    delay = (target - current).total_seconds()
    return max(1.0, delay)
