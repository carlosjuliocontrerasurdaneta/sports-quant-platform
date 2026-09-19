"""Research: sobredispersion de carreras MLB y coste del alpha del prompt 191.

Compara, sobre el MISMO recorrido walk-forward y los MISMOS lambda, tres
distribuciones del marcador por equipo:

    k = 3.8   produccion (Var = mu + mu^2/3.8, alpha equivalente 0.263)
    k = 6.667 prompt 191 v2 (NB_alpha = 0.15)
    k = None  Poisson puro (Var = mu)

Los tres adaptadores observan la misma secuencia de resultados, asi que sus
ratings (Elo, tasas de anotacion, park) son identicos y la UNICA diferencia
entre ellos es la distribucion. Mercados evaluados: moneyline, runline -1.5 y
totales en lineas fijas de referencia (sin cuotas: el desenlace sale del
marcador, asi que no hace falta historico de lineas).

Verifica ademas la dispersion empirica condicional Var(y|lambda)/lambda que
la auditoria 2026-07-31 fijo en 2.21.

Solo calibracion. Nunca inferir rentabilidad de estas metricas.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

from sqp.calibration.metrics import brier_score, log_loss
from sqp.domain.models import Event
from sqp.sports.registry import get_adapter

RESULTS = Path("data/historical/results_mlb.csv")
RATINGS = Path("configs/leagues/ratings.yaml")
TOTAL_LINES = (7.5, 8.5, 9.5)
VARIANTS = {"prod_k3.8": 3.8, "prompt191_k6.667": 1 / 0.15, "poisson": None}


def _mlb_params() -> dict:
    cfg = yaml.safe_load(RATINGS.read_text(encoding="utf-8"))
    return dict(cfg.get("leagues", {}).get("mlb", {}))


def _score(probs: list[float], outcomes: list[float]) -> dict:
    return {"n": len(probs),
            "brier": brier_score(probs, outcomes),
            "log_loss": log_loss(probs, outcomes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warmup", type=int, default=200)
    args = ap.parse_args()

    df = pd.read_csv(RESULTS, dtype={"date": str}).sort_values("date", kind="stable")
    rows = df.to_dict("records")
    base = _mlb_params()
    print(f"partidos={len(rows)} rango={df.date.min()}..{df.date.max()} warmup={args.warmup}")
    print(f"params mlb (ratings.yaml) = {base}\n")

    adapters = {name: get_adapter("mlb", "baseball", {**base, "dispersion_k": k})
                for name, k in VARIANTS.items()}
    # Series por variante y mercado.
    acc = {name: {"ml": ([], []), "rl": ([], []),
                  **{f"tot{t}": ([], []) for t in TOTAL_LINES}}
           for name in VARIANTS}
    # Dispersion empirica condicional, con los lambda de produccion.
    disp_terms: list[float] = []

    prod = adapters["prod_k3.8"]
    for i, r in enumerate(rows):
        if i >= args.warmup:
            ev = Event(event_id=str(i), sport_key="bt", league="mlb",
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label="real",
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            margin = r["home_score"] - r["away_score"]
            total = r["home_score"] + r["away_score"]
            y_ml = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)
            lam_h, lam_a = prod._rates(ev)
            for y, lam in ((r["home_score"], lam_h), (r["away_score"], lam_a)):
                disp_terms.append((y - lam) ** 2 / lam)
            for name, ad in adapters.items():
                est = ad.estimate(ev, -1.5, None)
                if y_ml in (0.0, 1.0):  # empates no existen en MLB, guarda defensiva
                    acc[name]["ml"][0].append(est.home_win_estimated_probability)
                    acc[name]["ml"][1].append(y_ml)
                acc[name]["rl"][0].append(est.home_cover_estimated_probability)
                acc[name]["rl"][1].append(1.0 if margin >= 2 else 0.0)
                for t in TOTAL_LINES:
                    e = ad.estimate(ev, None, t)
                    acc[name][f"tot{t}"][0].append(e.over_estimated_probability)
                    acc[name][f"tot{t}"][1].append(1.0 if total > t else 0.0)
        for ad in adapters.values():
            ad.observe(r)

    d_hat = sum(disp_terms) / len(disp_terms)
    print(f"[dispersion empirica condicional] Var(y|lambda)/lambda = {d_hat:.3f} "
          f"sobre {len(disp_terms)} equipos-partido")
    print("  Poisson exige 1.00. auditoria 2026-07-31 midio 2.21.")
    print(f"  k implicito = 1/(d-1) * ... -> alpha ~ {(d_hat - 1):.3f} / mu\n")

    markets = ["ml", "rl"] + [f"tot{t}" for t in TOTAL_LINES]
    print(f"{'mercado':<10} {'variante':<18} {'n':>6} {'brier':>9} {'log_loss':>9}")
    print("-" * 56)
    for m in markets:
        for name in VARIANTS:
            s = _score(*acc[name][m])
            print(f"{m:<10} {name:<18} {s['n']:>6} {s['brier']:>9.5f} {s['log_loss']:>9.5f}")
        print()


if __name__ == "__main__":
    main()
