"""Daily pipeline: fetch -> parse -> validate -> map team names -> long table.

    python -m ncaambb.pipeline                    # live download
    python -m ncaambb.pipeline --fixtures DIR     # offline, from saved files

Writes data/processed/metrics_long.csv and data/processed/status.json.
(Phase 2 adds the composite and the site JSON.)
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from . import DATA_DIR
from .config import load_sources_config
from .crosswalk import Crosswalk
from .fetching import make_session
from .schema import to_long, validate_wide
from .sources import REGISTRY

log = logging.getLogger("ncaambb")

MAX_UNMATCHED = 3  # more unknown team names than this fails the source


@dataclass
class SourceStatus:
    source: str
    ok: bool = False
    teams: int = 0
    unmatched: list[str] = field(default_factory=list)
    error: str | None = None


def find_fixture(fixtures: Path, source: str) -> Path:
    matches = sorted(fixtures.glob(f"{source}*"))
    if not matches:
        raise FileNotFoundError(f"no fixture for {source} in {fixtures}")
    return matches[0]


def read_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def run(
    fixtures: Path | None = None,
    out_dir: Path = DATA_DIR / "processed",
    raw_dir: Path | None = DATA_DIR / "raw",
    as_of: str | None = None,
) -> tuple[pd.DataFrame, list[SourceStatus]]:
    cfg = load_sources_config()
    crosswalk = Crosswalk.load()
    as_of = as_of or dt.date.today().isoformat()
    session = None if fixtures else make_session()

    frames, statuses = [], []
    for name, scfg in cfg["sources"].items():
        if not scfg.get("enabled", True):
            continue
        status = SourceStatus(source=name)
        statuses.append(status)
        source = REGISTRY[name](scfg["url"], cfg["season"])
        try:
            if fixtures:
                raw = read_bytes(find_fixture(fixtures, name))
            else:
                raw = source.fetch(session)
                if raw_dir:
                    raw_dir.mkdir(parents=True, exist_ok=True)
                    (raw_dir / f"{name}_{as_of}.{source.raw_extension}").write_bytes(raw)
            wide = source.parse(raw)
            validate_wide(wide, name)
            wide, unmatched = crosswalk.apply(name, wide)
            status.unmatched = unmatched
            if len(unmatched) > MAX_UNMATCHED:
                raise ValueError(f"{len(unmatched)} unknown team names: {unmatched[:10]}")
            # ESPN's name fields only seed teams.csv; keep them out of the metrics.
            wide = wide.drop(columns=[c for c in wide.columns if c.startswith("espn_")])
            frames.append(to_long(wide, name, as_of))
            status.ok, status.teams = True, len(wide)
            log.info("%s: %d teams (%d unmatched)", name, len(wide), len(unmatched))
        except Exception as exc:  # one bad source must not stop the others
            status.error = f"{type(exc).__name__}: {exc}"
            log.error("%s failed: %s", name, status.error)

    long = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out_dir.mkdir(parents=True, exist_ok=True)
    long.to_csv(out_dir / "metrics_long.csv", index=False)
    (out_dir / "status.json").write_text(
        json.dumps({"as_of": as_of, "sources": [asdict(s) for s in statuses]}, indent=2)
    )
    return long, statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, help="read saved files instead of downloading")
    parser.add_argument("--out", type=Path, default=DATA_DIR / "processed")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    _, statuses = run(fixtures=args.fixtures, out_dir=args.out)
    failed = [s.source for s in statuses if not s.ok]
    limit = load_sources_config().get("max_failed_sources", 3)
    if len(failed) >= min(limit, len(statuses)):
        log.error("too many failed sources: %s", failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
