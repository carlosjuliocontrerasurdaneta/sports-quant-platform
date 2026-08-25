"""Bootstrap agrupado por cluster: la unica inferencia valida en este proyecto.

El stream servido guarda LAS DOS caras de cada mercado (home y away, Over y
Under). Esas filas no son independientes: son la misma apuesta con el signo
cambiado. Tratarlas como independientes duplica el n efectivo, estrecha el
intervalo a ~1/sqrt(2) de su ancho real y fabrica significancia que no existe.

Todo intervalo publicado sobre el stream servido debe remuestrear CLUSTERS
enteros (evento, o evento+mercado), nunca filas. Este modulo es la unica
implementacion; `model_vs_market` y `edge_information` la comparten para que no
puedan divergir (la auditoria 2026-08-05 registro la divergencia de consenso
entre modulos como causa raiz recurrente).
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


def cluster_bootstrap_ci(values: np.ndarray, clusters: np.ndarray, *,
                         n_boot: int = 1000, seed: int = 42,
                         alpha: float = 0.05,
                         stat: Callable[[np.ndarray], float] | None = None,
                         ) -> tuple[float, float]:
    """IC bilateral del estadistico, remuestreando CLUSTERS enteros con reemplazo.

    `values` y `clusters` deben estar alineados fila a fila. `stat` opera sobre
    el vector remuestreado y por defecto es la media. Con menos de dos clusters
    distintos no hay variabilidad que estimar y se devuelve (nan, nan): un
    intervalo degenerado es preferible a uno de ancho cero que aparentaria
    certeza.
    """
    values = np.asarray(values, dtype=float)
    uniq = pd.unique(np.asarray(clusters))
    if len(uniq) < 2:
        return (float("nan"), float("nan"))
    agg = stat or (lambda v: float(np.mean(v)))
    idx_by_cluster = {c: np.flatnonzero(clusters == c) for c in uniq}
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        take = np.concatenate([idx_by_cluster[c] for c in chosen])
        draws[b] = agg(values[take])
    lo, hi = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))
