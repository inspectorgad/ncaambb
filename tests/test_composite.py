import math

import numpy as np
import pandas as pd
import pytest

from ncaambb import composite
from ncaambb.composite import Input, combine, rank_to_z, zscore
from ncaambb.schema import to_long


def long_rows(data: dict[str, dict[str, list]], teams: list[str]) -> pd.DataFrame:
    """{source: {metric: values}} -> long rows for the given teams."""
    frames = []
    for source, metrics in data.items():
        wide = pd.DataFrame({"team_id": teams, "source_name": teams, **metrics})
        frames.append(to_long(wide, source, "2026-11-18"))
    return pd.concat(frames, ignore_index=True)


def test_zscore():
    z = zscore(pd.Series([1.0, 2.0, 3.0]))
    assert z.tolist() == pytest.approx([-1.2247, 0.0, 1.2247], abs=1e-4)
    assert zscore(pd.Series([5.0, 5.0])).isna().all()


def test_rank_to_z_is_symmetric_and_ordered():
    z = rank_to_z(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert z.is_monotonic_decreasing
    assert z.iloc[0] == pytest.approx(-z.iloc[3])
    assert z.iloc[0] == pytest.approx(1.1503, abs=1e-4)  # Φ⁻¹(0.875)


def test_combine_rescales_weights_for_missing_inputs():
    z = pd.DataFrame({"a": [1.0, 1.0], "b": [3.0, np.nan]})
    out, n = combine(z, pd.Series({"a": 0.25, "b": 0.75}), trim_min=4)
    assert out.tolist() == pytest.approx([2.5, 1.0])
    assert n.tolist() == [2, 1]


def test_combine_trims_high_and_low():
    z = pd.DataFrame({"a": [0.0], "b": [1.0], "c": [2.0], "d": [100.0]})
    out, _ = combine(z, pd.Series(1.0, index=list("abcd")), trim_min=4)
    assert out.iloc[0] == pytest.approx(1.5)  # mean of b, c


def test_pick_prefers_first_source():
    long = pd.concat([
        long_rows({"ncaa_net": {"net_rank": [1, np.nan]}}, ["x", "y"]),
        long_rows({"warrennolan": {"net_rank": [9, 2]}}, ["x", "y"]),
    ])
    table = composite.numeric_table(long)
    assert composite.pick(table, ["ncaa_net", "warrennolan"], "net_rank").tolist() == [1, 2]


WEIGHTS = {
    "trim_min_inputs": 4,
    "predictive": [
        {"sources": ["s1"], "metric": "rating", "kind": "value", "weight": 1},
        {"sources": ["s2"], "metric": "rating", "kind": "value", "weight": 1},
    ],
    "resume": [
        {"sources": ["net"], "metric": "net_rank", "kind": "rank", "weight": 1},
        {"sources": ["s1"], "metric": "wab", "kind": "value", "weight": 1},
    ],
    "stats": {
        "adj_o": {"inputs": [["s1", "adj_o"], ["s2", "adj_o"]], "scale_from": ["s1", "s2"], "best": "high"},
        "adj_d": {"inputs": [["s1", "adj_d"], ["s2", "def", "invert"]], "scale_from": ["s1"], "best": "low"},
    },
}


@pytest.fixture
def built():
    teams = ["a", "b", "c", "d"]
    long = long_rows(
        {
            "s1": {"rating": [30, 20, 10, 0], "wab": [3, 1, 0, -2], "adj_o": [120, 110, 105, 100],
                   "adj_d": [90, 95, 100, 105]},
            "s2": {"rating": [25, 22, 5, 1], "adj_o": [118, 112, 104, 99], "def": [12, 6, 0, -6]},
        },
        teams,
    )
    return composite.build(long, WEIGHTS)


def test_build_orders_teams(built):
    assert built.index.tolist() == ["a", "b", "c", "d"]
    assert built["pred_rank"].tolist() == [1, 2, 3, 4]


def test_missing_input_is_skipped_not_fatal(built):
    # no "net" source today: résumé runs on WAB alone
    assert (built["res_n"] == 1).all()
    assert built["res_rank"].tolist() == [1, 2, 3, 4]


def test_stat_average_scale_and_direction(built):
    # adj_o back on the points-per-100 scale; best offense ranks 1
    assert built.loc["a", "adj_o_rank"] == 1
    assert 95 < built["adj_o"].min() < built["adj_o"].max() < 125
    # adj_d: lower is better; s2's "def" (points prevented) is inverted
    assert built.loc["a", "adj_d_rank"] == 1
    assert built.loc["a", "adj_d"] < built.loc["d", "adj_d"]
    assert built["adj_em"].tolist() == pytest.approx((built["adj_o"] - built["adj_d"]).tolist())


def test_gap_sign(built):
    assert (built["gap"] == built["pred_rank"] - built["res_rank"]).all()


def test_default_weights_file_loads():
    w = composite.load_weights()
    assert math.isclose(sum(i["weight"] for i in w["predictive"]), 1.0)
    for section in ("predictive", "resume"):
        for item in w[section]:
            Input(**item)
