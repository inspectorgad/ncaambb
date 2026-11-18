# NCAA D1 Men's Basketball Composite Rankings — Build Plan

A personal dashboard that pulls team ratings and stats from free rating sites every day, combines them into a **Predictive** score and a **Résumé** score, and publishes the result to GitHub Pages.

- **Stack:** Python 3.12 scrapers, a daily GitHub Actions job, and a static site on GitHub Pages.
- **Scope:** all 365 D1 teams, the composite rankings, and per-team stats (AdjO, AdjD, AdjEM, tempo, SOS, records and quadrant records). Each stat is shown by source and averaged across sources.

---

## 1. Data sources (all tested 2026-11-18)

| Source | Endpoint | Format | Feeds | Fields used |
|---|---|---|---|---|
| BartTorvik | `https://barttorvik.com/{YYYY}_team_results.csv` (YYYY = season end year, so 2027 means 2026-27) | CSV | Predictive + Résumé | `adjoe`, `adjde`, `barthag`, `adjt`, `sos`, `ncsos`, `consos`, `WAB`, `record`, `conf` |
| Haslametrics | `https://haslametrics.com/ratings.xml` (current season; must be downloaded with decompression on) | XML, one `<mr>` element per team | Predictive + Résumé | `rk`, `oe`, `de`, `ou`/`du` (pace), `ap` (All-Play %), `sos`, `r_q1..r_q4`, `w`, `l`, `mom` |
| ESPN BPI | `https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex?limit=400` | JSON | Predictive + Résumé | BPI, BPI offense and defense, SOR rank, ESPN team id, logos, conference |
| TeamRankings | `https://www.teamrankings.com/ncaa-basketball/ranking/predictive-by-other` | HTML table | Predictive | Rating, records vs. top 25/50/100 |
| Warren Nolan | `https://www.warrennolan.com/basketball/{YYYY}/net` | HTML table | Résumé | NET rank (current season) |
| NCAA.com | `https://www.ncaa.com/rankings/basketball-men/d1/ncaa-mens-basketball-net-rankings` | HTML table | Résumé | Official NET rank, Quad 1–4 records. Usually first published in early December; until then use Warren Nolan. |

Left out for now:
- **Massey, Hoop Explorer:** blocked by bot checks.
- **Cerebro:** has no team ratings.
- **KenPom, EvanMiya:** paid.

## 2. Repository layout

```
ncaambb/
├── pyproject.toml                # deps: requests, pandas, lxml, pyyaml, rapidfuzz, pytest
├── config/
│   ├── sources.yaml              # URLs, season, enabled flag, timeout per source
│   └── weights.yaml              # composite weights (editable)
├── data/
│   ├── teams.csv                 # canonical list: team_id, name, short_name, conference, espn_id
│   ├── aliases.csv               # source, source_name -> team_id
│   └── raw/                      # git-ignored; raw downloads kept for debugging
├── src/ncaambb/
│   ├── schema.py                 # shared row format + validation
│   ├── http.py                   # requests session: UA, retries, gzip/brotli, timeouts
│   ├── crosswalk.py              # name -> team_id resolution
│   ├── sources/
│   │   ├── base.py               # Source interface: fetch() -> bytes, parse(bytes) -> DataFrame
│   │   ├── torvik.py
│   │   ├── haslametrics.py
│   │   ├── espn_bpi.py
│   │   ├── teamrankings.py
│   │   ├── warrennolan.py
│   │   └── ncaa_net.py
│   ├── composite.py              # z-scores, weighting, trimmed mean, ranks
│   ├── build_site_data.py        # writes site/data/*.json
│   └── pipeline.py               # CLI entry: fetch all -> parse -> map -> composite -> write
├── tests/
│   ├── fixtures/                 # one saved real download per source
│   ├── test_parsers.py
│   ├── test_crosswalk.py
│   └── test_composite.py
├── site/
│   ├── index.html                # rankings table
│   ├── team.html                 # team detail (or hash routing in index)
│   ├── app.js, styles.css
│   └── data/                     # generated: latest.json, history/YYYY-MM-DD.json, meta.json
└── .github/workflows/update.yml
```

## 3. Shared data format

Every source parser returns rows in long format:

| column | example |
|---|---|
| `team_id` | `kansas` |
| `source` | `torvik` |
| `metric` | `adj_em`, `adj_o`, `adj_d`, `tempo`, `sos`, `rating`, `wab`, `net_rank`, `sor_rank`, `q1`…`q4`, `record` |
| `value` | `29.75` |
| `rank` | `1` (the source's own rank for that metric, if it publishes one) |
| `as_of` | `2026-11-18` |

Turning each source's fields into these metrics is the parser's job. For example, Torvik `adj_em = adjoe − adjde`. Validation (`schema.py`) checks that each source has 360 or more teams, that numbers fall in sensible ranges (AdjO 70–140, tempo 55–80), and that no `team_id` appears twice.

## 4. Team-name crosswalk

This is the most fiddly part, so it gets its own step.

1. **Seed `teams.csv` from ESPN BPI.** It has 365 teams with stable ESPN ids, full names and conferences. `team_id` is a slug such as `north-carolina` or `miami-fl`.
2. **Build `aliases.csv` once.** For each source, take its team names and fuzzy-match them to `teams.csv` with `rapidfuzz`, also using conference to settle ties. Then review the list by hand. Known traps include Miami (FL) vs Miami (OH), "Abil. Christian", "UConn/Connecticut", "St. John's", "Saint Mary's", and "App State".
3. **At runtime, use exact lookups only.** If a team name is missing from `aliases.csv`, the run logs it and drops that row. If more than 3 names are unmatched in one source, that source is marked **failed** for the day. The run never guesses a match during the season.
4. **Test:** a fixture test checks that every source's saved data maps all 365 teams.

## 5. Composite method

### 5.1 Inputs per score

**Predictive** (how good is the team?):

| Source | Metric | Default weight |
|---|---|---|
| Torvik | AdjEM (`adjoe − adjde`) | 0.25 |
| Haslametrics | Efficiency margin (`oe − de`). Their rank follows All-Play % exactly, but that is capped at 1.0 with many ties at the top. The margin agrees with it at Spearman 0.994 and spreads teams out better for z-scores. | 0.25 |
| ESPN BPI | BPI | 0.25 |
| TeamRankings | Predictive rating | 0.25 |

**Résumé** (what has the team earned?):

| Source | Metric | Default weight |
|---|---|---|
| NET (NCAA.com, or Warren Nolan until NCAA.com updates) | rank | 0.40 |
| ESPN | SOR rank | 0.30 |
| Torvik | WAB (wins above bubble) | 0.30 |

### 5.2 Calculation
1. **Standardize each metric** across all D1 teams: `z = (x − mean) / std`. Flip the sign where lower is better (AdjD).
2. **Sources that only publish ranks** (NET, SOR): convert to a percentile `p = 1 − (rank − 0.5)/N`, then `z = Φ⁻¹(p)`.
3. **Combine per team** with a weighted mean of the available z-scores. Weights are rescaled when a source is missing for that team.
   - With 4 or more inputs, take a trimmed mean that drops the single highest and lowest z.
4. **Rank** teams by composite z. Output: `pred_z`, `pred_rank`, `res_z`, `res_rank`.
5. **Diagnostics:**
   - `gap = pred_rank − res_rank`. Positive means the résumé ranks ahead of the team's quality (results flattering it). Negative means quality ranks ahead of résumé (under-rewarded so far).
   - `spread` = standard deviation of a team's z-scores across sources, i.e. how much the systems disagree about it.
   - A plain average of source ranks as a check column.
6. **Combined averages of each stat**, e.g. AdjO = mean of Torvik `adjoe`, Haslametrics `oe` and BPI offense. Each source is converted to z-scores first, then put back on the mean source's scale for display. The same applies to AdjD, tempo and SOS.

Weights live in `config/weights.yaml`. Changing them needs no code change.

## 6. Pipeline behavior (`python -m ncaambb.pipeline`)

1. Fetch each enabled source: one request each per day, a clear user agent, 30-second timeout, and 3 retries with backoff. Save the raw download to `data/raw/`.
2. Parse, validate and map to team ids.
3. **When a source fails**, reuse its last good snapshot from `site/data/history/` and mark it `stale: true` with its date. If a source is stale for more than 3 days, drop it from the composite.
4. Compute the composite and write:
   - `site/data/latest.json`: one record per team with every metric by source, the composite averages, ranks and diagnostics.
   - `site/data/history/YYYY-MM-DD.json`: a slimmer daily snapshot (ranks and z-scores) for trend charts.
   - `site/data/meta.json`: run time, status of each source (ok, stale or failed), weights used.
5. **Exit codes:** fail (non-zero) only when 3 or more sources fail or the crosswalk check breaks. The job then turns red and GitHub emails you.

## 7. Front end (GitHub Pages, static)

Plain HTML/JS with no build step and no libraries. The table, sorting and filters are hand-written, and the charts are small inline SVGs drawn at the screen's real width.

- **Rankings view:**
  - A sortable table of 365 teams: Pred rank, Res rank, Gap, Record, Conf, AdjEM/AdjO/AdjD/Tempo/SOS (averaged), and per-source ranks in columns you can expand.
  - Filters: conference, search, top-N.
  - A toggle to sort by Predictive or Résumé.
  - Cells colored by percentile.
- **Team view** (`#/team/kansas`):
  - Each source's rating and rank side by side.
  - Quad records.
  - Trend chart of predictive and résumé rank over the season, built from history files.
  - A source-agreement strip showing each source's z-score.
- **Header:** "Updated <time>" and source status badges from `meta.json`.
- **Layout:** works on a phone, and has a dark mode.

## 8. GitHub Actions (`.github/workflows/update.yml`)

```yaml
on:
  schedule: [{ cron: "17 11 * * *" }]   # ~6:17 AM ET, after overnight updates
  workflow_dispatch: {}
permissions: { contents: write, pages: write, id-token: write }
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e .
      - run: python -m ncaambb.pipeline
      - run: |   # commit only if data changed
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add site/data && git diff --cached --quiet || git commit -m "data: $(date -u +%F)" && git push
      - uses: actions/upload-pages-artifact@v3
        with: { path: site }
      - uses: actions/deploy-pages@v4
```

- A second workflow runs `pytest` on every push.
- Off-season: the scrape is skipped from mid-April through October, but the site stays up with the final rankings.
- **Pages setting:** Settings → Pages → Source: *GitHub Actions*. GitHub Pages is free only for public repos (private repos need GitHub Pro), and the site is publicly viewable either way. That's fine here, because only free public sources are used.

## 9. Testing

- **Parser tests:** run each parser against a saved real download in `tests/fixtures/` and check the row count and a few known values.
- **Crosswalk test:** every fixture maps 365/365 teams.
- **Composite tests:**
  - A small synthetic dataset with known z-scores and ranks.
  - Missing-source rescaling.
  - Trimmed mean.
  - Rank-to-z conversion.
- **Live smoke test** (manual, `pytest -m live`): download each source and run its parser.

## 10. Phases

| Phase | Deliverable | Done when |
|---|---|---|
| 1. Foundation ✅ | Project skeleton, `http.py`, schema, teams.csv from ESPN, Torvik, Haslametrics and BPI parsers, crosswalk for those three | `pytest` passes; 365/365 mapped for 3 sources |
| 2. Remaining sources + composite ✅ | TeamRankings, Warren Nolan and NCAA NET parsers; `composite.py`; JSON output | `latest.json` has Pred and Res ranks for all teams; top 25 looks sensible next to Torvik and BPI |
| 3. Front end ✅ | Rankings table, team view, status badges | Works locally (`python -m http.server -d site`) on desktop and phone |
| 4. Automation | Update and test workflows, Pages deploy | Manual trigger publishes the site; next scheduled run succeeds |
| 5. Later (optional) | Trend charts once history builds up, Massey via headless browser, local-only KenPom/EvanMiya columns, tuning weights against game results | – |

## 11. Risks

| Risk | Mitigation |
|---|---|
| A site changes its HTML or URL | One small parser per source; saved-file tests; fall back to last good data marked stale; red job sends an email |
| Torvik or Haslametrics add bot checks | Already avoided by using their data files instead of HTML pages; if blocked, disable that source in `sources.yaml` |
| Team names change (renames, conference moves) | Exact lookups only; unmatched names fail loudly; edit `aliases.csv` |
| NET isn't published until December | Use Warren Nolan's NET until then; the Résumé score shows how many sources it's using |
| Ratings are noisy early in the season | Torvik and BPI already include preseason priors; show "games played" and the spread column |
| Server load and site terms | One request per source per day, cached, personal use, no paid data |
