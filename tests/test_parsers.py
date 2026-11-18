import datetime as dt

import pandas as pd
import pytest

from ncaambb.schema import ValidationError, validate_wide
from ncaambb.sources import REGISTRY

RATING_SOURCES = ["torvik", "haslametrics", "espn_bpi", "teamrankings", "cbbd"]
NET_SOURCES = ["warrennolan", "ncaa_net"]
CORE = ["source_name", "rating", "rating_rank", "wins", "losses", "record"]


@pytest.mark.parametrize("source", RATING_SOURCES)
def test_parses_all_teams_and_validates(source, raw):
    df = REGISTRY[source].parse(raw[source])
    assert len(df) >= 364  # CBBD has no rating yet for one team
    assert set(CORE) - {"wins", "losses", "record"} <= set(df.columns)
    validate_wide(df, source)
    # rank 1 is the best team by the metric that source ranks on
    # (Haslametrics ranks by All-Play %, the others by their rating)
    ranked_by = "all_play" if source == "haslametrics" else "rating"
    top = df.loc[df["rating_rank"] == 1, ranked_by].iloc[0]
    assert top == pytest.approx(df[ranked_by].max())


@pytest.mark.parametrize("source", ["torvik", "haslametrics"])
def test_efficiency_columns(source, raw):
    df = REGISTRY[source].parse(raw[source])
    assert (df["adj_em"] - (df["adj_o"] - df["adj_d"])).abs().max() < 1e-9
    assert df["tempo"].between(55, 85).all()


def test_torvik_known_values(raw):
    df = REGISTRY["torvik"].parse(raw["torvik"]).set_index("source_name")
    kansas = df.loc["Kansas"]
    assert kansas["rating_rank"] == 1
    assert kansas["record"] == "4-0"
    assert kansas["adj_o"] == pytest.approx(121.5557, abs=1e-3)


def test_haslametrics_known_values(raw):
    df = REGISTRY["haslametrics"].parse(raw["haslametrics"]).set_index("source_name")
    duke = df.loc["Duke"]
    assert duke["rating_rank"] == 1
    assert duke["q1"] == "0-2"


def test_espn_known_values(raw):
    df = REGISTRY["espn_bpi"].parse(raw["espn_bpi"]).set_index("espn_name")
    illinois = df.loc["Illinois"]
    assert illinois["rating_rank"] == 1
    assert illinois["rating"] == pytest.approx(22.7278)
    assert illinois["source_name"] == "356"


def test_torvik_rejects_changed_layout():
    with pytest.raises(ValueError, match="missing columns"):
        REGISTRY["torvik"].parse(b"rank,team\n1,Kansas\n")


def test_haslametrics_rejects_empty_xml():
    with pytest.raises(ValueError, match="no <mr>"):
        REGISTRY["haslametrics"].parse(b"<mydata></mydata>")


def test_validation_catches_bad_data(raw):
    df = REGISTRY["torvik"].parse(raw["torvik"])
    with pytest.raises(ValidationError, match="only 10 teams"):
        validate_wide(df.head(10), "torvik")
    broken = df.copy()
    broken.loc[0, "tempo"] = 200
    with pytest.raises(ValidationError, match="tempo outside"):
        validate_wide(broken, "torvik")
    dup = pd.concat([df, df.head(1)])
    with pytest.raises(ValidationError, match="duplicate"):
        validate_wide(dup, "torvik")


@pytest.mark.parametrize("source", NET_SOURCES)
def test_net_pages(source, raw):
    df = REGISTRY[source].parse(raw[source])
    validate_wide(df, source)
    assert {"source_name", "net_rank", "record", "wins", "losses"} <= set(df.columns)
    assert df["net_rank"].min() == 1


def test_teamrankings_splits_name_and_record(raw):
    df = REGISTRY["teamrankings"].parse(raw["teamrankings"]).set_index("source_name")
    assert df.loc["Illinois", "record"] == "4-1"
    assert df.loc["Illinois", "rating"] == pytest.approx(26.7)
    assert not df.index.str.contains(r"\(").any()


def test_ncaa_net_quads(raw):
    df = REGISTRY["ncaa_net"].parse(raw["ncaa_net"]).set_index("source_name")
    assert df.loc["Michigan", "net_rank"] == 1
    assert df.loc["Michigan", "q1"] == "21-3"


def test_data_through_dates(raw):
    today = dt.date(2026, 11, 18)
    assert REGISTRY["ncaa_net"].data_through(raw["ncaa_net"], today) == dt.date(2026, 4, 6)
    assert REGISTRY["warrennolan"].data_through(raw["warrennolan"], today) == dt.date(2026, 3, 15)
    # a December date seen in January belongs to the previous calendar year
    page = b"NET Rank updated for games through <b>DEC 30th</b>"
    assert REGISTRY["warrennolan"].data_through(page, dt.date(2027, 1, 5)) == dt.date(2026, 12, 30)
    assert REGISTRY["torvik"].data_through(raw["torvik"], today) is None


def test_espn_polls(raw):
    df = REGISTRY["espn_bpi"].parse(raw["espn_bpi"])
    for poll in ("ap", "coaches"):
        ranked = df[f"{poll}_rank"].dropna()
        assert len(ranked) == 25 and ranked.min() == 1 and ranked.max() == 25
    top = df.set_index("espn_name").loc["Florida"]
    assert top["ap_rank"] == 1 and top["ap_points"] == 1472


def test_cbbd_parse_and_key(raw, monkeypatch):
    df = REGISTRY["cbbd"].parse(raw["cbbd"]).set_index("source_name")
    assert df.loc["118", "rating"] == pytest.approx(19.5)  # Illinois
    assert df.loc["118", "rating_rank"] == 1
    from ncaambb.fetching import NotConfigured
    monkeypatch.delenv("CBBD_API_KEY", raising=False)
    with pytest.raises(NotConfigured):
        REGISTRY["cbbd"]("https://example.invalid/{season}", 2027).fetch()


def test_bracketmatrix(raw):
    df = REGISTRY["bracketmatrix"].parse(raw["bracketmatrix"])
    validate_wide(df, "bracketmatrix", min_teams=REGISTRY["bracketmatrix"].min_teams)
    assert len(df) == 160
    duke = df.set_index("source_name").loc["Duke"]
    assert duke["avg_seed"] == 1.0 and duke["brackets"] == 52 and duke["consensus_seed"] == 1
