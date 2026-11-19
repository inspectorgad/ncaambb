"""Composite NCAA D1 men's basketball rankings."""

import datetime as _dt
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

# College basketball runs on US Eastern time: a 7:30 PM ET tip-off is already
# the next day in UTC. All calendar dates in the project use Eastern time.
EASTERN = ZoneInfo("America/New_York")


def today_eastern() -> _dt.date:
    return _dt.datetime.now(EASTERN).date()


def eastern_date(iso_utc: str) -> str:
    """'2026-11-19T00:30:00.000Z' -> '2026-11-18' (Eastern calendar date)."""
    if not iso_utc:
        return ""
    t = _dt.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=_dt.timezone.utc)
    return t.astimezone(EASTERN).date().isoformat()
