from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.schedule import (
    next_run_after,
    parse_discovery_times,
    parse_hhmm,
    seconds_until,
)


def test_parse_discovery_times_sorts_and_dedupes():
    times = parse_discovery_times("20:00, 08:00, 08:00")
    assert [(t.hour, t.minute) for t in times] == [(8, 0), (20, 0)]


def test_parse_hhmm_rejects_invalid():
    with pytest.raises(ValueError):
        parse_hhmm("25:00")


def test_next_run_same_day():
    now = datetime(2026, 7, 30, 9, 0, tzinfo=ZoneInfo("Europe/London"))
    nxt = next_run_after(now, parse_discovery_times("08:00,20:00"), "Europe/London")
    assert nxt == datetime(2026, 7, 30, 20, 0, tzinfo=ZoneInfo("Europe/London"))


def test_next_run_rolls_to_next_day():
    now = datetime(2026, 7, 30, 21, 0, tzinfo=ZoneInfo("Europe/London"))
    nxt = next_run_after(now, parse_discovery_times("08:00,20:00"), "Europe/London")
    assert nxt == datetime(2026, 7, 31, 8, 0, tzinfo=ZoneInfo("Europe/London"))


def test_seconds_until_positive():
    now = datetime(2026, 7, 30, 9, 0, tzinfo=ZoneInfo("UTC"))
    target = datetime(2026, 7, 30, 9, 5, tzinfo=ZoneInfo("UTC"))
    assert seconds_until(target, now) == 300
