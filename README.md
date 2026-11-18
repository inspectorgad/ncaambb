# ncaambb

Composite rankings for all 365 NCAA D1 men's basketball teams, built from free public rating systems. See [PLAN.md](PLAN.md) for the full design.

**Live site:** https://inspectorgad.github.io/ncaambb/

**Status:** Phases 1–4 done. A GitHub Actions job runs every morning in season, rebuilds the rankings and publishes the dashboard to GitHub Pages.

| Source | Feeds | Notes |
|---|---|---|
| BartTorvik | Predictive, Resume (WAB), stats | CSV |
| Haslametrics | Predictive, stats, quad records | XML |
| ESPN BPI | Predictive, Resume (SOR), stats | JSON |
| TeamRankings | Predictive | HTML |
| CollegeBasketballData (CBBD) | Predictive, stats | JSON API; needs a free API key (see *Automation*) |
| NCAA.com NET | Resume | Skipped until the first NET of the season (usually early December) |
| Warren Nolan NET | Resume (backup for NCAA.com) | Skipped while it still shows last season |
| AP & Coaches polls | Display only | Read from the ESPN data |
| Bracket Matrix | Display only | Consensus projected tournament seeds |

## Reading the dashboard

This section is also published as the dashboard's **guide page** (`site/guide.html`, linked from "ⓘ What do these columns mean?"). After editing it, rebuild the page with `python -m ncaambb.tools.build_guide`; a test fails if the two drift apart.

### Rankings table

Use the **Predictive / Resume** toggle to choose which composite the **#** column and default sort follow. Click any heading to sort, and click again to reverse. Hover over a heading for a short reminder of its meaning.

| Column | What it means | Better is |
|---|---|---|
| **#** | Rank in the selected composite (Predictive or Resume). | Lower |
| **Team** | School name, with its conference in grey. Click it to open the team page. | – |
| **W-L** | Wins and losses so far. Sorting uses win percentage, adjusted slightly so a 1-0 team doesn't outrank a 10-1 team. | – |
| **Pred** | **Predictive composite rank:** how good the team is, i.e. who would win on a neutral floor. It blends Torvik, Haslametrics, ESPN BPI, TeamRankings and CBBD. | Lower |
| **Resume** | **Resume composite rank:** what the team has *earned* with its results, the way the selection committee thinks. It blends NET, ESPN strength of record and Torvik wins above bubble. Before NET is published (early December), it uses the last two only. | Lower |
| **Gap** | Pred rank minus Resume rank, showing where quality and results disagree. **▲** means the results look better than the quality ("lucky" or a soft schedule). **▼** means the team is better than its results ("unlucky" or a tough schedule). For example, a team 2nd in Pred and 109th in Resume shows ▼107. | Near 0 = consistent |
| **AdjEM** | **Adjusted efficiency margin:** points per 100 possessions the team outscores an average D1 opponent by, adjusted for opponent strength and game location. It is AdjO minus AdjD, and the best one-number summary of team strength. Averaged across sources. | Higher |
| **AdjO** | **Adjusted offense:** points scored per 100 possessions against an average D1 defense. The small grey number is its rank. | Higher |
| **AdjD** | **Adjusted defense:** points *allowed* per 100 possessions against an average D1 offense. The small grey number is its rank. | **Lower** |
| **Tempo** | Possessions per 40 minutes, i.e. how fast the team plays. A style measure, not good or bad (rank 1 = fastest). | – |
| **SOS** | **Strength of schedule** rank, averaged from Torvik, Haslametrics and ESPN. 1 = toughest schedule played so far. | Lower = tougher |
| **Agree** | How much the five predictive systems **disagree** about the team: the spread of their ratings, in standard deviations. Below about 0.10 means they broadly agree; around 0.20 or more means they see the team quite differently, so treat its rank with more caution. | Lower = more agreement |

**Source columns:** tick this checkbox to show each site's own number next to the composites.

| Column | Source | What it is |
|---|---|---|
| **Torvik** | BartTorvik | Torvik's overall rank |
| **Hasla** | Haslametrics | Haslametrics' rank |
| **BPI** | ESPN | Basketball Power Index rank |
| **TR** | TeamRankings | Predictive rank |
| **CBBD** | CollegeBasketballData | Adjusted net rating rank. Early in the season it uses only this season's games, so it can differ from the others more than they differ from each other. |
| **NET** | NCAA (Warren Nolan as backup) | The official NCAA ranking used by the selection committee. Blank until published each season. |
| **SOR** | ESPN | **Strength of record:** how hard the team's record would be for an average top-25 team to match against the same schedule |
| **WAB** | Torvik | **Wins above bubble:** wins compared with what a bubble-level tournament team would have against the same schedule (+2.0 = two wins better) |
| **AP** | AP Top 25 (via ESPN) | Media poll rank. Blank = unranked. Display only, not in either composite. |
| **Coaches** | Coaches Poll (via ESPN) | Coaches' poll rank. Blank = unranked. Display only. |
| **Seed** | Bracket Matrix | Average projected NCAA tournament seed across about 50–100 published brackets (1.00 = a 1-seed in every bracket). Blank = not in any projected field. Display only. |

**Shading:** a blue tint marks the **top half of D1** in that column; the darker the tint, the closer to #1. The bottom half is unshaded so strong teams stand out. Tempo and Agree are never shaded because neither is a good-or-bad measure.

**Early season:** Resume and Gap swing a lot while teams have played only a handful of games. Pred is more stable, because these systems carry over preseason expectations.

### Team page

Click any team name to open its page.

**Header:** team, conference and record. **← All teams** returns to the table with your sort and filters kept.

**Summary tiles:**

| Tile | What it shows |
|---|---|
| **Predictive** | Composite quality rank, with its z-score and how many sources fed it |
| **Resume** | Composite results rank, with z-score and source count (2 before NET is published, 3 after) |
| **Gap** | Predictive rank minus Resume rank. ▼ under-rewarded so far, ▲ results flattering the team. |
| **AdjEM / AdjO / AdjD** | Cross-source efficiency numbers and their D1 rank (AdjD: lower is better) |
| **Tempo** | Possessions per 40 minutes, ranked from fastest |
| **Schedule** | Strength-of-schedule rank, averaged across sources (1 = toughest) |

**About z-scores:** a z-score is how many standard deviations a team sits above the D1 average. 0 is an average D1 team, +1 is roughly top 15%, +2 roughly top 2–3% (about the top 10 teams), and +2.5 is elite.

**Source agreement (dot chart):** each system's opinion of the team on one shared z-score scale.
- **Blue dots (Predictive):** Torvik, Haslametrics, ESPN BPI, TeamRankings and CBBD.
- **Orange dots (Resume):** ESPN SOR, Torvik WAB, and NET once published.
- **Dashed line:** the composite score for that group.
- **How to read it:** dots bunched together mean the systems agree. A dot far from the others means that system sees the team differently; hover over it for the system's own number and rank.

**Rank over the season (line chart):** Predictive rank (blue) and Resume rank (orange) day by day. Rank 1 is at the top, so a rising line means improvement. Hover for a given day's ranks. It needs at least two days of history before it draws.

**Four factors (table):** the four stats that best explain winning, for offense (this team) and defense (what opponents do against it), each with its D1 rank (1 = best).

| Factor | Meaning | Better offense |
|---|---|---|
| **Effective FG %** | Field-goal % with 3-pointers counted 1.5×, since they're worth more | Higher |
| **Turnover %** | Share of possessions ending in a turnover | Lower |
| **Offensive rebound %** | Share of the team's missed shots it rebounds | Higher |
| **Free throw rate** | Free-throw attempts per 100 field-goal attempts | Higher |

For defense, each is reversed: a low opponent eFG%, a high opponent turnover % and so on rank best.

**Game log (table):** every game so far with the result and score, plus games in the next week. "vs" is a home game, "@" an away game, and "(N)" a neutral site; "conf" marks a conference game. The grey number is the opponent's Predictive rank, and opponents link to their own pages. Hover over a row for the event name (e.g. a holiday tournament).

**Season stats (table):** points, shooting percentages (FG, 2-point, 3-point, free throw, true shooting), 3-point attempts, rebounds, offensive rebounds, assists, turnovers, steals and blocks. Values are per game except percentages. Each has a D1 rank for the team and for its **opponents** (what teams have done against it), where a low opponent figure ranks well.

The four factors, game log and season stats come from CollegeBasketballData, so they need the `CBBD_API_KEY` secret.

**Ratings by source (table):** each system's raw numbers.

| Column | Meaning |
|---|---|
| **Rating** | The system's own rating. Torvik and Haslametrics use efficiency margin, BPI is points better than an average team, TeamRankings uses predictive points. The scales differ, which is why the composite converts them to z-scores. |
| **Rank** | That system's own rank for the team |
| **Off / Def** | Offensive and defensive efficiency. For Torvik and Haslametrics these are points per 100 possessions (Def: lower is better). ESPN's are points above average (higher is better for both). |
| **Tempo** | Each system's pace estimate |

**Resume (table):**

| Row | Meaning |
|---|---|
| **NET rank** | The NCAA's official ranking used by the selection committee. "Not published yet" until early December. |
| **ESPN strength of record** | How hard the team's record would be for an average top-25 team to match against the same schedule |
| **Torvik wins above bubble** | Wins versus a bubble-level tournament team's expected wins against the same schedule, with its rank |
| **ESPN projected record** | ESPN's projected final regular-season record |
| **AP poll / Coaches poll** | Poll rank and voting points, or "unranked" |
| **Bracket Matrix seed** | Average projected tournament seed and how many brackets include the team, or "not in projected field" |
| **ESPN projected seed / chance to make Final Four** | ESPN's tournament projections. They appear later in the season. |
| **vs. top 25 / 26–50 / 51–100** | TeamRankings' record against teams in those ranking bands, a quick check on the quality of wins |
| **Quadrant record** | Wins and losses in the NCAA's four quadrants, which weigh each game by opponent quality *and* where it was played. Q1 is the hardest (e.g. a road game at a top-75 team) and Q4 the easiest. Q1 wins carry the most weight on Selection Sunday; Q3 and Q4 losses hurt the most. It comes from Haslametrics until NET is published, then from the official NCAA figures. |

### Header badges

The badges under the title show each source's status on the latest run:
- **OK** (green dot): downloaded today.
- **Stale** (amber dot): today's download failed, so the last good data (up to 3 days old) is in use.
- **Failed** (red dot): no usable data.
- **Not yet this season** (hollow dot): the source still shows last season, e.g. NET before early December.
- **No API key** (hollow dot): the source needs a key that isn't set up, e.g. CBBD without the `CBBD_API_KEY` secret.

On a phone the badges fold into one summary line; tap it to expand.

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
- `site/data/team/<team_id>.json`: each team's season stats, four factors and game log (loaded only by its team page).
- `data/latest/<source>.csv`: the last good data from each source. If a source fails, this is reused for up to 3 days.

Composite weights live in `config/weights.yaml`, and the source URLs in `config/sources.yaml`.

## Automation (GitHub Actions)

- **`.github/workflows/update.yml`:** runs daily at 11:17 UTC (about 6:17 AM ET), between Nov 1 and Apr 15. It runs the pipeline, commits the day's history snapshot and deploys `site/` to GitHub Pages. GitHub's Actions cache keeps each source's last good data for the stale-data fallback. Outside the season window it does nothing, and the site keeps the final rankings.
- **Run it by hand:** Actions → *Daily update* → *Run workflow*. A manual run works in the off-season too.
- **`.github/workflows/tests.yml`:** runs the tests on every push.
- **If a run fails** (three or more sources down, or a team-name problem), GitHub emails you and the previous site stays up.

**One-time setup, after this code is on `main`:**
1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Settings → Secrets and variables → Actions → *New repository secret*: name `CBBD_API_KEY`, value = your CollegeBasketballData API key. Without it, CBBD shows "No API key" and the composite runs on the other sources.
3. Actions → *Daily update* → *Run workflow* for the first deploy.
4. The site appears at `https://<your-username>.github.io/ncaambb/`.

To run the pipeline locally with CBBD, set the key in your shell first (`export CBBD_API_KEY=...`).

The season (e.g. 2027 = 2026-27) is worked out from the date, so nothing needs changing next year. When a source shows a new team name, add it to `data/aliases.csv` (see below).

## Preview the dashboard

```bash
python -m ncaambb.pipeline          # builds site/data/latest.json first
python -m http.server 8000 -d site
```

Then open http://localhost:8000.
- **Rankings:** a sortable table with Predictive/Resume toggle, conference filter, search, top-N and optional per-source columns.
- **Team page** (`#/team/<id>`): source agreement chart, rank trend, each source's ratings, resume and quadrant records.

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
