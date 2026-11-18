"""Haslametrics ratings, read from the XML file that powers haslametrics.com.

Their published rank ("rk") orders teams by All-Play % ("ap"). All-Play %
is capped at 1.0 and has many ties at the top, so the composite uses the
efficiency margin (oe - de), which tracks their rank at Spearman ~0.99.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd

from .base import Source

NUMERIC = {
    "rk": "rating_rank",
    "oe": "adj_o",
    "de": "adj_d",
    "ap": "all_play",
    "sos": "sos",
    "w": "wins",
    "l": "losses",
    "mom": "momentum",
    "rpi": "rpi",
    "ou": "pace_o",
    "du": "pace_d",
}
TEXT = {
    "t": "source_name",
    "c": "conference",
    "r_q1": "q1",
    "r_q2": "q2",
    "r_q3": "q3",
    "r_q4": "q4",
}


class Haslametrics(Source):
    name = "haslametrics"
    raw_extension = "xml"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        root = ET.fromstring(raw)
        rows = [el.attrib for el in root.iter("mr")]
        if not rows:
            raise ValueError("haslametrics XML has no <mr> team elements")
        df = pd.DataFrame(rows)
        missing = (set(NUMERIC) | set(TEXT)) - set(df.columns)
        if missing:
            raise ValueError(f"haslametrics XML missing attributes: {sorted(missing)}")
        out = df[list(TEXT)].rename(columns=TEXT)
        for attr, metric in NUMERIC.items():
            out[metric] = pd.to_numeric(df[attr], errors="coerce")
        out["source_name"] = out["source_name"].str.strip()
        out["rating_rank"] = out["rating_rank"].astype("Int64")
        out["adj_em"] = out["adj_o"] - out["adj_d"]
        out["rating"] = out["adj_em"]
        out["tempo"] = (out["pace_o"] + out["pace_d"]) / 2
        out["record"] = (
            out["wins"].astype("Int64").astype(str) + "-" + out["losses"].astype("Int64").astype(str)
        )
        return out.sort_values("rating_rank").reset_index(drop=True)
