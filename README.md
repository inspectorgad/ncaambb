# ncaambb

Composite rankings for all 365 NCAA D1 men's basketball teams, built from free public rating systems. See [PLAN.md](PLAN.md) for the full design.

**Status:** Phases 1–4 done. A GitHub Actions job runs every morning in season, rebuilds the rankings and publishes the dashboard to GitHub Pages.

| Source | Feeds | Notes |
|---|---|---|
| BartTorvik | Predictive, Résumé (WAB), stats | CSV |
| Haslametrics | Predictive, stats, quad records | XML |
| ESPN BPI | Predictive, Résumé (SOR), stats | JSON |
| TeamRankings | Predictive | HTML |
| NCAA.com NET | Résumé | Skipped until the first NET of the season (usually early December) |
| Warren Nolan NET | Résumé (backup for NCAA.com) | Skipped while it still shows last season |

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
```

## Run

```bash
python -m ncaambb.pipeline                          # download today's data
python -m ncaambb.pipeline --fixtures tests/fixtures  # offline, from saved files
```

Output (only the history snapshots are committed; the rest is rebuilt each run):
- `site/data/latest.json`: every team's composite ranks, averaged stats and each source's numbers.
- `site/data/history/YYYY-MM-DD.json`: a daily snapshot of ranks, for trend charts.
- `site/data/meta.json`: when it ran, each source's status (`ok`, `stale`, `failed` or `not_current`) and the weights used.
- `data/latest/<source>.csv`: the last good data from each source. If a source fails, this is reused for up to 3 days.

Composite weights live in `config/weights.yaml`, and the source URLs in `config/sources.yaml`.

## Automation (GitHub Actions)

- **`.github/workflows/update.yml`:** runs daily at 11:17 UTC (about 6:17 AM ET), between Nov 1 and Apr 15. It runs the pipeline, commits the day's history snapshot and deploys `site/` to GitHub Pages. GitHub's Actions cache keeps each source's last good data for the stale-data fallback. Outside the season window it does nothing, and the site keeps the final rankings.
- **Run it by hand:** Actions → *Daily update* → *Run workflow*. A manual run works in the off-season too.
- **`.github/workflows/tests.yml`:** runs the tests on every push.
- **If a run fails** (three or more sources down, or a team-name problem), GitHub emails you and the previous site stays up.

**One-time setup, after this code is on `main`:**
1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Actions → *Daily update* → *Run workflow* for the first deploy.
3. The site appears at `https://<your-username>.github.io/ncaambb/`.

The season (e.g. 2027 = 2026-27) is worked out from the date, so nothing needs changing next year. When a source shows a new team name, add it to `data/aliases.csv` (see below).

## Preview the dashboard

```bash
python -m ncaambb.pipeline          # builds site/data/latest.json first
python -m http.server 8000 -d site
```

Then open http://localhost:8000.
- **Rankings:** a sortable table with Predictive/Résumé toggle, conference filter, search, top-N and optional per-source columns.
- **Team page** (`#/team/<id>`): source agreement chart, rank trend, each source's ratings, résumé and quadrant records.

## Tests

```bash
pytest            # offline, uses saved downloads in tests/fixtures
pytest -m live    # also hits the real websites
```

## Team names

- `data/teams.csv`: the master list of 365 teams, built from ESPN with `python -m ncaambb.tools.seed_teams`.
- `data/aliases.csv`: how each source spells each team. When a source shows a new name, the pipeline reports it rather than guessing. To get match suggestions, run:

  ```bash
  python -m ncaambb.tools.seed_aliases <source> <raw file>
  ```

  Then add the confirmed rows to `aliases.csv`.
- `data/conferences.csv`: each source's conference names. The tests use it to catch wrong matches.
