#!/usr/bin/env python
"""CLV condicionado al movimiento de linea previo al pick (analisis one-off).

Prueba retrospectiva del filtro de confirmacion por movimiento (2026-07-14):
si los picks cuyo desacuerdo iba EN la direccion del movimiento previo del
mercado ("hacia") muestran CLV/beat-close mejores que los que iban "contra",
el filtro es candidato a gate de generacion (validacion aparte). Solo lee
datos guardados (data/bets + data/odds), sin cuota API; no toca el pipeline.

  python scripts/clv_by_line_movement.py

CLV es diagnostico de proceso, no promesa de ganancia; todas las cifras son
sobre probabilidades estimadas y ROI a stake plano (stakes reales 0 en shadow).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.clv_movement import clv_by_movement, movement_segments
from sqp.audit.report import DISCLAIMER
from sqp.config import ROOT


def main() -> int:
    bets_dir = ROOT / "data" / "bets"
    df, cov = clv_by_movement(bets_dir, ROOT)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        f"# CLV por movimiento previo de linea - {ts[:8]}",
        f"Generado: {ts}",
        "",
        f"Cobertura: {cov['n_matched_close']} emparejadas a cierre fresco; "
        f"{cov['n_with_movement']} con movimiento pre-pick computable "
        f"(>= 2 snapshots); sin cierre: {cov['n_unmatched_close']}.",
        "",
    ]
    if df.empty:
        lines.append("(sin picks con movimiento computable)")
    else:
        lines += [
            "## Global por direccion del movimiento",
            movement_segments(df).to_string(index=False),
            "",
            "## Por (liga, mercado) y direccion (n >= 10)",
        ]
        seg_lm = movement_segments(df, by=["league", "market"])
        seg_lm = seg_lm[seg_lm["n"] >= 10]
        lines.append(seg_lm.to_string(index=False) if not seg_lm.empty
                     else "(ningun segmento con n >= 10)")
        corr = df["movement_pp"].corr(df["clv_pct"], method="spearman")
        lb = df["lookback_h"]
        lines += [
            "",
            f"Spearman(movement_pp, clv_pct) = {corr:.3f} (n={len(df)})",
            f"Lookback pre-pick: mediana {lb.median():.1f}h | p25 "
            f"{lb.quantile(0.25):.1f}h | p75 {lb.quantile(0.75):.1f}h | "
            f"snapshots por pick: mediana "
            f"{df['n_snapshots'].median():.0f}",
            "",
            "movement_pp = prob. implicita del consenso de nuestra seleccion "
            "(ultimo snapshot <= pick) - (snapshot mas antiguo), en pp. "
            "'hacia' = el mercado venia moviendose a nuestro lado.",
        ]
    lines += ["", f"> {DISCLAIMER}"]
    text = "\n".join(lines)
    out = bets_dir / f"clv_movement_{ts[:8]}.md"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReporte escrito en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
