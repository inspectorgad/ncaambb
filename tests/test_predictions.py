import datetime as dt
import gzip
import json

import pandas as pd
import pytest

from ncaambb import pipeline, predictions

UTC = dt.timezone.utc


@pytest.fixture
def model():
    table = pd.DataFrame(
        {"adj_o": [115.0, 100.0, 105.0], "adj_d": [95.0, 110.0, 105.0], "tempo": [70.0, 66.0, 68.0]},
        index=["good", "bad", "avg"],
    )
    return predictions.Model(table, {"home_court": 3.0, "margin_sd": 11.0})


def game(gid, home_cbbd, away_cbbd, start, status="scheduled", hp=None, ap=None, neutral=False):
    return {"id": gid, "homeTeamId": home_cbbd, "awayTeamId": away_cbbd, "startDate": start,
            "status": status, "homePoints": hp, "awayPoints": ap, "neutralSite": neutral}


BY_CBBD = {"1": "good", "2": "bad", "3": "avg"}


def test_better_team_is_favored_and_home_court_counts(model):
    neutral = model.predict("good", "bad", neutral=True)
    home = model.predict("good", "bad", neutral=False)
    assert neutral["p"] > 0.9 and neutral["h"] > neutral["a"]
    assert home["h"] - home["a"] == pytest.approx(neutral["h"] - neutral["a"] + 3.0, abs=0.15)
    flipped = model.predict("bad", "good", neutral=True)
    assert flipped["p"] == pytest.approx(1 - neutral["p"], abs=0.002)


def test_even_teams_at_neutral_site_are_a_coin_flip(model):
    assert model.predict("avg", "avg", neutral=True)["p"] == pytest.approx(0.5)


def test_prediction_freezes_at_tip_off_and_is_graded(model):
    start = "2026-11-21T00:00:00.000Z"
    before = dt.datetime(2026, 11, 20, 11, tzinfo=UTC)
    after = dt.datetime(2026, 11, 21, 11, tzinfo=UTC)
    entries = predictions.update({}, [game(9, 1, 2, start)], model, BY_CBBD, before, "2026-11-20")
    made = dict(entries["9"])
    assert made["date"] == "2026-11-20" and made["made"] == "2026-11-20"

    # ratings change after tip-off: the stored prediction must not move
    other = predictions.Model(model.ratings.assign(adj_o=[100.0, 115.0, 105.0]))
    entries = predictions.update(entries, [game(9, 1, 2, start, "final", 80, 70)], other, BY_CBBD, after, "2026-11-21")
    assert {k: v for k, v in entries["9"].items() if k != "final"} == made
    assert entries["9"]["final"] == [80, 70]


def test_games_already_started_are_never_predicted(model):
    now = dt.datetime(2026, 11, 21, 11, tzinfo=UTC)
    games = [game(1, 1, 2, "2026-11-20T00:00:00.000Z", "final", 80, 70),
             game(2, 1, 2, "2026-11-21T10:00:00.000Z", "in_progress"),
             game(3, 1, 99, "2026-11-22T00:00:00.000Z")]  # non-D1 opponent
    assert predictions.update({}, games, model, BY_CBBD, now, "2026-11-21") == {}


def test_record_and_calibration():
    entries = {
        "1": {"date": "2026-11-18", "home": "a", "away": "b", "h": 75, "a": 65, "p": 0.82, "final": [70, 60]},
        "2": {"date": "2026-11-19", "home": "a", "away": "b", "h": 70, "a": 72, "p": 0.45, "final": [80, 70]},
        "3": {"date": "2026-11-19", "home": "a", "away": "b", "h": 60, "a": 70, "p": 0.18, "final": [60, 70]},
        "4": {"date": "2026-11-20", "home": "a", "away": "b", "h": 70, "a": 60, "p": 0.8},  # not played yet
    }
    rec = predictions.summary(entries, "2026-11-20")
    assert rec["overall"] == {"games": 3, "correct": 2, "pct": 0.667}
    assert rec["margin_error"] == pytest.approx((0 + 12 + 0) / 3, abs=0.05)
    by_range = {c["range"]: c for c in rec["calibration"]}
    assert by_range["80–90%"] == {"range": "80–90%", "games": 2, "expected": 0.82, "actual": 1.0}
    assert by_range["50–60%"]["actual"] == 0.0


def test_team_view_is_from_each_side():
    entries = {"5": {"date": "2026-11-19", "home": "a", "away": "b", "h": 75.4, "a": 65.2, "p": 0.8,
                     "final": [60, 70]}}
    view = predictions.team_view(entries)
    assert view["a"]["5"] == {"score": "75-65", "win": 0.8, "correct": False}
    assert view["b"]["5"] == {"score": "65-75", "win": 0.2, "correct": False}


def test_pipeline_writes_games_and_team_predictions(fixtures_dir, tmp_path):
    paths = pipeline.Paths(cache=tmp_path / "cache", site_data=tmp_path / "site", raw=None)
    pipeline.run(fixtures=fixtures_dir, paths=paths, today=dt.date(2026, 11, 19))
    site = tmp_path / "site"
    body = json.loads((site / "games.json").read_text())
    predicted = [g for g in body["games"] if "pred" in g]
    assert predicted and all(g["start"] > "2026-11-19T11:00" for g in predicted)  # 6 AM ET run
    assert all(g.get("home") and g.get("away") for g in predicted)
    assert json.loads((site / "history" / "predictions.json").read_text())["season"] == 2027
    kansas = json.loads((site / "team" / "kansas.json").read_text())
    upcoming = [g for g in kansas["games"] if g["status"] == "scheduled" and g["date"] >= "2026-11-20"]
    assert upcoming and all(g["pred"] and 0 <= g["pred"]["win"] <= 1 for g in upcoming)
    meta = json.loads((site / "meta.json").read_text())
    assert meta["team_details"]["predictions"]["status"] == "ok"
