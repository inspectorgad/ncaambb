"""Player ratings: a composite of free impact metrics, like the team composite.

Sources
  * CollegeBasketballData /stats/player/season (needs CBBD_API_KEY): box stats,
    offensive/defensive rating, usage, win shares, PORPAG.
  * BartTorvik player file (getadvstats.php, free): box plus/minus (BPM, OBPM,
    DBPM), class, height, role. Optional: if Torvik is unreachable, its last good
    file (up to 3 days old) is used, else the composite runs without BPM.

Composite: each metric is turned into a z-score among *eligible* players
(>= 40% of their team's minutes), then averaged with equal weights over the
metrics a player has. Players are ranked by that score.

Outputs
  * site/data/players.json            the Top 50 (with full breakdowns)
  * "players" in site/data/team/<id>.json   each team's roster with the same fields
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from rapidfuzz import fuzz

from .fetching import NotConfigured, fetch_bytes

log = logging.getLogger("ncaambb")

CBBD_URL = "https://api.collegebasketballdata.com/stats/player/season?season={season}"
TORVIK_URL = "https://barttorvik.com/getadvstats.php?year={season}&csv=1"
KEY_ENV = "CBBD_API_KEY"
MIN_SHARE = 0.40        # eligibility: share of team minutes
ROSTER_MIN_SHARE = 0.05  # roster cards list players above this share
TOP_N = 50
STALE_DAYS = 3

# Composite inputs: key -> (label, description, source)
METRICS = {
    "ws40": ("Win shares / 40", "Wins the player adds per 40 minutes (offense + defense)", "CBBD"),
    "porpag": ("PORPAG", "Points over a replacement-level player, per game", "CBBD"),
    "bpm": ("Box plus/minus", "Points per 100 possessions better than an average player, from the box score", "Torvik"),
}

# Torvik's player CSV has no header row; these positions were checked against known values.
TORVIK_COLS = {
    "name": 0, "team": 1, "games": 3, "min_pct": 4, "ortg": 5, "usage": 6, "ts": 8,
    "yr": 25, "ht": 26, "num": 27, "porpag": 28, "drtg": 46,
    "bpm": 50, "obpm": 51, "dbpm": 52, "mpg": 54, "role": 64,
}


# ------------------------------------------------------------------ helpers

def norm_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z ]", " ", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _pct(v: Any) -> float | None:
    """CBBD gives some shooting rates as fractions (0.71) and others as percents (71.0)."""
    v = _num(v)
    return None if v is None else (v * 100 if v <= 1.5 else v)


def _r(v: Any, d: int = 1) -> Any:
    v = _num(v)
    return None if v is None else round(v, d)


# ------------------------------------------------------------------ parsing

def parse_torvik(raw: bytes) -> pd.DataFrame:
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8", errors="replace"))))
    rows = [r for r in rows if len(r) > max(TORVIK_COLS.values())]
    if len(rows) < 500:
        raise ValueError(f"torvik players: only {len(rows)} usable rows")
    df = pd.DataFrame({k: [r[i] for r in rows] for k, i in TORVIK_COLS.items()})
    for k in ("games", "min_pct", "ortg", "usage", "ts", "porpag", "drtg", "bpm", "obpm", "dbpm", "mpg"):
        df[k] = pd.to_numeric(df[k], errors="coerce")
    # low-minute players can have wild BPMs; check the layout on regulars only
    # (one-game players can legitimately post extreme numbers, so allow a few outliers)
    sane = df.loc[df["min_pct"] >= 20, "bpm"].dropna()
    if len(sane) < 100 or sane.between(-40, 40).mean() < 0.98 or not df["min_pct"].dropna().between(0, 100).all():
        raise ValueError("torvik players: unexpected values (file layout changed?)")
    return df


def parse_cbbd(raw: bytes) -> list[dict]:
    data = json.loads(raw)
    if not isinstance(data, list) or not data or "athleteId" not in data[0]:
        raise ValueError("cbbd players: unexpected response")
    return data


# ------------------------------------------------------------------ building

def build(cbbd: list[dict], torvik: pd.DataFrame | None, crosswalk) -> list[dict]:
    """All D1 players with ratings; eligible ones get a composite score and rank."""
    by_cbbd = {str(r.cbbd_id): r.team_id for r in crosswalk.teams.itertuples() if str(r.cbbd_id)}
    players = [p for p in cbbd if str(p.get("teamId")) in by_cbbd and (p.get("minutes") or 0) > 0]

    # team minutes = total player minutes / 5 (five players on the floor)
    team_min: dict[str, float] = {}
    for p in players:
        tid = by_cbbd[str(p["teamId"])]
        team_min[tid] = team_min.get(tid, 0) + (p.get("minutes") or 0) / 5

    # Torvik rows by (team_id, normalized name)
    tv_index: dict[str, list[dict]] = {}
    if torvik is not None:
        tv_ids = crosswalk.resolve("torvik", torvik["team"]).team_ids
        for row, tid in zip(torvik.to_dict("records"), tv_ids):
            if isinstance(tid, str):
                tv_index.setdefault(tid, []).append({**row, "_n": norm_name(row["name"])})

    def match(tid: str, name: str) -> dict | None:
        cands = tv_index.get(tid, [])
        n = norm_name(name)
        for c in cands:
            if c["_n"] == n:
                return c
        best = max(cands, key=lambda c: fuzz.token_sort_ratio(n, c["_n"]), default=None)
        if best is not None and fuzz.token_sort_ratio(n, best["_n"]) >= 88:
            return best
        return None

    out = []
    for p in players:
        tid = by_cbbd[str(p["teamId"])]
        g = p.get("games") or 0
        share = (p.get("minutes") or 0) / team_min[tid] if team_min.get(tid) else 0
        tv = match(tid, p.get("name", "")) if tv_index else None
        reb, ws = p.get("rebounds") or {}, p.get("winShares") or {}
        fg3, ft = p.get("threePointFieldGoals") or {}, p.get("freeThrows") or {}
        per = lambda v: _r((v or 0) / g) if g else None  # noqa: E731
        out.append({
            "id": str(p["athleteId"]),
            "name": p.get("name"),
            "team_id": tid,
            "pos": p.get("position") or None,
            "role": (tv or {}).get("role") or None,
            "yr": (tv or {}).get("yr") or None,
            "ht": (tv or {}).get("ht") or None,
            "num": (tv or {}).get("num") or None,
            "games": g,
            "starts": p.get("starts"),
            "mpg": per(p.get("minutes")),
            "min_pct": _r(share * 100),
            "pts": per(p.get("points")), "reb": per(reb.get("total")), "ast": per(p.get("assists")),
            "stl": per(p.get("steals")), "blk": per(p.get("blocks")), "tov": per(p.get("turnovers")),
            "ts": _r(_pct(p.get("trueShootingPct"))), "efg": _r(_pct(p.get("effectiveFieldGoalPct"))),
            "fg3": _r(fg3.get("pct")), "fg3a": per(fg3.get("attempted")), "ft": _r(ft.get("pct")),
            "usage": _r(p.get("usage")), "ortg": _r(p.get("offensiveRating")), "drtg": _r(p.get("defensiveRating")),
            "ws": _r(ws.get("total"), 2),
            "raw": {
                "ws40": _num(ws.get("totalPer40")),
                "porpag": _num(p.get("PORPAG")),
                "bpm": _num((tv or {}).get("bpm")),
            },
            "obpm": _r((tv or {}).get("obpm")), "dbpm": _r((tv or {}).get("dbpm")),
            "eligible": share >= MIN_SHARE,
        })

    # z-scores among eligible players, then the composite
    elig = [p for p in out if p["eligible"]]
    stats = {}
    for k in METRICS:
        vals = pd.Series([p["raw"][k] for p in elig], dtype=float)
        stats[k] = (vals.mean(), vals.std(ddof=0)) if vals.notna().sum() > 1 else (None, None)
        ranked = vals.rank(ascending=False, method="min")
        for p, rk in zip(elig, ranked):
            p.setdefault("_rank", {})[k] = None if pd.isna(rk) else int(rk)
    for p in out:
        metrics, zs = {}, []
        for k in METRICS:
            v = p["raw"][k]
            mu, sd = stats[k]
            z = (v - mu) / sd if v is not None and mu is not None and sd else None
            if p["eligible"] and z is not None:
                zs.append(z)
            metrics[k] = {"value": _r(v, 2), "z": _r(z, 2),
                          "rank": p.get("_rank", {}).get(k) if p["eligible"] else None}
        p["metrics"] = metrics
        p["score"] = _r(sum(zs) / len(zs), 3) if p["eligible"] and zs else None
        p["n_metrics"] = len(zs) if p["eligible"] else 0
        p.pop("raw"), p.pop("_rank", None)
    scored = sorted((p for p in out if p["score"] is not None), key=lambda p: -p["score"])
    for i, p in enumerate(scored, 1):
        p["rank"] = i
    for p in out:
        p.setdefault("rank", None)
    return out


# ------------------------------------------------------------------ fetching & writing

def _fetch_cbbd(season: int, session: requests.Session | None) -> bytes:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise NotConfigured(f"{KEY_ENV} is not set")
    return fetch_bytes(CBBD_URL.format(season=season), session, headers={"Authorization": f"Bearer {key}"})


def _torvik(season: int, today: dt.date, cache_dir: Path, session) -> tuple[pd.DataFrame | None, str]:
    """Fresh Torvik file, else a cached one up to STALE_DAYS old, else None."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        raw = fetch_bytes(TORVIK_URL.format(season=season), session)
        df = parse_torvik(raw)
        for old in cache_dir.glob("torvik_players_*.csv"):
            old.unlink()
        (cache_dir / f"torvik_players_{today.isoformat()}.csv").write_bytes(raw)
        return df, "ok"
    except Exception as exc:  # noqa: BLE001 - fall back to cache
        log.warning("torvik players failed (%s: %s)", type(exc).__name__, exc)
        for path in sorted(cache_dir.glob("torvik_players_*.csv"), reverse=True):
            day = dt.date.fromisoformat(path.stem.rsplit("_", 1)[1])
            if (today - day).days <= STALE_DAYS:
                return parse_torvik(path.read_bytes()), f"stale ({day.isoformat()})"
        return None, "unavailable"


def _read_fixture(path: Path) -> bytes:
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def write(players: list[dict], site_data: Path, as_of: str, season: int, sources: dict) -> None:
    top = sorted((p for p in players if p["rank"]), key=lambda p: p["rank"])[:TOP_N]
    eligible = sum(1 for p in players if p["eligible"])
    doc = {
        "as_of": as_of, "season": season, "eligible": eligible, "min_share": MIN_SHARE,
        "sources": sources,
        "metrics": [{"key": k, "label": v[0], "desc": v[1], "source": v[2]} for k, v in METRICS.items()],
        "top": top,
    }
    (site_data / "players.json").write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))
    # rosters into the per-team files written by team_details
    by_team: dict[str, list[dict]] = {}
    for p in players:
        if (p["min_pct"] or 0) >= ROSTER_MIN_SHARE * 100:
            by_team.setdefault(p["team_id"], []).append(p)
    team_dir = site_data / "team"
    for tid, roster in by_team.items():
        path = team_dir / f"{tid}.json"
        doc_t = json.loads(path.read_text()) if path.exists() else {"as_of": as_of}
        doc_t["players"] = sorted(roster, key=lambda p: -(p["min_pct"] or 0))
        team_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc_t, separators=(",", ":"), ensure_ascii=False))


def run(season: int, today: dt.date, crosswalk, site_data: Path, cache_dir: Path,
        session: requests.Session | None = None, fixtures: Path | None = None) -> dict[str, Any]:
    """Build and write player ratings; never fails the daily run."""
    try:
        if fixtures:
            cbbd = parse_cbbd(_read_fixture(next(fixtures.glob("cbbd_players*"))))
            torvik, tv_status = parse_torvik(_read_fixture(next(fixtures.glob("torvik_players*")))), "ok"
        else:
            cbbd = parse_cbbd(_fetch_cbbd(season, session))
            torvik, tv_status = _torvik(season, today, cache_dir, session)
        players = build(cbbd, torvik, crosswalk)
        matched = sum(1 for p in players if p["metrics"]["bpm"]["value"] is not None)
        sources = {"cbbd": "ok", "torvik": tv_status, "torvik_matched": matched}
        write(players, site_data, today.isoformat(), season, sources)
        n_elig = sum(1 for p in players if p["eligible"])
        log.info("players: %d rated, %d eligible, %d matched to Torvik (%s)", len(players), n_elig, matched, tv_status)
        return {"status": "ok", "players": len(players), "eligible": n_elig, **sources}
    except NotConfigured as exc:
        log.warning("players skipped: %s", exc)
        return {"status": "not_configured", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - extras never fail the run
        log.error("players failed: %s: %s", type(exc).__name__, exc)
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
