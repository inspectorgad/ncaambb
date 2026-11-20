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
| **±** | Rank change since the previous daily update, for the selected composite (see *Story cards and trends*). | ▲ |
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
| **Trend** | A small line of the team's Predictive rank over the last two weeks (see *Story cards and trends*). | Rising |
| **Agree** | How much the five predictive systems **disagree** about the team: the spread of their ratings, in standard deviations. Below about 0.10 means they broadly agree; around 0.20 or more means they see the team quite differently, so treat its rank with more caution. | Lower = more agreement |

The **Today's story** cards above the table, and the **±** and **Trend** columns, are explained in detail under *Story cards and trends* below.

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

**Divider lines:** when the table is sorted by rank, lines mark the **Top 25** and **Top 50**, and the top-25 rank numbers are highlighted. Team logos come from ESPN.

**Shading:** a blue tint marks the **top half of D1** in that column; the darker the tint, the closer to #1. The bottom half is unshaded so strong teams stand out. Tempo and Agree are never shaded because neither is a good-or-bad measure.

**Early season:** Resume and Gap swing a lot while teams have played only a handful of games. Pred is more stable, because these systems carry over preseason expectations.

### Story cards and trends

**Today's story cards** sit above the rankings table and pick out what's notable today, so you don't have to scan 365 rows. Each row shows the team's logo and name, its current Predictive rank in grey (e.g. #53), and the card's key number on the right. Click a team to open its page.

| Card | What it shows | How teams are picked |
|---|---|---|
| **Rising** | Teams climbing fastest | Biggest Predictive rank gains since the previous daily update (▲7 = up seven places), among teams in the top 100. The cutoff keeps a jump from #300 to #250 off the card. |
| **Falling** | Teams dropping fastest | Biggest Predictive drops since the previous update (▼12), among teams that were in the top 100 |
| **Under-rewarded** | Good teams whose results haven't caught up | Top-50 Predictive teams with the largest gap between quality and resume. "▼122" means the Resume rank is 122 places worse than the Predictive rank, often from a tough early schedule or close losses. Their resume will likely improve if they keep playing this well. |
| **Systems disagree** | Teams the rating systems can't agree on | Top-50 teams with the biggest spread between Torvik, Haslametrics, ESPN BPI, TeamRankings and CBBD. "Spread 0.65" is high; under about 0.10 means near-consensus. Treat these teams' ranks with the most caution. |
| **Projected field** | Movement in and out of the projected NCAA tournament | Teams that joined (+ in) or dropped out of (− out) the Bracket Matrix consensus field since the previous update |

**When they fill in:**
- **Under-rewarded** and **Systems disagree** use only today's data, so they always show.
- **Rising**, **Falling** and **Projected field** compare against the previous daily update. They fill in once a normal day's games have been played between two updates.
- An empty card says when it will fill in.

**The ± column** is the rank change since the previous daily update, for whichever composite the Predictive/Resume toggle shows:
- **▲3** means up three places; **▼2** means down two; **0** means no change.
- **–** means there's no earlier update to compare with, for example a team missing from the previous day's data.
- Click the heading to sort, and the biggest risers go to the top.

**The Trend column** is a small line chart of each team's **Predictive rank over the last two weeks**:
- **Up means better.** Rank 1 sits at the top, so a line climbing to the right means the team is improving.
- **The dot is today**, at the right end.
- **Hover over the line** to see the exact rank on each date.
- **Small wiggles are flattened:** every line is drawn on at least a 5-place scale, so a team moving between #3 and #4 doesn't look like it's swinging wildly.
- **Sorting** by Trend orders teams by their 7-day change.
- **When it shows:** it needs three daily updates of history and shows "–" until then. After that it grows by one point a day, up to two weeks.

**Reading the ± and Trend columns together:** ± is today's move, and Trend shows whether it's part of a pattern. A ▲5 on a steadily rising line means something different from a ▲5 on a line that's been bouncing up and down. A team page's *Rank over the season* chart shows the full history at a larger size.

### Team page

Click any team name to open its page.

**Header:** a band in the school's colors with its logo, AP rank (if ranked), mascot, conference and record, plus a **Last 5** strip of recent results (W/L; hover a box for the date, score and opponent). **← All teams** returns to the table with your sort and filters kept.

**Summary tiles:**

| Tile | What it shows |
|---|---|
| **Predictive** | Composite quality rank with its change since the previous update (▲/▼), its z-score and how many sources fed it |
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

**Game log (table):** every game so far with the result and score, plus games in the next week. **Pred** is our win chance and predicted score for that game, locked at tip-off, with ✓ or ✗ once it's played (see [Games](#games)). "vs" is a home game, "@" an away game, and "(N)" a neutral site; "conf" marks a conference game. The grey number is the opponent's Predictive rank, and opponents link to their own pages. Hover over a row for the event name (e.g. a holiday tournament).

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

### Offense vs Defense

Every D1 team as a point: **adjusted offense** across (further right = scores more per 100 possessions) and **adjusted defense** up (higher = allows fewer points). The values are averaged across sources.

- **Quadrants:** the solid lines are the D1 averages. Top-right teams are above average at both ends ("Strong both ends"), top-left are defense-first, bottom-right are offense-first, and bottom-left are below average at both.
- **Dashed diagonals** connect teams with the same efficiency margin (EM = offense − defense). Moving toward the top-right corner crosses into higher margins.
- **Highlight** picks which teams show as logos: the Predictive top 25, the top 50, or one conference. Everyone else is a grey dot.
- Hover over a team for its record, ranks and efficiency numbers; click or tap to open its page.

### Conferences

Conferences ranked by their teams' **average AdjEM**.

| Column | Meaning |
|---|---|
| **Avg AdjEM** | Average adjusted efficiency margin of the conference's teams |
| **Field** | How many of its teams are on a consensus seed line in the Bracket Matrix (the projected NCAA field) |
| **Strip** | Each dot is one team, on the same scale for every conference. Blue = in the projected field, grey = not. The black line is the conference average. |

Hover over a dot for the team; click or tap to open its page.

### Bracket

The projected NCAA tournament field from the **Bracket Matrix**, the consensus of every bracket it tracks, laid out by seed line 1–16. Each team shows its **average projected seed**, how many brackets include it (e.g. 52/52), and its Predictive rank here. Lines with more than four teams include play-in (First Four) spots.

**Bubble** lists teams that appear in some brackets but not on a consensus seed line, most-included first.

### Players

**Top 50 players** by our own composite rating. EvanMiya-style player ratings are proprietary, so this one is built only from free, public metrics, the same way as the team composite:

| Metric | Meaning | Source |
|---|---|---|
| **Win shares / 40** | Wins a player adds per 40 minutes, offense plus defense. It measures impact per minute. | CollegeBasketballData |
| **PORPAG** | Points over a replacement-level player, per game. It rewards doing a lot, and doing it well. | CollegeBasketballData |
| **Box plus/minus (BPM)** | Points per 100 possessions better than an average player, estimated from the box score (split into offense and defense) | BartTorvik |

- **Score:** each metric becomes a z-score among **eligible** players (0 = an average eligible player, +2 is excellent), and the score is their average. If Torvik is unavailable on a given day, its last good file (up to 3 days old) is used; after that the score runs on the other two metrics, and the page says so.
- **Eligible** means at least **40% of the team's minutes**, so short-sample flukes stay off the list. Early in the season the list still moves a lot.
- **Sorting and shading:** click any heading to sort. Shading on the three metric columns marks how high each ranks among eligible players; the darker the tint, the closer to the top.
**Players table columns:**

| Column | What it means | Better is |
|---|---|---|
| **#** | Rank by the composite **Score** among all eligible D1 players | Lower |
| **Player** | Name, with team logo, team and class (Fr, So, Jr, Sr). Click it for the player page. | – |
| **Role** | Torvik's role label from how the player is used, e.g. *Pure PG* (pass-first point guard), *Scoring PG*, *Combo G*, *Wing G*, *Wing F*, *Stretch 4* (forward who shoots threes), *PF/C*, *C*. When Torvik has no match, the basic position (G, F, C) is shown. | – |
| **Min%** | Share of the team's total minutes the player has been on the floor. 75% means about 30 of 40 minutes a game. Eligibility needs 40% or more. | Higher = bigger role |
| **PTS / REB / AST** | Points, rebounds and assists per game | Higher |
| **TS%** | True shooting percentage: scoring efficiency that counts threes as worth more and includes free throws. About 55% is average for D1, 60%+ is very good, 65%+ is elite. | Higher |
| **USG** | Usage rate: the share of team possessions the player finishes, with a shot, free throws or a turnover, while on the floor. About 20% is average, 28%+ is a primary option. A high usage with a high TS% is the rarest, most valuable combination. | Context |
| **WS/40** | Win shares per 40 minutes: estimated wins the player adds per 40 minutes, offense plus defense. About 0.100 is average for a regular, 0.200 is very good, 0.300+ is star level. | Higher |
| **PORPAG** | Points over replacement per adjusted game: points per game the player adds compared with a replacement-level player. It combines efficiency with volume, so a heavy-minutes, efficient scorer ranks well. Around 2 is a solid starter, 5+ is excellent. | Higher |
| **BPM** | Box plus/minus: points per 100 possessions the player is better than an average D1 player, estimated from the box score. 0 is average, +5 is very good, +10 is All-American level. Blank if Torvik had no match. | Higher |
| **Score** | The composite: the average of the player's z-scores on WS/40, PORPAG and BPM among eligible players. 0 is an average eligible player, +1 is roughly top 15%, +2 is roughly top 2–3%. | Higher |

Early in the season the benchmark ranges above run higher and swing more, because a few games can produce extreme numbers.

- **Player page:** click a player for their page, which shows their rank among eligible players, every metric with its value, rank and z-score, the BPM offense/defense split, per-game stats and shooting.
- **Team rosters:** each team page has a **Roster** card listing its players by minutes, with their D1 player rank. Players under 40% of minutes appear in grey without a rank.

### Games

The **Games** tab shows every scheduled game involving a D1 team, one day at a time. Use **‹ ›** to change the day and **Today** to jump back. Each card shows both teams with their Predictive rank, then:

| Column | What it means |
|---|---|
| **Win %** | Our chance that the team wins. The favorite's name is bold and its bar is blue. |
| **Pred** | Predicted points for each team |
| **Final** | The final score, once the game is over. The winner's score is bold. |

**✓ Pick right / ✗ Pick wrong** shows whether the favorite won. "No prediction" means the game had tipped off before a prediction was made. That covers games from before tracking started, and games against non-D1 teams, which have no ratings. The filter shows all games, games with a Top 25 team, close games (the favorite between 40% and 60%) or conference games.

**How predictions are made:**
- **Pace:** possessions = the two teams' tempos multiplied, divided by the D1 average tempo.
- **Points:** each team's points = its offense × the opponent's defense ÷ the D1 average, scaled to those possessions. Offense, defense and tempo are the composite's cross-source averages (the AdjO, AdjD and Tempo columns).
- **Home court:** worth 3 points, so the home team gets +1.5 and the visitor −1.5. Nothing is added at neutral sites.
- **Win %:** comes from the predicted margin, assuming the real margin typically misses by about 11 points. A 4-point favorite wins about 64% of the time, and a 10-point favorite about 82%.
- **Updates and locking:** predictions are refreshed with each update until tip-off, then **locked**. The record counts only locked predictions, made before the game started.

**How the win % works:**

The win % answers one question: given the predicted margin, how often does that team actually win? Real games scatter around the prediction. A team predicted to win by 6 sometimes wins by 20 and sometimes loses by 5. Across many games, the real margin misses the predicted one by about **11 points** for a typical game, in a bell-shaped pattern: small misses are common and big ones are rare. About two of every three games finish within 11 points of the predicted margin.

So the win % is the share of that bell curve where the team still comes out ahead:
- **Predicted margin 0:** a coin flip, 50% each.
- **Bigger predicted margin:** the curve shifts further past zero, so the favorite wins more often.
- **The two teams always add up to 100%.**

| Predicted margin | Favorite's win % |
|---|---|
| 0 points | 50% |
| 2 | 57% |
| 4 | 64% |
| 6 | 71% |
| 8 | 77% |
| 10 | 82% |
| 12 | 86% |
| 15 | 91% |
| 20 | 97% |
| 25+ | 99% or more (shown as ">99%") |

**Worked example:** Team A (offense 115, defense 98, tempo 70) hosts Team B (offense 108, defense 104, tempo 68). Assume D1 averages of 108 points per 100 possessions and a tempo of 69.6.
1. **Possessions:** 70 × 68 ÷ 69.6 = 68.4.
2. **Team A's points:** 115 × 104 ÷ 108 × 68.4 ÷ 100 = 75.7, plus 1.5 for home court = **77.2**.
3. **Team B's points:** 108 × 98 ÷ 108 × 68.4 ÷ 100 = 67.0, minus 1.5 = **65.5**.
4. **Margin:** 77.2 − 65.5 = 11.7 points for Team A.
5. **Win %:** with an 11-point typical miss, Team A wins about **86%** of the time and Team B about **14%**. The card shows 86% and 14%, with a predicted score of 77–66 (rounded).

**What the win % does and doesn't mean:**
- **An 80% favorite is supposed to lose 1 time in 5.** An upset doesn't mean the prediction was wrong. Only a pattern over many games does.
- **The calibration table checks the percentages.** In the "Are the win percentages honest?" table, if 80–90% favorites win about 85% of the time, the percentages are honest. If they win much more often, the 11-point spread is too wide. If they win much less often, it's too narrow.
- **It covers only what the ratings know.** Injuries, suspensions, rest and travel aren't included, and early-season ratings still lean on preseason expectations, so they move more.

**Record (tiles at the top):**
- **Picks right, season / Last 7 days:** how often the favorite won. Good public models usually land around 70–75% over a full season. Early-season results run higher, because November has many mismatches.
- **Avg miss, margin:** average points between the predicted and actual margin. About 8–9 is typical.
- **Avg miss, total:** average points between the predicted and actual combined score.
- **Are the win percentages honest?** Open it to see the predictions grouped by the favorite's win %. When we say 70–80%, the favorite should win about 75% of the time. If it wins much more or less often, the percentages are too cautious or too confident.

On each **team page**, the game log has a **Pred** column with the team's win % and predicted score. Played games show ✓ or ✗.

The home-court value and the 11-point typical miss are set in `config/weights.yaml` under `predictions`.

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
- `site/data/games.json`: every game with its prediction and the prediction record, for the Games tab.
- `site/data/history/predictions.json`: every prediction made before tip-off, with the final score once played. It's committed, because it is the record.
- `data/latest/<source>.csv`: the last good data from each source. If a source fails, this is reused for up to 3 days.

Composite weights live in `config/weights.yaml`, and the source URLs in `config/sources.yaml`.

## Automation (GitHub Actions)

- **`.github/workflows/update.yml`:** runs daily at 11:17 UTC (about 6:17 AM ET), with a backup run at 16:43 UTC (about 11:43 AM ET) in case GitHub delays or skips the first one, between Nov 1 and Apr 15. The backup also gives a source that failed in the morning a second chance that day. Torvik sometimes refuses GitHub's servers for a few minutes (HTTP 403), so within each run a Torvik download refused that way is tried twice more, 2 and then 5 minutes later, before falling back to its saved data. It runs the pipeline, commits the day's history snapshot and deploys `site/` to GitHub Pages. GitHub's Actions cache keeps each source's last good data for the stale-data fallback. Outside the season window it does nothing, and the site keeps the final rankings.
- **Cache-busting:** each deploy gives `app.js` and `styles.css` a new versioned address (`app.js?v=<commit>-<run>`), so a normal reload shows a new deploy instead of a cached copy.
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
