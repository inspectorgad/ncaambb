"""Suggest aliases.csv rows for a source by fuzzy-matching its team names.

    python -m ncaambb.tools.seed_aliases torvik path/to/raw [--write]

Prints every source name that is not yet in aliases.csv with its best
match and score, lowest scores first, for review. With --write, appends
the suggestions to aliases.csv (only do this after reviewing them).
"""

from __future__ import annotations

import gzip
import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from .. import DATA_DIR
from ..crosswalk import Crosswalk
from ..sources import REGISTRY

ABBREVIATIONS = [
    (r"\bark\.", "arkansas"), (r"\bfla\.", "florida"), (r"\bcaro\.", "carolina"),
    (r"\bmich\.", "michigan"), (r"\bill\.", "illinois"), (r"\bky\.", "kentucky"),
    (r"\bwash\.", "washington"), (r"\bcolo\.", "colorado"), (r"\bariz\.", "arizona"),
    (r"\bala\.", "alabama"), (r"\bga\.", "georgia"), (r"\bmo\.", "missouri"),
    (r"\bconn\.", "connecticut"), (r"\btenn\.?", "tennessee"), (r"\bla\.", "louisiana"),
    (r"\bind\.", "indiana"), (r"\bmiss\.", "mississippi"), (r"\bval\.", "valley"),
    (r"\bcent\.", "central"), (r"\bintl\b", "international"), (r"\bcol\. of\b", ""),
    (r"\bst\.?$", "state"),
    (r"\bst\.?\s", "state "),  # mid-name 'St' is usually State...
    (r"\bn\.?\s", "north "),
    (r"\bs\.?\s", "south "),
    (r"\be\.?\s", "east "),
    (r"\bw\.?\s", "west "),
    (r"\bso\.?$", "southern"),
]


def normalize(name: str) -> str:
    n = name.lower().replace("&", " and ").replace("'", "").replace("(", " ").replace(")", " ")
    for pattern, repl in ABBREVIATIONS:
        n = re.sub(pattern, repl, n)
    return re.sub(r"\s+", " ", n).strip()


def build_choices(teams: pd.DataFrame) -> dict[str, str]:
    choices: dict[str, str] = {}
    for _, t in teams.iterrows():
        for col in ("name", "short_name"):
            choices[normalize(t[col])] = t["team_id"]
        choices[normalize(t["team_id"].replace("-", " "))] = t["team_id"]
    return choices


def suggest(source_names: list[str], teams: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    choices = build_choices(teams)
    # spellings already confirmed for other sources are good evidence too
    for name, team_id in zip(aliases["source_name"], aliases["team_id"]):
        choices.setdefault(normalize(name), team_id)
    rows = []
    for name in source_names:
        match, score, _ = process.extractOne(normalize(name), list(choices), scorer=fuzz.WRatio)
        rows.append({"source_name": name, "team_id": choices[match], "score": round(score, 1)})
    return pd.DataFrame(rows).sort_values("score")


def main(argv: list[str]) -> None:
    source, path, *flags = argv
    raw = Path(path).read_bytes()
    raw = gzip.decompress(raw) if path.endswith(".gz") else raw
    wide = REGISTRY[source].parse(raw)
    cw = Crosswalk.load()
    unmatched = cw.resolve(source, wide["source_name"]).unmatched
    sugg = suggest(unmatched, cw.teams, cw.aliases)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(sugg.to_string(index=False))
    if "--write" in flags and len(sugg):
        out = DATA_DIR / "aliases.csv"
        sugg.insert(0, "source", source)
        new = sugg[["source", "source_name", "team_id"]]
        if out.exists():
            new = pd.concat([pd.read_csv(out, dtype=str, keep_default_na=False), new])
        new.sort_values(["source", "source_name"]).to_csv(out, index=False)
        print(f"appended {len(sugg)} rows to {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
