#!/usr/bin/env python
"""gate_status.py — estado del prediction gate por (liga, mercado).

Muestra DOS cosas, separadas a proposito:

  1. El VEREDICTO persistido en `data/bets/prediction_gate.json` (lo que el
     run diario aplica: `allowed`, pestillo, motivo). Es la unica fuente de
     "habilitado para stake real".
  2. El PROGRESO estadistico: `evaluate_markets` sobre el stream servido
     graduado (`ServedStore.load_all_graded`), es decir, la misma funcion y
     la misma muestra que usa `write_prediction_gate`. Aqui `n` cuenta unidades
     independientes (una por evento y mercado), solo partidos posteriores a
     `VALIDATION_START`, con el test pareado modelo vs mercado y el EV plano.

Hasta el 2026-09-18 este script reconstruia OTRA regla (pick_history,
`estimated_probability`, aciertos contra 0,5, EV = p − 1/cuota, sin ventana,
sin unidad por evento, sin pestillo) y anunciaba "PASAN EL GATE" para cortes
que el gate real denegaba (AUD-001, ronda audit-2026-09-18, reproducido por el
auditor OpenAI: 300 filas de un mismo evento -> el script decia "pasa", el
gate devolvia n=1, muestra_insuficiente). Compartir MIN_N y ALPHA no hacia
equivalentes los procedimientos. Ahora no hay regla paralela: se reutiliza la
canonica.

Umbral por mercado: alpha de familia 0,05 repartido por Bonferroni sobre
K=41 cortes = 0,05/41 = 0,00122 (`PREDICTION_GATE_ALPHA`). Leer la constante,
no citarla de memoria.

Uso:
  python scripts/gate_status.py
  python scripts/gate_status.py --min-n 50     # solo cortes con n >= 50 en el progreso
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqp.risk.prediction_gate import (PREDICTION_GATE_ALPHA,  # noqa: E402
                                      PREDICTION_GATE_MIN_N, VALIDATION_START,
                                      evaluate_markets, load_prediction_gate,
                                      market_allowed)
from sqp.storage.served_store import ServedStore  # noqa: E402

MIN_N_GATE: int = PREDICTION_GATE_MIN_N
ALPHA: float = PREDICTION_GATE_ALPHA


def verdict_table(gate: dict[str, dict]) -> pd.DataFrame:
    """Tabla del veredicto persistido: una fila por corte del registro."""
    rows = []
    for key, entry in sorted(gate.items()):
        if not isinstance(entry, dict) or "|" not in key:
            continue
        league, market = key.split("|", 1)
        rows.append({
            "mercado": key,
            "habilitado": market_allowed(gate, league, market),
            "allowed_registro": bool(entry.get("allowed")),
            "pestillo": bool(entry.get("latched")),
            "n": int(entry.get("n") or 0),
            "motivo": str(entry.get("reason") or ""),
        })
    return pd.DataFrame(rows, columns=["mercado", "habilitado", "allowed_registro",
                                       "pestillo", "n", "motivo"])


def progress_table(graded: pd.DataFrame, *, min_n_display: int = 0) -> pd.DataFrame:
    """Progreso con el criterio canonico (misma funcion y muestra que el
    escritor del registro). `min_n_display` solo FILTRA la vista."""
    decided = evaluate_markets(graded)
    if decided.empty:
        return decided
    decided = decided.assign(
        mercado=decided["league"].astype(str) + "|" + decided["market"].astype(str),
        n_falta=(MIN_N_GATE - decided["n"]).clip(lower=0))
    if min_n_display > 0:
        decided = decided[decided["n"] >= min_n_display]
    return decided.sort_values(["allowed", "p_value", "n_falta"],
                               ascending=[False, True, True])


def render(gate: dict[str, dict], graded: pd.DataFrame, *,
           min_n_display: int = 0) -> str:
    out: list[str] = []
    out.append(f"=== PREDICTION GATE — umbral: n>={MIN_N_GATE} unidades "
               f"independientes, p<{ALPHA:.5f}, EV plano>0; partidos "
               f"posteriores a {VALIDATION_START} ===")
    out.append("")
    out.append("[1] VEREDICTO PERSISTIDO (lo que aplica el run diario):")
    verdict = verdict_table(gate)
    habilitados = verdict[verdict["habilitado"]] if not verdict.empty else verdict
    if not gate:
        out.append("  registro ausente o ilegible -> default-deny: NINGUN mercado "
                   "lleva stake real.")
    else:
        out.append("  Habilitados para stake real: "
                   + (", ".join(habilitados["mercado"]) if not habilitados.empty
                      else "ninguno (default-deny)"))
        latched = verdict[verdict["pestillo"]]
        if not latched.empty:
            out.append("  Pestillos armados (no reentran sin revision humana): "
                       + ", ".join(latched["mercado"]))
        out.append(verdict.to_string(index=False))
    out.append("")
    out.append("[2] PROGRESO ESTADISTICO (criterio canonico sobre el stream "
               "servido graduado; NO es una autorizacion):")
    progress = progress_table(graded, min_n_display=min_n_display)
    if progress.empty:
        out.append("  ningun corte con filas dentro de la ventana de validacion"
                   + (f" y n >= {min_n_display}" if min_n_display else "") + ".")
    else:
        cols = ["mercado", "n", "wins", "p_value", "ev_flat", "n_falta",
                "allowed", "reason"]
        out.append(progress[cols].rename(columns={"allowed": "cumple_criterios"})
                   .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
        cumplen = progress[progress["allowed"]]
        out.append(f"  Cumplen los criterios estadisticos hoy: {len(cumplen)} de "
                   f"{len(progress)}. La autorizacion es la de [1]: un corte con "
                   f"test de entrada consumido o pestillo NO reentra aunque cumpla.")
    out.append("")
    out.append("Probabilidades ESTIMADAS. Pasar el gate no promete rentabilidad.")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Estado del prediction gate por mercado")
    parser.add_argument("--min-n", type=int, default=0,
                        help="Mostrar en el progreso solo cortes con n >= este "
                             "valor (default: 0 = todos). Solo filtra la vista.")
    args = parser.parse_args()
    bets_dir = ROOT / "data" / "bets"
    gate = load_prediction_gate(bets_dir)
    graded = ServedStore(ROOT).load_all_graded()
    print(render(gate, graded, min_n_display=args.min_n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
