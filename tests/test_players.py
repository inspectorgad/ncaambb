import gzip
import json

import pandas as pd
import pytest

from ncaambb import players
from ncaambb.crosswalk import Crosswalk


@pytest.fixture(scope="module")
def built(fixtures_dir):
    cbbd = players.parse_cbbd(gzip.decompress((fixtures_dir / "cbbd_players_2027.json.gz").read_bytes()))
    torvik = players.parse_torvik(gzip.decompress((fixtures_dir / "torvik_players_2027.csv.gz").read_bytes()))
    return players.build(cbbd, torvik, Crosswalk.load())


def test_names_normalize_for_matching():
    assert players.norm_name("Patrick Ngongba II") == players.norm_name("Patrick Ngongba")
    assert players.norm_name("Silas Demary Jr.") == "silas demary"
    assert players.norm_name("José Pérez") == "jose perez"


def test_minute_shares_and_eligibility(built):
    by_team = {}
    for p in built:
        by_team.setdefault(p["team_id"], []).append(p)
    # five players on the floor: shares on a team add up to ~500%
    for roster in by_team.values():
        assert sum(p["min_pct"] for p in roster) == pytest.approx(500, abs=3)
    assert all(p["eligible"] == (p["min_pct"] >= 40) for p in built)


def test_composite_ranks_eligible_players_only(built):
    ranked = sorted((p for p in built if p["rank"]), key=lambda p: p["rank"])
    assert ranked and all(p["eligible"] for p in ranked)
    assert [p["rank"] for p in ranked] == list(range(1, len(ranked) + 1))
    assert all(a["score"] >= b["score"] for a, b in zip(ranked, ranked[1:]))
    assert all(p["rank"] is None and p["score"] is None for p in built if not p["eligible"])
    # z-scores average to ~0 across eligible players
    zs = [p["metrics"]["ws40"]["z"] for p in built if p["eligible"] and p["metrics"]["ws40"]["z"] is not None]
    assert sum(zs) / len(zs) == pytest.approx(0, abs=0.01)


def test_torvik_matching_fills_bpm_and_bio(built):
    elig = [p for p in built if p["eligible"]]
    matched = [p for p in elig if p["metrics"]["bpm"]["value"] is not None]
    assert len(matched) / len(elig) > 0.9
    assert any(p["yr"] in {"Fr", "So", "Jr", "Sr"} and p["ht"] for p in matched)


def test_without_torvik_the_composite_still_runs(fixtures_dir):
    cbbd = players.parse_cbbd(gzip.decompress((fixtures_dir / "cbbd_players_2027.json.gz").read_bytes()))
    out = players.build(cbbd, None, Crosswalk.load())
    top = min((p for p in out if p["rank"]), key=lambda p: p["rank"])
    assert top["n_metrics"] == 2 and top["metrics"]["bpm"]["value"] is None


def test_torvik_layout_check_rejects_garbage():
    with pytest.raises(ValueError):
        players.parse_torvik(b"a,b,c\n1,2,3\n")


def test_write_top50_and_rosters(built, tmp_path):
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "kansas.json").write_text(json.dumps({"as_of": "x", "games": []}))
    players.write(built, tmp_path, "2026-11-19", 2027, {"cbbd": "ok", "torvik": "ok"})
    doc = json.loads((tmp_path / "players.json").read_text())
    assert len(doc["top"]) == 50 and doc["top"][0]["rank"] == 1
    assert {m["key"] for m in doc["metrics"]} == {"ws40", "porpag", "bpm"}
    kansas = json.loads((team_dir / "kansas.json").read_text())
    assert kansas["games"] == [] and kansas["players"]  # roster added, existing data kept
    shares = [p["min_pct"] for p in kansas["players"]]
    assert shares == sorted(shares, reverse=True)


def test_shooting_rates_are_percentages(built):
    shooters = [p for p in built if p["eligible"] and p["ts"]]
    assert all(10 <= p["ts"] <= 100 for p in shooters)
    assert players._pct(0.712) == pytest.approx(71.2) and players._pct(71.2) == 71.2
