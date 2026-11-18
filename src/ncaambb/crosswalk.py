"""Maps each source's team names to one canonical ``team_id``.

* data/teams.csv   - canonical list (team_id, name, short_name, conference, espn_id)
* data/aliases.csv - source, source_name -> team_id

Lookups are exact. Unknown names are reported, never guessed; add them to
aliases.csv (``python -m ncaambb.tools.seed_aliases`` suggests matches).
ESPN rows are matched on ESPN's numeric team id via teams.csv.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import DATA_DIR

ID_SOURCES = {"espn_bpi": "espn_id"}  # sources matched by an id column in teams.csv


@dataclass
class Resolution:
    team_ids: pd.Series  # aligned with the input names; NaN where unmatched
    unmatched: list[str]


class Crosswalk:
    def __init__(self, teams: pd.DataFrame, aliases: pd.DataFrame):
        self.teams = teams
        self.aliases = aliases
        self._maps: dict[str, dict[str, str]] = {}
        for source, col in ID_SOURCES.items():
            self._maps[source] = dict(zip(teams[col].astype(str), teams["team_id"]))
        for source, group in aliases.groupby("source"):
            self._maps.setdefault(source, {}).update(zip(group["source_name"], group["team_id"]))

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "Crosswalk":
        teams = pd.read_csv(data_dir / "teams.csv", dtype=str, keep_default_na=False)
        aliases_path = data_dir / "aliases.csv"
        if aliases_path.exists():
            aliases = pd.read_csv(aliases_path, dtype=str, keep_default_na=False)
        else:
            aliases = pd.DataFrame(columns=["source", "source_name", "team_id"])
        unknown = set(aliases["team_id"]) - set(teams["team_id"])
        if unknown:
            raise ValueError(f"aliases.csv references unknown team_ids: {sorted(unknown)[:10]}")
        return cls(teams, aliases)

    def resolve(self, source: str, names: pd.Series) -> Resolution:
        mapping = self._maps.get(source, {})
        ids = names.astype(str).map(mapping)
        unmatched = names[ids.isna()].astype(str).tolist()
        return Resolution(ids, unmatched)

    def apply(self, source: str, wide: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Add ``team_id`` to a parsed frame; drop and report unmatched rows."""
        res = self.resolve(source, wide["source_name"])
        out = wide.assign(team_id=res.team_ids.values)
        out = out[out["team_id"].notna()]
        dupes = out["team_id"][out["team_id"].duplicated()].tolist()
        if dupes:
            raise ValueError(f"{source}: several names map to the same team: {dupes[:5]}")
        return out.reset_index(drop=True), res.unmatched
