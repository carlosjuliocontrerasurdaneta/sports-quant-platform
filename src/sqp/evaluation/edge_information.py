"""¿El edge que declara el modelo tiene valor realizado? — la prueba decisiva.

`model_vs_market` responde si nuestras probabilidades igualan a las del mercado.
Esta es la pregunta siguiente, y la que decide si el sistema puede ganar dinero:
**cuando el modelo dice que una cara esta infravalorada, ¿lo esta?**

La respuesta operativa no es una correlacion sino una escalera. Si el edge
declarado tuviera informacion, subir el umbral `min_edge` tendria que MEJORAR el
ROI realizado: estariamos quedandonos con las apuestas de mayor ventaja. Esa
monotonia es la firma de una ventaja real, y su ausencia —o su inversion— es la
firma de que el edge es error de medida del modelo, no ventaja.

Es la prueba que ninguna otra capa hace. La calibracion mide el acierto MEDIO
sobre todas las caras servidas; los gates miden el resultado DESPUES de filtrar.
Ninguna de las dos ve la relacion entre la magnitud del edge declarado y el ROI
realizado, que es exactamente donde vive el problema si el filtro de picks
selecciona al reves.

Fuente: `data/calibration/graded_*.csv` (`ServedStore.load_all_graded`), todas
las caras priceadas antes de cualquier filtro de stake. Las apuestas liquidadas
NO sirven: solo contienen edges que ya pasaron el umbral, asi que la escalera
quedaria truncada justo donde hay que medirla.

Inferencia: bootstrap agrupado por evento (`evaluation.bootstrap`). Sin el, las
dos caras de cada mercado se cuentan como observaciones independientes y el
intervalo aparenta la mitad de su ancho real.

Nada de este modulo es una promesa de ganancia: mide ROI realizado sobre muestra
historica y lo publica con su intervalo, que es lo unico defendible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sqp.evaluation.bootstrap import cluster_bootstrap_ci

# Escalera por defecto. Empieza en 0 (todo lo que el modelo considera favorable)
# y llega a 0.12: por encima, la muestra historica se queda sin filas utiles.
DEFAULT_THRESHOLDS: tuple[float, ...] = (0.0, 0.02, 0.05, 0.08, 0.12)
# Con menos filas que esto el ROI es anecdota, no medicion: se emite la fila con
# el intervalo en NaN en vez de omitirla, para que el hueco sea visible.
MIN_ROWS = 40


def prepare(df: pd.DataFrame, *,
            edge_col: str = "estimated_edge",
            prob_col: str = "calibrated_probability") -> pd.DataFrame:
    """Proyecta el stream graduado a las columnas que necesita el analisis.

    Conserva solo `win`/`loss`: push y void no tienen resultado binario ni P&L
    que puntuar. Si falta `edge_col` lo reconstruye como `p * precio - 1` sobre
    `prob_col`, que es la definicion que usa produccion.
    """
    needed = {"result", "price_decimal", "event_id"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"faltan columnas obligatorias: {sorted(missing)}")

    d = df[df["result"].isin(["win", "loss"])].copy()
    price = pd.to_numeric(d["price_decimal"], errors="coerce")
    if edge_col in d.columns:
        edge = pd.to_numeric(d[edge_col], errors="coerce")
    elif prob_col in d.columns:
        edge = pd.to_numeric(d[prob_col], errors="coerce") * price - 1.0
    else:
        raise ValueError(f"ni {edge_col!r} ni {prob_col!r} estan en el frame")

    d["_won"] = (d["result"] == "win").astype(float)
    d["_price"] = price
    d["_edge"] = edge
    # ROI flat: unidad apostada, se recupera precio-1 al ganar y se pierde 1 al
    # perder. Es el P&L de la politica, independiente del sizing de Kelly, que
    # solo escalaria el mismo signo.
    d["_roi"] = np.where(d["_won"] > 0, price - 1.0, -1.0)
    # Un valor no finito en precio o edge envenena media e intervalo sin avisar
    # (auditoria 2026-08-05, RC-1): se descarta explicitamente.
    finite = np.isfinite(d["_price"]) & np.isfinite(d["_edge"])
    return d[finite].reset_index(drop=True)


def _roi_ci(sub: pd.DataFrame, *, n_boot: int, seed: int) -> tuple[float, float]:
    if len(sub) < MIN_ROWS:
        return (float("nan"), float("nan"))
    return cluster_bootstrap_ci(sub["_roi"].to_numpy(), sub["event_id"].to_numpy(),
                                n_boot=n_boot, seed=seed)


def edge_ladder(df: pd.DataFrame, *,
                thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
                price_floor: float = 0.0,
                n_boot: int = 1000, seed: int = 42,
                **prep_kwargs: str) -> pd.DataFrame:
    """ROI realizado en funcion del umbral `min_edge`, con IC95 clusterizado.

    `price_floor` acota por probabilidad implicita sin vig minima: sirve para
    separar el efecto del edge del sesgo favorito-longshot, que mueve el ROI por
    su cuenta y puede imitar o esconder una escalera.

    Lectura: `roi_flat` creciente en `min_edge` = el edge declarado tiene valor.
    Plano = no lo tiene. Decreciente = el filtro de picks selecciona al reves y
    subir el umbral empeora el resultado.
    """
    d = prepare(df, **prep_kwargs)
    if "implied_probability_novig" in d.columns and price_floor > 0.0:
        keep = pd.to_numeric(d["implied_probability_novig"], errors="coerce")
        d = d[keep >= price_floor]

    rows = []
    for t in thresholds:
        sub = d[d["_edge"] >= t]
        lo, hi = _roi_ci(sub, n_boot=n_boot, seed=seed)
        rows.append({
            "min_edge": t,
            "price_floor": price_floor,
            "n_rows": len(sub),
            "n_events": int(sub["event_id"].nunique()),
            "hit_rate": round(float(sub["_won"].mean()), 5) if len(sub) else float("nan"),
            "roi_flat": round(float(sub["_roi"].mean()), 5) if len(sub) else float("nan"),
            "roi_lo": round(lo, 5),
            "roi_hi": round(hi, 5),
        })
    out = pd.DataFrame(rows)
    # El veredicto lo da el intervalo, nunca el punto estimado.
    out["veredicto"] = np.where(
        out["roi_lo"] > 0, "ROI positivo",
        np.where(out["roi_hi"] < 0, "ROI negativo", "indistinguible de 0"))
    return out


def edge_signal(df: pd.DataFrame, *, n_boot: int = 1000, seed: int = 42,
                **prep_kwargs: str) -> dict[str, float]:
    """Contraste directo: ROI donde el modelo apuesta vs donde no apostaria.

    `delta = ROI(edge > 0) - ROI(edge <= 0)`. Es el resumen de una linea de la
    escalera: positivo y con IC que excluye 0 = la seleccion aporta; negativo con
    IC que excluye 0 = la seleccion resta, y el sistema esta apostando
    sistematicamente el peor lado de cada mercado.

    El IC se obtiene remuestreando eventos enteros y recalculando la diferencia
    en cada replica, no restando dos intervalos independientes (que ignoraria la
    correlacion entre los dos grupos dentro del mismo evento).
    """
    d = prepare(df, **prep_kwargs)
    picked = d["_edge"] > 0
    a, b = d[picked], d[~picked]
    out = {
        "n_picked": float(len(a)), "n_rest": float(len(b)),
        "n_events": float(d["event_id"].nunique()),
        "roi_picked": float(a["_roi"].mean()) if len(a) else float("nan"),
        "roi_rest": float(b["_roi"].mean()) if len(b) else float("nan"),
    }
    out["delta"] = out["roi_picked"] - out["roi_rest"]

    if len(a) < MIN_ROWS or len(b) < MIN_ROWS:
        out["delta_lo"] = out["delta_hi"] = float("nan")
        return out

    roi = d["_roi"].to_numpy()
    mask = picked.to_numpy()
    # El estadistico se recalcula sobre cada remuestra; `cluster_bootstrap_ci`
    # remuestrea indices de fila, asi que se codifica el grupo en el signo del
    # indice pasandolo como columna paralela via closure sobre `order`.
    order = np.arange(len(d))

    def delta_of(idx: np.ndarray) -> float:
        sel = idx.astype(int)
        m = mask[sel]
        if m.all() or not m.any():
            return float("nan")
        return float(roi[sel][m].mean() - roi[sel][~m].mean())

    lo, hi = cluster_bootstrap_ci(order, d["event_id"].to_numpy(),
                                  n_boot=n_boot, seed=seed, stat=delta_of)
    out["delta_lo"], out["delta_hi"] = lo, hi
    return out
