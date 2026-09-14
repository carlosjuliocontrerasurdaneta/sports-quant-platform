# Verificación de remediación — 2026-09-14

## 1. Resumen ejecutivo

**Decisión: APTO CON PENDIENTES.** Se verifican como corregidos AUD-001 y AUD-003–010. AUD-002 permanece reproducido y se clasifica **Reabierto** en la taxonomía de verificación: nunca se había declarado corregido. AUD-011–013 siguen **No verificables**. No se confirmó ninguna regresión atribuible a las correcciones examinadas. P0 abiertos: **0**; P1 abiertos: **0**.

Evidencia nueva: **336 pruebas aprobadas** de componentes afectados y consumidores, **6 controles adicionales aprobados**, Ruff satisfactorio, mypy satisfactorio sobre 101 archivos y wheel construido offline. Uno de los seis controles afirma deliberadamente la persistencia del defecto AUD-002; su resultado verde no significa que ese hallazgo esté corregido.

Este dictamen cubre la remediación revisada, no la ausencia absoluta de defectos ni una autorización para promover modelos, modificar stakes, reparar datos históricos o desplegar.

## 2. Alcance

- Protocolo leído íntegramente: `audits/prompts/verificar-remediacion.md`.
- Fuentes: `audits/consolidated/latest.md`, `audits/remediation/latest.md`, código actual, diff y pruebas. No se modificaron esas fuentes.
- Raíz: `C:/dev/3/sports-quant-platform`; rama `main`; HEAD `8503b7a63acdac017b50e1559a3044581b44cc9e`.
- Al finalizar, HEAD avanzó concurrentemente a `91bda90c69ed0304a992b1a6db79e39884461385` (`audits: auditoria independiente Claude/Opus 5 (ciclo audits/, paso 1)`). Esta verificación no ejecutó ese commit. El diff entre ambos HEAD incorpora informes/prompts y el registro de tarea, no código funcional. Los 636 contenidos vigilados siguieron idénticos: cambió su estado de seguimiento, no el código sometido a pruebas. Las correcciones funcionales continúan como cambios locales.
- Las correcciones son cambios locales sin commit. El SHA de HEAD por sí solo no identifica el código verificado; se guardó un manifiesto SHA256 de **636 archivos** en `.codex-tmp/verification-before.json`.
- Todo el working tree inicial se trató como preexistente: cambios en motores, runner, almacenamiento, caché, hooks/instalador, fixtures/tests, notas Obsidian y `.claude/automation/runtime/current-task.md`; también los archivos nuevos de pruebas, helper de secretos y `audits/`.
- Se leyeron `AGENTS.md`, `CLAUDE.md` y `Makefile`. `make check` no se utilizó porque su pytest no fija `--basetemp`; se ejecutaron controles equivalentes explícitos y con temporales aislados.
- Los únicos entregables del proyecto creados en esta fase son este informe y `audits/consolidated/status.md`. Scripts de comprobación, copias y artefactos de pruebas/build permanecen en scratch; pip usó además un temporal estándar durante el build autorizado.

No existían un informe de verificación ni `audits/consolidated/status.md` anteriores. No había una verificación previa que archivar.

## 3. Metodología

Para cada ID se contrastaron causa original, cambio real, criterio de aceptación, escenario de activación y consumidores. Se inspeccionaron las transacciones y el orden de locks, no solo la ausencia de fallos en una carrera. Para temporalidad se revisaron las series consumidas por `pergame.py` y `tuning.py`, además de los motores. Para seguridad se verificaron valores múltiples, comentarios, nombres de variables, prefijos, paths Bash y conservación del código de los hooks al reinstalar.

Se preparó una copia nueva del código actual en `.codex-tmp/verification-isolated`, incluyendo archivos Python nuevos sin seguimiento. La batería ampliada se ejecutó allí; los controles adicionales usan únicamente datos sintéticos y temporales. No se corrigieron código, tests, configuración, dependencias o migraciones durante esta fase.

La separación es metodológica: esta verificación ocurre en la misma conversación y por el mismo agente que realizó la remediación; **no se presenta como aprobación de un segundo autor o tercero externo**. Se comprobó evidencia actual y se añadieron controles independientes de los tests de remediación, sin tomar las afirmaciones de aquel informe como prueba suficiente.

## 4. Limitaciones

- Windows/Python 3.14.4. No se ejecutó la matriz multiintérprete de CI ni semántica de handles en POSIX.
- No se consultaron APIs deportivas reales, secretos, ledger operativo, resultados históricos completos ni modelos reales deserializados. No se cuantificó impacto histórico en ROI o calibración.
- No se repitieron las 2042 pruebas del repositorio indiscriminadamente: la validación global razonable de esta fase cubrió 336 pruebas de componentes/consumidores, controles adicionales, lint, tipos y build. La suite completa de la fase anterior es antecedente, no una ejecución nueva de esta verificación.
- El sandbox ya había impedido temporales en copias aisladas durante la sesión; las pruebas ampliadas y el build se ejecutaron con autorización y destinos de trabajo aislados. No hubo errores ambientales en los controles efectivos de esta fase. Git mantiene el aviso de acceso denegado al ignore global; el diff es inspeccionable.
- Los tres asuntos de investigación carecen de carga representativa o contratos de confianza suficientes. No se confunde esa ausencia con una refutación.
- El manifiesto controla entradas de código/documentación; no congela procesos operativos ni certifica que todo `data/` permanezca estático.

## 5. Hallazgos verificados

Los 13 IDs se revisaron. Diez tienen resolución concluyente en esta fase: nueve correcciones y un defecto persistente. Tres no alcanzan evidencia suficiente para cierre.

| Métrica | Cantidad |
|---|---:|
| IDs revisados | 13 |
| Verificaciones concluyentes | 10 |
| Verificado — Corregido | 9 |
| Verificado — Mitigado | 0 |
| Reabierto | 1 |
| No verificable | 3 |
| No aplicable | 0 |
| Regresiones confirmadas | 0 |
| P0 abiertos | 0 |
| P1 abiertos | 0 |

## 6. Corregidos

### AUD-001 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED y revisión estructural.**

Causa original: el adaptador observaba el resultado de cada fila inmediatamente, incluso dentro del día de otra predicción. En `engine.py:69–75,115` y `roi_engine.py:309–316,388`, los resultados se acumulan y solo entran al adaptador al pasar al siguiente día. `_prior_games` mantiene también el filtro de fechas estrictamente anteriores.

Aceptación comprobada:

- Cambio de marcador posterior e IDs inversos: la probabilidad anterior permanece invariante, con y sin hora, mediante `test_audit_temporal.py`.
- Reordenación de entrada: pruebas de paridad/determinismo y control adicional con entrada D+1, D, D+1.
- El control adicional instrumenta el adaptador: **cada** llamada a estimate —moneyline, spread y total— ve solo fechas estrictamente anteriores. Las dos predicciones de D+1 ven exactamente un resultado de D; las de D ven cero.
- Control positivo: un resultado del día anterior sí modifica la estimación del adaptador real.
- `pergame_pairs_from_results` consume probabilidades, outcomes y fechas de la misma salida; tuning calcula pérdidas con las series alineadas. Las pruebas de esos consumidores pasan.

El cambio del fixture de mercados mantiene las comprobaciones de marcadores/pushes y corrige fechas que antes ciclaban meses mientras el oráculo cortaba por posición. No se eliminó ninguna comprobación funcional para ocultar el fallo.

Límite: se verifica el corte diario conservador, no disponibilidad intradía no almacenada. El cierre de este ID no valida cifras históricas calculadas antes del fix.

### AUD-003 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED.**

Causa original: se recuperaban candidatos desplazados, pero faltaba la metadata de sus eventos. `_tennis_prediction_metadata` en `runner.py:497` une snapshots archivados dentro del horizonte canónico, filtra por ID y prioriza el snapshot vigente; `_settle_tennis`, desde `:592`, usa esa metadata para scores, fechas, expiración y enriquecimiento.

Las pruebas e2e ejecutadas recuperan candidatos cuyo evento no está en el vigente, también cuando no hay archivo vigente; comprueban win/loss, PnL, game_date, persistencia y segunda ejecución idempotente. El resto del directorio `tests/settlement` comprueba fallback histórico, salud de payloads, expiración y deduplicación. No se movió el fallo a una salida prematura por ausencia del vigente.

Aceptación cumplida. La precedencia es por ID y último snapshot conocido; no hay timestamp de generación exacto en predicciones históricas y no se inventa. La retención finita y archivos ilegibles siguen siendo límites documentados, no una garantía de recuperación ilimitada.

### AUD-004 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED.**

Causa original: ROI omitía coeficientes de penalización. `roi_engine.py:328,371–373` calcula dispersión por el helper productivo y pasa valor, coeficiente y umbral. `:269–270` rechaza movimiento o velocidad no cero cuando la interfaz no contiene trayectorias.

`test_audit_penalties.py` comprueba el efecto sobre stake mediante desviación estándar y fórmula de Kelly independiente; compara coeficientes cero/no cero y rechaza separadamente los dos términos sin datos. Las pruebas de ROI y paridad pasan. Los callers usan RiskConfig, cuyo contrato incluye los campos añadidos; no se observó rotura de una API admitida por el repositorio.

Aceptación cumplida: aplica lo representable y declara explícitamente lo no representable. No consulta información posterior para fabricar trayectoria. Continúan las exclusiones previas del benchmark documentadas en el módulo.

### AUD-005 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED y STATICALLY_VERIFIED.**

`revalidation.py:70–87` encierra lectura, reconciliación de columnas y reemplazo bajo `locked(path)`. Los dos callers de revalidación y `intraday_scan.py:168` usan el mismo helper y el mismo lock por archivo. El writer no toma luego el lock de candidatos: no se encontró inversión que forme un ciclo de locks.

El test concurrente fuerza un escritor con snapshot pendiente y otro append; sobreviven ambas filas y sus columnas. Un control adicional retiene el lock de `intraday_edge_log.csv`, fuerza timeout inmediato del segundo acceso y verifica `LockNoAdquiridoError` y bytes anteriores intactos. La exclusión se establece por estructura, no por una sola carrera que casualmente no ocurrió.

Aceptación cumplida: unión sin actualización perdida y timeout visible/seguro. No se garantiza éxito contra un titular que nunca libera; se conserva la política canónica del lock.

### AUD-006 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED en Windows.**

`atomic.py:21–37` añade reintento acotado al reemplazo; CSV y JSON lo utilizan conservando fsync, temporal único y cleanup. WinError 5/32/33 se reintenta hasta dos segundos; otros errores se propagan sin bucle. Una denegación permanente sigue propagándose sin destruir el archivo anterior.

Se ejecutaron los tests de lector transitorio/permanente, CSV/JSON y errores ajenos al sharing. El control adicional recorrió **daily._finalize completo**: un lector real provocó el primer PermissionError, se cerró, la publicación terminó, el nuevo CSV contenía `new`, el archivo guardado contenía `old` y no quedaron temporales. La liberación se hace después del fallo nativo para evitar un falso verde por temporizador.

Aceptación cumplida. El retraso adicional máximo de dos segundos ante denegación Windows permanente es conocido y no oculta el error. No se modificaron permisos ni coordinación de lectores externos.

### AUD-007 — Verificado — Corregido

**MEDIUM / P2; confianza HIGH; evidencia REPRODUCED.**

`odds_cache.py:80–85` incluye mkdir y write dentro del mismo bloque best-effort. Las pruebas existentes verifican FileExistsError/PermissionError sintéticos, payload, cuota y caché sana. El control adicional crea un **archivo real como padre de la caché**, ejecuta un cliente HTTP falso con respuesta 200 y comprueba payload íntegro, seis créditos registrados y el archivo padre intacto.

Aceptación cumplida: la respuesta válida no se pierde por persistencia auxiliar. Se preservan TTL, force-refresh y semántica de error del proveedor; no se consumieron créditos reales.

### AUD-008 — Verificado — Corregido

**MEDIUM / P3; confianza HIGH; evidencia STATICALLY_VERIFIED y REPRODUCED.**

La fixture `isolated_pipeline_outputs` redirige únicamente ROOT de salidas y los alias de lectura de los módulos afectados; los seis módulos la solicitan. `CONFIG_DIR` y el ROOT canónico de configuración siguen intactos. Se revisaron además los otros callers de `run_league` en pruebas live, inactividad y frescura: ya usan tmp_path explícito.

La batería ejecutó los seis módulos demo; el test de aislamiento comprobó destino temporal, configuración preservada y centinelas externos intactos. Dos procesos publicaron simultáneamente sin colisionar al usar raíces independientes. Las escrituras de `_finalize` y ServedStore reciben el ROOT redirigido. No se infiere aislamiento solo porque la suite se haya corrido en una copia: se comprobó el mecanismo de las fixtures.

Aceptación cumplida para los callers actuales revisados. El test de centinelas, por sí solo, sería insuficiente: aquí se combina con el rastreo de destinos y la ejecución de los callers. Los tests futuros deberán solicitar la fixture si usan el pipeline.

### AUD-009 — Verificado — Corregido

**LOW / P3; confianza HIGH; evidencia REPRODUCED.**

`check-secrets.sh` delega la extracción a `_secret_literals.py`; los placeholders se evalúan sobre cada valor capturado, no sobre la línea. Las pruebas ejecutan el hook real Git Bash sobre Python, BAT y YAML con/sin comentario `example`; permiten placeholders y referencias a entorno y verifican que no se imprima el literal.

El control adicional comprueba nombre de variable que contiene `example`, comentario `getenv`, dos valores en una línea —uno placeholder y otro literal—, YAML entre comillas y token con prefijo en mayúsculas. Todos los literales son detectados independientemente del texto ajeno al valor.

Aceptación cumplida y sin vía equivalente confirmada al bypass por comentario. Autenticación/autorización de aplicación no son aplicables a este detector local; no se ampliaron permisos ni se cambió la selección de destinos `_targets.py`. Se conserva su naturaleza heurística y comportamiento ante archivo ilegible/intérprete ausente; no es una auditoría histórica de secretos.

### AUD-010 — Verificado — Corregido

**LOW / P3; confianza HIGH; evidencia REPRODUCED y STATICALLY_VERIFIED.**

`instalar-candados.sh` ya no tiene heredocs que reescriban hooks. Exige los scripts versionados y `_targets.py`, habilita ejecución y muestra el matcher incluyendo Bash. El test ejecuta el instalador en un árbol temporal, verifica bytes idénticos de los tres hooks y comprueba que un destino Bash existente arma el marcador.

Se inspeccionó `crossreview-on-stop.sh`: se conserva la selección `--uncommitted`, `--base` o `--commit HEAD`, sin prompt posicional incompatible y con tratamiento de fallos. Al no reescribirlo, el instalador mantiene esos controles. No se ejecutó un revisor externo ni se tocaron settings reales.

Aceptación cumplida. El instalador depende del paquete completo con los hooks versionados; se trata de la fuente única explícita, no de un bootstrap autónomo de un solo archivo.

## 7. Mitigados

Ninguno. Los límites descritos en las nueve correcciones no dejan activo el escenario original dentro del contrato verificado. No se utiliza «mitigado» para cerrar las investigaciones sin evidencia.

## 8. Reabiertos

### AUD-002 — Reabierto (defecto persistente; remediación lo dejó bloqueado)

- **Severidad:** MEDIUM, puntuación original 58.75; **prioridad:** P2; **confianza:** HIGH; **evidencia:** REPRODUCED.
- **Archivo/código relevante:** `src/sqp/pipeline/daily.py:114–117`, descarte de recent si fecha/equipos aparecen en cualquiera de `_adjacent_days(day)` del histórico.
- **Activación:** histórico D con A/B 3–2; recientes D+1 con A/B 1–5 y D+2 con A/B 4–0; IDs h1, r2, r3.
- **Problema/esperado:** conservar tres partidos distintos.
- **Observado/evidencia:** el control nuevo `test_unresolved_merge_is_still_reproduced` obtiene solo `['h1', 'r3']`; el partido r2 sigue desapareciendo.
- **Causa raíz:** proximidad de día/equipos usada como identidad entre fuentes cuyos IDs no se reconcilian.
- **Consecuencia:** omisión de información reciente del entrenamiento/evidencia. No se cuantificó impacto agregado.
- **Fix mínimo propuesto:** establecer y persistir identidad/evento o un contrato explícito de tratamiento de ambigüedades; conservar juegos distintos y reconciliar duplicados reales. No se recomienda un umbral inventado ni identidad por marcador.
- **Tests necesarios:** D/D+1/D+2 conservados; mismo evento con drift UTC único; partidos distintos con el mismo marcador no fusionados; comportamiento explícito ante ambigüedad.
- **Aceptación:** incumplida. No es REG-XXX: no fue introducido ni agravado por las correcciones de esta fase, y nunca fue declarado resuelto.

## 9. No verificables

| ID | Evidencia actual | Condición faltante | Decisión |
|---|---|---|---|
| AUD-011 | `_league_odds` sigue dentro del lock de candidatos cuando hay evaluables; el lock aborta al timeout | Medición representativa de duración/contención que establezca el problema operativo | No verificable; no se atribuye corrupción ni se extrapola el comportamiento Windows a POSIX |
| AUD-012 | `_verify_hash` permite legado sin sidecar por contrato; las pruebas de modelos/compatibilidad pasan | Procedencia, permisos, actor fuera de la frontera de código y política de confianza aprobada | No verificable como vulnerabilidad; no apagar modelos ni crear sidecars para simular autenticación |
| AUD-013 | `fillSelect` y otros sinks interpolan; `build_model_map` produce mercados de conjunto cerrado | Ruta de entrada adversaria aceptada hasta DOM y contrato de confianza | No verificable; sin reproducción de ejecución ni descarte general de todos los sinks |

Se revisó la evidencia disponible de los tres, sin cerrar automáticamente por estar bloqueados. No hay severidad confirmada ni score nuevo para estas investigaciones. Su confianza como defectos sigue siendo insuficiente; no se reportan como regresiones.

## 10. No aplicables

Ninguno de los IDs existentes se reclasificó como no aplicable. Las mejoras descartadas por el consolidado no se convirtieron en nuevos defectos ni trabajo adicional.

## 11. Regresiones

**Regresiones confirmadas: 0.** No corresponde asignar IDs REG-XXX ni aplicar la fórmula de severidad a una sospecha no demostrada. La tabla se conserva explícita:

| ID | Hallazgo original | Regresión | Severidad | Evidencia | Acción recomendada |
|---|---|---|---|---|---|
| — | — | Ninguna confirmada en el alcance | — | Diff, consumidores, pruebas y controles descritos | Mantener la cobertura y atender los pendientes |

Los tres fallos de fixture informados durante remediación ya no se reproducen en el estado actual. No se modificaron tests durante esta verificación para obtener ese resultado.

## 12. Validación global

| Control nuevo | Resultado |
|---|---|
| Seis probes en `.codex-tmp/verification_probes.py` | 6 passed en 9.73 s; uno confirma AUD-002 persistente |
| Batería ampliada en snapshot actual | 336 passed en 137.81 s; sin skips ni errores |
| `ruff check --no-cache src scripts tests .claude/hooks/_secret_literals.py` | All checks passed |
| `mypy --cache-dir .codex-tmp/verification-mypy src` | Success: 101 source files |
| `git diff --check` | Sin errores; avisos CRLF/LF del árbol preexistente |
| Wheel sin red, dependencias ni instalación | Construido `sqp-1.0.0-py3-none-any.whl`; SHA256 `d0ab8674ac3a81d3f607d44407efff4d5e4ab95b1e8dd40a96c73053ace8fab0` |
| Preservación de entradas | 636 hashes iguales; ningún archivo fuente/test/config/informe previo modificado |

No se contabilizan como controles nuevos las ejecuciones de la fase de remediación. Los controles aquí ejecutados no tuvieron NEW_REGRESSION ni ENVIRONMENTAL_FAILURE. AUD-002 es un PRE_EXISTING_FAILURE reproducido por el probe; los asuntos sin evidencia se clasifican NOT_VERIFIABLE. Los errores de búsquedas de archivos inexistentes durante exploración no constituyen defectos de producto.

## 13. P0/P1 pendientes

**P0: 0. P1: 0.** No se encontró un bloqueo crítico ni una regresión grave atribuible a la remediación. AUD-002 permanece P2 y requiere trabajo planificado antes de declarar resuelta la integridad del entrenamiento.

## 14. Tabla maestra

PVI = Pendiente de validación independiente en el informe de remediación.

| ID | Severidad | Prioridad | Estado remediación | Estado verificación | Criterio aceptación | Regresión | Evidencia |
|---|---|---|---|---|---|---|---|
| AUD-001 | MEDIUM | P2 | PVI | Verificado — Corregido | Corte diario/invariancia y control previo cumplidos | No confirmada | REPRODUCED: pruebas + adaptador instrumentado |
| AUD-002 | MEDIUM | P2 | Bloqueado | Reabierto | Incumplido: r2 desaparece | No; preexistente | REPRODUCED: 3 entradas → 2 |
| AUD-003 | MEDIUM | P2 | PVI | Verificado — Corregido | Archivo ausente/ajeno, win/loss, persistencia/idempotencia cumplidos | No confirmada | REPRODUCED: settlement e2e |
| AUD-004 | MEDIUM | P2 | PVI | Verificado — Corregido | Penalización aplicada o rechazo explícito cumplidos | No confirmada | REPRODUCED: stake y configuración |
| AUD-005 | MEDIUM | P2 | PVI | Verificado — Corregido | Unión concurrente y timeout seguro cumplidos | No confirmada | REPRODUCED + estructura del lock |
| AUD-006 | MEDIUM | P2 | PVI | Verificado — Corregido | Publicación transitoria/error permanente acotado cumplidos | No confirmada | REPRODUCED: lectores reales y finalize |
| AUD-007 | MEDIUM | P2 | PVI | Verificado — Corregido | Payload y cuota ante mkdir fallido cumplidos | No confirmada | REPRODUCED: padre archivo real |
| AUD-008 | MEDIUM | P3 | PVI | Verificado — Corregido | Destinos temporales, centinelas y procesos cumplidos | No confirmada | STATICALLY_VERIFIED + pruebas |
| AUD-009 | LOW | P3 | PVI | Verificado — Corregido | Literales detectados sin filtrar comentarios cumplido | No confirmada | REPRODUCED: hook y variantes |
| AUD-010 | LOW | P3 | PVI | Verificado — Corregido | Fuente única, cobertura Bash/alcance preservados | No confirmada | REPRODUCED + hook conservado |
| AUD-011 | No asignada | P3 | Bloqueado | No verificable | Falta carga representativa | No confirmada | NOT_VERIFIABLE |
| AUD-012 | No asignada | P3 | Bloqueado | No verificable | Falta política/frontera de confianza | No confirmada | NOT_VERIFIABLE |
| AUD-013 | No asignada | P3 | Bloqueado | No verificable | Falta ruta adversaria al DOM | No confirmada | NOT_VERIFIABLE |

## 15. Recomendaciones de siguiente acción

1. Resolver el contrato de identidad/reconciliación de AUD-002 y remediarlo en una fase separada, con regresiones de fechas, duplicados y marcadores iguales. Esta verificación no autoriza una migración destructiva.
2. Planificar las mediciones y contratos faltantes para AUD-011–013; no cerrarlos por falta de reproducción.
3. Antes de utilizar benchmarks históricos para aprobar modelos, recalcularlos con el corte temporal corregido y resolver la omisión de resultados de AUD-002. No inferir rentabilidad de estos tests.
4. Mantener `audits/consolidated/latest.md` y `audits/remediation/latest.md` como históricos; consultar `audits/consolidated/status.md` para el estado posterior a esta verificación.

No se requiere otra corrección de código para cerrar los nueve IDs verificados dentro de los criterios y límites establecidos. Una aprobación organizacional por un autor distinto sigue siendo una decisión separada si el responsable la exige.

## 16. Anexo de comandos

Lecturas: protocolo, AGENTS/CLAUDE, informes, Makefile, diff y búsquedas `rg` acotadas. Se inspeccionaron `git status --short`, `git branch --show-current` y `git rev-parse HEAD`.

```text
python -B .codex-tmp/prepare_verification.py
python -B -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/verification-probe-tmp .codex-tmp/verification_probes.py
```

Desde `.codex-tmp/verification-isolated`, con autorización de ejecución y basetemp dentro del workspace:

```text
python -m pytest -q -p no:cacheprovider --basetemp=C:/dev/3/sports-quant-platform/.codex-tmp/verification-suite tests/test_audit_temporal.py tests/test_audit_penalties.py tests/test_audit_log_concurrency.py tests/test_audit_atomic_readers.py tests/test_audit_pipeline_isolation.py tests/test_audit_hooks.py tests/test_backtest_parity.py tests/test_backtest_markets.py tests/test_backtest_tuning.py tests/test_market_tuning.py tests/test_pergame_calibration.py tests/test_roi_engine.py tests/test_storage.py tests/test_pipeline_demo.py tests/test_calibration_live.py tests/test_accuracy_mode.py tests/test_team_scoring.py tests/test_line_movement.py tests/test_revalidation.py tests/test_odds_cache.py tests/test_hook_targets.py tests/settlement tests/test_settle_persist.py tests/test_intraday_scan.py tests/pipeline/test_intraday_scan.py tests/test_ml_models.py
python -m pip wheel --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir .codex-tmp/wheel .
```

Desde la raíz:

```text
python -m ruff check --no-cache src scripts tests .claude/hooks/_secret_literals.py
python -m mypy --cache-dir .codex-tmp/verification-mypy src
git diff --check
python -B .codex-tmp/check_verification_preservation.py
```
