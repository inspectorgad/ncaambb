"""Per-team season stats, four factors and game log (from CollegeBasketballData).

Writes site/data/team/<team_id>.json, loaded only by that team's page.
Never fails the daily run: errors are logged and reported in meta.json.

API use stays small: 1 call for season stats, and for games 1 call per day
(the last 3 days plus the next 7, merged into a cached copy in
data/latest/cbbd_games.json). With no cache, the season so far is
back-filled in 14-day chunks.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from . import eastern_date, predictions
from .fetching import NotConfigured, fetch_bytes
from .sources.base import season_start

log = logging.getLogger("ncaambb")

API = "https://api.collegebasketballdata.com"
KEY_ENV = "CBBD_API_KEY"
CHUNK_DAYS = 14
LOOKBACK_DAYS = 3
LOOKAHEAD_DAYS = 7

# (key, label, getter(stats_block, games) -> value, higher_is_better)
def _pg(path: tuple[str, ...]):
    def get(block: dict, games: int) -> float | None:
        v = block
        for p in path:
            v = (v or {}).get(p)
        return None if v is None or not games else v / games
    return get


def _val(path: tuple[str, ...], scale: float = 1.0):
    def get(block: dict, games: int) -> float | None:
        v = block
        for p in path:
            v = (v or {}).get(p)
        return None if v is None else v * scale
    return get


SEASON_STATS = [
    ("ppg", "Points", _pg(("points", "total")), True),
    ("fg_pct", "Field goal %", _val(("fieldGoals", "pct")), True),
    ("two_pct", "2-point %", _val(("twoPointFieldGoals", "pct")), True),
    ("three_pct", "3-point %", _val(("threePointFieldGoals", "pct")), True),
    ("three_pa", "3-point attempts", _pg(("threePointFieldGoals", "attempted")), True),
    ("ft_pct", "Free throw %", _val(("freeThrows", "pct")), True),
    ("ts_pct", "True shooting %", _val(("trueShooting",)), True),
    ("reb", "Rebounds", _pg(("rebounds", "total")), True),
    ("oreb", "Offensive rebounds", _pg(("rebounds", "offensive")), True),
    ("ast", "Assists", _pg(("assists",)), True),
    ("tov", "Turnovers", _pg(("turnovers", "total")), False),
    ("stl", "Steals", _pg(("steals",)), True),
    ("blk", "Blocks", _pg(("blocks",)), True),
]
# For the opponents' column, "better" flips: fewer opponent points is better, etc.

FOUR_FACTORS = [
    ("efg", "Effective FG %", _val(("fourFactors", "effectiveFieldGoalPct"))),
    ("tov", "Turnover %", _val(("fourFactors", "turnoverRatio"), 100.0)),
    ("orb", "Offensive rebound %", _val(("fourFactors", "offensiveReboundPct"))),
    ("ftr", "Free throw rate", _val(("fourFactors", "freeThrowRate"))),
]
# offense: high efg/orb/ftr good, low tov good; defense (opponents): the reverse
FF_OFF_HIGHER_BETTER = {"efg": True, "tov": False, "orb": True, "ftr": True}


# ---------------------------------------------------------------- fetching

def _key() -> str:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise NotConfigured(f"{KEY_ENV} is not set")
    return key


def _get(session: requests.Session | None, path: str, **params: Any) -> Any:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    raw = fetch_bytes(f"{API}/{path}?{query}", session, headers={"Authorization": f"Bearer {_key()}"})
    return json.loads(raw)


def fetch_games(
    session: requests.Session | None, season: int, today: dt.date, cache_path: Path
) -> list[dict]:
    games: dict[str, dict] = {}
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get("season") == season:
            games = cached["games"]
    if games:
        windows = [(today - dt.timedelta(days=LOOKBACK_DAYS), today + dt.timedelta(days=LOOKAHEAD_DAYS))]
    else:  # back-fill the season so far in chunks
        windows, start = [], season_start(season)
        end = today + dt.timedelta(days=LOOKAHEAD_DAYS)
        while start <= end:
            stop = min(start + dt.timedelta(days=CHUNK_DAYS - 1), end)
            windows.append((start, stop))
            start = stop + dt.timedelta(days=1)
    for lo, hi in windows:
        for g in _get(session, "games", season=season, startDateRange=lo.isoformat(),
                      endDateRange=hi.isoformat()):
            games[str(g["id"])] = g
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"season": season, "games": games}))
    return list(games.values())


# ---------------------------------------------------------------- building

def _rank(values: pd.Series, higher_is_better: bool) -> pd.Series:
    return values.rank(ascending=not higher_is_better, method="min")


def build(
    stats: list[dict], games: list[dict], teams: pd.DataFrame,
    preds: dict[str, dict[str, dict]] | None = None,
) -> dict[str, dict]:
    """CBBD rows -> {team_id: {"stats": ..., "four_factors": ..., "games": [...]}}.

    preds: team_id -> game id -> that team's prediction (from predictions.team_view).
    """
    preds = preds or {}
    by_cbbd = {str(r.cbbd_id): r.team_id for r in teams.itertuples() if str(r.cbbd_id)}
    d1 = [s for s in stats if str(s.get("teamId")) in by_cbbd]

    rows = {}
    for s in d1:
        n = s.get("games") or 0
        team, opp = s.get("teamStats") or {}, s.get("opponentStats") or {}
        row = {"games": n, "pace": s.get("pace")}
        for key, _, get, _ in SEASON_STATS:
            row[f"t_{key}"], row[f"o_{key}"] = get(team, n), get(opp, n)
        for key, _, get in FOUR_FACTORS:
            row[f"off_{key}"], row[f"def_{key}"] = get(team, n), get(opp, n)
        rows[by_cbbd[str(s["teamId"])]] = row
    df = pd.DataFrame.from_dict(rows, orient="index").apply(pd.to_numeric, errors="coerce")

    ranks = {}
    for key, _, _, higher in SEASON_STATS:
        ranks[f"t_{key}"] = _rank(df[f"t_{key}"], higher)
        ranks[f"o_{key}"] = _rank(df[f"o_{key}"], not higher)
    for key, _, _ in FOUR_FACTORS:
        ranks[f"off_{key}"] = _rank(df[f"off_{key}"], FF_OFF_HIGHER_BETTER[key])
        ranks[f"def_{key}"] = _rank(df[f"def_{key}"], not FF_OFF_HIGHER_BETTER[key])
    ranks["pace"] = _rank(df["pace"], True)

    def num(v: Any, digits: int = 1) -> Any:
        return None if v is None or pd.isna(v) else round(float(v), digits)

    out: dict[str, dict] = {}
    for team_id, row in df.iterrows():
        out[team_id] = {
            "games_played": int(row["games"]) if pd.notna(row["games"]) else None,
            "pace": {"value": num(row["pace"]), "rank": num(ranks["pace"][team_id], 0)},
            "stats": [
                {
                    "key": key, "label": label,
                    "team": num(row[f"t_{key}"]), "team_rank": num(ranks[f"t_{key}"][team_id], 0),
                    "opp": num(row[f"o_{key}"]), "opp_rank": num(ranks[f"o_{key}"][team_id], 0),
                    "higher_is_better": higher,
                }
                for key, label, _, higher in SEASON_STATS
            ],
            "four_factors": [
                {
                    "key": key, "label": label,
                    "off": num(row[f"off_{key}"]), "off_rank": num(ranks[f"off_{key}"][team_id], 0),
                    "def": num(row[f"def_{key}"]), "def_rank": num(ranks[f"def_{key}"][team_id], 0),
                }
                for key, label, _ in FOUR_FACTORS
            ],
            "games": [],
        }

    for g in sorted(games, key=lambda g: g.get("startDate") or ""):
        for side, other in (("home", "away"), ("away", "home")):
            team_id = by_cbbd.get(str(g.get(f"{side}TeamId")))
            if team_id is None or team_id not in out:
                continue
            pts, opp_pts = g.get(f"{side}Points"), g.get(f"{other}Points")
            final = g.get("status") == "final" and pts is not None and opp_pts is not None
            out[team_id]["games"].append(
                {
                    "id": g.get("id"),
                    "date": eastern_date(g.get("startDate") or ""),  # Eastern calendar date
                    "start": g.get("startDate"),                       # exact tip-off (UTC)
                    "opp": by_cbbd.get(str(g.get(f"{other}TeamId"))),  # None = non-D1
                    "opp_name": g.get(f"{other}Team"),
                    "site": "N" if g.get("neutralSite") else ("H" if side == "home" else "A"),
                    "conf": bool(g.get("conferenceGame")),
                    "status": g.get("status"),
                    "result": ("W" if pts > opp_pts else "L") if final else None,
                    "score": f"{pts}-{opp_pts}" if final else None,
                    "note": g.get("gameNotes") or None,
                    "pred": preds.get(team_id, {}).get(str(g.get("id"))),
                }
            )
    return out


def write(details: dict[str, dict], out_dir: Path, as_of: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    for team_id, block in details.items():
        (out_dir / f"{team_id}.json").write_text(
            json.dumps({"as_of": as_of, **block}, separators=(",", ":"), ensure_ascii=False)
        )


def _read_fixture(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def run(
    season: int,
    today: dt.date,
    teams: pd.DataFrame,
    out_dir: Path,
    cache_dir: Path,
    session: requests.Session | None = None,
    fixtures: Path | None = None,
    table: pd.DataFrame | None = None,
    now: dt.datetime | None = None,
    prediction_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and write the per-team files; returns a status dict for meta.json.

    With the composite `table`, also runs the game predictions (games.json);
    their status is returned under "predictions".
    """
    pred_status: dict[str, Any] = {"status": "not_run"}
    try:
        if fixtures:
            stats = _read_fixture(next(fixtures.glob("cbbd_team_stats*")))
            games = _read_fixture(next(fixtures.glob("cbbd_games*")))
        else:
            stats = _get(session, "stats/team/season", season=season)
            games = fetch_games(session, season, today, cache_dir / "cbbd_games.json")
        team_preds = None
        if table is not None:
            try:
                pred_status, team_preds = predictions.run(
                    season, today, now or dt.datetime.now(dt.timezone.utc), games, table, teams,
                    site_data=out_dir.parent, settings=prediction_settings,
                )
            except Exception as exc:  # predictions are extras too
                log.error("predictions failed: %s: %s", type(exc).__name__, exc)
                pred_status = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        details = build(stats, games, teams, team_preds)
        write(details, out_dir, today.isoformat())
        n_games = sum(1 for g in games if g.get("status") == "final")
        log.info("team details: %d teams, %d final games", len(details), n_games)
        return {"status": "ok", "teams": len(details), "final_games": n_games, "predictions": pred_status}
    except NotConfigured as exc:
        log.warning("team details skipped: %s", exc)
        return {"status": "not_configured", "error": str(exc), "predictions": pred_status}
    except Exception as exc:  # never fail the daily run over extras
        log.error("team details failed: %s: %s", type(exc).__name__, exc)
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "predictions": pred_status}
