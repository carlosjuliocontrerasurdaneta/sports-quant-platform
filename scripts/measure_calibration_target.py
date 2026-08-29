#!/usr/bin/env python
"""Ejecuta el pre-registro del 2026-08-24: objetivo de calibracion `_p_adj` vs crudo.

`docs/research/2026-08-24-preregistro-calibracion-train-serve.md` fijo el cambio
(entrenar el calibrador sobre `adjusted_probability`, la misma cantidad que
recibe al servir) Y su medicion de no-regresion. El cambio se implemento y esta
vivo; la medicion no se habia ejecutado nunca.

Metrica primaria y umbrales, copiados del pre-registro y NO reinventados aqui:

  - primaria : ECE OOS de la `calibrated_probability` REBLENDEADA
               `(1-s)*cal(.) + s*fair`, con s = `risk.market_shrink`.
  - aceptar  : el ECE OOS no empeora mas de +0.002 en NINGUN (liga, mercado) con
               n >= 200, y el Brier OOS no empeora mas de +0.001.
  - rechazar : cualquier corte que regrese sobre el umbral -> revertir `prob_col`
               a `model_probability` (la via correcta seria la Opcion B).

Split temporal por fecha de partido, con el holdout agrupado por evento: lo hace
`train_calibration`, que es la misma funcion que usa produccion, para que la
medicion no use un procedimiento distinto del que valida.

Solo lee datos guardados. No consume cuota de API, no toca el registro live ni
promueve nada.

  python scripts/measure_calibration_target.py
  python scripts/measure_calibration_target.py --min-n 200 --val-fraction 0.30
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

import sqp.calibration.calibrator as cal
from sqp.calibration.data import load_calibration_training_history
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import ROOT, Settings

# Umbrales del pre-registro. Cambiarlos invalida la prueba.
ECE_MAX_REGRESION = 0.002
BRIER_MAX_REGRESION = 0.001
MIN_N_CORTE = 200


def _reblend(calibrada: np.ndarray, fair: np.ndarray, s: float) -> np.ndarray:
    """`(1-s)*cal(.) + s*fair`, la probabilidad que de verdad se reporta."""
    fair = np.where(np.isfinite(fair), fair, calibrada)
    return (1.0 - s) * calibrada + s * fair


def _evaluar_corte(df: pd.DataFrame, objetivo: str, s: float,
                   val_fraction: float, tmp: Path) -> dict | None:
    """Entrena con `objetivo` sobre el tramo antiguo y puntua el reciente.

    Lo unico que cambia entre brazos es el OBJETIVO DE ENTRENAMIENTO. La
    aplicacion es siempre sobre `adjusted_probability`, porque es lo que hace
    `daily._decision_probability` al servir, y el pre-registro compara
    exactamente eso: entrenar sobre la cantidad que se sirve, frente a entrenar
    sobre la cruda y aplicarla igualmente a `_p_adj` -- que es el desajuste
    train/serve que motivo el cambio. Aplicar cada calibrador a su propia
    columna mediria un sistema coherente que NUNCA existio, y convertiria el
    brazo "actual" en una ficcion.

    Devuelve None cuando el corte no da para un holdout temporal por eventos.
    """
    APLICADA = "adjusted_probability"
    marca = f"medicion_{objetivo}"
    try:
        res = cal.train_calibration(
            df, prob_col=objetivo, outcome_col="won", sport=marca,
            val_fraction=val_fraction, staging=True,
            time_col="date", group_col="event_id")
    except ValueError:
        return None
    # Reproducimos el mismo split para poder puntuar nosotros el holdout: el
    # orden es por fecha de partido y por grupos de evento enteros.
    d = df.dropna(subset=[objetivo, APLICADA, "won", "date"]).sort_values(
        "date", kind="stable")
    orden = (d.groupby("event_id", sort=False)["date"].min()
             .sort_values(kind="stable").index.tolist())
    corte = max(1, min(len(orden) - 1, int(len(orden) * (1.0 - val_fraction))))
    val = d[~d["event_id"].isin(set(orden[:corte]))]
    if val.empty:
        return None
    metodo = res.get("best_method")
    p = pd.to_numeric(val[APLICADA], errors="coerce").to_numpy(dtype=float)
    if metodo:
        p = cal.apply_calibration(p, sport=marca, method=metodo)
    fair = pd.to_numeric(val["implied_probability_novig"],
                         errors="coerce").to_numpy(dtype=float)
    y = val["won"].to_numpy(dtype=float)
    final = _reblend(p, fair, s)
    return {"n": int(len(val)), "eventos": int(val["event_id"].nunique()),
            "metodo": metodo or "no-op",
            "ece": float(expected_calibration_error(final, y)),
            "brier": float(np.mean((final - y) ** 2))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-n", type=int, default=MIN_N_CORTE)
    ap.add_argument("--val-fraction", type=float, default=0.20)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    s = float(Settings.load().risk.market_shrink)
    hist = load_calibration_training_history()
    if hist.empty:
        print("Sin historia graduada: nada que medir.")
        return 1
    hist = hist[hist["result"].isin(["win", "loss"])].copy()
    hist["won"] = (hist["result"] == "win").astype(float)
    if "implied_probability_novig" not in hist.columns:
        print("Falta `implied_probability_novig`: no se puede reblendear.")
        return 1

    filas = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Los calibradores de la medicion se escriben en un directorio temporal:
        # esto NO puede tocar staging ni el registro live.
        original = cal.MODELS_DIR
        cal.MODELS_DIR = tmp
        (tmp / "staging").mkdir(parents=True, exist_ok=True)
        try:
            for (liga, mercado), g in hist.groupby(["league", "market"]):
                if len(g) < args.min_n:
                    continue
                fila = {"liga": str(liga), "mercado": str(mercado), "n": len(g)}
                for etiqueta, objetivo in (("nuevo", "adjusted_probability"),
                                           ("actual", "model_probability")):
                    cal._load_calibrator.cache_clear()
                    r = _evaluar_corte(g, objetivo, s, args.val_fraction, tmp)
                    if r is None:
                        fila = None
                        break
                    fila[f"ece_{etiqueta}"] = r["ece"]
                    fila[f"brier_{etiqueta}"] = r["brier"]
                    fila[f"metodo_{etiqueta}"] = r["metodo"]
                    fila["n_val"] = r["n"]
                    fila["eventos_val"] = r["eventos"]
                if fila:
                    filas.append(fila)
        finally:
            cal.MODELS_DIR = original
            cal._load_calibrator.cache_clear()

    if not filas:
        print("Ningun (liga, mercado) alcanza el minimo; nada que decidir.")
        return 1
    t = pd.DataFrame(filas)
    t["d_ece"] = t["ece_nuevo"] - t["ece_actual"]
    t["d_brier"] = t["brier_nuevo"] - t["brier_actual"]
    grandes = t[t["n_val"] >= args.min_n]
    regresiones = grandes[(grandes["d_ece"] > ECE_MAX_REGRESION)
                          | (grandes["d_brier"] > BRIER_MAX_REGRESION)]
    veredicto = "ACEPTAR" if regresiones.empty else "RECHAZAR"

    # POTENCIA de la prueba. Los dos brazos solo pueden diferir donde
    # `adjusted_probability != model_probability`; donde coinciden, el delta es 0
    # por construccion y no dice nada. Sin esta cifra, un tablero de ceros se
    # leeria como "no hay regresion" cuando en realidad es "no se ha medido".
    _a = pd.to_numeric(hist["adjusted_probability"], errors="coerce")
    _m = pd.to_numeric(hist["model_probability"], errors="coerce")
    difiere = (_a - _m).abs() > 1e-9
    frac = float(difiere.mean()) if len(hist) else 0.0

    lineas = [
        "# Resultado — objetivo de calibración `_p_adj` vs prob cruda",
        "",
        f"Generado: {date.today().isoformat()} · `market_shrink` = {s}",
        "Pre-registro: `docs/research/2026-08-24-preregistro-calibracion-train-serve.md`",
        "",
        f"Cortes evaluados: {len(t)} · con `n_val >= {args.min_n}`: {len(grandes)}",
        "",
        f"**Potencia de la prueba:** los dos objetivos difieren en "
        f"{int(difiere.sum())} de {len(hist)} filas graduadas ({frac:.2%}). "
        "Donde coinciden, el delta es 0 por construccion: con una fraccion baja, "
        "un veredicto favorable confirma la AUSENCIA DE REGRESION y no demuestra "
        "que el cambio ayude.",
        "",
        "Delta = nuevo (`adjusted_probability`) menos actual (`model_probability`).",
        "NEGATIVO = el objetivo nuevo es mejor. Umbrales del pre-registro: "
        f"ECE `+{ECE_MAX_REGRESION}`, Brier `+{BRIER_MAX_REGRESION}`.",
        "",
        # `to_markdown` exige `tabulate`, que no esta en `requirements.lock`
        # (misma razon que en `model_vs_market_report`).
        "```",
        t.round(5).to_string(index=False),
        "```",
        "",
        f"## Veredicto: **{veredicto}**",
        "",
    ]
    if regresiones.empty:
        lineas.append(
            "Ningún corte con `n_val` suficiente regresa sobre el umbral. Según "
            "la regla de decisión, el cambio se mantiene en STAGE; la promoción "
            "sigue exigiendo aprobación humana explícita y su propio gate.")
    else:
        lineas += [
            "Cortes que regresan sobre el umbral:", "",
            regresiones.round(5).to_string(index=False), "",
            "La regla de decisión manda revertir `prob_col` a "
            "`model_probability` y considerar la Opción B.",
        ]
    lineas += ["", "Estas son probabilidades ESTIMADAS y métricas de calibración "
               "sobre muestra histórica. No es una promesa de ganancia.", ""]
    informe = "\n".join(lineas)
    print(informe)
    out = args.out or ROOT / "audit" / f"calibration_target_{date.today():%Y%m%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(informe, encoding="utf-8")
    print(f"Escrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
