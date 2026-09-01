"""Closing Line Value (CLV) sobre las apuestas liquidadas.

CLV compara el precio al que se APOSTO contra el consenso de CIERRE del mercado
para el mismo evento/mercado/seleccion/linea. Ganarle al cierre de forma
consistente (CLV positivo) es el mejor predictor conocido de rentabilidad a
largo plazo; CLV negativo significa precios sistematicamente malos (perdida
estructural, no varianza). Es un diagnostico, no una promesa: el proxy de
cierre es el consenso mediano del ultimo snapshot capturado antes del comienzo
del evento — y solo si ese snapshot es reciente (CLOSE_MAX_AGE_MIN); un
snapshot matinal no es un cierre y produciria CLV=0 por construccion. La
cobertura queda limitada a lo que CAPTURE_CLOSE haya guardado.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.audit.report import DISCLAIMER, load_all_settled
from sqp.backtesting.roi_engine import load_closing_odds
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.pipeline.probabilities import _consensus_lines
from sqp.risk.clv_gate import CLV_GATE_MIN_N, gate_decisions, write_clv_gate

log = get_logger("sqp.clv")

# Regla de salida del shadow mode (2026-07-04), parte CLV: mediana positiva
# sobre al menos este numero de picks liquidados. La otra parte (gate de
# Brier) se evalua en la capa de calibracion.
SHADOW_EXIT_MIN_N = 100

# Frescura maxima del snapshot de cierre (minutos antes del comienzo) para que
# una apuesta cuente en el CLV. Auditoria 2026-07-12: sin este filtro, el 59%
# de las apuestas emparejadas tenia CLV exactamente 0 porque su "cierre" era el
# snapshot matinal (mediana de antiguedad ~2.8h, p75 >10h) — el mismo del que
# salio el precio de entrada — sesgando la mediana del gate hacia cero. Con
# captura horaria (CAPTURE_CLOSE, ventana 120 min) un snapshot a <=90 min del
# comienzo si es un proxy razonable de cierre.
CLOSE_MAX_AGE_MIN = 90.0

# Magnitud de CLV por encima de la cual la fila es sospechosa de un defecto de
# emparejamiento, no de un mal precio. Referencia empirica (2026-08-05): tras
# corregir KI-019 el peor CLV legitimo observado ronda el 6%, mientras que las
# dos filas contaminadas por precios EN VIVO daban -48.5% y -28.0%. El aviso
# NO descarta la fila: descartar en silencio es como se pierde evidencia.
CLV_IMPLAUSIBLE_PCT = 0.25


def _point(market: str, line) -> float | None:
    if market == "h2h":
        return None
    try:
        return None if pd.isna(line) else float(line)
    except (TypeError, ValueError):
        return None


def compute_clv(bets_dir: Path, root: Path,
                max_age_min: float | None = CLOSE_MAX_AGE_MIN
                ) -> tuple[pd.DataFrame, int]:
    """CLV por apuesta para cada apuesta liquidada (win/loss) emparejable a un
    precio de cierre capturado a lo sumo ``max_age_min`` minutos antes del
    comienzo (sin captura fresca la apuesta cuenta como sin_cierre). Devuelve
    (filas, n_sin_cierre); las filas traen league, market, selection, result,
    entry, close, clv_pct y beat_close."""
    settled = load_all_settled(bets_dir)
    if settled.empty:
        return pd.DataFrame(), 0
    settled = settled[settled["result"].isin(["win", "loss"])].copy()

    cons_cache: dict[str, dict] = {}
    for lg in sorted(settled["league"].unique()):
        odds = load_closing_odds(root, lg, max_age_min=max_age_min)
        cons_cache[lg] = {eid: _consensus_lines(eo) for eid, eo in odds.items()}

    rows: list[dict] = []
    unmatched = 0
    for r in settled.itertuples():
        cons = cons_cache.get(r.league, {}).get(str(r.event_id))
        close = None
        if cons:
            close = cons.get((str(r.market), str(r.selection),
                              _point(str(r.market), r.line)))
        if close is None or close <= 1.0:
            unmatched += 1
            continue
        entry = float(r.price_decimal)
        clv_pct = entry / float(close) - 1.0
        if not math.isfinite(clv_pct):
            log.warning(
                "CLV no finito en %s %s/%s (evento %s): entrada %r vs cierre "
                "%r. Precio ausente o corrupto en el origen; la fila se "
                "conserva con clv_pct no finito y SI cuenta en n y en "
                "beat_close_rate; si es inf tambien contamina mediana y media.",
                r.league, r.market, r.selection, str(r.event_id),
                entry, float(close))
        elif abs(clv_pct) >= CLV_IMPLAUSIBLE_PCT:
            log.warning(
                "CLV implausible %.1f%% en %s %s/%s (evento %s): entrada %.2f "
                "vs cierre %.2f. Revisar el emparejamiento entrada-cierre; la "
                "fila se conserva.",
                clv_pct * 100, r.league, r.market, r.selection,
                str(r.event_id), entry, float(close))
        gen = getattr(r, "generated_at", None)
        rows.append({
            "league": r.league, "market": r.market, "selection": r.selection,
            # claves de join para analisis aguas abajo (p.ej. CLV condicionado
            # al movimiento previo de linea): evento + linea + momento del pick
            "event_id": str(r.event_id), "line": r.line,
            "generated_at": "" if gen is None or pd.isna(gen) else str(gen),
            "result": r.result, "entry": entry, "close": float(close),
            "clv_pct": clv_pct,
            # Equality is neutral CLV, not "beating" the close. Counting ties as
            # wins inflated the observed beat-close rate (82.7% while the median
            # CLV was exactly zero in the audited dataset).
            "beat_close": entry > float(close),
        })
    return pd.DataFrame(rows), unmatched


def finite_clv(df: pd.DataFrame) -> pd.DataFrame:
    """Filas con `clv_pct` finito -- las unicas sobre las que se puede contar o
    promediar.

    `compute_clv` conserva a proposito las filas no finitas para que se vean.
    Agregando con `size` se cuentan filas sin informacion, `beat_close` queda en
    False para un NaN (`NaN > x` es False) y sesga la tasa a la baja, y con `inf`
    es peor: pandas NO lo ignora en median/mean, asi que UNA sola fila lleva la
    mediana a `inf` (auditoria 2026-08-05, F-02).

    El filtro estaba duplicado en `clv_segments` y en `clv_gate.gate_decisions`
    pero faltaba en el resumen global de `daily_clv` y, con el, en la REGLA DE
    SALIDA DEL SHADOW MODE, donde `inf > 0` es True: una sola fila con precio
    corrupto podia declarar cumplida la parte CLV de una decision de dinero real
    (auditoria 2026-08-31, N4-M-4). Se comparte para que no vuelva a faltar.
    """
    if df.empty:
        return df
    clv = pd.to_numeric(df["clv_pct"], errors="coerce")
    return df[clv.notna() & (clv != math.inf) & (clv != -math.inf)]


def clv_segments(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """n, CLV mediano/medio y % que batio el cierre por segmento."""
    if df.empty:
        return pd.DataFrame()
    # Ver `finite_clv`: el filtro es obligatorio antes de contar o promediar.
    # Solo filas informativas. Antes se agregaba con `size`, que CUENTA las no
    # finitas que median/mean saltan, asi que el n>=min_n del gate de CLV se
    # satisfacia con filas sin informacion; y beat_close quedaba en False para
    # un NaN (NaN > x es False), sesgando beat_close_rate a la baja. Peor con
    # inf: pandas NO lo ignora en median/mean, asi que una sola fila llevaba la
    # mediana a inf (auditoria 2026-08-05, F-02).
    df = finite_clv(df)
    if df.empty:
        return pd.DataFrame()
    out = (df.groupby(by)
             .agg(n=("clv_pct", "size"),
                  median_clv_pct=("clv_pct", "median"),
                  mean_clv_pct=("clv_pct", "mean"),
                  beat_close_rate=("beat_close", "mean"))
             .reset_index())
    for c in ("median_clv_pct", "mean_clv_pct", "beat_close_rate"):
        out[c] = out[c].round(4)
    return out


def daily_clv(bets_dir: Path | None = None, root: Path | None = None,
              gate_min_n: int = CLV_GATE_MIN_N) -> dict:
    """Calcula el CLV de todas las apuestas liquidadas, escribe el reporte
    markdown con fecha (data/bets/clv_YYYYMMDD.md, junto a la auditoria de
    liquidacion), reescribe el registro del gate por (liga, mercado)
    (data/bets/clv_gate.json, allow-list que consume el run diario) y devuelve
    un resumen para el log del run diario."""
    root = root or ROOT
    bets_dir = bets_dir or (root / "data" / "bets")
    df, unmatched = compute_clv(bets_dir, root)
    seg_lm = clv_segments(df, ["league", "market"])
    gate_path = write_clv_gate(seg_lm, bets_dir, gate_min_n)
    decided = gate_decisions(seg_lm, gate_min_n)
    gate_allowed = ([] if decided.empty else
                    sorted(f"{r.league}|{r.market}"
                           for r in decided.itertuples() if r.allowed))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [f"# CLV sobre apuestas liquidadas - {ts[:8]}", f"Generado: {ts}", ""]
    summary: dict = {"n_matched": int(len(df)), "n_unmatched": int(unmatched),
                     "median_clv_pct": None, "beat_close_rate": None,
                     "shadow_clv_ok": False, "gate_path": str(gate_path),
                     "gate_allowed": gate_allowed}
    if df.empty:
        lines += ["(ninguna apuesta liquidada pudo emparejarse a un precio de "
                  f"cierre capturado; sin_cierre={unmatched})", "",
                  "## Gate de CLV por (liga, mercado)",
                  "Registro reescrito sin mercados habilitados (default-deny): "
                  "ningun (liga, mercado) puede llevar stake real."]
    else:
        # El global y la regla de salida del shadow se miden SOLO sobre filas
        # finitas, igual que los segmentos y el gate (N4-M-4). Sin esto una fila
        # con precio corrupto llevaba la mediana a `inf`, e `inf > 0` declaraba
        # cumplida la parte CLV de una decision de dinero real.
        fin = finite_clv(df)
        n_desc = int(len(df) - len(fin))
        med = float(fin["clv_pct"].median()) if not fin.empty else float("nan")
        beat = float(fin["beat_close"].mean()) if not fin.empty else float("nan")
        summary.update(median_clv_pct=med, beat_close_rate=beat,
                       n_finite=int(len(fin)), n_non_finite=n_desc,
                       shadow_clv_ok=(len(fin) >= SHADOW_EXIT_MIN_N and med > 0))
        lines += [
            "## Global",
            f"Emparejadas a cierre: {len(df)} | con CLV utilizable: {len(fin)}"
            + (f" | descartadas por CLV no finito: {n_desc}" if n_desc else "")
            + f" | sin cierre disponible: {unmatched}",
            f"CLV mediano: {med:+.2%} | CLV medio: {fin['clv_pct'].mean():+.2%} | "
            f"batio el cierre: {beat:.1%}",
            "",
            "## Regla de salida del shadow mode (parte CLV)",
            f"Requiere CLV mediano > 0 con n >= {SHADOW_EXIT_MIN_N} sobre filas "
            f"con CLV finito. Estado: n={len(fin)}, mediana={med:+.2%} -> "
            + ("CUMPLE la parte CLV (falta verificar el gate de Brier)"
               if summary["shadow_clv_ok"] else "aun NO cumple"),
            "",
            "## Gate de CLV por (liga, mercado)",
            f"Habilitados para stake real (mediana > 0 con n >= {gate_min_n}): "
            + (", ".join(gate_allowed) if gate_allowed else
               "ninguno (default-deny)"),
            decided.to_string(index=False), "",
            "## Por liga", clv_segments(df, ["league"]).to_string(index=False), "",
            "## Por mercado", clv_segments(df, ["market"]).to_string(index=False), "",
            "## Por resultado (con edge real, los ganadores baten mas el cierre)",
            clv_segments(df, ["result"]).to_string(index=False), "",
            "CLV positivo = entrada a mejor precio que el cierre. Proxy de "
            "cierre = consenso mediano capturado a <="
            f"{CLOSE_MAX_AGE_MIN:.0f} min del comienzo; apuestas sin captura "
            "fresca cuentan como sin_cierre (cobertura limitada).",
        ]
    lines += ["", f"> {DISCLAIMER}"]
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / f"clv_{ts[:8]}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    summary["path"] = str(path)
    return summary
