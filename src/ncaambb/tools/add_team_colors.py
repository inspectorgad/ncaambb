"""Add school colors (from a CollegeBasketballData /teams download) to data/teams.csv.

    python -m ncaambb.tools.add_team_colors path/to/cbbd_teams.json

Fills `color` and `alt_color` (6-digit hex, no '#') by matching cbbd_id.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from .. import DATA_DIR

HEX = re.compile(r"^[0-9a-fA-F]{6}$")


def main(argv: list[str]) -> None:
    rows = json.loads(Path(argv[0]).read_text())
    colors = {
        str(t["id"]): (
            (t.get("primaryColor") or "").lower() if HEX.match(t.get("primaryColor") or "") else "",
            (t.get("secondaryColor") or "").lower() if HEX.match(t.get("secondaryColor") or "") else "",
        )
        for t in rows
    }
    path = DATA_DIR / "teams.csv"
    teams = pd.read_csv(path, dtype=str, keep_default_na=False)
    teams["color"] = teams["cbbd_id"].map(lambda i: colors.get(i, ("", ""))[0])
    teams["alt_color"] = teams["cbbd_id"].map(lambda i: colors.get(i, ("", ""))[1])
    teams.to_csv(path, index=False)
    missing = teams.loc[teams["color"] == "", "team_id"].tolist()
    print(f"colors for {len(teams) - len(missing)} of {len(teams)} teams; missing: {missing}")


if __name__ == "__main__":
    main(sys.argv[1:])
