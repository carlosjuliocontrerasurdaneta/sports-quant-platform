"""Self-contained HTML dashboard for the daily run.

Four tabs in one file (no external assets, no network):
  - Picks del Dia: sortable table with filters (sport / market / min EV) and a
    stats bar (best EV, average EV, average Kelly) recomputed over the filtered
    rows. EV is the estimated edge (p*price-1); Kelly is the fractional-Kelly
    stake pct already capped by the risk engine.
  - Auditoria: realized-ROI segments (overall / per league / per market) plus an
    estimated-vs-realized calibration check, from settled bets.
  - Patrones: hit-rate / frequency breakdowns from the consolidated pick history
    backtest (by market, situation, home/away, Over/Under, per team) with a
    short data-driven reading.
  - Historial: chronological list of every graded bet.

All numbers are estimated probabilities / estimated edges, never certainties.
"""
from __future__ import annotations

import html
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.audit.patterns import (conclusions, load_pick_history,
                                pattern_breakdowns)
from sqp.audit.report import (DISCLAIMER, _segment_audit, load_all_candidates,
                              load_all_settled, rank_candidates)
from sqp.config import ROOT

# Columns shown in the Picks del Dia table, in order: (key, header, kind).
# kind drives client-side sorting and formatting: "txt" | "num" | "pct" | "odds".
_PICK_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("league", "Deporte", "txt"),
    ("partido", "Partido", "txt"),
    ("market", "Mercado", "txt"),
    ("selection", "Seleccion", "txt"),
    ("line", "Linea", "num"),
    ("price_decimal", "Cuota", "odds"),
    ("estimated_probability", "Prob. estimada", "pct"),
    ("implied_probability_novig", "Prob. no-vig", "pct"),
    ("estimated_edge", "EV (edge)", "pct"),
    ("kelly_stake_pct", "Kelly %", "pct"),
    ("stake", "Stake", "num"),
)


def _picks_records(predictions_dir: Path) -> list[dict]:
    """Actionable picks (stake>0, not flagged) ranked by estimated edge, as plain
    JSON-serializable dicts for the client-side table."""
    df = load_all_candidates(predictions_dir)
    if df.empty:
        return []
    ranked = rank_candidates(df)
    if ranked.empty:
        return []
    if "home" in ranked.columns and "away" in ranked.columns:
        ranked = ranked.assign(
            partido=ranked["away"].astype(str) + " @ " + ranked["home"].astype(str))
    else:
        ranked = ranked.assign(partido=ranked.get("event_id", "").astype(str))
    records: list[dict] = []
    for _, row in ranked.iterrows():
        rec: dict = {}
        for key, _hdr, kind in _PICK_COLUMNS:
            val = row.get(key)
            if kind == "txt":
                rec[key] = "" if pd.isna(val) else str(val)
            else:
                rec[key] = None if pd.isna(val) else float(val)
        records.append(rec)
    return records


def _df_to_html_table(df: pd.DataFrame, *, empty_msg: str) -> str:
    if df is None or df.empty:
        return f'<p class="empty">{html.escape(empty_msg)}</p>'
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(_fmt_cell(v))}</td>" for v in row)
        body_rows.append(f"<tr>{cells}</tr>")
    return (f'<table class="grid"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>')


def _fmt_cell(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 1000 else f"{v:.2f}"
    return "" if v is None else str(v)


def _audit_section(bets_dir: Path) -> str:
    df = load_all_settled(bets_dir)
    if df.empty:
        return ('<p class="empty">Sin apuestas liquidadas todavia. Corre '
                'SETTLE_ALL.bat tras los partidos para poblar esta pestana.</p>')
    graded = df[df["result"].isin(["win", "loss"])]
    staked = float(graded["stake"].sum())
    overall_roi = float(df["pnl"].sum() / staked) if staked else 0.0
    by_league = _segment_audit(df, ["league"])
    by_market = _segment_audit(df, ["market"])
    return "".join([
        '<div class="cards">',
        _card("Apuestas liquidadas", f"{len(graded)}",
              f"pushes/void: {len(df) - len(graded)}"),
        _card("Stake total", f"{staked:.2f}", f"PnL: {df['pnl'].sum():.2f}"),
        _card("ROI realizado", f"{overall_roi:.2%}", "global, sobre stake graded"),
        "</div>",
        "<h3>Por liga</h3>", _df_to_html_table(by_league, empty_msg="(sin datos)"),
        "<h3>Por mercado</h3>", _df_to_html_table(by_market, empty_msg="(sin datos)"),
        '<p class="note">Chequeo de calibracion: <code>mean_est_prob</code> deberia '
        'aproximar <code>hit_rate</code> y <code>mean_est_edge</code> deberia '
        'aproximar <code>realized_roi</code> si el modelo esta bien calibrado.</p>',
    ])


_PATTERN_BLOCKS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("by_market", "1) Aciertos por tipo de mercado",
     ("market_label", "n", "wins", "losses", "hit_rate_%", "roi_%", "mean_edge")),
    ("by_situation", "2) Situaciones con mayor tasa de acierto (mercado x lado)",
     ("market_label", "side", "n", "wins", "hit_rate_%", "roi_%")),
    ("moneyline_side", "3) Moneyline: local (home) vs visitante (away)",
     ("side", "n", "wins", "losses", "hit_rate_%", "roi_%")),
    ("handicap_side", "4) Handicap: local (home) vs visitante (away)",
     ("side", "n", "wins", "losses", "hit_rate_%", "roi_%")),
    ("totals_side", "5) Totales: Over vs Under",
     ("side", "n", "wins", "losses", "hit_rate_%", "roi_%")),
    ("team_top", "6a) Equipos con mayor tasa de acierto (ML + handicap)",
     ("team", "n", "wins", "losses", "hit_rate_%", "roi_%")),
    ("team_bottom", "6b) Equipos con menor tasa de acierto (ML + handicap)",
     ("team", "n", "wins", "losses", "hit_rate_%", "roi_%")),
)


def _patterns_section(history_path: Path | None = None) -> str:
    """Hit-rate / frequency breakdowns from the consolidated pick-history
    backtest. ``n`` is the pick frequency per group (home/away, Over/Under)."""
    hist = load_pick_history(history_path)
    if hist.empty:
        return ('<p class="empty">Sin historial consolidado todavia. Se genera en '
                'el run diario (o corre <code>scripts/build_pick_history.py</code>) '
                'una vez que existan odds historicas y resultados.</p>')
    breaks = pattern_breakdowns(hist)
    graded = hist[hist["result"].isin(["win", "loss"])]
    parts = [
        '<p class="note">Backtest sobre un proxy de cierre (snapshot unico, '
        'cobertura limitada). <code>n</code> es la frecuencia de picks por grupo; '
        'la tasa de acierto es realizada pero NO garantiza resultados futuros y el '
        'edge estimado NO es ROI realizado.</p>',
        '<div class="cards">',
        _card("Picks (historial)", f"{len(hist)}", f"graduados: {len(graded)}"),
        _card("Ligas", f"{hist['league'].nunique()}",
              ", ".join(sorted(hist["league"].unique()))),
        _card("Rango", f"{hist['date'].min()}", f"-> {hist['date'].max()}"),
        "</div>",
        "<h3>Lectura</h3><ul class='reading'>",
    ]
    for line in conclusions(breaks):
        parts.append(f"<li>{_emph(line)}</li>")
    parts.append("</ul>")
    for key, title, cols in _PATTERN_BLOCKS:
        df = breaks.get(key)
        parts.append(f"<h3>{html.escape(title)}</h3>")
        if df is None or df.empty:
            parts.append('<p class="empty">(sin muestra suficiente)</p>')
            continue
        shown = df[[c for c in cols if c in df.columns]]
        parts.append(_df_to_html_table(shown, empty_msg="(sin datos)"))
    return "".join(parts)


def _emph(text: str) -> str:
    """Escape text, then render **bold** spans (used in the reading bullets)."""
    out, bold = [], False
    for chunk in html.escape(text).split("**"):
        out.append(f"<strong>{chunk}</strong>" if bold else chunk)
        bold = not bold
    return "".join(out)


def _history_section(bets_dir: Path) -> str:
    df = load_all_settled(bets_dir)
    if df.empty:
        return '<p class="empty">Sin historial de apuestas liquidadas.</p>'
    d = df.copy()
    d["fecha"] = d.get("settled_at", "").astype(str).str[:10]
    cols = [c for c in ["fecha", "league", "market", "selection", "line",
                        "price_decimal", "stake", "result", "pnl",
                        "estimated_edge", "estimated_probability"]
            if c in d.columns]
    d = d[cols].sort_values("fecha", ascending=False)
    d = d.rename(columns={"league": "deporte", "market": "mercado",
                          "selection": "seleccion", "line": "linea",
                          "price_decimal": "cuota", "result": "resultado",
                          "estimated_edge": "edge_estimado",
                          "estimated_probability": "prob_estimada"})
    return _df_to_html_table(d, empty_msg="(sin historial)")


def _card(title: str, value: str, sub: str = "") -> str:
    sub_html = f'<span class="sub">{html.escape(sub)}</span>' if sub else ""
    return (f'<div class="card"><span class="label">{html.escape(title)}</span>'
            f'<span class="value">{html.escape(value)}</span>{sub_html}</div>')


def open_in_browser(path: str | Path) -> bool:
    """Open a generated report in the default browser.

    Best-effort: returns True if the platform accepted the request, False on any
    failure (headless box, no browser configured). Never raises -- the daily run
    must never fail just because a UI could not be displayed.
    """
    try:
        return webbrowser.open(Path(path).resolve().as_uri())
    except Exception:
        return False


def html_dashboard(predictions_dir: Path | None = None,
                   bets_dir: Path | None = None,
                   *, make_latest: bool = True) -> str:
    """Build the daily HTML dashboard and return the written file path.

    When ``make_latest`` is True, also write a stable ``report_latest.html`` copy
    next to the dated file so a single bookmark always points at the newest run.
    """
    predictions_dir = predictions_dir or (ROOT / "data" / "predictions")
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = ts[:8]

    picks = _picks_records(predictions_dir)
    columns_meta = [{"key": k, "header": h, "kind": kind}
                    for k, h, kind in _PICK_COLUMNS]
    payload = json.dumps({"picks": picks, "columns": columns_meta},
                         ensure_ascii=False)

    page = _TEMPLATE.format(
        day=html.escape(day),
        generated=html.escape(ts),
        audit=_audit_section(bets_dir),
        patterns=_patterns_section(),
        history=_history_section(bets_dir),
        disclaimer=html.escape(DISCLAIMER),
        data_json=payload,
    )
    predictions_dir.mkdir(parents=True, exist_ok=True)
    path = predictions_dir / f"report_{day}.html"
    path.write_text(page, encoding="utf-8")
    if make_latest:
        (predictions_dir / "report_latest.html").write_text(page, encoding="utf-8")
    return str(path)


_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SQP - Reporte diario {day}</title>
<style>
  :root {{ --bg:#0f1419; --panel:#1a2029; --ink:#e6edf3; --muted:#8b98a5;
           --accent:#3fb950; --line:#2d333b; --warn:#d29922; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif; }}
  header {{ padding:18px 22px; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0; font-size:18px; }}
  .gen {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  .tabs {{ display:flex; gap:4px; padding:0 18px; border-bottom:1px solid var(--line); }}
  .tab {{ padding:10px 16px; cursor:pointer; color:var(--muted);
          border-bottom:2px solid transparent; user-select:none; }}
  .tab.active {{ color:var(--ink); border-bottom-color:var(--accent); }}
  main {{ padding:18px 22px; }}
  .panel {{ display:none; }}
  .panel.active {{ display:block; }}
  .stats {{ display:flex; gap:14px; flex-wrap:wrap; margin-bottom:14px; }}
  .cards {{ display:flex; gap:14px; flex-wrap:wrap; margin-bottom:8px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px;
           padding:12px 16px; min-width:150px; display:flex; flex-direction:column; }}
  .card .label {{ color:var(--muted); font-size:12px; }}
  .card .value {{ font-size:22px; font-weight:600; margin-top:2px; }}
  .card .sub {{ color:var(--muted); font-size:11px; margin-top:2px; }}
  .filters {{ display:flex; gap:14px; flex-wrap:wrap; align-items:end; margin-bottom:12px; }}
  .filters label {{ display:flex; flex-direction:column; font-size:12px; color:var(--muted); gap:4px; }}
  .tagfilter {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .tag {{ cursor:pointer; padding:4px 12px; border-radius:9999px; font-size:12px;
          font-weight:600; border:1.5px solid transparent; background:var(--panel);
          user-select:none; transition:all .15s; }}
  .tag.active {{ border-color:currentColor; }}
  .tag.inactive {{ opacity:0.35; }}
  select,input {{ background:var(--panel); color:var(--ink); border:1px solid var(--line);
                  border-radius:6px; padding:6px 8px; font-size:13px; }}
  table.grid {{ border-collapse:collapse; width:100%; font-size:13px; }}
  table.grid th,table.grid td {{ border-bottom:1px solid var(--line); padding:7px 10px; text-align:right; }}
  table.grid th:first-child,table.grid td:first-child,
  table.grid th.txt,table.grid td.txt {{ text-align:left; }}
  table.grid thead th {{ position:sticky; top:0; background:var(--panel); cursor:pointer; white-space:nowrap; }}
  table.grid thead th.sorted::after {{ content:" \\2195"; color:var(--accent); }}
  table.grid tbody tr:hover {{ background:#161b22; }}
  .pos {{ color:var(--accent); }} .neg {{ color:#f85149; }}
  .empty,.note {{ color:var(--muted); }}
  .note code {{ color:var(--ink); }}
  footer {{ padding:16px 22px; color:var(--muted); font-size:11px;
            border-top:1px solid var(--line); }}
  h3 {{ margin:18px 0 8px; font-size:14px; }}
  ul.reading {{ margin:6px 0 0; padding-left:18px; }}
  ul.reading li {{ margin:3px 0; }}
</style>
</head>
<body>
<header>
  <h1>Sports Quant Platform &mdash; Reporte diario {day}</h1>
  <div class="gen">Generado (UTC): {generated}</div>
</header>
<nav class="tabs">
  <div class="tab active" data-tab="picks">Picks del Dia</div>
  <div class="tab" data-tab="audit">Auditoria</div>
  <div class="tab" data-tab="patterns">Patrones</div>
  <div class="tab" data-tab="history">Historial</div>
</nav>
<main>
  <section class="panel active" id="picks">
    <div class="stats" id="statsBar"></div>
    <div class="filters">
      <label>Deporte<div class="tagfilter" id="sportTags"></div></label>
      <label>Mercado<select id="fMarket"></select></label>
      <label>EV minimo<input id="fEv" type="number" step="0.01" value="0" style="width:90px"></label>
      <label>&nbsp;<span class="gen" id="count"></span></label>
    </div>
    <table class="grid" id="picksTable"><thead></thead><tbody></tbody></table>
  </section>
  <section class="panel" id="audit">{audit}</section>
  <section class="panel" id="patterns">{patterns}</section>
  <section class="panel" id="history">{history}</section>
</main>
<footer>{disclaimer}</footer>
<script>
const DATA = {data_json};
const COLS = DATA.columns;
let rows = DATA.picks.slice();
let sortKey = "estimated_edge", sortDir = -1;
let activeSports = new Set();

// Per-sport toggle pills (multi-select). Labels/colors are best-effort; any
// league not listed falls back to its uppercased id and a palette colour.
const SPORT_LABELS = {{
  mlb:"MLB", nba:"NBA", wnba:"WNBA", ncaab:"NCAAB", wncaab:"WNCAAB",
  nfl:"NFL", ncaaf:"NCAAF", nhl:"NHL", epl:"EPL", laliga:"LaLiga",
  seriea:"Serie A", bundesliga:"Bundesliga", ligue1:"Ligue 1", ucl:"UCL",
  mls:"MLS", ligamx:"Liga MX", brasileirao:"Brasileirao", chile:"Chile",
  uwcl:"UWCL"
}};
const SPORT_COLORS = {{
  mlb:"#3fb950", nba:"#e3853a", wnba:"#d96bb0", ncaab:"#e3b341", wncaab:"#bc8cff",
  nfl:"#58a6ff", ncaaf:"#79c0ff", nhl:"#39c5cf"
}};
const PALETTE = ["#3fb950","#58a6ff","#d29922","#bc8cff","#f85149","#39c5cf",
                 "#e3853a","#7ee787","#ff7b72","#a5d6ff","#d96bb0","#e3b341"];

function titleCase(s) {{
  return s.split(" ").map(w => w ? w[0].toUpperCase() + w.slice(1) : w).join(" ");
}}
function labelFor(lg) {{
  if (SPORT_LABELS[lg]) return SPORT_LABELS[lg];
  if (lg.indexOf("tennis_") === 0) {{
    const p = lg.split("_");
    return ((p[1] || "").toUpperCase() + " " + titleCase(p.slice(2).join(" "))).trim();
  }}
  return lg.toUpperCase();
}}
function colorFor(lg, i) {{ return SPORT_COLORS[lg] || PALETTE[i % PALETTE.length]; }}

function buildSportTags() {{
  const leagues = uniq("league");
  const el = document.getElementById("sportTags");
  el.innerHTML = leagues.map((lg, i) =>
    `<span class="tag active" style="color:${{colorFor(lg, i)}}" `
    + `data-sport="${{lg}}" onclick="toggleSport('${{lg}}')">${{labelFor(lg)}}</span>`
  ).join("");
}}
function toggleSport(lg) {{
  if (activeSports.has(lg)) activeSports.delete(lg); else activeSports.add(lg);
  document.querySelectorAll(`[data-sport="${{lg}}"]`).forEach(e => {{
    e.classList.toggle("active", activeSports.has(lg));
    e.classList.toggle("inactive", !activeSports.has(lg));
  }});
  refresh();
}}

const fmt = {{
  txt: v => v == null ? "" : v,
  num: v => v == null ? "" : (Math.round(v * 100) / 100).toString(),
  odds: v => v == null ? "" : v.toFixed(2),
  pct: v => v == null ? "" : (v * 100).toFixed(2) + "%",
}};

function kindOf(key) {{ return (COLS.find(c => c.key === key) || {{}}).kind || "txt"; }}

function uniq(key) {{
  return [...new Set(DATA.picks.map(r => r[key]).filter(v => v !== "" && v != null))].sort();
}}

function fillSelect(el, vals) {{
  el.innerHTML = '<option value="">(todos)</option>' +
    vals.map(v => `<option value="${{v}}">${{v}}</option>`).join("");
}}

function filtered() {{
  const m = document.getElementById("fMarket").value;
  const ev = parseFloat(document.getElementById("fEv").value) || -Infinity;
  return DATA.picks.filter(r =>
    activeSports.has(r.league) && (!m || r.market === m) &&
    ((r.estimated_edge == null ? -Infinity : r.estimated_edge) >= ev));
}}

function renderStats(list) {{
  const evs = list.map(r => r.estimated_edge).filter(v => v != null);
  const ks = list.map(r => r.kelly_stake_pct).filter(v => v != null);
  const best = evs.length ? Math.max(...evs) : null;
  const avg = evs.length ? evs.reduce((a, b) => a + b, 0) / evs.length : null;
  const ak = ks.length ? ks.reduce((a, b) => a + b, 0) / ks.length : null;
  const card = (l, v) => `<div class="card"><span class="label">${{l}}</span>`
    + `<span class="value">${{v == null ? "&mdash;" : (v * 100).toFixed(2) + "%"}}</span></div>`;
  document.getElementById("statsBar").innerHTML =
    card("Mejor EV", best) + card("EV promedio", avg) + card("Kelly promedio", ak);
}}

function renderTable(list) {{
  const dir = sortDir;
  const k = sortKey;
  list = list.slice().sort((a, b) => {{
    let x = a[k], y = b[k];
    if (x == null) return 1; if (y == null) return -1;
    if (typeof x === "string") return x.localeCompare(y) * dir;
    return (x - y) * dir;
  }});
  const thead = document.querySelector("#picksTable thead");
  thead.innerHTML = "<tr>" + COLS.map(c => {{
    const cls = (c.kind === "txt" ? "txt" : "") + (c.key === k ? " sorted" : "");
    return `<th class="${{cls}}" data-key="${{c.key}}">${{c.header}}</th>`;
  }}).join("") + "</tr>";
  thead.querySelectorAll("th").forEach(th => th.onclick = () => {{
    const key = th.dataset.key;
    sortDir = (key === sortKey) ? -sortDir : (kindOf(key) === "txt" ? 1 : -1);
    sortKey = key; refresh();
  }});
  const tbody = document.querySelector("#picksTable tbody");
  tbody.innerHTML = list.map(r => "<tr>" + COLS.map(c => {{
    const v = r[c.key];
    let cls = c.kind === "txt" ? "txt" : "";
    if ((c.key === "estimated_edge" || c.key === "kelly_stake_pct") && v != null)
      cls += v >= 0 ? " pos" : " neg";
    return `<td class="${{cls}}">${{fmt[c.kind](v)}}</td>`;
  }}).join("") + "</tr>").join("");
  document.getElementById("count").textContent = list.length + " picks";
}}

function refresh() {{
  const list = filtered();
  renderStats(list);
  renderTable(list);
}}

function init() {{
  activeSports = new Set(uniq("league"));   // all sports active by default
  buildSportTags();
  fillSelect(document.getElementById("fMarket"), uniq("market"));
  ["fMarket", "fEv"].forEach(id =>
    document.getElementById(id).addEventListener("input", refresh));
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {{
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    document.getElementById(t.dataset.tab).classList.add("active");
  }});
  if (!DATA.picks.length) {{
    document.querySelector("#picks .filters").style.display = "none";
    document.getElementById("picksTable").outerHTML =
      '<p class="empty">Sin candidatos accionables hoy.</p>';
    renderStats([]);
    return;
  }}
  refresh();
}}
init();
</script>
</body>
</html>
"""
