"""Combines the sources into Predictive and Résumé scores (see PLAN.md §5).

1. Standardize each input across D1: z = (x - mean) / std.
   Rank-only inputs: percentile p = 1 - (rank - 0.5) / N, then z = Φ⁻¹(p).
2. Per team, take the weighted mean of the z-scores it has (weights
   rescaled over available inputs). With >= trim_min_inputs inputs, drop
   the single highest and lowest z first.
3. Rank by the combined z.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd
import yaml

from . import CONFIG_DIR

_NORMAL = NormalDist()


@dataclass
class Input:
    sources: list[str]
    metric: str
    kind: str = "value"  # "value" or "rank"
    weight: float = 1.0

    @property
    def label(self) -> str:
        return f"{'/'.join(self.sources)}:{self.metric}"


def load_weights(path: Path | None = None) -> dict[str, Any]:
    with open(path or CONFIG_DIR / "weights.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def numeric_table(long: pd.DataFrame) -> pd.DataFrame:
    """Long rows -> one row per team, columns (source, metric), numbers only."""
    num = long.assign(value=pd.to_numeric(long["value"], errors="coerce")).dropna(subset=["value"])
    return num.pivot_table(index="team_id", columns=["source", "metric"], values="value", aggfunc="first")


def pick(table: pd.DataFrame, sources: list[str], metric: str) -> pd.Series:
    """Per team, the value from the first listed source that has one."""
    out = pd.Series(np.nan, index=table.index, dtype=float)
    for source in sources:
        if (source, metric) in table.columns:
            out = out.fillna(table[(source, metric)])
    return out


def zscore(x: pd.Series) -> pd.Series:
    std = x.std(ddof=0)
    if x.notna().sum() < 2 or not std:
        return x * np.nan
    return (x - x.mean()) / std


def rank_to_z(rank: pd.Series) -> pd.Series:
    """Rank 1 = best -> large positive z."""
    n = rank.notna().sum()
    if n < 2:
        return rank * np.nan
    pct = 1 - (rank - 0.5) / n
    return pct.clip(1e-6, 1 - 1e-6).map(lambda p: _NORMAL.inv_cdf(p) if pd.notna(p) else np.nan)


def input_z(table: pd.DataFrame, inp: Input) -> pd.Series:
    x = pick(table, inp.sources, inp.metric)
    if inp.kind == "rank":
        # re-rank among teams present so N matches (handles gaps and ties)
        return rank_to_z(x.rank(method="average"))
    return zscore(x)


def combine(z: pd.DataFrame, weights: pd.Series, trim_min: int) -> tuple[pd.Series, pd.Series]:
    """Weighted mean of each row's available z-scores, trimmed when enough.

    Returns (combined z, number of inputs used before trimming).
    """
    values = z.to_numpy(dtype=float)
    w = weights.reindex(z.columns).to_numpy(dtype=float)
    out = np.full(len(z), np.nan)
    counts = np.zeros(len(z), dtype=int)
    for i, row in enumerate(values):
        have = ~np.isnan(row)
        counts[i] = have.sum()
        if not have.any():
            continue
        idx = np.flatnonzero(have)
        if len(idx) >= trim_min:
            order = idx[np.argsort(row[idx])]
            idx = order[1:-1]
        out[i] = np.sum(row[idx] * w[idx]) / np.sum(w[idx])
    return pd.Series(out, index=z.index), pd.Series(counts, index=z.index)


def score(table: pd.DataFrame, inputs: list[Input], trim_min: int) -> dict[str, pd.Series | pd.DataFrame]:
    z = pd.DataFrame({inp.label: input_z(table, inp) for inp in inputs}, index=table.index)
    z = z.dropna(axis=1, how="all")  # inputs with no data today (e.g. NET pre-December)
    weights = pd.Series({inp.label: inp.weight for inp in inputs})
    combined, n = combine(z, weights, trim_min)
    return {
        "z": combined,
        "rank": combined.rank(ascending=False, method="min"),
        "n_inputs": n,
        "inputs": z,
    }


def stat_average(table: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """Cross-source average of one stat -> columns value, rank, z."""
    zs = []
    for entry in spec["inputs"]:
        source, metric, *flags = entry
        if (source, metric) not in table.columns:
            continue
        x = table[(source, metric)]
        if "rank" in flags:
            z = rank_to_z(x.rank(method="average"))
        else:
            z = zscore(x)
        if "invert" in flags:
            z = -z
        zs.append(z)
    if not zs:
        return pd.DataFrame(index=table.index, columns=["value", "rank", "z"], dtype=float)
    z = pd.concat(zs, axis=1).mean(axis=1, skipna=True)
    value = pd.Series(np.nan, index=table.index)
    if spec.get("scale_from"):
        cols = [
            table[(src, metric)]
            for src, metric, *_ in spec["inputs"]
            if src in spec["scale_from"] and (src, metric) in table.columns
        ]
        if cols:
            means = np.mean([c.mean() for c in cols])
            stds = np.mean([c.std(ddof=0) for c in cols])
            value = means + z * stds
    ascending = spec.get("best", "high") == "low"
    # the stat's z points toward *higher native values*; rank by "best"
    rank = z.rank(ascending=ascending, method="min")
    return pd.DataFrame({"value": value, "rank": rank, "z": z})


def build(long: pd.DataFrame, weights: dict[str, Any] | None = None) -> pd.DataFrame:
    """Long metrics -> one row per team with composite and averaged stats."""
    weights = weights or load_weights()
    table = numeric_table(long)
    trim = int(weights.get("trim_min_inputs", 4))
    pred_inputs = [Input(**i) for i in weights["predictive"]]
    res_inputs = [Input(**i) for i in weights["resume"]]
    pred = score(table, pred_inputs, trim)
    res = score(table, res_inputs, trim)

    out = pd.DataFrame(index=table.index)
    out["pred_z"], out["pred_rank"], out["pred_n"] = pred["z"], pred["rank"], pred["n_inputs"]
    out["res_z"], out["res_rank"], out["res_n"] = res["z"], res["rank"], res["n_inputs"]
    # gap > 0: résumé ranks ahead of quality (results flattering the team);
    # gap < 0: quality ahead of résumé (under-rewarded so far)
    out["gap"] = out["pred_rank"] - out["res_rank"]
    out["spread"] = pred["inputs"].std(axis=1, ddof=0)
    # plain average of each predictive source's D1 rank (sanity check column)
    input_ranks = pred["inputs"].rank(ascending=False, method="min")
    out["avg_source_rank"] = input_ranks.mean(axis=1)

    for name, spec in weights.get("stats", {}).items():
        stat = stat_average(table, spec)
        out[f"{name}"], out[f"{name}_rank"], out[f"{name}_z"] = stat["value"], stat["rank"], stat["z"]
    if {"adj_o", "adj_d"} <= set(out.columns):
        out["adj_em"] = out["adj_o"] - out["adj_d"]
        out["adj_em_rank"] = out["adj_em"].rank(ascending=False, method="min")

    # per-input z-scores for the "source agreement" view
    for col in pred["inputs"].columns:
        out[f"zp:{col}"] = pred["inputs"][col]
    for col in res["inputs"].columns:
        out[f"zr:{col}"] = res["inputs"][col]
    return out.sort_values(["pred_rank", "res_rank"])
