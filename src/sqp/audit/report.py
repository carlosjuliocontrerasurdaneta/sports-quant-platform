"""Audit reports: per-league calibration, model-vs-market deviation, segment
analysis (home/away, favorite/underdog). Reproducible and timestamped."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from sqp.config import ROOT

DISCLAIMER = ("Estas son probabilidades estimadas, no certezas. El edge estimado "
              "no es ROI realizado y no garantiza ganancias. Auditar antes de usar.")


def has_flag(flags: pd.Series, flag: str) -> pd.Series:
    """Token-wise membership test over the `;`-separated ``flags`` column.

    ``flags`` started as a single token, so the reports compared it with `==`.
    Since `pick_mode: accuracy` (2026-07-28) daily.py concatenates markers
    (``"shadow_mode;accuracy_mode"``), and the equality test silently stopped
    matching: every production pick vanished from the ranking, the consolidated
    report and the dashboard (audit 2026-07-29, B-01). Match tokens, not the
    whole string, so any future marker composes without breaking visibility.
    """
    s = flags.fillna("").astype(str)
    return s.str.split(";").apply(lambda toks: flag in [t.strip() for t in toks])


def write_calibration_report(backtest_result: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = ROOT / "data" / "processed"
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"calibration_{backtest_result['league']}_{ts}.md"
    tbl: pd.DataFrame = backtest_result["reliability_table"]
    lines = [
        f"# Calibration report - {backtest_result['league']}",
        f"Generated: {ts}",
        f"Games evaluated: {backtest_result['n_games_evaluated']}",
        f"Brier score: {backtest_result['brier_score']:.4f}",
        f"Log loss: {backtest_result['log_loss']:.4f}",
        f"ECE: {backtest_result['ece']:.4f}",
        "",
        "## Reliability table (estimated probability vs observed frequency)",
        tbl.to_string(index=False) if not tbl.empty else "(empty)",
        "",
        f"> {backtest_result['note']}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# --- Consolidated picks report ------------------------------------------------

def rank_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """Visible picks (staked or shadow) ranked by estimated edge.

    The blocking flags (`market_paused`, `edge_exceeds_max_plausible`) force
    stake=0 AND hide the row, so a stake>0 row is always a real bet.
    `daily_exposure_scaled` is NOT a blocking flag -- it marks a bet whose stake
    was proportionally reduced to respect the daily exposure cap, so it must
    still count as actionable. Filtering on `flags == ""` (the prior behavior)
    wrongly hid every scaled pick, which is exactly the whole league on a day
    the exposure cap triggers. A `shadow_mode` row also stays visible: it IS
    the day's pick, only its stake is forced to 0 while evidence accrues (the
    stake>0-only filter blanked the whole dashboard on the first shadow day)."""
    d = df.copy()
    flags = d["flags"].fillna("") if "flags" in d.columns else pd.Series("", index=d.index)
    visible = d[(d["stake"] > 0) | has_flag(flags, "shadow_mode")]
    return visible.sort_values("estimated_edge", ascending=False)


def load_all_candidates(predictions_dir: Path,
                        generated_day: str | None = None) -> pd.DataFrame:
    """Concatenate every candidates_<league>.csv (league inferred from filename),
    joining home/away from the matching predictions_<league>.csv when present.

    When ``generated_day`` is supplied, current-schema files are restricted to
    that UTC generation day. This prevents a league skipped by today's quota
    guard (or preserved after a transient failure) from appearing as a new pick
    merely because yesterday's candidates file still exists. Legacy files with
    no usable ``generated_at`` retain the prior behavior for compatibility.
    """
    frames = []
    for cf in sorted(predictions_dir.glob("candidates_*.csv")):
        league = cf.stem.replace("candidates_", "")
        c = pd.read_csv(cf)
        if c.empty:
            continue
        if generated_day and "generated_at" in c.columns:
            days = c["generated_at"].astype(str).str[:10]
            valid = days.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
            if valid.any():
                c = c[days == generated_day].copy()
                if c.empty:
                    continue
        c["league"] = league
        pf = predictions_dir / f"predictions_{league}.csv"
        if pf.exists() and pf.stat().st_size > 1:
            p = pd.read_csv(pf, usecols=lambda x: x in ("event_id", "home", "away", "start_time"))
            c = c.merge(p, on="event_id", how="left")
        frames.append(c)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def consolidated_report(predictions_dir: Path | None = None, top: int = 100) -> str:
    """Unified cross-league pick report: per-league summary + actionable ranking
    by estimated edge. Writes a timestamped markdown file and returns its path."""
    predictions_dir = predictions_dir or (ROOT / "data" / "predictions")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    day = ts[:8]
    generated_day = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
    df = load_all_candidates(predictions_dir, generated_day=generated_day)
    lines = [f"# Reporte consolidado de picks - {day}", f"Generado: {ts}", ""]
    if df.empty:
        lines += ["(sin candidatos generados)", "", f"> {DISCLAIMER}"]
    else:
        df["flags"] = df["flags"].fillna("") if "flags" in df.columns else ""
        # Visible = stake>0 or shadow (see rank_candidates): blocking flags zero
        # the stake AND hide the row; shadow zeroes the stake but stays visible.
        visible_mask = (df["stake"] > 0) | has_flag(df["flags"], "shadow_mode")
        summary = (df.assign(actionable=visible_mask)
                   .groupby("league")
                   .agg(candidatos=("selection", "size"),
                        accionables=("actionable", "sum"),
                        stake=("stake", "sum"))
                   .reset_index().sort_values("accionables", ascending=False))
        actionable = rank_candidates(df).head(top)
        if "home" in actionable.columns:
            actionable = actionable.assign(
                partido=actionable["away"].astype(str).str[:16] + " @ "
                + actionable["home"].astype(str).str[:16])
        cols = [c for c in ["league", "partido", "market", "selection", "line",
                            "price_decimal", "model_probability", "estimated_probability",
                            "implied_probability_novig", "estimated_edge", "stake"]
                if c in actionable.columns]
        lines += [
            "## Resumen por liga", summary.to_string(index=False), "",
            f"## Picks accionables (top {top}, ranked por edge estimado)",
            actionable[cols].to_string(index=False) if not actionable.empty else "(ninguno)",
            "",
            f"Total accionables: {len(rank_candidates(df))} | "
            f"no accionables (pausados / edge implausible, no apostados): "
            f"{int((~visible_mask).sum())}",
            "", f"> {DISCLAIMER}",
        ]
    outdir = predictions_dir
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"report_{day}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# --- Settlement audit ---------------------------------------------------------

def load_all_settled(bets_dir: Path) -> pd.DataFrame:
    frames = []
    for sf in sorted(bets_dir.glob("settled_*.csv")):
        s = pd.read_csv(sf)
        if not s.empty:
            s["league"] = sf.stem.replace("settled_", "")
            frames.append(s)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def graded_in_window(settled: pd.DataFrame, *, window_days: int,
                     today: date | None = None) -> pd.DataFrame:
    """Filas graduadas win/loss cuya fecha de partido (fallback generated_at)
    cae dentro de la ventana movil. Comparacion lexicografica ISO. Base comun
    del monitor de degradacion y el diagnostico por segmentos."""
    if settled.empty or "result" not in settled.columns:
        return settled.iloc[0:0]
    df = settled[settled["result"].isin(["win", "loss"])].copy()
    if df.empty:
        return df
    gd = df["game_date"].astype(str) if "game_date" in df.columns else pd.Series("", index=df.index)
    gen = df["generated_at"].astype(str) if "generated_at" in df.columns else pd.Series("", index=df.index)
    fecha = gd.where(gd.str.len() >= 10, gen).str[:10]
    cutoff = ((today or datetime.now(timezone.utc).date())
              - timedelta(days=window_days)).isoformat()
    return df[fecha >= cutoff]


def breakeven_probability(price_decimal: float | None) -> float | None:
    """Fraccion de aciertos necesaria para no perder dinero a esa cuota: 1/price.

    Es la vara con la que hay que medir un hit rate. A 2.50 basta 40%; a 1.07
    hacen falta 93.5%. Juzgar los picks contra un umbral fijo en vez de contra su
    propia cuota fue lo que llevo al modo accuracy a subir el porcentaje de
    aciertos perdiendo dinero (decision 2026-07-31).

    Devuelve None si la cuota no paga nada (<= 1.0): no hay equilibrio posible.
    """
    if price_decimal is None:
        return None
    try:
        p = float(price_decimal)
    except (TypeError, ValueError):
        return None
    if not p > 1.0 or p != p:  # <=1.0 o NaN
        return None
    return 1.0 / p


def _segment_audit(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    graded = df[df["result"].isin(["win", "loss"])].copy()
    if graded.empty:
        return pd.DataFrame()
    # Punto de equilibrio por pick, promediado por segmento: cuanto habria que
    # acertar para quedar en tablas con las cuotas realmente tomadas.
    if "price_decimal" in graded.columns:
        graded["_breakeven"] = graded["price_decimal"].map(breakeven_probability)
    else:
        graded["_breakeven"] = float("nan")  # historico antiguo sin la columna
    g = graded.groupby(by)
    out = g.agg(n=("result", "size"),
                wins=("result", lambda r: (r == "win").sum()),
                staked=("stake", "sum"),
                pnl=("pnl", "sum"),
                mean_est_edge=("estimated_edge", "mean"),
                mean_est_prob=("estimated_probability", "mean"),
                breakeven_hit_rate=("_breakeven", "mean")).reset_index()
    out["hit_rate"] = (out["wins"] / out["n"]).round(4)
    out["realized_roi"] = (out["pnl"] / out["staked"]).round(4)
    # La lectura de una sola cifra: positivo = se acerto MAS de lo que las cuotas
    # exigian; negativo = menos, por alto que parezca el hit rate absoluto.
    #
    # LIMITACION: `mean(1/precio)` es el equilibrio exacto solo si los aciertos se
    # reparten uniformemente entre cuotas. Si se concentran en las cuotas largas,
    # el gap puede salir negativo con ROI positivo -- verificado en datos reales
    # (totals: gap -2.0% con ROI +4.7%). El gap es la lectura interpretable; el
    # ROI realizado es la cifra autoritativa.
    out["hit_rate_vs_breakeven"] = (out["hit_rate"] - out["breakeven_hit_rate"]).round(4)
    out["breakeven_hit_rate"] = out["breakeven_hit_rate"].round(4)
    out["mean_est_edge"] = out["mean_est_edge"].round(4)
    out["mean_est_prob"] = out["mean_est_prob"].round(4)
    return out


def settlement_audit_report(bets_dir: Path | None = None) -> str:
    """Realized-ROI audit across all settled bets: overall, per league, per
    market, plus an estimated-edge vs realized-ROI reality check. Timestamped."""
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    df = load_all_settled(bets_dir)
    lines = [f"# Auditoria de liquidacion (ROI realizado) - {ts[:8]}",
             f"Generado: {ts}", ""]
    if df.empty:
        lines += ["(sin apuestas liquidadas todavia)", "", f"> {DISCLAIMER}"]
    else:
        graded = df[df["result"].isin(["win", "loss"])]
        staked = graded["stake"].sum()
        overall_roi = float(df["pnl"].sum() / staked) if staked else 0.0
        lines += [
            "## Global",
            f"Apuestas liquidadas (win/loss): {len(graded)} | "
            f"pushes/void: {len(df) - len(graded)}",
            f"Stake total: {staked:.2f} | PnL: {df['pnl'].sum():.2f} | "
            f"ROI realizado: {overall_roi:.2%}",
            "",
            "## Por liga", _segment_audit(df, ["league"]).to_string(index=False), "",
            "## Por mercado", _segment_audit(df, ["market"]).to_string(index=False), "",
            "## Estimado vs realizado (chequeo de calibracion)",
            "mean_est_prob deberia aproximar hit_rate; mean_est_edge deberia "
            "aproximar realized_roi si el modelo esta bien calibrado.", "",
            f"> {DISCLAIMER}",
        ]
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / f"audit_{ts[:8]}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


# --- History loader (closed + open union for dashboard) -----------------------

_HISTORY_COLS = ["fecha", "league", "market", "line", "home", "away",
                 "selection", "price_decimal", "stake", "result", "pnl", "is_closed"]


def _normalize_history(df: pd.DataFrame, *, fecha: pd.Series, is_closed: bool) -> pd.DataFrame:
    """Project a settled/candidate frame onto the common history columns."""
    out = pd.DataFrame(index=df.index)
    out["fecha"] = fecha.astype(str).str[:10]
    for col in ("league", "market", "home", "away", "selection", "result"):
        out[col] = df[col].astype(str) if col in df.columns else ""
    for col in ("line", "price_decimal", "stake", "pnl"):
        out[col] = pd.to_numeric(df[col], errors="coerce") if col in df.columns else float("nan")
    out["is_closed"] = is_closed
    return out[_HISTORY_COLS]


def load_history(predictions_dir: Path, bets_dir: Path) -> pd.DataFrame:
    """Union of closed (settled) bets and open actionable candidates, projected
    onto a common column set. Closed rows carry result/pnl; open rows do not.
    `fecha` is the game date (settled: game_date, fallback generated_at; open:
    start_time)."""
    frames = []
    closed = load_all_settled(bets_dir)
    if not closed.empty:
        gd = closed["game_date"] if "game_date" in closed.columns else pd.Series("", index=closed.index)
        gen = closed["generated_at"] if "generated_at" in closed.columns else pd.Series("", index=closed.index)
        fecha = gd.where(gd.astype(str).str.len() >= 10, gen)
        frames.append(_normalize_history(closed, fecha=fecha, is_closed=True))
    cands = load_all_candidates(predictions_dir)
    open_df = rank_candidates(cands) if not cands.empty else cands
    if not open_df.empty:
        st = open_df["start_time"] if "start_time" in open_df.columns else pd.Series("", index=open_df.index)
        frames.append(_normalize_history(open_df, fecha=st, is_closed=False))
    if not frames:
        return pd.DataFrame(columns=_HISTORY_COLS)
    return pd.concat(frames, ignore_index=True)


def visible_history(df: pd.DataFrame, today: str) -> pd.DataFrame:
    """Drop open rows (not closed) whose game date is in the past. Closed rows
    always shown; open rows shown only when fecha >= today."""
    if df.empty:
        return df
    keep = df["is_closed"] | (df["fecha"] >= today)
    return df[keep].reset_index(drop=True)
