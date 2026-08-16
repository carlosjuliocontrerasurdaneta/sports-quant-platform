"""Mide la PREDICCION contra la REALIDAD, sin mercado de por medio.

Responde la pregunta del objetivo del sistema: las probabilidades pregame que
emite, ¿son mejores que no saber nada? Hasta ahora todas las mediciones del
proyecto (CLV, model_vs_market, value scanning) comparaban contra el mercado,
que es una pregunta distinta: mide rendimiento contra un precio, no veracidad.

Dataset: el STREAM SERVIDO graduado (``data/bets/served/graded_*.csv``), no los
picks. Los picks son una muestra pequeña y adversamente seleccionada; el stream
contiene TODOS los lados priceados con su probabilidad, antes de cualquier
filtro de edge o stake, graduados por la liquidacion. Es la unica base sin sesgo
de seleccion que existe en el repositorio.

Se evalua cada estimador contra tres baselines. El sistema solo "predice" algo
si bate a los tres:

  1. constante 0.50            -- no saber nada.
  2. tasa base del segmento    -- saber solo con que frecuencia gana ese lado,
                                  calculada IN-SAMPLE (favorable al baseline: si
                                  el modelo no la bate, el resultado es rotundo).
  3. mercado no-vig            -- referencia, no baseline: dice si ademas se
                                  puede cobrar, que es otra propiedad.

Estimadores medidos (las tres columnas que el pipeline persiste por fila):
  model_probability       p_model puro, sin calibrar y SIN mezcla de mercado.
  estimated_probability   la mezcla cruda (1-s)*p_model + s*fair, s=market_shrink.
  calibrated_probability  la probabilidad con la que se decidio el pick.

Metricas: Brier, log loss y ECE (sqp.calibration.metrics, las mismas del resto
del sistema). Menor es mejor en Brier y log loss.

Solo lectura. No escribe en data/, no llama a ningun proveedor, no gasta cuota.

Uso:
    PYTHONPATH=src python audit/reproductions/prediction_vs_reality.py
    PYTHONPATH=src python audit/reproductions/prediction_vs_reality.py --min-n 50
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from sqp.calibration.metrics import brier_score, expected_calibration_error, log_loss
from sqp.config import ROOT
from sqp.storage.served_store import ServedStore

ESTIMATORS = {
    "modelo_puro": "model_probability",
    "mezcla_servida": "estimated_probability",
    "decision": "calibrated_probability",
}
MARKET_COL = "implied_probability_novig"
DEFAULT_MIN_N = 30


def load_graded(demo: bool = False) -> pd.DataFrame:
    """Todas las filas graduadas del stream servido, con su liga."""
    store = ServedStore(ROOT, demo=demo)
    frames = []
    for league in store.leagues():
        path = store.graded_path(league)
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if df.empty:
            continue
        df["league"] = league
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def to_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Filas resueltas win/loss con su resultado binario. Push y void fuera:
    no son eventos con verdad binaria y contaminarian el Brier."""
    if "result" not in df.columns:
        raise SystemExit("El stream graduado no tiene columna 'result'.")
    out = df[df["result"].isin(["win", "loss"])].copy()
    out["y"] = (out["result"] == "win").astype(int)
    return out


def _clean(probs: pd.Series, y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Pares (p, y) con p numerica y en [0, 1]. Cada estimador se evalua sobre
    las filas donde EL existe; el n se reporta por separado para que un
    estimador con menos cobertura no parezca mejor por evaluarse en menos."""
    p = pd.to_numeric(probs, errors="coerce")
    ok = p.notna() & (p >= 0.0) & (p <= 1.0)
    return p[ok].to_numpy(float), y[ok].to_numpy(int)


def score(probs: pd.Series, y: pd.Series) -> dict:
    p, yy = _clean(probs, y)
    if len(p) == 0:
        return {"n": 0, "brier": float("nan"), "log_loss": float("nan"),
                "ece": float("nan")}
    return {"n": len(p), "brier": brier_score(p, yy), "log_loss": log_loss(p, yy),
            "ece": expected_calibration_error(p, yy)}


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por estimador y baseline sobre el subconjunto recibido."""
    y = df["y"]
    rows = []
    for label, col in ESTIMATORS.items():
        if col not in df.columns:
            continue
        rows.append({"estimador": label, "tipo": "modelo", **score(df[col], y)})
    if MARKET_COL in df.columns:
        rows.append({"estimador": "mercado_novig", "tipo": "referencia",
                     **score(df[MARKET_COL], y)})
    # Baselines. Se evaluan sobre TODAS las filas resueltas del subconjunto.
    rows.append({"estimador": "baseline_0.50", "tipo": "baseline",
                 **score(pd.Series(0.5, index=df.index), y)})
    base_rate = float(y.mean())
    rows.append({"estimador": f"baseline_tasa_base ({base_rate:.3f})",
                 "tipo": "baseline",
                 **score(pd.Series(base_rate, index=df.index), y)})
    return pd.DataFrame(rows)


def sign_test_vs_market(df: pd.DataFrame) -> tuple[int, int, float]:
    """Test de signo PAREADO del modelo puro contra el mercado, fila a fila.

    Por fila: d = (p_mercado - y)^2 - (p_modelo - y)^2. d > 0 = el modelo erro
    menos EN ESE EVENTO. Pareado, asi que no lo afecta que unos partidos sean
    mas predecibles que otros. Empates exactos excluidos (misma convencion que
    el gate intradia, KI-020). Unilateral: la hipotesis es que el modelo gana.

    Devuelve (n_gana_modelo, n_no_empatadas, p_valor).
    """
    p_m = pd.to_numeric(df.get("model_probability"), errors="coerce")
    p_k = pd.to_numeric(df.get(MARKET_COL), errors="coerce")
    y = df["y"]
    ok = p_m.notna() & p_k.notna()
    if not ok.any():
        return 0, 0, float("nan")
    d = (p_k[ok] - y[ok]) ** 2 - (p_m[ok] - y[ok]) ** 2
    wins = int((d > 0).sum())
    n = int((d != 0).sum())
    if n == 0:
        return 0, 0, float("nan")
    from scipy.stats import binomtest
    return wins, n, float(binomtest(wins, n, 0.5, alternative="greater").pvalue)


def verdict(table: pd.DataFrame) -> tuple[str, str]:
    """Compara el mejor estimador del modelo contra el mejor baseline.
    Devuelve (veredicto, detalle). Criterio: Brier estrictamente menor."""
    modelo = table[table["tipo"] == "modelo"].dropna(subset=["brier"])
    base = table[table["tipo"] == "baseline"].dropna(subset=["brier"])
    if modelo.empty or base.empty:
        return "SIN DATOS", "no hay filas suficientes para comparar."
    mejor_m = modelo.loc[modelo["brier"].idxmin()]
    mejor_b = base.loc[base["brier"].idxmin()]
    delta = mejor_b["brier"] - mejor_m["brier"]
    detalle = (f"mejor modelo: {mejor_m['estimador']} (Brier {mejor_m['brier']:.4f}) "
               f"vs mejor baseline: {mejor_b['estimador']} "
               f"(Brier {mejor_b['brier']:.4f}) -> delta {delta:+.4f}")
    return ("PREDICE" if delta > 0 else "NO PREDICE"), detalle


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N,
                    help="minimo de filas resueltas para reportar un corte")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    raw = load_graded(demo=args.demo)
    if raw.empty:
        print("No hay stream servido graduado. Nada que medir.")
        return 1
    df = to_outcomes(raw)
    print(f"Filas graduadas: {len(raw)}  |  resueltas win/loss: {len(df)}")
    if df.empty:
        return 1

    print("\n" + "=" * 78)
    print("GLOBAL — la prediccion contra la realidad")
    print("=" * 78)
    glob = evaluate(df)
    print(glob.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    v, detalle = verdict(glob)
    print(f"\nVEREDICTO GLOBAL: {v}\n  {detalle}")

    print("\n" + "=" * 78)
    print(f"POR LIGA Y MERCADO (min n = {args.min_n})")
    print("=" * 78)
    resumen = []
    for (lg, mk), g in df.groupby(["league", "market"]):
        if len(g) < args.min_n:
            continue
        t = evaluate(g)
        vv, det = verdict(t)
        base = t[t["tipo"] == "baseline"].dropna(subset=["brier"])
        mercado = t[t["estimador"] == "mercado_novig"]
        # El corte que importa para el objetivo: el modelo PURO contra el
        # mercado. La mezcla y la decision ya contienen el precio dentro, asi
        # que compararlas contra el mercado no dice si el modelo aporta algo.
        puro = t[t["estimador"] == "modelo_puro"]
        b_puro = puro["brier"].iloc[0] if not puro.empty else float("nan")
        b_mkt = mercado["brier"].iloc[0] if not mercado.empty else float("nan")
        resumen.append({
            "liga": lg, "mercado": mk, "n": len(g),
            "brier_puro": b_puro,
            "brier_baseline": base["brier"].min() if not base.empty else float("nan"),
            "brier_mercado": b_mkt,
            "vs_baseline": vv,
            "bate_mercado": "SI" if (b_puro == b_puro and b_mkt == b_mkt
                                     and b_puro < b_mkt) else "no"}
            | dict(zip(("gana", "n_par", "p_valor"), sign_test_vs_market(g))))
    if not resumen:
        print(f"Ningun (liga, mercado) llega a {args.min_n} filas resueltas.")
    else:
        out = pd.DataFrame(resumen).sort_values(["bate_mercado", "n"],
                                                ascending=[False, False])
        print(out.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        n_ok = int((out["vs_baseline"] == "PREDICE").sum())
        n_mkt = int((out["bate_mercado"] == "SI").sum())
        print(f"\nCortes que baten a su mejor baseline: {n_ok} de {len(out)}")
        print(f"Cortes donde el MODELO PURO bate al mercado: {n_mkt} de {len(out)}")
        print("  (lo primero dice que el sistema predice; lo segundo es lo unico "
              "que puede pagar el vig)")
        # Correccion por comparaciones multiples: con 25 cortes a p<0.05 se
        # esperan ~1.25 falsos positivos. Bonferroni es conservador a proposito;
        # el proyecto ya se quemo con un bucket aislado (KI-019).
        alpha = 0.05
        bonf = alpha / max(len(out), 1)
        sig = out[out["p_valor"] < alpha]
        sig_b = out[out["p_valor"] < bonf]
        print("\nTest de signo pareado vs mercado (unilateral):")
        print(f"  p < {alpha}: {len(sig)} corte(s)  ->  "
              f"{', '.join(f'{r.liga}/{r.mercado}' for r in sig.itertuples()) or 'ninguno'}")
        print(f"  p < {bonf:.4f} (Bonferroni, {len(out)} cortes): {len(sig_b)} corte(s)  ->  "
              f"{', '.join(f'{r.liga}/{r.mercado}' for r in sig_b.itertuples()) or 'ninguno'}")

    print("\nProbabilidades ESTIMADAS. Brier/log loss menores son mejores. "
          "Batir un baseline no implica rentabilidad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
