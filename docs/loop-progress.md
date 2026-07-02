# Ledger del loop de precisión

Una línea por iteración (ver `docs/loop-mandate-precision.md`, ciclo paso 5).
Formato: `<fecha> <tema>: <qué se hizo> (commit <sha7>)`

## Iteraciones

- 2026-07-01 deuda--rebuild: HECHO fuera del loop (auditoría interactiva): warn cuando
  `--rebuild` se ignora bajo `--source settled` + docstring al flujo staging (commit fd22c92,
  ya en main). El ítem del backlog queda CERRADO.
- 2026-07-02 gate-observability: veredictos por condición del gate (ece_ok/brier_ok/monotone_ok)
  en resultados, log del retrain diario (`dropped: brier`) y CLI; resúmenes por grupo propagan
  gates + raw_val_brier. Motivación: el drop de mlb_spreads de hoy era indiagnosticable desde el
  log. TDD, suite 271 verde. (commit dc1fe05, rama loop/gate-observability — pendiente de merge
  humano)

## Auditoría solo-lectura (backlog ítem 4) — estado del gate por mercado, 2026-07-02

Fuente: retrain sobre settled reales del run de hoy + reproducción aislada del fit.

| grupo | n (graded) | n_val | raw ECE | mejor ECE | veredicto |
|---|---:|---:|---:|---:|---|
| mlb/spreads | 96 | 20 | 0.1528 | iso 0.0491 | DROP por Brier (0.2384→0.2418). Dirección correcta (deflacta favoritos 0.60→0.53, 0.70→0.57); colas 0.10→0.01 sobreajustadas. EL MÁS CERCANO a pasar: re-evaluar al crecer n. |
| mlb/totals | 69 | 14 | 0.1689 | — | DROP por ECE+Brier (ambos modelos). Lejos. |
| mlb/h2h | 38 | — | — | — | Bajo min_n=40; a 2 bets de entrenar. |
| tennis_wta_wimbledon/h2h | 45 | 9 | 0.2702 | iso 0.1757 | KEPT (staged) pero n_val=9 y el mapa es un escalón que colapsa p≥0.5 a 0.50. RECOMENDACIÓN: NO promover. Torneo termina ~13-jul; muestra no crecerá mucho. |
| wnba/* | 19–28 | — | — | — | Bajo min_n. |

Lectura: ningún candidato merece promoción hoy. El registro live sigue `{}` (correcto).
mlb/spreads es el grupo a vigilar: con ~2 semanas más de settled (≥150 graded) el split de
validación deja de ser ruido y el Brier decidirá con evidencia.

- 2026-07-02 research-pmodel: COMPLETADO el ítem 1 del backlog (investigación, sin cambios de
  serving). Hallazgo: reblend `0.5·cal(p_model)+0.5·fair` domina a `cal(p_used)` en ECE Y Brier
  en los 4 cortes temporales de mlb/spreads (n=96) y es la única variante que habría pasado el
  gate. Doc: docs/research/2026-07-02-calibrar-pmodel-puro-vs-blend.md. Decisión de adoptar el
  cambio de serving = humana, pendiente.

## Bloqueos / notas
- Backlog ítem 2 (edge cases de data.py): pendiente, siguiente iteración natural.
- La mayoría de grupos están bloqueados por acumulación de datos (min_n) — se destraban solos
  con los settled diarios ahora que el staging automático corre (fix C1, main 2714ea6).
