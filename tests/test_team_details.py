import datetime as dt
import gzip
import json

import pytest

from ncaambb import team_details
from ncaambb.crosswalk import Crosswalk


@pytest.fixture(scope="module")
def built(fixtures_dir):
    load = lambda name: json.loads(gzip.decompress((fixtures_dir / name).read_bytes()))
    return team_details.build(
        load("cbbd_team_stats_2027.json.gz"), load("cbbd_games_2027.json.gz"), Crosswalk.load().teams
    )


def test_every_d1_team_has_a_block(built):
    assert len(built) == 365


def test_kansas_values(built):
    k = built["kansas"]
    assert k["games_played"] == 4
    ff = {f["key"]: f for f in k["four_factors"]}
    assert ff["efg"]["off"] == pytest.approx(63.3)
    assert ff["tov"]["off"] == pytest.approx(18.0)  # API gives 0.18; shown as a %
    stats = {s["key"]: s for s in k["stats"]}
    assert stats["ppg"]["team"] == pytest.approx(93.8)


def test_ranks_run_the_right_way(built):
    ppg = {tid: next(s for s in b["stats"] if s["key"] == "ppg") for tid, b in built.items()}
    best_offense = min(ppg, key=lambda t: ppg[t]["team_rank"])
    assert ppg[best_offense]["team"] == max(p["team"] for p in ppg.values())
    best_defense = min(ppg, key=lambda t: ppg[t]["opp_rank"])
    assert ppg[best_defense]["opp"] == min(p["opp"] for p in ppg.values())  # fewest points allowed


def test_game_log(built):
    games = built["kansas"]["games"]
    final = [g for g in games if g["result"]]
    assert [g["result"] for g in final] == ["W"] * 4
    first = {k: v for k, v in final[0].items() if k not in ("id", "pred")}
    assert first == {
        # 8 PM ET on Nov 2 is 01:00 UTC on Nov 3: the date must be the Eastern one
        "date": "2026-11-02", "start": "2026-11-03T01:00:00.000Z",
        "opp": "fordham", "opp_name": "Fordham", "site": "H", "conf": False,
        "status": "final", "result": "W", "score": "95-65", "note": None,
    }
    wvu = next(g for g in games if g["opp"] == "west-virginia")
    assert wvu["date"] == "2026-11-18"  # 7:30 PM ET tip-off, 00:30 UTC Nov 19
    assert games == sorted(games, key=lambda g: g["date"])


def test_non_d1_opponents_have_no_team_id(built):
    non_d1 = [g for b in built.values() for g in b["games"] if g["opp"] is None]
    assert non_d1 and all(g["opp_name"] for g in non_d1)


def test_fetch_games_backfills_then_updates_incrementally(tmp_path, monkeypatch):
    calls, next_id = [], iter(range(1, 100))

    def fake_get(session, path, **params):
        calls.append((params["startDateRange"], params["endDateRange"]))
        return [{"id": next(next_id), "startDate": params["startDateRange"]}]

    monkeypatch.setattr(team_details, "_get", fake_get)
    cache = tmp_path / "games.json"
    today = dt.date(2026, 11, 18)
    first = team_details.fetch_games(None, 2027, today, cache)
    # cold cache: Nov 1 .. Nov 25 in 14-day chunks
    assert calls == [("2026-11-01", "2026-11-14"), ("2026-11-15", "2026-11-25")]
    assert len(first) == 2

    calls.clear()
    second = team_details.fetch_games(None, 2027, today + dt.timedelta(days=1), cache)
    assert calls == [("2026-11-16", "2026-11-26")]  # one call: 3 days back, 7 ahead
    assert len(second) == 3

    calls.clear()
    team_details.fetch_games(None, 2028, dt.date(2027, 11, 3), cache)  # new season: back-fill again
    assert calls[0][0] == "2027-11-01"


def test_run_without_key_is_not_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("CBBD_API_KEY", raising=False)
    status = team_details.run(2027, dt.date(2026, 11, 18), Crosswalk.load().teams,
                              out_dir=tmp_path / "team", cache_dir=tmp_path)
    assert status["status"] == "not_configured"
