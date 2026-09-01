# Hallazgos — Auditoría integral 2026-08-30

Severidades: CRÍTICO / ALTO / MEDIO / BAJO / INFORMATIVO.
Estados de evidencia según `.claude/skills/full-audit/references/taxonomy.md`.

Alcance: repositorio completo. Resultado de cobertura: **PARCIAL** (ver
`VALIDATION.md`).

## ALTO

### A-1 · `audit.md` rompe dos contratos del sistema de loops

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** regresión introducida
- **Componente:** `.claude/loops/audit.md`
- **Evidencia:** `pytest tests/ -q` → `3 failed, 1375 passed, 1 skipped`. Dos
  fallos son de este archivo:
  - `tests/test_claude_system_contract.py::test_general_loops_share_an_identical_guardrail_block`
  - `tests/test_claude_system_contract.py::test_all_general_loops_finish_through_verification_gate`
- **Comprobación independiente:** extracción programática del bloque
  `## Common guardrails` de los 11 archivos de `.claude/loops/*.md`: 10 comparten
  un bloque byte-idéntico de 5 viñetas; `audit.md` es la única desviación (4
  viñetas, dos de ellas propias) y el único sin `/verification-gate`.
- **Esperado vs observado:** el contrato exige bloque idéntico en todos los loops
  y cierre por `/verification-gate`. `audit.md` incumple ambos.
- **Causa raíz:** el archivo se creó el 2026-08-29 durante la reestructuración de
  la skill `full-audit` redactando guardarraíles a medida en vez de reutilizar el
  bloque canónico, y sin ejecutar la suite completa después.
- **Impacto:** suite en rojo. El contrato existe porque cada loop se carga solo y
  debe ser autocontenido; el riesgo que vigila no es la duplicación sino la
  deriva, que es exactamente lo que se introdujo.
- **Solución mínima:** restaurar el bloque canónico literal bajo
  `## Common guardrails`, mover las restricciones específicas de auditoría a una
  sección propia fuera de ese encabezado, y cerrar por `/verification-gate`.
- **Riesgo de regresión:** nulo sobre código de producción; el archivo es
  instruccional. Lo cubren los dos tests que hoy fallan.

## MEDIO

### M-1 · La auditoría del 2026-08-29 no dejó ningún artefacto persistido

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** trazabilidad
- **Componente:** `audit/latest/`, `.claude/skills/full-audit/references/taxonomy.md`
- **Evidencia:** el último commit que toca `audit/latest/` es `84e5c72`
  (2026-08-05) y `audit/latest/FINDINGS.md` se titulaba "Auditoría integral
  2026-08-04". Entre el 2026-08-28 y el 2026-08-29 hay commits que corrigen
  `AUD-HIGH-001`, `AUD-MED-002`, `AUD-LOW-001`, `AUD-LOW-002` y `AUD-LOW-003`.
- **Esperado vs observado:** seis correcciones referencian IDs de una auditoría
  cuyo informe no existe en el repositorio; los IDs no resuelven contra ningún
  documento.
- **Causa raíz:** hasta el 2026-08-29 la skill `full-audit` prohibía escribir
  cualquier archivo salvo un informe expresamente autorizado, y no definía
  destino; el estado de la auditoría vivía sólo en el contexto de la sesión.
- **Impacto:** no hay línea base ni registro revisable de la auditoría más
  reciente. `git log` documenta los arreglos, no la evidencia ni lo descartado.
- **Efecto secundario detectado:** coexisten dos esquemas de ID. Los artefactos
  persistidos usan `C-n/A-n/M-n/B-n/I-n`; la auditoría del 2026-08-29 usó
  `AUD-<NIVEL>-NNN`. `taxonomy.md` fija el primero por ser el de los artefactos,
  pero debe registrar la equivalencia para que los IDs históricos —que aparecen
  en mensajes de commit y en `known-issues.md`— sigan siendo resolubles.
- **Solución mínima:** la causa raíz ya está corregida (persistencia incremental
  obligatoria en la skill reestructurada, más este informe). Resta documentar la
  equivalencia de esquemas en `taxonomy.md`.

## BAJO

### B-1 · La revalidación del registro live no corre si no hay historial graduado

- **Estado:** `INFERIDO` · **Confianza:** BAJA · **Categoría:** robustez
- **Componente:** `src/sqp/calibration/data.py`, `src/sqp/calibration/calibrator.py:573`
- **Evidencia:** `revalidate_live_registry()` se invoca al final de
  `train_market_calibrators` (`calibrator.py:573`). La cadena diaria es
  `run_all.py:325` → `stage_calibrators_from_settled` → `train_market_calibrators`.
  Pero `stage_calibrators_from_settled` retorna `[]` **antes** de llamar a
  `train_market_calibrators` si `calibration_enabled` es falso o si
  `load_calibration_training_history()` viene vacío.
- **Condición de activación:** historial graduado vacío o ilegible mientras el
  registro live sigue sirviendo calibradores.
- **Por qué la confianza es BAJA:** no se ha observado. Con
  `calibration_enabled=false` los calibradores live no se aplican, así que esa
  rama es inocua; la rama de historial vacío exige cero apuestas liquidadas, algo
  que no ocurre en producción. No se ha construido un caso que lo active.
- **Decisión:** **no se corrige.** La necesidad no está sustentada por evidencia
  observada, sólo por lectura del flujo de control. Queda registrado para que una
  auditoría futura lo evalúe con datos, no para actuar sobre una hipótesis.

## INFORMATIVO

### I-1 · Fallo preexistente no atribuible a esta auditoría

`tests/test_claude_model_routing.py::test_main_model_matches_the_authorized_policy`
falla porque `.claude/settings.json` declara `claude-opus-5` mientras `HEAD`
declara `claude-fable-5`. Verificado con `git show HEAD:.claude/settings.json`:
la divergencia ya estaba en el árbol de trabajo al abrir la sesión del
2026-08-29, y no era deriva accidental sino un cambio deliberado aplicado a
medias: `settings.json` y `docs/MODEL-ROUTING.md` en Opus 5, la política y el
literal del test en Fable 5.

**CERRADO el 2026-08-30 por decisión del operador:** Opus 5 en las cuatro
puntas. Se alinearon `.claude/automation/MODEL_ROUTING.md` y los dos literales
de `tests/test_claude_model_routing.py`. La suite queda **completamente verde:
1378 passed, 0 fallos**. La jerarquía de capacidad no cambia —`claude-fable-5` >
`claude-opus-5` > `sonnet` > `haiku`— y sigue afirmada por su propio test: lo que
cambió es el punto de partida, no el techo.

Nota de proceso: el candado de tres puntas hizo exactamente lo que se diseñó para
hacer. Sostuvo la suite en rojo hasta que un humano decidió, en vez de dejar que
un cambio a medias pasara inadvertido. Ver `known-issues.md` KI-021.

### I-2 · `shadow_mode: false` es deliberado

`configs/default.yaml:167` tiene `shadow_mode: false`. No es deriva: el flag se
levantó el 2026-08-16 por decisión registrada (`src/sqp/audit/html_report.py:79`).
Se anota porque implica que el sistema dimensiona stakes reales, lo que eleva la
importancia de los gates de riesgo.

## Auditoría de los gates de riesgo (2026-08-31, alcance P-1)

Cierra el `PARCIAL` que dejó la auditoría del 2026-08-30 sobre `src/sqp/risk/`.
Lectura completa de los 5 módulos (708 líneas) más consumidores.

### R-A-1 · El colapso a unidades independientes no ve las dos caras de `spreads`

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** validez estadística del gate
- **Componente:** `src/sqp/risk/prediction_gate.py:84-115` (`_independent_units`)
- **Evidencia (reproducción controlada):** construidas dos filas complementarias
  del mismo evento y mercado (`p_b = 1-p_a`, `y_b = 1-y_a`), el estadístico `d`
  sale **idéntico** en ambos lados (+0,0425). El colapso funciona en `h2h` y
  `totals` (1 unidad) y **falla en `spreads` (2 unidades)**, porque cada lado
  lleva el hándicap opuesto como `line` (−3,5 / +3,5) y `line` es clave de
  agrupación; en `h2h` es nula en ambos lados y en `totals` es la misma (8,5).
- **Corroboración independiente sobre el registro vivo**
  (`data/bets/prediction_gate.json`, 2026-08-30): `mlb|spreads` n=228 es
  **exactamente 2×** `mlb|h2h` n=114 sobre la misma liga y ventana, mientras
  `mlb|totals` n=118 ≈ 114. Es el patrón que predice la reproducción.
- **Esperado vs observado:** el propio docstring fija el criterio —"el lado B
  duplica n sin aportar ni un bit"— y la corrección de 2026-08-27 lo implementó
  para la repetición diaria y para `h2h`/`totals`. `spreads` quedó fuera.
- **Impacto cuantificado:** con `n` duplicado el binomial se hunde. Con 160
  eventos reales y 88 aciertos, el test correcto **deniega** (p=0,1178) y el
  inflado **aprueba** (p=0,0415, alpha=0,05). Con 200 eventos: 0,0895 → 0,0255.
  Además `min_n=300` se alcanza con ~150 eventos independientes, la mitad del
  listón pre-registrado.
- **Exposición actual:** **ninguna.** El registro vivo tiene 39 mercados y **0
  permitidos**; todos caen en `muestra_insuficiente`. Pero `mlb|spreads` (n=228)
  es el más cercano al umbral y es precisamente un mercado de spreads.
- **Causa raíz:** la clave de agrupación `(event_id, market, line)` identifica la
  *apuesta*, no el *evento*. Para spreads las dos apuestas del mismo evento
  tienen líneas distintas y la misma información.
- **Solución mínima:** quitar `line` de las claves y agrupar por
  `(event_id, market)`. Es estrictamente más conservador —sólo puede reducir `n`
  y subir el p-valor, nunca abrir una puerta cerrada—, que es el mismo principio
  que el docstring ya invoca. Alternativa menos agresiva: usar `abs(line)`, que
  arregla spreads pero deja separadas las líneas alternativas del mismo evento,
  que tampoco son independientes.
- **Riesgo de regresión:** el cambio **altera un criterio pre-registrado**
  (`docs/research/2026-08-16-preregistro-regla-de-salida.md`). Endurece el gate,
  nunca lo afloja, pero exige decisión humana y enmienda del pre-registro, no un
  parche silencioso. Cubierto por `tests/test_prediction_gate.py`.

### R-B-1 · `max_drawdown` no siembra el pico con el balance de apertura

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** métrica de riesgo
- **Componente:** `src/sqp/risk/bankroll.py:97-106` (`_max_drawdown`)
- **Evidencia:** con banca inicial 1000 y tres pérdidas de 100, la curva es
  [900, 800, 700] y el método reporta **−200**; el drawdown real desde la
  apertura es **−300**. `peak` arranca en `-inf`, así que el primer punto de la
  curva —ya *después* de la primera apuesta— se convierte en el pico y esa
  primera pérdida nunca se contabiliza.
- **Impacto:** subestima el drawdown, que es la dirección insegura para una
  métrica de riesgo. No gobierna ningún gate: se consume en `summary()` y en
  `scripts/bankroll_status.py`, es informativa.
- **Solución mínima:** sembrar `peak` con `self.initial + self.adjustments_total()`
  (la base de la curva) en vez de `-inf`.
- **Riesgo de regresión:** bajo; cubierto por `tests/test_bankroll.py`.

### R-I-1 · El default de Kelly en la firma es 0,25 y producción usa 0,08

`kelly_fraction_stake(..., fraction: float = 0.25, ...)`
(`src/sqp/risk/kelly.py:16`). Los dos únicos llamadores
(`pipeline/daily.py:863`, `backtesting/roi_engine.py:250`) pasan
`risk.kelly_fraction` explícito desde configuración, así que **hoy no hay ruta
de fallo**. Se anota porque un llamador nuevo que omitiera el argumento
dimensionaría al triple de la fracción de producción sin que nada lo señalara.
No se eleva de INFORMATIVO: no hay ruta causal demostrable.

### R-I-2 · `summary()` relee todos los `settled_*.csv` cuatro veces

`summary()` invoca `_settled()`, `realized_pnl()`, `current_balance()` y
`_max_drawdown()`, y cada uno vuelve a leer los CSV desde disco
(`src/sqp/risk/bankroll.py:108-125`). Es una ruta de CLI y reporte, no del run
diario; se registra como deuda, no como defecto de rendimiento demostrable.

## Reanudación 2026-08-31 (fase 2): settlement, persistencia y dependencias

Continúa la misma auditoría; no se re-auditó ninguna área ya `REVISADA`.

### R-I-3 · El lock entre procesos no guarda pid ni refresca `mtime`

`src/sqp/storage/lock.py`. Un `.lock` se declara huérfano por antigüedad
(`LOCK_STALE_S`=300 s) usando el `mtime` de creación, que nunca se refresca, y
el archivo no lleva pid. Una sección crítica que superara los 300 s vería su
lock roto por otro proceso, y al salir el primero borraría el `.lock` del
segundo.

**No se eleva por encima de INFORMATIVO: no hay ruta demostrable.** Se
inspeccionaron las seis secciones bloqueadas
(`closing_capture.py:82`, `daily.py:314,409`, `revalidation.py:169,277`,
`odds_store.py:59`) y todas son read-modify-write de CSV local o escritura de un
contador —sin red ni trabajo largo—, órdenes de magnitud por debajo del umbral.
Se registra para que una futura sección crítica que sí pueda tardar (p. ej. si
alguien metiera una llamada de red dentro del `with`) reabra la evaluación.

## Descartados con evidencia

| Sospecha | Por qué se descartó |
|---|---|
| `revalidate_live_registry()` sería código muerto: no aparecía en ningún llamador de producción. | Falso positivo de mi propia búsqueda, que excluía el módulo que la define. `grep` sobre el repo completo la encuentra en `calibrator.py:573`, dentro de `train_market_calibrators`, alcanzable desde el run diario (`run_all.py:325`). |
| El guard de `price_decimal <= 1.0` seguiría pendiente, según `KI-019`. | Resuelto. `is_usable_price` (`src/sqp/markets/odds.py:7`) rechaza `None`, NaN, ±inf y todo precio ≤ 1.0, y lo consumen `edge.py:65`, `odds.py:31,38` y `probabilities.py:35,62`. |
| Secretos versionados. | Barrido sobre archivos trackeados sin coincidencias; sólo `.env.example` está en git. |
| Peticiones HTTP sin timeout. | Cero `requests.get/post` sin `timeout` en `src` y `scripts`. |
| Incoherencia manifiesto/lock. | `pip check` → "No broken requirements found." |
| El gate usaría comparación lexicográfica de fechas y dejaría pasar filas del día del pre-registro. | Descartado. `game_date` se construye siempre como `str(start_time)[:10]` (`pipeline/daily.py:218,876`; `settlement/backfill_teams.py:22`), es decir `YYYY-MM-DD` de 10 caracteres fijos, donde el orden lexicográfico coincide con el cronológico. |
| El gate no corregiría por comparaciones múltiples (~39 cortes a alpha 0,05). | Descartado como defecto: está **pre-registrado** con su razonamiento en `docs/research/2026-08-16-preregistro-regla-de-salida.md:115-119` — ~25 cortes, ~1,25 falsos positivos esperados, aceptados porque la condición EV>0 es un filtro independiente, con ruta de endurecimiento a Bonferroni si entran varios cortes con EV marginal. Es una decisión registrada, no un descuido. |
| `degradation.py` heredaría la duplicación 2,19x del stream servido al contar `n = len(g)`. | Descartado por medición: sobre `data/bets/settled_*.csv`, 1.054 filas graduadas dan 1.049 unidades únicas por `(event_id, market, selection, line)` — factor **1,00x**. El settlement deduplica; la duplicación vive en el stream servido, que es lo que consume el prediction gate y por eso `_independent_units` existe. |
| `kelly_fraction_stake` abriría el guard de precio a NaN/inf al open-codear `price_decimal <= 1.0` en vez de usar `is_usable_price`. | Descartado por ejecución: NaN, +inf, NaN en probabilidad y precio 1.0 devuelven todos `stake=0.0` sin excepción. El `max(0.0, ...)` final absorbe el NaN. Queda como duplicación del predicado, no como defecto. |
| El grading fabricaría resultados cuando la selección no casa con `home` ni con `away` (fallthrough del guard de `settle.py:43-46`, que exige `away` presente). | Descartado por medición: de **845** filas h2h/spreads liquidadas, **0** tienen `away` ausente o vacío. El guard es alcanzable sólo si el backfill de equipos dejara huecos, y hoy no los hay. |
| `three_way` podría no fijarse por liga, gradando los empates de fútbol como `push` en vez de `loss`. | Descartado: se deriva de `family == "soccer"` en los dos únicos consumidores — `pipeline/daily.py:62` y `backtesting/roi_engine.py:235,269` — sin ruta que los desincronice. |
| Vulnerabilidades conocidas en dependencias (quedó `NO_EJECUTADA` el 2026-08-30 por no estar `pip-audit` instalado). | Ejecutado el 2026-08-31 con `pip-audit 2.10.1`: `python -m pip_audit -s osv -r requirements.lock` → **"No known vulnerabilities found"**. |
| Deriva de calidad estática. | `ruff check src scripts tests` → "All checks passed!"; `mypy src` → "no issues found in 98 source files". |

---

# Iteración 3 (2026-08-31): cierre de la cobertura `PARCIAL`

Alcance: las ~2.700 líneas que la iteración 2 dejó sin lectura línea a línea
(`pipeline/daily.py`, `probabilities.py`, `budget.py`, `settlement/runner.py`,
`backfill_teams.py`, `pipeline/revalidation.py`, el resto de `storage/`,
`closing_capture.py`, `intraday_scan.py`, `cleanup.py`) más los 8 `.bat`
operacionales, que seguían `NO_EJECUTADA`.

Método: tres especialistas de solo lectura en paralelo (fase 1) y **revalidación
propia de todos los hallazgos ALTOS por segundo método** (fase 2). Ningún
hallazgo de especialista se acepta sin comprobación directa. Dos afirmaciones
suyas fueron corregidas a la baja; quedan registradas abajo.

## Nota sobre el estado del árbol

`.claude/skills/full-audit/references/` está **borrado en el árbol de trabajo**
(4 archivos, sin commitear). Siete referencias vivas apuntan a esos archivos:
`FINDINGS.md:4,42`, `VALIDATION.md:25` y `CHANGES.md:25,81,86,90`. El borrado es
un cambio preexistente del usuario y **no se revierte**; se registra como N-M-8.

## ALTO

### N-A-1 · La poda de ligas fuera de temporada borra ficheros sin liquidar cuando ningún pick tiene stake — que es el 100% del estado actual

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** pérdida de datos irrecuperable
- **Componente:** `src/sqp/pipeline/cleanup.py:44-54`, `:57-71`, `:89-96`
- **Evidencia:** `_all_actionable_settled` devuelve `True` sin comprobar nada
  cuando `_actionable(cands)` está vacío (`cleanup.py:62-63`,
  `# nothing stakeable -> nothing to lose by pruning`), y `_actionable` exige
  `stake > 0` (`:54`).
- **Comprobación independiente (mía):** la premisa de `_actionable` es falsa.
  Su docstring afirma que las filas con stake son *"the only ones that get
  settled"*, pero `settle_candidates` (`src/sqp/settlement/settle.py:86-95`)
  itera **todas** las filas del candidato sin filtrar por stake: una fila con
  `stake=0` obtiene `pnl=0.0` pero **se persiste igual** en `settled_*.csv`.
  Liquidable ≠ apostable.
- **Condición de activación:** hoy, siempre. `data/bets/prediction_gate.json`
  tiene 39 combinaciones (liga|mercado) y **0 permitidas**, así que `daily.py`
  pone `stake=0` en todas las filas y `_actionable` está vacío para **todas** las
  ligas. Cualquier liga que salga del conjunto activo se poda incondicionalmente.
- **Esperado vs observado:** el docstring del módulo (`:4-13`) promete que se
  poda sólo cuando *"every actionable pick in it is already graded"*. Observado:
  se poda sin verificar liquidación alguna.
- **Impacto:** borrado irrecuperable de `candidates_<liga>.csv` y
  `predictions_<liga>.csv` en el primer run tras salir de temporada. **No hay
  respaldo**: `_archive_existing` (`daily.py:358-385`) sólo copia *antes de
  sobrescribir*, y una liga fuera de temporada ya no se sobrescribe nunca. Se
  pierden `adjusted_edge`, `edge_penalty`, `kelly_stake_pct`, `flags`,
  `bookmaker` y toda fila aún sin graduar. Mitigación parcial: el stream
  `served_*`/`graded_*` conserva la probabilidad servida, por eso no es CRÍTICO.
  En un sistema cuyo cuello de botella declarado es la n graduada (`min_n=300`,
  no alcanzado en ningún mercado), destruir evidencia graduable es caro.
- **Solución mínima:** que `_all_actionable_settled` verifique contra el mismo
  conjunto que liquida `settle_candidates` (todas las filas), no contra
  `_actionable`; y archivar antes de cada `unlink()` (`:92`, `:95`).
- **Riesgo de regresión:** las ligas fuera de temporada con muchas filas no
  graduables dejarían de podarse y reaparecerían en el reporte consolidado.
  Cubierto por `tests/test_cleanup.py` (hoy 51 passed en el conjunto dirigido).

### N-A-2 · Una sola línea corrupta inutiliza el stream servido de una liga de forma permanente y silenciosa

- **Estado:** `REPRODUCIDO` (por el especialista) + `VERIFICADO_ESTATICAMENTE` (por mí) · **Confianza:** ALTA · **Categoría:** integridad de persistencia
- **Componente:** `src/sqp/storage/served_store.py:99-112`, `:114-139`, `:141-160`
- **Evidencia:** `_load` captura `ParserError` y devuelve un DataFrame vacío
  (`:106-112`). Tres consecuencias encadenadas, verificadas en el código:
  1. `append_served:122-123` recibe `prior` vacío → el dedup se salta entero.
  2. `append_served:132` comprueba `_header(p) != COLUMNS`; la cabecera sigue
     intacta (la corrupción está en una línea posterior), así que toma la rama
     de append barato de `:138` y **sigue escribiendo detrás de la línea
     corrupta**, perpetuándola y añadiendo duplicados.
  3. `pending():147-149` devuelve vacío → esa liga **no vuelve a graduar jamás**.
- **Esperado vs observado:** el comentario dice `degraded until repaired`, que
  sugiere un estado transitorio. Nada repara, nada pone en cuarentena y el único
  aviso es un `log.warning`. El monitor de salud usa el mismo `_load`, así que
  también ve el fichero vacío y tampoco lo detecta.
- **Contraste interno:** el proyecto tomó la decisión **opuesta y correcta** para
  el mismo modo de fallo en `settlement/runner.py:235-238`, donde el
  `ParserError` se propaga a propósito para no destruir el histórico.
- **Impacto:** desaparición silenciosa de una liga de `load_all_graded()`, del
  prediction gate y del entrenamiento del calibrador. Volumen expuesto: 23
  `served_*.csv`, 21 `graded_*.csv`.
- **Solución mínima:** en `_load`, mover el fichero corrupto a
  `<nombre>.corrupt.<ts>` y elevar a `log.error` con contador visible en el
  informe de salud. Propagar sería más consistente pero rompe la liquidación de
  la liga en vez de degradarla; la cuarentena es la variante de menor riesgo.

### N-A-3 · Una respuesta vacía del proveedor de scores se interpreta como «todos cancelados» y anula en masa, de forma irreversible

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** respuestas parciales del proveedor / pérdida de evidencia
- **Componente:** `src/sqp/settlement/runner.py:389-406`; finalidad en `:24`, `:239-242`
- **Evidencia (verificada por mí):** `raw = client.fetch_scores(...)` seguido de
  `scores = _scores_map(raw)` **sin ninguna comprobación de contenido**
  (`runner.py:389-390`). A continuación, `_void_stale_served(league)` (`:400`) y
  `_with_stale_voids(...)` (`:405`) se ejecutan igual, y el primero **ni siquiera
  mira `scores`**.
- **Condición de activación:** dos vías independientes. (a) `fetch_scores`
  devuelve 200 con lista vacía (clave de deporte fuera de temporada, glitch del
  proveedor); (b) el esquema del proveedor cambia y el guard por-entrada de
  `_scores_map` (`:30-43`, M-10) descarta todas las entradas. En ambos casos **no
  hay excepción**, así que `settle_all.py` no marca la liga como fallida.
- **La anulación es final:** `DEDUP_KEY` (`:24`) no incluye `result`, así que la
  fila graduada que llegue mañana comparte clave con el `void` ya persistido y
  `_persist_settled:239-242` la descarta. Re-ejecutar no repara.
- **Esperado vs observado:** `stale_void` debe significar *"el partido lleva >3
  días comenzado y el proveedor confirma que no hay resultado"* (política
  2026-07-12, `settle.py:14-19`). Observado: significa *"el proveedor no me
  devolvió resultado"*, sea porque no existe o porque la llamada volvió vacía.
- **Impacto:** un único día con respuesta vacía puede anular permanentemente
  todos los picks y filas servidas de 3 a 7 días de antigüedad de esa liga, con
  `pnl 0`, contaminando a la baja la muestra de calibración sin traza
  distinguible de un aplazamiento genuino. Es el modo de fallo más costoso
  encontrado en esta iteración: silencioso, masivo y no revertible.
- **Solución mínima:** guardar la anulación tras una prueba de salud del payload
   — si `raw` está vacío, o si `raw` trae entradas pero `_scores_map` no produjo
  ninguna, saltar `_with_stale_voids` y `_void_stale_served` para esa liga y
  registrar `log.error`. La graduación normal puede seguir intacta.
- **Riesgo de regresión:** bajo. Posponer la anulación un día en el caso
  degenerado; basta un día sano para que la política de expiración siga
  funcionando, así que no reabre el bloqueo indefinido que 2026-07-12 cerró.

### N-A-4 · El cap global de exposición sólo cuenta los picks generados HOY, mientras las vistas los cuentan por VIGENCIA

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** control de riesgo no efectivo · **LATENTE hoy**
- **Componente:** `src/sqp/pipeline/daily.py:296-355`, filtro en `:325-332`
- **Evidencia (verificada por mí):** el docstring de `apply_global_exposure_cap`
  (`:298-303`) declara que limita *"the WHOLE day's staked exposure across every
  league"* y que *"this is the only place the cross-league limit is enforced"*.
  El filtro de `:325-332` restringe `eligible` a `days == generated_day`.
- **Comprobación independiente:** el contrato está **codificado en un test**,
  `tests/test_daily_exposure.py:120-129`: dos ligas con 90 y 60 de stake, cap de
  100 (banca 1000 × `max_total_exposure_pct: 0.10`), y la aserción es
  `factor == 1.0` con los 90 de ayer intactos. Es decir, 150 sobre un cap de 100,
  por diseño y con test que lo fija.
- **Y esos picks antiguos sí son accionables:** `evaluation/labels.py:65-90`
  (`picks_vigentes`) filtra por *"partido no se ha jugado todavía"*, no por día
  de generación, y su propio docstring registra la magnitud medida: *«Todos los
  Picks» mostraba 82 filas de UNA liga mientras quedaban 577 filas de 13 ligas
  con el partido por jugar*. Coincide con la memoria del proyecto
  (`vistas-filtran-por-vigencia-2026-08-28`).
- **Condición de activación:** cualquier día en que una liga con picks staked no
  se regenere: aplazada por el guardián de presupuesto, caída por excepción
  (`run_all.py:191-196`) u omitida por el guard M2 (`run_all.py:144-154`).
- **Impacto:** el único límite de banca a nivel cartera puede excederse por un
  múltiplo igual al número de días de arrastre × ligas no refrescadas.
- **Por qué es LATENTE y no activo:** con 0 de 39 mercados permitidos por el
  prediction gate, todos los stakes son 0 y `total` es 0 en ambos caps. Se activa
  el día en que el gate habilite el primer mercado.
- **Causa raíz:** dos definiciones de «el día» conviviendo. El scoping por
  `generated_at` se introdujo para no re-escalar una liga aplazada (comentario en
  `:328-331`), lo que resuelve N-B-3 pero abre este hueco. Son objetivos
  incompatibles con esta implementación.
- **Riesgo de regresión: ALTO — requiere decisión del operador, no es un parche
  mecánico.** Cambiar el denominador a vigencia reduce stakes de picks nuevos
  cuando hay arrastre y modificaría ficheros de días anteriores, hoy intocables.
  Además **invalida un test que fija el contrato actual**. Mismo perfil que
  `R-A-1`: endurece un criterio existente y exige aprobación explícita.
- **Alternativa de coste cero:** dejar la semántica como está y **loguear** la
  exposición viva total frente al cap, para que el hueco sea al menos visible.

### N-A-5 · El stream graduado duplica 2,31x y la normalización no vive en el punto de lectura compartido

- **Estado:** `REPRODUCIDO` (medición propia) · **Confianza:** ALTA · **Categoría:** validez inferencial
- **Componente:** `src/sqp/storage/served_store.py:38-41` (origen), `:83-97` (`load_all_graded`), `:141-160`
- **Medición propia (comando y salida reales):**
  ```
  files 21 rows 16702 unique 7243 ratio 2.306
  top ratios: bundesliga 5.83 · ligue1 5.63 · epl 5.41 · ligamx 5.37 ·
              brasileirao 5.35 · mls 5.29 · laliga 5.25 · chile 5.11
  ```
  (dedup por `(event_id, market, selection, line)`, por fichero.)
- **Origen, por diseño:** `KEY_COLS` incluye `generated_at` truncado a día
  (`:38-41`), y con `event_horizon_days = 7` (`config.py:232`) el mismo lado de
  mercado se sirve una vez al día durante hasta 7 días. Verificado sobre
  `graded_mls.csv`: 3.103 filas, 69 eventos distintos, 587 unidades por
  `(event,market,selection,line)` — ~5 días de servicio por lado.
- **Esperado vs observado:** `load_all_graded` se documenta a sí mismo
  (`:87-89`) como el punto único *"para que las tres consumidoras no puedan
  divergir"*. Observado: la mitigación (colapso a unidades independientes) vive
  en `risk/prediction_gate.py:84-115` (`_independent_units`), **no** en
  `load_all_graded`. `scripts/model_vs_market_report.py:184-190`,
  `audit/reproductions/model_review_by_sport.py:143` y
  `prediction_vs_reality.py:62` consumen las filas crudas. La divergencia que el
  docstring dice impedir ya existe.
- **Impacto:** todo intervalo de confianza, test de signo o error estándar
  calculado sobre `load_all_graded()` sin colapsar está inflado por ~2,3x en n
  (hasta 5,8x en bundesliga). **El prediction gate está protegido** por
  `_independent_units`; los informes modelo-vs-mercado y las reproducciones de
  auditoría, no.
- **¿Filas irrecuperables?** No. La duplicación es determinista y reversible;
  `generated_at` conserva qué día se sirvió cada una. Lo irrecuperable del stream
  servido es otra cosa (las 152 filas expiradas sin graduar que cuenta
  `health.py`), ajena a este defecto.
- **Solución mínima:** exponer `load_all_graded_units()` en `ServedStore` con la
  misma normalización que `_independent_units`, que `prediction_gate` la consuma
  en vez de reimplementarla, y documentar que `load_all_graded` devuelve crudo.
- **Riesgo de regresión:** los números históricos de los informes bajan en n y
  suben en p-valor. Dirección conservadora; nunca abre una puerta cerrada.

## Correcciones que introduje sobre los especialistas (fase 2)

Se registran porque cambian la conclusión, no por completitud procedimental.

| Afirmación del especialista | Mi comprobación | Resolución |
|---|---|---|
| La duplicación del stream graduado es **3,84x** (4.352 unidades sobre 16.702 filas), hasta 9,57x en ligue1. | Medición propia con la clave declarada `(event_id, market, selection, line)`: **7.243 unidades, ratio 2,306**, máximo 5,83x. Sobre `mls` probé las tres claves plausibles (587 / 483 / 3.103) y **ninguna reproduce su 380**. El total de filas sí coincide exactamente (16.702). | **Magnitud NO reproducida.** Se registra 2,31x, que además es coherente con la medición del 2026-08-27 (2,19x). El defecto existe; su cifra no. |
| `FS-01` (el hash de fuente del feature store ignora `starters_mlb.csv`) es **ALTO**. | `grep` sobre todos los consumidores de `build_training_dataset`: sólo `scripts/train_models.py`, `scripts/build_features.py` y `evaluation/compare.py`. Los tres viven en la rama ML, que `REFRESH_ML.bat` declara **manual desde 2026-08-29** y cuya inferencia no tiene llamador en producción (`ml_predict.py:4`, AUD-LOW-003). | **Rebajado a MEDIO** (N-M-1). El defecto es real y el mecanismo está bien descrito, pero no toca ningún pick servido: corrompe la evidencia con la que se decidiría conectar el ML. |

## MEDIO

| ID | Hallazgo | Componente | Estado |
|---|---|---|---|
| N-M-1 | El hash de fuente del feature store cubre `ResultsStore` pero no `StartersStore`, del que `_mlb_results_df` también depende: cambiar los abridores no invalida la caché del dataset MLB. Cierra a medias la corrección D-10. | `storage/feature_store.py:58-68`, `:71-79`, `:126-128` | `VERIFICADO_ESTATICAMENTE` |
| N-M-2 | `_novig_probs` de-vig-ea sobre más desenlaces de los que el mercado admite: el guard es `len(keys) < required`, sin control por exceso. Con 4 claves en un 2-way, `fair` sale 0,25 en vez de 0,50, en silencio. Misma clase que QNT-08, ya cerrada en la dimensión `point` pero no en `outcome`. | `pipeline/probabilities.py:104-119` | `REPRODUCIDO` |
| N-M-3 | `_pick_main_lines` es el único lector de `eo.lines` que no aplica `is_usable_price`: la línea principal puede fijarse sobre cotizaciones que el resto del pipeline descarta, y entonces el mercado desaparece del pick list sin aviso **y** se publica `spread_line`/`total_line` que nadie cotiza. | `pipeline/probabilities.py:140-151` | `REPRODUCIDO` |
| N-M-4 | Con cuota ilegible (`remaining is None`), `--max-leagues N` deja de ser techo y pasa a ser objetivo: se ignora `fallback_leagues` y el aviso del llamador está suprimido justo en esa rama. 19 ligas ≈133 créditos sin racionar ni avisar. | `pipeline/budget.py:55-57`, `scripts/run_all.py:85` | `REPRODUCIDO` |
| N-M-5 | El clamp `max(0.01, min(0.99, ...))` convierte cualquier NaN en 0,99, y el guard previo sólo comprueba `is None`. La fila envenenada se persiste como `adjusted_probability`, que es la columna sobre la que se reentrena el calibrador. Vía de activación **no establecida**. | `pipeline/daily.py:780`, `:805` | `REPRODUCIDO` (el clamp) / `INFERIDO` (la vía) |
| N-M-6 | `unsettled_completed_picks` valida `stake` y `start_time` pero no `event_id`, y luego hace `merge(on="event_id")`. El `KeyError` no está capturado: `run_all.py:147` corre **antes** del bucle de ligas y fuera de todo `try` — a diferencia del monitor de degradación justo debajo (`:167-184`), que sí lo está. Un fichero defectuoso impide generar picks de **todas** las ligas ese día. | `pipeline/cleanup.py:135`, `:142`; `scripts/run_all.py:147` | `REPRODUCIDO` |
| N-M-7 | El fallback histórico de tenis usa el matcher **ordenado**, pero el histórico de tenis normaliza `home = ganador`. Medido sobre datos reales: de 36 filas de tenis anuladas, **6 tenían su resultado descargado**, sólo alcanzable con la clave invertida. | `settlement/runner.py:352` → `:168` → `:113-141` | `REPRODUCIDO` |
| N-M-8 | `.claude/skills/full-audit/references/` está borrado en el árbol y 7 referencias vivas lo citan (`FINDINGS.md:4,42`, `VALIDATION.md:25`, `CHANGES.md:25,81,86,90`). Cambio preexistente del usuario: **no se revierte**. | artefactos de auditoría | `VERIFICADO_ESTATICAMENTE` |
| N-M-9 | El «edge re-validado» congela el `market_shrink`, así que no es «el edge con el que hoy se generaría el pick»: con `s=0,5` reacciona ~1,9x más rápido al movimiento de precio que una regeneración real, pero se compara contra el mismo `min_edge`. Sesga la comparación CLV revocados-vs-mantenidos que el pase existe para producir. | `pipeline/revalidation.py:140-151`, `:213`, `:218` | `VERIFICADO_ESTATICAMENTE` |
| N-M-10 | El rastro de la re-validación se escribe una sola vez al final y fuera del lock, mientras las revocaciones se persisten por liga dentro del bucle. Una excepción a mitad deja revocaciones en disco **sin ninguna fila de log**, y el llamador la degrada a warning. | `pipeline/revalidation.py:169-242`; `scripts/capture_closing_odds.py:54-55` | `VERIFICADO_ESTATICAMENTE` |
| N-M-11 | La re-validación puede «aprobar por vacío»: cuatro salidas silenciosas sin contador hacen que un pase inerte sea indistinguible de uno limpio. Sólo baja stakes, así que no crea riesgo: falla en evitarlo. | `pipeline/revalidation.py:174-200` | `VERIFICADO_ESTATICAMENTE` |
| N-M-12 | `_league_odds` concatena **todo** el histórico de cuotas de la liga (673 MB en 58 ficheros; MLB solo 228 MB) en cada pase horario, y en `revalidation` lo hace **dentro del lock** que el run diario necesita. Si supera `LOCK_TIMEOUT_S=30`, el run diario degrada a escritura sin lock. | `pipeline/revalidation.py:117-121`, `:169-181`; `pipeline/intraday_scan.py:103` | `INFERIDO` (no se cronometró) |
| N-M-13 | `intraday_scan` filtra por *día UTC de generación igual al día actual*, así que los eventos de las primeras horas UTC nunca se escanean. Sesgo horario estructural en el dataset (6.849 filas) que existe para decidir una fase del sistema. | `pipeline/intraday_scan.py:84`, `:98-101` | `VERIFICADO_ESTATICAMENTE` |
| N-M-14 | `closing_capture`: el guard `min_remaining` es inerte para la primera liga de cada pase (`requests_remaining` arranca en `None` y el proceso se crea de cero cada hora) — hasta 24 fetches/día sin guard. | `pipeline/closing_capture.py:119-133` | `VERIFICADO_ESTATICAMENTE` |
| N-M-15 | La contabilidad de créditos depende por completo del header `x-requests-last`; si falta, `delta = 0`, no se llama a `add_spent` y el tope `max_credits` nunca se activa aunque se hayan hecho N llamadas reales. | `pipeline/closing_capture.py:137-142` | `VERIFICADO_ESTATICAMENTE` |
| N-M-16 | `closing_capture` no comprueba `last_response_cached` antes de persistir, a diferencia del guard canónico de `daily.py:671`. Con el cliente por defecto (`force_refresh=True`) no se manifiesta; con un cliente inyectado sellaría `captured_at = now` sobre un payload de hasta 6 h. Frescura fabricada. | `pipeline/closing_capture.py:136-150` | `VERIFICADO_ESTATICAMENTE` |
| N-M-17 | El store de cuotas no persiste el timestamp del proveedor: `captured_at` es la hora de *nuestro* fetch, no la de la cotización. `_fresh_snapshot` mide la frescura de la captura, no la del precio. | `storage/odds_store.py:26-27`, `:42-48` | `VERIFICADO_ESTATICAMENTE` (que el proveedor emita `last_update` es `INFERIDO`) |
| N-M-18 | `append_snapshot` no deduplica: reinsertar el mismo snapshot duplica filas y re-pondera la mediana del consenso. Toda la protección vive en los llamadores, y `closing_capture.py:150` no tiene ninguna. | `storage/odds_store.py:49-73` | `REPRODUCIDO` |
| N-M-19 | `log_pitcher_confirmation` registra un cambio de abridor **falso en cada ejecución** cuando sólo hay un lanzador nombrado: el ausente vuelve del CSV como `NaN` (`"nan"`) y entra como `None` (`"None"`). El control con ambos nombrados sí deduplica. | `storage/starters.py:76-79` | `REPRODUCIDO` |
| N-M-20 | `StartersStore.save` sigue destruyendo un abridor almacenado cuando la fila nueva trae sólo uno: el guard descarta filas con **ambos** ausentes, y `drop_duplicates(keep="last")` borra el otro. Es la variante parcial de la degradación que D-01 dice cerrar. | `storage/starters.py:119-133` | `REPRODUCIDO` |
| N-M-21 | `StarterFIPStore.save` no tiene guard de informatividad alguno: una fila sin FIP borra los FIP reales y los nombres. La corrección D-01 nunca se replicó aquí, y `reindex` rellena con `NaN` en silencio donde el hermano lanzaría `KeyError`. | `storage/starter_fip.py:24-43` | `REPRODUCIDO` |
| N-M-22 | El guard de duplicados de `ResultsStore` es unidireccional: contempla la fila legacy almacenada, no la entrante. Un `game_id` vacío que llega después de uno real crea un partido duplicado en el histórico que alimenta Elo y el feature store. `BACKFILL_ALL` solapa 14 días con cadencia semanal. | `storage/results_store.py:63-69` | `REPRODUCIDO` |
| N-M-23 | Una `candidates_*.csv` sin columna `stake` se poda como si no tuviera nada que perder, contra el docstring que promete devolver `False` cuando el estado no es verificable. | `pipeline/cleanup.py:47-48`, `:62-63` | `REPRODUCIDO` |
| N-M-24 | `purge_old_artifacts` no tiene dry-run ni registra los nombres borrados (sólo el conteo por familia), y corre semanalmente sin comprobación de errorlevel. | `pipeline/cleanup.py:174-217`; `scripts/purge_artifacts.py` | `VERIFICADO_ESTATICAMENTE` |
| N-M-25 | La ruta rápida de `append_served` no es atómica ni está bajo lock, a diferencia de sus pares (`odds_store.py:59`, `append_graded`). Es el mecanismo que produce N-A-2. | `storage/served_store.py:138` | `VERIFICADO_ESTATICAMENTE` |
| N-M-26 | El feature store devuelve tipos distintos según haya caché o no: la rama de reutilización hace `read_csv` sin `parse_dates`, así que `date` vuelve como cadena donde la rama de construcción da datetime. | `storage/feature_store.py:137-139` vs `:159-172` | `VERIFICADO_ESTATICAMENTE` |

## BAJO e INFORMATIVO

| ID | Hallazgo | Componente |
|---|---|---|
| N-B-1 | Los dos caps de exposición pueden dejar el total por encima del cap tras redondear a 2 decimales (medido: 100,20 sobre 100,00 con 60 candidatos). Cota: `n × 0,005`. | `pipeline/daily.py:290`, `:344` |
| N-B-2 | `_ref_date = eo.event.start_time[:10]` es el único uso sin `str()` en `run_league`; sus tres hermanos (`:193`, `:210`, `:876`) sí son defensivos. Un `commence_time` nulo tumba la liga entera. | `pipeline/daily.py:739` |
| N-B-3 | `apply_global_exposure_cap` no es idempotente: un segundo run el mismo día vuelve a escalar las ligas no regeneradas (`kelly × f1 × f2`). Dirección conservadora. Interactúa con N-A-4. | `pipeline/daily.py:317-354` |
| N-B-4 | `_attach_probable_pitchers` envuelve el bucle de fechas completo en un `try` cuyo `except` hace `return`, no `break`: el fallo de UNA fecha descarta los abridores de TODAS y deja MLB sin candidatos. | `pipeline/daily.py:199-205` |
| N-B-5 | `_archive_existing` mezcla hora local naive y UTC en la clave de archivo; cerca de medianoche dos ficheros del mismo run pueden archivarse con días distintos. | `pipeline/daily.py:379` |
| N-B-6 | Se carga todo el histórico de cuotas y se calcula el movimiento de línea por selección aunque `line_movement_penalty` y `line_velocity_penalty` estén ambos a 0: trabajo íntegramente muerto en la configuración actual. | `pipeline/daily.py:692`, `:846-847` |
| N-B-7 | `history_scores_map`: un `game_date` vacío vuelve del CSV como `NaN`, y `str(NaN)` es `"nan"` (truthy), así que el `or` nunca cae al respaldo `start_time`. Medido: 19.162 filas servidas, **0 afectadas hoy**. Latente. | `settlement/runner.py:135` |
| N-B-8 | `backfill_settled_file` decide sólo por `home`: filas con `home` lleno y `game_date` vacío no se rellenan ni se cuentan como no resueltas, y `prediction_gate` aplica default-deny si falta `game_date`. Medido: 1.070 filas, 0 afectadas. Latente. | `settlement/backfill_teams.py:37-45` |
| N-B-9 | `teams_from_odds` no tiene guard: con `usecols` como callable, una columna ausente emerge como `AttributeError` y aborta el backfill de todas las ligas. | `settlement/backfill_teams.py:15-22` |
| N-B-10 | `backfill_settled_file` reescribe `settled_*.csv` completo sin lock ni coordinación con `_persist_settled`: *lost update* si corre junto a `SETTLE_ALL`. | `settlement/backfill_teams.py:29`, `:46-50` |
| N-B-11 | Si un `settled_*.csv` legado no tiene las cinco columnas de `DEDUP_KEY`, el dedup se salta entero y cada corrida duplica filas, contra el docstring que se anuncia idempotente. Medido: 1.070 filas, 0 duplicados, 0 ficheros afectados. Latente. | `settlement/runner.py:239` |
| N-B-12 | Las tres escrituras de `revalidation.py` usan `tmp + replace` sin `fsync`, mientras `atomic.py` documenta que el `fsync` se añadió a propósito (COR-07). `revalidation_log.csv` es acumulativo y no reconstruible. | `pipeline/revalidation.py:73-75`, `:238-240`, `:370-372` |
| N-B-13 | El criterio de retención documentado no aplica a la familia `archive`: el regex es `(20\d{6})` pero `_archive_existing` nombra los ficheros con guiones (`_2026-07-12.csv`). 918 de 919 caen al fallback de mtime, que `apply_global_exposure_cap` reescribe a diario. Retención efectiva más larga (dirección segura) pero indeterminada. | `pipeline/cleanup.py:163-171`; `pipeline/daily.py:383` |
| N-B-14 | La familia `clv_reports` es un glob desnudo (`clv_*.md`) sin exigir fecha en el nombre. Hoy 0 ficheros afectados; latente para cualquier registro vivo futuro con ese prefijo. | `pipeline/cleanup.py:193` |
| N-B-15 | Fan-out del merge en `unsettled_completed_picks` infla el conteo de picks en riesgo (dirección conservadora, pero informa un número falso al operador). | `pipeline/cleanup.py:142` |
| N-B-16 | `intraday_edge_log.csv` se reescribe entero en cada pase (crecimiento O(n²) acumulado) y no está en ninguna allowlist de purga. Hoy 1,01 MB / 6.849 filas. Falta política, no borrado. | `pipeline/intraday_scan.py:153` |
| N-B-17 | `except Exception` por liga en `closing_capture` traga también errores de programación, y el `summary` no tiene campo de errores: una liga puede dejar de capturar cierres durante semanas sin alarma. | `pipeline/closing_capture.py:155-156` |
| N-B-18 | `ResultsStore.load` acepta cualquier subconjunto de columnas vía `usecols` callable y luego indexa duro `df[self._LOAD_COLS]`: un fichero sin `neutral` rompe toda lectura, incluida la del feature store. | `storage/results_store.py:31-34` |
| N-B-19 | El `added` de `ResultsStore.upsert` puede salir negativo y el upsert elimina duplicados preexistentes sin log, contra la prohibición de mutación oculta de `data-integrity-rules.md`. | `storage/results_store.py:69-70` |
| N-B-20 | `StartersStore` lee sin `try/except` (`EmptyDataError`/`ParserError` propagan) y escribe el log de confirmaciones sin lock ni atomicidad en la creación. | `storage/starters.py:64` |
| N-B-21 | `float(fip)` tras `pd.notna` lanza `ValueError` con texto (`pd.notna("x")` es `True`); el llamador `daily.py:649` no está en un `try` propio. | `storage/starter_fip.py:60` |
| N-B-22 | La partición mensual se deriva por rebanado sin validar `captured_at`: una fecha sin separadores produce `odds_mlb_2026083.csv`. | `storage/odds_store.py:52` |
| N-B-23 | El manifest del feature store se escribe sin atomicidad mientras el dataset sí la tiene. Ambas rutas de fallo son seguras (se reconstruye); asimetría, no riesgo. | `storage/feature_store.py:163-169` |
| N-I-1 | El docstring de `_decision_probability` afirma que el retrain entrena sobre `model_probability`; el retrain usa `adjusted_probability` (`calibration/data.py:213`) desde el pre-registro 2026-08-24. El invariante train==serve **sí se cumple**, pero por la otra columna. `calibrator.py:516-518` arrastra la misma afirmación obsoleta. | `pipeline/probabilities.py:187-190` |
| N-I-2 | El docstring de `_zero_stake_flag` omite `incomplete_market`, que en el código tiene la segunda precedencia. El orden del código es el correcto. | `pipeline/daily.py:452-479` |
| N-I-3 | La ventana efectiva del rescate histórico es de 0 a 3 días (`STALE_VOID_DAYS`), no la del histórico: si el backfill se retrasa >3 días la evidencia se anula, y >7 días las filas salen de `pending` y quedan invisibles. Verificado que hoy funciona: las 122 anulaciones de fútbol son aplazamientos genuinos (0 tienen resultado en el store). | `settlement/runner.py:152`, `:196` |
| N-I-4 | Off-by-one conservador en el aviso de filas fuera de la ventana de scores (`days_from + 1` = 4 días frente a los 3 que cubre la API), y la ruta de tenis nunca emite el aviso. | `settlement/runner.py:304-312`, `:347` |
| N-I-5 | `backfill_teams` importa el alias privado `_atomic_write_csv` desde `runner` en vez del canónico `sqp.storage.atomic`, arrastrando la cadena de imports del runner en un módulo que presume «no API». | `settlement/backfill_teams.py:49` |
| N-I-6 | El guard `st != "nan"` es código muerto bajo pandas 3.0. El resultado sigue siendo correcto por otra vía (la comparación con faltante da `False`). | `pipeline/cleanup.py:143-144` |
| N-I-7 | Rama muerta en el conteo devuelto por `log_pitcher_confirmation`: `atomic_write_csv` crea el fichero, así que `p.exists()` es siempre `True` y ambos valores del ternario coinciden. | `storage/starters.py:88-89` |
| N-I-8 | `intraday_scan` documenta y reporta «h2h» cuando desde la v2 evalúa `h2h`, `spreads` y `totals`. | `pipeline/intraday_scan.py:80-82`; `scripts/capture_closing_odds.py:103` |
| N-I-9 | `closing_capture` gasta cuota en ligas cuyos picks tienen todos stake 0. Puede ser deliberado (CLV en modo sombra); el contrato no está explícito. | `pipeline/closing_capture.py:38`, `:43` |
| N-I-10 | Rutas fijas a `ROOT` en `closing_capture` pese a recibir `predictions_dir` como parámetro: sin aislamiento demo, a diferencia del resto del proyecto. | `pipeline/closing_capture.py:105`, `:122` |
| N-I-11 | `closing_capture` no captura el cierre real: con cadencia horaria y ventana de 120 min, la última foto cae en `[0, 60)` min antes del inicio. Deducción del calendario, no medición. | `pipeline/closing_capture.py:30-33` |
| N-I-12 | Docstring del feature store desactualizado: dice «currently nba/nfl/nhl» cuando `SUPPORTED` incluye `mlb` y todo el camino MLB existe. | `storage/feature_store.py:132-134` |
| N-I-13 | El default de `kelly_fraction_stake` en la firma es 0,25 y producción usa 0,08. Ya registrado como `R-I-1` en la iteración 2; se mantiene. | `risk/kelly.py:16` |

## Descartados con evidencia (iteración 3)

| Sospecha | Por qué se descartó |
|---|---|
| Look-ahead en las features de forma/racha/promedios, que no reciben fecha de referencia (a diferencia de `team_rest_days`). | Refutado para la ruta diaria: `results` sólo contiene partidos completados (`daily.py:532` filtra por `s.get("completed")`) y todo evento que genera candidato está en el futuro — `daily.py:699` marca los ya comenzados con `warn` y `:780` salta el bucle entero. Todos los inputs preceden al cutoff. **Caveat registrado:** esas funciones son ciegas a la fecha, así que cualquier llamador de replay/backtest debe pasarles un `results` ya truncado. |
| Los gates de riesgo se podrían sortear por alguna ruta de escritura de stake. | Refutado: no existe camino que escriba `stake > 0` sin pasar por `_zero_stake_flag`. Modo edge (`daily.py:917-918`) y modo accuracy (`:894-912`) convergen en `:925-933`; los dos caps sólo multiplican por `factor < 1`; `_gate_verdicts` es default-deny (`:440-443`). |
| NaN propagándose al de-vig. | Refutado: `is_usable_price` filtra en `_consensus_lines:35`, `_consensus_counts:62` y `_consensus_spread:78`; `_novig_probs:111` y `_spread_novig:134` lo re-verifican sobre las medianas; `remove_vig_power` lanza `ValueError` ante no finitos. |
| Probabilidades fuera de [0,1]. | Refutado: `_p_adj` clampeado; `_decision_probability` es combinación convexa de dos valores en [0,1]; `kelly_fraction_stake` rechaza `p` fuera de `(0,1)`. |
| Duplicación del stream servido al reejecutar el mismo día. | Refutado: `KEY_COLS` incluye `generated_at` truncado a día, así que un segundo run escribe 0 filas. |
| `three_way` mal configurado inflando el de-vig. | Refutado: las 8 entradas de `SPORT_KEYS` son 2-way genuinas, tenis lo es por construcción y todas las ligas de `soccer.yaml` entran con `three_way: True`. |
| Un run demo pisando salidas live. | Refutado: `_finalize` enruta a `data/predictions/demo` y `ServedStore(..., demo=True)` a `data/calibration/demo`. |
| Las 12 anulaciones de MLB indicarían que el fallback histórico falla también en deportes de equipo. | Refutado: las 12 son ambigüedades (más de un resultado para el mismo par en ±1 día), es decir doubleheaders. Es el skip intencionado y documentado en `runner.py:121-123`. |
| Las 122 anulaciones de fútbol serían evidencia recuperable perdida. | Refutado: ninguna tiene resultado en el `ResultsStore` (0 en orden directo, 0 en inverso, 122 ausentes). Aplazamientos genuinos. |
| Re-ejecutar el settlement puede anular un pick ya liquidado correctamente. | Refutado: `void_stale_candidates` salta los eventos con score y, si el evento salió de la ventana, el `void` comparte `DEDUP_KEY` con la fila persistida y se descarta. |
| `realized_roi` mezclaría numerador y denominador. | Refutado: `push` y `void` reciben `pnl = 0.0`, así que el numerador es idéntico al de las filas graduadas. Sin efecto. |
| `purge_old_artifacts` podría borrar datos crudos, `settled_*.csv` o modelos. | Refutado: la allowlist son tres pares carpeta+patrón literales, sin recursión, y `clv_gate.json` queda fuera por el filtro `.md`. |
| Comparación lexicográfica de `start_time` con sufijos `Z` y `+00:00` mezclados. | Refutado: The Odds API emite `...Z` y ambos módulos formatean `now` con `"%Y-%m-%dT%H:%M:%SZ"`. Formato homogéneo → orden lexicográfico == cronológico. |
| `add_spent` perdería gasto acumulado, o `with_suffix` corrompería el dotfile `.closing_credits_*`. | Refutado por reproducción: el lock + `tmp` + `os.replace` funciona, los negativos se ignoran y `tmp` sale `.closing_credits_20260830.tmp`. Sin huérfanos. |
| `entry_edge` y `edge_now` de `intraday_scan` se calcularían sobre bases distintas. | Refutado: `daily.py:841` persiste `e = edge(p_decision, price)` como `estimated_edge`, y `intraday_scan:125-134` usa `calibrated_probability`, que es el mismo `p_decision`. |
| Los 8 `.bat` propagarían mal el errorlevel. | Refutado por lectura de los 8: `if errorlevel 1 goto :error` tras cada paso que lo requiere, `call` para los anidados (`DIARIO_COMPLETO` → `SETTLE_ALL` → `RUN_DIARIO_ALL`, con `exit /b 1` que propaga), `setlocal` en todos, intérprete fijo con fallback y rotación de log vía `call`. La única omisión (`purge_artifacts.py` sin comprobación en `BACKFILL_ALL.bat:31`) está **documentada como deliberada** en el propio comentario `:28-30`. |

---

# Iteración 4 (2026-08-31 / 09-01): la superficie que ninguna iteración había tocado

Alcance: `features/`, `sports/`, `models/`, `simulation/`, `backtesting/`,
`evaluation/`, `calibration/{data,pergame,metrics}`, `providers/`, `audit/`,
`monitoring/`. Unas 6.500 líneas que las iteraciones 1-3 nunca auditaron como
alcance primario.

Método: cuatro especialistas de solo lectura en paralelo (fase 1). Tres se
cayeron por error de API y se relanzaron. Fase 2 propia sobre todos los ALTOS.
`git status` idéntico antes y después de la fase de auditoría.

## ALTO

### N4-A-1 · La lista diaria de picks ordena y puntúa con la probabilidad SIN calibrar

- **Estado:** `REPRODUCIDO` (medición propia) · **Confianza:** ALTA · **Categoría:** corrección de métricas
- **Componente:** `audit/html_report.py:_todos_records`, `evaluation/tipster.py:tipster_table`
- **Contrato canónico:** `_decision_probability` (`pipeline/probabilities.py:178-201`)
  devuelve **dos** probabilidades. `p_used = (1-s)*p_model + s*fair` es la mezcla
  **cruda** y se persiste como `estimated_probability`;
  `p_decision = (1-s)*cal(p_model) + s*fair` lleva el calibrador, se persiste
  como `calibrated_probability` y es la que produce el edge (`daily.py:841`).

- **Medición propia** sobre las últimas 2.000 filas de `served_mlb.csv`:

  | Comprobación | Resultado |
  |---|---|
  | `estimated_edge` consistente con la **calibrada** | **2.000 / 2.000** |
  | `estimated_edge` consistente con la **estimada** | 729 / 2.000 |
  | Filas donde ambas difieren | **1.272** (máx **8,95 pp**) |
  | Cambios de signo del margen | **252** |
  | Selecciones con «margen positivo» | **441** con la cruda vs **271** con la de decisión (**+63 %**) |

  La comprobación de consistencia exige una tolerancia acorde al doble redondeo
  a 4 decimales de ambas columnas. Con `1e-6` salen 112/2.000 y la conclusión se
  invierte: estuve a punto de refutar el hallazgo por eso, y lo anoto para que
  nadie repita el error.

- **Esperado vs observado:** el propio repositorio ya había fijado la regla en
  `audit/segments.py`: "la CALIBRADA cuando existe... medir sobre otra
  probabilidad que la que decidió el pick distorsionaría el control (decisión
  2026-07-27)". `segments` la cumplía; la lista diaria y el tipster no. El
  docstring de `roi_esp` afirmaba ser "el `estimated_edge` de siempre" — falso
  en el 64 % de las filas MLB.
- **Impacto:** la vista que materializa la REGLA FUNDAMENTAL —todos los deportes
  y mercados ordenados por probabilidad descendente— ordenaba, calculaba
  breakeven, margen y ROI esperado, y asignaba el tier del Tipster, con una
  probabilidad que el sistema había descartado.
- **CORREGIDO.** El predicado vive ahora una sola vez en
  `evaluation/labels.decision_prob`, compartido por `segments`, la lista diaria y
  el tipster. Se eligió `labels` y no `audit/segments` para no acoplar
  `evaluation` a `audit`.

### N4-A-2 · Un fallo de liquidación desaparece y el tablero se pone verde

- **Estado:** `VERIFICADO_ESTATICAMENTE` (verificado por mí) · **Confianza:** ALTA · **Categoría:** monitoring
- **Componente:** `monitoring/run_status.py:34-52`, `:55-74`
- **Evidencia:** `record_run_failure` hacía `out.write_text(...)`, sobrescribiendo
  el fichero entero en vez de fusionar por etapa. Secuencia:
  1. `SETTLE_ALL.bat` falla, centinela `{stage: settle}`.
  2. `RUN_DIARIO_ALL.bat` falla, centinela **sobrescrito** `{stage: run}`; el de
     liquidación ya no existe.
  3. Se arregla el run y se relanza: `run_status.py --clear --only-stage run`
     encuentra `stage == "run"`, da el visto bueno y **borra el centinela entero**.

  Resultado: liquidación nunca ejecutada, `health` en verde, banner apagado.
- **Esperado vs observado:** el docstring de `clear_run_status` dice literalmente
  que "borrar el centinela entero dejaria el fallo de la otra sin avisar". El
  `--only-stage` implementa esa intención en la lectura; la escritura la
  destruía.
- **Impacto:** rompe en silencio el contrato SETTLE→RUN de `CLAUDE.md`. La
  auditoría de ROI, el CLV, el monitor de degradación y el prediction gate
  siguen corriendo sobre datos de liquidación viejos sin que nada avise. Es la
  reaparición del hueco S-1 que este módulo existe para cerrar.
- **CORREGIDO.** El centinela se indexa por etapa (`{"stages": {...}}`), se
  fusiona al escribir, `--only-stage` borra sólo su entrada, y con las dos rotas
  manda la de liquidación. Se absorbe el formato plano anterior para no estrenar
  una ventana ciega al actualizar.

### N4-A-3 · El único arnés que mide las features está congelado: no mide nada

- **Estado:** `REPRODUCIDO` (verificado por mí) · **Confianza:** ALTA · **Categoría:** validación / contaminación metodológica
- **Componente:** `scripts/measure_features.py:166-242`
- **Evidencia (lectura propia):** `team_hist` sólo recibe `append` en el cebado
  del warmup (`:152-153`) y en la rama de marcador ilegible (`:173-174`, seguida
  de `continue`). El cuerpo normal del bucle termina en `:242` **sin reinsertar
  el partido evaluado**. Cada partido de test se puntúa contra el mismo
  historial congelado en el borde del warmup: la feature es una **constante por
  equipo** y la correlación medida es un efecto fijo de equipo, no una señal
  walk-forward.
- **Agravante:** sobre marcadores aleatorios puros el arnés emitía significación
  espuria (`rest_diff ... 0,0467 **`), y sobre datos cíclicos deterministas todas
  las features salían `***`.
- **Impacto:** es el **único** arnés del repositorio que mide las features de
  `rest_form`. El bug existe desde su primer commit (`83b1e96`, 2026-08-23), el
  mismo día en que se activó `streak_coef=0.01` apoyándose en sus cifras.
- **CORREGIDO.** El partido evaluado se reinserta al final del cuerpo del bucle,
  después de calcular todas las señales. Hay test explícito de que la corrección
  **no** introduce lookahead.

### N4-A-4 · `streak_coef` es el único coeficiente activo y multiplica un entero sin cota

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** validez del modelo
- **Componente:** `features/rest_form.py:478-516` (`team_streak`), `:519-542`
  (`streak_p_adjustment`); `configs/default.yaml`
- **Verificado por mí** con `Settings.load()`: `streak_coef = 0.01` es el
  **único** coeficiente de feature no nulo; los otros siete están a 0,0.
  `min_edge=0.02`, `market_shrink=0.5`, `max_plausible_edge=0.075`,
  `kelly_fraction=0.08`. Una sonda con `Settings()` en vez de `Settings.load()`
  devuelve los defaults del dataclass (kelly 0.25, max_plausible 0.15) y fue lo
  que me hizo dudar del especialista antes de comprobarlo bien.
- **Evidencia:** `team_streak` es la única feature del módulo **sin parámetro
  `n`**: recorre todo el histórico, sin ventana y sin corte de temporada, y
  devuelve un entero sin acotar. `streak_p_adjustment:542` devuelve
  `sign * (streak_home - streak_away) * streak_coef`, sin cap. Todas las
  hermanas acotan su entrada.
- **Magnitud medida** sobre `data/historical/results_*.csv`: con
  `streak_coef=0.01` y `market_shrink=0.5` el desplazamiento de `p_decision` es
  `0,005 * d`. Un `|d| >= 4` iguala por sí solo todo el suelo `min_edge` de 2 pp,
  y ocurre en el **31-45 % de los partidos** de MLB/NBA/NFL/NHL. El máximo
  observado (NBA, d=37) son **18,5 pp**.
- **Origen:** el commit que lo activó (`7062dae`, 2026-08-23) dice
  "Sin evidencia OOS aun; activado para comenzar a acumular datos",
  contradiciendo el contrato del propio módulo (`:532`): "streak_coef defaults
  to 0 (no-op); activate only after OOS validation". La evidencia que existía
  venía del arnés roto de N4-A-3.
- **Compatible** con la memoria «Escalera min_edge invertida 2026-08-25» (subir
  `min_edge` empeora monótonamente hit rate y ROI: síntoma de un edge declarado
  que es error del modelo). **No se afirma causalidad**, sólo coincidencia
  temporal y mecánica.
- **NO CORREGIDO — requiere decisión del operador.** Es un parámetro de modelo.

### N4-A-5 · El tuning despliega el argmin de muestra COMPLETA y lo etiqueta como validado fuera de muestra

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** selección retrospectiva
- **Componente:** `backtesting/tuning.py:102-111`, `:166`, `:173`; `scripts/tune_ratings.py:79-92`
- **Evidencia:** `rolling_origin_improvement` mide la mejora del *procedimiento*
  por folds y devuelve `selections`, pero `_gate` **descarta** ese campo. Lo que
  se recomienda y se escribe a `configs/leagues/ratings.yaml` es
  `table.loc[table["log_loss"].idxmin()]`: el argmin sobre **toda** la serie,
  bloques de test incluidos. Reproducido: el valor desplegado (150,0) no fue
  elegido por **ningún** fold (todos eligieron 15,0), y aun así el `note` que ve
  el operador dice "selection validated out-of-sample". El docstring del módulo
  dice lo contrario y es el correcto: "selection is still in-sample".
- **Impacto:** hay al menos un parámetro ya desplegado con esa justificación
  (`registry.py:73`, wnba `scoring_half_life_days=60`, "mejora OOS +0,0289 sobre
  4 folds"): esa cifra valida el procedimiento, no el 60.
- **NO CORREGIDO todavía.**

### N4-A-6 · El histórico de entrenamiento de calibración no colapsa la duplicación; `min_n` cuenta FILAS

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** calibración
- **Componente:** `calibration/data.py:116-131`, `calibrator.py:510`, `:553`
- **Evidencia:** la clave de dedup incluye `gen.str[:10]`, así que un pick
  servido 7 días sobrevive 7 veces. Aguas abajo, `train_market_calibrators` corta
  por `len(df) < min_n` (filas, no eventos) y registra `n_events` **sin usarlo
  como gate**. Medido: 47 grupos `(liga, mercado)`, 45 con `filas >= 40` pero
  sólo **27 con picks >= 40**. Peores casos: bundesliga h2h 63 filas / 9 picks /
  3 eventos; epl h2h 222 filas / 36 picks / 12 eventos. Además las 7 copias de un
  pick no son idénticas (rango intra-pick medio de `adjusted_probability` 0,0047,
  máx 0,0545): son observaciones correlacionadas, no repetidas.
- **Atenuante verificado:** el split train/val sí agrupa por `event_id` y la
  promoción sí exige eventos (`AUTO_PROMOTE_MIN_N_VAL=30` sobre `n_val_events`).
  El daño es al ajuste y al gate de entrenamiento, no a la fuga entre splits.
- **NO CORREGIDO** — 18 grupos dejarían de entrenar. Cambio operativo visible.

### N4-A-7 · `expected_calibration_error` sub-reporta ante cualquier probabilidad NaN

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** métrica de gate
- **Componente:** `calibration/metrics.py:20-42`
- **Evidencia:** `np.digitize(nan, bins)` aterriza en el bin superior tras el
  `clip`; luego `Series.sum()` omite NaN mientras el denominador sigue contando
  esas filas. Con `p=[0.1, 0.2, nan, 0.9]` el ECE sale **deflactado**, no NaN, y
  además anula la contribución del bin legítimo 0.9-1.0.
- **Impacto:** el ECE gobierna los gates de entrenamiento y el pre-registro
  2026-08-24. Sub-reportar en silencio, y en la dirección que aparenta mejor
  calibración, es el modo de fallo que deja pasar un calibrador defectuoso.
- **CORREGIDO.** `reliability_table` descarta los pares no finitos.

### N4-A-8 · `score_model_vs_market` puntúa sobre el stream inflado

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** independencia de la muestra
- **Componente:** `evaluation/model_vs_market.py:114-141`
- **Evidencia:** filtra por `result` y agrupa, pero nunca colapsa a una fila por
  pick, aunque `edge_information.one_row_per_pick` existe exactamente para eso.
  Medido: 17.213 filas a 7.338 picks (2,35x). En `totals` el estimador puntual
  **subestima el déficit del modelo en un 43 %** (0,00846 crudo vs 0,01483
  colapsado). El bootstrap sí clusteriza por evento, así que el intervalo absorbe
  la correlación; el problema es el punto estimado y el `n` publicado.
- **NO CORREGIDO todavía.**

### N4-A-9 · `health.py` puede dar verde con el sistema roto

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** monitoring
- **Componente:** `monitoring/health.py:24`, `:158-177`
- **Evidencia:** (a) `ML_LEAGUES = ["mlb","nba","nfl","nhl"]` mientras producción
  sirve **23 ligas**: no cubre 20 de ellas, y sí cubre nba/nfl/nhl, que hoy no
  sirven. (b) `totals_model`, `calibration`, `calibration_markets`,
  `model_age_days` y `registry_exists` se registran en el JSON y **ninguno
  genera warning ni error**. (c) El informe real del 2026-08-30 dice
  `"status": "WARN", "errors": []` con nba/nfl/nhl en `calibration: false` y
  `model_age_days: 19.9`. (d) No hay ningún chequeo de «¿corrió el run?».
- **NO CORREGIDO todavía** — ampliar el alcance disparará errores ruidosos el
  primer día; requiere distinguir «liga ML» de «liga servida».

## MEDIO y BAJO

| ID | Hallazgo | Componente |
|---|---|---|
| N4-M-1 | El ajuste de abridor MLB es un **no-op** (`pitcher_bound: 0.0`), pero un abridor desconocido sigue suprimiendo todos los candidatos: no aporta al modelo y sí bloquea picks. Todo el backfill de FIP queda inerte. | `models/starters.py:34-46`, `configs/leagues/ratings.yaml:16-19` |
| N4-M-2 | `weather.py` cambia a datos **observados** (endpoint archive) para cualquier fecha pasada, según el reloj de pared y no el corte de información: trampa de fuga para backtest/replay. Hoy inalcanzable (coefs a 0, único llamador sobre eventos futuros). | `features/weather.py:43-50` |
| N4-M-3 | El ROI global no expone `n_staked`: se publica «1.090 apuestas liquidadas» junto a «ROI realizado -15,3 %» cuando el ROI corresponde a **150** apuestas con stake. `_segment_audit` ya recibió esta corrección; el bloque global no. | `audit/report.py:276-284` |
| N4-M-4 | El CLV global y la **regla de salida de shadow** cuentan filas no finitas. Una sola fila con precio corrupto lleva la mediana a `inf`, e `inf > 0` satisface la condición. El arreglo F-02 se aplicó en `clv_segments` y en `clv_gate`, no aquí. | `audit/clv.py:178-192` |
| N4-M-5 | Truncado silencioso a 500 filas en «Todos los Picks» mientras el contador dice 910. La vista existe para cumplir «TODOS los deportes y mercados». | `audit/html_report.py:1330` |
| N4-M-6 | `OFFLINE_MODE` no protege los endpoints sin caché: `/scores` (de pago) y `/sports` salen a la red igualmente. | `providers/odds_api.py:148-150` |
| N4-M-7 | Los proveedores ESPN sólo reintentan `Timeout`/`ConnectionError`: un 429 o un cuerpo no-JSON aborta el backfill completo de la liga, contra lo que promete su docstring. `_RETRY_STATUS` no incluye 429, que sí se añadió en `odds_api`. | `providers/espn_results.py:105-122`, `espn_tennis.py:106-122` |
| N4-M-8 | `SyntheticProvider` revienta con `KeyError 'tennis'`: el modo demo no existe para tenis y falla con una excepción opaca en vez de `ProviderNotConfiguredError`. | `providers/synthetic.py:12-18` |
| N4-M-9 | La ventana de tenis se recorre a saltos de 7 días: con los defaults de producción sólo se consultan 2 de los 8 días, y con `days_back=7` el final de la ventana nunca se consulta. El test que dice cubrirlo omite la aserción del extremo. | `providers/espn_tennis.py:30`, `:96-101` |
| N4-M-10 | MLB StatsAPI se limita a `gameType="R"` en resultados/starters/FIP, pero **no** en `fetch_probable_pitchers`: se generan picks de playoff cuyos resultados el mismo proveedor nunca devolverá. | `providers/mlb_statsapi.py:58`, `:90`, `:114` |
| N4-M-11 | El test de signo del gate intradía trata como independientes filas del mismo evento en mercados distintos (1,10-1,13x). Es el único test de hipótesis formal del alcance y su `PASS` autoriza construir la fase intradía. | `audit/intraday_gate.py:46`, `:99-109` |
| N4-M-12 | `pergame.cross_evaluate_on_settled` aplica el calibrador live a `model_probability` cuando el objetivo vivo es `adjusted_probability`, y puntúa el brazo `live` **en muestra**. Comparación asimétrica sesgada a favor de `live`. | `calibration/pergame.py:128`, `:136` |
| N4-M-13 | El backtest de ROI omite la capa de ajuste por features sin declararlo entre sus exclusiones, y usa el mismo snapshot pre-commence como precio **y** como ancla de shrink, mientras producción sirve hasta 7 días antes. | `backtesting/roi_engine.py:227-239`, `:83-92` |
| N4-B-1 | `team_recent_form`, `team_h2h_form` y las dos por rol cuentan las filas ilegibles en el denominador; las cinco hermanas del mismo módulo no. Sesgo siempre hacia derrota. | `features/rest_form.py:76-90` y ss. |
| N4-B-2 | `team_rest_days` lanza `ValueError` no capturada con fecha vacía, y se invoca incondicionalmente aunque `rest_days_coef` sea 0. | `features/rest_form.py:50-52` |
| N4-B-3 | Semántica de fecha mixta local/UTC entre `results` y la fecha de referencia del evento. Hoy nulo (`rest_days_coef=0`), bloqueante si se activa. | `features/rest_form.py:29-52` |
| N4-B-4 | `ml_predict._check_hash` avisa y **carga igualmente** un artefacto joblib cuyo hash no cuadra; `joblib.load` deserializa pickle. Ruta desconectada. | `models/ml_predict.py:38-50` |
| N4-B-5 | `patterns.hit_rate` produce `roi_% = inf` sin stake; `report.py:249` ya tiene la protección y este módulo no la recibió. Latente: la pestaña está muerta porque `pick_history.csv` no existe. | `audit/patterns.py:116` |
| N4-B-6 | 5 filas graduadas duplicadas por pick en `settled_*.csv` (5/1090 = 0,46 %), por `DEDUP_KEY` con `generated_at`. | `audit/report.py:172-179` |
| N4-B-7 | Caché de cuotas en disco sin poda y con escritura no atómica. | `providers/odds_cache.py:49-54` |
| N4-B-8 | `_capture_quota` no corre en las llamadas que terminan en error: un 429, que es la respuesta con más información de cuota, se descarta. | `providers/odds_api.py:178-192` |
| N4-B-9 | `build_team_rolling_dataset` acepta en silencio un DataFrame no ordenable (`sort_values([])` no lanza), anulando la garantía walk-forward. Hoy protegido por el único llamador. | `features/builders.py:48-55` |

## Descartados con evidencia (iteración 4)

El primero es el más importante, porque era la hipótesis central del encargo.

| Sospecha | Por qué se descartó |
|---|---|
| **Fuga temporal por las features sin fecha de corte.** `team_recent_form`, `team_streak`, `team_avg_*`, `team_over_rate`, `team_h2h_form` y las dos por rol no reciben fecha de referencia, a diferencia de `team_rest_days`. La iteración 3 lo descartó sólo para la ruta diaria y dejó abierto si algún llamador de backtest/replay/entrenamiento podía pasar un histórico no truncado. | **Refutado por enumeración exhaustiva.** Existen exactamente **dos** llamadores en todo el repo: `pipeline/daily.py` (pasa sólo partidos completados, y todo candidato está en el futuro; `_already_started` marca `warn` y `:780` descarta) y `scripts/measure_features.py` (construye rebanadas previas; N4-A-3 demuestra que además estaban congeladas, es decir aún más conservadoras). **Ningún** llamador de backtest, replay, entrenamiento ni feature store: verificado positivamente que `backtesting/engine.py`, `roi_engine.py`, `storage/feature_store.py`, `models/ml_train.py` y `scripts/train_models.py` no importan `sqp.features.rest_form`. |
| Los dos motores de backtest tendrían lookahead. | Refutado: `engine.py:67-108` y `roi_engine.py:207-264` estiman con `adapter.estimate(...)` y sólo después ejecutan `adapter.observe(r)`. Ningún resultado entra al estado antes de ser predicho. |
| Split aleatorio en `ml_train.py`. | Refutado: `TimeSeriesSplit` sobre datos ordenados por fecha; `oos_moneyline_metrics` corta por índice tras `sort_values("date")`; `random_state=42` sólo alimenta el `subsample` de los GBM. `SimpleImputer` y `StandardScaler` van dentro del `Pipeline`, así que se reajustan por fold: no hay fuga de preprocesado. |
| Contaminación de etiqueta en los builders. | Refutado: `get_team_features` se calcula **antes** de `update_team_stats`, y `NON_FEATURE_COLS` excluye una a una todas las columnas postpartido que emiten ambos builders. |
| `evaluation/bootstrap.py` sería el principal contaminado por la n inflada. | Refutado: su llamador `edge_information.prepare` **sí** colapsa con `one_row_per_pick` antes de medir (17.213 a 7.338, coherente con el 2,31x medido en la iteración 3), y su remuestreo por clusters es metodológicamente correcto. El módulo culpable es `model_vs_market.py` (N4-A-8). |
| La duplicación 2,31x contaminaría las cifras de `audit/`. | Refutado: los cuatro módulos que producen cifras leen `settled_*.csv`, no el stream servido; 5 duplicados sobre 1.090 filas (0,46 %). |
| El `n` del gate de CLV estaría inflado por filas del mismo evento. | Refutado en magnitud: dentro de cada `(liga, mercado)` los ratios filas/eventos son 1,00-1,09. `clv_segments` agrupa así, luego su `n` es prácticamente de unidades independientes. |
| `compare.py` seleccionaría y puntuaría sobre el mismo tramo. | Refutado: selecciona en `[:mid]` y reporta en `[mid:]`, disjuntos. |
| Push/void inflarían el ROI del backtest. | Refutado: `settle.py:92-93` asigna `pnl=0.0` a ambos y `_summarize` usa denominador sólo-graduado. Queda un defecto de reporte, no de cálculo. |
| Peticiones sin timeout en providers. | Refutado línea a línea en los 8 ficheros: `odds_api` 30 s, `mlb_statsapi` 60 s por defecto más los explícitos, ESPN 60 s. Ninguna sin límite. |
| La clave de caché filtraría el `apiKey`. | Doblemente refutado: la clave se calcula **antes** de inyectar la key, y `odds_cache.py:22` la filtra explícitamente. Hay test que lo fija. |
| Un payload de 6 h servido como fresco para generar picks. | Refutado: `daily.py` acota el TTL contra `revalidation_price_max_age_min` y hay test que ancla el literal. |
| Fuga de secretos en los informes HTML o en `monitoring/`. | Refutado: cero coincidencias de credenciales; todas las tablas se construyen con listas de columnas explícitas; el banner escapa con `html.escape`. |
