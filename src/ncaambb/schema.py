"""Shared data format and validation.

Each source parser returns a *wide* DataFrame: one row per team, a
``source_name`` column holding the team's name as that source spells it,
and one column per metric. Optional ``<metric>_rank`` columns carry the
source's own rank for that metric. A ``*_rank`` column whose base metric
is absent (e.g. ``sor_rank``) is treated as a metric itself.

After name resolution, :func:`to_long` turns it into the long format
used downstream::

    team_id | source | metric | value | rank | as_of
"""

from __future__ import annotations

import pandas as pd

LONG_COLUMNS = ["team_id", "source", "metric", "value", "rank", "as_of"]

# Plausible ranges for numeric metrics; values outside mean a parser broke.
RANGES: dict[str, tuple[float, float]] = {
    "adj_o": (70, 145),
    "adj_d": (70, 145),
    "adj_em": (-60, 60),
    "tempo": (55, 85),
    "rating": (-60, 60),
    "wins": (0, 45),
    "losses": (0, 45),
}

MIN_TEAMS = 360


class ValidationError(ValueError):
    """Raised when parsed source data fails sanity checks."""


def validate_wide(df: pd.DataFrame, source: str, min_teams: int = MIN_TEAMS) -> None:
    problems: list[str] = []
    if "source_name" not in df.columns:
        problems.append("missing source_name column")
    else:
        if len(df) < min_teams:
            problems.append(f"only {len(df)} teams (need >= {min_teams})")
        dupes = df["source_name"][df["source_name"].duplicated()].tolist()
        if dupes:
            problems.append(f"duplicate team names: {dupes[:5]}")
    for metric, (lo, hi) in RANGES.items():
        if metric not in df.columns:
            continue
        col = pd.to_numeric(df[metric], errors="coerce")
        bad = df.loc[col.notna() & ((col < lo) | (col > hi)), "source_name"].tolist()
        if bad:
            problems.append(f"{metric} outside [{lo}, {hi}] for {bad[:5]}")
        if col.isna().mean() > 0.05:
            problems.append(f"{metric} missing for {col.isna().sum()} teams")
    if problems:
        raise ValidationError(f"{source}: " + "; ".join(problems))


def to_long(wide: pd.DataFrame, source: str, as_of: str) -> pd.DataFrame:
    """Wide frame with a ``team_id`` column -> long rows."""
    # "<metric>_rank" is a rank *of* <metric> only when <metric> exists;
    # otherwise (sor_rank, net_rank, ...) it is a metric in its own right.
    rank_cols = {c for c in wide.columns if c.endswith("_rank") and c[: -len("_rank")] in wide.columns}
    metric_cols = [
        c for c in wide.columns if c not in rank_cols and c not in ("team_id", "source_name")
    ]
    records = []
    for _, row in wide.iterrows():
        for metric in metric_cols:
            value = row[metric]
            if pd.isna(value):
                continue
            rank = row.get(f"{metric}_rank")
            records.append(
                {
                    "team_id": row["team_id"],
                    "source": source,
                    "metric": metric,
                    "value": value,
                    "rank": None if rank is None or pd.isna(rank) else int(rank),
                    "as_of": as_of,
                }
            )
    return pd.DataFrame.from_records(records, columns=LONG_COLUMNS)
