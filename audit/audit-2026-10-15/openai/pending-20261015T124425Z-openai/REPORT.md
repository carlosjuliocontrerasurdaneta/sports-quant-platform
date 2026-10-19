# Diagnostico OpenAI - pendiente de coordinacion de ronda

## Estado y alcance

**EJECUCION INCOMPLETA: diagnostico parcial documentado; ronda, preservacion y consolidacion pendientes. No PASS.**

Peticion: ejecutar `audits/prompts/auditoria-openai-astra.md`. Se interpreta como auditoria integral del estado actual, no exclusivamente del diff local. Base: `65368c815530bf179c5780db78a9fe196996802d`, rama `main`. Se inventariaron 113 archivos en src, 83 en scripts, 181 tests versionados, 161 en .claude, 5 configs y un workflow; tambien BAT, Docker, dependencias, documentacion y datos ignorados. Estos conteos no implican revision linea por linea.

Se preservaron los 14 archivos modificados y dos sin seguimiento que existian al comenzar. No se corrigio codigo, no se hicieron commits ni operaciones sobre datos productivos o servicios de pago. Las validaciones escribieron temporales y cache MyPy en `.codex-tmp/`; Python no escribio bytecode y los lotes que importan sqp desactivaron el handler de archivo antes de importar el codigo evaluado.

`audit/latest/MANIFEST.json` corresponde a `audit-2026-09-23`, otra base y otro alcance temporal. Hay otra sesion CLI de Claude y procesos Python activos. No se pudo establecer que esa sesion no esta preparando/escribiendo una auditoria. Se pregunto al operador y la respuesta sigue pendiente. No se archivo ni reemplazo la ronda; estos documentos nuevos registran el diagnostico y el bloqueo, NO son entregables incorporados a la ronda de septiembre. Los IDs siguientes son provisionales, hasta asignar una ronda nueva; no reemplazan los OPENAI-001/002 historicos.

El contrato dice: Si el ID es ambiguo, hay un escritor activo o falla la preservacion, no sobrescribir: registrar bloqueo. La existencia de procesos NO demuestra que estan escribiendo audit/latest; la exclusividad queda NOT_VERIFIABLE. Falta resolver esa incertidumbre antes de reemplazar entregables.

Independencia: al leer el manifest para identificar ronda/base quedaron visibles sus conclusiones historicas. Se declara esta exposicion. No se leyeron los informes Claude ni FINDINGS/BACKLOG/STATUS en el diagnostico principal. Los dos hallazgos se verificaron directamente; despues de fijar el primero se consultaron los encabezados y referencias del informe OpenAI anterior. No se revalidaron integramente todos los IDs historicos.

## Resumen

Confirmados: CRITICAL 0, HIGH 0, MEDIUM 2, LOW 0. Prioridades: P0 0, P1 0, P2 2. Confianza HIGH en ambos. 345 pruebas aprobadas en cuatro lotes independientes; Ruff, MyPy (113 archivos), sync, routing y pip check satisfactorios. Suite completa no ejecutada. CI remoto rojo en otra base: causa contrastada en OPENAI-002.

## Matriz de cobertura

| area | Criticidad | Estado | Metodo y evidencia | Limitacion |
|---|---|---|---|---|
| Arquitectura/entrypoints | P0 | REVISADA_PARCIALMENTE | Inventario; daily, roi_engine, referencias a consumidores y BAT | No lectura completa de los 83 scripts |
| Probabilidades/riesgo | P0 | REVISADA_PARCIALMENTE | probability helpers, Kelly, prediction_gate; tests odds/Kelly/gate | Sin simulacion economica integral |
| Temporalidad/ML/calibracion | P0 | REVISADA_PARCIALMENTE | temporal.py, ml_train, engine, calibration/data, calibrator; tests temporales/calibracion | Sin retraining ni validacion empirica OOS de modelos actuales |
| Backtest ROI | P0 | REVISADA | Matcher, callers, calculo y tests; reproduccion sintetica OPENAI-001 | No cuantificacion sobre historico real |
| Liquidacion | P0 | REVISADA_PARCIALMENTE | Identidad exacta, calendario MLB, settle; pruebas de fallback y ROI medias | No liquidacion productiva |
| Persistencia/concurrencia | P0 | REVISADA_PARCIALMENTE | atomic.py, lock.py, pruebas stores concurrentes | Sin prueba multiproceso exhaustiva de todos los escritores |
| Proveedores/frescura/cuota | P1 | REVISADA_PARCIALMENTE | Odds API, presupuesto, TTL y guard de cuota vencida; retries aislados | No llamadas a proveedores ni consumo de cuota |
| Configuracion/dependencias | P1 | REVISADA_PARCIALMENTE | pyproject, lock, config; pip check | Sin escaneo actual de vulnerabilidades; no se instalaron dependencias |
| Seguridad | P0 | REVISADA_PARCIALMENTE | Redaccion de query API, YAML seguro, hashes de modelos, permisos CI, Docker sin root | Sin barrido de secretos en datos/logs ni pentest; no afirmar ausencia de secretos |
| CI | P1 | REVISADA | YAML, estado y log efectivo de run 38256027979; OPENAI-002 | Ese run evalua d985ef8, no HEAD local; sin nueva ejecucion remota |
| Infraestructura/operacion | P1 | REVISADA_PARCIALMENTE | Inspeccion DIARIO_COMPLETO y Docker; 5 tareas SQP con LastTaskResult=0 | No ejecutar BAT, construir Docker o cambiar tareas; rc=0 no prueba salida cuantitativa correcta |
| Monitorizacion | P1 | REVISADA_PARCIALMENTE | Logica run_status, rutas de error BAT, alerta CI exitosa | Sin auditoria completa del contenido de logs/health actuales |
| Skills/prompts/routing/hooks | P1 | REVISADA_PARCIALMENTE | Contrato canunico/referencias, hook nuevo, targets; 77 tests, sync y routing | Sin medir duracion real de toda la suite rapida del hook ni invocar agentes externos |
| Tests | P1 | REVISADA_PARCIALMENTE | Inspeccion de aislamiento, 345 tests; dos huecos discriminantes descritos | No suite global ni coverage |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | Presupuestos/retries, exclusion heavy y dependencias directas declaradas | Sin benchmark representativo; no defectos por optimizacion hipotetica |
| Datos productivos/modelos | P0 | EXCLUIDA | Solo codigo y datos sinteticos | No mutacion, migracion, entrenamiento ni acceso masivo a datos reales |
| Docs/historicos/codigo generado | P2/P3 | REVISADA_PARCIALMENTE | Inventario, sync y comparacion historica limitada | Sin revalidacion completa de antiguos IDs; caches/vendor excluidos |
| Auth web/pagos/migraciones DB | P0 | NO_APLICABLE | No se identifico servidor web, pagos o base transaccional en el alcance inspeccionado | Los HTML son artefactos; esta disposicion no certifica todos los scripts |

## OPENAI-001 - El matcher del backtest consume cuotas de otro dia

- Categoria: integridad cuantitativa / identidad de eventos / backtesting.
- Severidad: MEDIUM. Confianza: HIGH. Evidencia: REPRODUCED. Prioridad: P2.
- Archivo/lineas: `src/sqp/backtesting/roi_engine.py:179-198`, caller `:334`.
- Activacion: misma pareja local/visitante en dias consecutivos; resultados de ambos partidos, pero cuotas capturadas unicamente del segundo; warmup/ventana permiten evaluar el primero.
- Problema: el resultado del primer dia encuentra como unico candidato las cuotas del segundo dentro de +/-1 dia, las consume en `used` y deja sin emparejar el resultado correcto.
- Evidencia: resultados sinteticos Boston/Tampa de 10 junio (0-5) y 11 junio (5-0), evento `odds-jun11` a las 23:00Z del 11. `_match_result` produce `game-jun10 -> odds-jun11`, `game-jun11 -> None`. `realized_roi_backtest`, con adaptador determinista (p local .6), RiskConfig por defecto, bankroll 1000 y cuota 2, produce `event_id=odds-jun11,date=2026-06-10,result=loss,pnl=-20,stake=20`.
- Esperado: asociar las cuotas al resultado del 11 (+20 para ese pick), o abstenerse si no se acredita identidad; nunca graduar con el resultado del 10.
- Observado: -20 y fecha del dia anterior; se omite el resultado realmente correspondiente. Reproduccion de Python terminada sin excepcion; el comando compuesto acabo con rc=1 unicamente por una consulta gh posterior mal entrecomillada, reintentada correctamente aparte.
- Causa raiz: asignacion greedy de resultados cronologicos contra candidatos de cuotas, sin reservar coincidencias exactas para otros resultados ni acreditar que la diferencia de dia sea solo zona horaria.
- Consecuencia: etiquetas, PnL y ROI incorrectos; potencial contaminacion de evaluacion/investigacion. Consumidores verificados: backtest_roi, validate_oos, oos_pitcher_mlb, audit/patterns y varios scripts research. No se demostro perdida de dinero real ni frecuencia historica.
- Controles existentes: rechazo de empates entre multiples cuotas equidistantes, used para no reutilizarlas, fechas deterministas. No protegen cuando falta el snapshot del primer partido. La liquidacion operativa utiliza identidad exacta/calendario en otra implementacion; no se atribuye alli este defecto.
- Correccion minima propuesta: resolver primero la identidad con fecha canonica/proveedor (y calendario en MLB), evitando que un fallback de +/-1 dia consuma un evento con otro resultado exacto; abstenerse donde no se pueda demostrar identidad. No basta cambiar el orden de iteracion.
- Pruebas necesarias: dos resultados/dias y un solo snapshot del segundo; fechas locales/UTC legitimas; series consecutivas, doble jornada, aplazados y orden permutado. Comprobar identidad, signo del PnL y que el resultado exacto no se pierde.
- Aceptacion: ninguna cuota se liquida con el marcador del partido adyacente; coincidencias verificadas y metricas coherentes se conservan.
- Historico: hallazgo nuevo respecto a los encabezados del informe OpenAI de septiembre consultados; comparacion historica exhaustiva NOT_VERIFIABLE/no completada. Misma clase de problema que el fallback operativo ya tratado, pero implementacion y remediacion distintas.
- Limitacion: el adaptador fue sustituido por un doble determinista para aislar identidad; matcher, stake y settlement fueron reales. El efecto poblacional no se midio.

## OPENAI-002 - CI omite el tag requerido por dos tests

- Categoria: CI / contrato de fixtures / pruebas dependientes del entorno.
- Severidad: MEDIUM. Confianza: HIGH. Evidencia: STATICALLY_VERIFIED. Prioridad: P2.
- Archivo/lineas: `tests/research/test_measure_tier_a_gap.py:521-524` y `:1073`; checkout de `.github/workflows/ci.yml`; `scripts/research/measure_tier_a_gap.py:225-229`.
- Activacion: runner CI limpio con checkout superficial sin tags.
- Problema: un test exige leer la anotacion real `prereg-tier-a-t0`; el test de exito completo tambien espera su valor 0.075 sin aislar esa dependencia. CI no proporciona dicho tag.
- Evidencia independiente: run 38256027979, commit d985ef869766eca51a219d51fe1a64fe090a3a7b, job 114834217657: comando efectivo `git ... fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +d985ef8...:refs/remotes/origin/main`. Log: ambas pruebas fallan `None == 0.075`; 2 failed, 3004 passed, 83 skipped. El YAML actual mantiene checkout sin configuracion para obtener tags. Codigo actual lee `git tag -l --format=%(contents)` y exige el numero. El tag existe localmente y las dos pruebas pasan localmente en 12.40 s.
- Esperado: CI obtiene explicitamente el tag/historial requerido o las pruebas unitarias usan fixtures aisladas, manteniendo una verificacion de integracion separada para el preregistro.
- Observado: todos los jobs test de ese run fallan en pytest; el escaneo de dependencias posterior queda skipped. El job de alerta so termina success.
- Causa raiz: dependencia de estado Git local no suministrado por el checkout CI.
- Consecuencia: puerta CI roja y escaneo de vulnerabilidades no ejecutado en ese run. No implica una vulnerabilidad confirmada ni un fallo de calculo productivo.
- Controles existentes: matriz Python/Windows y aviso ci-rojo detectan el fallo; entorno local con tag lo oculta. La marca heavy no lo excluye del CI completo.
- Correccion minima propuesta: proveer el tag anotado y objetos necesarios en ambos checkouts (fetch completo o especifico), y aislar la lectura en el test sintetico de run_medir; no eliminar assertions ni saltarse la prueba para aparentar verde.
- Pruebas necesarias: runner limpio sin tags al inicio; verificar anotacion, ambos tests y ejecucion efectiva del escaneo de dependencias.
- Aceptacion: checkout reproducible, los dos tests pasan en CI y la auditoria de dependencias llega a ejecutarse.
- Historico/clasificacion: PRE_EXISTING_FAILURE respecto al working tree local; se observo remotamente antes de esta auditoria. No se atribuye al nuevo hook ni a los markers locales.
- Limitaciones: no se lanzo CI ni se clono un checkout nuevo; los logs remotos y el codigo se contrastaron directamente. CI de HEAD local no disponible.

## Validaciones y comandos

Cada lote pytest uso `-q -p no:cacheprovider --basetemp=.codex-tmp/pytest/<directorio-unico>` y PYTHONDONTWRITEBYTECODE=1.

1. Hook/routing: tests/test_stop_tests_hook.py + tests/test_claude_model_routing.py: primer intento 55 passed/22 setup errors porque faltaba el padre de basetemp, rc1, ENVIRONMENTAL_FAILURE. Creado solo el directorio temporal permitido y repetido en otra ruta: 77 passed, 13.19s, rc0.
2. Nucleo: test_roi_engine, test_temporal_cutoff, test_audit_temporal, test_calibrator, test_calibration_data, test_kelly, test_odds, test_prediction_gate, test_store_concurrency, test_atomic_write_bytes: 212 passed, 139.54s, rc0.
3. Integracion: test_odds_api_retry, test_live_gate_integration, settlement/test_candidate_history_fallback, test_realized_roi_consistency: 54 passed, 48.27s, rc0.
4. Dos tests exactos de OPENAI-002: 2 passed, 12.40s, rc0. No se repitieron suites sin una nueva razon.
5. `ruff check --no-cache src scripts tests`: All checks passed; `mypy --cache-dir=.codex-tmp/mypy-astra-20261015 src`: Success, 113 source files. Comando secuencial terminado rc0; mensajes individuales satisfactorios.
6. `python -B scripts/sync_agent_instructions.py --check`: synchronized, rc0. `python -B scripts/validate_claude_model_routing.py`: OK, rc0.
7. `python -B -m pip check`: No broken requirements found, rc0.
8. `gh run list --branch main --limit 1 --json headSha,status,conclusion,url,updatedAt`: failure/completed para d985ef8, actualizacion 2026-10-12T13:36:56Z. `gh run view` y logs de job contrastados. No atribuir esos resultados a HEAD 65368c8.
9. Get-ScheduledTask/Get-ScheduledTaskInfo: Backfill 12 octubre, Capture Close 15 octubre, Dashboard/Diario 14 octubre, Validate OOS 1 octubre: todos LastTaskResult=0. Solo consulta, no ejecucion.
10. Git status antes/despues de validar: mismos 14 modificados y 2 untracked; base no cambio.

Incidencias de herramientas: dos arranques de shell sandbox fallaron `helper_unknown_error: setup refresh had errors`; se solicito escalacion de lectura y ejecucion. El prompt no estaba en raiz, se localizo con rg. Un comando Python -c perdio comillas en PowerShell (NameError) y una expresion jq perdio comillas; ambos son fallos del arnes, no del proyecto. `.dockerignore` no existe y el nombre inicialmente supuesto check_model_routing.py tampoco; se localizo el validador real con rg. No son hallazgos por so mismos.

## Descartes, pendientes y plan

DISMISSED: los 22 setup errors iniciales no son regresion; la repeticion completa pasa. No se confirma que la liquidacion operativa sufra OPENAI-001: tiene controles distintos y sus pruebas seleccionadas pasan. La exclusion de dependencias transitivas en seleccion heavy es explicita y CI conserva suite completa; no se reporta como bug por so sola. No se infiere seguridad ni rentabilidad de tests verdes.

NOT_VERIFIABLE: exclusividad de audit/latest; CI de HEAD; vulnerabilidades actuales (pip check no es pip-audit); modelos/produccion OOS, impactos sobre datos historicos; duracion completa del hook; suite global; comparacion de todos los IDs historicos. No hay hallazgos INFERRED promovidos a confirmados.

Proximo paso de coordinacion: aclarar si la sesion Claude escribe auditoria. Si no, preservar integramente audit/latest en audit/audit-2026-09-23, verificar inventario y SHA256, inicializar manifest de ronda nueva y trasladar este diagnostico a entregables canunicos preservando lo anterior. Si so, identificar ronda/base/coordinador antes de integrarse. Con un unico auditor, consolidar solo despues de la coordinacion, declarando ausencia de segunda opinion. No se han creado FINDINGS/BACKLOG ni alterado MANIFEST.

Remediacion propuesta (no autorizada por esta auditoria): P2 OPENAI-001 corregir identidad y anadir tests discriminantes; P2 OPENAI-002 hacer reproducible el checkout/fixtures y validar CI. No hay P0/P1 confirmados. Ninguna correccion se implemento.

## Comprobacion final y concurrencia

El MANIFEST previo conserva SHA256 9d23b278a3b2595039761ec4594a3918358147ba30f0a1ec2076f17793cb01ac. Tras preparar el informe aparecieron cambios ajenos en .claude/memory/known-issues.md, .claude/memory/session-summaries.md y una nueva nota diaria de Obsidian del 2026-10-15. No fueron escritos por esta auditoria ni se leyeron sus conclusiones. Hay actividad concurrente en el workspace, aunque no demuestra un escritor de audit/latest. Las versiones previas de los dos entregables estan preservadas en history y se verificaron byte a byte. Texto normalizado a ASCII por la codificacion del pipe PowerShell.
