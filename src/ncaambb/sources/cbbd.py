"""CollegeBasketballData.com adjusted efficiency ratings (JSON API, needs a key).

The key is read from the CBBD_API_KEY environment variable (a GitHub
Actions secret in the daily job). ``source_name`` is CBBD's numeric team
id, recorded in data/teams.csv as ``cbbd_id``, so no name aliases needed.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import requests

from ..fetching import NotConfigured, fetch_bytes
from .base import Source

KEY_ENV = "CBBD_API_KEY"


class Cbbd(Source):
    name = "cbbd"
    raw_extension = "json"

    def fetch(self, session: requests.Session | None = None) -> bytes:
        key = os.environ.get(KEY_ENV, "").strip()
        if not key:
            raise NotConfigured(f"{KEY_ENV} is not set")
        return fetch_bytes(self.url, session, headers={"Authorization": f"Bearer {key}"})

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            raise ValueError("cbbd: expected a non-empty list of team ratings")
        rows = []
        for t in data:
            ranks = t.get("rankings") or {}
            rows.append(
                {
                    "source_name": str(t["teamId"]),
                    "conference": t.get("conference"),
                    "rating": t.get("netRating"),
                    "rating_rank": ranks.get("net"),
                    "adj_o": t.get("offensiveRating"),
                    "adj_o_rank": ranks.get("offense"),
                    "adj_d": t.get("defensiveRating"),
                    "adj_d_rank": ranks.get("defense"),
                }
            )
        out = pd.DataFrame(rows)
        num = ["rating", "rating_rank", "adj_o", "adj_o_rank", "adj_d", "adj_d_rank"]
        out[num] = out[num].apply(pd.to_numeric, errors="coerce")
        return out.sort_values("rating_rank").reset_index(drop=True)
