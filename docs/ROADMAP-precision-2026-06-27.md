# Hoja de ruta: mejorar la precisión del sistema

Fecha de creación: 2026-06-27

Hoja de ruta secuenciada para decidir, con evidencia, si el sistema tiene edge
real y cómo mejorar su precisión — sin tocar nada en caliente. Cada fase está
atada a una tarea programada ya existente.

## Contexto (diagnóstico 2026-06-26/27)

- En vivo: 156 apuestas liquidadas, acierto 44.2%, ROI realizado −13.3% (MLB −26%).
- Modelo **sobreconfiado**: prob. estimada media 0.525 vs acierto real 0.442 (+8 pts).
- **Backtest vs vivo divergen**: MLB backtest +7.8% vs vivo −26%.
- **CLV no era medible**: solo había un snapshot de cuotas por evento (entrada = cierre).
- Refutado con datos (NO re-perseguir): ajuste de **pitcher** (RA v1 y FIP v2 empeoran
  OOS), el **shrink** como "defecto" (es control de daños), y **matar toda la
  calibración** (solo `mlb/spreads` es sospechoso).

Verdad de fondo: los mercados deportivos son muy eficientes. La precisión llega
por **medición + calibración + disciplina de precio/mercado**, no por un modelo
más complejo ni más features a ciegas.

## Fase 0 — Ahora → continuo: recolectar, no tocar nada

- Corriendo solo: captura de línea de cierre (horaria, `SQP_Capture_Close_Cdev`),
  run diario (`SQP_Diario_Completo_Cdev`, picks + liquidación), acumulando
  apuestas y líneas de cierre.
- Decisión: ninguna.
- Guardarraíl: cero cambios a modelo/calibración/staking. 156 bets no distinguen
  "roto" de "varianza".

## Fase 1 — Dom 2026-06-28, 09:30 — revisión de calibración

- Corre: `SQP_Calibration_Review_MLB_h2h_Cdev` (`REVIEW_CALIBRATION_MLB_H2H.bat`)
  → ECE OOS antes/después + pestaña Auditoría.
- Decisión: cruzar el ECE de la revisión con el hallazgo en memoria
  (`mlb/spreads` net-negativo en Brier sobre resultados en vivo). Si **ambos**
  (backtest-ECE y Brier-en-vivo) coinciden en que empeora → borrar
  `data/models/mlb_spreads_calibration_*.joblib` (ese mercado vuelve a
  sin-calibrar). `mlb/h2h` ayuda pero n=9 → dejarlo, no decidir aún.
- Guardarraíl: NO tocar `market_shrink` / `uncertainty_penalty` (refutado).
  Borrar un calibrador solo si las dos métricas concuerdan.

## Fase 2 — Lun 2026-06-29 — backfill (08:00) + refresh ML (10:30)

- Corre: `SQP_Backfill_Cdev` (resultados históricos) + `SQP_Refresh_ML_Cdev`
  (features/modelos ML al día).
- Decisión: ninguna — mantenimiento.
- Guardarraíl: solo verificar que corrieron limpios (logs).

## Fase 3 — 2026-07-01 — VALIDATE_OOS mensual

- Corre: `SQP_Validate_OOS_Cdev` → frozen vs full_history vs family_default por liga.
- Decisión: si los parámetros tuneados de una liga ya no le ganan OOS al
  family_default, revertir esa liga a defaults (params del modelo, distinto de
  la calibración).
- Guardarraíl: decisión por liga solo con muestra suficiente.

## Fase 4 — 2026-07-10, 09:00 — HITO: revisión de CLV

- Corre: `SQP_CLV_Review_20260710` → `logs/clv_review_20260710.txt`
  (`scripts/clv_analysis.py`).
- Decisión (la que define el rumbo):
  - CLV dejó de ser ~0 y es POSITIVO → hay edge real; el −26% fue varianza/arranque.
    Seguir; considerar escalar con cuidado.
  - CLV NEGATIVO → no hay edge real; problema estructural (precio/timing/modelo).
    Acción: subir `min_edge`, pausar mercados perdedores (`settings.paused_markets`),
    o pausar apuestas en vivo mientras se trabaja el modelo.
  - CLV aún ~0 → faltan snapshots de cierre; esperar más.
- Guardarraíl: muestra aún modesta → direccional, no veredicto final.

## Fase 5 — Después del 10-07 (condicional al CLV)

- Con CLV + más muestra: recalibrar contra resultados reales, podar mercados sin
  edge, y solo entonces evaluar señales nuevas — siempre con gate OOS + CLV,
  nunca a ciegas.

## Principio transversal

Toda decisión se valida con datos; nunca actuar en caliente sobre muestras chicas.
Lenguaje: separar probabilidad estimada / implícita / edge estimado / ROI realizado
/ CLV; ninguna garantía de profit.

Memoria relacionada: ver `[[oos-generalization-findings]]`,
`[[closing-capture-and-pitcher-findings]]`, `[[cdev-production-migration]]`.
