"""Game predictions (winner, win %, score) and their running accuracy record.

Model, from the composite's cross-source offense, defense and tempo:

    possessions = tempo_home * tempo_away / avg_tempo
    points_home = adj_o_home * adj_d_away / avg_eff * possessions / 100
    (and the same for the away team), then the home team gets
    +home_court/2 and the away team -home_court/2 unless the site is neutral.
    win % for home = Phi(margin / margin_sd)

Predictions are kept in site/data/history/predictions.json, which the daily
workflow commits. A game's prediction is refreshed on every run until its
tip-off, then frozen; once the game is final it is graded. Only games
predicted before tip-off count toward the record.

site/data/games.json (rebuilt every run) is what the Games tab reads.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

import pandas as pd

from . import eastern_date

log = logging.getLogger("ncaambb")
_NORMAL = NormalDist()

DEFAULTS = {"home_court": 3.0, "margin_sd": 11.0}
BUCKETS = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


def _start(game: dict) -> dt.datetime | None:
    raw = game.get("startDate")
    if not raw:
        return None
    t = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


class Model:
    def __init__(self, table: pd.DataFrame, settings: dict[str, Any] | None = None):
        cfg = {**DEFAULTS, **(settings or {})}
        self.home_court = float(cfg["home_court"])
        self.margin_sd = float(cfg["margin_sd"])
        cols = ["adj_o", "adj_d", "tempo"]
        missing = [c for c in cols if c not in table.columns]
        if missing:
            raise ValueError(f"composite has no {missing}")
        self.ratings = table[cols].dropna()
        self.avg_eff = (self.ratings["adj_o"].mean() + self.ratings["adj_d"].mean()) / 2
        self.avg_tempo = self.ratings["tempo"].mean()

    def has(self, team_id: str | None) -> bool:
        return team_id is not None and team_id in self.ratings.index

    def predict(self, home: str, away: str, neutral: bool) -> dict[str, float]:
        h, a = self.ratings.loc[home], self.ratings.loc[away]
        poss = h["tempo"] * a["tempo"] / self.avg_tempo
        ph = h["adj_o"] * a["adj_d"] / self.avg_eff * poss / 100
        pa = a["adj_o"] * h["adj_d"] / self.avg_eff * poss / 100
        if not neutral:
            ph, pa = ph + self.home_court / 2, pa - self.home_court / 2
        p_home = _NORMAL.cdf((ph - pa) / self.margin_sd)
        return {"h": round(ph, 1), "a": round(pa, 1), "p": round(p_home, 3)}


# ---------------------------------------------------------------- log

def load_log(path: Path, season: int) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data.get("games", {}) if data.get("season") == season else {}


def update(
    entries: dict[str, dict],
    games: list[dict],
    model: Model,
    by_cbbd: dict[str, str],
    now: dt.datetime,
    as_of: str,
) -> dict[str, dict]:
    """Refresh predictions for games not yet started; record final scores."""
    for g in games:
        gid = str(g.get("id"))
        home, away = by_cbbd.get(str(g.get("homeTeamId"))), by_cbbd.get(str(g.get("awayTeamId")))
        start = _start(g)
        if g.get("status") == "scheduled" and start and start > now and model.has(home) and model.has(away):
            entries[gid] = {
                "date": eastern_date(g["startDate"]), "home": home, "away": away,
                "neutral": bool(g.get("neutralSite")), **model.predict(home, away, bool(g.get("neutralSite"))),
                "made": as_of,
            }
        elif gid in entries and g.get("status") == "final":
            hp, ap = g.get("homePoints"), g.get("awayPoints")
            if hp is not None and ap is not None:
                entries[gid]["final"] = [hp, ap]
    return entries


def write_log(path: Path, season: int, entries: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"season": season, "games": dict(sorted(entries.items(), key=lambda kv: (kv[1]["date"], kv[0])))}
    path.write_text(json.dumps(body, separators=(",", ":")))


# ---------------------------------------------------------------- record

def _graded(entries: dict[str, dict]) -> list[dict]:
    return [e for e in entries.values() if e.get("final") and e["final"][0] != e["final"][1]]


def summary(entries: dict[str, dict], today: str) -> dict[str, Any]:
    graded = _graded(entries)
    week_ago = (dt.date.fromisoformat(today) - dt.timedelta(days=7)).isoformat()

    def record(rows: list[dict]) -> dict[str, Any]:
        right = sum(1 for e in rows if (e["p"] >= 0.5) == (e["final"][0] > e["final"][1]))
        return {"games": len(rows), "correct": right,
                "pct": round(right / len(rows), 3) if rows else None}

    out: dict[str, Any] = {"overall": record(graded), "last_7_days": record([e for e in graded if e["date"] > week_ago])}
    if graded:
        out["margin_error"] = round(
            sum(abs((e["h"] - e["a"]) - (e["final"][0] - e["final"][1])) for e in graded) / len(graded), 1)
        out["total_error"] = round(
            sum(abs((e["h"] + e["a"]) - sum(e["final"])) for e in graded) / len(graded), 1)
    calib = []
    for lo, hi in BUCKETS:
        rows = [e for e in graded if lo <= max(e["p"], 1 - e["p"]) < hi]
        fav_won = sum(1 for e in rows if (e["p"] >= 0.5) == (e["final"][0] > e["final"][1]))
        calib.append({
            "range": f"{round(lo * 100)}–{min(round(hi * 100), 100)}%",
            "games": len(rows),
            "expected": round(sum(max(e["p"], 1 - e["p"]) for e in rows) / len(rows), 3) if rows else None,
            "actual": round(fav_won / len(rows), 3) if rows else None,
        })
    out["calibration"] = calib
    return out


# ---------------------------------------------------------------- site

def site_games(games: list[dict], entries: dict[str, dict], by_cbbd: dict[str, str]) -> list[dict]:
    """Every game with a D1 team, with its prediction when there is one."""
    rows = []
    for g in sorted(games, key=lambda g: (g.get("startDate") or "", g.get("id"))):
        home, away = by_cbbd.get(str(g.get("homeTeamId"))), by_cbbd.get(str(g.get("awayTeamId")))
        if home is None and away is None:
            continue
        e = entries.get(str(g.get("id")))
        final = g.get("status") == "final" and g.get("homePoints") is not None
        row = {
            "id": g.get("id"),
            "date": eastern_date(g.get("startDate") or ""),
            "start": g.get("startDate"),
            "tbd": bool(g.get("startTimeTbd")),
            "home": home, "away": away,
            # names only for non-D1 opponents; the page looks D1 teams up by id
            "home_name": None if home else g.get("homeTeam"),
            "away_name": None if away else g.get("awayTeam"),
            "neutral": bool(g.get("neutralSite")),
            "conf": bool(g.get("conferenceGame")),
            "status": g.get("status"),
            "score": [g.get("homePoints"), g.get("awayPoints")] if final else None,
            "pred": {k: e[k] for k in ("h", "a", "p")} if e else None,
            "note": g.get("gameNotes") or None,
        }
        # drop empty fields to keep the file small (it holds the whole season)
        rows.append({k: v for k, v in row.items() if v not in (None, False)})
    return rows


def team_view(entries: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """team_id -> game id -> the prediction from that team's side."""
    out: dict[str, dict[str, dict]] = {}
    for gid, e in entries.items():
        for side, p in (("home", e["p"]), ("away", 1 - e["p"])):
            mine, theirs = (e["h"], e["a"]) if side == "home" else (e["a"], e["h"])
            view = {"score": f"{round(mine)}-{round(theirs)}", "win": round(p, 3)}
            if e.get("final") and e["final"][0] != e["final"][1]:
                won = (e["final"][0] > e["final"][1]) == (side == "home")
                view["correct"] = (p >= 0.5) == won
            out.setdefault(e[side], {})[gid] = view
    return out


def run(
    season: int,
    today: dt.date,
    now: dt.datetime,
    games: list[dict],
    table: pd.DataFrame,
    teams: pd.DataFrame,
    site_data: Path,
    settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, dict]]]:
    """Update the log, write games.json; returns (status for meta, team_view)."""
    by_cbbd = {str(r.cbbd_id): r.team_id for r in teams.itertuples() if str(r.cbbd_id)}
    model = Model(table, settings)
    log_path = site_data / "history" / "predictions.json"
    entries = update(load_log(log_path, season), games, model, by_cbbd, now, today.isoformat())
    write_log(log_path, season, entries)
    record = summary(entries, today.isoformat())
    body = {
        "as_of": today.isoformat(),
        "model": {"home_court": model.home_court, "margin_sd": model.margin_sd},
        "record": record,
        "games": site_games(games, entries, by_cbbd),
    }
    (site_data / "games.json").write_text(json.dumps(body, separators=(",", ":"), ensure_ascii=False))
    upcoming = sum(1 for e in entries.values() if not e.get("final") and e["date"] >= today.isoformat())
    log.info("predictions: %d upcoming, record %s", upcoming, record["overall"])
    return {"status": "ok", "upcoming": upcoming, **record["overall"]}, team_view(entries)
