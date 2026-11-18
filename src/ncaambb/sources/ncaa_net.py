"""Official NCAA NET rankings from ncaa.com (HTML table)."""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from .base import Source, html_table, split_record

COLUMNS = {"Rank", "School", "Record", "Conf", "Quad 1", "Quad 2", "Quad 3", "Quad 4"}


class NcaaNet(Source):
    name = "ncaa_net"
    raw_extension = "html"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        t = html_table(raw, COLUMNS)
        out = pd.DataFrame(
            {
                "source_name": t["School"].astype(str).str.strip(),
                "conference": t["Conf"].astype(str),
                "record": t["Record"].astype(str),
                "net_rank": pd.to_numeric(t["Rank"], errors="coerce"),
                "net_prev_rank": pd.to_numeric(t.get("Prev"), errors="coerce"),
                "road": t.get("Road"),
                "neutral": t.get("Neutral"),
                "home": t.get("Home"),
                "q1": t["Quad 1"],
                "q2": t["Quad 2"],
                "q3": t["Quad 3"],
                "q4": t["Quad 4"],
            }
        )
        out["wins"], out["losses"] = split_record(out["record"])
        return out.reset_index(drop=True)

    @staticmethod
    def data_through(raw: bytes, today: dt.date) -> dt.date | None:
        """'Through Games Apr. 06 2026'."""
        text = raw.decode("utf-8", errors="replace")
        m = re.search(r"Through Games\s+([A-Za-z]{3})\.?\s+(\d{1,2}),?\s+(\d{4})", text)
        if not m:
            return None
        return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date()
