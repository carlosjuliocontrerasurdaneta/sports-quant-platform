# Informe del auditor Claude — ronda `audit-2026-09-22-r2`

- **Fecha:** 2026-09-22 (sesión 20:30–21:05 hora local, fin 2026-09-23T00:05Z)
- **Auditor:** Claude Code, `claude-opus-5-5`, sesión principal, **sin subagentes** (modo no orquestado)
- **Base Git:** `main@9fa276a` = `origin/main`. **Árbol de trabajo NO limpio:** 34 ficheros modificados + 3 sin seguimiento (detalle en §2)
- **Alcance:** auditoría integral del árbol de trabajo tal como lo ejecutará producción, incluida la remediación sin commit de la ronda `audit-2026-09-22`
- **Autorización:** sólo diagnóstico, validación y planificación. **No se ha modificado ningún fichero fuera de `audit/latest/`**, ni `src/`, `tests/`, `scripts/`, `configs/`, `data/`, BAT ni `.claude/`

## 0. Declaraciones previas

1. **Contaminación declarada.** La sesión leyó al principio el `STATUS.md`, la matriz de cobertura y parte de `FINDINGS.md` de la ronda `audit-2026-09-22` (esta mañana) para no duplicar trabajo. Por tanto este diagnóstico **no es ciego** respecto a ella: es una segunda pasada informada. Donde una conclusión propia se apoya en la ronda anterior, se dice.
2. **La skill con la que se lanzó esta auditoría no es la versionada.** `.claude/skills/full-audit/` en el árbol de trabajo es byte a byte la del commit `8952755` (2026-09-03), no la de `HEAD`. Es el hallazgo **CLAUDE-004**. La precedencia de esa misma skill da prioridad a las instrucciones del repositorio, así que esta ronda sigue el contrato canónico `.claude/automation/audit-workflow.md`: rondas, entregables en `audit/latest/` y taxonomía de `AGENTS.md`.
3. **Segunda opinión:** no hubo. El MCP `codex` falló al conectar en esta sesión (`CONNECTION_CLOSED`), igual que en la ronda anterior (`AUD-008`/`KI-056`).

## 1. Resumen ejecutivo

**Propósito del sistema.** Estimar probabilidades para todos los partidos y mercados, y publicar picks diarios priorizados por probabilidad, con salida a stake real sólo a través del gate de predicción pre-registrado.

**Arquitectura.** Paquete Python `src/sqp` (106 módulos, ~20.300 líneas) orquestado por BAT desde el Programador de tareas de Windows. **El árbol de trabajo ES producción**: la tarea ejecuta lo que hay en disco.

**Estado general.** El código versionado está sano: ruff y mypy limpios, CI verde en `HEAD`, 2049 pruebas rápidas en verde y los ocho arreglos de esta mañana correctos en lo sustancial. Los problemas están en el **estado del árbol** y en **un defecto latente de fallo abierto** del gate:

| ID | Sev. | Prio | Evidencia | Resumen |
|---|---|---|---|---|
| **CLAUDE-001** | HIGH | **P0** | `REPRODUCED` | **La ejecución de producción de mañana (2026-09-23 12:00) abortará antes de liquidar y no habrá picks**: la guarda de árbol limpio de `DIARIO_COMPLETO.bat` encuentra 6 ficheros de código sin commit (la remediación de esta mañana) |
| **CLAUDE-002** | HIGH | P1 | `REPRODUCED` | Los escritores de los registros con estado (`prediction_gate`, `degradation`) tratan un registro **ilegible** como **vacío**: pierden pestillos y tests de entrada gastados, y el gate **falla abierto** hacia stake real |
| **CLAUDE-003** | MEDIUM | P1 | `STATICALLY_VERIFIED` | El `AUD-001` de esta mañana contradice el pre-registro sellado del 2026-09-04: hasta 50 cortes **es la tolerancia pre-registrada**, no un incumplimiento. La remediación ordena en el log re-pre-registrar dentro de esa banda |
| **CLAUDE-004** | MEDIUM | P1 | `REPRODUCED` | `.claude/skills/full-audit/` revertida hoy, sin commit, a la versión del 2026-09-03: 3 pruebas de contrato en rojo y la skill desconectada del contrato canónico |

**Conclusión.** Hay un P0 con plazo de **~15 horas** que se resuelve con un commit selectivo (sin la reversión de CLAUDE-004), con el aviso de que la remediación de esta mañana queda así verificada **sólo por esta ronda**, que no es ciega (§0). CLAUDE-002 no tiene efecto hoy, porque ningún corte ha gastado todavía su test de entrada. Se vuelve alcanzable en cuanto `mlb|h2h` o `mlb|spreads` crucen `n ≥ 300`, previsiblemente hacia el **2026-09-25/26** (§7).

**Limitaciones.** No hubo auditor independiente ni revisión de Codex. No se ejecutó ninguna llamada a proveedores. No se cargaron datasets completos. La suite `slow` no se ejecutó en esta ronda (sí en la de esta mañana, sobre `HEAD`).

## 2. Inventario

| Elemento | Medida |
|---|---|
| Paquete | `src/sqp`: 106 módulos, 20.326 líneas; Python 3.14.4 en producción, CI 3.11–3.14 |
| Pruebas | 151 ficheros `tests/*.py`; subconjunto `not slow` = 2052 pruebas (225 `slow` deseleccionadas) |
| Scripts | 71 ficheros en `scripts/` |
| Orquestación | 10 BAT en la raíz; `DIARIO_COMPLETO.bat` = guarda de árbol → `SETTLE_ALL` → `RUN_DIARIO_ALL` → lista/tipster/derivados → salud |
| Programación | 5 tareas `SQP_*_Cdev` (4 en S4U, `Dashboard` interactiva) |
| Configuración | `configs/default.yaml` (+ `venues`, `leagues/*`), `.env` (no leído, denegado por política), `Settings.load()` |
| Dependencias | `pyproject.toml` + `requirements.lock` |
| Persistencia | CSV/JSON/joblib bajo `data/` con escritura atómica (`storage/atomic.py`) y bloqueo (`storage/lock.py`) |
| Proveedores | The Odds API, ESPN, MLB StatsAPI, Open-Meteo (deshabilitado) |
| Sistema de agentes | `.claude/`: 34 skills, agentes, hooks (7 + gate `Stop` del plugin Codex), `automation/`, memoria |
| CI | `.github/workflows/ci.yml` |

**Estado del árbol al inicio (preexistente, no tocado).** Código que ejecuta producción y está sucio: `scripts/validate_claude_model_routing.py`, `src/sqp/pipeline/{cleanup,team_totals_capture}.py`, `src/sqp/risk/{bankroll,prediction_gate}.py`, `src/sqp/storage/atomic.py`. Además: 6 tests, `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh`, 4 ficheros de `.claude/skills/full-audit/`, `CLAUDE.md`, routing de modelo, memoria y entregables de `audit/latest/`. Sin seguimiento: `audit/audit-2026-09-18/`, `audit/audit-2026-09-22/` y `Obsidian/Bitácora/2026-09-22.md`.

## 3. Matriz de cobertura

«r22» = ronda `audit-2026-09-22` de esta mañana. Donde el estado se apoya en ella, se indica.

| Área | Prio | Estado | Componentes | Método | Validación / **estado del control** | Limitaciones |
|---|---|---|---|---|---|---|
| Diff sin commit (remediación r22) | P0 | REVISADA | 6 módulos, hook, `settings.json`, 6 tests | Lectura línea a línea del diff + callers + suite | Los 8 IDs revalidados (§8). 1 premisa errónea → CLAUDE-003 | — |
| Guarda de árbol / operación diaria | P0 | REVISADA | `DIARIO_COMPLETO.bat:39-74,296-308`, tarea `SQP_Diario_Completo_Cdev` | Lectura + **reproducción del comando exacto de la guarda** + acción de la tarea | `git status --porcelain -- src scripts configs *.bat` → **6 líneas** → CLAUDE-001 | — |
| Gate de predicción | P0 | REVISADA | `risk/prediction_gate.py` (decisión, pestillo, test único, lector) | Lectura + reproducción en memoria + estado vivo | Estado 2026-09-22T15:15Z: 49 cortes, 0 `allowed`, mayor `n` = 270/300 (`mlb|h2h`, `mlb|spreads`) → CLAUDE-002, CLAUDE-003 | — |
| Monitor de degradación | P0 | REVISADA_PARCIALMENTE | `risk/degradation.py:173-264` | Lectura del escritor | Mismo patrón que el gate → CLAUDE-002 (manifestación secundaria) | No reproducido dinámicamente; conclusión estática |
| Banca / ROI realizado | P0 | REVISADA | `risk/bankroll.py:333-362`, `settlement/settle.py:128-140` | Lectura + suite | Cambio de r22 equivalente en comportamiento (push/void con `pnl 0`) | — |
| Liquidación de derivados | P1 | REVISADA | `pipeline/team_totals_capture.py:368-440` | Lectura | Fecha en hora del Este; doubleheader sin graduar; una captura por selección | — |
| Captura de derivados (presupuesto, cobertura) | P1 | REVISADA | `team_totals_capture.py:209-358`, `DIARIO_COMPLETO.bat:293` | Lectura + configuración efectiva | `regions=us,eu` → coste 2 por evento, coherente con `CREDITS_PER_EVENT` | Cuota real del proveedor: NO_VERIFICABLE (llamada externa) |
| Lógica / leakage / calibración / line shopping | P0 | REVISADA_PARCIALMENTE | `markets/`, `features/`, `calibration/`, `pipeline/probabilities.py` | **Sin relectura propia**: sin cambios desde `HEAD`, que r22 revisó a fondo | Se apoya en r22 (§3 de su informe) | Dependencia declarada de la ronda anterior |
| Pruebas | P1 | REVISADA | 2052 `not slow` | Ejecución completa aislada, sin caché | **3 failed, 2049 passed, 225 deselected, 570,24 s**. Los 3 fallos → CLAUDE-004 | `slow` no ejecutada en esta ronda |
| CI/CD | P1 | REVISADA | `ci.yml` | **Estado del control** | `gh run list`: último run `35426317559` **success** sobre `9fa276a` (2026-09-19). El diff sin commit **no ha pasado por CI** | — |
| Tareas programadas | P1 | REVISADA | 5 `SQP_*_Cdev` | `Get-ScheduledTaskInfo` (2026-09-22 ~20:55) | `Diario` rc 0 (12:00), `Capture_Close` rc 0 (20:30), `Backfill` rc 0, `Validate_OOS` rc 0 (17/09). `Dashboard` rc 267014 = `SCHED_S_TASK_TERMINATED` (interactiva, terminada; no es fallo del pipeline). Historial del Programador **deshabilitado** (KI-054, persistente) | — |
| Observabilidad | P1 | REVISADA | `data/output/pipeline_health.json` | Lectura del estado vivo | `WARN`, 0 errores, 1 aviso (historial del Programador). `served_pending_expired_total` = 150, **estable** respecto al 2026-09-13 | — |
| Hooks | P2 | REVISADA | `.claude/settings.json`, `run-tests-on-stop.sh`, `mark-tests-pending.sh` | Lectura + `command -v timeout` + centinelas | `timeout` = GNU coreutils 8.32. **Centinela `.tests-pending` puesto desde las 20:51**: la sesión de remediación cerró sin veredicto de la suite local | — |
| Skills / instrucciones / routing | P2 | REVISADA | `.claude/skills/`, `automation/`, validadores | `sync_agent_instructions.py --check` (rc 0), `validate_claude_model_routing.py` (rc 0), comparación contra el historial de Git | → CLAUDE-004 | Origen de la reversión: NO_VERIFICABLE |
| Seguridad y secretos | P1 | REVISADA | Árbol versionado | `git grep` de literales tipo clave (valores redactados) | Sólo fixtures sintéticos en `tests/test_audit_hooks.py`. `.env` denegado por política (control **comprobado en vivo**) | — |
| Salidas de apuestas | P1 | REVISADA | `src/`, `scripts/`, BAT | Búsqueda de promesas de beneficio | Sólo avisos de «no garantiza»; ninguna promesa | — |
| Dependencias | P1 | REVISADA_PARCIALMENTE | `pyproject.toml`, `requirements.lock` | Sin cambios desde r22 | r22: `pip-audit` rc 0 | No re-ejecutado (sin cambios de dependencias) |
| Integraciones externas | P1 | REVISADA_PARCIALMENTE | `providers/` | Sin cambios desde `HEAD` | Se apoya en r22 | Llamadas reales prohibidas |
| Datos y persistencia | P1 | REVISADA_PARCIALMENTE | `storage/`, `cleanup.py` | Lectura del diff; agregados del estado vivo | Purga de `.team_totals_credits_*` por `mtime` no alcanza el mes corriente | Datasets completos excluidos por regla |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | Suite | Medida | Suite `not slow` 570 s aislada frente al presupuesto del hook (1080 s) | Run diario no perfilado |
| Limpieza y racionalización | P2 | REVISADA | Raíz, `.codex-tmp/`, `audit/` | Historial Git + consumidores | 1 candidato (CLN-001), 1 descartado (`OPTIMIZATION.diff`) | Contenido de subdirectorios de `.codex-tmp/` con ACL denegada: NO_VERIFICABLE |
| Documentación | P2 | REVISADA_PARCIALMENTE | `IMPLEMENTACION.md`, pre-registros | Contraste puntual | El pre-registro del gate contradice el texto de la remediación r22 → CLAUDE-003 | README no verificado comando a comando |
| Código generado / vendorizado | P3 | NO_APLICABLE | — | — | No hay | — |
| Infraestructura declarativa | P3 | NO_APLICABLE | `Dockerfile` | Lectura (r22) | Entorno de demo declarado | — |

## 4. Hallazgos confirmados

### CLAUDE-001 — La ejecución diaria de mañana abortará por árbol sucio: día sin liquidación y sin picks

| Campo | Valor |
|---|---|
| Categoría | Operación / proceso de liberación |
| Severidad | **HIGH** |
| Confianza | HIGH |
| Evidencia | `REPRODUCED` (condición exacta de la guarda ejecutada) + `STATICALLY_VERIFIED` (rama de aborto y acción de la tarea) |
| Prioridad | **P0**: plazo hasta el **2026-09-23 12:00** hora local |
| Archivos | `DIARIO_COMPLETO.bat:60-74` (guarda), `:296-308` (`error_arbol`); tarea `SQP_Diario_Completo_Cdev` |

- **Activación:** la tarea diaria lanza `C:\dev\3\sports-quant-platform\DIARIO_COMPLETO.bat` a las 12:00 (verificado con `Get-ScheduledTask`).
- **Problema:** la guarda KI-036 ejecuta `git status --porcelain -- src scripts configs *.bat` y aborta con `exit /b 1` **antes de liquidar** si hay salida.
- **Evidencia concreta:** el mismo comando devuelve ahora 6 líneas: `scripts/validate_claude_model_routing.py`, `src/sqp/pipeline/cleanup.py`, `src/sqp/pipeline/team_totals_capture.py`, `src/sqp/risk/bankroll.py`, `src/sqp/risk/prediction_gate.py` y `src/sqp/storage/atomic.py`. Todos se modificaron a las 17:07–17:09 de hoy, **después** de la ejecución de las 12:00 (que terminó con rc 0 sobre `HEAD`). Por eso hoy no saltó.
- **Esperado:** que una remediación terminada llegue al árbol de producción commiteada, o no llegue.
- **Observado:** la ronda r22 cerró con la remediación **sin commit**, «pendiente de verificación independiente» (`audit/latest/STATUS.md` de r22).
- **Causa raíz:** dos controles correctos por separado que chocan. El contrato de auditoría deja la remediación pendiente de verificación independiente, y la guarda (orden del operador del 2026-09-06) impide ejecutar código sin commit. Nada de lo que dejó escrito la sesión anterior avisa del choque: ni `STATUS.md` ni el resumen de sesión.
- **Consecuencia:** un día sin liquidación ni picks, lo que va contra la regla fundamental de generar picks diarios. La guarda sí deja rastro (`run_status --fail --stage guard_arbol` y aviso en el log), así que el fallo sería visible, pero no se evitaría.
- **Controles existentes:** la guarda funciona tal como se diseñó; el escape `SQP_SKIP_TREE_GUARD=1` existe sólo para recuperación manual.
- **Corrección mínima:** antes de las 12:00 del 2026-09-23, dejar vacío `git status --porcelain -- src scripts configs *.bat` con un **commit selectivo** de los ficheros de la remediación r22 (los 6 de arriba, sus 6 tests, `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh` y los entregables de auditoría), **excluyendo** `.claude/skills/full-audit/` (CLAUDE-004). La alternativa es revertirlos, y exige la misma autorización. No usar `git add -A`.
- **Pruebas necesarias:** `ruff`, `mypy` y la suite `not slow` sobre el árbol resultante. Esta ronda ya las ejecutó sobre el árbol actual: 2049 passed y 3 failed, los 3 de CLAUDE-004. Tras el push, comprobar el CI.
- **Criterio de aceptación:** comando de la guarda sin salida; CI verde sobre el nuevo commit; a las 12:00 del 23/09, `diario_completo.log` sin «ABORTADO ANTES DE LIQUIDAR».
- **Limitaciones:** commitear es escritura en Git (y el push, externa): requiere autorización expresa del operador.

### CLAUDE-002 — Los registros con estado fallan abiertos: un registro ilegible borra pestillos y tests de entrada gastados

| Campo | Valor |
|---|---|
| Categoría | Integridad de estado / cuantitativo (pre-registro) / seguridad financiera |
| Severidad | **HIGH**: el impacto alcanzable es stake real en un corte que suspendió su único test o que tiene el pestillo armado. La rareza de la activación no rebaja la severidad (contrato de hallazgos) |
| Confianza | HIGH |
| Evidencia | `REPRODUCED` (gate, en memoria, con un registro ilegible en un directorio temporal) + `STATICALLY_VERIFIED` (degradación) |
| Prioridad | **P1**: hoy no hay estado que perder; lo habrá en cuanto un corte gaste su test (previsiblemente 2026-09-25/26) |
| Archivos | `src/sqp/risk/prediction_gate.py:456-458` (escritor), `:573-590` (lector compartido); `src/sqp/risk/degradation.py:173-188,257-264` |

- **Problema:** `write_prediction_gate` obtiene el estado previo con `load_prediction_gate`, que devuelve `{}` si el fichero existe pero no se puede leer (`OSError`, JSON corrupto, raíz no objeto). Para el **consumidor** `{}` es default-deny, y es correcto. Para el **escritor** significa «no había estado»: `_apply_latch` trata cada corte como nuevo, el que ya gastó su test lo **estrena otra vez** y un pestillo armado **desaparece**. El resultado se persiste encima.
- **Reproducción** (`scratchpad/repro_latch.py`, sin tocar `data/`): con dos cortes previos, `mlb|h2h` con test gastado y no superado y `mlb|totals` con pestillo armado, y criterios cumplidos hoy:

  | Corte | Registro legible | Registro ilegible |
  |---|---|---|
  | `mlb|h2h` | `allowed False`, `agotado_test_unico` | **`allowed True`**, test «estrenado» con fecha de hoy |
  | `mlb|totals` | `allowed False`, pestillo armado | **`allowed True`**, **pestillo desarmado** |

- **Esperado:** «no puedo leer el estado» ≠ «no hay estado». El escritor debería negarse a sobrescribir y dejar el registro previo intacto, con error ruidoso.
- **Causa raíz:** un único lector tolerante compartido por consumidor y escritor. La tolerancia es correcta para leer una autorización y errónea para derivar un estado nuevo.
- **Consecuencia:** se vulnera el pre-registro del 2026-09-04 («un solo test de entrada»; «no reentra sin liberación humana») y un corte puede salir del modo shadow hacia stake real (`pipeline/daily.py:650-657,960`; `prediction_gate.enabled: true` en `configs/default.yaml:273`). En degradación, una pausa pierde su histéresis y se reanuda si las métricas quedan entre los umbrales de pausa y de reanudación.
- **Activación realista:** con la escritura atómica y el `fsync`, la corrupción es improbable. La vía plausible es un `OSError` transitorio de Windows (violación de uso compartido) en el instante en que el run diario relee el registro, por ejemplo con otro lector abierto. Hoy no tiene efecto: 0 cortes con `entry_test_at` y 0 pestillos armados.
- **Controles existentes:** `prediction_gate_latch_log.csv` registra las transiciones de pestillo, pero **no se relee nunca** para reconstruir el estado y **no registra** el consumo de tests de entrada. No compensa.
- **Corrección mínima:** en los dos escritores, distinguir «ausente» (estado inicial legítimo) de «existe pero ilegible». En el segundo caso, lanzar una excepción explícita del paquete, no escribir y dejar que el run lo notifique. Los consumidores conservan su default-deny.
- **Pruebas necesarias:** registro corrupto → el escritor lanza y el fichero queda **byte a byte igual**; raíz no objeto → lo mismo; registro ausente → estado inicial; regresión de todos los tests actuales del pestillo. Idem en degradación.
- **Criterio de aceptación:** la reproducción de arriba deja `mlb|h2h` con `agotado_test_unico` y `mlb|totals` con el pestillo armado, o aborta sin escribir.
- **Limitaciones:** la vía de activación es inferida. Lo reproducido es la consecuencia una vez activado.

### CLAUDE-003 — La remediación de `AUD-001` (r22) contradice el pre-registro sellado y empuja una decisión de gate sobre una premisa falsa

| Campo | Valor |
|---|---|
| Categoría | Cuantitativo: fidelidad al pre-registro / trazabilidad de decisiones |
| Severidad | MEDIUM |
| Confianza | HIGH |
| Evidencia | `STATICALLY_VERIFIED` |
| Prioridad | **P1**: `audit/latest/STATUS.md` (r22) pide al operador decidir «con prisa» antes de que un corte cruce `n ≥ 300` (~2026-09-25/26) |
| Archivos | `src/sqp/risk/prediction_gate.py:463-489` (diff sin commit); `docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md:124-127`; `audit/audit-2026-09-22/{FINDINGS,STATUS}.md` |

- **Problema:** el pre-registro fija **de antemano** que el universo puede crecer: «si el número de cortes evaluados supera **50** (un 22 % sobre 41), este criterio se re-pre-registra antes…», y «No se re-divide α sobre la marcha». Con 49 cortes, el criterio se aplica **tal como se registró**. El `AUD-001` de r22 citaba esas mismas líneas (`:115-125`) y aun así concluyó «el criterio sigue incumplido». La auditoría del 2026-09-18 (OBS-1) lo había clasificado correctamente: «dentro del +22 % aceptado».
- **Observado en el diff:** el aviso salta ahora con `> K` (41) y dice «RE-PRE-REGISTRAR el criterio antes de que un corte nuevo alcance n>=300». Es justo la acción que el pre-registro reserva para `> 50`. El comentario de `:469-471` afirma que «entre 42 y 50 cortes el criterio YA esta incumplido».
- **Lo que sí es correcto y debe conservarse:** la aritmética (`49 × 0,05/41 = 0,0598`) y la publicación de `fwer_bound` en el registro, que es trazabilidad útil.
- **Consecuencia:** a diario un aviso que contradice un documento sellado, y una recomendación al operador de cambiar `K`/`alpha` (clase de escalación de `CLAUDE.md`) basada en una premisa falsa, días antes del primer test de entrada. Re-pre-registrar ahora, con datos ya acumulados, reabriría el riesgo que el pre-registro quería cerrar («volvería el umbral dependiente del calendario»).
- **Corrección mínima:** mantener `fwer_bound`. A partir de `> K`, emitir un mensaje **informativo** («cota de familia X; dentro de la tolerancia pre-registrada de 50 cortes»). La orden «RE-PRE-REGISTRAR» sólo con `> PREDICTION_GATE_K_REPREGISTRO`, como estaba. Corregir el comentario. La corrección de `STATUS`/`FINDINGS` de r22 corresponde a su fase de verificación.
- **Pruebas necesarias:** 49 cortes → sin texto «RE-PRE-REGISTRAR» y con `fwer_bound`; 51 cortes → `log.error` con el texto. Ningún veredicto cambia.
- **Criterio de aceptación:** el código y sus comentarios no afirman incumplimiento en la banda 42–50, y la prueba lo fija.
- **Limitaciones:** si el operador **quiere** endurecer el criterio, es una decisión legítima, pero es un cambio del pre-registro que se registra como tal, no la corrección de un defecto.

### CLAUDE-004 — La skill `full-audit` se revirtió hoy, sin commit, a su versión del 2026-09-03

| Campo | Valor |
|---|---|
| Categoría | Sistema de skills e instrucciones / pruebas de contrato |
| Severidad | MEDIUM |
| Confianza | HIGH |
| Evidencia | `REPRODUCED` (3 pruebas en rojo) + `STATICALLY_VERIFIED` (identidad byte a byte con `8952755`) |
| Prioridad | P1: bloquea un commit limpio (CLAUDE-001) y pondría el CI en rojo |
| Archivos | `.claude/skills/full-audit/SKILL.md` y `references/{evidence-findings,reporting,validation-remediation}.md` |

- **Evidencia concreta:** el `SKILL.md` de trabajo coincide exactamente con `git show 8952755:` (2026-09-03), con `mtime` de ese día y un BOM añadido. El árbol estaba limpio a las 13:00Z (manifest r22), así que la reversión ocurrió **hoy**. Deshace `f93bdc1` (2026-09-17, enlace al contrato canónico `audit-workflow.md`) y `56edbcd` (2026-09-18, bloque `## Common guardrails` y cierre por `/verification-gate`).
- **Pruebas en rojo:** `test_agent_instruction_sync.py::test_guardrails_remain_self_contained_in_each_general_loop` (`assert 6 == 7`), `test_claude_system_contract.py::test_all_general_loops_finish_through_verification_gate` (`['full-audit'] == []`) y `::test_general_skills_share_an_identical_guardrail_block`.
- **Consecuencia:** las auditorías lanzadas con `/full-audit` siguen un procedimiento superado, sin rondas, sin preservación y sin taxonomía canónica (esta misma ronda lo sufrió, §0). Si entra en un commit, el CI se pone en rojo. La sesión de la tarde lo detectó y lo dejó anotado sin tocarlo, correctamente.
- **Causa raíz:** NO_VERIFICABLE. No hay copia de usuario en `~/.claude/skills/` que lo explique; parece la restauración de una copia antigua que conservó las fechas.
- **Corrección mínima:** restaurar los cuatro ficheros desde `HEAD`. Es **destructivo para cambios sin commit**: antes, guardar una copia fuera del árbol y confirmar con el operador que no hay nada en ellos que quiera conservar.
- **Criterio de aceptación:** las 3 pruebas en verde y `git status` sin `.claude/skills/full-audit/`.

## 5. Hallazgos inferidos

Ninguno con entidad propia. La vía de activación de CLAUDE-002 es inferida y está declarada dentro del hallazgo.

## 6. No verificables

| Elemento | Qué falta | Evidencia necesaria |
|---|---|---|
| Origen de la reversión de CLAUDE-004 | Historial de operaciones sobre ficheros | Registro del operador o de la herramienta que restauró la copia |
| Contenido de los subdirectorios de `.codex-tmp/` con ACL denegada | Permisos de lectura | Inspección con la cuenta que los creó |
| Cuota real de The Odds API | Llamada externa (prohibida en diagnóstico) | Cabecera `x-requests-remaining` de un run real |
| Fecha exacta en que `mlb|h2h` cruzará `n = 300` | Resultados futuros | Ritmo medido: 231 (18/09) → 270 (22/09) ≈ 10/día, luego ~3 días. Estimación, no hecho |

## 7. Detecciones de herramientas pendientes

Ninguna. ruff y mypy no reportan nada.

## 8. Comparación histórica: revalidación de los IDs de la ronda r22

Revalidados contra el árbol actual: diff leído, callers revisados, suite ejecutada. **Aviso:** todos los arreglos siguen **sin commit**, así que «corregido» significa corregido **en el árbol de trabajo**. En `HEAD` y en el CI no están.

| ID (r22) | Estado revalidado | Evidencia |
|---|---|---|
| `AUD-007` | verificado-corregido | Presupuesto 1200 s en `settings.json`; autoacotado 1080 s con `rc 124` como rama propia; `timeout` = GNU coreutils 8.32. Suite medida en **570,24 s** aislada (53 % del autoacotado). Riesgo residual: con el centinela puesto, **cada** cierre de turno ejecuta la suite (~10 min) |
| `AUD-001` | **reabierto (premisa)** | La instrumentación (`fwer_bound`) es correcta. El diagnóstico y el aviso contradicen el pre-registro → CLAUDE-003 |
| `AUD-008` | persistente / no aplicable al repo | El MCP `codex` falla también en esta sesión (`CONNECTION_CLOSED`) |
| `AUD-002` | verificado-corregido | `coverage_baseline` excluye el día en curso; el aviso compara candidatos contra la mediana de capturados. Riesgo residual: el aviso **saltará casi a diario al acabar la temporada regular de la MLB** (postemporada con pocos partidos). Ruido esperable, no defecto |
| `AUD-003` | verificado-corregido | La guarda usa el coste previsto; `CREDITS_PER_EVENT = 2` coherente con `regions = us,eu` efectivo. Observación: la constante no se deriva de `regions` |
| `AUD-004` | verificado-corregido | `REPLACE_RETRY_SECONDS` como constante; test acotado contra ella; en verde |
| `AUD-005` | verificado-corregido | Mismo resultado con `push`/`void` con `pnl 0`; `realized_pnl` sigue siendo el total del ledger |
| `AUD-006` | verificado-corregido | La purga por `mtime` > 90 días no alcanza el mes corriente que consulta `spent_this_month` |

**Evidencia de Fase 5 de r22 incompleta (observación):** el `MANIFEST.json` de r22 declara en `status` «remediación completada», pero en `tests_final` dice «no hubo remediación». `VALIDATION.md` sólo recoge la validación del diagnóstico, y el centinela `.tests-pending` quedó puesto a las 20:51, sin veredicto. Esta ronda aporta la ejecución global que faltaba (§9).

IDs de r18 arrastrados: `AUD-004` (historial del Programador, KI-054) sigue **persistente**; `pipeline_health.json` lo avisa.

## 9. Descartes (falsos positivos y no-defectos)

| Candidato | Por qué se descarta |
|---|---|
| `OPTIMIZATION.diff` en la raíz: ya no aplica (`git apply --check` falla) | Instantánea histórica **deliberada**: la citan `BUILD_INFO.json` (manifiesto de hashes), `IMPLEMENTACION.md` y la ronda del 13/09 («snapshot, no se regenera»). CONSERVAR |
| Grading de `team_totals` por fecha UTC | Usa la fecha en `America/New_York` y no gradúa ante doubleheader. Correcto |
| `Dashboard` con rc 267014 | `SCHED_S_TASK_TERMINATED` en una tarea interactiva; no pertenece al pipeline de datos |
| Literales tipo clave en `tests/test_audit_hooks.py` | Fixtures sintéticos del propio detector de secretos |
| 150 picks servidos vencidos sin liquidar | Cifra idéntica a la del 2026-09-13: no crece. Ya registrado |
| Lenguaje de las salidas de apuestas | Ninguna promesa de beneficio; sólo avisos de «no garantiza» |

## 10. Validaciones ejecutadas

| Comando | Propósito | Resultado | Efectos |
|---|---|---|---|
| `git status --short`, `git diff`, `git rev-parse HEAD origin/main` | Estado del árbol | 34 M + 3 `??`; `HEAD == origin/main` | Ninguno |
| `gh run list --limit 5` | Estado del CI | 5 × `success`; último `35426317559` sobre `9fa276a` | Lectura remota |
| `Get-ScheduledTask SQP_* \| Get-ScheduledTaskInfo` | Estado de las tareas | Ver matriz | Ninguno |
| `ruff check src scripts tests --no-cache` | Lint | rc 0 | Ninguno |
| `mypy src` | Tipos | rc 0, 106 ficheros | Caché de mypy |
| `PYTHONPATH=src python -m pytest tests/ -q -p no:cacheprovider -m "not slow"` | Suite rápida sobre el árbol de producción | rc 1: **3 failed, 2049 passed, 225 deselected, 570,24 s** (pared 9 m 38 s). Los 3 son CLAUDE-004 → `PRE_EXISTING_FAILURE` (introducidos hoy antes de esta sesión, sin commit) | Temporales del sistema. Nota: el contrato pide `--basetemp=.codex-tmp/pytest`; no se pasó y se usó el temporal por defecto (fuera del árbol) |
| `python scripts/sync_agent_instructions.py --check` | Deriva de instrucciones | rc 0, `synchronized` | Ninguno |
| `python scripts/validate_claude_model_routing.py` | Candado de routing | rc 0, `OK` | Ninguno |
| `git status --porcelain -- src scripts configs '*.bat'` | Reproducir la guarda de CLAUDE-001 | 6 líneas | Ninguno |
| `PYTHONPATH=src python scratchpad/repro_latch.py` | Reproducir CLAUDE-002 | Tabla de §4 | Sólo un directorio temporal del sistema |
| `Settings.load()` (sólo `regions`, `mode`, `prediction_gate_enabled`) | Configuración efectiva sin secretos | `us,eu`, `demo` (los BAT pasan `--mode live`), `True` | Ninguno |
| Comparación byte a byte de `full-audit/SKILL.md` contra el historial | Datar la reversión | Igual a `8952755` | Ninguno |
| `sha256sum` de `audit/latest` frente a `audit/audit-2026-09-22` | Preservación de la ronda anterior | 11/11 idénticos | Ninguno |

## 11. Plan priorizado (requiere autorización expresa; nada se ha aplicado)

| Orden | ID | Acción | Archivos | Pruebas | Aceptación |
|---|---|---|---|---|---|
| 1 | CLAUDE-004 | Guardar una copia de los 4 ficheros revertidos fuera del árbol; confirmar con el operador; restaurar desde `HEAD` | `.claude/skills/full-audit/**` | Las 3 pruebas de contrato | Suite `not slow` sin fallos |
| 2 | CLAUDE-001 | Commit **selectivo** de la remediación r22 + push; **antes de las 12:00 del 23/09** | Los 6 de código, sus 6 tests, `settings.json`, hook, `audit/` | ruff, mypy, `not slow` y CI | Guarda sin salida; CI verde; run del 23/09 sin aborto |
| 3 | CLAUDE-003 | Rebajar el aviso de 42–50 cortes a informativo; «RE-PRE-REGISTRAR» sólo con > 50; corregir el comentario | `risk/prediction_gate.py`, `tests/test_prediction_gate.py` | 49 → sin orden; 51 → `error` | Ningún veredicto cambia |
| 4 | CLAUDE-002 | El escritor distingue ausente de ilegible; ilegible → excepción sin escribir | `risk/prediction_gate.py`, `risk/degradation.py`, `exceptions.py`, tests | Corrupto → fichero intacto; ausente → estado inicial | La reproducción no reabre tests ni pestillos |
| 5 | CLN-001 | Vaciar los subdirectorios accesibles de `.codex-tmp/` de rondas cerradas | `.codex-tmp/*` (ignorado por Git) | Ninguna (scratch) | `grep -r` sin `Permission denied` |

Los pasos 1 y 2 van **en ese orden**: si se commitea antes de restaurar la skill, o con `git add -A`, el CI se pone en rojo. Los pasos 3 y 4 tocan un gate: según `MODEL_ROUTING.md` son clase de escalación y conviene hacerlos en el escalón superior.

## 12. Limpieza y racionalización

| ID | Ruta | Categoría | Evidencia | Impacto | Reemplazo | Riesgo | Decisión | Validación |
|---|---|---|---|---|---|---|---|---|
| CLN-001 | `.codex-tmp/` (≈60 subdirectorios y 16 ficheros de rondas del 14 al 22/09) | GENERADO_RECONSTRUIBLE (los accesibles) / NO_VERIFICABLE (los de ACL denegada) | Ignorado en `.gitignore:85`; basetemps de pytest y scripts de rondas cerradas; `grep -r` sobre el árbol termina con rc 2 por los directorios denegados | Ruido en búsquedas; espacio | Ninguno (scratch) | Bajo | PROPONER_ELIMINACIÓN **sólo de los accesibles**; los denegados, CONSERVAR hasta verificarlos | `git status` sin cambios |
| — | `OPTIMIZATION.diff`, `BUILD_INFO.json` | CONSERVAR | Instantánea deliberada (§9) | — | — | — | CONSERVAR | — |

## 13. Riesgos pendientes

- **Plazo de CLAUDE-001:** si nadie actúa antes de las 12:00 del 23/09, el día se pierde. Es visible, pero no se evita.
- **Primer test de entrada del gate** (~25–26/09): se producirá con CLAUDE-002 abierto, salvo que se corrija antes, y con la duda de CLAUDE-003 planteada al operador.
- **Remediación r22 sin revisión de terceros:** esta ronda la verifica, pero no es ciega (§0) y Codex sigue caído (KI-056).
- **Historial del Programador deshabilitado** (KI-054): una tarea que no llegue a lanzarse no deja rastro.
- **Suite local a ~570–800 s:** con el centinela puesto, cada cierre de turno con ediciones de código cuesta ~10–13 min.
- Nada de esto dice nada sobre ventaja predictiva: las mediciones registradas siguen sin mostrar ventaja sobre el consenso de mercado, y el ROI realizado del ledger es negativo (−0,1526 según r22).
