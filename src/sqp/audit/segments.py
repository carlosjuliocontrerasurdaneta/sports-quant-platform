"""Diagnostico automatico por segmentos sobre la ventana movil de liquidadas.

Complementa el monitor de degradacion (sqp.risk.degradation, que decide por
(liga, mercado) completo): aqui se corta cada (liga, mercado) en segmentos y
se compara probabilidad estimada media vs frecuencia observada (gap), Brier
del modelo vs baseline del mercado y ROI a stake plano, para localizar DONDE
vive una desviacion sistematica (p.ej. el sesgo Under de WNBA del 2026-07-04,
que hasta ahora requeria una sesion de analisis manual).

Dimensiones:
- favorito: favorito / underdog segun la probabilidad implicita sin vig.
- lado: local / visita / over / under / empate segun la seleccion.
- banda_prob: bandas fijas de probabilidad estimada.
- banda_linea: terciles de la linea dentro de cada (liga, mercado).

Solo observabilidad: NO pausa ni ajusta nada (eso es del monitor de
degradacion); escribe un reporte markdown con las desviaciones flageadas al
frente y un CSV estable para el dashboard. Lenguaje: siempre probabilidades
estimadas, nunca certezas.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sqp.audit.report import DISCLAIMER, graded_in_window, load_all_settled
from sqp.config import ROOT
from sqp.evaluation.labels import decision_prob as _labels_decision_prob

DEFAULT_WINDOW_DAYS = 60
# Minimo por SEGMENTO para flagear (mas bajo que el gate de pausa: esto solo
# senala donde mirar, no actua).
SEGMENTS_MIN_N = 15
GAP_THRESHOLD = 0.07     # |frecuencia observada - probabilidad estimada media|
BRIER_MARGIN = 0.01      # mismo margen vs mercado que el monitor de degradacion

# La region >= 0.70 va en bandas finas: es donde vive el modo precision
# (pick_mode: accuracy, umbral 0.70) y su KPI de cumplimiento del umbral es
# hit rate observado vs probabilidad estimada media POR BANDA (decision
# 2026-07-27); una sola banda ">0.70" no distinguiria 0.72 de 0.88.
_PROB_BINS = [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
_PROB_LABELS = ["<0.40", "0.40-0.50", "0.50-0.60", "0.60-0.70",
                "0.70-0.80", "0.80-0.90", ">0.90"]
_LINE_LABELS = ["linea_baja", "linea_media", "linea_alta"]
_TABLE_COLS = ["league", "market", "dimension", "segment", "n", "hit_rate",
               "mean_est_prob", "gap", "brier_model", "brier_market",
               "roi_flat", "flags"]
SEGMENTS_CSV = "segment_diagnostics_latest.csv"


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(float("nan"), index=df.index)


def _text(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].fillna("").astype(str)
    return pd.Series("", index=df.index)


# La probabilidad de decision se define UNA vez, en `evaluation.labels`, y la
# comparten esta auditoria, el tablero y el tipster. Vivia aqui como privada y
# las otras dos vistas acabaron midiendo sobre la probabilidad cruda (auditoria
# 2026-08-31, A-01).
decision_prob = _labels_decision_prob


def _line_bands(line: pd.Series, league: pd.Series, market: pd.Series) -> pd.Series:
    """Terciles de la linea DENTRO de cada (liga, mercado): una linea de 8.5 es
    alta en MLB y absurda en NBA, asi que las bandas nunca cruzan grupos."""
    out = pd.Series(None, index=line.index, dtype=object)
    if not line.notna().any():
        return out
    for _, idx in line.groupby([league, market]).groups.items():
        vals = line.loc[idx]
        if vals.notna().sum() < 3 or vals.nunique() < 3:
            continue
        try:
            out.loc[idx] = pd.qcut(vals, 3, labels=_LINE_LABELS,
                                   duplicates="drop").astype(object)
        except ValueError:
            continue
    return out


def segment_dimensions(df: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    """Las series de segmento por fila (None = fila fuera de la dimension)."""
    implied = _num(df, "implied_probability_novig")
    est = decision_prob(df)
    sel = _text(df, "selection")
    home, away = _text(df, "home"), _text(df, "away")
    sel_low = sel.str.lower()
    # Centinela "" -> None al final: np.where/np.select no tipan bien con None.
    favorito = pd.Series(
        np.select([implied.isna(), implied >= 0.5], ["", "favorito"],
                  default="underdog"),
        index=df.index, dtype=object).map(lambda v: v or None)
    lado = pd.Series(
        np.select(
            [sel_low == "over", sel_low == "under", sel == "Draw",
             (home != "") & (sel == home), (away != "") & (sel == away)],
            ["over", "under", "empate", "local", "visita"], default=""),
        index=df.index, dtype=object).map(lambda v: v or None)
    banda_prob = pd.cut(est, _PROB_BINS, labels=_PROB_LABELS,
                        include_lowest=True).astype(object)
    banda_linea = _line_bands(_num(df, "line"), _text(df, "league"),
                              _text(df, "market"))
    return [("favorito", favorito), ("lado", lado),
            ("banda_prob", banda_prob), ("banda_linea", banda_linea)]


def segment_table(settled: pd.DataFrame, *,
                  window_days: int = DEFAULT_WINDOW_DAYS,
                  today: date | None = None,
                  min_n: int = SEGMENTS_MIN_N,
                  gap_threshold: float = GAP_THRESHOLD,
                  brier_margin: float = BRIER_MARGIN) -> pd.DataFrame:
    """Tabla por (liga, mercado, dimension, segmento): n, frecuencia observada,
    probabilidad estimada media, gap (observada - estimada; negativo =
    sobreconfianza), Brier modelo vs mercado, ROI a stake plano, y flags para
    los segmentos con n >= min_n que muestran desviacion sistematica."""
    df = graded_in_window(settled, window_days=window_days, today=today)
    if df.empty:
        return pd.DataFrame(columns=_TABLE_COLS)
    y = (df["result"] == "win").astype(float)
    # Misma base que banda_prob: gap y Brier del modelo se miden sobre la
    # probabilidad que decidio el pick (calibrada si existe).
    est = decision_prob(df)
    implied = _num(df, "implied_probability_novig")
    price = _num(df, "price_decimal")
    base = df.assign(_y=y, _est=est, _se_model=(est - y) ** 2,
                     _se_market=(implied - y) ** 2,
                     _pnl_flat=(price - 1.0).where(y > 0, -1.0))
    rows = []
    for dim_name, seg in segment_dimensions(df):
        tmp = base.assign(_seg=seg)
        tmp = tmp[tmp["_seg"].notna()]
        if tmp.empty:
            continue
        for (lg, mk, sg), g in tmp.groupby(["league", "market", "_seg"]):
            n = int(len(g))
            hit = float(g["_y"].mean())
            mep = float(g["_est"].mean())
            gap = hit - mep
            brier_model = float(g["_se_model"].mean())
            brier_market = float(g["_se_market"].mean())
            flags = []
            if n >= min_n:
                if gap <= -gap_threshold:
                    flags.append("sobreconfianza")
                elif gap >= gap_threshold:
                    flags.append("subconfianza")
                if (pd.notna(brier_model) and pd.notna(brier_market)
                        and brier_model > brier_market + brier_margin):
                    flags.append("peor_que_mercado")
            rows.append({
                "league": str(lg), "market": str(mk), "dimension": dim_name,
                "segment": str(sg), "n": n, "hit_rate": round(hit, 4),
                "mean_est_prob": round(mep, 4), "gap": round(gap, 4),
                "brier_model": round(brier_model, 4),
                "brier_market": (round(brier_market, 4)
                                 if pd.notna(brier_market) else float("nan")),
                "roi_flat": round(float(g["_pnl_flat"].mean()), 4),
                "flags": ";".join(flags),
            })
    return pd.DataFrame(rows, columns=_TABLE_COLS)


def segment_diagnostics_report(bets_dir: Path | None = None, *,
                               window_days: int = DEFAULT_WINDOW_DAYS,
                               min_n: int = SEGMENTS_MIN_N,
                               gap_threshold: float = GAP_THRESHOLD,
                               brier_margin: float = BRIER_MARGIN,
                               today: date | None = None) -> str:
    """Reporte diario del diagnostico: markdown con las desviaciones flageadas
    al frente + tabla completa, y CSV estable (segment_diagnostics_latest.csv)
    para consumo del dashboard. Devuelve la ruta del markdown."""
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    tbl = segment_table(load_all_settled(bets_dir), window_days=window_days,
                        today=today, min_n=min_n, gap_threshold=gap_threshold,
                        brier_margin=brier_margin)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    flagged = tbl[tbl["flags"] != ""] if not tbl.empty else tbl
    lines = [
        f"# Diagnostico por segmentos - {ts[:8]}",
        f"Generado: {ts} | ventana: {window_days} dias | min_n por segmento: "
        f"{min_n} | umbral de gap: {gap_threshold} | margen Brier: {brier_margin}",
        "",
        "gap = frecuencia observada - probabilidad estimada media (negativo = "
        "sobreconfianza). roi_flat = ROI realizado a stake plano de 1 unidad "
        "por pick (los stakes reales son 0 bajo shadow). Solo observabilidad: "
        "las pausas las decide el monitor de degradacion por mercado completo.",
        "",
        f"## Desviaciones detectadas (n >= {min_n})",
        flagged.to_string(index=False) if not flagged.empty else "(ninguna)",
        "",
        "## Tabla completa por segmento",
        tbl.to_string(index=False) if not tbl.empty else "(sin liquidadas en ventana)",
        "",
        f"> {DISCLAIMER}",
    ]
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / f"segment_diagnostics_{ts[:8]}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    tbl.to_csv(bets_dir / SEGMENTS_CSV, index=False)
    return str(path)
