"""Marcador: ¿nuestras probabilidades estimadas igualan a las del mercado?

Esta es la pregunta que plantea la idea fundacional del proyecto ("determinar la
probabilidad real con la mayor precision posible"), y hasta 2026-07-31 nunca se
habia medido.

Encuadre importante: aqui el mercado NO es el rival a batir para ganar dinero.
Es el **patron de medida**. La probabilidad sin vig del consenso es el mejor
estimador disponible de la probabilidad real de un partido, asi que "empatar con
el mercado" es un resultado legitimo y exigente, no un fracaso.

Metodo:
  - Se comparan Brier y log loss sobre las MISMAS filas (comparacion pareada).
    La diferencia pareada tiene mucha menos varianza que las puntuaciones
    sueltas, asi que detecta brechas pequenas con menos muestra.
  - `diff = modelo - mercado`. Brier mas bajo es mejor, luego **negativo =
    el modelo gana**.
  - El intervalo se calcula con bootstrap **agrupado por evento**: el stream
    servido guarda los dos lados de cada mercado, y esas filas estan
    perfectamente correlacionadas. Tratarlas como independientes reduciria el
    intervalo a la mitad y fabricaria significancia que no existe.

La fuente natural es `data/calibration/graded_<liga>.csv`, que captura todos los
lados con precio antes de cualquier filtro de stake: es la muestra insesgada, a
diferencia de las apuestas liquidadas (que son una seleccion adversa).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sqp.evaluation.bootstrap import cluster_bootstrap_ci

# Fuera de (0,1) el log loss es infinito y un solo caso arruinaria el segmento.
_EPS = 1e-6


def flattened_segments(df: pd.DataFrame, *, min_range: float = 0.10,
                       model_min_range: float = 0.20,
                       min_rows: int = 6) -> pd.DataFrame:
    """Segmentos servidos con la probabilidad CALIBRADA aplanada.

    Un dia-segmento cuenta como aplanado cuando el modelo discrimina
    (`model_probability` con recorrido > `model_min_range`) pero lo calibrado
    sale casi constante (recorrido < `min_range`). Es la huella de un calibrador
    colapsado en produccion, y hay que verla ANTES de leer el veredicto del
    segmento: lo que se puntuo ahi no es el modelo, es una constante.

    No es teorico. `wnba_totals` sirvio asi del 2026-07-22 al 2026-08-27 (34
    dias, 412 filas) y `mlb_totals` del 2026-07-28 al 2026-08-23 (14 dias, 342);
    en total 754 filas del stream, con sus veredictos por segmento calculados
    sobre un predictor plano. Ver `calibration.calibrator._keeps_resolution`.

    Devuelve una fila por (liga, mercado) afectado: dias, filas y ventana.
    Frame vacio -- el caso sano -- si no hay ninguno.
    """
    cols = {"league", "market", "generated_at", "calibrated_probability",
            "model_probability"}
    if df.empty or not cols.issubset(df.columns):
        return pd.DataFrame(columns=["league", "market", "dias", "filas",
                                     "desde", "hasta"])
    d = df.assign(_dia=df["generated_at"].astype(str).str[:10])
    g = d.groupby(["league", "market", "_dia"]).agg(
        filas=("calibrated_probability", "size"),
        cal_rec=("calibrated_probability", lambda s: s.max() - s.min()),
        mod_rec=("model_probability", lambda s: s.max() - s.min()))
    malo = g[(g["cal_rec"] < min_range) & (g["mod_rec"] > model_min_range)
             & (g["filas"] >= min_rows)].reset_index()
    if malo.empty:
        return pd.DataFrame(columns=["league", "market", "dias", "filas",
                                     "desde", "hasta"])
    return (malo.groupby(["league", "market"])
            .agg(dias=("_dia", "nunique"), filas=("filas", "sum"),
                 desde=("_dia", "min"), hasta=("_dia", "max"))
            .reset_index().sort_values("filas", ascending=False))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    """Error cuadratico medio entre probabilidad estimada y resultado (0/1)."""
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def log_loss_safe(p: np.ndarray, y: np.ndarray) -> float:
    """Log loss con recorte a [_EPS, 1-_EPS] para que sea siempre finito."""
    q = np.clip(np.asarray(p, float), _EPS, 1 - _EPS)
    t = np.asarray(y, float)
    return float(-np.mean(t * np.log(q) + (1 - t) * np.log(1 - q)))


def _cluster_bootstrap_ci(diff: np.ndarray, events: np.ndarray, *,
                          n_boot: int, seed: int,
                          alpha: float = 0.05) -> tuple[float, float]:
    """IC de la diferencia media, remuestreando EVENTOS enteros (no filas).

    Alias fino sobre `evaluation.bootstrap.cluster_bootstrap_ci`, que es la unica
    implementacion. Se conserva el nombre porque es el punto de entrada historico
    de este modulo.
    """
    return cluster_bootstrap_ci(diff, events, n_boot=n_boot, seed=seed, alpha=alpha)


def score_model_vs_market(df: pd.DataFrame,
                          by: list[str] | None = None,
                          *, n_boot: int = 1000, seed: int = 42,
                          model_col: str = "model_probability",
                          market_col: str = "implied_probability_novig") -> pd.DataFrame:
    """Brier y log loss del modelo frente al mercado, por segmento.

    `df` es el stream graduado: necesita `result` (win/loss), las dos columnas de
    probabilidad y `event_id` para agrupar el bootstrap. Pushes y voids se
    excluyen: no tienen un resultado binario que puntuar.
    """
    by = by or ["league", "market"]
    d = df[df["result"].isin(["win", "loss"])].copy()
    d = d.dropna(subset=[model_col, market_col])
    if d.empty:
        return pd.DataFrame()
    d["_y"] = (d["result"] == "win").astype(float)

    out = []
    for keys, g in d.groupby(by, dropna=False):
        pm = g[model_col].to_numpy(float)
        pk = g[market_col].to_numpy(float)
        y = g["_y"].to_numpy(float)
        # Diferencia por fila: base de la comparacion pareada y del bootstrap.
        row_diff = (pm - y) ** 2 - (pk - y) ** 2
        ev = g["event_id"].to_numpy() if "event_id" in g.columns else np.arange(len(g))
        lo, hi = _cluster_bootstrap_ci(row_diff, ev, n_boot=n_boot, seed=seed)
        rec = dict(zip(by, keys if isinstance(keys, tuple) else (keys,)))
        rec.update(
            n_rows=len(g),
            n_events=int(pd.unique(ev).size),
            brier_model=round(brier(pm, y), 5),
            brier_market=round(brier(pk, y), 5),
            brier_diff=round(float(row_diff.mean()), 5),
            brier_diff_lo=round(lo, 5),
            brier_diff_hi=round(hi, 5),
            logloss_model=round(log_loss_safe(pm, y), 5),
            logloss_market=round(log_loss_safe(pk, y), 5),
        )
        out.append(rec)
    res = pd.DataFrame(out)
    # Veredicto legible: el IC decide, no el punto estimado.
    res["veredicto"] = np.where(
        res["brier_diff_hi"] < 0, "modelo MEJOR",
        np.where(res["brier_diff_lo"] > 0, "mercado mejor", "equivalente (IC cruza 0)"))
    return res.sort_values("n_rows", ascending=False).reset_index(drop=True)
