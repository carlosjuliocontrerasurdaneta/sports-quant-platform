---
tags: [estado, sqp]
creada: 2026-07-07
actualizada: 2026-08-25
---

# Estado del proyecto — Sports Quant Platform

> Snapshot al 2026-08-04, con la actualización del 2026-08-25 abajo. Punto de entrada: [[00 - Inicio]].
> Las cifras de probabilidad son siempre **probabilidades estimadas**, nunca certezas; el ROI esperado es una estimación y el ROI realizado es el observado.

## Actualización 2026-08-25 — auditoría integral

**Software sano, sin ventaja.** `ruff` limpio, `mypy` 95 archivos sin
incidencias, `pip-audit` 0 vulnerabilidades, `health_check` OK, suite completa
en verde.

**Los dos números que gobiernan el proyecto hoy** (medidos sobre 13.861 filas
servidas / 1.200 eventos, IC95 clusterizado por evento):

1. **El mercado bate al modelo y es significativo.** Brier calibrado 0,23261 vs
   0,23013, diff **+0,00248 IC95 [+0,00051, +0,00444]**. El `market_shrink`
   óptimo walk-forward es **1,00 en los cuatro cortes** — el modelo no aporta
   información sobre el consenso sin vig en ningún momento medido.
2. **La escalera de `min_edge` va al revés.** Subir el umbral empeora
   monótonamente hit rate (0,430 → 0,301) y ROI (−11,0% → −23,9%). Donde el
   modelo declara ≥8% de ventaja, el ROI realizado es **−23,9% [−41,0%, −5,4%]**.

Es la sexta medición negativa independiente, y la más específica: no solo no hay
ventaja, sino que **el criterio de selección apunta al lado equivocado** y la
palanca canónica para corregirlo es contraproducente. Ver [[Bitácora/2026-08-25]].

**Lo que cambió operativamente:** la pregunta fundacional ahora **se mide sola**
cada mes (`scripts/model_vs_market_report.py`, enganchado a `VALIDATE_OOS.bat`
en best-effort). Antes existía el código y no lo corría nadie.

**Sin cambios en producción:** `shadow_mode` sigue en `true`, stakes en 0,
`configs/default.yaml` intacto, ningún parámetro de modelo, riesgo o estrategia
tocado. El gate de predicción sigue en **0 de 32 aprobados**, y `mls|h2h` —
primer corte en completar la ventana n≥300 — dio `no_bate_al_mercado`.

## Objetivo sacrosanto: GANAR DINERO (directiva 2026-08-02)

Directiva de Carlos, textual: **"El fin del sistema es ganar dinero, eso
escríbelo sobre piedra. Es sacrosanto."** La rentabilidad realizada es el fin
último; supersede el pivot a hit rate del 2026-07-27. El hit rate se reporta
siempre contra el breakeven por cuota, nunca en absoluto. (Objetivo ≠ logro:
a esta fecha no hay edge demostrado — shadow activo, gate de CLV vacío.)

## Modo de selección: EDGE (revertido el 2026-07-31)

**`pick_mode: edge` es el modo activo en producción** desde el 2026-07-31
(commit `f6c2130`, decisión explícita del operador). El modo precisión
(`accuracy`, activo del 07-28 al 07-31) se revirtió porque seleccionar por
probabilidad ≥ 0.70 elegía favoritos extremos con cuotas observadas 1.07–1.16:
a cuota 1.07 el punto de equilibrio es 93.5% de aciertos, así que el modo subía
el hit rate y perdía dinero **por construcción**, además de recortar el sistema
a 1 de sus 3 mercados (solo h2h).

- El mismo commit añadió `breakeven_probability(price) = 1/price` y las
  columnas `breakeven_hit_rate` / `hit_rate_margin` al reporte por segmento:
  todo hit rate se juzga contra lo que la cuota exige, nunca en absoluto.
- El modo accuracy queda **disponible y conmutable** (`picks.mode: accuracy` o
  env `PICK_MODE`, umbral 0.70, solo moneyline, stake plano); sus advertencias
  (umbral sobre blend no calibrado, sin backtest propio) siguen vigentes si se
  reactiva. Ver [[Bitácora/2026-07-28]] y [[Bitácora/2026-08-02]].
- La redefinición de objetivo del 2026-07-27 (hit rate como métrica rectora de
  REPORTE: observado vs prometido por banda) se mantiene; lo que se revirtió es
  usarla como criterio de SELECCIÓN.

## Modo operativo: SHADOW LEVANTADO — el gate de CLV es ahora la única barrera

**2026-08-16, decisión explícita del operador: `shadow_mode: false`.**

Lo que esto cambia y lo que no, medido antes de tocarlo:

- **Riesgo de capital hoy: sigue siendo cero.** El gate de CLV por (liga, mercado)
  está *por debajo* de shadow y es **default-deny**. Las 24 entradas de
  `data/bets/clv_gate.json` están en `allowed: false`, así que todos los picks
  siguen con stake 0. Verificado ejecutando `_zero_stake_flag` sobre el registro
  completo: **24 mercados a stake 0, 0 con stake real**.
- **Lo que sí cambia:** el flag que verán los reportes pasa de `shadow_mode` a
  `clv_gate`, y el gate deja de ser invisible para convertirse en la barrera
  vinculante y visible.
- **⚠️ CONSECUENCIA A VIGILAR:** con shadow levantado, un mercado pasa a llevar
  **dinero real de forma AUTOMÁTICA** en cuanto la auditoría diaria de CLV le
  escriba `allowed: true` (CLV mediano > 0 sobre ≥30 apuestas liquidadas
  emparejadas a cierre). **Ya no hace falta ninguna aprobación humana en ese
  punto.** Para mantener la aprobación manual: `clv_gate.enabled: false` y curar
  el registro a mano, o volver a poner `shadow_mode: true`.
- **RESUELTO el 2026-08-17:** la regla de salida por mercado es ahora el **gate de
  predicción** (`prediction_gate.enabled: true`; el de CLV pasa a
  `enabled: false` y queda como evidencia). Un mercado lleva stake real solo si su
  modelo puro bate al mercado en test de signo pareado **fuera de muestra**
  (n ≥ 300, p < 0,05) **y** su EV a stake plano es positivo. Criterio
  pre-registrado antes de implementar. **Hoy no lo pasa ningún mercado** — la
  ventana de validación arranca tras el pre-registro, así que la evidencia se
  acumula desde cero. Ver [[Bitácora/2026-08-17]].

### Historial

- `shadow_mode: true` desde el 2026-07-03 (commit `fe9ef84`) hasta el 2026-08-16.
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

- **Train ≠ promote**: el reentreno diario presenta candidatos en staging. Desde el 2026-08-04 `calibration.auto_promote: false` vuelve a ser el default autoritativo: ningún calibrador cambia el registro live sin aprobación humana explícita. La función opcional de auto-promoción conserva gates OOS y exige ≥30 eventos independientes, pero solo puede activarse deliberadamente; la vía normal es `scripts/promote_calibration.py`.
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
