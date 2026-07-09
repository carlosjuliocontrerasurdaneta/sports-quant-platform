"""Closing Line Value (CLV) sobre las apuestas liquidadas.

CLV compara el precio al que se APOSTO contra el consenso de CIERRE del mercado
para el mismo evento/mercado/seleccion/linea. Ganarle al cierre de forma
consistente (CLV positivo) es el mejor predictor conocido de rentabilidad a
largo plazo; CLV negativo significa precios sistematicamente malos (perdida
estructural, no varianza). Es un diagnostico, no una promesa: el proxy de
cierre es el consenso mediano del ultimo snapshot capturado antes del comienzo
del evento, con cobertura limitada a lo que CAPTURE_CLOSE haya guardado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.audit.report import DISCLAIMER, load_all_settled
from sqp.backtesting.roi_engine import load_closing_odds
from sqp.config import ROOT
from sqp.pipeline.probabilities import _consensus_lines
from sqp.risk.clv_gate import CLV_GATE_MIN_N, gate_decisions, write_clv_gate

# Regla de salida del shadow mode (2026-07-04), parte CLV: mediana positiva
# sobre al menos este numero de picks liquidados. La otra parte (gate de
# Brier) se evalua en la capa de calibracion.
SHADOW_EXIT_MIN_N = 100


def _point(market: str, line) -> float | None:
    if market == "h2h":
        return None
    try:
        return None if pd.isna(line) else float(line)
    except (TypeError, ValueError):
        return None


def compute_clv(bets_dir: Path, root: Path) -> tuple[pd.DataFrame, int]:
    """CLV por apuesta para cada apuesta liquidada (win/loss) emparejable a un
    precio de cierre capturado. Devuelve (filas, n_sin_cierre); las filas traen
    league, market, selection, result, entry, close, clv_pct y beat_close."""
    settled = load_all_settled(bets_dir)
    if settled.empty:
        return pd.DataFrame(), 0
    settled = settled[settled["result"].isin(["win", "loss"])].copy()

    cons_cache: dict[str, dict] = {}
    for lg in sorted(settled["league"].unique()):
        odds = load_closing_odds(root, lg)
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
        rows.append({
            "league": r.league, "market": r.market, "selection": r.selection,
            "result": r.result, "entry": entry, "close": float(close),
            "clv_pct": entry / float(close) - 1.0,
            "beat_close": entry >= float(close),
        })
    return pd.DataFrame(rows), unmatched


def clv_segments(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """n, CLV mediano/medio y % que batio el cierre por segmento."""
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
        med = float(df["clv_pct"].median())
        beat = float(df["beat_close"].mean())
        summary.update(median_clv_pct=med, beat_close_rate=beat,
                       shadow_clv_ok=(len(df) >= SHADOW_EXIT_MIN_N and med > 0))
        lines += [
            "## Global",
            f"Emparejadas a cierre: {len(df)} | sin cierre disponible: {unmatched}",
            f"CLV mediano: {med:+.2%} | CLV medio: {df['clv_pct'].mean():+.2%} | "
            f"batio el cierre: {beat:.1%}",
            "",
            "## Regla de salida del shadow mode (parte CLV)",
            f"Requiere CLV mediano > 0 con n >= {SHADOW_EXIT_MIN_N}. Estado: "
            f"n={len(df)}, mediana={med:+.2%} -> "
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
            "cierre = consenso mediano capturado; cobertura limitada.",
        ]
    lines += ["", f"> {DISCLAIMER}"]
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / f"clv_{ts[:8]}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    summary["path"] = str(path)
    return summary
