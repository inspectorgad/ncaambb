"""Rank movement, trend lines and "Today's story" lists from the daily history.

History snapshots (site/data/history/YYYY-MM-DD.json) hold each team's
ranks for that day (see build_site_data.HISTORY_FIELDS) and, from Phase C
on, the projected tournament field. Everything here degrades gracefully:
with no earlier snapshot, movement is None and the stories that need a
comparison are empty.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

TREND_DAYS = 14        # points in each team's sparkline (including today)
STORY_SIZE = 3         # teams per story card
RISER_POOL = 100       # risers/fallers are drawn from the top 100 (today or before)
CONTENDER_POOL = 50    # under-rewarded / disputed are drawn from the Predictive top 50


def load_history(history_dir: Path, before: str) -> list[tuple[str, dict]]:
    """Dated snapshots strictly before `before`, oldest first."""
    out = []
    for p in sorted(history_dir.glob("*.json")):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem) and p.stem < before:
            try:
                snap = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(snap.get("teams"), dict):
                out.append((p.stem, snap))
    return out


def _rank(snap: dict, team_id: str, field: str) -> int | None:
    row = snap["teams"].get(team_id)
    if row is None or field not in snap.get("fields", []):
        return None
    value = row[snap["fields"].index(field)]
    return int(value) if value is not None else None


def add_movement(records: list[dict], history: list[tuple[str, dict]], as_of: str) -> None:
    """Add "move" and "trend" to each team record (in place)."""
    prev = history[-1] if history else None
    week_cut = (dt.date.fromisoformat(as_of) - dt.timedelta(days=7)).isoformat()
    week = next((h for h in reversed(history) if h[0] <= week_cut), None)
    recent = history[-(TREND_DAYS - 1):]
    for r in records:
        tid, pred, res = r["id"], r["pred"]["rank"], r["res"]["rank"]

        def change(snap: tuple[str, dict] | None, field: str, now: int | None) -> int | None:
            if snap is None or now is None:
                return None
            before = _rank(snap[1], tid, field)
            return None if before is None else before - now  # positive = moved up

        r["move"] = {
            "since": prev[0] if prev else None,
            "pred": change(prev, "pred_rank", pred),
            "res": change(prev, "res_rank", res),
            "week_since": week[0] if week else None,
            "pred_7d": change(week, "pred_rank", pred),
            "res_7d": change(week, "res_rank", res),
        }
        r["trend"] = {
            "dates": [d for d, _ in recent] + [as_of],
            "pred": [_rank(s, tid, "pred_rank") for _, s in recent] + [pred],
            "res": [_rank(s, tid, "res_rank") for _, s in recent] + [res],
        }


def field_ids(records: list[dict]) -> list[str]:
    return sorted(r["id"] for r in records if (r.get("sources", {}).get("bracketmatrix") or {}).get("consensus_seed"))


def stories(records: list[dict], history: list[tuple[str, dict]]) -> dict[str, Any]:
    """Short lists of team ids for the story cards."""
    prev = history[-1] if history else None
    by_id = {r["id"]: r for r in records}

    def pick(rows: list[dict], key, reverse: bool, value) -> list[dict]:
        rows = sorted(rows, key=key, reverse=reverse)[:STORY_SIZE]
        return [{"id": r["id"], "value": value(r)} for r in rows]

    moved = [r for r in records if r["move"]["pred"] is not None]
    risers = [r for r in moved if r["move"]["pred"] > 0 and r["pred"]["rank"] <= RISER_POOL]
    fallers = [r for r in moved if r["move"]["pred"] < 0 and r["pred"]["rank"] - r["move"]["pred"] <= RISER_POOL]
    contenders = [r for r in records if r["pred"]["rank"] is not None and r["pred"]["rank"] <= CONTENDER_POOL]

    out: dict[str, Any] = {
        "since": prev[0] if prev else None,
        "risers": pick(risers, lambda r: (r["move"]["pred"], -r["pred"]["rank"]), True, lambda r: r["move"]["pred"]),
        "fallers": pick(fallers, lambda r: (r["move"]["pred"], r["pred"]["rank"]), False, lambda r: r["move"]["pred"]),
        "under_rewarded": pick([r for r in contenders if (r.get("gap") or 0) < 0],
                               lambda r: r["gap"], False, lambda r: r["gap"]),
        "disputed": pick([r for r in contenders if r.get("spread") is not None],
                         lambda r: r["spread"], True, lambda r: r["spread"]),
        "new_in_field": [],
        "left_field": [],
        "field_tracked": bool(prev and isinstance(prev[1].get("field"), list)),
    }
    if out["field_tracked"]:
        before, now = set(prev[1]["field"]), set(field_ids(records))
        out["new_in_field"] = [{"id": i, "value": None} for i in sorted(now - before, key=lambda i: by_id[i]["pred"]["rank"])]
        out["left_field"] = [{"id": i, "value": None} for i in sorted(before - now) if i in by_id]
    return out
