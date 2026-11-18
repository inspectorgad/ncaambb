"""Warren Nolan NET page (HTML table)."""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from .base import Source, html_table, split_record

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


class WarrenNolan(Source):
    name = "warrennolan"
    raw_extension = "html"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        t = html_table(raw, {"Team", "Record", "NET Rank"})
        out = pd.DataFrame(
            {
                "source_name": t["Team"].astype(str).str.strip(),
                "record": t["Record"].astype(str),
                "net_rank": pd.to_numeric(t["NET Rank"], errors="coerce"),
            }
        )
        out["wins"], out["losses"] = split_record(out["record"])
        return out.reset_index(drop=True)

    @staticmethod
    def data_through(raw: bytes, today: dt.date) -> dt.date | None:
        """'NET Rank updated for games through MAR 15th' (no year given)."""
        text = raw.decode("utf-8", errors="replace")
        m = re.search(r"games through\s*(?:<[^>]+>\s*)*([A-Z]{3})\s+(\d{1,2})", text)
        if not m or m.group(1) not in MONTHS:
            return None
        month, day = MONTHS[m.group(1)], int(m.group(2))
        # most recent such date on or before today
        year = today.year if (month, day) <= (today.month, today.day) else today.year - 1
        return dt.date(year, month, day)
