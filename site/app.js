"use strict";

/* ================= data ================= */

const SOURCE_LABELS = {
  torvik: "Torvik",
  haslametrics: "Haslametrics",
  espn_bpi: "ESPN BPI",
  teamrankings: "TeamRankings",
  cbbd: "CBBD",
  bracketmatrix: "Bracket Matrix",
  warrennolan: "Warren Nolan",
  ncaa_net: "NCAA NET",
};
const INPUT_LABELS = {
  "torvik:rating": "Torvik",
  "haslametrics:rating": "Haslametrics",
  "espn_bpi:rating": "ESPN BPI",
  "teamrankings:rating": "TeamRankings",
  "cbbd:rating": "CBBD",
  "ncaa_net/warrennolan:net_rank": "NET",
  "espn_bpi:sor_rank": "ESPN SOR",
  "torvik:wab": "Torvik WAB",
};
const GUIDE_URL = "guide.html";
const HELP = {
  table: `${GUIDE_URL}#rankings-table`,
  stories: `${GUIDE_URL}#story-cards-and-trends`,
  team: `${GUIDE_URL}#team-page`,
  scatter: `${GUIDE_URL}#offense-vs-defense`,
  conferences: `${GUIDE_URL}#conferences`,
  bracket: `${GUIDE_URL}#bracket`,
  players: `${GUIDE_URL}#players`,
};
const helpLink = (href, text) =>
  `<a class="help-link" href="${href}">ⓘ ${text}</a>`;
const STATUS_TEXT = {
  ok: "OK", stale: "Stale", failed: "Failed", not_current: "Not yet this season", not_configured: "No API key",
};

const state = {
  latest: null,
  meta: null,
  byId: new Map(),
  historyIndex: null,
  history: new Map(), // date -> snapshot
};

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

/* ================= helpers ================= */

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 1) => (v == null || Number.isNaN(v) ? "–" : Number(v).toFixed(d));
const fmtInt = (v) => (v == null ? "–" : String(Math.round(v)));
const signed = (v, d = 0) => (v == null ? "–" : (v > 0 ? "+" : "") + Number(v).toFixed(d));
const ordinal = (n) => {
  if (n == null) return "–";
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};
const N_TEAMS = () => state.latest?.teams.length || 365;

/* ---------- logos & team colors ---------- */

function isDark() {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}

/** ESPN team logo, resized by ESPN's image service. `onDark` picks the dark-background version. */
function logoUrl(t, size, onDark = isDark()) {
  const variant = onDark ? "500-dark" : "500";
  const px = size * 2; // crisp on high-density screens
  return `https://a.espncdn.com/combiner/i?img=/i/teamlogos/ncaa/${variant}/${t.espn_id}.png&h=${px}&w=${px}`;
}

function logo(t, size, onDark = isDark()) {
  if (!t?.espn_id) return "";
  const src = logoUrl(t, size, onDark);
  return `<img class="logo" src="${src}" width="${size}" height="${size}" alt="" loading="lazy" decoding="async"
    onerror="this.style.visibility='hidden'">`;
}

/* ---------- movement ---------- */

const shortDate = (iso) => iso ? new Date(iso + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric" }) : "";

function moveBadge(v, since) {
  if (v == null) return `<span class="muted" title="No earlier update to compare yet">–</span>`;
  if (v === 0) return `<span class="move flat" title="No change since ${shortDate(since)}">0</span>`;
  const up = v > 0;
  return `<span class="move ${up ? "up" : "down"}" title="${up ? "Up" : "Down"} ${Math.abs(v)} since ${shortDate(since)}">${up ? "▲" : "▼"}${Math.abs(v)}</span>`;
}

/** Tiny rank line: rank 1 at the top. Needs at least three points. */
function sparkline(trend, w = 64, h = 18) {
  const pts = (trend?.pred || []).map((r, i) => [i, r]).filter(([, r]) => r != null);
  if (pts.length < 3) return `<span class="muted" title="Needs three days of history">–</span>`;
  const n = trend.pred.length - 1 || 1;
  const rs = pts.map(([, r]) => r), lo = Math.min(...rs), hi = Math.max(...rs);
  const span = Math.max(hi - lo, 5); // don't magnify tiny wiggles
  const x = (i) => 2 + (i / n) * (w - 4);
  const y = (r) => 2 + ((r - lo) / span) * (h - 4);
  const path = pts.map(([i, r]) => `${x(i).toFixed(1)},${y(r).toFixed(1)}`).join(" ");
  const [li, lr] = pts[pts.length - 1];
  const label = pts.map(([i, r]) => `${shortDate(trend.dates[i])}: ${r}`).join(" · ");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="Predictive rank trend">
    <title>${esc(label)}</title><polyline points="${path}"/><circle cx="${x(li).toFixed(1)}" cy="${y(lr).toFixed(1)}" r="2.2"/></svg>`;
}

/** WCAG relative luminance of a 6-digit hex color. */
function luminance(hex) {
  const c = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

/** Team band colors: background, readable text color, and whether it counts as dark. */
function teamBand(t) {
  const hex = /^[0-9a-f]{6}$/i.test(t.color || "") ? t.color : null;
  if (!hex) return null;
  const L = luminance(hex);
  // pick whichever text color has the higher contrast ratio against the band
  const whiteContrast = 1.05 / (L + 0.05), blackContrast = (L + 0.05) / 0.05;
  const dark = whiteContrast >= blackContrast;
  return { bg: `#${hex}`, fg: dark ? "#ffffff" : "#111111", dark,
    accent: /^[0-9a-f]{6}$/i.test(t.alt_color || "") ? `#${t.alt_color}` : null };
}

/** Inline style tinting a cell by rank: rank 1 strongest, bottom half unshaded. */
function heatStyle(rank) {
  if (rank == null) return "";
  const strength = Math.max(0, 1 - (rank - 1) / (N_TEAMS() / 2));
  if (strength <= 0) return "";
  return ` style="--h: color-mix(in oklab, var(--heat) calc(var(--heat-max) * ${strength.toFixed(3)}), transparent)"`;
}

/* ================= tooltip ================= */

const tip = {
  el: null,
  show(evt, html) {
    this.el ||= $("#tooltip");
    this.el.innerHTML = html;
    this.el.style.display = "block";
    this.move(evt);
  },
  move(evt) {
    if (!this.el || this.el.style.display !== "block") return;
    const pad = 14, w = this.el.offsetWidth, h = this.el.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    this.el.style.left = Math.max(8, x) + "px";
    this.el.style.top = Math.max(8, y) + "px";
  },
  hide() { if (this.el) this.el.style.display = "none"; },
};

/* ================= header ================= */

function renderHeader() {
  const meta = state.meta;
  const when = new Date(meta.generated_at);
  $("#updated").textContent = `Data as of ${meta.as_of} · updated ${when.toLocaleString([], {
    dateStyle: "medium", timeStyle: "short" })}`;
  $("#badges").innerHTML = meta.sources.map((s) => {
    const label = SOURCE_LABELS[s.source] || s.source;
    const detail = s.status === "ok" ? `${s.teams} teams`
      : s.status === "stale" ? `using data from ${s.data_date}`
      : s.status === "not_current" ? `latest data ${s.data_date}`
      : s.status === "not_configured" ? "add the API key as a GitHub Actions secret"
      : (s.error || "");
    return `<span class="badge" data-status="${s.status}" title="${esc(label)}: ${esc(STATUS_TEXT[s.status])} – ${esc(detail)}">
      <span class="dot" aria-hidden="true"></span>${esc(label)}<span class="muted">· ${esc(STATUS_TEXT[s.status] || s.status)}</span></span>`;
  }).join("");
  const counts = {};
  meta.sources.forEach((s) => { counts[s.status] = (counts[s.status] || 0) + 1; });
  $("#sources-summary").textContent = "Sources: " + Object.entries(counts)
    .map(([k, n]) => `${n} ${k === "not_current" ? "not yet this season" : STATUS_TEXT[k].toLowerCase()}`).join(" · ");
  // always open on wide screens (the summary line is hidden there)
  const wide = matchMedia("(min-width: 720px)");
  const sync = () => { if (wide.matches) $("#sources-box").open = true; };
  sync(); wide.addEventListener("change", sync);
}

function initTheme() {
  $("#theme-toggle").addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* ignore */ }
    route(); // redraw charts with new colors
  });
}

/* ================= rankings view ================= */

const src = (t, s, k) => t.sources?.[s]?.[k];
const COLUMNS = [
  { key: "rank", label: "#", cls: "rk sticky", get: (t, ui) => ui.mode === "res" ? t.res.rank : t.pred.rank,
    cell: (t, ui) => fmtInt(ui.mode === "res" ? t.res.rank : t.pred.rank), title: "Rank in the selected composite" },
  { key: "team", label: "Team", cls: "l sticky2 team-cell", get: (t) => t.name, dir: 1,
    cell: (t) => `<a class="team-link" href="#/team/${t.id}">${logo(t, 22)}<span class="tname">${esc(t.name)}</span></a><span class="conf">${esc(t.conf)}</span>` },
  { key: "move", label: "±", dir: -1,
    get: (t, ui) => (ui.mode === "res" ? t.move?.res : t.move?.pred),
    cell: (t, ui) => moveBadge(ui.mode === "res" ? t.move?.res : t.move?.pred, t.move?.since),
    title: "Rank change since the previous daily update (for the selected composite)" },
  { key: "record", label: "W-L", get: (t) => {
      const m = /^(\d+)-(\d+)$/.exec(t.record || ""); return m ? (+m[1] + 1) / (+m[1] + +m[2] + 2) : null;
    }, dir: -1, cell: (t) => esc(t.record || "–") },
  { key: "pred", label: "Pred", get: (t) => t.pred.rank, heat: (t) => t.pred.rank,
    cell: (t) => fmtInt(t.pred.rank), title: "Predictive composite rank (Torvik, Haslametrics, BPI, TeamRankings, CBBD)" },
  { key: "res", label: "Resume", get: (t) => t.res.rank, heat: (t) => t.res.rank,
    cell: (t) => fmtInt(t.res.rank), title: "Resume composite rank (NET, ESPN SOR, Torvik WAB)" },
  { key: "gap", label: "Gap", get: (t) => t.gap, dir: -1,
    cell: (t) => t.gap == null ? "–" : t.gap === 0 ? "0"
      : `<span class="${t.gap > 0 ? "gap-up" : "gap-down"}">${Math.abs(t.gap)}</span>`,
    title: "Pred rank − Resume rank. ▲ resume ahead of quality; ▼ quality ahead of resume (under-rewarded)" },
  { key: "adj_em", label: "AdjEM", get: (t) => t.stats.adj_em?.rank, heat: (t) => t.stats.adj_em?.rank,
    cell: (t) => fmt(t.stats.adj_em?.value), title: "Adjusted efficiency margin, averaged across sources" },
  { key: "adj_o", label: "AdjO", get: (t) => t.stats.adj_o?.rank, heat: (t) => t.stats.adj_o?.rank,
    cell: (t) => `${fmt(t.stats.adj_o?.value)}<span class="sub">${fmtInt(t.stats.adj_o?.rank)}</span>`,
    title: "Adjusted offense (points per 100 possessions); small number = rank" },
  { key: "adj_d", label: "AdjD", get: (t) => t.stats.adj_d?.rank, heat: (t) => t.stats.adj_d?.rank,
    cell: (t) => `${fmt(t.stats.adj_d?.value)}<span class="sub">${fmtInt(t.stats.adj_d?.rank)}</span>`,
    title: "Adjusted defense (points allowed per 100; lower is better); small number = rank" },
  { key: "tempo", label: "Tempo", get: (t) => t.stats.tempo?.rank,
    cell: (t) => `${fmt(t.stats.tempo?.value)}<span class="sub">${fmtInt(t.stats.tempo?.rank)}</span>`,
    title: "Possessions per 40 minutes; rank 1 = fastest" },
  { key: "sos", label: "SOS", get: (t) => t.stats.sos?.rank, heat: (t) => t.stats.sos?.rank,
    cell: (t) => fmtInt(t.stats.sos?.rank), title: "Strength of schedule rank (1 = toughest), averaged across sources" },
  { key: "spread", label: "Agree", get: (t) => t.spread,
    cell: (t) => fmt(t.spread, 2), title: "How much the predictive sources disagree (std. dev. of z-scores). Lower = more agreement" },
  { key: "trend", label: "Trend", get: (t) => t.move?.pred_7d ?? t.move?.pred,  dir: -1,
    cell: (t) => sparkline(t.trend), title: "Predictive rank over the last two weeks (higher = better); appears after three days of history" },
  { key: "s_torvik", label: "Torvik", src: true, get: (t) => src(t, "torvik", "rating_rank"),
    cell: (t) => fmtInt(src(t, "torvik", "rating_rank")), title: "Torvik's own rank" },
  { key: "s_hasla", label: "Hasla", src: true, get: (t) => src(t, "haslametrics", "rating_rank"),
    cell: (t) => fmtInt(src(t, "haslametrics", "rating_rank")), title: "Haslametrics' own rank" },
  { key: "s_bpi", label: "BPI", src: true, get: (t) => src(t, "espn_bpi", "rating_rank"),
    cell: (t) => fmtInt(src(t, "espn_bpi", "rating_rank")), title: "ESPN BPI rank" },
  { key: "s_tr", label: "TR", src: true, get: (t) => src(t, "teamrankings", "rating_rank"),
    cell: (t) => fmtInt(src(t, "teamrankings", "rating_rank")), title: "TeamRankings predictive rank" },
  { key: "s_cbbd", label: "CBBD", src: true, get: (t) => src(t, "cbbd", "rating_rank"),
    cell: (t) => fmtInt(src(t, "cbbd", "rating_rank")), title: "CollegeBasketballData adjusted net rating rank" },
  { key: "s_net", label: "NET", src: true, get: (t) => src(t, "ncaa_net", "net_rank") ?? src(t, "warrennolan", "net_rank"),
    cell: (t) => fmtInt(src(t, "ncaa_net", "net_rank") ?? src(t, "warrennolan", "net_rank")), title: "NCAA NET rank (blank until published this season)" },
  { key: "s_sor", label: "SOR", src: true, get: (t) => src(t, "espn_bpi", "sor_rank"),
    cell: (t) => fmtInt(src(t, "espn_bpi", "sor_rank")), title: "ESPN strength of record rank" },
  { key: "s_wab", label: "WAB", src: true, get: (t) => src(t, "torvik", "wab"), dir: -1,
    cell: (t) => signed(src(t, "torvik", "wab"), 1), title: "Torvik wins above bubble" },
  { key: "s_ap", label: "AP", src: true, get: (t) => src(t, "espn_bpi", "ap_rank"),
    cell: (t) => fmtInt(src(t, "espn_bpi", "ap_rank")), title: "AP Top 25 rank (blank = unranked). Display only, not in the composite" },
  { key: "s_coaches", label: "Coaches", src: true, get: (t) => src(t, "espn_bpi", "coaches_rank"),
    cell: (t) => fmtInt(src(t, "espn_bpi", "coaches_rank")), title: "Coaches Poll rank (blank = unranked). Display only, not in the composite" },
  { key: "s_seed", label: "Seed", src: true, get: (t) => src(t, "bracketmatrix", "avg_seed"),
    cell: (t) => fmt(src(t, "bracketmatrix", "avg_seed"), 2),
    title: "Bracket Matrix average projected NCAA tournament seed (blank = not in the projected field). Display only" },
];

const ui = Object.assign(
  { mode: "pred", sort: "rank", dir: 1, q: "", conf: "", top: "all", sources: false },
  store.get("ui", {}),
);
ui.q = ""; // never restore a search

function filteredTeams() {
  const q = ui.q.trim().toLowerCase();
  let teams = state.latest.teams.filter((t) =>
    (!ui.conf || t.conf === ui.conf) &&
    (!q || t.name.toLowerCase().includes(q) || t.short.toLowerCase().includes(q)));
  if (ui.top !== "all") {
    const n = +ui.top;
    teams = teams.filter((t) => (ui.mode === "res" ? t.res.rank : t.pred.rank) <= n);
  }
  const col = COLUMNS.find((c) => c.key === ui.sort) || COLUMNS[0];
  const dir = ui.dir;
  return teams.slice().sort((a, b) => {
    const va = col.get(a, ui), vb = col.get(b, ui);
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === "string") return dir * va.localeCompare(vb);
    return dir * (va - vb) || (a.pred.rank - b.pred.rank);
  });
}

function renderRankings() {
  const confs = [...new Set(state.latest.teams.map((t) => t.conf))].sort();
  const app = $("#app");
  app.innerHTML = `
    ${storyCards()}
    <div class="controls" role="search">
      <div class="seg" role="group" aria-label="Composite">
        <button type="button" data-mode="pred" aria-pressed="${ui.mode === "pred"}">Predictive</button>
        <button type="button" data-mode="res" aria-pressed="${ui.mode === "res"}">Resume</button>
      </div>
      <input type="search" id="q" placeholder="Search teams" aria-label="Search teams">
      <select id="conf" aria-label="Conference">
        <option value="">All conferences</option>
        ${confs.map((c) => `<option ${c === ui.conf ? "selected" : ""}>${esc(c)}</option>`).join("")}
      </select>
      <select id="top" aria-label="How many teams">
        ${[["all", "All teams"], ["25", "Top 25"], ["50", "Top 50"], ["100", "Top 100"]]
          .map(([v, l]) => `<option value="${v}" ${v === ui.top ? "selected" : ""}>${l}</option>`).join("")}
      </select>
      <label class="check"><input type="checkbox" id="sources" ${ui.sources ? "checked" : ""}> Source columns</label>
      <span class="count" id="count"></span>
    </div>
    <div class="help-row">${helpLink(HELP.table, "What do these columns mean?")}</div>
    <div class="table-wrap ${ui.sources ? "show-sources" : ""}" id="table-wrap">
      <table class="rank">
        <thead><tr>${COLUMNS.map((c) => `<th scope="col" data-key="${c.key}"
          class="${c.cls?.includes("l") ? "l " : ""}${c.cls?.includes("sticky2") ? "sticky2" : c.cls?.includes("sticky") ? "sticky" : ""} ${c.src ? "src-col" : ""}"
          title="${esc(c.title || "")}">${esc(c.label)}</th>`).join("")}</tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <p class="legend-note">
      <b>Pred</b> ranks how good a team is (Torvik, Haslametrics, ESPN BPI, TeamRankings, CBBD).
      <b>Resume</b> ranks what it has earned (NET, ESPN strength of record, Torvik wins above bubble).
      <b>Gap</b>: ▲ results flattering the team, ▼ under-rewarded so far.
      Shading marks the top half of D1 on each column. Hover any heading for details; tap a team for its page.
    </p>`;

  $("#q").value = ui.q;
  app.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
    ui.mode = b.dataset.mode; ui.sort = "rank"; ui.dir = 1; save(); renderRankings();
  }));
  $("#q").addEventListener("input", (e) => { ui.q = e.target.value; renderRows(); });
  $("#conf").addEventListener("change", (e) => { ui.conf = e.target.value; save(); renderRows(); });
  $("#top").addEventListener("change", (e) => { ui.top = e.target.value; save(); renderRows(); });
  $("#sources").addEventListener("change", (e) => {
    ui.sources = e.target.checked; save();
    $("#table-wrap").classList.toggle("show-sources", ui.sources);
  });
  app.querySelectorAll("thead th[data-key]").forEach((th) => th.addEventListener("click", () => {
    const col = COLUMNS.find((c) => c.key === th.dataset.key);
    if (ui.sort === col.key) ui.dir = -ui.dir;
    else { ui.sort = col.key; ui.dir = col.dir || 1; }
    save(); renderRows();
  }));
  renderRows();
}

/* ---------- "Today's story" cards ---------- */

function storyCards() {
  const st = state.latest.stories;
  if (!st) return "";
  const since = st.since ? `since ${shortDate(st.since)}` : "";
  const waiting = "Appears after the next daily update.";
  const row = (item, valueHtml) => {
    const t = state.byId.get(item.id);
    if (!t) return "";
    return `<li><a class="team-link" href="#/team/${t.id}">${logo(t, 20)}<span>${esc(t.short)}</span></a>
      <span class="story-meta">${fmtInt(t.pred.rank)}</span><span class="story-val">${valueHtml}</span></li>`;
  };
  const card = (title, sub, items, valueFn, empty) => `<section class="story">
      <h3>${title}</h3><p class="story-sub">${sub}</p>
      ${items.length ? `<ul>${items.map((i) => row(i, valueFn(i))).join("")}</ul>` : `<p class="story-empty">${empty}</p>`}
    </section>`;
  const arrow = (v) => moveBadge(v, st.since);
  const fieldItems = st.new_in_field.concat(st.left_field.map((i) => ({ ...i, left: true })));
  return `<div class="help-row stories-help">${helpLink(HELP.stories, "About these cards and the ± / Trend columns")}</div>
  <div class="stories" aria-label="Today's story">
    ${card("Rising", `Biggest Predictive gains in the top 100 ${since}`, st.risers, (i) => arrow(i.value), since ? "No risers today." : waiting)}
    ${card("Falling", `Biggest Predictive drops in the top 100 ${since}`, st.fallers, (i) => arrow(i.value), since ? "No fallers today." : waiting)}
    ${card("Under-rewarded", "Top-50 teams whose resume trails their quality most", st.under_rewarded,
      (i) => `<span class="gap-down">${Math.abs(i.value)}</span>`, "None right now.")}
    ${card("Systems disagree", "Top-50 teams the rating systems see most differently", st.disputed,
      (i) => `spread ${fmt(i.value, 2)}`, "None right now.")}
    ${card("Projected field", st.field_tracked ? `Teams entering (+) or leaving (−) the Bracket Matrix field ${since}` : "Changes to the Bracket Matrix field",
      fieldItems.slice(0, 5), (i) => (i.left ? "− out" : "+ in"), st.field_tracked ? "No changes." : "Tracking starts with today's update.")}
  </div>`;
}

function renderRows() {
  const teams = filteredTeams();
  // landmark rows ("Top 25", "Top 50") only make sense in rank order
  const rankOrder = ui.sort === "rank" && ui.dir === 1;
  const rankOf = (t) => (ui.mode === "res" ? t.res.rank : t.pred.rank);
  const LANDMARKS = [25, 50];
  const rows = [];
  teams.forEach((t, i) => {
    const top25 = rankOf(t) <= 25 ? " top25" : "";
    rows.push(`<tr class="team-row${top25}">${COLUMNS.map((c) => {
      const style = c.heat ? heatStyle(c.heat(t)) : "";
      return `<td class="${c.cls || ""} ${c.src ? "src-col" : ""}${style ? " heat" : ""}"${style}>${c.cell(t, ui)}</td>`;
    }).join("")}</tr>`);
    const next = teams[i + 1];
    if (rankOrder && next) {
      for (const n of LANDMARKS) {
        if (rankOf(t) <= n && rankOf(next) > n) {
          rows.push(`<tr class="landmark"><td colspan="${COLUMNS.length}"><span>▲ Top ${n}</span></td></tr>`);
        }
      }
    }
  });
  $("#tbody").innerHTML = rows.join("") || `<tr><td colspan="${COLUMNS.length}" class="empty">No teams match.</td></tr>`;
  document.querySelectorAll("thead th[data-key]").forEach((th) => {
    th.setAttribute("aria-sort", th.dataset.key === ui.sort ? (ui.dir === 1 ? "ascending" : "descending") : "none");
  });
  $("#count").textContent = `Showing ${teams.length} of ${N_TEAMS()}`;
}

function save() { store.set("ui", { ...ui, q: "" }); }

/* ================= team view ================= */

async function renderTeam(id) {
  const t = state.byId.get(id);
  const app = $("#app");
  if (!t) {
    app.innerHTML = `<a class="back" href="#/">← All teams</a><p class="empty">Unknown team “${esc(id)}”.</p>`;
    return;
  }
  document.title = `${t.name} · D1 Composite Rankings`;
  const n = N_TEAMS();
  const st = t.stats;
  const tile = (label, value, note) =>
    `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div><div class="note">${note}</div></div>`;
  const gapNote = t.gap == null ? "" : t.gap > 0 ? "results ahead of quality" : t.gap < 0 ? "under-rewarded so far" : "in line";

  app.innerHTML = `
    <div class="nav-row">
      <a class="back" href="#/">← All teams</a>
      ${helpLink(HELP.team, "How to read this page")}
    </div>
    ${teamHeader(t)}
    <div class="tiles">
      ${tile("Predictive", `${ordinal(t.pred.rank)} <span class="tile-move">${moveBadge(t.move?.pred, t.move?.since)}</span>`,
        `z ${fmt(t.pred.z, 2)} · ${t.pred.n} sources${t.move?.since ? ` · vs ${shortDate(t.move.since)}` : ""}`)}
      ${tile("Resume", `${ordinal(t.res.rank)} <span class="tile-move">${moveBadge(t.move?.res, t.move?.since)}</span>`,
        `z ${fmt(t.res.z, 2)} · ${t.res.n} sources${t.move?.since ? ` · vs ${shortDate(t.move.since)}` : ""}`)}
      ${tile("Gap", t.gap == null ? "–" : t.gap === 0 ? "0" : (t.gap > 0 ? "▲ " : "▼ ") + Math.abs(t.gap), gapNote)}
      ${tile("AdjEM", fmt(st.adj_em?.value), `${ordinal(st.adj_em?.rank)} of ${n}`)}
      ${tile("AdjO", fmt(st.adj_o?.value), `${ordinal(st.adj_o?.rank)} of ${n}`)}
      ${tile("AdjD", fmt(st.adj_d?.value), `${ordinal(st.adj_d?.rank)} of ${n} (lower is better)`)}
      ${tile("Tempo", fmt(st.tempo?.value), `${ordinal(st.tempo?.rank)} fastest`)}
      ${tile("Schedule", ordinal(st.sos?.rank), "toughest, averaged")}
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Source agreement</h3>
        <p class="desc">Each source's rating as a z-score (0 = D1 average). The line marks the composite.</p>
        <div id="agree"></div>
      </section>
      <section class="card">
        <h3>Rank over the season</h3>
        <p class="desc">Composite ranks by day (1 at top).</p>
        <div id="trend"><p class="empty">Loading history…</p></div>
      </section>
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Four factors</h3>
        <p class="desc">The four stats that best explain winning. Offense = this team; defense = what opponents do against it. Ranks are out of D1 (1 = best).</p>
        <div class="plain-wrap" id="four-factors"><p class="empty">Loading stats…</p></div>
      </section>
      <section class="card">
        <h3>Game log</h3>
        <p class="desc">Results so far and games in the next week. Grey number = opponent's predictive rank; (N) = neutral site; hover a row for the event name.</p>
        <div class="plain-wrap" id="game-log"><p class="empty">Loading games…</p></div>
      </section>
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Season stats</h3>
        <p class="desc">Per game unless it's a percentage, with D1 ranks (1 = best). "Opponents" is what teams have done against this one, so a low opponent figure ranks well.</p>
        <div class="plain-wrap" id="season-stats"><p class="empty">Loading stats…</p></div>
      </section>
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Roster</h3>
        <p class="desc">Players by share of team minutes. "Rank" is the player rating among all D1 players with at least 40% of their team's minutes; click a player for the breakdown.</p>
        <div class="plain-wrap" id="roster"><p class="empty">Loading roster…</p></div>
      </section>
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Ratings by source</h3>
        <p class="desc">Each system's own numbers and rank.</p>
        <div class="plain-wrap">${sourceTable(t)}</div>
      </section>
      <section class="card">
        <h3>Resume</h3>
        <p class="desc">${t.quads ? `Quadrant records from ${esc(SOURCE_LABELS[t.quads.source] || t.quads.source)}.` : ""}</p>
        <div class="plain-wrap">${resumeTable(t)}</div>
      </section>
    </div>`;
  drawAgreement($("#agree"), t);
  loadTeamDetail(id).then(renderTeamDetail, () => {
    for (const sel of ["#four-factors", "#game-log", "#season-stats"]) {
      if ($(sel)) $(sel).innerHTML = `<p class="empty">Stats unavailable.</p>`;
    }
  });
  let series = null;
  try {
    series = await loadTeamHistory(id);
    drawTrend($("#trend"), series);
  } catch (e) {
    $("#trend").innerHTML = `<p class="empty">History unavailable.</p>`;
  }
  // charts are drawn at their real pixel width so text stays legible: redraw on resize
  redrawCharts = () => {
    if ($("#agree")) drawAgreement($("#agree"), t);
    if ($("#trend") && series) drawTrend($("#trend"), series);
  };
}

let redrawCharts = null;
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => redrawCharts && redrawCharts(), 150);
});

/* ---------- season stats, four factors, game log ---------- */

async function loadTeamDetail(id) {
  return getJSON(`data/team/${id}.json`);
}

const rankCell = (rank) => {
  const style = heatStyle(rank);
  return `<td class="rk-cell${style ? " heat" : ""}"${style}>${fmtInt(rank)}</td>`;
};

function renderTeamDetail(d) {
  if (!$("#four-factors")) return; // user navigated away
  renderRoster(d);
  const last5 = d.games.filter((g) => g.result).slice(-5);
  if (last5.length && $("#band-form")) {
    $("#band-form").innerHTML = `<span class="form-label">Last ${last5.length}</span>` + last5.map((g) => {
      const opp = g.opp ? state.byId.get(g.opp) : null;
      return `<span class="form-chip ${g.result === "W" ? "w" : "l"}" title="${esc(`${shortDate(g.date)} ${g.result} ${g.score} vs ${opp ? opp.name : g.opp_name}`)}">${g.result}</span>`;
    }).join("");
  }
  // which values are percentages differs per table ("tov" is a rate in one, per game in the other)
  const FF_PCT = new Set(["efg", "tov", "orb"]);
  const STAT_PCT = new Set(["fg_pct", "two_pct", "three_pct", "ft_pct", "ts_pct"]);
  const val = (pct, key, v) => v == null ? "–" : `${fmt(v, 1)}${pct.has(key) ? "%" : ""}`;

  $("#four-factors").innerHTML = `<table class="plain">
    <thead><tr><th class="l">Factor</th><th>Offense</th><th>Rank</th><th>Defense</th><th>Rank</th></tr></thead>
    <tbody>${d.four_factors.map((f) => `<tr><td class="l">${esc(f.label)}</td>
      <td>${val(FF_PCT, f.key, f.off)}</td>${rankCell(f.off_rank)}<td>${val(FF_PCT, f.key, f.def)}</td>${rankCell(f.def_rank)}</tr>`).join("")}
    </tbody></table>
    <p class="desc" style="margin-top:8px">Better offense: higher eFG%, OReb% and FT rate, lower turnover %. Defense is the reverse.
    FT rate = free-throw attempts per 100 field-goal attempts.</p>`;

  $("#season-stats").innerHTML = `<table class="plain">
    <thead><tr><th class="l">Stat</th><th>Team</th><th>Rank</th><th>Opponents</th><th>Rank</th></tr></thead>
    <tbody>${d.stats.map((s) => `<tr><td class="l">${esc(s.label)}</td>
      <td>${val(STAT_PCT, s.key, s.team)}</td>${rankCell(s.team_rank)}<td>${val(STAT_PCT, s.key, s.opp)}</td>${rankCell(s.opp_rank)}</tr>`).join("")}
    </tbody></table>
    <p class="desc" style="margin-top:8px">${d.games_played ?? "–"} games played (as of ${esc(d.as_of)}). Source: CollegeBasketballData.</p>`;

  const fmtDay = (iso) => new Date(iso + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric" });
  const siteText = { H: "vs", A: "@", N: "vs" };
  const siteTitle = { H: "home", A: "away", N: "neutral site" };
  const rows = d.games.map((g) => {
    const opp = g.opp ? state.byId.get(g.opp) : null;
    const name = opp ? `<a class="team-link" href="#/team/${opp.id}">${logo(opp, 16)}<span>${esc(opp.name)}</span></a><span class="sub">${fmtInt(opp.pred.rank)}</span>`
      : `${esc(g.opp_name || "?")}<span class="sub">non-D1</span>`;
    const where = `<span class="site" title="${siteTitle[g.site] || ""}">${siteText[g.site] || ""}</span>`;
    const tags = (g.site === "N" ? '<span class="sub">(N)</span>' : "") + (g.conf ? '<span class="sub">conf</span>' : "");
    const result = g.result ? `<b>${g.result}</b> ${esc(g.score)}`
      : `<span class="muted">${g.status === "postponed" ? "postponed" : g.status === "in_progress" ? "live" : "next"}</span>`;
    return `<tr${g.result ? "" : ' class="muted"'} title="${esc(g.note || "")}">
      <td class="l">${fmtDay(g.date)}</td><td class="l opp-cell">${where} ${name}${tags}</td><td>${result}</td></tr>`;
  });
  $("#game-log").innerHTML = rows.length
    ? `<table class="plain"><thead><tr><th class="l">Date</th><th class="l">Opponent</th><th>Result</th></tr></thead>
       <tbody>${rows.join("")}</tbody></table>`
    : `<p class="empty">No games yet.</p>`;
}

function teamHeader(t) {
  const band = teamBand(t);
  const style = band ? ` style="--band-bg:${band.bg};--band-fg:${band.fg}${band.accent ? `;--band-accent:${band.accent}` : ""}"` : "";
  const ap = t.sources?.espn_bpi?.ap_rank;
  return `<div class="team-band${band ? "" : " plain-band"}"${style}>
      <div class="band-logo">${logo(t, 64, false)}</div>
      <div class="band-text">
        <h2>${ap ? `<span class="ap-rank">#${fmtInt(ap)}</span> ` : ""}${esc(t.name)}</h2>
        <div class="meta">${esc(t.mascot || "")}${t.mascot ? " · " : ""}${esc(t.conf)} · ${esc(t.record || "")}</div>
        <div class="form" id="band-form" aria-label="Last five games"></div>
      </div>
    </div>`;
}

function sourceTable(t) {
  const rows = [
    ["torvik", (s) => [fmt(s.rating), fmtInt(s.rating_rank), fmt(s.adj_o), fmt(s.adj_d), fmt(s.tempo)]],
    ["haslametrics", (s) => [fmt(s.rating), fmtInt(s.rating_rank), fmt(s.adj_o), fmt(s.adj_d), fmt(s.tempo)]],
    ["espn_bpi", (s) => [fmt(s.rating), fmtInt(s.rating_rank), signed(s.bpi_off, 1), signed(s.bpi_def, 1), "–"]],
    ["teamrankings", (s) => [fmt(s.rating), fmtInt(s.rating_rank), "–", "–", "–"]],
    ["cbbd", (s) => [fmt(s.rating), fmtInt(s.rating_rank), fmt(s.adj_o), fmt(s.adj_d), "–"]],
  ].filter(([k]) => t.sources[k]);
  if (!rows.length) return `<p class="empty">No source data.</p>`;
  return `<table class="plain"><thead><tr><th class="l">Source</th><th>Rating</th><th>Rank</th><th>Off</th><th>Def</th><th>Tempo</th></tr></thead>
    <tbody>${rows.map(([k, f]) => `<tr><td class="l">${SOURCE_LABELS[k]}</td>${f(t.sources[k]).map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</tbody></table>
    <p class="desc" style="margin-top:8px">Ratings: Torvik, Haslametrics and CBBD = efficiency margin; BPI = points vs. average team; TeamRankings = predictive points. ESPN Off/Def are points above average.</p>`;
}

function resumeTable(t) {
  const s = t.sources;
  const net = s.ncaa_net?.net_rank ?? s.warrennolan?.net_rank;
  const lines = [
    ["NET rank", net == null ? "not published yet" : fmtInt(net)],
    ["ESPN strength of record", ordinal(s.espn_bpi?.sor_rank)],
    ["Torvik wins above bubble", s.torvik?.wab == null ? "–" : `${signed(s.torvik.wab, 2)} (${ordinal(s.torvik.wab_rank)})`],
    ["ESPN projected record", s.espn_bpi?.proj_wins == null ? "–" : `${fmt(s.espn_bpi.proj_wins, 1)}–${fmt(s.espn_bpi.proj_losses, 1)}`],
    ["ESPN projected seed", s.espn_bpi?.proj_seed ? fmtInt(s.espn_bpi.proj_seed) : "not published yet"],
    ["ESPN chance to make Final Four", s.espn_bpi?.final4_pct == null ? "not published yet" : `${fmt(s.espn_bpi.final4_pct, 1)}%`],
    ["AP poll", s.espn_bpi?.ap_rank ? `#${fmtInt(s.espn_bpi.ap_rank)} (${fmtInt(s.espn_bpi.ap_points)} pts)` : "unranked"],
    ["Coaches poll", s.espn_bpi?.coaches_rank ? `#${fmtInt(s.espn_bpi.coaches_rank)} (${fmtInt(s.espn_bpi.coaches_points)} pts)` : "unranked"],
    ["Bracket Matrix seed", s.bracketmatrix
      ? `${fmt(s.bracketmatrix.avg_seed, 2)} avg (in ${fmtInt(s.bracketmatrix.brackets)} brackets)`
      : "not in projected field"],
    ["vs. top 25 / 26–50 / 51–100", s.teamrankings ? `${s.teamrankings.vs_top25} / ${s.teamrankings.vs_26_50} / ${s.teamrankings.vs_51_100}` : "–"],
  ];
  const q = t.quads;
  return `<table class="plain"><tbody>${lines.map(([k, v]) => `<tr><td class="l">${k}</td><td>${esc(v)}</td></tr>`).join("")}</tbody></table>
    ${q ? `<table class="plain" style="margin-top:10px"><thead><tr><th class="l">Quadrant</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr></thead>
      <tbody><tr><td class="l">Record</td><td>${esc(q.q1)}</td><td>${esc(q.q2)}</td><td>${esc(q.q3)}</td><td>${esc(q.q4)}</td></tr></tbody></table>` : ""}`;
}

/* ---------- source agreement dot plot ---------- */

function drawAgreement(el, t) {
  const groups = [
    { name: "Predictive", color: "var(--series-1)", z: t.z.predictive, composite: t.pred.z },
    { name: "Resume", color: "var(--series-2)", z: t.z.resume, composite: t.res.z },
  ].map((g) => ({ ...g, rows: Object.entries(g.z).filter(([, v]) => v != null) }))
   .filter((g) => g.rows.length);
  if (!groups.length) { el.innerHTML = `<p class="empty">No ratings.</p>`; return; }

  const all = groups.flatMap((g) => g.rows.map(([, v]) => v).concat(g.composite ?? []));
  const lo = Math.min(-3, Math.floor(Math.min(...all))), hi = Math.max(3, Math.ceil(Math.max(...all)));
  const W = Math.max(280, el.clientWidth || 520), labelW = W < 400 ? 92 : 110;
  const right = 16, rowH = 24, headH = 20, axisH = 26;
  const height = groups.reduce((h, g) => h + headH + g.rows.length * rowH + 6, 0) + axisH;
  const x = (v) => labelW + ((v - lo) / (hi - lo)) * (W - labelW - right);

  let y = 0, svg = "";
  for (let v = lo; v <= hi; v++) {
    svg += `<line class="gridline" x1="${x(v)}" x2="${x(v)}" y1="0" y2="${height - axisH}" ${v === 0 ? 'style="stroke:var(--border)"' : ""}/>`;
    svg += `<text x="${x(v)}" y="${height - 8}" text-anchor="middle">${v > 0 ? "+" + v : v}</text>`;
  }
  for (const g of groups) {
    svg += `<text x="0" y="${y + 14}" style="font-weight:600;fill:var(--text-primary)">${g.name}</text>`;
    const top = y + headH;
    const bottom = top + g.rows.length * rowH;
    if (g.composite != null) {
      svg += `<line x1="${x(g.composite)}" x2="${x(g.composite)}" y1="${top - 2}" y2="${bottom - 4}" stroke="${g.color}" stroke-width="2" stroke-dasharray="3 3"/>`;
    }
    g.rows.forEach(([key, v], i) => {
      const cy = top + i * rowH + rowH / 2 - 2;
      const label = INPUT_LABELS[key] || key;
      svg += `<text x="0" y="${cy + 4}">${esc(label)}</text>`;
      svg += `<line x1="${x(Math.min(0, v))}" x2="${x(Math.max(0, v))}" y1="${cy}" y2="${cy}" stroke="${g.color}" stroke-opacity="0.35" stroke-width="2"/>`;
      svg += `<circle cx="${x(v)}" cy="${cy}" r="5.5" fill="${g.color}" stroke="var(--surface-1)" stroke-width="2"/>`;
      svg += `<rect class="hit" x="${labelW}" y="${cy - rowH / 2}" width="${W - labelW}" height="${rowH}" fill="transparent"
        data-tip="${esc(`<b>${label}</b><br>z ${fmt(v, 2)}${sourceDetail(t, key)}`)}"/>`;
    });
    y = bottom + 6;
  }
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${height}" role="img"
    aria-label="Source z-scores for ${esc(t.name)}">${svg}</svg>`;
  el.querySelectorAll("[data-tip]").forEach((r) => {
    r.addEventListener("pointerenter", (e) => tip.show(e, r.dataset.tip));
    r.addEventListener("pointermove", (e) => tip.move(e));
    r.addEventListener("pointerleave", () => tip.hide());
  });
}

function sourceDetail(t, key) {
  const [srcs, metric] = key.split(":");
  for (const s of srcs.split("/")) {
    const block = t.sources[s];
    if (block && block[metric] != null) {
      const rank = block[`${metric}_rank`];
      const value = metric.endsWith("_rank") ? ordinal(block[metric]) : fmt(block[metric], 2);
      return `<br>${esc(SOURCE_LABELS[s] || s)}: ${value}${rank ? ` (${ordinal(rank)})` : ""}`;
    }
  }
  return "";
}

/* ---------- history / trend ---------- */

async function loadTeamHistory(id) {
  state.historyIndex ||= await getJSON("data/history/index.json");
  const dates = state.historyIndex.filter((d) => /^\d{4}-\d{2}-\d{2}$/.test(d)).slice(-150);
  await Promise.all(dates.filter((d) => !state.history.has(d)).map(async (d) => {
    try { state.history.set(d, await getJSON(`data/history/${d}.json`)); } catch (e) { /* skip a bad day */ }
  }));
  return dates.filter((d) => state.history.get(d)?.teams?.[id]).map((d) => {
    const snap = state.history.get(d);
    const row = snap.teams[id];
    const rec = Object.fromEntries(snap.fields.map((f, i) => [f, row[i]]));
    return { date: d, pred: rec.pred_rank, res: rec.res_rank };
  });
}

function drawTrend(el, series) {
  if (series.length < 2) {
    el.innerHTML = `<p class="empty">The trend line appears once a few days of history have built up${
      series.length ? ` (first snapshot: ${series[0].date})` : ""}.</p>`;
    return;
  }
  const W = Math.max(280, el.clientWidth || 520), H = 220, L = 34, R = 64, T = 10, B = 26;
  const ranks = series.flatMap((p) => [p.pred, p.res]).filter((v) => v != null);
  const maxRank = Math.max(10, Math.ceil(Math.max(...ranks) / 10) * 10);
  const t0 = Date.parse(series[0].date), t1 = Date.parse(series.at(-1).date);
  const x = (d) => L + ((Date.parse(d) - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (r) => T + ((r - 1) / (maxRank - 1)) * (H - T - B);
  const lines = [
    { key: "pred", name: "Predictive", color: "var(--series-1)" },
    { key: "res", name: "Resume", color: "var(--series-2)" },
  ];
  let svg = "";
  const ticks = niceTicks(1, maxRank, 5);
  for (const r of ticks) {
    svg += `<line class="gridline" x1="${L}" x2="${W - R}" y1="${y(r)}" y2="${y(r)}"/>`;
    svg += `<text x="${L - 6}" y="${y(r) + 4}" text-anchor="end">${r}</text>`;
  }
  const fmtDate = (d) => new Date(d + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric" });
  const xTicks = [series[0], series[Math.floor(series.length / 2)], series.at(-1)];
  for (const p of new Set(xTicks)) svg += `<text x="${x(p.date)}" y="${H - 6}" text-anchor="middle">${fmtDate(p.date)}</text>`;
  for (const ln of lines) {
    const pts = series.filter((p) => p[ln.key] != null);
    if (!pts.length) continue;
    svg += `<polyline fill="none" stroke="${ln.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"
      points="${pts.map((p) => `${x(p.date)},${y(p[ln.key])}`).join(" ")}"/>`;
    const last = pts.at(-1);
    svg += `<circle cx="${x(last.date)}" cy="${y(last[ln.key])}" r="4" fill="${ln.color}" stroke="var(--surface-1)" stroke-width="2"/>`;
    svg += `<text x="${x(last.date) + 8}" y="${y(last[ln.key]) + 4}" style="fill:var(--text-primary)">${ln.name.slice(0, 4)}. ${last[ln.key]}</text>`;
  }
  svg += `<line id="xh" class="axis" y1="${T}" y2="${H - B}" style="display:none"/>`;
  svg += `<rect id="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent"/>`;
  el.innerHTML = `<div class="chart-legend">${lines.map((l) =>
      `<span><span class="key" style="background:${l.color}"></span>${l.name}</span>`).join("")}</div>
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rank history">${svg}</svg>`;
  const svgEl = el.querySelector("svg"), xh = el.querySelector("#xh");
  el.querySelector("#hit").addEventListener("pointermove", (e) => {
    const box = svgEl.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    const p = series.reduce((best, q) => Math.abs(x(q.date) - px) < Math.abs(x(best.date) - px) ? q : best);
    xh.setAttribute("x1", x(p.date)); xh.setAttribute("x2", x(p.date)); xh.style.display = "";
    tip.show(e, `<b>${fmtDate(p.date)}</b><br>Predictive ${p.pred ?? "–"}<br>Resume ${p.res ?? "–"}`);
  });
  el.querySelector("#hit").addEventListener("pointerleave", () => { xh.style.display = "none"; tip.hide(); });
}

function niceTicks(lo, hi, count) {
  const step = [1, 2, 5, 10, 20, 25, 50, 100].find((s) => (hi - lo) / s <= count) || 100;
  const out = [1];
  for (let v = step; v <= hi; v += step) out.push(v);
  return out;
}


/* ================= Phase B views ================= */

const goTeam = (id) => { location.hash = `#/team/${id}`; };
const stat = (t, k) => t.stats?.[k]?.value;
const median = (xs) => { const s = xs.slice().sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;

/** Nearest-point hover for SVG charts: points = [{x, y, t}], in viewBox units. */
function attachNearest(svg, points, W, onHover, onLeave, radius = 18) {
  const hit = (e) => {
    const box = svg.getBoundingClientRect();
    const scale = W / box.width;
    const px = (e.clientX - box.left) * scale, py = (e.clientY - box.top) * scale;
    let best = null, bestD = (radius * scale) ** 2;
    for (const p of points) {
      const d = (p.x - px) ** 2 + (p.y - py) ** 2;
      if (d < bestD) { bestD = d; best = p; }
    }
    return best;
  };
  svg.addEventListener("pointermove", (e) => { const p = hit(e); svg.style.cursor = p ? "pointer" : ""; p ? onHover(e, p) : onLeave(); });
  svg.addEventListener("pointerleave", onLeave);
  svg.addEventListener("click", (e) => { const p = hit(e); if (p) goTeam(p.t.id); });
}

const teamTip = (t, extra = "") => `<b>${esc(t.name)}</b> <span style="opacity:.7">${esc(t.conf)} · ${esc(t.record || "")}</span><br>
  Predictive ${fmtInt(t.pred.rank)} · Resume ${fmtInt(t.res.rank)}<br>
  AdjO ${fmt(stat(t, "adj_o"))} (${ordinal(t.stats.adj_o?.rank)}) · AdjD ${fmt(stat(t, "adj_d"))} (${ordinal(t.stats.adj_d?.rank)})${extra}`;

/* ---------- offense vs defense scatter ---------- */

const scatterUi = { highlight: "top25" };

function renderScatter() {
  const confs = [...new Set(state.latest.teams.map((t) => t.conf))].sort();
  $("#app").innerHTML = `
    <div class="view-head">
      <h2 class="view-title">Offense vs Defense</h2>
      <div class="help-row">${helpLink(HELP.scatter, "How to read this chart")}</div>
      <p class="desc">Every D1 team by adjusted offense (across) and adjusted defense (up = fewer points allowed).
      Up and to the right is better at both ends. Dashed diagonals are equal efficiency margin (EM = offense − defense). Hover a team for details; click or tap to open it.</p>
      <div class="controls">
        <label class="check">Highlight
          <select id="hl" aria-label="Highlight teams">
            <option value="top25">Top 25 (Predictive)</option>
            <option value="top50">Top 50 (Predictive)</option>
            ${confs.map((c) => `<option value="conf:${esc(c)}">${esc(c)}</option>`).join("")}
          </select></label>
      </div>
    </div>
    <section class="card"><div id="scatter"></div></section>`;
  $("#hl").value = scatterUi.highlight;
  $("#hl").addEventListener("change", (e) => { scatterUi.highlight = e.target.value; drawScatter($("#scatter")); });
  drawScatter($("#scatter"));
  redrawCharts = () => $("#scatter") && drawScatter($("#scatter"));
}

function drawScatter(el) {
  const teams = state.latest.teams.filter((t) => stat(t, "adj_o") != null && stat(t, "adj_d") != null);
  const W = Math.max(320, el.clientWidth || 900);
  const H = Math.round(Math.min(640, Math.max(380, W * 0.62)));
  const M = { l: 46, r: 16, t: 14, b: 40 };
  const xs = teams.map((t) => stat(t, "adj_o")), ys = teams.map((t) => stat(t, "adj_d"));
  const pad = 2;
  const x0 = Math.floor(Math.min(...xs) - pad), x1 = Math.ceil(Math.max(...xs) + pad);
  const y0 = Math.floor(Math.min(...ys) - pad), y1 = Math.ceil(Math.max(...ys) + pad);
  const x = (v) => M.l + ((v - x0) / (x1 - x0)) * (W - M.l - M.r);
  const y = (v) => M.t + ((v - y0) / (y1 - y0)) * (H - M.t - M.b); // low AdjD (good) at top
  const hl = scatterUi.highlight;
  const isHl = (t) => hl === "top25" ? t.pred.rank <= 25 : hl === "top50" ? t.pred.rank <= 50 : t.conf === hl.slice(5);

  let svg = `<defs><clipPath id="plot"><rect x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}"/></clipPath></defs>`;
  const step = (x1 - x0) > 40 ? 10 : 5;
  for (let v = Math.ceil(x0 / step) * step; v <= x1; v += step) {
    svg += `<line class="gridline" x1="${x(v)}" x2="${x(v)}" y1="${M.t}" y2="${H - M.b}"/><text x="${x(v)}" y="${H - M.b + 16}" text-anchor="middle">${v}</text>`;
  }
  for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step) {
    svg += `<line class="gridline" x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  }
  svg += `<text x="${(M.l + W - M.r) / 2}" y="${H - 6}" text-anchor="middle" class="axis-label">Adjusted offense (points per 100 possessions) →</text>`;
  svg += `<text transform="translate(12 ${(M.t + H - M.b) / 2}) rotate(-90)" text-anchor="middle" class="axis-label">← Adjusted defense (points allowed per 100)</text>`;
  // equal-margin diagonals: AdjEM = O - D
  svg += `<g clip-path="url(#plot)">`;
  for (const k of [-20, -10, 0, 10, 20, 30, 40]) {
    svg += `<line class="iso" x1="${x(x0)}" y1="${y(x0 - k)}" x2="${x(x1)}" y2="${y(x1 - k)}"/>`;
    const lx = Math.min(x1, y1 + k) - 0.6, ly = lx - k;
    if (W >= 640 && lx > x0 + 2 && ly > y0 + 1 && ly < y1 - 1) {
      svg += `<text class="iso-label" x="${x(lx)}" y="${y(ly) - 4}" text-anchor="end">EM ${k > 0 ? "+" : ""}${k}</text>`;
    }
  }
  // D1 averages split the plot into quadrants
  const mo = mean(xs), md = mean(ys);
  svg += `<line class="avg" x1="${x(mo)}" x2="${x(mo)}" y1="${M.t}" y2="${H - M.b}"/><line class="avg" x1="${M.l}" x2="${W - M.r}" y1="${y(md)}" y2="${y(md)}"/>`;
  svg += `</g>`;
  const q = (tx, ty, anchor, label) => `<text class="quad" x="${tx}" y="${ty}" text-anchor="${anchor}">${label}</text>`;
  svg += q(W - M.r - 6, M.t + 14, "end", "Strong both ends") + q(M.l + 6, M.t + 14, "start", "Defense-first")
       + q(W - M.r - 6, H - M.b - 8, "end", "Offense-first") + q(M.l + 6, H - M.b - 8, "start", "Below average");

  const pts = teams.map((t) => ({ t, x: x(stat(t, "adj_o")), y: y(stat(t, "adj_d")), hl: isHl(t) }));
  svg += pts.filter((p) => !p.hl).map((p) => `<circle class="dot" cx="${p.x}" cy="${p.y}" r="3.5"/>`).join("");
  const size = W < 520 ? 18 : 24;
  svg += pts.filter((p) => p.hl).sort((a, b) => b.t.pred.rank - a.t.pred.rank).map((p) => p.t.espn_id
    ? `<circle class="logo-ring" cx="${p.x}" cy="${p.y}" r="${size / 2 + 3}"/><image href="${logoUrl(p.t, size, false)}" x="${p.x - size / 2}" y="${p.y - size / 2}" width="${size}" height="${size}"/>`
    : `<circle class="dot hl" cx="${p.x}" cy="${p.y}" r="5"/>`).join("");
  el.innerHTML = `<svg class="chart scatter" viewBox="0 0 ${W} ${H}" role="img" aria-label="Scatter plot of adjusted offense versus adjusted defense for all D1 teams">${svg}</svg>
    <p class="desc" style="margin-top:6px">${pts.filter((p) => p.hl).length} highlighted · ${teams.length} teams · values averaged across sources.</p>`;
  const svgEl = el.querySelector("svg");
  // highlighted teams win ties in hit-testing by being listed first
  const order = pts.filter((p) => p.hl).concat(pts.filter((p) => !p.hl));
  attachNearest(svgEl, order, W, (e, p) => tip.show(e, teamTip(p.t)), () => tip.hide());
}

/* ---------- conferences ---------- */

function projectedField() {
  const bm = state.latest.teams.map((t) => t.sources.bracketmatrix).filter(Boolean);
  const maxB = bm.length ? Math.max(...bm.map((b) => b.brackets || 0)) : 0;
  return { maxB, inField: (t) => !!t.sources.bracketmatrix?.consensus_seed };
}

function renderConferences() {
  const { maxB, inField } = projectedField();
  const groups = {};
  for (const t of state.latest.teams) (groups[t.conf] ||= []).push(t);
  const confs = Object.entries(groups).map(([name, ts]) => {
    const em = ts.map((t) => stat(t, "adj_em")).filter((v) => v != null);
    return { name, teams: ts.sort((a, b) => a.pred.rank - b.pred.rank), avg: mean(em), med: median(em),
      bids: ts.filter(inField).length, best: ts[0] };
  }).sort((a, b) => b.avg - a.avg);
  const all = state.latest.teams.map((t) => stat(t, "adj_em")).filter((v) => v != null);
  const lo = Math.floor(Math.min(...all) / 5) * 5, hi = Math.ceil(Math.max(...all) / 5) * 5;

  $("#app").innerHTML = `
    <div class="view-head">
      <h2 class="view-title">Conferences</h2>
      <div class="help-row">${helpLink(HELP.conferences, "How to read this page")}</div>
      <p class="desc">Conferences ranked by their teams' average adjusted efficiency margin (AdjEM). Each dot is a team, placed on the same scale for every conference;
      the line marks the conference average. "Field" counts teams on a consensus seed line in the Bracket Matrix${maxB ? ` (${maxB} brackets)` : ""}. Hover a dot for the team; click or tap to open it.
      <span style="white-space:nowrap"><span class="legend-dot" style="background:var(--series-1)"></span>in projected field<span class="legend-dot" style="background:var(--neutral)"></span>other</span></p>
    </div>
    <section class="card conf-card">
      <div class="conf-row conf-header"><span>#</span><span>Conference</span><span class="num">Avg AdjEM</span><span class="num">Field</span><span class="strip-head" id="strip-axis"></span></div>
      ${confs.map((c, i) => `<div class="conf-row" data-conf="${esc(c.name)}">
        <span class="rk">${i + 1}</span>
        <span class="conf-name"><b>${esc(c.name)}</b><span class="sub">${c.teams.length} teams · best: ${esc(c.best.short)} (${fmtInt(c.best.pred.rank)})</span></span>
        <span class="num">${signed(c.avg, 1)}</span>
        <span class="num">${c.bids || "–"}</span>
        <span class="strip"></span></div>`).join("")}
    </section>`;
  const draw = () => {
    const strips = [...document.querySelectorAll(".conf-row .strip")];
    if (!strips.length) return;
    const W = Math.max(220, strips[0].clientWidth || 400), H = 26, pad = 8;
    const x = (v) => pad + ((v - lo) / (hi - lo)) * (W - 2 * pad);
    const ticks = []; for (let v = lo; v <= hi; v += 10) ticks.push(v);
    $("#strip-axis").innerHTML = `<svg class="chart" viewBox="0 0 ${W} 18">${ticks.map((v) =>
      `<text x="${x(v)}" y="13" text-anchor="middle">${v > 0 ? "+" : ""}${v}</text>`).join("")}</svg>`;
    strips.forEach((el, i) => {
      const c = confs[i];
      const pts = c.teams.filter((t) => stat(t, "adj_em") != null).map((t) => ({ t, x: x(stat(t, "adj_em")), y: H / 2 }));
      el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}">
        ${ticks.map((v) => `<line class="gridline" x1="${x(v)}" x2="${x(v)}" y1="2" y2="${H - 2}"${v === 0 ? ' style="stroke:var(--border)"' : ""}/>`).join("")}
        <line class="conf-avg" x1="${x(c.avg)}" x2="${x(c.avg)}" y1="3" y2="${H - 3}"/>
        ${pts.map((p) => `<circle class="conf-dot${inField(p.t) ? " in-field" : ""}" cx="${p.x}" cy="${p.y}" r="5"/>`).join("")}
      </svg>`;
      attachNearest(el.querySelector("svg"), pts, W, (e, p) => tip.show(e, teamTip(p.t,
        inField(p.t) ? `<br>Projected ${fmtInt(p.t.sources.bracketmatrix.consensus_seed)} seed` : "")), () => tip.hide(), 10);
    });
  };
  draw();
  redrawCharts = draw;
}

/* ---------- bracket (seed lines) ---------- */

function renderBracket() {
  const { maxB } = projectedField();
  const withBm = state.latest.teams.filter((t) => t.sources.bracketmatrix);
  if (!withBm.length) { $("#app").innerHTML = `<p class="empty">No Bracket Matrix data yet.</p>`; return; }
  const lines = {};
  for (const t of withBm) {
    const s = t.sources.bracketmatrix.consensus_seed;
    if (s) (lines[s] ||= []).push(t);
  }
  const bubble = withBm.filter((t) => !t.sources.bracketmatrix.consensus_seed)
    .sort((a, b) => b.sources.bracketmatrix.brackets - a.sources.bracketmatrix.brackets).slice(0, 12);
  const chip = (t) => {
    const b = t.sources.bracketmatrix;
    return `<a class="seed-chip" href="#/team/${t.id}" title="${esc(t.name)}: average seed ${fmt(b.avg_seed, 2)} in ${fmtInt(b.brackets)} of ${maxB} brackets">
      ${logo(t, 26)}<span class="chip-text"><b>${esc(t.short)}</b><span class="sub">${fmt(b.avg_seed, 2)} · ${fmtInt(b.brackets)}/${maxB} · Pred ${fmtInt(t.pred.rank)}</span></span></a>`;
  };
  $("#app").innerHTML = `
    <div class="view-head">
      <h2 class="view-title">Bracket</h2>
      <div class="help-row">${helpLink(HELP.bracket, "How to read this page")}</div>
      <p class="desc">Projected NCAA tournament field from the Bracket Matrix: the consensus of ${maxB} published brackets.
      Each team shows its average projected seed, how many brackets include it, and its Predictive rank here. Lines with more than four teams include play-in (First Four) spots.</p>
    </div>
    <section class="card seed-lines">
      ${Array.from({ length: 16 }, (_, i) => i + 1).map((s) => `<div class="seed-line">
        <div class="seed-num">${s}</div>
        <div class="seed-teams">${(lines[s] || []).sort((a, b) => a.sources.bracketmatrix.avg_seed - b.sources.bracketmatrix.avg_seed).map(chip).join("")}</div>
      </div>`).join("")}
    </section>
    <section class="card">
      <h3>Bubble</h3>
      <p class="desc">In some brackets but not on a consensus seed line, most-included first.</p>
      <div class="seed-teams">${bubble.map(chip).join("") || '<span class="muted">None</span>'}</div>
    </section>`;
}


/* ================= players ================= */

async function loadPlayers() {
  state.players ||= await getJSON("data/players.json");
  return state.players;
}

const yrHt = (p) => [p.role || p.pos, p.yr, p.ht].filter(Boolean).join(" · ");
const playerHref = (p) => `#/player/${p.team_id}/${p.id}`;

/** Shade by rank among eligible players (top half shaded, like the team table). */
function heatStyleN(rank, n) {
  if (rank == null || !n) return "";
  const strength = Math.max(0, 1 - (rank - 1) / (n / 2));
  return strength > 0 ? ` style="--h: color-mix(in oklab, var(--heat) calc(var(--heat-max) * ${strength.toFixed(3)}), transparent)"` : "";
}

const PLAYER_COLS = [
  { key: "rank", label: "#", title: "Rank by the composite Score among eligible D1 players", get: (p) => p.rank, cls: "rk sticky", cell: (p) => fmtInt(p.rank) },
  { key: "name", label: "Player", title: "Name, team and class. Click for the player page", get: (p) => p.name, dir: 1, cls: "l sticky2 team-cell",
    cell: (p) => { const t = state.byId.get(p.team_id);
      return `<a class="team-link" href="${playerHref(p)}">${t ? logo(t, 22) : ""}<span class="tname">${esc(p.name)}</span></a>
        <span class="conf">${esc(t ? t.short : "")}${p.yr ? ` · ${esc(p.yr)}` : ""}</span>`; } },
  { key: "role", label: "Role", title: "Torvik's role label (e.g. Pure PG, Wing F, Stretch 4); basic position if no match", get: (p) => p.role || p.pos, dir: 1, cls: "l muted", cell: (p) => esc(p.role || p.pos || "–") },
  { key: "min_pct", label: "Min%", title: "Share of the team's minutes played (eligibility needs 40%+)", get: (p) => p.min_pct, dir: -1, cell: (p) => fmt(p.min_pct, 1) },
  { key: "pts", label: "PTS", title: "Points per game", get: (p) => p.pts, dir: -1, cell: (p) => fmt(p.pts, 1) },
  { key: "reb", label: "REB", title: "Rebounds per game", get: (p) => p.reb, dir: -1, cell: (p) => fmt(p.reb, 1) },
  { key: "ast", label: "AST", title: "Assists per game", get: (p) => p.ast, dir: -1, cell: (p) => fmt(p.ast, 1) },
  { key: "ts", label: "TS%", title: "True shooting %: efficiency counting threes and free throws (~55% average, 65%+ elite)", get: (p) => p.ts, dir: -1, cell: (p) => fmt(p.ts, 1) },
  { key: "usage", label: "USG", title: "Usage %: share of team possessions the player finishes while on the floor (~20% average)", get: (p) => p.usage, dir: -1, cell: (p) => fmt(p.usage, 1) },
  { key: "ws40", label: "WS/40", get: (p) => p.metrics.ws40.value, dir: -1, metric: "ws40", cell: (p) => fmt(p.metrics.ws40.value, 3) },
  { key: "porpag", label: "PORPAG", get: (p) => p.metrics.porpag.value, dir: -1, metric: "porpag", cell: (p) => fmt(p.metrics.porpag.value, 1) },
  { key: "bpm", label: "BPM", get: (p) => p.metrics.bpm.value, dir: -1, metric: "bpm", cell: (p) => signed(p.metrics.bpm.value, 1) },
  { key: "score", label: "Score", title: "Composite: average z-score of WS/40, PORPAG and BPM (0 = average eligible player)", get: (p) => p.score, dir: -1, cell: (p) => `<b>${fmt(p.score, 2)}</b>` },
];
const playersUi = { sort: "rank", dir: 1 };

async function renderPlayers() {
  $("#app").innerHTML = `<p class="empty">Loading players…</p>`;
  let doc;
  try { doc = await loadPlayers(); } catch (e) {
    $("#app").innerHTML = `<p class="empty">Player ratings aren't available yet.</p>`; return;
  }
  if (!location.hash.startsWith("#/players")) return;
  const tv = doc.sources?.torvik || "";
  const note = tv === "ok" ? "" : tv.startsWith("stale")
    ? ` Box plus/minus is from Torvik's last good file (${esc(tv.replace(/^stale \(|\)$/g, ""))}).`
    : " Torvik is unavailable today, so box plus/minus is left out.";
  $("#app").innerHTML = `
    <div class="view-head">
      <h2 class="view-title">Top 50 Players</h2>
      <div class="help-row">${helpLink(HELP.players, "How players are rated")}</div>
      <p class="desc">Our own composite player rating: <b>win shares per 40</b>, <b>PORPAG</b> (points over replacement per game) and
      <b>box plus/minus</b>, each turned into a z-score among the ${fmtInt(doc.eligible)} D1 players with at least
      ${Math.round(doc.min_share * 100)}% of their team's minutes, then averaged. Early-season numbers move a lot.${note}
      Click a player for the breakdown.</p>
    </div>
    <div class="table-wrap"><table class="rank players-table">
      <thead><tr>${PLAYER_COLS.map((c) => `<th scope="col" data-key="${c.key}" class="${c.cls?.includes("l") ? "l " : ""}${c.cls?.includes("sticky2") ? "sticky2" : c.cls?.includes("sticky") ? "sticky" : ""}"
        title="${esc(c.metric ? doc.metrics.find((m) => m.key === c.metric)?.desc || "" : c.title || "")}">${esc(c.label)}</th>`).join("")}</tr></thead>
      <tbody id="ptbody"></tbody></table></div>
    <p class="legend-note">Shading marks how high each metric ranks among eligible players. Sources: CollegeBasketballData (box stats, win shares, PORPAG) and BartTorvik (box plus/minus, class, height, role).</p>`;
  const draw = () => {
    const col = PLAYER_COLS.find((c) => c.key === playersUi.sort);
    const rows = doc.top.slice().sort((a, b) => {
      const va = col.get(a), vb = col.get(b);
      if (va == null) return 1; if (vb == null) return -1;
      return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * playersUi.dir || a.rank - b.rank;
    });
    $("#ptbody").innerHTML = rows.map((p) => `<tr class="team-row">${PLAYER_COLS.map((c) => {
      const style = c.metric ? heatStyleN(p.metrics[c.metric].rank, doc.eligible) : "";
      return `<td class="${c.cls || ""}${style ? " heat" : ""}"${style}>${c.cell(p)}</td>`;
    }).join("")}</tr>`).join("");
    document.querySelectorAll(".players-table thead th").forEach((th) => th.setAttribute("aria-sort",
      th.dataset.key === playersUi.sort ? (playersUi.dir === 1 ? "ascending" : "descending") : "none"));
  };
  document.querySelectorAll(".players-table thead th").forEach((th) => th.addEventListener("click", () => {
    const c = PLAYER_COLS.find((x) => x.key === th.dataset.key);
    if (playersUi.sort === c.key) playersUi.dir = -playersUi.dir; else { playersUi.sort = c.key; playersUi.dir = c.dir || 1; }
    draw();
  }));
  draw();
}

function renderRoster(d) {
  const el = $("#roster");
  if (!el) return;
  const roster = d.players || [];
  if (!roster.length) { el.innerHTML = `<p class="empty">No player data.</p>`; return; }
  el.innerHTML = `<table class="plain"><thead><tr><th class="l">Player</th><th class="l">Role</th><th>Min%</th><th>PTS</th><th>REB</th><th>AST</th><th>Rank</th></tr></thead>
    <tbody>${roster.map((p) => `<tr${p.eligible ? "" : ' class="muted"'}>
      <td class="l"><a href="${playerHref(p)}">${esc(p.name)}</a>${p.num ? `<span class="sub">#${esc(p.num)}</span>` : ""}</td>
      <td class="l">${esc([p.role || p.pos, p.yr].filter(Boolean).join(" · ") || "–")}</td>
      <td>${fmt(p.min_pct, 1)}</td><td>${fmt(p.pts, 1)}</td><td>${fmt(p.reb, 1)}</td><td>${fmt(p.ast, 1)}</td>
      <td>${p.rank ? fmtInt(p.rank) : '<span title="Below 40% of team minutes">–</span>'}</td></tr>`).join("")}</tbody></table>`;
}

async function renderPlayer(teamId, playerId) {
  const t = state.byId.get(teamId);
  $("#app").innerHTML = `<p class="empty">Loading player…</p>`;
  let d, doc;
  try { [d, doc] = await Promise.all([loadTeamDetail(teamId), loadPlayers().catch(() => null)]); } catch (e) { d = null; }
  const p = d?.players?.find((x) => x.id === playerId);
  if (!t || !p) { $("#app").innerHTML = `<a class="back" href="#/players">← Top 50 players</a><p class="empty">Player not found.</p>`; return; }
  document.title = `${p.name} · D1 Composite Rankings`;
  const band = teamBand(t);
  const style = band ? ` style="--band-bg:${band.bg};--band-fg:${band.fg}${band.accent ? `;--band-accent:${band.accent}` : ""}"` : "";
  const n = doc?.eligible;
  const metrics = doc?.metrics || Object.keys(p.metrics).map((k) => ({ key: k, label: k, desc: "", source: "" }));
  const tile = (label, value, note) => `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div><div class="note">${note}</div></div>`;
  $("#app").innerHTML = `
    <div class="nav-row"><a class="back" href="#/team/${t.id}">← ${esc(t.name)}</a>${helpLink(HELP.players, "How players are rated")}</div>
    <div class="team-band${band ? "" : " plain-band"}"${style}>
      <div class="band-logo">${logo(t, 64, false)}</div>
      <div class="band-text">
        <h2>${p.num ? `<span class="ap-rank">#${esc(p.num)}</span> ` : ""}${esc(p.name)}</h2>
        <div class="meta">${esc(yrHt(p) || "")}${yrHt(p) ? " · " : ""}<a class="band-link" href="#/team/${t.id}">${esc(t.name)}</a> · ${esc(t.conf)}</div>
      </div>
    </div>
    <div class="tiles">
      ${tile("Player rank", p.rank ? ordinal(p.rank) : "–", p.rank && n ? `of ${fmtInt(n)} eligible` : "below 40% of team minutes")}
      ${tile("Score", fmt(p.score, 2), p.score != null ? `z-score · ${p.n_metrics} metrics` : "not rated")}
      ${tile("Minutes", `${fmt(p.min_pct, 0)}%`, `${fmt(p.mpg, 1)} per game · ${fmtInt(p.games)} games`)}
      ${tile("Points", fmt(p.pts, 1), "per game")}
      ${tile("Rebounds", fmt(p.reb, 1), "per game")}
      ${tile("Assists", fmt(p.ast, 1), "per game")}
      ${tile("True shooting", `${fmt(p.ts, 1)}%`, `usage ${fmt(p.usage, 1)}%`)}
      ${tile("Off / Def rating", `${fmt(p.ortg, 0)} / ${fmt(p.drtg, 0)}`, "points per 100 possessions")}
    </div>
    <div class="grid2">
      <section class="card">
        <h3>Metrics behind the score</h3>
        <p class="desc">Each metric as a value, its rank among eligible D1 players, and its z-score (0 = average eligible player). The score is the average of the z-scores.</p>
        <div class="plain-wrap"><table class="plain wrap-first">
          <thead><tr><th class="l">Metric</th><th>Value</th><th>Rank</th><th>z</th><th class="l">Source</th></tr></thead>
          <tbody>${metrics.map((m) => { const v = p.metrics[m.key] || {};
            return `<tr title="${esc(m.desc)}"><td class="l">${esc(m.label)}<div class="sub" style="margin-left:0">${esc(m.desc)}</div></td>
              <td>${v.value == null ? "–" : m.key === "bpm" ? signed(v.value, 1) : fmt(v.value, m.key === "ws40" ? 3 : 1)}</td>
              <td>${v.rank ? fmtInt(v.rank) : "–"}</td><td>${v.z == null ? "–" : signed(v.z, 2)}</td><td class="l">${esc(m.source)}</td></tr>`; }).join("")}
          </tbody></table></div>
        ${p.obpm != null ? `<p class="desc" style="margin-top:8px">Box plus/minus split: offense ${signed(p.obpm, 1)}, defense ${signed(p.dbpm, 1)}.</p>` : ""}
      </section>
      <section class="card">
        <h3>Per game & shooting</h3>
        <p class="desc">Season to date.</p>
        <div class="plain-wrap"><table class="plain"><tbody>
          ${[["Minutes", fmt(p.mpg, 1)], ["Points", fmt(p.pts, 1)], ["Rebounds", fmt(p.reb, 1)], ["Assists", fmt(p.ast, 1)],
             ["Steals", fmt(p.stl, 1)], ["Blocks", fmt(p.blk, 1)], ["Turnovers", fmt(p.tov, 1)],
             ["Effective FG %", `${fmt(p.efg, 1)}%`], ["3-point %", `${fmt(p.fg3, 1)}% (${fmt(p.fg3a, 1)} att.)`],
             ["Free throw %", `${fmt(p.ft, 1)}%`], ["Win shares (total)", fmt(p.ws, 2)], ["Starts", fmtInt(p.starts)]]
            .map(([k, v]) => `<tr><td class="l">${k}</td><td>${v}</td></tr>`).join("")}
        </tbody></table></div>
      </section>
    </div>`;
}

/* ================= routing ================= */

function route() {
  tip.hide();
  redrawCharts = null;
  const m = /^#\/team\/([a-z0-9-]+)/.exec(location.hash);
  const pm = /^#\/player\/([a-z0-9-]+)\/(\w+)/.exec(location.hash);
  const view = m ? "team" : pm ? "player" : (/^#\/(charts|conferences|bracket|players)/.exec(location.hash)?.[1] || "rankings");
  document.querySelectorAll("#tabs a").forEach((a) => {
    a.toggleAttribute("aria-current", a.dataset.view === view || (view === "team" && a.dataset.view === "rankings")
      || (view === "player" && a.dataset.view === "players"));
  });
  const titles = { charts: "Offense vs Defense", conferences: "Conferences", bracket: "Bracket", players: "Top 50 Players" };
  document.title = titles[view] ? `${titles[view]} · D1 Composite Rankings` : "D1 Composite Rankings";
  if (view === "team") renderTeam(m[1]);
  else if (view === "charts") renderScatter();
  else if (view === "conferences") renderConferences();
  else if (view === "bracket") renderBracket();
  else if (view === "players") renderPlayers();
  else if (view === "player") renderPlayer(pm[1], pm[2]);
  else renderRankings();
  window.scrollTo(0, 0);
}

async function init() {
  initTheme();
  try {
    [state.latest, state.meta] = await Promise.all([getJSON("data/latest.json"), getJSON("data/meta.json")]);
  } catch (e) {
    $("#app").innerHTML = `<p class="empty">Could not load rankings data (${esc(e.message)}).</p>`;
    $("#updated").textContent = "";
    return;
  }
  state.latest.teams.forEach((t) => state.byId.set(t.id, t));
  renderHeader();
  window.addEventListener("hashchange", route);
  route();
}

init();
