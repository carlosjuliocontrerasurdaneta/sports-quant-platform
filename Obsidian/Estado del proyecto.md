---
tags: [estado, sqp]
creada: 2026-07-07
actualizada: 2026-07-08
---

# Estado del proyecto — Sports Quant Platform

> Snapshot al 2026-07-08 (commit `4651392` en `main`). Punto de entrada: [[00 - Inicio]].
> Las cifras de probabilidad son siempre **probabilidades estimadas**, nunca certezas; el ROI esperado es una estimación y el ROI realizado es el observado.

## Modo operativo: SHADOW MODE

- `shadow_mode: true` en `configs/default.yaml` (desde el 2026-07-03, commit `fe9ef84`).
- Todos los picks se generan y registran con **stake 0** (tenis incluido); no hay dinero en juego.
- **Regla de salida**: mediana de CLV positiva + pasar el gate de Brier tras ~100 picks liquidados.
- **Gate de CLV por (liga, mercado)** (2026-07-08, `bc27252`): la salida del shadow es POR MERCADO — allow-list default-deny, ≥30 apuestas con CLV mediano positivo. Ver [[Conocimiento/CLV y selección adversa]].
- Balance congelado: 915.75.

## Por qué estamos en shadow

1. **ROI realizado MLB persistentemente negativo** (−27.6%): sesgo sistemático de sobreconfianza.
2. **Selección adversa**: barrido de shrink sobre apuestas MLB reales (n=71) mostró que incluso usando la probabilidad justa del mercado (s=1.0) se pierde — el edge seleccionado tiene CLV negativo. El CLV pasa a ser la métrica de gating.
3. **Calibradores degenerados**: isotónicos sobreajustados (mlb_spreads, nhl_h2h) empujaban favoritos a 0.92–0.99 creando edges fantasma. Registro live **vacío**: toda la plataforma sirve probabilidades crudas (no-op) hasta que un mercado pase el gate de Brier OOS.

## Calibración: estado del pipeline

- **Train ≠ promote**: el reentreno diario solo *presenta candidatos* (staging); la promoción a live es un paso humano explícito (`scripts/promote_calibration.py`).
- **Fix del mismatch train/serve** (2026-07-01, `d39f975`): se entrenaba con historial anclado al cierre pero se servía anclado a apertura; ahora entrena sobre `data/bets/settled_*.csv` (distribución de servicio).
- **Stream de probabilidades servidas** (2026-07-05/07, `578ace6`): `ServedStore` captura la distribución completa de probabilidades servidas (no solo los picks apostados) para entrenar calibradores sin sesgo de selección. Liquidación del stream integrada para todas las ligas no-tenis.
- Primer candidato en staging: MLB spreads (ECE OOS +0.0524). Promoción pendiente de revisión.

## Modelo — fixes recientes

- Decaimiento por recencia (180d) en tasas de anotación; corregido el sesgo Under de WNBA (`31356a1`).
- Tenis: el vertical se eliminó y luego se **revirtió** (`d8a77dc`); la causa raíz de su mala precisión es inadecuación del modelo Elo, no datos obsoletos. Corre en shadow como el resto.
- MLB pitcher (RA+FIP): refutado OOS — no volver a perseguirlo.
- mypy limpio en `src` (`a22f8a8`).

## Automatización (Task Scheduler, 5 tareas)

| Tarea | Frecuencia |
|---|---|
| Diario_Completo | diaria 11:00 |
| Capture_Close (CLV) | cada hora |
| Backfill (tenis incluido) | lunes 09:00 |
| Refresh_ML | lunes 09:45 |
| Validate_OOS | mensual, día 1, 12:00 |

`StartWhenAvailable` debe permanecer en True. Producción vive en `C:\dev` (migración desde OneDrive completada).

## Riesgo

- Caps de exposición en dos capas: por liga (`max_daily`) + global (`max_total`).
- Una liga se auto-excluye del run diario si tiene picks comenzados sin liquidar.
- (En shadow todo esto opera con stake 0.)

## Pendientes

Lista viva en [[Tareas]]. Resumen:

- [ ] Acumular ~100 picks liquidados en shadow y evaluar la regla de salida (CLV mediana + Brier).
- [ ] Revisar/promover el candidato de calibración MLB spreads.
- [ ] Seguimiento del quota-guard del proveedor de odds.
- [x] ~~Deuda del dashboard-history~~: escrituras atómicas en settle (07-01), filtro/"nan" de Línea (KI-018, `11bd999`) y e2e de tenis (KI-017, `7471ce4`) — todo cerrado.
