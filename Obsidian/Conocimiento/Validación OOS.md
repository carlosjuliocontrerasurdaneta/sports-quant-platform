---
tags: [validacion, oos, backtesting, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Validación OOS

## Metodología

- **Backtest walk-forward** sobre `data/historical/` por liga (warmup 60), con baseline de tasa local. Ligas 3-way: P(local | no empate) + calibración del empate por separado.
- **validate_oos** (`scripts/validate_oos.py`): congela parámetros en TRAIN, mide ROI realizado en TEST posterior; compara frozen_train vs full_history vs family_default. Corre mensualmente (tarea `Validate_OOS`).
- **Reglas anti-sesgo del ROI**: solo cierre/pre-commence, book real (no best-line retrospectivo), flat y Kelly por separado, separar siempre estimada/implícita/no-vig/edge/ROI esperado/ROI realizado.
- Odds OOS: captura forward propia diaria + backfill histórico de pago autorizado por tramos (NBA/NHL playoffs ~90d, 5.310 créditos, 2026-06-22).

## Resultados clave (2026-06-22/26)

| Liga | Muestra OOS | Veredicto |
|---|---|---|
| **MLB** | n≈1.150 | **Generaliza**: frozen +0.41% vs sin-tuning −3.28% (~+3.7pp); el tuning NO es overfit. Único con muestra confiable |
| **WNBA** | n=170 | No generaliza / params = default de familia → nada que validar; ruido |
| **NHL** | n=188 (playoffs) | El modelo PIERDE (−4.5%); cobertura para validar señales, no para operar |
| **NBA** | n=67 (playoffs) | Marginal; pierde (−25.6%) |
| **Tenis** | 3-9 apuestas/torneo | Ruido puro; capacidad de medir, no señal |

## Estado de honestidad del sistema

- Los parámetros de MLB generalizan; el resto sigue in-sample o sin muestra.
- Todo el ROI OOS es sobre **proxy de cierre de un snapshot, sin intervalos de confianza** → no es rentabilidad demostrada.
- El sistema ha estado ≈ break-even en su mejor configuración; el ROI realizado con dinero real fue negativo (MLB −27.6%) por sobreconfianza + selección adversa → [[Estado del proyecto|shadow mode]].

Relacionado: [[Conocimiento/Señales por deporte]], [[Conocimiento/CLV y selección adversa]].
