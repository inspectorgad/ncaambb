"""BartTorvik (T-Rank) team results CSV."""

from __future__ import annotations

import io

import pandas as pd

from .base import Source

# CSV column -> our metric name
COLUMNS = {
    "team": "source_name",
    "conf": "conference",
    "record": "record",
    "rank": "rating_rank",  # T-Rank overall (by Barthag)
    "adjoe": "adj_o",
    "oe Rank": "adj_o_rank",
    "adjde": "adj_d",
    "de Rank": "adj_d_rank",
    "barthag": "barthag",
    "adjt": "tempo",
    "sos": "sos",
    "ncsos": "sos_noncon",
    "consos": "sos_conf",
    "WAB": "wab",
    "WAB Rk": "wab_rank",
    "proj. W": "proj_wins",
    "Proj. L": "proj_losses",
}


class Torvik(Source):
    name = "torvik"
    raw_extension = "csv"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        df = pd.read_csv(io.BytesIO(raw))
        missing = set(COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"torvik CSV missing columns: {sorted(missing)}")
        out = df[list(COLUMNS)].rename(columns=COLUMNS)
        out["source_name"] = out["source_name"].str.strip()
        out["adj_em"] = out["adj_o"] - out["adj_d"]
        # Rating used in the composite: adjusted efficiency margin.
        out["rating"] = out["adj_em"]
        record = out["record"].str.extract(r"^(\d+)-(\d+)$").astype(float)
        out["wins"], out["losses"] = record[0], record[1]
        return out.reset_index(drop=True)
