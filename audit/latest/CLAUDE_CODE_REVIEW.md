# Revisión de Claude Code y Quant Loops — Auditoría 2026-07-29/30

Alcance: 3 `CLAUDE.md`, `ORCHESTRATOR.md`, 7 archivos de `automation/`, 8 loops
genéricos + 14 quant, 24 agentes, 16 comandos, 8 rules, 6 workflows, 7 playbooks,
6 checklists, 5 output-styles, 6 templates, `settings.json`, 5 hooks, router de
modelo (4 archivos), `README.md`, `docs/`, bóveda Obsidian.

## 1. Arquitectura y jerarquía de instrucciones

La jerarquía está bien declarada y **sin contradicciones internas**:

1. `CLAUDE.md` raíz + `.claude/CLAUDE.md` (reglas permanentes) — `ORCHESTRATOR.md:6`
   lo confirma: *"permanent repository rules always have precedence"*.
2. `.claude/rules/*.md` (8 reglas).
3. `.claude/automation/autonomy-policy.md` (límite duro de autonomía).
4. `.claude/automation/decision-engine.md` (selección de loop).
5. El loop seleccionado.
6. Router de modelo — explícitamente subordinado (`decision-engine.md:47`,
   `ORCHESTRATOR.md:92`).

**El problema no era la jerarquía sino la deriva de contenido dentro de ella**, y en
particular que el cambio de objetivo ROI→hit rate del 2026-07-27 no se propagó.

### Integridad referencial: excelente

Se extrajeron y verificaron las **67 referencias únicas** en backticks a
`.md`/`.py`/`.bat`/`.json`/`.yaml`/`.sh`/`.toml` de `ORCHESTRATOR.md`, `CLAUDE.md`,
`automation/`, los 22 loops, 16 comandos, 6 workflows, 7 playbooks y 6 checklists.

**Resultado: 0 referencias rotas.** Inusual en una configuración de este tamaño.
Los 5 hooks de `settings.json` existen (todos LF), y los 24 agentes referenciados
existen y están registrados en el harness.

### Contradicciones encontradas y resueltas

| Contradicción | Fuentes | Resolución |
|---|---|---|
| El loop 01 ordenaba `RUN_DIARIO_ALL.bat`, que el README declara prohibido antes de liquidar | `01:19` vs `README:76-78` | Loop y `.claude/CLAUDE.md:50` → `DIARIO_COMPLETO.bat`, con el orden crítico explícito |
| Dos protocolos de memoria en conflicto | `skills/memoria-persistente/SKILL.md:12-20` (stubs vacíos) vs `commands/memoria-cargar.md:6-9` (`.claude/memory/`) | `SKILL.md` reescrito; los 8 stubs convertidos en punteros |
| Política de modelos escrita 3 veces, ya divergente | `MODEL_ROUTING.md:12-14`, `decision-engine.md:47`, `ORCHESTRATOR.md:90-92` | `MODEL_ROUTING.md` es la fuente única; los otros dos enlazan |
| Los loops 01 y 03 ordenan gastar API de pago contra el gate de aprobación | `01:19`, `03:17` vs `ORCHESTRATOR.md:74`, `autonomy-policy.md:17` | Nota explícita de aprobación en ambos loops |
| El `.gitignore` afirma que `superpowers-main` fue eliminada "deliberadamente, no restaurar"; hay 172 archivos en disco | `.gitignore:27-29` vs disco | **Sin resolver: requiere decisión humana.** No puedo confirmar si fue intencional |

## 2. Estado del router de modelo

**Registro del hook: correcto.** `settings.json:95-105` registra `route-model.py` en
`UserPromptSubmit` con timeout 10 s; el contrato de salida
(`hookSpecificOutput.additionalContext`) es el adecuado, y el `except` global
(`route-model.py:33-35`) degrada a no-op sin bloquear el prompt. Buen diseño defensivo.

**Coherencia de referencias: correcta.** Los 10 `primary_agent`, 21 `support_agents`
y 9 `loop` referenciados existen todos en disco.

### K-004 — el fallo grave, corregido

10 agentes y 5 rutas declaraban `model: fable`: principal-orchestrator, ml-engineer,
calibration-auditor, leakage-detector, backtest-reviewer, risk-manager,
sports-quant-auditor, feature-engineer, backend-architect, odds-market-auditor.

Es decir, **precisamente los subagentes de mayor criticidad** — auditoría, modelado,
calibración, backtesting y riesgo — apuntaban a un modelo sin créditos en la cuenta,
**sin ningún fallback**. Verificado en esta misma auditoría: dos subagentes fallaron
con `API Error: Fable 5 uses usage credits and you're out`, con `subagent_tokens: 0` y
`tool_uses: 0`. Hubo que relanzarlos con `model` explícito.

`validate_claude_model_routing.py:12` aceptaba `fable` como válido sin comprobar
entitlement, así que el validador daba OK.

**Corregido:** `fable` → `opus` en los 10 agentes y las 5 rutas.
`MODEL_ROUTING.md` documenta por qué. `tests/test_claude_model_routing.py` incluye
ahora `test_no_route_uses_an_unavailable_model`, que impide su reintroducción por
descuido; reactivar Fable exige créditos y revertir esa prueba deliberadamente.

### K-012 — dos clasificadores paralelos (pendiente)

`decision-engine.md:1` declara *"the first matching condition wins"* con 23 reglas
semánticas; `model-routing.json` tiene 10 rutas por keyword con mapeos de loop
distintos. El matching es **substring desnudo** (`route-model.py:12`), sin límites de
palabra: `"error"` matchea "sin errores", `"modelo"` matchea "router de modelo".

Evidencia directa: **el prompt de esta auditoría se clasificó como `modeling`**, no
como `full-audit` — que es la causa mecánica de K-004. Además `full-audit` y
`security` mapean ambos a `refactor.md`: una auditoría completa no es un refactor.

Mitigación existente: la salida se declara "recomendación determinista" y las reglas
permanentes tienen precedencia. Elegir un clasificador único es decisión de diseño.

### K-015 — validador reforzado

Validaba modelo válido, existencia de `primary_agent` y presencia del hook.
**No validaba** que los `loop` ni los `support_agents` existieran, ni el entitlement
del modelo — justo lo que falló. Añadida cobertura vía tests
(`test_every_route_references_an_existing_loop_and_agents`).

## 3. Estado de los agentes

24 agentes, todos con `name`, `description` y `model` en el frontmatter, todos
registrados en el harness. Los 25 archivos estaban modificados sin commitear por una
sesión previa (el trabajo del router).

Un déficit de contenido corregido: **`risk-manager.md:12-19` describía solo el mundo
pre-accuracy** (flat stake, fractional Kelly, Kelly caps, minimum edge thresholds).
Bajo `pick_mode: accuracy` no hay Kelly ni umbral de edge, así que el agente de
riesgo revisaría criterios que ya no gobiernan la selección. Añadido el umbral de
probabilidad y el cumplimiento por banda.

## 4. Estado de la memoria

**Tres almacenes**, uno de ellos activamente dañino:

| Almacén | Estado |
|---|---|
| `.claude/memory/` | **El real.** 19–51 KB por archivo. Es lo que leen `/memoria-cargar` y `/memoria-guardar`. |
| `.claude/skills/memoria-persistente/` | **Stubs vacíos de 15–99 bytes con los mismos nombres**, y el `SKILL.md` ordenaba leerlos. |
| Memoria del harness (fuera del repo) | La que se inyecta al contexto al iniciar sesión; la única que reflejaba el objetivo hit rate. |

Tamaños medidos: `session-summaries.md` 20 bytes vs 51.526; `project-decisions.md`
20 vs 39.427; `known-issues.md` 15 vs 22.705.

El fallo era **silencioso por diseño**: `SKILL.md:41` dice "Nunca inventar memoria",
así que un agente que cargaba los stubs vacíos concluía "sin contexto previo" en
lugar de lanzar un error. **Corregido:** `SKILL.md` reescrito con `.claude/memory/`
como almacén canónico y los 8 stubs convertidos en punteros explícitos.

## 5. Estado de `current-task.md`

Presentaba como actual un estado de **15 días atrás**:

- `Status: done`, `Loop: feature`, `Iteration: 6 / 8`.
- Objetivo del 2026-07-14 ("palanca de velocidad de información").
- `pytest: 407/407` cuando el número real era 439 (hoy 466).
- Y lo más grave: **`"Autorización del operador: total (sesión 2026-07-14 PM),
  incluye commit, push y cambio de scheduler"` — sin fecha de caducidad.**

`ORCHESTRATOR.md:15` y `route-task.md:5` hacen de este archivo la fuente del estado
de tarea, así que un agente leía un `done` ajeno como contexto vigente y una
autorización de push caducada como permiso actual.

**Corregido:** reseteado al estado real de esta auditoría, autorización retirada
explícitamente, y regla añadida a la skill de memoria: *"una autorización del
operador se registra con su fecha; una autorización sin caducidad no se trata como
permanente"*.

No se encontraron loops "aparentemente activos pero terminados" más allá de este.

## 6. Evaluación de los 14 Quant Loops

### Situación encontrada

Grep exhaustivo sobre `.claude/loops/`: `PASS`, `DEGRADED` y `BLOCKED` aparecían **dos
veces en total** (`01:22` y `11:22`), y **`DONE` cero veces**. Ni una sola definición
de umbral. Los 13 loops restantes usaban **vocabularios propios y también
indefinidos**: `INSUFFICIENT/MONITOR/ACTIONABLE` (04), `NORMAL/WATCH/PERSISTENT/CRITICAL`
(06), `NO_DRIFT/DATA_DRIFT/…/INCONCLUSIVE` (07), `REJECT/CONTINUE_SHADOW/CANDIDATE_FOR_APPROVAL`
(09), `MAINTAIN/MONITOR/FIX_DATA/RUN_EXPERIMENT/ESCALATE_INCIDENT` (13).

Criterios expresados en prosa, no verificables: *"muestra suficiente"* (06:22),
*"evidencia insuficiente"* (en los 14), *"confianza media/alta"* (13:19).

Cobertura medida (14 loops × 18 criterios):

| Criterio | Cobertura antes |
|---|---|
| Propósito | 14/14 |
| Precondiciones | 1/14 |
| Comandos concretos ejecutables | 4/14 (01, 03, 09, 10) |
| Artefactos con ruta concreta | **0/14** |
| `PASS` / `DEGRADED` / `DONE` definidos | **0/14** |
| `BLOCKED` definido | 0/14 (aparece como modo en 11, sin definir) |
| Trazabilidad loop→ejecución→artefacto | 1/14 (solo el 10) |
| Acciones permitidas enumeradas en positivo | ~2/14 (los loops solo prohíben) |

Nota: `REVIEW_CALIBRATION_MLB_H2H.bat` y la skill `review-calibration` **existen**,
pero ningún loop los citaba. Y los artefactos existen en el repo
(`segment_diagnostics_latest.csv`, `degradation_pause.json`, `clv_gate.json`,
`report_<día>.md`, `promotion_log.csv`) sin que ningún loop los nombrara.

El loop **10 (controlled-recalibration)** era el único razonablemente completo:
comandos reales, versionado con hash y rango de datos, transición explícita al 09,
gate de aprobación propio. Sirvió de plantilla.

### Mejoras aplicadas

**`.claude/loops/quant/STATES.md` (nuevo)** — fuente única de los cuatro estados,
que es la raíz del problema. Define cada estado por **condiciones observables**, no
por juicio:

- `PASS`: todos los comandos exit 0 **y** todas las validaciones ejecutadas sin
  fallo **y** los artefactos declarados escritos y legibles **y** nada pendiente de
  aprobación.
- `DEGRADED`: comandos y artefactos OK, pero una validación no aplica por muestra
  insuficiente o una fuente no crítica no estaba fresca. **Exige nombrar la
  limitación y el `n`.** Nunca para ocultar un fallo.
- `BLOCKED`: cualquier comando ≠ 0, artefacto ausente/ilegible, validación crítica
  fallida, evidencia insuficiente, o siguiente acción que requiere aprobación humana.
- `DONE`: `PASS` + `/verification-gate` aprobado + bitácora del día + sin ítems
  abiertos. Se aclara que los loops periódicos (01–04, 06, 07, 13) terminan en
  `PASS`/`DEGRADED`/`BLOCKED`; solo los de trabajo cerrado (08, 09, 10, 12) llegan a
  `DONE`.

Regla general explícita: **si el estado no puede determinarse desde un artefacto o la
salida de un comando, el estado es `BLOCKED`, nunca `PASS`.**

Y una tabla de umbrales de muestra que **toma los valores del código, no los invita a
inventarlos**: 15 (segmentos), 30 (degradación), 30 (CLV gate), 30 eventos
independientes (auto-promoción), 200/80 (tuning), cada uno con su archivo de origen.
Cierre explícito: *"si un loop necesita un umbral que no existe en el código, el
estado correcto es `BLOCKED` con una propuesta de umbral, no un `PASS` con un número
improvisado."* Esto era el riesgo real de "mejorar los loops": fabricar criterios
cuantitativos sin evidencia.

**Los 14 loops** referencian ahora `STATES.md` en su bloque de reglas comunes.

**Loops 01, 03 y 04** (los que realmente corren a diario) reescritos con
precondiciones, inputs, comandos concretos, artefactos con ruta, criterios de salida
propios y acciones que requieren aprobación. El loop 04 además ahora reporta **hit
rate y `gap` por banda como métrica principal**, con ROI/CLV degradados a secundarios
y la advertencia de que ROI 0.0 bajo shadow no significa equilibrio.

### Verificación de acciones prohibidas

Se revisó si algún loop permite implícitamente acciones prohibidas. Hallazgos:

- **K-009 (corregido):** "desactivar shadow mode" **no aparecía literalmente** en
  ninguna lista de gates (`ORCHESTRATOR.md:69-77`, `autonomy-policy.md:14-20`); solo
  quedaba cubierto por el genérico *"production configuration changes"*. Y
  `11-season-transition.md:22` permite *"Definir modo NORMAL, CONSERVATIVE, SHADOW o
  BLOCKED"*, donde pasar de SHADOW a NORMAL convierte stake 0 en dinero real.
  Añadido literalmente a ambas listas, junto a `pick_mode`, `accuracy_threshold` y
  `bankroll`.
- **K-002 (corregido):** los loops 01 y 03 ordenaban ejecutar batches que consumen
  The Odds API (plan de pago) sin nombrar el gate. Control mitigante real que ya
  existía: `settings.json` no tiene ninguna entrada `allow` para `*.bat`, así que el
  harness pide permiso de todos modos.
- **K-008 (parcial):** los mejores gates de aprobación estaban en los loops que menos
  se ejecutan (08, 09, 10, 12, 13 tienen gate explícito propio); los diarios (01–04)
  dependían solo de la línea común. Añadido a 01, 03 y 04.

**Defensa en profundidad que sí funciona:** la deny-list de `settings.json`
(`Write(./data/**)`, `Bash(git push:*)`, `Read(./.env)`) bloquea al loop 08 —que
escribe datos— aunque su gate textual fallara.

### K-010 — el gate de salida del shadow sigue sin definir (parcial)

`Obsidian/Tareas.md:12`, el primer pendiente activo, es *"Definir el gate de salida
del shadow para el MODO PRECISIÓN"*. Ningún loop lo cubre: `decision-engine.md:8-20`
enumera 13 rutas quant y ninguna es ese gate, y `09-champion-challenger.md:20` mide
*"Brier, Log Loss, ECE, discriminación, cobertura, ROI/yield y CLV"* — **sin hit rate
ni cumplimiento de umbral por banda**, que es exactamente el KPI nuevo. La skill
`clv-shadow-exit` existe, pero es el gate viejo de CLV, ya declarado no rector.

Aplicado: el loop 04 reporta hit rate y `gap`. **Pendiente:** definir el gate en sí,
que es una decisión estadística del operador, no una corrección mecánica.

## 7. Otros hallazgos de configuración

- **K-013:** `MODEL_ROUTER_INTEGRATION.json` en la **raíz del repositorio** contiene
  `{"version":1,"changed_files":[33 rutas]}` y tiene **0 referencias** en todo el
  repo. Su contenido es equivalente a `git status`. Es una nota de trabajo con
  extensión `.json`. No lo borré (no lo creé yo); se señala.
- **K-025:** `automation/backlog.md:7` está vacío (`No approved autonomous task`) y
  `decision-engine.md:43` hace que el canal autónomo se detenga siempre, mientras
  `Obsidian/Tareas.md` tiene 17 pendientes. No es un bug —el default-deny es correcto
  y deliberado— pero el canal autónomo está estructuralmente inerte.
- **K-026:** `.claude/settings.local.json.backup-audit-20260623` (36 días) sigue en
  disco, cubierto por `*.backup-*`. `Tareas.md:19` deja `M-7` abierto sobre recortar
  los permisos amplios de `settings.local.json`.
- **K-016 (corregido):** `.claude/hooks/__pycache__/` no estaba ignorado (el patrón
  global no lo cubría) y `validate_claude_model_routing.py:3` tenía el único error de
  lint del repo.
- **K-011:** `graphify-out/wiki/index.md`, citado por el `CLAUDE.md` raíz para
  navegación, no existe. La instrucción es condicional, así que no es referencia
  rota, pero la vía recomendada no está disponible.

## 8. Documentación vs código

- **K-017 (corregido):** `README.md:61` decía `# 198 tests`; el real era 439 (hoy
  466). Ninguna de las tres cifras del repo coincidía entre sí
  (`Bitácora/2026-07-28.md` decía 436, que + 3 del router = 439, coherente). Se
  **eliminó** la cifra en lugar de actualizarla: es un valor que se desactualiza en
  cada commit.
- **K-018 (corregido):** el README no mencionaba `pick_mode`, `accuracy_mode`,
  `accuracy_threshold` ni "hit rate", y `:117` describía las salidas como *"solo
  candidatos con edge ≥ mínimo y stake por Kelly fraccional"* — exactamente lo que el
  modo accuracy **ya no hace**. Añadida una sección con las 3 advertencias verificadas.
- **K-020 (corregido):** `.claude/CLAUDE.md:26` y `rules/betting-output-rules.md` no
  incluían el hit rate en la separación obligatoria de métricas, siendo ahora la
  métrica rectora.
- **K-022 (buena práctica, no hallazgo):** `docs/` usa fecha en el nombre
  (`AUDIT-2026-06-14.md`, `CALIBRATION-2026-06-21.md`), lo que evita que se lean como
  estado actual. `docs/CONFIG-PRECEDENCE.md` es el único vivo y está correctamente
  enlazado desde el README.

## 9. Bóveda Obsidian

- **K-007 (corregido):** 17 archivos con nombre **mojibake** (doble codificación
  CP437/UTF-8): `Bit├ícora/` completo (10 archivos), `Bit├ícora.md`,
  `Metodolog├¡a de documentaci├│n.md`, `Automatizaci├│n y operaci├│n.md` y 4 notas de
  `Conocimiento/`. Verificados **byte-idénticos** (sha256) a su equivalente
  versionado. Violaba `Metodología de documentación.md:41` ("No duplicar fuentes
  canónicas") y Obsidian resolvería `[[Bitácora/2026-07-28]]` de forma ambigua.
  Eliminados con un script que solo borra si existe pareja versionada idéntica; los 5
  archivos sin pareja (`.obsidian/`, config del editor) se conservaron.
- **K-024 (corregido):** la última bitácora era del 2026-07-28 y no existía entrada
  para el trabajo del router de modelo (33 archivos), los 14 quant loops ni los 25
  agentes modificados —todo untracked—, contra `.claude/CLAUDE.md:37` ("en la MISMA
  sesión"). Creada `Obsidian/Bitácora/2026-07-30.md`.

## 10. Estado final

| Dimensión | Estado |
|---|---|
| Conectados | ✅ 67/67 rutas válidas; 5 hooks existen; 24 agentes registrados; router registrado en `settings.json` |
| Versionados | ⚠️ Los 14 quant loops, el router (4 archivos) y `STATES.md` siguen **sin commitear**. CI no los lintea ni ejecuta su test hasta que se committeen |
| Consistentes | ✅ Las 5 contradicciones documentadas resueltas, salvo `superpowers-main` (decisión humana) |
| Verificables | ✅ Los 4 estados tienen definición exacta por condiciones observables; los umbrales salen del código |
| Ejecutables | ⚠️ 7 de 14 loops siguen sin comandos concretos (05, 06, 07, 08, 11, 12, 13). Los 4 diarios sí los tienen |
| Pendientes | K-010 (gate de salida del shadow), K-012 (un clasificador o dos), K-023 (`superpowers-main`), K-025 (activar backlog autónomo), completar precondiciones/artefactos en los 10 loops no diarios |

## 11. Mejoras pendientes priorizadas

1. **Definir el gate de salida del shadow para el modo precisión** (K-010) — es el
   pendiente nº1 del proyecto y requiere decisión estadística del operador.
2. **Completar los 10 loops no diarios** con precondiciones, comandos concretos y
   artefactos, usando el 10 como plantilla y `STATES.md` para los estados (~2 h).
3. **Decidir un solo clasificador** (K-012) y anclar los keywords a límites de
   palabra; corregir el mapeo `full-audit → refactor.md`.
4. **Resolver `superpowers-main`** (K-023): borrar el directorio o actualizar
   `.gitignore` y KI-015 explicando la re-vendorización. La contradicción es lo
   inaceptable.
5. **Promover 1-2 ítems de `Tareas.md` a `backlog.md`** o documentar que el backlog
   autónomo es intencionalmente manual (K-025).
6. **Cerrar M-7**: recortar los permisos amplios de `settings.local.json`
   (`pip install *`, `python -`).
