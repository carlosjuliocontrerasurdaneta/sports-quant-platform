# BACKLOG — ronda `audit-2026-09-22`

Ordenado por prioridad, impacto y dependencia. **Ningún elemento está autorizado
para implementar.** Consolidar no autoriza correcciones: hace falta que el
operador identifique el alcance (IDs, grupo inequívoco o «todos los
confirmados»), y entonces la remediación continúa por la skill
`audit-remediation`.

---

## P1 — inmediato

### `AUD-007` — El hook `Stop` de pruebas no cabe en su timeout

- **Cambio mínimo (dos partes, ninguna debilita la puerta):**
  1. Subir `"timeout"` del hook `Stop` `run-tests-on-stop.sh` de **600** a un
     valor con margen medido (≥ 1200 s), dejando escrito contra qué medición se
     fijó, como ya hace el propio fichero con las anteriores.
  2. Sacar `rm -f "$marker"` de la rama de éxito (o registrar el intento) para
     que un hook interrumpido no condene al turno siguiente a repetir los 600 s
     sin veredicto.
- **Archivos:** `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh`.
- **Pruebas:** no es código del paquete; la validación es la medición. Añadir
  además un candado en `tests/test_claude_system_contract.py` que compare el
  `timeout` declarado con la duración medida más reciente, al estilo de los
  candados que el proyecto ya usa ahí.
- **Criterio de aceptación:** el comando exacto del hook termina dentro de su
  `timeout` con ≥ 30 % de margen en la máquina real, y un hook interrumpido no
  deja el centinela bloqueando el turno siguiente.
- **Dependencias:** ninguna.
- **Riesgo del cambio:** bajo. Subir un presupuesto no relaja ninguna aserción.
- **Autorización pendiente:** alcance ordinario.

---

## P2 — urgente

### `AUD-001` — El gate de predicción reparte alpha entre 41 cortes y evalúa 49

- **Cambio mínimo — dos opciones, y la elección es del operador:**
  - **(a) Sólo instrumentación, no toca el criterio.** Que la alarma dispare con
    `len(markets) > PREDICTION_GATE_K` en vez de `> PREDICTION_GATE_K_REPREGISTRO`,
    y que el volcado de `prediction_gate.json` publique la cota real de error de
    familia (`n_cortes_evaluados × alpha`) junto a `family_alpha`.
  - **(b) Re-pre-registro.** Fijar `K` al universo actual **antes** de que ningún
    corte alcance `n ≥ 300`, documentándolo como hizo el pre-registro del
    2026-09-04.
- **Archivos:** `src/sqp/risk/prediction_gate.py`, `tests/test_prediction_gate.py`
  y, si se elige (b), un documento nuevo en `docs/research/`.
- **Pruebas:** un test que fije que el aviso se emite en cuanto el universo
  supera el `K` con el que se repartió el alpha (49 cortes hoy lo activan), y
  otro que fije la relación `alpha = family_alpha / K` y la cota publicada.
- **Criterio de aceptación:** el registro publica la cota real y el aviso se
  emite con los 49 cortes actuales.
- **Dependencias:** ninguna técnica. **Decisión previa del operador** sobre (a)
  o (b).
- **Riesgo del cambio:** la opción (a) es puramente informativa y no mueve
  ningún veredicto (hoy los 49 cortes están en `muestra_insuficiente`). La (b)
  **cambia un umbral de gate** y altera qué p-valor basta para autorizar stake
  real.
- **Autorización pendiente:** **ESCALACIÓN.** `CLAUDE.md` clasifica los
  parámetros de riesgo/modelo/estrategia/umbral/gate como clase de escalación, y
  contradecir un criterio pre-registrado es exactamente eso. No se toca sin
  orden explícita.

### `AUD-008` — La revisión cruzada de Codex no se ejecuta

- **Causa de fondo fuera del repositorio.** El runtime de Codex abre hilo,
  devuelve `rawOutput` vacío y sale con código 1. `codex --version` responde: el
  binario está instalado, el servicio no funciona. El proyecto **no puede
  arreglar** esa causa; sí puede dejar de creerse protegido por ella.
- **Cambio mínimo (tres pasos, ninguno en `src/`):**
  1. Diagnosticar el runtime **fuera de un turno**: reautenticar `codex`,
     comprobar cuota y, si hace falta, reinstalar el plugin. Confirmar con una
     **tarea real**, nunca con `--version`.
  2. Mientras no funcione, decidir explícitamente qué hacer con el gate `Stop`
     del plugin `codex`, que hoy **bloquea el cierre** sin aportar revisión y
     además declara una causa falsa. El hook del propio proyecto
     (`crossreview-on-stop.sh`) puede quedarse: degrada correctamente, avisa de
     que la revisión no se ejecutó y no bloquea.
  3. Registrar el estado en `.claude/memory/known-issues.md` junto a `KI-055`,
     que ya recoge la caída del MCP: son el mismo problema por dos vías.
- **Archivos:** ninguno de `src/`. `.claude/memory/known-issues.md` y, según la
  decisión del paso 2, la configuración del plugin.
- **Pruebas:** una comprobación de **estado**, no de configuración:
  `codex-companion.mjs task --json "…"` debe devolver `status: 0` con salida no
  vacía.
- **Criterio de aceptación:** un turno con cambios de riesgo produce un veredicto
  real de un tercero, o el sistema dice con claridad que no lo hubo sin bloquear.
- **Dependencias:** ninguna.
- **Riesgo del cambio:** desactivar el gate del plugin **reduce** cobertura de
  revisión — pero hoy esa cobertura es cero y el coste es un bloqueo. Decisión
  del operador.
- **Autorización pendiente:** alcance ordinario.

### `AUD-002` — La captura Fase 1 de `team_totals` no tiene control de cobertura

- **Cambio mínimo:** añadir al resumen el número de eventos **candidatos**
  (`len(upcoming)`) junto a los capturados, y emitir `WARNING` cuando los
  capturados caigan por debajo de una fracción de la mediana reciente de la
  propia serie. Alternativa equivalente: llevar la cobertura de `team_totals` a
  `monitoring/health.py` como aviso accionable.
- **Archivos:** `src/sqp/pipeline/team_totals_capture.py`,
  `tests/test_team_totals_capture.py` (y `src/sqp/monitoring/health.py` si se
  elige la alternativa).
- **Pruebas:** con `upcoming` no vacío y pocas capturas se emite el aviso; el
  resumen incluye el recuento de candidatos.
- **Criterio de aceptación:** reproducir el día 2026-09-21 (3 capturados) con el
  resumen nuevo y comprobar que avisa.
- **Dependencias:** conviene hacerlo **junto a `AUD-003` y `AUD-006`**: mismo
  módulo, misma causa raíz (G2), un solo lote de validación.
- **Riesgo del cambio:** bajo. Sólo añade observabilidad; no toca el gasto, ni
  el guard prepartido, ni la probabilidad sellada.
- **Autorización pendiente:** alcance ordinario.

---

## P3 — planificado

### `AUD-004` — Aserción de reloj de pared que vuelve no determinista la suite

- **Cambio mínimo:** medir sólo la llamada a `publish()` y acotarla en términos
  del plazo de la implementación (`< 2.0 + holgura declarada`), o sustituir la
  medida de pared por un reloj inyectado que cuente reintentos. **No** basta con
  subir el número: eso reproduce el defecto más lejos.
- **Archivos:** `tests/test_audit_atomic_readers.py`.
- **Pruebas:** la propia, reescrita, ejercitada bajo carga artificial.
- **Criterio de aceptación:** 20 ejecuciones consecutivas en verde con la
  máquina cargada.
- **Dependencias:** ninguna. Conviene **antes** que nada que dependa de leer la
  suite como señal fiable.
- **Riesgo del cambio:** bajo, si la propiedad comprobada se conserva (que
  `_replace` no reintente indefinidamente).
- **Autorización pendiente:** alcance ordinario.

### `AUD-003` — El tope diario de créditos de `team_totals` se rebasa

- **Cambio mínimo:** comprobar el coste **previsto** antes de pedir
  (`already_day + spent + COSTE_POR_EVENTO > MAX_CREDITS_PER_DAY` → parar), o
  declarar el tope en número de eventos en lugar de créditos — esta segunda
  opción elimina la clase entera de error.
- **Archivos:** `src/sqp/pipeline/team_totals_capture.py`,
  `tests/test_team_totals_capture.py`.
- **Pruebas:** con tope impar y coste 2, el gasto final nunca supera el tope.
- **Criterio de aceptación:** el contador diario no excede
  `MAX_CREDITS_PER_DAY` para ningún coste por petición.
- **Dependencias:** lote con `AUD-002` y `AUD-006`.
- **Riesgo del cambio:** bajo; la dirección del cambio es **conservadora**
  (gastar menos, nunca más).
- **Autorización pendiente:** alcance ordinario. El gasto de cuota ya está
  autorizado (2026-09-19) y este cambio sólo lo reduce.

### `AUD-005` — `bankroll.summary()` fuera de la definición canónica de ROI

- **Cambio mínimo:** sustituir en `bankroll.summary()` el numerador y el filtro
  en línea por `realized_roi_parts(df)` y `staked_mask`, preservando las claves
  de salida (`realized_pnl` sigue siendo el pnl total del ledger si se usa para
  el saldo; el **ROI** pasa a usar el numerador canónico).
- **Archivos:** `src/sqp/risk/bankroll.py`, `tests/test_bankroll.py`.
- **Pruebas:** un test con una fila `void` de `pnl ≠ 0` que fije que
  `bankroll.summary()["realized_roi"]` coincide con `realized_roi_parts`. Debe
  **fallar antes** del cambio y pasar después.
- **Criterio de aceptación:** el test discrimina, y el ROI del ledger real **no
  se mueve** (−0,1526).
- **Dependencias:** ninguna.
- **Riesgo del cambio:** bajo y verificable: hoy ambas vías dan el mismo número,
  así que la regresión sería inmediatamente visible.
- **Autorización pendiente:** alcance ordinario. **Nota:** toca una métrica de
  apuestas publicada en el panel de banca y el dashboard; conviene registrar que
  el número no cambia.

### `AUD-006` — `.team_totals_credits_*` fuera de la lista de purga

- **Cambio mínimo:** añadir
  `"team_totals_credits": (root / "data" / "odds", ".team_totals_credits_*")` al
  diccionario `families` de `purge_old_artifacts`.
- **Archivos:** `src/sqp/pipeline/cleanup.py`, su test.
- **Pruebas:** un contador de hace 100 días se purga; uno del mes corriente
  sobrevive y `spent_this_month` sigue devolviendo el total correcto.
- **Criterio de aceptación:** el anterior, verde.
- **Dependencias:** lote con `AUD-002` y `AUD-003`.
- **Riesgo del cambio:** bajo. La retención de 90 días no puede alcanzar al mes
  corriente, que es el único que `spent_this_month` consulta. **Aun así es un
  borrado de ficheros**: exige la comprobación de rutas y consumidores que el
  contrato pide antes de retirar nada.
- **Autorización pendiente:** alcance ordinario, con la cautela de borrado.

---

## Arrastrado de la ronda `audit-2026-09-18`

### `AUD-004` (r18) — Historial del Programador de tareas deshabilitado

- **Estado:** **PERSISTENTE**. `pipeline_health.json` (2026-09-21) sigue
  reportando `scheduled_tasks.history_enabled = false`. La remediación de la
  ronda 18 añadió **detección**, no la habilitación.
- **Cambio mínimo:** `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`.
- **Archivos:** ninguno del repositorio. Es configuración del **host**.
- **Autorización pendiente:** **proceso elevado**, aunque la cuenta sea
  administradora. Fuera del alcance de una sesión ordinaria.
- **Consecuencia de dejarlo:** una tarea que no llegue a lanzarse sigue sin
  dejar rastro diagnosticable; sólo persisten `LastRunTime`/`LastTaskResult`.

---

## Pendiente de autorización, no ejecutado

**Residuo de la ronda anterior en `audit/latest/`.** `openai/REPORT.md`,
`openai/EVIDENCE.json` y `history/manifest-20260918T121551Z` pertenecen a
`audit-2026-09-18`, están preservados íntegros en `audit/audit-2026-09-18/` (11
ficheros, sha256 idénticos) y **no forman parte de esta ronda**. `CHANGES.md`,
`VALIDATION.md` y `STATUS.md` se han reescrito como entregables de esta ronda,
declarando que sus fases no se han ejecutado. Retirar los ficheros de `openai/`
y `history/` de `latest` sería una **eliminación** y requiere autorización
explícita: se registra como pendiente y no se ejecuta.
