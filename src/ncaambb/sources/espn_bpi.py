"""ESPN Basketball Power Index (BPI) JSON API.

``source_name`` is ESPN's numeric team id, which data/teams.csv records
directly, so this source needs no name aliases.
"""

from __future__ import annotations

import json

import pandas as pd

from .base import Source

# category -> {ESPN field name: our metric name}
FIELDS = {
    "bpi": {
        "bpi": "rating",
        "bpirank": "rating_rank",
        "bpioffense": "bpi_off",
        "bpidefense": "bpi_def",
        "wins": "wins",
        "losses": "losses",
        "projtotalwins": "proj_wins",
        "projtotallosses": "proj_losses",
        "sosremrank": "sos_remaining_rank",
    },
    "resume": {
        "sorrank": "sor_rank",
        "sospastrank": "sos_past_rank",
        "projectedtournamentseed": "proj_seed",
    },
    "tournament": {
        "chancencaachampion": "champ_pct",
        "chancefinal4": "final4_pct",
    },
}


class EspnBpi(Source):
    name = "espn_bpi"
    raw_extension = "json"

    @staticmethod
    def parse(raw: bytes) -> pd.DataFrame:
        data = json.loads(raw)
        # Field order is given once per category at the top level.
        names = {c["name"]: c["names"] for c in data["categories"]}
        missing = [
            f"{cat}.{field}"
            for cat, fields in FIELDS.items()
            for field in fields
            if field not in names.get(cat, [])
        ]
        if missing:
            raise ValueError(f"ESPN BPI missing fields: {missing}")

        rows = []
        for entry in data["teams"]:
            team = entry["team"]
            row = {
                "source_name": str(team["id"]),
                "espn_name": team["nickname"],
                "espn_display_name": team["displayName"],
                "espn_mascot": team["name"],
                "espn_abbreviation": team["abbreviation"],
                "conference": team["group"]["shortName"],
            }
            values = {c["name"]: c["values"] for c in entry["categories"]}
            for cat, fields in FIELDS.items():
                vals = values.get(cat, [])
                for field, metric in fields.items():
                    idx = names[cat].index(field)
                    row[metric] = vals[idx] if idx < len(vals) else None
            rows.append(row)

        out = pd.DataFrame(rows)
        num = [m for f in FIELDS.values() for m in f.values()]
        out[num] = out[num].apply(pd.to_numeric, errors="coerce")
        out["record"] = (
            out["wins"].astype("Int64").astype(str) + "-" + out["losses"].astype("Int64").astype(str)
        )
        return out.sort_values("rating_rank").reset_index(drop=True)
