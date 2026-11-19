"""Turns the composite table + long metrics into the JSON the site reads.

site/data/latest.json            full record per team
site/data/history/YYYY-MM-DD.json  slim daily snapshot for trend charts
site/data/meta.json              run time, source status, weights
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

HISTORY_FIELDS = ["pred_rank", "res_rank", "pred_z", "res_z"]
QUAD_SOURCES = ["ncaa_net", "haslametrics"]  # first one with quad records wins
RECORD_SOURCES = ["espn_bpi", "torvik", "haslametrics", "teamrankings"]
STATS = ["adj_em", "adj_o", "adj_d", "tempo", "sos"]  # cross-source averages, in display order


def clean(value: Any, digits: int = 3) -> Any:
    """JSON-friendly scalar: NaN -> None, floats rounded, whole floats -> int."""
    if value is None:
        return None
    if isinstance(value, float) or hasattr(value, "item"):
        try:
            value = value.item()
        except AttributeError:
            pass
    if isinstance(value, float):
        if math.isnan(value):
            return None
        rounded = round(value, digits)
        return int(rounded) if rounded.is_integer() and abs(rounded) < 1e6 else rounded
    return value


def source_blocks(long: pd.DataFrame) -> dict[str, dict[str, dict[str, Any]]]:
    """team_id -> source -> {metric: value, metric_rank: rank}."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for row in long.itertuples(index=False):
        block = out.setdefault(row.team_id, {}).setdefault(row.source, {})
        value = row.value
        try:
            value = float(value)
        except (TypeError, ValueError):
            pass
        block[row.metric] = clean(value)
        if row.rank is not None and not (isinstance(row.rank, float) and math.isnan(row.rank)):
            block[f"{row.metric}_rank"] = clean(float(row.rank))
    return out


def first_text(sources: dict[str, dict[str, Any]], order: list[str], key: str) -> Any:
    for s in order:
        if s in sources and sources[s].get(key) not in (None, ""):
            return sources[s][key]
    return None


def team_records(composite: pd.DataFrame, long: pd.DataFrame, teams: pd.DataFrame) -> list[dict]:
    blocks = source_blocks(long)
    info = teams.set_index("team_id")
    stat_names = [s for s in STATS if f"{s}_rank" in composite.columns]
    records = []
    for team_id, row in composite.iterrows():
        src = blocks.get(team_id, {})
        quad_source = next((s for s in QUAD_SOURCES if s in src and "q1" in src[s]), None)
        records.append(
            {
                "id": team_id,
                "name": info.at[team_id, "name"],
                "short": info.at[team_id, "short_name"],
                "mascot": info.at[team_id, "mascot"] if "mascot" in info.columns else "",
                "conf": info.at[team_id, "conference"],
                "espn_id": info.at[team_id, "espn_id"],
                "color": info.at[team_id, "color"] if "color" in info.columns else "",
                "alt_color": info.at[team_id, "alt_color"] if "alt_color" in info.columns else "",
                "record": first_text(src, RECORD_SOURCES, "record"),
                "pred": {"rank": clean(row["pred_rank"]), "z": clean(row["pred_z"]), "n": clean(row["pred_n"])},
                "res": {"rank": clean(row["res_rank"]), "z": clean(row["res_z"]), "n": clean(row["res_n"])},
                "gap": clean(row["gap"]),
                "spread": clean(row["spread"]),
                "avg_source_rank": clean(row["avg_source_rank"], 2),
                "stats": {
                    s: {"value": clean(row.get(s), 2), "rank": clean(row.get(f"{s}_rank"))}
                    for s in stat_names
                },
                "quads": (
                    {"source": quad_source, **{q: src[quad_source].get(q) for q in ("q1", "q2", "q3", "q4")}}
                    if quad_source else None
                ),
                "z": {
                    "predictive": {c[3:]: clean(row[c]) for c in composite.columns if c.startswith("zp:")},
                    "resume": {c[3:]: clean(row[c]) for c in composite.columns if c.startswith("zr:")},
                },
                "sources": src,
            }
        )
    return records


def write(
    site_data: Path,
    composite: pd.DataFrame,
    long: pd.DataFrame,
    teams: pd.DataFrame,
    meta: dict[str, Any],
) -> None:
    site_data.mkdir(parents=True, exist_ok=True)
    (site_data / "history").mkdir(exist_ok=True)
    as_of = meta["as_of"]
    records = team_records(composite, long, teams)
    latest = {"as_of": as_of, "season": meta["season"], "teams": records}
    (site_data / "latest.json").write_text(json.dumps(latest, separators=(",", ":"), ensure_ascii=False))
    history = {
        "as_of": as_of,
        "fields": HISTORY_FIELDS,
        "teams": {tid: [clean(row[f]) for f in HISTORY_FIELDS] for tid, row in composite.iterrows()},
    }
    (site_data / "history" / f"{as_of}.json").write_text(json.dumps(history, separators=(",", ":")))
    # only dated snapshots (not index.json itself)
    index = sorted(
        p.stem for p in (site_data / "history").glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)
    )
    (site_data / "history" / "index.json").write_text(json.dumps(index))
    meta = {**meta, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (site_data / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
