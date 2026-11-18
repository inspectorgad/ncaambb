import pandas as pd
import pytest

from ncaambb import DATA_DIR
from ncaambb.crosswalk import Crosswalk
from ncaambb.sources import REGISTRY

SOURCES = ["torvik", "haslametrics", "espn_bpi", "teamrankings", "warrennolan"]


@pytest.fixture(scope="module")
def crosswalk():
    return Crosswalk.load()


def test_teams_csv_is_clean(crosswalk):
    teams = crosswalk.teams
    assert len(teams) == 365
    assert teams["team_id"].is_unique
    assert teams["espn_id"].is_unique
    assert teams["team_id"].str.fullmatch(r"[a-z0-9-]+").all()


@pytest.mark.parametrize("source", SOURCES)
def test_every_team_maps_exactly_once(source, raw, crosswalk):
    wide = REGISTRY[source].parse(raw[source])
    mapped, unmatched = crosswalk.apply(source, wide)
    assert unmatched == []
    assert len(mapped) == 365
    assert set(mapped["team_id"]) == set(crosswalk.teams["team_id"])


@pytest.mark.parametrize("source", ["torvik", "haslametrics"])
def test_conferences_agree_with_espn(source, raw, crosswalk):
    """A wrong alias almost always puts a team in the wrong conference."""
    conf_map = pd.read_csv(DATA_DIR / "conferences.csv")
    conf_map = conf_map[conf_map["source"] == source]
    conf_map = dict(zip(conf_map["source_conference"], conf_map["conference"]))
    mapped, _ = crosswalk.apply(source, REGISTRY[source].parse(raw[source]))
    espn_conf = crosswalk.teams.set_index("team_id")["conference"]
    got = mapped["conference"].map(conf_map)
    want = mapped["team_id"].map(espn_conf)
    wrong = mapped.loc[got != want, ["source_name", "conference", "team_id"]]
    assert wrong.empty, wrong.to_string()


def test_ncaa_net_last_season_fixture(raw, crosswalk):
    """Saved page is 2025-26: Saint Francis (PA) has since left D1 and
    West Florida joined, so exactly one name is unmatched."""
    mapped, unmatched = crosswalk.apply("ncaa_net", REGISTRY["ncaa_net"].parse(raw["ncaa_net"]))
    assert unmatched == ["Saint Francis"]
    assert len(mapped) == 364


def test_unknown_names_are_reported_not_guessed(crosswalk):
    wide = pd.DataFrame({"source_name": ["Kansas", "Hogwarts"]})
    mapped, unmatched = crosswalk.apply("torvik", wide)
    assert mapped["team_id"].tolist() == ["kansas"]
    assert unmatched == ["Hogwarts"]


def test_two_names_for_one_team_is_an_error():
    teams = pd.DataFrame({"team_id": ["uconn"], "espn_id": ["41"]})
    aliases = pd.DataFrame(
        {"source": ["x", "x"], "source_name": ["UConn", "Connecticut"], "team_id": ["uconn"] * 2}
    )
    with pytest.raises(ValueError, match="same team"):
        Crosswalk(teams, aliases).apply("x", pd.DataFrame({"source_name": ["UConn", "Connecticut"]}))
