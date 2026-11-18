"""TeamRankings predictive ratings (HTML table)."""

from __future__ import annotations

import pandas as pd

from .base import Source, html_table, split_record

COLUMNS = {"Rank", "Team", "Rating", "v 1-25", "v 26-50", "v 51-100", "Hi", "Lo"}


class TeamRankings(Source):
    name = "teamrankings"
    raw_extension = "html"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        t = html_table(raw, COLUMNS)
        parts = t["Team"].astype(str).str.extract(r"^(.*?)\s*\((\d+-\d+)\)$")
        if parts[0].isna().any():
            raise ValueError("teamrankings: could not split 'Team (W-L)'")
        out = pd.DataFrame(
            {
                "source_name": parts[0].str.strip(),
                "record": parts[1],
                "rating": pd.to_numeric(t["Rating"], errors="coerce"),
                "rating_rank": pd.to_numeric(t["Rank"], errors="coerce"),
                "vs_top25": t["v 1-25"],
                "vs_26_50": t["v 26-50"],
                "vs_51_100": t["v 51-100"],
                "season_high_rank": pd.to_numeric(t["Hi"], errors="coerce"),
                "season_low_rank": pd.to_numeric(t["Lo"], errors="coerce"),
            }
        )
        out["wins"], out["losses"] = split_record(out["record"])
        return out.reset_index(drop=True)
