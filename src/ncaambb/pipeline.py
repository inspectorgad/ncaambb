"""Daily pipeline: fetch -> parse -> validate -> map names -> composite -> site JSON.

    python -m ncaambb.pipeline                    # live download
    python -m ncaambb.pipeline --fixtures DIR     # offline, from saved files

Per source, the outcome is one of:
  ok           downloaded and parsed today
  stale        failed today; using its last good data (<= stale_max_days old)
  failed       failed today and no recent good data
  not_current  the source's data predates this season (e.g. NET before December)

Writes data/latest/<source>.csv (last good rows per source) and
site/data/{latest.json, meta.json, history/<date>.json}. Only the history
snapshots are committed; the rest is rebuilt each run (GitHub Actions keeps
data/latest in its cache for the stale-data fallback).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from . import DATA_DIR, PROJECT_ROOT, build_site_data, composite
from .config import load_sources_config
from .crosswalk import Crosswalk
from .fetching import make_session
from .schema import LONG_COLUMNS, to_long, validate_wide
from .sources import REGISTRY
from .sources.base import season_start

log = logging.getLogger("ncaambb")

MAX_UNMATCHED = 3  # more unknown team names than this fails the source


@dataclass
class SourceStatus:
    source: str
    status: str = "failed"
    teams: int = 0
    data_date: str | None = None
    unmatched: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def usable(self) -> bool:
        return self.status in ("ok", "stale")


@dataclass
class Paths:
    cache: Path = DATA_DIR / "latest"
    site_data: Path = PROJECT_ROOT / "site" / "data"
    raw: Path | None = DATA_DIR / "raw"


def find_fixture(fixtures: Path, source: str) -> Path:
    matches = sorted(fixtures.glob(f"{source}_*")) or sorted(fixtures.glob(f"{source}*"))
    if not matches:
        raise FileNotFoundError(f"no fixture for {source} in {fixtures}")
    return matches[0]


def read_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    return gzip.decompress(raw) if path.suffix == ".gz" else raw


def load_cached(cache: Path, source: str, today: dt.date, max_days: int) -> pd.DataFrame | None:
    path = cache / f"{source}.csv"
    if not path.exists():
        return None
    rows = pd.read_csv(path, dtype={"team_id": str, "source": str, "metric": str, "value": object})
    if rows.empty:
        return None
    age = (today - dt.date.fromisoformat(str(rows["as_of"].iloc[0]))).days
    return rows if age <= max_days else None


def collect(
    cfg: dict,
    crosswalk: Crosswalk,
    today: dt.date,
    paths: Paths,
    fixtures: Path | None = None,
) -> tuple[pd.DataFrame, list[SourceStatus]]:
    as_of = today.isoformat()
    session = None if fixtures else make_session()
    max_days = int(cfg.get("stale_max_days", 3))
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
                if paths.raw:
                    paths.raw.mkdir(parents=True, exist_ok=True)
                    (paths.raw / f"{name}_{as_of}.{source.raw_extension}").write_bytes(raw)
            through = source.data_through(raw, today)
            if through:
                status.data_date = through.isoformat()
                if through < season_start(cfg["season"]):
                    status.status = "not_current"
                    log.info("%s: data is from %s, before this season; skipped", name, through)
                    continue
            wide = source.parse(raw)
            validate_wide(wide, name)
            wide, unmatched = crosswalk.apply(name, wide)
            status.unmatched = unmatched
            if len(unmatched) > MAX_UNMATCHED:
                raise ValueError(f"{len(unmatched)} unknown team names: {unmatched[:10]}")
            # ESPN's name fields only seed teams.csv; keep them out of the metrics.
            wide = wide.drop(columns=[c for c in wide.columns if c.startswith("espn_")])
            rows = to_long(wide, name, as_of)
            paths.cache.mkdir(parents=True, exist_ok=True)
            rows.to_csv(paths.cache / f"{name}.csv", index=False)
            frames.append(rows)
            status.status, status.teams = "ok", len(wide)
            status.data_date = status.data_date or as_of
            if unmatched:
                log.warning("%s: unmatched team names %s (add to data/aliases.csv)", name, unmatched)
            log.info("%s: %d teams", name, len(wide))
        except Exception as exc:  # one bad source must not stop the others
            status.error = f"{type(exc).__name__}: {exc}"
            cached = load_cached(paths.cache, name, today, max_days)
            if cached is not None:
                frames.append(cached)
                status.status = "stale"
                status.teams = cached["team_id"].nunique()
                status.data_date = str(cached["as_of"].iloc[0])
                log.warning("%s failed (%s); using data from %s", name, status.error, status.data_date)
            else:
                log.error("%s failed: %s", name, status.error)

    long = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=LONG_COLUMNS)
    return long, statuses


def run(
    fixtures: Path | None = None,
    paths: Paths | None = None,
    today: dt.date | None = None,
) -> tuple[pd.DataFrame, list[SourceStatus]]:
    paths = paths or Paths()
    today = today or dt.date.today()
    cfg = load_sources_config(today=today)
    weights = composite.load_weights()
    crosswalk = Crosswalk.load()

    long, statuses = collect(cfg, crosswalk, today, paths, fixtures)
    if long.empty:
        raise RuntimeError("no usable sources")
    table = composite.build(long, weights)
    meta = {
        "as_of": today.isoformat(),
        "season": cfg["season"],
        "sources": [asdict(s) for s in statuses],
        "weights": weights,
    }
    build_site_data.write(paths.site_data, table, long, crosswalk.teams, meta)
    return table, statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixtures", type=Path, help="read saved files instead of downloading")
    parser.add_argument("--date", type=dt.date.fromisoformat, help="override today's date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        _, statuses = run(fixtures=args.fixtures, today=args.date)
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1
    broken = [s.source for s in statuses if s.status in ("failed", "stale")]
    limit = load_sources_config().get("max_failed_sources", 3)
    if len(broken) >= limit:
        log.error("too many sources failed today: %s", broken)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
