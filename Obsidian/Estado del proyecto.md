---
tags: [estado, sqp]
creada: 2026-07-07
actualizada: 2026-07-28
---

# Estado del proyecto — Sports Quant Platform

> Snapshot al 2026-07-28. Punto de entrada: [[00 - Inicio]].
> Las cifras de probabilidad son siempre **probabilidades estimadas**, nunca certezas; el ROI esperado es una estimación y el ROI realizado es el observado.

## Objetivo del proyecto: % DE ACIERTOS (desde 2026-07-27)

Decisión de Carlos: el fin último es **maximizar el porcentaje de aciertos de
los picks**; bankroll, ROI y CLV se calculan pero dejan de ser rectores.
Implementado el 2026-07-28: **modo precisión ACTIVO en producción**
(`picks: {mode: accuracy, accuracy_threshold: 0.70}` en `configs/default.yaml`).

- Selección por **probabilidad de decisión calibrada** (blend modelo + no-vig
  del consenso) ≥ 0.70, SOLO moneyline; nada de Kelly (stake plano
  `bankroll * max_stake_pct`, hoy 0 por shadow).
- Cada pick lleva el flag `accuracy_mode`; la revocación por edge del segundo
  pase los salta (el guard de cambio de abridor sí aplica).
- **KPI**: hit rate por (liga, banda de probabilidad) sobre la probabilidad
  calibrada — bandas finas ≥0.70 en `sqp/audit/segments.py`, visible en
  `segment_diagnostics_latest.csv` y la pestaña Diagnóstico. El `gap`
  (observado − estimado medio) de las bandas altas ES el control de
  cumplimiento del umbral.
- El modo edge queda conmutable vía `picks.mode: edge` o env `PICK_MODE`.
- Pendiente: definir el gate de salida del shadow propio del modo precisión
  (ver [[Tareas]]).

## Modo operativo: SHADOW MODE

- `shadow_mode: true` en `configs/default.yaml` (desde el 2026-07-03, commit `fe9ef84`).
- Todos los picks se generan y registran con **stake 0** (tenis incluido); no hay dinero en juego.
- **Regla de salida**: mediana de CLV positiva + pasar el gate de Brier tras ~100 picks liquidados.
- **Gate de CLV por (liga, mercado)** (2026-07-08, `bc27252`): la salida del shadow es POR MERCADO — allow-list default-deny, ≥30 apuestas con CLV mediano positivo. Ver [[Conocimiento/CLV y selección adversa]].
- **Filtro de frescura del cierre** (2026-07-12): solo cuenta como cierre un snapshot a ≤90 min del comienzo; antes el 59% de las apuestas emparejaba contra el snapshot matinal (CLV≡0 por construcción) y la mediana del gate quedaba clavada en 0. Estado honesto: n=191 emparejadas, batió-el-cierre 41%, ningún mercado habilitado aún (el más cercano: WTA Wimbledon h2h, mediana +0.46%, n=21/30).
- **Monitor de degradación por (liga, mercado)** (2026-07-13): auto-pausa gated diaria sobre la ventana móvil de 60 días de liquidadas — pausa si el Brier estimado es peor que el del mercado (+0.01) o el ROI a stake plano < −15% con n≥30; reanuda solo con histéresis. Alimenta `paused_markets` por unión (nunca des-pausa lo estático). Registro: `data/bets/degradation_pause.json`. Dry-run inicial pausaría: mlb_spreads, tenis ATP/WTA Wimbledon h2h y wnba_totals — exactamente los mercados con problemas ya diagnosticados; mlb_h2h queda intacto.
- **Diagnóstico automático por segmentos** (2026-07-13): reporte diario que localiza DENTRO de cada (liga, mercado) dónde vive una desviación (favorito/underdog, lado, banda de probabilidad estimada, banda de línea; n≥15, gap ±0.07 o Brier peor que mercado). Solo observabilidad. Hallazgos del dry-run: la sobreconfianza del tenis vive en underdogs, la de wnba_totals en el Under, mlb_spreads mal en todo; wnba_h2h underdogs con subconfianza (señal nueva). Salida: `data/bets/segment_diagnostics_*.md` + `segment_diagnostics_latest.csv`.
- Balance congelado: 915.75.

## Por qué estamos en shadow

1. **ROI realizado MLB persistentemente negativo** (−27.6%): sesgo sistemático de sobreconfianza.
2. **Selección adversa**: barrido de shrink sobre apuestas MLB reales (n=71) mostró que incluso usando la probabilidad justa del mercado (s=1.0) se pierde — el edge seleccionado tiene CLV negativo. El CLV pasa a ser la métrica de gating.
3. **Calibradores degenerados**: isotónicos sobreajustados (mlb_spreads, nhl_h2h) empujaban favoritos a 0.92–0.99 creando edges fantasma. Registro live casi vacío: solo `mlb_h2h` pasó todos los gates (auto-promovido 07-13); el resto de la plataforma sirve probabilidades crudas (no-op).

## Calibración: estado del pipeline

- **Train ≠ promote**: el reentreno diario *presenta candidatos* (staging); desde el 2026-07-08 la **auto-promoción gated** está activa (`auto_promote: true`): promueve a live solo candidatos que pasan los gates OOS (ECE + Brier + monotonía + **no-inflación a extremos**, este último desde el 2026-07-13) y, desde el 2026-07-11, con **≥15 eventos independientes** de validación (no lados correlacionados del mismo partido — port del linaje Nc2, commit `a2027b9`). `scripts/promote_calibration.py` sigue como vía manual.
- **Fix del mismatch train/serve** (2026-07-01, `d39f975`): se entrenaba con historial anclado al cierre pero se servía anclado a apertura; ahora entrena sobre `data/bets/settled_*.csv` (distribución de servicio).
- **Stream de probabilidades servidas** (2026-07-05/07, `578ace6`): `ServedStore` captura la distribución completa de probabilidades servidas (no solo los picks apostados) para entrenar calibradores sin sesgo de selección. Liquidación del stream integrada para todas las ligas no-tenis.
- **Staging vacío al 2026-07-12**: el candidato MLB spreads del 07-01 (ECE OOS +0.0524) dejó de regenerarse — con los datos actuales y los gates vigentes (Brier OOS desde 06-30, monotonía, ≥15 eventos independientes desde 07-11), los 8 mercados con muestra suficiente fallan al menos un gate. Ej.: mlb_spreads iso mejora ECE (0.1461→0.1076) pero empeora Brier OOS → descartado. No hay nada que promover; el sistema sigue sirviendo probabilidades crudas por diseño.
- **Estado al 2026-07-13** (revisión integral, ver [[Bitácora/2026-07-13]]): `mlb_h2h` LIVE (isotónico, ECE OOS 0.117→0.037, 23 eventos de validación, preview compresivo sano 0.90→0.61). Gate nuevo **anti-inflación a extremos**: un candidato wnba_h2h pasó ECE+Brier+monotonía con 24 filas/8 eventos mientras mapeaba 0.80→0.99 (la firma del incidente 06-30); ahora esa forma se rechaza en el fit (`extreme_ok`). En staging queda solo wnba_totals (isotónico plano en 0.48 — sin poder discriminativo, inocuo; bloqueado por <15 eventos). Los demás mercados (mlb spreads/totals, tenis Wimbledon, wnba h2h/spreads) siguen no-op: ningún calibrador mejora OOS sin degenerarse.

## Modelo — fixes recientes

- Decaimiento por recencia (180d) en tasas de anotación; corregido el sesgo Under de WNBA (`31356a1`).
- Tenis: el vertical se eliminó y luego se **revirtió** (`d8a77dc`); la causa raíz de su mala precisión es inadecuación del modelo Elo, no datos obsoletos. Corre en shadow como el resto.
- MLB pitcher (RA+FIP): refutado OOS — no volver a perseguirlo.
- mypy limpio en `src` (`a22f8a8`).

## Automatización (Task Scheduler, 6 tareas)

| Tarea | Frecuencia |
|---|---|
| Diario_Completo | diaria 11:00 |
| Dashboard (interactiva) | disparada por Diario_Completo al terminar + al iniciar sesión (abre `report_latest.html` solo si es de hoy y no se mostró; ver [[Bitácora/2026-07-16]]) |
| Capture_Close (CLV) | cada 30 min desde 07-14 PM (antes cada hora); persiste snapshot completo de liga + revalidación + guard de abridores + observatorio intradía |
| Backfill (tenis incluido) | lunes 09:00 |
| Refresh_ML | lunes 09:45 |
| Validate_OOS | mensual, día 1, 12:00 |

`StartWhenAvailable` debe permanecer en True. Producción vive en `C:\dev\3\sports-quant-platform` (corte 07-14 PM: scheduler repuntado, datos sincronizados, `.git` movido; copia vieja archivada como `C:\dev\sports-quant-platform_ARCHIVADO_2026-07-14`). **2026-07-11**: retirada la copia paralela de `C:\Nueva carpeta (2)` — sus mejoras se portaron a `C:\dev` (ver [[Bitácora/2026-07-11]]), sus 5 tareas `SQP_*_Nc2` se eliminaron y la carpeta quedó respaldada en `C:\ZIP\sports-quant-platform-Nc2-respaldo-20260711.zip`. Ya no existe pipeline paralelo ni gasto doble de cuota del API de odds.

## Riesgo

- Caps de exposición en dos capas: por liga (`max_daily`) + global (`max_total`).
- Una liga se auto-excluye del run diario si tiene picks comenzados sin liquidar.
- (En shadow todo esto opera con stake 0.)

## Pendientes

Lista viva en [[Tareas]]. Resumen:

- [ ] Evaluar la regla de salida del shadow (CLV mediana + Brier). El volumen ya está (n=191 con cierre genuino al 07-12); falta que algún mercado logre mediana > 0 con n≥30 y que un calibrador pase el gate de Brier.
- [x] ~~Revisar/promover el candidato de calibración MLB spreads~~ — obsoleto al 07-12: el candidato ya no se regenera (falla el gate de Brier OOS con los datos actuales); staging vacío, nada que promover.
- [ ] Seguimiento del quota-guard del proveedor de odds.
- [x] ~~Deuda del dashboard-history~~: escrituras atómicas en settle (07-01), filtro/"nan" de Línea (KI-018, `11bd999`) y e2e de tenis (KI-017, `7471ce4`) — todo cerrado.
