# CHANGES — ronda `audit-2026-09-22`

Fase de **remediación autorizada**. El operador autorizó expresamente las fases 4
y 5 el 2026-09-22, con alcance «todos los hallazgos confirmados del informe más
las mejoras sustentadas por la evidencia».

- **Base:** `9fa276a` (`main`).
- **Estado del árbol antes de corregir:** limpio salvo los entregables de
  diagnóstico bajo `audit/`.
- **Línea base de validación:** `ruff` rc 0, `mypy` rc 0, suite
  `1 failed, 2263 passed, 1 skipped` (el fallo, `ENVIRONMENTAL_FAILURE`, es
  `AUD-004`), subconjunto `not slow` 2040 passed en 796,09 s,
  `pip-audit` sin vulnerabilidades.
- **Ficheros tocados:** 13 (5 de `src/`, 5 de `tests/`, 3 de `.claude/`).
  Ninguno fuera del alcance de un hallazgo. Sin refactors, sin limpiezas y sin
  actualizaciones de dependencias ajenas al defecto.

---

## AUD-007 — El hook `Stop` de pruebas no cabe en su timeout · P1

- **Estado inicial:** confirmado, `REPRODUCED` (796,09 s medidos contra 600 s).
- **Causa:** presupuesto de tiempo fijado una vez (600 s, sobre una medición de
  270,73 s) contra una suite que crece. Y una segunda mitad más grave: un proceso
  que mata el harness **no ejecuta ni una línea más**, así que la puerta moría
  muda y el turno cerraba en verde.
- **Archivos:** `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh`.
- **Cambio:**
  1. `timeout` del hook de pruebas 600 → **1200** (sólo ese; el de
     `crossreview-on-stop.sh` se deja en 600).
  2. El script se **autoacota** con `timeout $PRESUPUESTO_S` (1080 s, por debajo
     del presupuesto del harness) para ganar siempre la carrera y poder hablar.
     `rc 124` se trata como rama propia: **no son tests en rojo**, es que no hay
     veredicto. Se anuncia en voz alta, se sale con 0 (el modelo no puede acortar
     la suite a mitad de turno) y **el centinela se deja puesto**: «no se pudo
     comprobar» no es «está bien». Si `timeout` no está disponible se ejecuta
     igual, sin autoacotado.
  3. La serie de mediciones (270,73 → 489,76 → 796,09 s) queda en la cabecera del
     script, como ya hacía con las anteriores.
- **Prueba:** no es código del paquete. Validación = medición (§VALIDATION).
- **Aceptación:** el comando del hook cabe en su presupuesto con ~35 % de margen,
  y un hook interrumpido dice qué pasó en vez de morir mudo.
- **Riesgos residuales:** la suite seguirá creciendo. El autoacotado convierte el
  próximo rebase en un aviso ruidoso en vez de en un silencio, pero **no** lo
  evita: hay que volver a medir. El aviso nombra el fichero y la constante.
- **Estado final:** corregido, pendiente de verificación independiente.

## AUD-001 — El gate reparte alpha entre 41 cortes y evalúa 49 · P2

- **Estado inicial:** confirmado, `STATICALLY_VERIFIED`.
- **Archivos:** `src/sqp/risk/prediction_gate.py`, `tests/test_prediction_gate.py`.
- **Cambio — opción (a) del backlog, SÓLO instrumentación:**
  - `fwer_bound(n_cortes, alpha)`: cota real de Bonferroni del error de familia.
  - El aviso se emite al superar **`PREDICTION_GATE_K`**, no
    `PREDICTION_GATE_K_REPREGISTRO`. Entre 42 y 50 cortes el criterio ya estaba
    incumplido y nadie lo decía. Por encima de 50 sube a `log.error`.
  - El registro publica `fwer_bound` junto a `family_alpha`: la discrepancia se
    lee, no hay que calcularla a mano.
- **Lo que NO se ha tocado, deliberadamente:** `PREDICTION_GATE_K = 41`,
  `PREDICTION_GATE_ALPHA`, `PREDICTION_GATE_MIN_N`, `VALIDATION_START` y el
  pestillo. Son el **criterio pre-registrado**, y `CLAUDE.md` clasifica los
  parámetros de gate como clase de escalación. La opción (b) del backlog
  —re-pre-registrar `K`— sigue siendo **decisión del operador** y no se ha
  ejecutado. Ningún veredicto del gate cambia con este commit: hoy los 49 cortes
  siguen en `muestra_insuficiente` y `allowed` sigue vacío.
- **Pruebas:** `test_fwer_bound_es_el_alpha_por_corte_multiplicado_por_los_cortes`,
  `test_el_aviso_salta_al_superar_K_no_al_superar_el_limite_de_repregistro`,
  `test_con_el_universo_dentro_de_K_no_hay_aviso_y_la_cota_cuadra`.
- **Aceptación:** con 49 cortes el aviso se emite y el registro publica una cota
  (0,0598) por encima del alpha declarado (0,05). Cumplido.
- **Riesgos residuales:** **el criterio sigue incumplido**. Esto lo hace visible,
  no lo arregla. La decisión de fondo sigue abierta y es urgente: basta con que
  un corte alcance `n ≥ 300` para que gaste su único test de entrada con un alpha
  que sobregira el presupuesto de familia.
- **Estado final:** corregido *en lo instrumentable*; la decisión de fondo queda
  **pendiente del operador**.

## AUD-008 — La revisión cruzada de Codex no se ejecuta · P2

- **Estado inicial:** confirmado, `REPRODUCED`.
- **Causa de fondo:** fuera del repositorio (runtime de Codex y plugin
  `openai-codex/codex/1.0.6`). El proyecto no puede corregirla.
- **Archivos:** `.claude/memory/known-issues.md`.
- **Cambio:** registrada como **KI-056**, enlazada con KI-055 (misma avería por
  la otra vía) y con el patrón KI-035 (fallo de infraestructura disfrazado de
  veredicto). Queda escrito que `setup` y `--version` se declaran sanos sobre un
  servicio que no responde, y que la confirmación exige una **tarea real**.
- **Lo que NO se ha hecho:** desactivar la puerta `Stop` del plugin. El
  clasificador de permisos lo denegó por debilitar un control, y la denegación es
  correcta: el contrato de auditoría prohíbe tocar controles para obtener un
  cierre satisfactorio. Es decisión del operador.
- **Aceptación:** el estado queda registrado y diagnosticable. Cumplido.
- **Riesgos residuales:** todo cambio de riesgo cierra turno **sin revisión de un
  tercero**, incluida esta misma remediación. CI ejecuta la suite completa al
  publicar, pero eso es otro control y no sustituye a éste.
- **Estado final:** **no aplicable al repositorio**; documentado y abierto.

## AUD-002 — La captura Fase 1 no tiene control de cobertura · P2

- **Estado inicial:** confirmado, `INFERRED`.
- **Archivos:** `src/sqp/pipeline/team_totals_capture.py`,
  `tests/test_team_totals_capture.py`.
- **Cambio:** `coverage_baseline()` calcula la mediana de eventos capturados por
  día en los `COVERAGE_BASELINE_DAYS` (7) anteriores, **excluyendo el día en
  curso**, que es lo que se quiere juzgar. Si los candidatos del horizonte caen
  por debajo de `COVERAGE_MIN_FRACTION` (0,5) de esa mediana, se emite `WARNING`.
  El resumen y el log llevan ahora `candidates` y `coverage_baseline`.
- **Por qué mira los CANDIDATOS y no lo capturado:** una recolección corta puede
  fallar en dos sitios —el proveedor devuelve pocos eventos, o el presupuesto
  corta el bucle— y sólo el primero es invisible. El segundo ya lo delata `stop`.
- **Sin histórico no se avisa:** un aviso que no distingue «hoy hay pocos
  partidos» de «falló la recolección» no informa de nada.
- **Pruebas:** `test_la_cobertura_baja_se_avisa_contra_la_mediana_reciente`
  (reproduce el 2026-09-21: 3 candidatos contra mediana 14),
  `test_una_jornada_normal_no_avisa_de_cobertura`,
  `test_sin_historico_no_se_avisa_de_cobertura`.
- **Riesgos residuales:** sigue sin poder distinguirse un calendario corto de un
  fallo del proveedor; el aviso pide mirar, no diagnostica. Y sigue sin ser
  verificable si la MLB jugó 3 partidos el 2026-09-21.
- **Estado final:** corregido, pendiente de verificación independiente.

## AUD-003 — El tope diario de créditos se rebasa · P3

- **Estado inicial:** confirmado, `REPRODUCED` en producción (`46/45`).
- **Archivos:** `src/sqp/pipeline/team_totals_capture.py`,
  `tests/test_team_totals_capture.py`.
- **Cambio:** constante `CREDITS_PER_EVENT = 2` y guarda sobre el coste
  **previsto** (`already + spent + CREDITS_PER_EVENT > MAX`), en los topes diario
  y mensual. La guarda pasa de «¿ya me pasé?» a «¿me pasaré si pido esto?».
- **Nota importante sobre el test:** `test_captura_respeta_el_tope_diario_antes_de_llamar`
  **codificaba el defecto como comportamiento esperado** (`credits_spent == 46`,
  con un comentario que lo justificaba). Se ha reescrito para fijar el invariante
  correcto —44 créditos, 22 llamadas, `<= MAX_CREDITS_PER_DAY`— y se ha añadido
  `test_el_tope_diario_nunca_se_rebasa_sea_par_o_impar`, parametrizado con topes
  par e impar, que fija el invariante en vez de un conteo. **Esto endurece la
  aserción, no la debilita.**
- **Riesgos residuales:** `CREDITS_PER_EVENT` es una constante del proyecto y el
  coste real lo fija el proveedor en la cabecera de respuesta. Si el proveedor
  cambia el precio por evento, la guarda se queda corta otra vez —acotada, eso sí,
  a un evento—. El gasto real sigue contándose por el `delta` observado.
- **Estado final:** corregido, pendiente de verificación independiente.

## AUD-004 — Aserción de reloj de pared no determinista · P3

- **Estado inicial:** confirmado, fallo observado a 4,485 s y 5/5 en verde aislado.
- **Archivos:** `src/sqp/storage/atomic.py`, `tests/test_audit_atomic_readers.py`.
- **Cambio:** el plazo de reintento sale del literal enterrado en `_replace` a la
  constante de módulo `REPLACE_RETRY_SECONDS = 2.0`. La prueba mide **sólo** la
  llamada a `publish()` (antes el cronómetro arrancaba antes, e incluía
  serialización y fixtures) y se acota contra `3 * REPLACE_RETRY_SECONDS`, con
  mensaje que nombra la propiedad comprobada.
- **Por qué no basta con subir el número:** un límite mayor pero igual de
  arbitrario reproduce el defecto más lejos. Lo que se comprueba es que
  `_replace` **no reintenta indefinidamente**, y eso se acota contra su plazo.
- **Riesgos residuales:** sigue siendo una medida de tiempo, luego sigue siendo
  sensible a una máquina patológicamente lenta; el margen es ahora 3× el plazo y
  proporcional a él, no un número suelto.
- **Estado final:** corregido, pendiente de verificación independiente.

## AUD-005 — `bankroll.summary()` fuera de la definición canónica de ROI · P3

- **Estado inicial:** confirmado, divergencia **latente** (hoy −0,152588 por
  ambas vías).
- **Archivos:** `src/sqp/risk/bankroll.py`, `tests/test_bankroll.py`.
- **Cambio:** `summary()` enruta por `settle.realized_roi_parts` y `staked_mask`.
  `realized_pnl` sigue siendo el pnl **total** del ledger —es lo que define el
  saldo, y ahí cuentan todas las filas—; el que pasa a ser canónico es el
  numerador del **ROI**.
- **Comportamiento preservado:** el ROI del ledger real no se mueve (−0,1526), y
  las claves de salida son las mismas. `bankroll_status.py`, el dashboard y
  `html_report` no cambian.
- **Pruebas:** `test_un_void_con_pnl_no_nulo_no_contamina_el_roi_realizado`
  (activa la divergencia que hoy es latente) y
  `test_el_roi_de_summary_coincide_con_la_definicion_canonica`.
- **Efecto de hook observado y declarado:** al sustituir el import antes de
  cambiar su consumidor, el hook `PostToolUse` de formato (autofix de `ruff`)
  **borró la línea de import** por considerarla no usada, y la suite falló con
  `NameError: name 'staked_mask' is not defined`. Se repuso el import una vez
  existía el consumidor. No es un fallo del hook: es el orden en que edité.
- **Riesgos residuales:** ninguno conocido. La divergencia era latente y ahora
  hay una prueba que la activa.
- **Estado final:** corregido, pendiente de verificación independiente.

## AUD-006 — `.team_totals_credits_*` fuera de la lista de purga · P3

- **Estado inicial:** confirmado, `STATICALLY_VERIFIED`.
- **Archivos:** `src/sqp/pipeline/cleanup.py`, `tests/test_cleanup.py`.
- **Cambio:** familia `team_totals_credits` añadida a la lista blanca de
  `purge_old_artifacts`. Queda documentado que su fecha lleva guiones —que
  `_artifact_date` no reconoce, porque busca `YYYYMMDD` compacto— y que por eso
  la edad sale del `mtime`, que para un contador diario **es** su fecha.
- **Pruebas:** `test_purge_cubre_los_contadores_de_team_totals_sin_tocar_el_mes_corriente`,
  con `mtime` fijado explícitamente y comprobación final de que
  `spent_this_month` sigue devolviendo el total correcto: purgar no regala cuota.
  Se actualizaron los dos asertos exactos de familias
  (`test_purge_deletes_only_old_allowlisted_artifacts` y
  `test_purge_missing_dirs_is_noop`).
- **Riesgos residuales:** es un **borrado de ficheros**. La retención de 90 días
  no puede alcanzar al mes corriente, que es el único que `spent_this_month`
  consulta, y el test lo fija.
- **Estado final:** corregido, pendiente de verificación independiente.

---

## Arrastrado — `AUD-004` de la ronda `audit-2026-09-18`

Historial del Programador de tareas deshabilitado. **No corregido**: exige
consola elevada, fuera del alcance de esta sesión y del repositorio. Ya estaba
registrado como `KI-054` y sigue ABIERTO. La mitigación (bloque
`scheduled_tasks` en `health_check`) sigue en pie.

## Mejoras adicionales

Ninguna. Se revisó el informe en busca de mejoras «sustentadas por la evidencia»
fuera de los ocho hallazgos y no se encontró ninguna que cumpliera el criterio:
las observaciones de §7 del informe son hechos medidos (ROI realizado, estado de
las puertas, antigüedad de artefactos) o decisiones registradas del operador
(B-9), no defectos con corrección demostrada. Ampliar por iniciativa propia
habría sido salirse del alcance.
