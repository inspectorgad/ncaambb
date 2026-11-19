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
  team: `${GUIDE_URL}#team-page`,
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
function logo(t, size, onDark = isDark()) {
  if (!t?.espn_id) return "";
  const variant = onDark ? "500-dark" : "500";
  const px = size * 2; // crisp on high-density screens
  const src = `https://a.espncdn.com/combiner/i?img=/i/teamlogos/ncaa/${variant}/${t.espn_id}.png&h=${px}&w=${px}`;
  return `<img class="logo" src="${src}" width="${size}" height="${size}" alt="" loading="lazy" decoding="async"
    onerror="this.style.visibility='hidden'">`;
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
      ${tile("Predictive", ordinal(t.pred.rank), `z ${fmt(t.pred.z, 2)} · ${t.pred.n} sources`)}
      ${tile("Resume", ordinal(t.res.rank), `z ${fmt(t.res.z, 2)} · ${t.res.n} sources`)}
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

/* ================= routing ================= */

function route() {
  tip.hide();
  redrawCharts = null;
  const m = /^#\/team\/([a-z0-9-]+)/.exec(location.hash);
  if (m) renderTeam(m[1]);
  else { document.title = "D1 Composite Rankings"; renderRankings(); }
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
