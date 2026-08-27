"""Self-contained HTML dashboard for the daily run.

Six tabs in one file (no external assets, no network):
  - Picks del Dia: TODOS los candidatos del dia (los que superaron min_edge y
    llegaron al motor de riesgo), con la razon de su stake en la columna Estado.
    Sortable table with filters (event date / sport / market / min EV) and a
    stats bar (best EV, average EV, average Kelly) recomputed over the filtered
    rows. The run keeps every event inside the 7-day horizon (early
    lines feed the CLV audit), so picks are grouped by LOCAL event date behind
    toggle pills defaulting to "Hoy". EV is the estimated edge (p*price-1);
    Kelly is the fractional-Kelly stake pct already capped by the risk engine.
  - Todos los Picks: TODAS las caras priceadas del dia (stream servido),
    ordenadas por probabilidad estimada descendente, con breakeven y margen al
    lado. Cumple la REGLA FUNDAMENTAL del operador (2026-08-26). Distinta de
    "Picks del Dia", que solo muestra los CANDIDATOS que superaron min_edge.
  - Auditoria: realized-ROI segments (overall / per league / per market) plus an
    estimated-vs-realized calibration check, from settled bets.
  - Diagnostico: current auto-pause state from the degradation monitor plus the
    flagged rows of the per-segment diagnostics (observability of the
    self-evaluation loop; both artifacts are produced by the daily run).
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
                              load_all_settled)
from sqp.config import ROOT
from sqp.monitoring.run_status import read_run_status
from sqp.sports.team_names import normalize_key

# Columns shown in the Picks del Dia table, in order: (key, header, kind).
# kind drives client-side sorting and formatting: "txt" | "num" | "pct" | "odds".
_PICK_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("fecha", "Fecha", "txt"),
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
    ("estado", "Estado", "txt"),
)


def _picks_records(predictions_dir: Path,
                   generated_day: str | None = None) -> list[dict]:
    """TODOS los candidatos del dia, ordenados por edge estimado, con la razon
    por la que cada uno lleva (o no) stake en la columna `estado`.

    Antes mostraba solo los ACCIONABLES via `rank_candidates` (stake>0 o flag
    `shadow_mode`). Al levantar shadow el 2026-08-16 ese flag dejo de emitirse y
    **la pestana que se abre por defecto quedo en blanco**, sin que nada lo
    señalara: el operador paso 53 dias creyendo que el sistema no generaba
    nada. Generaba 63 candidatos al dia; ninguno llevaba dinero.

    Se cambia AQUI y no en `rank_candidates` a proposito: esa funcion define
    "accionable" y alimenta el contador `Total accionables` del reporte
    markdown, que debe seguir contando solo los que llevarian dinero.
    """
    df = load_all_candidates(predictions_dir, generated_day=generated_day)
    if df.empty:
        return []
    ranked = df.sort_values("estimated_edge", ascending=False).copy()
    # `estado` explica el 0: sin el, 63 filas a stake 0 parecen una averia.
    flags = (ranked["flags"].fillna("").astype(str)
             if "flags" in ranked.columns
             else pd.Series("", index=ranked.index))
    stake = pd.to_numeric(ranked.get("stake"), errors="coerce").fillna(0.0)
    ranked["estado"] = [f if f else ("con stake" if s > 0 else "sin stake")
                        for s, f in zip(stake, flags)]
    if ranked.empty:
        return []
    if "home" in ranked.columns and "away" in ranked.columns:
        ranked = ranked.assign(
            partido=ranked["away"].astype(str) + " @ " + ranked["home"].astype(str))
    else:
        ranked = ranked.assign(partido=ranked.get("event_id", "").astype(str))
    # Event date in LOCAL time: a US west-coast night game commences after
    # 00:00Z, so the UTC date would file today's game under "tomorrow".
    if "start_time" in ranked.columns:
        st = pd.to_datetime(ranked["start_time"], errors="coerce", utc=True)
        local_tz = datetime.now(timezone.utc).astimezone().tzinfo
        ranked = ranked.assign(
            fecha=st.dt.tz_convert(local_tz).dt.strftime("%Y-%m-%d").fillna(""))
    else:
        ranked = ranked.assign(fecha="")
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


def _df_to_html_table(df: pd.DataFrame, *, empty_msg: str,
                      table_id: str | None = None) -> str:
    if df is None or df.empty:
        return f'<p class="empty">{html.escape(empty_msg)}</p>'
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body_rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(_fmt_cell(v))}</td>" for v in row)
        body_rows.append(f"<tr>{cells}</tr>")
    id_attr = f' id="{html.escape(table_id)}"' if table_id else ""
    return (f'<table class="grid"{id_attr}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>')


def _fmt_cell(v: object) -> str:
    if isinstance(v, float):
        if v != v:  # NaN: markets without a point (h2h) — KI-018
            return "—"
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


_DEGRADATION_COLS: tuple[tuple[str, str], ...] = (
    ("liga", "Liga"), ("mercado", "Mercado"), ("estado", "Estado"),
    ("razones", "Razones"), ("n", "n"), ("brier_modelo", "Brier modelo"),
    ("brier_mercado", "Brier mercado"), ("roi_flat", "ROI flat"),
    ("desde", "Pausado desde"))

_SEGMENT_COLS: tuple[str, ...] = (
    "league", "market", "dimension", "segment", "n", "hit_rate",
    "mean_est_prob", "gap", "brier_model", "brier_market", "roi_flat", "flags")


def _diagnostics_section(bets_dir: Path) -> str:
    """Estado del loop de autoevaluacion: auto-pausas vigentes del monitor de
    degradacion (degradation_pause.json) + segmentos con desviacion sistematica
    del diagnostico por segmentos (segment_diagnostics_latest.csv). Solo
    observabilidad sobre probabilidades estimadas; las pausas ya las aplico el
    run diario, aqui solo se muestran."""
    # local imports: sqp.risk.degradation/sqp.audit.segments importan
    # sqp.audit.report; locales evitan acoplar la carga del modulo
    from sqp.audit.segments import SEGMENTS_CSV
    from sqp.risk.degradation import load_degradation_registry
    parts: list[str] = ["<h3>Monitor de degradacion (auto-pausa por liga/mercado)</h3>"]
    markets = load_degradation_registry(bets_dir)
    if not markets:
        parts.append('<p class="empty">El monitor de degradacion aun no ha '
                     'corrido (se ejecuta en el run diario y persiste '
                     '<code>degradation_pause.json</code>).</p>')
    else:
        rows = []
        for key, e in sorted(markets.items()):
            if "|" not in key or not isinstance(e, dict):
                continue
            lg, mk = key.split("|", 1)
            rows.append({
                "liga": lg, "mercado": mk,
                "estado": "PAUSADO" if e.get("paused") else "activo",
                "razones": ", ".join(e.get("reasons") or []),
                "n": e.get("n"), "brier_modelo": e.get("brier_model"),
                "brier_mercado": e.get("brier_market"),
                "roi_flat": e.get("roi_flat"),
                "desde": str(e.get("since") or "")[:10],
            })
        deg = pd.DataFrame(rows, columns=[k for k, _ in _DEGRADATION_COLS])
        deg.columns = [h for _, h in _DEGRADATION_COLS]
        n_paused = sum(r["estado"] == "PAUSADO" for r in rows)
        parts.extend([
            '<div class="cards">',
            _card("Mercados auto-pausados", str(n_paused),
                  f"de {len(rows)} monitoreados"),
            "</div>",
            _df_to_html_table(deg, empty_msg="(sin mercados monitoreados)",
                              table_id="degradationTable"),
            '<p class="note">Pausa si el Brier de la probabilidad estimada es '
            'peor que el del mercado o el ROI a stake plano cae bajo el umbral; '
            'reanuda solo con histeresis. Un mercado pausado se sigue estimando '
            'y registrando con stake 0.</p>',
        ])
    parts.append("<h3>Segmentos con desviacion sistematica</h3>")
    seg_path = Path(bets_dir) / SEGMENTS_CSV
    if not seg_path.exists():
        parts.append('<p class="empty">Sin diagnostico por segmentos todavia '
                     '(se genera en el run diario como '
                     '<code>segment_diagnostics_latest.csv</code>).</p>')
        return "".join(parts)
    try:
        seg = pd.read_csv(seg_path)
    except Exception:
        seg = pd.DataFrame()
    if seg.empty or "flags" not in seg.columns:
        parts.append('<p class="empty">El diagnostico por segmentos no tiene '
                     'filas utilizables.</p>')
        return "".join(parts)
    flagged = seg[seg["flags"].fillna("") != ""]
    shown = flagged[[c for c in _SEGMENT_COLS if c in flagged.columns]]
    parts.extend([
        '<div class="cards">',
        _card("Segmentos flageados", str(len(flagged)),
              f"de {len(seg)} analizados"),
        "</div>",
        _df_to_html_table(shown, empty_msg="(ninguna desviacion detectada)",
                          table_id="segmentsTable"),
        '<p class="note">gap = frecuencia observada &minus; probabilidad '
        'estimada media (negativo = sobreconfianza); <code>roi_flat</code> es '
        'ROI realizado a stake plano de 1 unidad. Solo observabilidad: las '
        'pausas las decide el monitor por mercado completo.</p>',
    ])
    return "".join(parts)


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


_HISTORY_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("fecha", "Fecha", True), ("league", "Deporte", True),
    ("market", "Mercado", True), ("line", "Linea", False),
    ("home", "Home", True), ("away", "Away", True),
    ("selection", "Seleccion", True), ("price_decimal", "Cuota", False),
    ("stake", "Stake", False), ("result", "Resultado", True),
    ("pnl", "PnL", False),
)


def _team_condition(selection: object, home: object, away: object) -> str:
    """Condition of the picked side: "home" | "away" | "" (not team-bound).

    Compares the normalized selection against the normalized team names so
    vendor spelling differences do not break the match. Spread-style selections
    that append the line ("Yankees -1.5") match via prefix. Totals (Over/Under)
    and unmatched selections yield "" and are excluded from the condition
    filter rather than guessed."""
    sel = normalize_key(str(selection))
    if not sel:
        return ""
    for key, cond in ((normalize_key(str(home)), "home"),
                      (normalize_key(str(away)), "away")):
        if key and (sel == key or sel.startswith(key + " ")):
            return cond
    return ""


def _history_section(predictions_dir: Path, bets_dir: Path,
                     today: str | None = None) -> str:
    """Unified history: closed bets + open actionable picks, with filters
    (sport/market/condition/team/home/away/date) and totals cards (picks,
    closed, wins, losses, hit-rate %) recomputed client-side over the visible
    rows. The team / home / away option lists cascade from the selected sport.
    Past picks that never settled are hidden (not deleted)."""
    from datetime import date
    from sqp.audit.report import load_history, visible_history
    today = today or date.today().isoformat()
    df = visible_history(load_history(predictions_dir, bets_dir), today)
    if df.empty:
        return '<p class="empty">Sin historial de picks.</p>'
    df = df.sort_values("fecha", ascending=False)
    cols = [(k, hdr, txt) for k, hdr, txt in _HISTORY_COLUMNS if k in df.columns]
    cards = (
        '<div class="cards" id="historyCards">'
        '<div class="card"><span class="label">Picks</span><span class="value" id="hPicks">0</span></div>'
        '<div class="card"><span class="label">Picks cerrados</span><span class="value" id="hClosed">0</span></div>'
        '<div class="card"><span class="label">Wins</span><span class="value pos" id="hWins">0</span></div>'
        '<div class="card"><span class="label">Losses</span><span class="value neg" id="hLosses">0</span></div>'
        '<div class="card"><span class="label">Acierto %</span><span class="value" id="hHit">-</span></div>'
        '</div>')
    controls = (
        '<div class="filters" id="historyFilters">'
        '<label>Deporte<select id="hSport"><option value="">(todos)</option></select></label>'
        '<label>Mercado<select id="hMarket"><option value="">(todos)</option></select></label>'
        '<label>Condicion<select id="hCond"><option value="">(todas)</option>'
        '<option value="home">Home (local)</option>'
        '<option value="away">Away (visitante)</option></select></label>'
        '<label>Equipo<select id="hTeam"><option value="">(todos)</option></select></label>'
        '<label>Home<select id="hHome"><option value="">(todos)</option></select></label>'
        '<label>Away<select id="hAway"><option value="">(todos)</option></select></label>'
        '<label>Desde<input type="date" id="hFrom"></label>'
        '<label>Hasta<input type="date" id="hTo"></label>'
        '<label>&nbsp;<span class="gen" id="hCount"></span></label>'
        '</div>')
    head = "".join(f'<th class="{"txt" if txt else ""}">{html.escape(hdr)}</th>'
                   for _, hdr, txt in cols)
    body = []
    for _, row in df.iterrows():
        cells = "".join(
            f'<td class="{"txt" if txt else ""}">{html.escape(_fmt_cell(row.get(k)))}</td>'
            for k, _, txt in cols)
        body.append(
            f'<tr data-fecha="{html.escape(str(row.get("fecha", "")))}" '
            f'data-league="{html.escape(str(row.get("league", "")))}" '
            f'data-market="{html.escape(str(row.get("market", "")))}" '
            f'data-home="{html.escape(str(row.get("home", "")))}" '
            f'data-away="{html.escape(str(row.get("away", "")))}" '
            f'data-cond="{_team_condition(row.get("selection"), row.get("home"), row.get("away"))}" '
            f'data-result="{html.escape(str(row.get("result", "")))}">{cells}</tr>')
    table = (f'<table class="grid" id="historyTable"><thead><tr>{head}</tr></thead>'
             f'<tbody>{"".join(body)}</tbody></table>')
    return cards + controls + table


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


def _run_alert_banner(root: Path | None = None) -> str:
    """Banner rojo cuando el ultimo run diario fallo; cadena vacia si no.

    El dashboard se abre solo al terminar el run, asi que es donde el operador
    mira de todos modos. Sin esto, un fallo del pipeline solo era visible
    entrando al Programador de tareas (auditoria 2026-07-29, S-1).
    """
    st = read_run_status(root if root is not None else ROOT)
    if not st or not st.get("failed"):
        return ""
    stage = html.escape(str(st.get("stage", "?")))
    code = html.escape(str(st.get("exit_code", "?")))
    when = html.escape(str(st.get("failed_at", "fecha desconocida")))
    return (
        '<div class="runalert">'
        f"<strong>El ultimo run diario FALLO</strong> en la etapa "
        f"<code>{stage}</code> (exit {code}) el {when}. "
        "Los picks mostrados pueden estar incompletos o ser de un dia anterior. "
        "Revisar <code>logs/run_diario.log</code> y re-ejecutar "
        "<code>DIARIO_COMPLETO.bat</code>."
        "</div>")


def _todos_records(cal_dir: Path | None = None) -> list[dict]:
    """TODAS las caras priceadas del ultimo run, para la pestana "Todos los Picks".

    REGLA FUNDAMENTAL del operador (2026-08-26, SACROSANTA E INAMOVIBLE):
    "generar picks para todos los deportes y mercados, priorizando aquellos con
    las mayores probabilidades".

    Existe aparte de "Picks del Dia" porque esa muestra lo que llevaria DINERO
    (stake>0) -- hoy CERO, porque el gate bloquea los 32 mercados -- mientras
    esta muestra todo lo evaluado: 541 filas el 2026-08-26.

    `fecha` es la del PARTIDO en hora local, no la de generacion. El run guarda
    eventos con horizonte de 7 dias, asi que "generado hoy" incluye partidos de
    hasta 6 dias despues: de las 541 del 2026-08-26 solo 105 se jugaban ese dia.
    Filtrar por generacion y llamarlo "picks de hoy" era enganoso.

    `breakeven = 1/precio` y `margen = prob - breakeven` no son opcionales:
    ordenar por probabilidad a secas es el `pick_mode: accuracy` revertido el
    2026-07-31, donde un favorito a cuota 1.07 acierta el 90% y pierde igual.

    Sin stakes. Generar picks y apostarlos son cosas distintas.
    """
    cal_dir = cal_dir or (ROOT / "data" / "calibration")
    frames = []
    for f in sorted(cal_dir.glob("served_*.csv")):
        try:
            d = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
            continue
        if not d.empty:
            frames.append(d)
    if not frames:
        return []
    df = pd.concat(frames, ignore_index=True)
    if "generated_at" in df.columns:
        gen = df["generated_at"].astype(str).str[:10]
        df = df[gen == gen.max()]
    if df.empty:
        return []

    p = pd.to_numeric(df.get("estimated_probability"), errors="coerce")
    price = pd.to_numeric(df.get("price_decimal"), errors="coerce")
    be = 1.0 / price.where(price > 1.0)
    # Fecha del PARTIDO en hora local: un partido nocturno en la costa oeste de
    # EEUU comienza despues de las 00:00Z, asi que la fecha UTC lo archivaria
    # como de manana (mismo criterio que la pestana "Picks del Dia").
    st = pd.to_datetime(df.get("start_time"), errors="coerce", utc=True)
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    fecha = st.dt.tz_convert(local_tz).dt.strftime("%Y-%m-%d").fillna("")

    out = pd.DataFrame({
        "fecha": fecha, "league": df.get("league"), "market": df.get("market"),
        "seleccion": df.get("selection"), "linea": df.get("line"),
        "cuota": price, "prob": p, "breakeven": be, "margen": p - be,
        # ROI esperado por unidad apostada: p*cuota - 1. Es el `estimated_edge`
        # de siempre, llamado por su nombre. El operador pidio "sin dejar de
        # considerar el ROI" (2026-08-26) y resulta que ya se calculaba.
        "roi_esp": p * price - 1.0,
        "casas": pd.to_numeric(df.get("books_count"), errors="coerce"),
    })
    out = out[p.notna() & be.notna()].sort_values("prob", ascending=False)
    records: list[dict] = []
    for _, row in out.iterrows():
        rec: dict = {}
        for k in out.columns:
            v = row[k]
            if k in ("fecha", "league", "market", "seleccion"):
                rec[k] = "" if pd.isna(v) else str(v)
            else:
                rec[k] = None if pd.isna(v) else float(v)
        records.append(rec)
    return records


def html_dashboard(predictions_dir: Path | None = None,
                   bets_dir: Path | None = None,
                   *, make_latest: bool = True,
                   patterns_path: Path | None = None) -> str:
    """Build the daily HTML dashboard and return the written file path.

    When ``make_latest`` is True, also write a stable ``report_latest.html`` copy
    next to the dated file so a single bookmark always points at the newest run.
    """
    predictions_dir = predictions_dir or (ROOT / "data" / "predictions")
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = ts[:8]

    generated_day = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    picks = _picks_records(predictions_dir, generated_day=generated_day)
    columns_meta = [{"key": k, "header": h, "kind": kind}
                    for k, h, kind in _PICK_COLUMNS]
    # Local generation day: anchors the "Hoy" date pill to the run, not to
    # whenever the file happens to be opened.
    today_local = datetime.now(timezone.utc).astimezone().date().isoformat()
    payload = json.dumps({"picks": picks, "columns": columns_meta,
                          "today": today_local, "todos": _todos_records()},
                         ensure_ascii=False)

    page = _TEMPLATE.format(
        run_alert=_run_alert_banner(),
        day=html.escape(day),
        generated=html.escape(ts),
        audit=_audit_section(bets_dir),
        diagnostics=_diagnostics_section(bets_dir),
        patterns=_patterns_section(patterns_path),
        history=_history_section(predictions_dir, bets_dir),
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
.runalert {{ background:#7f1d1d; color:#fee2e2; border:1px solid #ef4444;
  border-radius:6px; padding:10px 14px; margin:10px 0; font-size:14px; }}
.runalert code {{ background:#450a0a; padding:1px 4px; border-radius:3px; }}
</style>
</head>
<body>
<header>
  <h1>Sports Quant Platform &mdash; Reporte diario {day}</h1>
  <div class="gen">Generado (UTC): {generated}</div>
</header>
{run_alert}
<nav class="tabs">
  <div class="tab active" data-tab="picks">Picks del Dia</div>
  <div class="tab" data-tab="todos">Todos los Picks</div>
  <div class="tab" data-tab="audit">Auditoria</div>
  <div class="tab" data-tab="diagnostics">Diagnostico</div>
  <div class="tab" data-tab="patterns">Patrones</div>
  <div class="tab" data-tab="history">Historial</div>
</nav>
<main>
  <section class="panel active" id="picks">
    <div class="stats" id="statsBar"></div>
    <div class="filters">
      <label>Fecha del evento<div class="tagfilter" id="dateTags"></div></label>
      <label>Deporte<div class="tagfilter" id="sportTags"></div></label>
      <label>Mercado<select id="fMarket"></select></label>
      <label>EV minimo<input id="fEv" type="number" step="0.01" value="0" style="width:90px"></label>
      <label>&nbsp;<span class="gen" id="count"></span></label>
    </div>
    <table class="grid" id="picksTable"><thead></thead><tbody></tbody></table>
  </section>
  <section class="panel" id="todos">
    <div class="stats" id="statsTodos"></div>
    <p class="gen"><strong>Todas las caras priceadas</strong>, ordenadas por
      probabilidad estimada. <code>Breakeven = 1/cuota</code> es el acierto que la
      CUOTA exige para no perder dinero; <code>Margen = Prob &minus; Breakeven</code>.
      Un margen negativo pierde a largo plazo <em>por alta que sea la
      probabilidad</em>. <code>Casas</code> es cuantas casas de apuestas cotizan
      esa linea: la cuota usada es la MEDIANA de todas ellas.
      <code>ROI esp.</code> es el retorno esperado por unidad apostada
      (<code>prob &times; cuota &minus; 1</code>). <strong>Pincha cualquier
      cabecera para reordenar</strong>: por defecto manda la probabilidad, pero
      probabilidad y ROI apuntan en sentidos OPUESTOS &mdash; el favorito mas
      probable suele tener ROI esperado negativo. Estas lineas
      <strong>no llevan stake</strong>.</p>
    <div class="filters">
      <label>Fecha del partido<div class="tagfilter" id="dateTagsT"></div></label>
      <label>Deporte<div class="tagfilter" id="sportTagsT"></div></label>
      <label>Mercado<select id="fMarketT"></select></label>
      <label>Margen minimo<input id="fMargenT" type="number" step="0.01" value="" placeholder="(todos)" style="width:100px"></label>
      <label>&nbsp;<span class="gen" id="countT"></span></label>
    </div>
    <table class="grid" id="todosTable"><thead></thead><tbody></tbody></table>
  </section>
  <section class="panel" id="audit">{audit}</section>
  <section class="panel" id="diagnostics">{diagnostics}</section>
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
let activeDates = new Set();

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

function labelFor(lg) {{
  if (SPORT_LABELS[lg]) return SPORT_LABELS[lg];
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

// Event-date toggle pills. The run keeps every event inside the 7-day horizon
// (early lines feed the CLV audit), so the table can hold future matchdays;
// the default view is today's games only, the rest stay one click away.
function dateLabel(d) {{
  if (!d) return "(sin fecha)";
  if (d === DATA.today) return "Hoy";
  const wd = new Date(d + "T12:00:00").toLocaleDateString("es", {{ weekday: "short" }});
  return `${{wd}} ${{d.slice(8, 10)}}-${{d.slice(5, 7)}}`;
}}
function buildDateTags() {{
  const dates = [...new Set(DATA.picks.map(r => r.fecha == null ? "" : r.fecha))].sort();
  document.getElementById("dateTags").innerHTML = dates.map(d =>
    `<span class="tag" style="color:${{d === DATA.today ? "var(--accent)" : "var(--ink)"}}" `
    + `data-date="${{d}}" onclick="toggleDate('${{d}}')">${{dateLabel(d)}}</span>`
  ).join("");
  // default: today only when today has picks; otherwise every date (never blank)
  activeDates = dates.includes(DATA.today) ? new Set([DATA.today]) : new Set(dates);
  document.querySelectorAll("[data-date]").forEach(e => {{
    e.classList.toggle("active", activeDates.has(e.dataset.date));
    e.classList.toggle("inactive", !activeDates.has(e.dataset.date));
  }});
}}
function toggleDate(d) {{
  if (activeDates.has(d)) activeDates.delete(d); else activeDates.add(d);
  document.querySelectorAll(`[data-date="${{d}}"]`).forEach(e => {{
    e.classList.toggle("active", activeDates.has(d));
    e.classList.toggle("inactive", !activeDates.has(d));
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
    activeSports.has(r.league) && activeDates.has(r.fecha == null ? "" : r.fecha) &&
    (!m || r.market === m) &&
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

// Generic client-side sorting for the server-rendered tables (Auditoria,
// Patrones, Historial). Numeric-aware: strips % and thousands separators.
function cellSortVal(td) {{
  const t = td.textContent.trim().replace("%", "").replace(/,/g, "");
  const n = parseFloat(t);
  return (t !== "" && !isNaN(n)) ? n : t.toLowerCase();
}}
function makeSortable(table) {{
  const ths = [...table.querySelectorAll("thead th")];
  ths.forEach((th, idx) => {{
    th.style.cursor = "pointer";
    th.addEventListener("click", () => {{
      const dir = th.dataset.dir === "1" ? -1 : 1;
      ths.forEach(o => {{ o.dataset.dir = ""; o.classList.remove("sorted"); }});
      th.dataset.dir = dir === 1 ? "1" : "0";
      th.classList.add("sorted");
      const tb = table.querySelector("tbody");
      [...tb.querySelectorAll("tr")].sort((a, b) => {{
        const x = cellSortVal(a.cells[idx]), y = cellSortVal(b.cells[idx]);
        if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
        return String(x).localeCompare(String(y)) * dir;
      }}).forEach(r => tb.appendChild(r));
    }});
  }});
}}
function initSortable() {{
  document.querySelectorAll("table.grid").forEach(t => {{
    if (t.id !== "picksTable") makeSortable(t);   // picks has its own sorter
  }});
}}

// Historial: filter rows by sport / market / condition (home|away) / team
// (either side) / home / away / date range (data-* on each row). Team lists
// cascade from the selected sport.
function initHistory() {{
  const table = document.getElementById("historyTable");
  if (!table) return;
  const rowsArr = [...table.querySelectorAll("tbody tr")];
  const uniqOf = a => [...new Set(rowsArr.map(r => r.dataset[a]).filter(Boolean))].sort();
  const fill = (id, vals, lbl) => {{
    const sel = document.getElementById(id);
    vals.forEach(v => sel.add(new Option(lbl ? lbl(v) : v, v)));
  }};
  fill("hSport", uniqOf("league"), labelFor);
  fill("hMarket", uniqOf("market"));
  // Equipo / Home / Away options are scoped to the selected sport and rebuilt
  // whenever it changes; a selection still valid for the new sport is kept.
  const refill = (id, vals) => {{
    const sel = document.getElementById(id);
    const prev = sel.value;
    sel.length = 1;                          // keep the "(todos)" option
    vals.forEach(v => sel.add(new Option(v, v)));
    sel.value = vals.includes(prev) ? prev : "";
  }};
  const fillTeams = () => {{
    const lg = document.getElementById("hSport").value;
    const rows = rowsArr.filter(r => !lg || r.dataset.league === lg);
    const vals = a => rows.map(r => r.dataset[a]).filter(Boolean);
    refill("hTeam", [...new Set([...vals("home"), ...vals("away")])].sort());
    refill("hHome", [...new Set(vals("home"))].sort());
    refill("hAway", [...new Set(vals("away"))].sort());
  }};
  fillTeams();
  // registered before filterHistory so the team lists are rebuilt first
  document.getElementById("hSport").addEventListener("input", fillTeams);
  ["hSport", "hMarket", "hCond", "hTeam", "hHome", "hAway", "hFrom", "hTo"].forEach(id =>
    document.getElementById(id).addEventListener("input", filterHistory));
  filterHistory();
}}
function filterHistory() {{
  const table = document.getElementById("historyTable");
  const g = id => document.getElementById(id).value;
  const lg = g("hSport"), mk = g("hMarket"), cn = g("hCond"), tm = g("hTeam"),
        ho = g("hHome"), aw = g("hAway"), from = g("hFrom"), to = g("hTo");
  let picks = 0, closed = 0, wins = 0, losses = 0;
  table.querySelectorAll("tbody tr").forEach(r => {{
    const d = r.dataset;
    const ok = (!lg || d.league === lg) && (!mk || d.market === mk) &&
               (!cn || d.cond === cn) &&
               (!tm || d.home === tm || d.away === tm) &&
               (!ho || d.home === ho) && (!aw || d.away === aw) &&
               (!from || d.fecha >= from) && (!to || d.fecha <= to);
    r.style.display = ok ? "" : "none";
    if (!ok) return;
    picks++;
    if (d.result) closed++;
    if (d.result === "win") wins++;
    if (d.result === "loss") losses++;
  }});
  const set = (id, v) => {{ const e = document.getElementById(id); if (e) e.textContent = v; }};
  set("hPicks", picks); set("hClosed", closed); set("hWins", wins); set("hLosses", losses);
  const graded = wins + losses;
  set("hHit", graded ? (100 * wins / graded).toFixed(1) + "%" : "-");
  set("hCount", picks + " filas");
}}

function init() {{
  initSortable();
  initHistory();
  activeSports = new Set(uniq("league"));   // all sports active by default
  buildSportTags();
  buildDateTags();                          // today-only view by default
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
// ---- Pestana "Todos los Picks" -------------------------------------------
// Filtros propios (fecha del PARTIDO, deporte, mercado, margen minimo) sobre
// TODAS las caras priceadas. Reutiliza labelFor/colorFor/dateLabel de arriba.
// Por defecto muestra SOLO los partidos de hoy: el run guarda 7 dias de
// horizonte, asi que sin este filtro "los picks de hoy" mezclaba seis dias.
const TODOS = DATA.todos || [];
let tDates = new Set(), tSports = new Set();

const T_COLS = [
  ["fecha","Fecha","txt"], ["league","Deporte","lg"], ["market","Mercado","txt"],
  ["seleccion","Seleccion","txt"], ["linea","Linea","num"], ["cuota","Cuota","odds"],
  ["prob","Prob. est.","pct"], ["breakeven","Breakeven","pct"],
  ["margen","Margen","pct"], ["roi_esp","ROI esp.","pct"], ["casas","Casas","int"],
];
// Orden por defecto: PROBABILIDAD descendente (regla fundamental del operador).
// Pinchando una cabecera se reordena -- asi "mayor probabilidad" y "mejor ROI"
// son dos clics, no dos vistas. Van en sentidos opuestos en estos datos: el
// favorito mas probable suele tener ROI esperado NEGATIVO.
let tSortKey = "prob", tSortDir = -1;
function tSort(k) {{
  if (tSortKey === k) {{ tSortDir = -tSortDir; }} else {{ tSortKey = k; tSortDir = -1; }}
  tRefresh();
}}
const tFmt = {{
  txt: v => v == null ? "" : v,
  lg:  v => labelFor(v),
  int: v => v == null ? "" : String(Math.round(v)),
  num: v => v == null ? "—" : (Math.round(v * 100) / 100).toString(),
  odds: v => v == null ? "" : v.toFixed(2),
  pct: v => v == null ? "" : (v * 100).toFixed(2) + "%",
}};

function tBuildDates() {{
  const ds = [...new Set(TODOS.map(r => r.fecha || ""))].sort();
  document.getElementById("dateTagsT").innerHTML = ds.map(d =>
    `<span class="tag" style="color:${{d === DATA.today ? "var(--accent)" : "var(--ink)"}}" `
    + `data-tdate="${{d}}" onclick="tToggleDate('${{d}}')">${{dateLabel(d)}}</span>`).join("");
  tDates = ds.includes(DATA.today) ? new Set([DATA.today]) : new Set(ds);
  tSync("data-tdate", tDates, e => e.dataset.tdate);
}}
function tBuildSports() {{
  const lgs = [...new Set(TODOS.map(r => r.league))].filter(Boolean).sort();
  document.getElementById("sportTagsT").innerHTML = lgs.map((lg, i) =>
    `<span class="tag active" style="color:${{colorFor(lg, i)}}" `
    + `data-tsport="${{lg}}" onclick="tToggleSport('${{lg}}')">${{labelFor(lg)}}</span>`).join("");
  tSync("data-tsport", tSports, e => e.dataset.tsport);
}}
function tSync(attr, set, get) {{
  document.querySelectorAll(`[${{attr}}]`).forEach(e => {{
    const on = set.size === 0 ? true : set.has(get(e));
    e.classList.toggle("active", on); e.classList.toggle("inactive", !on);
  }});
}}
function tToggleDate(d) {{
  if (tDates.has(d)) tDates.delete(d); else tDates.add(d);
  tSync("data-tdate", tDates, e => e.dataset.tdate); tRefresh();
}}
function tToggleSport(lg) {{
  if (tSports.has(lg)) tSports.delete(lg); else tSports.add(lg);
  tSync("data-tsport", tSports, e => e.dataset.tsport); tRefresh();
}}
function tBuildMarkets() {{
  const ms = [...new Set(TODOS.map(r => r.market))].filter(Boolean).sort();
  document.getElementById("fMarketT").innerHTML =
    '<option value="">(todos)</option>' + ms.map(m => `<option>${{m}}</option>`).join("");
}}
function tFiltered() {{
  const mk = document.getElementById("fMarketT").value;
  const mgRaw = document.getElementById("fMargenT").value;
  const mg = mgRaw === "" ? null : parseFloat(mgRaw);
  return TODOS.filter(r =>
    (tDates.size === 0 || tDates.has(r.fecha || "")) &&
    (tSports.size === 0 || tSports.has(r.league)) &&
    (!mk || r.market === mk) &&
    (mg == null || (r.margen != null && r.margen >= mg)));
}}
function tRefresh() {{
  const rows = tFiltered();
  const pos = rows.filter(r => r.margen > 0).length;
  const lig = new Set(rows.map(r => r.league)).size;
  document.getElementById("statsTodos").innerHTML =
      `<div class="card"><div class="k">Selecciones</div><div class="v">${{rows.length}}</div></div>`
    + `<div class="card"><div class="k">Ligas</div><div class="v">${{lig}}</div></div>`
    + `<div class="card"><div class="k">Margen positivo</div><div class="v">${{pos}}</div></div>`;
  document.getElementById("countT").textContent = `${{rows.length}} de ${{TODOS.length}}`;
  rows.sort((a, b) => {{
    const x = a[tSortKey], y = b[tSortKey];
    if (x == null) return 1;
    if (y == null) return -1;
    if (typeof x === "string") return tSortDir * x.localeCompare(y);
    return tSortDir * (x - y);
  }});
  const tbl = document.getElementById("todosTable");
  tbl.querySelector("thead").innerHTML =
    "<tr>" + T_COLS.map(c => {{
      const on = c[0] === tSortKey ? (tSortDir < 0 ? " ▼" : " ▲") : "";
      return `<th style="cursor:pointer" onclick="tSort('${{c[0]}}')">${{c[1]}}${{on}}</th>`;
    }}).join("") + "</tr>";
  tbl.querySelector("tbody").innerHTML = rows.length
    ? rows.slice(0, 500).map(r => "<tr>" + T_COLS.map(c =>
        `<td>${{tFmt[c[2]](r[c[0]])}}</td>`).join("") + "</tr>").join("")
    : `<tr><td colspan="${{T_COLS.length}}">Sin selecciones con estos filtros.</td></tr>`;
}}
tBuildDates(); tBuildSports(); tBuildMarkets();
document.getElementById("fMarketT").addEventListener("change", tRefresh);
document.getElementById("fMargenT").addEventListener("input", tRefresh);
tRefresh();

</script>
</body>
</html>
"""
