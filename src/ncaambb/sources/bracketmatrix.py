"""The Bracket Project's Bracket Matrix: consensus NCAA tournament seeds.

Only teams that appear in at least one projected bracket are listed
(roughly 70-170), so this source has a low minimum team count. Display
only: it is not part of either composite.
"""

from __future__ import annotations

import io

import pandas as pd

from .base import Source


class BracketMatrix(Source):
    name = "bracketmatrix"
    raw_extension = "html"
    min_teams = 40

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        text = raw.decode("utf-8", errors="replace")
        tables = pd.read_html(io.StringIO(text))
        if not tables:
            raise ValueError("bracketmatrix: no table found")
        t = max(tables, key=len)
        avg = pd.to_numeric(t.iloc[:, 3], errors="coerce")
        brackets = pd.to_numeric(t.iloc[:, 4], errors="coerce")
        rows = t[avg.notna() & brackets.notna() & t.iloc[:, 1].notna()]
        if rows.empty:
            raise ValueError("bracketmatrix: no team rows (layout changed?)")
        out = pd.DataFrame(
            {
                "source_name": rows.iloc[:, 1].astype(str).str.replace(r"\s+", " ", regex=True).str.strip(),
                "conference": rows.iloc[:, 2].astype(str),
                "consensus_seed": pd.to_numeric(rows.iloc[:, 0], errors="coerce"),
                "avg_seed": avg[rows.index],
                "brackets": brackets[rows.index],
            }
        )
        return out.reset_index(drop=True)
