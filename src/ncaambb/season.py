"""Says whether the daily job should run today.

    python -m ncaambb.season [--date YYYY-MM-DD] [--github-output]

Prints active=true/false; with --github-output also appends it to the
file named by $GITHUB_OUTPUT so later workflow steps can use it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from .config import in_active_window, load_sources_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", type=dt.date.fromisoformat, default=None)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args(argv)
    today = args.date or dt.date.today()
    cfg = load_sources_config(today=today)
    line = f"active={'true' if in_active_window(cfg, today) else 'false'}"
    print(f"{line} (season {cfg['season']}, {today})")
    if args.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
