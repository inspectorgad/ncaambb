import pandas as pd
import pytest

from ncaambb.schema import ValidationError, validate_wide
from ncaambb.sources import REGISTRY

SOURCES = ["torvik", "haslametrics", "espn_bpi"]
CORE = ["source_name", "conference", "rating", "rating_rank", "wins", "losses", "record"]


@pytest.mark.parametrize("source", SOURCES)
def test_parses_all_teams_and_validates(source, raw):
    df = REGISTRY[source].parse(raw[source])
    assert len(df) == 365
    assert set(CORE) <= set(df.columns)
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
