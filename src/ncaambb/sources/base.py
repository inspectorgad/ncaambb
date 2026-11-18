"""Common interface for every rating source."""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod

import pandas as pd
import requests

from ..fetching import fetch_bytes


class Source(ABC):
    #: short id used in config, aliases.csv and output (e.g. "torvik")
    name: str = ""
    #: file extension used when saving the raw download
    raw_extension: str = "txt"

    def __init__(self, url_template: str, season: int):
        self.url_template = url_template
        self.season = season

    @property
    def url(self) -> str:
        return self.url_template.format(season=self.season)

    def fetch(self, session: requests.Session | None = None) -> bytes:
        return fetch_bytes(self.url, session)

    @staticmethod
    @abstractmethod
    def parse(raw: bytes) -> pd.DataFrame:
        """Raw download -> wide DataFrame (see ncaambb.schema)."""

    @staticmethod
    def data_through(raw: bytes, today: dt.date) -> dt.date | None:
        """Date of the last games included, if the source states it.

        The pipeline skips a source whose data predates the current season
        (e.g. a NET page still showing last season's final rankings).
        """
        return None


def season_start(season: int) -> dt.date:
    """Season 2027 (2026-27) starts 1 Nov 2026."""
    return dt.date(season - 1, 11, 1)


def html_table(raw: bytes, required: set[str]):
    """The largest table on an HTML page that has all the required columns."""
    import io

    tables = pd.read_html(io.StringIO(raw.decode("utf-8", errors="replace")))
    candidates = [t for t in tables if required <= set(map(str, t.columns))]
    if not candidates:
        raise ValueError(f"no table with columns {sorted(required)}")
    return max(candidates, key=len)


def split_record(record: pd.Series) -> tuple[pd.Series, pd.Series]:
    parts = record.astype(str).str.extract(r"^(\d+)-(\d+)$").astype(float)
    return parts[0], parts[1]
