"""Build data/teams.csv from an ESPN BPI download.

    python -m ncaambb.tools.seed_teams [path/to/espn_bpi.json[.gz]]

Without a path it downloads the live ESPN feed.
"""

from __future__ import annotations

import gzip
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

from .. import DATA_DIR
from ..config import load_sources_config
from ..sources import EspnBpi


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", "").replace("'", "").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def location_name(display_name: str, mascot: str) -> str:
    """'Miami (OH) RedHawks' minus 'RedHawks' -> 'Miami (OH)'."""
    if display_name.endswith(" " + mascot):
        return display_name[: -len(mascot) - 1].strip()
    return display_name


def read_raw(path: str | None) -> bytes:
    if path is None:
        cfg = load_sources_config()["sources"]["espn_bpi"]
        return EspnBpi(cfg["url"], season=0).fetch()
    raw = Path(path).read_bytes()
    return gzip.decompress(raw) if path.endswith(".gz") else raw


def build(raw: bytes) -> pd.DataFrame:
    df = EspnBpi.parse(raw)
    teams = pd.DataFrame(
        {
            "name": [
                location_name(d, m) for d, m in zip(df["espn_display_name"], df["espn_mascot"])
            ],
            "short_name": df["espn_name"],
            "mascot": df["espn_mascot"],
            "conference": df["conference"],
            "espn_id": df["source_name"],
        }
    )
    teams.insert(0, "team_id", teams["name"].map(slugify))
    dupes = teams["team_id"][teams["team_id"].duplicated()].tolist()
    if dupes:
        raise SystemExit(f"duplicate team_ids, fix by hand: {dupes}")
    return teams.sort_values("team_id").reset_index(drop=True)


def main(argv: list[str]) -> None:
    teams = build(read_raw(argv[0] if argv else None))
    out = DATA_DIR / "teams.csv"
    teams.to_csv(out, index=False)
    print(f"wrote {len(teams)} teams to {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
