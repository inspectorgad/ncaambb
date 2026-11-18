"""Loads config/sources.yaml and works out the season."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

from . import CONFIG_DIR


def season_for(today: dt.date) -> int:
    """Season end year: Aug 2026 – Jul 2027 -> 2027."""
    return today.year + 1 if today.month >= 8 else today.year


def load_sources_config(path: Path | None = None, today: dt.date | None = None) -> dict[str, Any]:
    path = path or CONFIG_DIR / "sources.yaml"
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if cfg.get("season", "auto") == "auto":
        cfg["season"] = season_for(today or dt.date.today())
    cfg["season"] = int(cfg["season"])
    return cfg


def in_active_window(cfg: dict[str, Any], today: dt.date) -> bool:
    """True during the season window (which wraps around New Year)."""
    window = cfg.get("active_window")
    if not window:
        return True
    start = tuple(int(x) for x in window["start"].split("-"))
    end = tuple(int(x) for x in window["end"].split("-"))
    md = (today.month, today.day)
    if start <= end:
        return start <= md <= end
    return md >= start or md <= end
