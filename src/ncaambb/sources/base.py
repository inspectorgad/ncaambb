"""Common interface for every rating source."""

from __future__ import annotations

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
