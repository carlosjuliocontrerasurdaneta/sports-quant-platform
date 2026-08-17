"""Revision del modelo por deporte: separa SESGO de SOBRECONFIANZA.

El Brier dice que un mercado va mal, no POR QUE. Este analisis lo descompone en
las dos patologias que tienen tratamiento distinto y parametro distinto:

  SESGO DIRECCIONAL -- el modelo apunta al lado equivocado de forma sistematica.
    Se mide como `sesgo = media(p_modelo) - frecuencia observada` POR LADO. Un
    sesgo de +0,10 en el Over significa que el modelo promete Overs que no
    ocurren. Parametro responsable: la MEDIA (avg_total, elo_home_adv,
    home_scoring_bonus, points_per_elo).

    CRITICO -- medirlo sobre el (liga, mercado) COMPLETO da exactamente 0,000
    siempre, y no porque no haya sesgo: el stream contiene AMBOS lados de cada
    mercado, sus probabilidades suman 1 y exactamente uno gana, asi que la media
    y la frecuencia se anulan por construccion. El sesgo solo existe POR LADO
    (over/under, home/away). Detectado y corregido el 2026-08-17.

  SOBRECONFIANZA -- el modelo apunta bien pero exagera la magnitud. Se mide con
    la PENDIENTE DE CALIBRACION: regresion logistica de y sobre logit(p_modelo).
      pendiente = 1  -> calibrado.
      pendiente < 1  -> SOBRECONFIADO (dice 0,80 cuando deberia decir 0,65).
      pendiente > 1  -> subconfiado (podria ser mas agresivo).
    Parametro responsable: la DISPERSION (margin_sigma, total_sigma,
    dispersion_k, tilt_scale).

    CRITICO -- la pendiente solo es interpretable si el modelo SEPARA. En
    spreads y totals las probabilidades se apinan alrededor de 0,50: el logit
    apenas varia y la regresion devuelve pendientes de -2,9 o +7,5 que son ruido,
    no diagnostico. Por eso se reporta `sd_logit` junto a la pendiente y los
    cortes con sd_logit < SD_LOGIT_MIN se marcan `sin_dispersion` en vez de
    diagnosticarse. Detectado y corregido el 2026-08-17.

La distincion importa porque son correcciones opuestas: subir sigma arregla la
sobreconfianza y no toca el sesgo; mover avg_total arregla el sesgo y no toca la
sobreconfianza. Confundirlas fue el patron del 2026-08-16, donde varios cortes
acertaban en MAS eventos que el mercado y aun asi perdian en Brier.

Base: el stream servido graduado (todos los lados priceados, sin sesgo de
seleccion). El mercado no-vig se mide igual, como referencia de que pendiente y
sesgo son alcanzables en ese mercado.

Solo lectura, cero consumo de cuota.

Uso:
    PYTHONPATH=src python audit/reproductions/model_review_by_sport.py
    PYTHONPATH=src python audit/reproductions/model_review_by_sport.py --min-n 100
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from sqp.calibration.metrics import brier_score
from sqp.config import ROOT
from sqp.storage.served_store import ServedStore

MODEL_COL = "model_probability"
MARKET_COL = "implied_probability_novig"
DEFAULT_MIN_N = 60
_EPS = 1e-6
# Por debajo de esta dispersion en el logit, la pendiente es ruido: el modelo no
# separa lo suficiente para que la regresion diga nada. ~0.20 en logit son unos
# +-5 puntos porcentuales alrededor de 0.50.
SD_LOGIT_MIN = 0.20


def _side(df: pd.DataFrame) -> pd.Series:
    """Lado de la apuesta: over/under, home/away/draw. Es la unica dimension en
    la que el sesgo direccional puede verse (ver docstring del modulo)."""
    sel = df["selection"].astype(str).str.strip()
    home = df["home"].astype(str).str.strip()
    away = df["away"].astype(str).str.strip()
    low = sel.str.lower()
    out = pd.Series("otro", index=df.index, dtype=object)
    out[low == "over"] = "over"
    out[low == "under"] = "under"
    out[low == "draw"] = "draw"
    out[(out == "otro") & (sel == home)] = "home"
    out[(out == "otro") & (sel == away)] = "away"
    return out


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, _EPS, 1 - _EPS)
    return np.log(p / (1 - p))


def calibration_slope(probs: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(pendiente, intercepto) de la regresion logistica de y sobre logit(p).

    Pendiente 1 e intercepto 0 = perfectamente calibrado. Necesita ambas clases
    presentes; si no, no hay nada que ajustar."""
    if len(np.unique(y)) < 2 or len(y) < 10:
        return float("nan"), float("nan")
    x = _logit(probs).reshape(-1, 1)
    # C alto = practicamente sin regularizacion: queremos el ajuste crudo, no un
    # encogimiento que enmascare justo lo que buscamos medir.
    m = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000).fit(x, y)
    return float(m.coef_[0][0]), float(m.intercept_[0])


def diagnose(g: pd.DataFrame, col: str) -> dict:
    p = pd.to_numeric(g[col], errors="coerce")
    ok = p.notna() & (p >= 0) & (p <= 1)
    p, y = p[ok].to_numpy(float), g["y"][ok].to_numpy(int)
    if len(p) == 0:
        return {"n": 0}
    slope, intercept = calibration_slope(p, y)
    return {"n": len(p), "p_medio": float(p.mean()), "obs": float(y.mean()),
            "sesgo": float(p.mean() - y.mean()), "pendiente": slope,
            "intercepto": intercept, "brier": brier_score(p, y),
            "sd_logit": float(_logit(p).std())}


def _verdict(pendiente: float, sd_logit: float, *, pend_min: float) -> str:
    """Etiqueta la patologia de MAGNITUD. El sesgo no entra aqui: solo es
    visible por lado, y va en la tabla aparte."""
    if pd.isna(pendiente) or pd.isna(sd_logit):
        return "sin_datos"
    if sd_logit < SD_LOGIT_MIN:
        return "sin_dispersion"
    if pendiente < pend_min:
        return "SOBRECONFIADO"
    if pendiente > 1.0 / pend_min:
        return "subconfiado"
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    ap.add_argument("--sesgo-max", type=float, default=0.05,
                    help="|sesgo| por encima del cual se marca (default 0.05)")
    ap.add_argument("--pendiente-min", type=float, default=0.80,
                    help="pendiente por debajo de la cual se marca (default 0.80)")
    args = ap.parse_args()

    raw = ServedStore(ROOT).load_all_graded()
    if raw.empty or "result" not in raw.columns:
        print("No hay stream servido graduado. Nada que revisar.")
        return 1
    df = raw[raw["result"].isin(["win", "loss"])].copy()
    df["y"] = (df["result"] == "win").astype(int)
    df["lado"] = _side(df)
    print(f"Filas resueltas: {len(df)}  |  min n por corte: {args.min_n}")

    print("\n" + "=" * 78)
    print("MAGNITUD — pendiente de calibracion (< 1 = SOBRECONFIADO, exagera)")
    print("=" * 78)
    filas = []
    for (lg, mk), g in df.groupby(["league", "market"]):
        if len(g) < args.min_n:
            continue
        mod = diagnose(g, MODEL_COL)
        mkt = diagnose(g, MARKET_COL)
        if not mod.get("n"):
            continue
        filas.append({
            "liga": lg, "mercado": mk, "n": mod["n"],
            "sd_logit": mod["sd_logit"], "pendiente": mod["pendiente"],
            "brier": mod["brier"], "brier_mkt": mkt.get("brier", float("nan")),
            "diagnostico": _verdict(mod["pendiente"], mod["sd_logit"],
                                    pend_min=args.pendiente_min)})
    if not filas:
        print(f"Ningun corte llega a {args.min_n} filas.")
        return 0

    out = pd.DataFrame(filas).sort_values(["mercado", "liga"])
    print(out.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    print("\n" + "=" * 78)
    print("SESGO DIRECCIONAL — por LADO (unica dimension donde es visible)")
    print("=" * 78)
    sesgos = []
    for (lg, mk, sd), g in df.groupby(["league", "market", "lado"]):
        if len(g) < args.min_n or sd == "otro":
            continue
        d = diagnose(g, MODEL_COL)
        m = diagnose(g, MARKET_COL)
        if not d.get("n"):
            continue
        # EXCESO sobre el mercado: lo unico atribuible al modelo. Si el mercado
        # se equivoca en la misma direccion, ese trozo del sesgo es propiedad de
        # la ventana (temporada corta, racha) y no un parametro mal puesto:
        # "corregirlo" seria ajustar el modelo al ruido de estos meses.
        exceso = d["sesgo"] - m.get("sesgo", float("nan"))
        sesgos.append({"liga": lg, "mercado": mk, "lado": sd, "n": d["n"],
                       "p_medio": d["p_medio"], "obs": d["obs"],
                       "sesgo": d["sesgo"],
                       "sesgo_mkt": m.get("sesgo", float("nan")),
                       "exceso": exceso,
                       "marca": ("EXCESO" + ("+" if exceso > 0 else "-")
                                 if abs(exceso) > args.sesgo_max else "ok")})
    if sesgos:
        sdf = pd.DataFrame(sesgos).sort_values("exceso", key=abs, ascending=False)
        print(sdf.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    else:
        print("Sin cortes con muestra suficiente por lado.")

    print("\n" + "=" * 78)
    print("RESUMEN POR PATOLOGIA")
    print("=" * 78)
    for etiqueta, sub in (
            ("SOBRECONFIADOS (subir dispersion)",
             out[out["diagnostico"] == "SOBRECONFIADO"]),
            ("Subconfiados (podria ser mas agresivo)",
             out[out["diagnostico"] == "subconfiado"]),
            ("SIN DISPERSION (el modelo no separa; la pendiente no dice nada)",
             out[out["diagnostico"] == "sin_dispersion"]),
            ("Sanos", out[out["diagnostico"] == "ok"])):
        nombres = [f"{r.liga}/{r.mercado}" for r in sub.itertuples()]
        print(f"\n{etiqueta}: {len(sub)}")
        if nombres:
            print("  " + ", ".join(nombres))
    if sesgos:
        marcados = sdf[sdf["marca"] != "ok"]
        print(f"\nSESGO EN EXCESO sobre el mercado (mover la media): "
              f"{len(marcados)}")
        if len(marcados):
            print("  " + ", ".join(f"{r.liga}/{r.mercado}/{r.lado} "
                                   f"({r.exceso:+.3f})"
                                   for r in marcados.itertuples()))

    print("\nProbabilidades ESTIMADAS. Los umbrales marcan donde mirar, "
          "no significancia estadistica.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
