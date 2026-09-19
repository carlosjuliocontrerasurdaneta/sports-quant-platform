#!/usr/bin/env python
"""Ejecuta el pre-registro del 2026-08-25: suelo de precio `p_novig >= 0.35`.

`docs/research/2026-08-25-preregistro-suelo-de-precio.md` congelo el umbral, la
ventana y la regla de decision ANTES de que la ventana tuviera datos. Este
script las aplica tal cual; no reinventa ninguna:

  - datos     : stream graduado (`data/calibration/graded_*.csv`), `win`/`loss`,
                `game_date` estrictamente posterior a 2026-08-25, colapsado a
                UNA fila por pick (`one_row_per_pick`, correccion del 08-27).
  - candidatos: `estimated_edge >= 0` (la regla de seleccion vigente).
  - brazo     : candidatos con `implied_probability_novig >= 0.35`.
  - n minimo  : 800 picks unicos y 250 eventos en el brazo; por debajo se espera.
  - primaria  : delta = ROI_plano(con suelo) - ROI_plano(sin suelo) sobre el
                mismo conjunto candidato, IC95 por bootstrap agrupado por evento
                (>= 3.000 replicas, seed 42).
  - ACEPTAR   : delta > 0 y el IC95 excluye el cero. Cualquier otro caso RECHAZA.
  - contraprueba obligatoria: el efecto por quintil de `p_novig`; si desaparece
                al condicionar, lo medido es el sesgo favorito-longshot.

Solo lee datos guardados. No consume cuota de API, no escribe en `data/` ni toca
`configs/`. Las cifras son ROI REALIZADO sobre muestra historica; ninguna es una
promesa de ganancia, y el propio pre-registro declara que su valor es acotar
donde vive el dano, no abrir una via de rentabilidad.

  python scripts/research/measure_price_floor_preregistration.py
  python scripts/research/measure_price_floor_preregistration.py --n-boot 4000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from sqp.config import ROOT  # noqa: E402
from sqp.evaluation.bootstrap import cluster_bootstrap_ci  # noqa: E402
from sqp.evaluation.edge_information import (DEFAULT_THRESHOLDS,  # noqa: E402
                                             edge_ladder, prepare)
from sqp.storage.served_store import ServedStore  # noqa: E402

# Fijados por el pre-registro; no son parametros del script a proposito.
PRICE_FLOOR = 0.35
WINDOW_AFTER = "2026-08-25"
MIN_PICKS = 800
MIN_EVENTS = 250


def _delta_ci(roi: np.ndarray, mask: np.ndarray, events: np.ndarray, *,
              n_boot: int, seed: int) -> tuple[float, float]:
    """IC del delta pareado: cada remuestra de eventos recalcula ambos brazos."""
    order = np.arange(len(roi))

    def delta_of(idx: np.ndarray) -> float:
        sel = idx.astype(int)
        m = mask[sel]
        if not m.any():
            return float("nan")
        return float(roi[sel][m].mean() - roi[sel].mean())

    return cluster_bootstrap_ci(order, events, n_boot=n_boot, seed=seed,
                                stat=delta_of)


def run(raw: pd.DataFrame, *, n_boot: int, seed: int) -> dict[str, object]:
    window = raw[raw["game_date"].astype(str) > WINDOW_AFTER]
    d = prepare(window)
    d["_novig"] = pd.to_numeric(d["implied_probability_novig"], errors="coerce")
    cand = d[(d["_edge"] >= 0) & np.isfinite(d["_novig"])].reset_index(drop=True)
    mask = (cand["_novig"] >= PRICE_FLOOR).to_numpy()
    roi = cand["_roi"].to_numpy()
    events = cand["event_id"].to_numpy()

    n_arm = int(mask.sum())
    ev_arm = int(cand.loc[mask, "event_id"].nunique())
    enough = n_arm >= MIN_PICKS and ev_arm >= MIN_EVENTS

    out: dict[str, object] = {
        "window": (str(window["game_date"].min()), str(window["game_date"].max())),
        "n_candidates": len(cand), "ev_candidates": int(cand["event_id"].nunique()),
        "n_arm": n_arm, "ev_arm": ev_arm, "enough": enough,
    }
    if not enough:
        out["verdict"] = "ESPERAR (muestra insuficiente)"
        return out

    roi_sin, roi_con = float(roi.mean()), float(roi[mask].mean())
    delta = roi_con - roi_sin
    lo, hi = _delta_ci(roi, mask, events, n_boot=n_boot, seed=seed)
    out.update({
        "roi_sin": roi_sin, "hit_sin": float(cand["_won"].mean()),
        "roi_sin_ci": cluster_bootstrap_ci(roi, events, n_boot=n_boot, seed=seed),
        "roi_con": roi_con, "hit_con": float(cand.loc[mask, "_won"].mean()),
        "roi_con_ci": cluster_bootstrap_ci(roi[mask], events[mask], n_boot=n_boot, seed=seed),
        "delta": delta, "delta_ci": (lo, hi),
        "verdict": "ACEPTAR" if (delta > 0 and lo > 0) else "RECHAZAR",
    })

    # Contraprueba: ROI por quintil de precio y delta dentro del quintil que el
    # suelo parte en dos (en los demas el filtro no actua y el delta es 0).
    cand["_q"] = pd.qcut(cand["_novig"], 5, labels=False, duplicates="drop")
    quintiles = []
    for q, sub in cand.groupby("_q"):
        r, e = sub["_roi"].to_numpy(), sub["event_id"].to_numpy()
        m = (sub["_novig"] >= PRICE_FLOOR).to_numpy()
        row = {
            "q": int(q) + 1, "novig_min": float(sub["_novig"].min()),
            "novig_max": float(sub["_novig"].max()), "n": len(sub),
            "roi": float(r.mean()),
            "roi_ci": cluster_bootstrap_ci(r, e, n_boot=n_boot, seed=seed),
            "frac_arm": float(m.mean()), "delta": float("nan"),
            "delta_ci": (float("nan"), float("nan")),
        }
        if m.any() and not m.all():
            row["delta"] = float(r[m].mean() - r.mean())
            row["delta_ci"] = _delta_ci(r, m, e, n_boot=n_boot, seed=seed)
        quintiles.append(row)
    out["quintiles"] = quintiles

    out["ladders"] = {
        floor: edge_ladder(window, thresholds=DEFAULT_THRESHOLDS, price_floor=floor,
                           n_boot=min(n_boot, 1000), seed=seed)
        for floor in (0.0, PRICE_FLOOR)
    }
    return out


def _fmt(res: dict[str, object]) -> str:
    lines = [
        f"Ventana: game_date > {WINDOW_AFTER} (datos {res['window'][0]} -> {res['window'][1]})",
        f"Candidatos edge>=0: {res['n_candidates']} picks / {res['ev_candidates']} eventos",
        f"Brazo p_novig>={PRICE_FLOOR}: {res['n_arm']} picks / {res['ev_arm']} eventos "
        f"(minimo {MIN_PICKS} / {MIN_EVENTS})",
    ]
    if not res["enough"]:
        return "\n".join([*lines, f"Veredicto: {res['verdict']}"])
    ci = res["roi_sin_ci"]
    lines.append(f"ROI plano SIN suelo: {res['roi_sin']:+.4f} IC95 [{ci[0]:+.4f}, {ci[1]:+.4f}] "
                 f"hit={res['hit_sin']:.4f}")
    ci = res["roi_con_ci"]
    lines.append(f"ROI plano CON suelo: {res['roi_con']:+.4f} IC95 [{ci[0]:+.4f}, {ci[1]:+.4f}] "
                 f"hit={res['hit_con']:.4f}")
    lo, hi = res["delta_ci"]
    lines += [f"DELTA = {res['delta']:+.4f} IC95 [{lo:+.4f}, {hi:+.4f}]",
              f"Veredicto pre-registrado (primaria): {res['verdict']}", "",
              "Contraprueba por quintil de p_novig:"]
    for r in res["quintiles"]:
        lo, hi = r["roi_ci"]
        line = (f"  Q{r['q']} [{r['novig_min']:.3f}, {r['novig_max']:.3f}] n={r['n']} "
                f"roi={r['roi']:+.4f} IC95 [{lo:+.4f}, {hi:+.4f}] frac_brazo={r['frac_arm']:.2f}")
        if np.isfinite(r["delta"]):
            dlo, dhi = r["delta_ci"]
            line += f" | delta condicionado={r['delta']:+.4f} IC95 [{dlo:+.4f}, {dhi:+.4f}]"
        lines.append(line)
    for floor, lad in res["ladders"].items():
        lines += ["", f"Escalera de min_edge con suelo {floor:.2f}:",
                  lad[["min_edge", "n_rows", "hit_rate", "roi_flat", "roi_lo", "roi_hi"]]
                  .to_string(index=False)]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    raw = ServedStore(ROOT).load_all_graded()
    if raw.empty:
        print("Sin stream graduado en data/calibration: nada que medir.")
        return 1
    print(_fmt(run(raw, n_boot=args.n_boot, seed=args.seed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
