# Revisión cuantitativa — Auditoría 2026-08-02

Todo lo que sigue son **probabilidades estimadas** y controles de proceso. No
hay en este documento ninguna afirmación de rentabilidad. La revisión profunda
por deporte/mercado se hizo el 2026-07-29/31 (historial git de este archivo);
aquí se audita lo que cambió desde entonces y el estado de la evidencia.

## Objetivo rector (actualizado 2026-08-02)

Directiva del operador: **el fin del sistema es ganar dinero** (sacrosanto).
Implicación metodológica: la métrica de juicio es rentabilidad realizada/CLV, y
el hit rate SOLO se lee contra el breakeven por cuota
(`breakeven_hit_rate = 1/price`, `hit_rate_margin`), disponibles en el reporte
por segmento desde `f6c2130`.

## Cambios cuantitativos desde la auditoría anterior (todos con evidencia)

| Cambio | Commit | Evidencia registrada |
|---|---|---|
| Béisbol: Poisson → binomial negativa (colas subestimadas) | `fa503f9` | Test de no-regresión hockey/fútbol + pérdida por truncamiento; parametrización verificada en esta auditoría (media preservada) |
| Dispersión de totals: 4 ligas de baloncesto corregidas | `3500436` | Residual walk-forward medido; WNBA totals Brier 0.3363→0.3149, IC [+0.0092,+0.0332] excluye cero |
| margin_sigma: 3 ligas universitarias (+NBA/WNBA ajuste) | `c0dd670` | Mismo método; NFL salió exacta (valida el método) |
| Fútbol: avg_goals por temporada real; tenis: elo_k medido (24→40) | `37ed825` | Tests nuevos (test_soccer_avg_goals, test_tennis_params); claim falso "surface-aware" retirado |
| Manifest de features versiona config+código del builder (D-10) | `3d67b6d` | Caches viejos invalidados correctamente; fingerprints únicos por liga |
| Calibración: fecha validada como día ISO real | `1dba6b0` | 15 pruebas de calibración; previene leakage por orden temporal con fechas malformadas |
| Marcador modelo vs mercado | `820185c` | Nueva medición; no altera producción |
| Separación muestra liquidada vs apostada en segmentos | `d665fff` | Corrige conflación en el reporte |

Patrón común documentado en la bitácora 07-31: **dispersión subestimada**
(el modelo se equivocaba "con confianza"); ninguno era bug de programación sino
supuestos heredados nunca medidos.

## Selección de picks: estado real

- `pick_mode: edge` activo desde 2026-07-31. El experimento accuracy
  (07-28→07-31) queda como evidencia de que maximizar hit rate sin mirar la
  cuota pierde dinero por construcción (favoritos 1.07–1.16, breakeven ≥ 93.5%).
- Penalización de EV por desacuerdo modelo-mercado activa; techo
  `max_plausible_edge 0.075`; cap de exposición diaria; bankroll dinámico.

## Calibración

- `method: auto` por (liga, mercado) con gate auto-sanador OOS; auto-promoción
  gated (ECE + Brier + monotonía + anti-inflación a extremos + ≥15 eventos
  independientes). Fecha ISO validada desde `1dba6b0`.
- Estado: solo `mlb_h2h` pasó todos los gates históricamente; el resto sirve
  probabilidades crudas (no-op seguro). Sin cambios en esta auditoría.

## Evidencia fuera de muestra — lo que ESTÁ y NO está demostrado

**Demostrado (con evidencia reproducible):**
- Las correcciones de dispersión mejoran Brier OOS donde se midieron (IC
  excluye cero en WNBA totals).
- La infraestructura de medición funciona: CLV con filtro de frescura (≤90
  min), monitor de degradación, diagnóstico por segmentos, breakeven por cuota.

**NO demostrado:**
- **Ventaja predictiva sobre el mercado.** OOS de la regla edge/Kelly: −5.32%.
  Gate de CLV vacío: ningún (liga, mercado) con mediana > 0 y n≥30. Mediana
  global de CLV 0.00% (n=300).
- Rentabilidad de ningún modo de selección. El sistema debe permanecer en
  shadow por su propia regla.

## Riesgos metodológicos vigentes

- **M-01 (esta auditoría):** 87 filas servidas sin liquidar fuera de la ventana
  de scores → sesgo de supervivencia en las muestras de auditoría/calibración
  hasta que se backfillee y liquide.
- Masa de CLV=0.00 exactos sin explicar (hipótesis: entrada al precio de
  cierre; timing sin investigar) — hallazgo del 07-27, sigue abierto.
- Muestras por (liga, mercado) mayoritariamente < 30: toda métrica por
  segmento es ruido hasta acumular volumen.

## Conclusión cuantitativa

La plataforma mide con honestidad y sus supuestos distribucionales están ahora
medidos contra el histórico, pero **no hay evidencia de que gane dinero**. Bajo
el objetivo sacrosanto, el camino es: liquidar el rezago (M-01), acumular
muestra en shadow, y solo mover stake real cuando un mercado pase el gate de
CLV — apostar sin edge demostrado es la forma más rápida de perder dinero.
