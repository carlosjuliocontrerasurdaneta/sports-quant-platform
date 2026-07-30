# Backlog — Auditoría 2026-07-29/30

Lo que no se corrigió, por qué, y qué haría falta para cerrarlo.
Esfuerzo: S (< 1 h) · M (1–4 h) · L (> 4 h).

## P0 — Bloquean la interpretación del sistema actual

| ID | Ítem | Dep. | Esf. | Riesgo si no se hace | Criterio de aceptación | Decisión humana |
|---|---|---|---|---|---|---|
| B-02 | **Backtest de la regla vigente.** Parametrizar `realized_roi_backtest` con el modo de selección y añadir `hit_rate` + `n` por banda de `p_decision` a `_summarize`; re-correr `validate_oos.py` con `pick_mode=accuracy`. | — | L | El proyecto no tiene ninguna estimación OOS del KPI que persigue. El −5.32% mide otra regla. | `validate_oos.py --pick-mode accuracy` reporta hit rate y `gap` por banda con `n`, y el resultado queda en la bitácora. | No: es ingeniería. Sí para actuar sobre el resultado. |
| Q-02 | **Decidir el significado del umbral frente a `market_shrink: 0.5`.** Con el blend al 50%, "≥0.70" es `p_model + fair ≥ 1.40`: el mercado aporta la mitad del criterio y el edge sale negativo contra el precio con vig. Opciones: (a) aplicar el umbral a `cal(p_model)` con calibrador obligatorio y usar `fair` solo como filtro de sanidad; (b) mantener el blend y documentar que el umbral no es una afirmación del modelo. | Q-01 | M | Se mide el hit rate contra un umbral que no describe lo que el sistema estima. | Decisión registrada en `Obsidian/Bitácora` con su justificación, y el README actualizado. | **Sí — cambia la política de selección.** |
| Q-01 | **Entrenar y promover un calibrador `<liga>_h2h`, o aceptar formalmente que el modo precisión corre sin calibrar.** Hoy el WARNING lo hace visible, pero la premisa sigue incumplida. | — | M | "Probabilidad calibrada ≥ 0.70" es literalmente falso hoy. | O existe `<liga>_h2h` en `calibration_methods.json` con gates pasados, o `accuracy_threshold` se reinterpreta según Q-02. | **Sí — promoción de calibrador.** |
| K-010 | **Definir el gate de salida del shadow para el modo precisión.** Pendiente nº1 de `Obsidian/Tareas.md`. Propuesta del operador: "hit rate observado ≥ prometido por banda con n suficiente". Requiere fijar `n` mínimo y un intervalo de confianza que excluya el umbral (ver B-11). | B-02, B-11 | M | El shadow no tiene condición de salida, luego no puede terminar. | Gate escrito como loop o skill, con umbral numérico y `n` mínimo justificados. | **Sí — decisión estadística.** |
| S-1 | **Alerta de fallo del run diario.** `SQP_Diario_Completo_Cdev` falló el 2026-07-29 (`LastTaskResult = 1`) y no hay ningún mecanismo de alerta en el repo. Mínimo: escribir un centinela en `:error_settle`/`:error_run` de `DIARIO_COMPLETO.bat` y que el health check lo lea. | — | S | Los fallos de producción son invisibles. Ya ocurrió. | Un fallo del batch produce una señal observable sin abrir el Programador. | **Sí — modifica scripts de producción.** |
| — | **Investigar por qué falló el run del 2026-07-29.** Requiere leer `logs/`, prohibido para el agente por las reglas del repo. | S-1 | S | Causa desconocida; puede repetirse. | Causa identificada y registrada en la bitácora. | Sí — el operador debe revisar los logs. |

## P1 — Riesgo antes de cualquier movimiento a dinero real

| ID | Ítem | Dep. | Esf. | Riesgo | Criterio de aceptación | Decisión humana |
|---|---|---|---|---|---|---|
| B-11 | **Incertidumbre en todo el stack de evaluación.** No existe ninguna implementación (`bootstrap\|wilson\|binomtest` → 0 resultados). Mínimo: intervalo de Wilson para hit rate y beat-close, bootstrap por bloques para ROI y CLV mediana. Exigir que el IC excluya el umbral, no solo el punto estimado. | — | M | `segments.py:155-159` flaguea con `\|gap\| >= 0.07` a `n >= 15`, cuando el error estándar es ≈0.13: **los gates disparan por debajo del ruido**. | Toda métrica de los reportes lleva `n` e IC. | No |
| B-03 | **Alinear el ancla temporal del backtest con producción.** Usar el snapshot más antiguo del día (o el más cercano a la hora real de generación) como entrada y ancla; reservar el último pre-commence solo para CLV. | — | M | El backtest está mejor informado que producción → resultados optimistas en la dirección desfavorable. | El backtest reproduce la información disponible a las 11:00. | No |
| B-04 | **Congelar los parámetros de riesgo fuera de la ventana de test.** Incluirlos en `_freeze_on_train` o reportar el resultado con los defaults de riesgo como contraste. | B-03 | M | `max_plausible_edge`, `uncertainty_penalty`, `market_shrink`, `min_edge` y `max_stake_pct` se eligieron maximizando ROI sobre la misma ventana que se llama OOS. | El informe OOS distingue parámetros congelados de sintonizados. | No |
| B-07 | **Adaptar el monitor de degradación al objetivo hit rate.** Usar `_decision_prob` en lugar de `estimated_probability`, y con `pick_mode == accuracy` sustituir el criterio de ROI por uno de hit rate vs prometido por banda. | B-11 | M | El Brier se mide sobre una probabilidad que ya no decide, y `roi_pause: -0.15` puede **auto-pausar permanentemente el único mercado habilitado**: la histéresis exige `roi_flat >= -0.05`, umbral que el modo precisión probablemente nunca alcance. | El monitor juzga por la métrica rectora y su histéresis es alcanzable. | **Sí — política de riesgo.** |
| B-15 | **Kill switch y límite de drawdown con enforcement.** `_max_drawdown` se calcula y solo se publica. Propuesta: umbral en `default.yaml` que fuerce `shadow_mode`, reutilizando `_zero_stake_flag`. | — | S | No hay freno automático. El único freno implícito (banca ≤ 0 → Kelly) no aplica en modo precisión. | Superar el drawdown fuerza stake 0 de forma verificable por prueba. | **Sí — control de riesgo.** |
| Q-04 | **Gate de calibración sobre la banda ≥ umbral.** Para claves `*_h2h`, exigir en `[threshold, 1)` que `n >= n_min` y `\|prob_media − frecuencia_observada\| <= tol`; sin muestra en la banda, no promover. | Q-01 | S | Un calibrador que mapee `0.55 → 0.85` pasa los 4 gates actuales y, con el modo precisión, **fabrica picks en masa**. | El gate rechaza un calibrador que infle la banda de selección. | **Sí — criterio de promoción.** |
| Q-06 | **Renormalizar por mercado tras calibrar**, o permitir como máximo un pick por `(evento, mercado)` en modo precisión. | Q-01 | S | Latente hoy. Al promover un calibrador h2h, ambos lados del mismo partido podrían superar 0.70 → picks contradictorios que contaminan el KPI por banda. | `sum(p_decision)` por `(evento, mercado, punto)` = 1, con prueba. | No (es corrección), pero debe ir **antes** de Q-01. |
| Q-07 | **Exigir `books_count >= min_books_for_consensus` en `_accuracy_selected`.** | — | S | `fair` —el 50% del criterio— puede venir de un solo libro, con overround no representativo. | Un h2h con 1 libro no genera pick de precisión. | **Sí — cambia qué picks se emiten.** |
| Q-08 | **Revalidación equivalente para picks de precisión.** Recalcular `p_decision` con el `fair` del snapshot fresco y revocar si cae bajo el umbral; flaguear `price_moved`. | — | M | Los picks de precisión están exentos de la revalidación por edge (correctamente) pero **sin sustituto**: nada verifica que la cuota siga disponible al comienzo. | Un pick cuyo `p_decision` cae bajo el umbral se revoca, con log. | **Sí — política de revocación.** |
| B-17 | **Quitar `generated_at` de `DEDUP_KEY`** (o sustituirlo por el día). Es el instante del run, no la identidad económica de la apuesta. | — | S | Dos runs el mismo día **doblan** stake y pnl en `settled_*.csv`, que es la fuente única del ledger, del ROI y del entrenamiento del calibrador. | Reproducir el mismo pick dos veces produce una sola fila liquidada. | **Sí — cambia la semántica de dedup sobre datos ya liquidados.** |
| B-16 | Descontar los stakes en vuelo de la banca al dimensionar exposición. | — | S | La exposición se calcula sobre una banca ya parcialmente comprometida. Latente bajo shadow. | Los caps consideran picks no liquidados. | No |

## P2 — Integridad de datos

| ID | Ítem | Esf. | Riesgo | Criterio de aceptación | Decisión humana |
|---|---|---|---|---|---|
| D-03 | **`force_refresh` o TTL ≤ 300 s en el run diario** (hoy 6 h), o persistir el snapshot con el `captured_at` real de la caché. | S | Picks precificados con cuotas de hasta 6 h y **sin snapshot de entrada**, lo que impide medir CLV. Consistente con "CLV n=300 mediana 0.00". | Todo run diario deja snapshot con `captured_at` propio. | **Sí — aumenta el gasto de API de pago.** |
| B-09 | **Exigir `captured_at > generated_at` del pick** en `load_closing_odds`, y reportar `n_same_snapshot` aparte. | S | Entrada y "cierre" pueden ser el mismo snapshot → `clv_pct = 0` exacto, que es lo que deja el gate de CLV vacío. | El CLV se calcula solo contra cierres posteriores al pick. | **Sí — altera la muestra del gate.** |
| D-02 | **Clave de dedup normalizada en `results_store`**: por `game_id` cuando no está vacío, y por `(date, nk(home), nk(away))` cuando lo está. Medir primero cuántos duplicados hay con un script de solo lectura. | M | Un cambio de ortografía del vendor duplica el partido en el fit de Elo y en las features. | Un partido con dos ortografías entra una sola vez. | **Sí — requiere migración del store.** |
| D-10 | Versionar la config del builder en el manifest de features. | S | Cambiar `rolling_windows`/`ewm_span` o el código del builder no invalida la caché → el dataset servido deja de corresponder al builder. | Cambiar un parámetro del builder fuerza rebuild. | No |
| D-12 | Validación de esquema/tipos en la ingesta de resultados (scores numéricos ≥ 0, `home != away`, fecha real). | S | Un cambio de esquema del vendor entra y falla más tarde y más lejos. | Fila malformada rechazada con log en el punto de ingesta. | No |
| D-13 | Descartar (con contador) las filas de tenis sin `game_id`, o clavear por `(date, frozenset(players))`. | S | Todos los partidos sin id se sobrescriben mutuamente y sobrevive uno solo, sin log. | Ningún partido desaparece en silencio. | No |
| D-14 | WARNING explícito de "nombre no reconocido" en `run_league`, contando los equipos cuyo key normalizado no aparece en el histórico. | S | `team_aliases.yaml` está vacío; un fallo de match es indistinguible de un equipo genuinamente nuevo. | Un nombre no reconocido produce un WARNING nominal. | No |
| D-07 | Reintentos en `MLBStatsProvider` (tiene timeouts, no retry). | S | Un 5xx transitorio aborta el backfill completo. | Un 5xx transitorio no aborta el backfill. | No |
| D-11 | Idempotencia de `backfill_historical_odds` cuando el snapshot cae en otro día. | S | La siguiente corrida re-paga ~10× créditos y duplica snapshot. | Re-ejecutar no vuelve a gastar créditos por el mismo día. | No |
| D-15 | Lock en `revalidation._append_log`. | S | Dos pases solapados pierden el append del más lento. | Appends concurrentes no se pierden. | No |
| D-17 | Leer solo el archivo de cuotas del mes en curso en `_league_odds`. | S | `pd.concat` sobre todo el histórico en cada pase horario: coste lineal creciente. | Coste del pase independiente del tamaño del histórico. | No |
| D-16 | Importar `storage/atomic.py` en `served_store` en lugar de reimplementarlo, y añadir lock a `append_served`/`append_graded`. | S | Riesgo latente (hoy la programación es secuencial). | Una sola implementación de escritura atómica. | No |
| D-19..D-25 | `fsync` en `atomic.py`; `date.today()` → UTC en 5 providers; guard en `starter_fip.py:60`; versión de payload en `odds_cache`; contador persistente de degradaciones del lock; 4 excepciones silenciadas con log (`mlb_statsapi.py:97-100`, `espn_results.py:136-137`, `features/common.py:34-35`, `cleanup.py:120`). | M | Fallos silenciosos y diagnóstico difícil. | Ninguna excepción de datos se descarta sin contador ni log. | No |

## P3 — Operación, seguridad y calidad

| ID | Ítem | Esf. | Criterio de aceptación | Decisión humana |
|---|---|---|---|---|
| S-2 | Reducir `ExecutionTimeLimit` de PT72H a PT20M (captura) / PT2H (diario y backfill) en las 6 tareas programadas. | S | Un proceso colgado no retiene el lock 3 días ni descarta 144 capturas de cierre. | **Sí — Programador de tareas.** |
| S-3 | Encadenar `BACKFILL_ALL.bat` → `REFRESH_ML.bat` en un solo .bat (como ya se hizo con `DIARIO_COMPLETO`) y añadir lockfile entre captura y diario. | S | Ninguna tarea escribe los mismos artefactos que otra en curso. | **Sí — scripts y Programador.** |
| S-4 | Log por proceso (`sqp_<pid>.log`) o un solo escritor. | S | La rotación no falla con procesos concurrentes en Windows. | No |
| S-6 | Subir la pata Windows de CI a Python 3.14 (la versión real de producción). | S | La combinación SO+versión de producción se prueba en CI. | Sí — depende de disponibilidad en el runner. |
| S-8 | Que el fallback de `SQP_PYTHON` avise en lugar de degradar en silencio. | S | Un intérprete ausente produce un WARNING en el log. | **Sí — scripts de producción.** |
| S-14 | Sustituir `Read(./.env.*)` por denies específicos para que `.env.example` sea auditable. **Deliberadamente no aplicado:** relajar un deny de secretos es la dirección equivocada. | S | `.env.example` legible sin abrir un hueco para `.env.staging`. | **Sí — control de seguridad.** |
| S-15 | Validar `sport`/`name` contra `^[a-z0-9_]+$` antes de construir la ruta de `joblib.load`. | S | Un id de liga con `..` no puede eludir la separación staging/live. | No |
| S-12 | Pasar el argumento de `rotate_log.cmd` por variable de entorno. Hoy no explotable (todos los llamadores pasan literales). | S | Un argumento con comilla simple no puede romper la cadena. | No |
| — | **Auditoría de calidad de código y arquitectura.** El subagente asignado agotó su límite de sesión sin devolver informe. No hubo revisión sistemática de acoplamiento, dependencias circulares, código muerto, duplicación `scripts/` ↔ `src/`, ni cobertura por módulo. `daily.py` supera las 700 líneas y concentra fetch, merge, probabilidades, edge, staking y persistencia. | L | Informe con los 10 módulos más grandes, código muerto verificado por grep y módulos núcleo sin prueba. | No |
| — | Ejecutar `pip-audit -r requirements.lock`. **No puedo confirmar** que el lock siga limpio; el último saneamiento es del 2026-07-02 y CI lo declara bloqueante. | S | `pip-audit` en verde o vulnerabilidades registradas. | No |
| — | **Revisar `logs/` en busca de URLs con `apiKey=` anteriores al fix de redacción del 2026-07-24.** El agente no puede leer `logs/`. Si existen rotaciones previas a esa fecha, tratar la clave de The Odds API como potencialmente expuesta en disco y **rotarla**. | S | Confirmado que no hay claves en logs, o clave rotada. | **Sí — rotación de credencial.** |

## P4 — Claude Code y documentación

| ID | Ítem | Esf. | Decisión humana |
|---|---|---|---|
| — | Completar los 10 loops quant no diarios (05, 06, 07, 08, 09, 11, 12, 13 y el 00) con precondiciones, comandos concretos y artefactos, usando el 10 como plantilla y `STATES.md` para los estados. | M | No |
| K-012 | Decidir un solo clasificador (`decision-engine.md` como tabla loop→tarea, y el JSON solo agente/modelo); anclar keywords a límites de palabra; corregir `full-audit → refactor.md`. | S | **Sí — decisión de diseño.** |
| K-023 | Resolver `superpowers-main`: borrar los 172 archivos, o actualizar `.gitignore:27-29` y KI-015 explicando la re-vendorización. **No puedo confirmar** si fue intencional. | S | **Sí.** |
| ~~K-013~~ | ~~Borrar `MODEL_ROUTER_INTEGRATION.json` de la raíz.~~ **RESUELTO 2026-07-30:** el operador autorizó borrarlo; era un manifiesto de andamiaje sin consumidor. | — | Hecho |
| K-026 | Borrar `.claude/settings.local.json.backup-audit-20260623` (36 días). Cerrar M-7 (permisos amplios de `settings.local.json`). | S | **Sí.** |
| K-025 | Promover 1-2 ítems de `Tareas.md` a `backlog.md` con status `ready`, o documentar que el backlog autónomo es intencionalmente manual. | S | **Sí.** |
| Q-05 | Revalidar OOS y activar `pitcher_bound` (>0), **o** corregir el docstring de `adapters.py` que afirma que el abridor es "the largest single factor" cuando es un no-op. Registrar cuál antes de juzgar el hit rate de MLB. | M | **Sí — parámetro de modelo.** |
| Q-10 | Renombrar `calibrated_probability` → `decision_probability`, o añadir `calibrator_applied: bool` por fila. | S | Sí — rompe esquema de artefactos existentes. |
| Q-11 | Actualizar el comentario de `default.yaml` (dice `n_val_events >= 15`; el código usa 30). | S | No |
| Q-09 | Documentar en el esquema que `estimated_edge` se deriva de `calibrated_probability`, o persistir `edge_from_estimated`. | S | No |
| Q-13 | Documentar en el model card que la ruta ML no está en producción; corregir la clave a `calibration_key(sport, "h2h")` si algún día se conecta. | S | No |
| Q-15 | Añadir el ECE/Brier del calibrador **live** al gate (hoy compara contra *raw*) y conservar el modelo sustituido como `*_prev.joblib` para permitir rollback. | S | No |
| B-10 | Devolver `None`/`NaN` en lugar de `0.0` cuando `staked == 0` y renderizar "n/a (stake 0)"; añadir tarjeta de hit rate por banda al dashboard. | S | No |
| B-12 | Etiquetar las tablas de `patterns.py` como "in-sample, regla edge (no la política vigente)" y mostrar IC junto al hit rate. | S | No |
| K-011 | Generar `graphify-out/wiki/` o quitar la referencia del `CLAUDE.md` raíz. | S | No |

## Resumen de decisiones humanas requeridas

**23 ítems** requieren autorización. Los seis más urgentes:

1. **Autorizar (o no) el commit** de este trabajo: 58 archivos modificados, 3 creados,
   17 duplicados eliminados. Nada commiteado.
2. **Q-02 / Q-01:** qué significa el umbral 0.70 frente a `market_shrink: 0.5`, y si
   se entrena un calibrador h2h o se reinterpreta el umbral.
3. **S-1:** alerta del run diario, que falló el 2026-07-29 sin que nadie se enterara;
   y revisar los logs para saber por qué.
4. **B-07:** el monitor de degradación puede auto-pausar permanentemente el único
   mercado habilitado.
5. **K-023:** destino de `superpowers-main` (la contradicción documentada).
6. **Rotación de la clave de The Odds API** si `logs/` conserva rotaciones anteriores
   al 2026-07-24.
