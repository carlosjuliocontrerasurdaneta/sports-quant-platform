# Diagn?stico OpenAI ? pendiente de coordinaci?n de ronda

## Estado y alcance

**EJECUCI?N INCOMPLETA: diagn?stico parcial documentado; ronda, preservaci?n y consolidaci?n pendientes. No PASS.**

Petici?n: ejecutar `audits/prompts/auditoria-openai-astra.md`. Se interpreta como auditor?a integral del estado actual, no exclusivamente del diff local. Base: `65368c815530bf179c5780db78a9fe196996802d`, rama `main`. Se inventariaron 113 archivos en src, 83 en scripts, 181 tests versionados, 161 en .claude, 5 configs y un workflow; tambi?n BAT, Docker, dependencias, documentaci?n y datos ignorados. Estos conteos no implican revisi?n l?nea por l?nea.

Se preservaron los 14 archivos modificados y dos sin seguimiento que exist?an al comenzar. No se corrigi? c?digo, no se hicieron commits ni operaciones sobre datos productivos o servicios de pago. Las validaciones escribieron temporales y cach? MyPy en `.codex-tmp/`; Python no escribi? bytecode y los lotes que importan sqp desactivaron el handler de archivo antes de importar el c?digo evaluado.

`audit/latest/MANIFEST.json` corresponde a `audit-2026-09-23`, otra base y otro alcance temporal. Hay otra sesi?n CLI de Claude y procesos Python activos. No se pudo establecer que esa sesi?n no est? preparando/escribiendo una auditor?a. Se pregunt? al operador y la respuesta sigue pendiente. No se archiv? ni reemplaz? la ronda; estos documentos nuevos registran el diagn?stico y el bloqueo, NO son entregables incorporados a la ronda de septiembre. Los IDs siguientes son provisionales, hasta asignar una ronda nueva; no reemplazan los OPENAI-001/002 hist?ricos.

El contrato dice: ?Si el ID es ambiguo, hay un escritor activo o falla la preservaci?n, no sobrescribir: registrar bloqueo?. La existencia de procesos NO demuestra que est?n escribiendo audit/latest; la exclusividad queda NOT_VERIFIABLE. Falta resolver esa incertidumbre antes de reemplazar entregables.

Independencia: al leer el manifest para identificar ronda/base quedaron visibles sus conclusiones hist?ricas. Se declara esta exposici?n. No se leyeron los informes Claude ni FINDINGS/BACKLOG/STATUS en el diagn?stico principal. Los dos hallazgos se verificaron directamente; despu?s de fijar el primero se consultaron los encabezados y referencias del informe OpenAI anterior. No se revalidaron ?ntegramente todos los IDs hist?ricos.

## Resumen

Confirmados: CRITICAL 0, HIGH 0, MEDIUM 2, LOW 0. Prioridades: P0 0, P1 0, P2 2. Confianza HIGH en ambos. 345 pruebas aprobadas en cuatro lotes independientes; Ruff, MyPy (113 archivos), sync, routing y pip check satisfactorios. Suite completa no ejecutada. CI remoto rojo en otra base: causa contrastada en OPENAI-002.

## Matriz de cobertura

| ?rea | Criticidad | Estado | M?todo y evidencia | Limitaci?n |
|---|---|---|---|---|
| Arquitectura/entrypoints | P0 | REVISADA_PARCIALMENTE | Inventario; daily, roi_engine, referencias a consumidores y BAT | No lectura completa de los 83 scripts |
| Probabilidades/riesgo | P0 | REVISADA_PARCIALMENTE | probability helpers, Kelly, prediction_gate; tests odds/Kelly/gate | Sin simulaci?n econ?mica integral |
| Temporalidad/ML/calibraci?n | P0 | REVISADA_PARCIALMENTE | temporal.py, ml_train, engine, calibration/data, calibrator; tests temporales/calibraci?n | Sin retraining ni validaci?n emp?rica OOS de modelos actuales |
| Backtest ROI | P0 | REVISADA | Matcher, callers, c?lculo y tests; reproducci?n sint?tica OPENAI-001 | No cuantificaci?n sobre hist?rico real |
| Liquidaci?n | P0 | REVISADA_PARCIALMENTE | Identidad exacta, calendario MLB, settle; pruebas de fallback y ROI medias | No liquidaci?n productiva |
| Persistencia/concurrencia | P0 | REVISADA_PARCIALMENTE | atomic.py, lock.py, pruebas stores concurrentes | Sin prueba multiproceso exhaustiva de todos los escritores |
| Proveedores/frescura/cuota | P1 | REVISADA_PARCIALMENTE | Odds API, presupuesto, TTL y guard de cuota vencida; retries aislados | No llamadas a proveedores ni consumo de cuota |
| Configuraci?n/dependencias | P1 | REVISADA_PARCIALMENTE | pyproject, lock, config; pip check | Sin escaneo actual de vulnerabilidades; no se instalaron dependencias |
| Seguridad | P0 | REVISADA_PARCIALMENTE | Redacci?n de query API, YAML seguro, hashes de modelos, permisos CI, Docker sin root | Sin barrido de secretos en datos/logs ni pentest; no afirmar ausencia de secretos |
| CI | P1 | REVISADA | YAML, estado y log efectivo de run 38256027979; OPENAI-002 | Ese run eval?a d985ef8, no HEAD local; sin nueva ejecuci?n remota |
| Infraestructura/operaci?n | P1 | REVISADA_PARCIALMENTE | Inspecci?n DIARIO_COMPLETO y Docker; 5 tareas SQP con LastTaskResult=0 | No ejecutar BAT, construir Docker o cambiar tareas; rc=0 no prueba salida cuantitativa correcta |
| Monitorizaci?n | P1 | REVISADA_PARCIALMENTE | L?gica run_status, rutas de error BAT, alerta CI exitosa | Sin auditor?a completa del contenido de logs/health actuales |
| Skills/prompts/routing/hooks | P1 | REVISADA_PARCIALMENTE | Contrato can?nico/referencias, hook nuevo, targets; 77 tests, sync y routing | Sin medir duraci?n real de toda la suite r?pida del hook ni invocar agentes externos |
| Tests | P1 | REVISADA_PARCIALMENTE | Inspecci?n de aislamiento, 345 tests; dos huecos discriminantes descritos | No suite global ni coverage |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | Presupuestos/retries, exclusi?n heavy y dependencias directas declaradas | Sin benchmark representativo; no defectos por optimizaci?n hipot?tica |
| Datos productivos/modelos | P0 | EXCLUIDA | Solo c?digo y datos sint?ticos | No mutaci?n, migraci?n, entrenamiento ni acceso masivo a datos reales |
| Docs/hist?ricos/c?digo generado | P2/P3 | REVISADA_PARCIALMENTE | Inventario, sync y comparaci?n hist?rica limitada | Sin revalidaci?n completa de antiguos IDs; caches/vendor excluidos |
| Auth web/pagos/migraciones DB | P0 | NO_APLICABLE | No se identific? servidor web, pagos o base transaccional en el alcance inspeccionado | Los HTML son artefactos; esta disposici?n no certifica todos los scripts |

## OPENAI-001 ? El matcher del backtest consume cuotas de otro d?a

- Categor?a: integridad cuantitativa / identidad de eventos / backtesting.
- Severidad: MEDIUM. Confianza: HIGH. Evidencia: REPRODUCED. Prioridad: P2.
- Archivo/l?neas: `src/sqp/backtesting/roi_engine.py:179-198`, caller `:334`.
- Activaci?n: misma pareja local/visitante en d?as consecutivos; resultados de ambos partidos, pero cuotas capturadas ?nicamente del segundo; warmup/ventana permiten evaluar el primero.
- Problema: el resultado del primer d?a encuentra como ?nico candidato las cuotas del segundo dentro de ?1 d?a, las consume en `used` y deja sin emparejar el resultado correcto.
- Evidencia: resultados sint?ticos Boston/Tampa de 10 junio (0-5) y 11 junio (5-0), evento `odds-jun11` a las 23:00Z del 11. `_match_result` produce `game-jun10 -> odds-jun11`, `game-jun11 -> None`. `realized_roi_backtest`, con adaptador determinista (p local .6), RiskConfig por defecto, bankroll 1000 y cuota 2, produce `event_id=odds-jun11,date=2026-06-10,result=loss,pnl=-20,stake=20`.
- Esperado: asociar las cuotas al resultado del 11 (+20 para ese pick), o abstenerse si no se acredita identidad; nunca graduar con el resultado del 10.
- Observado: -20 y fecha del d?a anterior; se omite el resultado realmente correspondiente. Reproducci?n de Python terminada sin excepci?n; el comando compuesto acab? con rc=1 ?nicamente por una consulta gh posterior mal entrecomillada, reintentada correctamente aparte.
- Causa ra?z: asignaci?n greedy de resultados cronol?gicos contra candidatos de cuotas, sin reservar coincidencias exactas para otros resultados ni acreditar que la diferencia de d?a sea solo zona horaria.
- Consecuencia: etiquetas, PnL y ROI incorrectos; potencial contaminaci?n de evaluaci?n/investigaci?n. Consumidores verificados: backtest_roi, validate_oos, oos_pitcher_mlb, audit/patterns y varios scripts research. No se demostr? p?rdida de dinero real ni frecuencia hist?rica.
- Controles existentes: rechazo de empates entre m?ltiples cuotas equidistantes, used para no reutilizarlas, fechas deterministas. No protegen cuando falta el snapshot del primer partido. La liquidaci?n operativa utiliza identidad exacta/calendario en otra implementaci?n; no se atribuye all? este defecto.
- Correcci?n m?nima propuesta: resolver primero la identidad con fecha can?nica/proveedor (y calendario en MLB), evitando que un fallback de ?1 d?a consuma un evento con otro resultado exacto; abstenerse donde no se pueda demostrar identidad. No basta cambiar el orden de iteraci?n.
- Pruebas necesarias: dos resultados/d?as y un solo snapshot del segundo; fechas locales/UTC leg?timas; series consecutivas, doble jornada, aplazados y orden permutado. Comprobar identidad, signo del PnL y que el resultado exacto no se pierde.
- Aceptaci?n: ninguna cuota se liquida con el marcador del partido adyacente; coincidencias verificadas y m?tricas coherentes se conservan.
- Hist?rico: hallazgo nuevo respecto a los encabezados del informe OpenAI de septiembre consultados; comparaci?n hist?rica exhaustiva NOT_VERIFIABLE/no completada. Misma clase de problema que el fallback operativo ya tratado, pero implementaci?n y remediaci?n distintas.
- Limitaci?n: el adaptador fue sustituido por un doble determinista para aislar identidad; matcher, stake y settlement fueron reales. El efecto poblacional no se midi?.

## OPENAI-002 ? CI omite el tag requerido por dos tests

- Categor?a: CI / contrato de fixtures / pruebas dependientes del entorno.
- Severidad: MEDIUM. Confianza: HIGH. Evidencia: STATICALLY_VERIFIED. Prioridad: P2.
- Archivo/l?neas: `tests/research/test_measure_tier_a_gap.py:521-524` y `:1073`; checkout de `.github/workflows/ci.yml`; `scripts/research/measure_tier_a_gap.py:225-229`.
- Activaci?n: runner CI limpio con checkout superficial sin tags.
- Problema: un test exige leer la anotaci?n real `prereg-tier-a-t0`; el test de ?xito completo tambi?n espera su valor 0.075 sin aislar esa dependencia. CI no proporciona dicho tag.
- Evidencia independiente: run 38256027979, commit d985ef869766eca51a219d51fe1a64fe090a3a7b, job 114834217657: comando efectivo `git ... fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +d985ef8...:refs/remotes/origin/main`. Log: ambas pruebas fallan `None == 0.075`; 2 failed, 3004 passed, 83 skipped. El YAML actual mantiene checkout sin configuraci?n para obtener tags. C?digo actual lee `git tag -l --format=%(contents)` y exige el n?mero. El tag existe localmente y las dos pruebas pasan localmente en 12.40 s.
- Esperado: CI obtiene expl?citamente el tag/historial requerido o las pruebas unitarias usan fixtures aisladas, manteniendo una verificaci?n de integraci?n separada para el preregistro.
- Observado: todos los jobs test de ese run fallan en pytest; el escaneo de dependencias posterior queda skipped. El job de alerta s? termina success.
- Causa ra?z: dependencia de estado Git local no suministrado por el checkout CI.
- Consecuencia: puerta CI roja y escaneo de vulnerabilidades no ejecutado en ese run. No implica una vulnerabilidad confirmada ni un fallo de c?lculo productivo.
- Controles existentes: matriz Python/Windows y aviso ci-rojo detectan el fallo; entorno local con tag lo oculta. La marca heavy no lo excluye del CI completo.
- Correcci?n m?nima propuesta: proveer el tag anotado y objetos necesarios en ambos checkouts (fetch completo o espec?fico), y aislar la lectura en el test sint?tico de run_medir; no eliminar assertions ni saltarse la prueba para aparentar verde.
- Pruebas necesarias: runner limpio sin tags al inicio; verificar anotaci?n, ambos tests y ejecuci?n efectiva del escaneo de dependencias.
- Aceptaci?n: checkout reproducible, los dos tests pasan en CI y la auditor?a de dependencias llega a ejecutarse.
- Hist?rico/clasificaci?n: PRE_EXISTING_FAILURE respecto al working tree local; se observ? remotamente antes de esta auditor?a. No se atribuye al nuevo hook ni a los markers locales.
- Limitaciones: no se lanz? CI ni se clon? un checkout nuevo; los logs remotos y el c?digo se contrastaron directamente. CI de HEAD local no disponible.

## Validaciones y comandos

Cada lote pytest us? `-q -p no:cacheprovider --basetemp=.codex-tmp/pytest/<directorio-unico>` y PYTHONDONTWRITEBYTECODE=1.

1. Hook/routing: tests/test_stop_tests_hook.py + tests/test_claude_model_routing.py: primer intento 55 passed/22 setup errors porque faltaba el padre de basetemp, rc1, ENVIRONMENTAL_FAILURE. Creado solo el directorio temporal permitido y repetido en otra ruta: 77 passed, 13.19s, rc0.
2. N?cleo: test_roi_engine, test_temporal_cutoff, test_audit_temporal, test_calibrator, test_calibration_data, test_kelly, test_odds, test_prediction_gate, test_store_concurrency, test_atomic_write_bytes: 212 passed, 139.54s, rc0.
3. Integraci?n: test_odds_api_retry, test_live_gate_integration, settlement/test_candidate_history_fallback, test_realized_roi_consistency: 54 passed, 48.27s, rc0.
4. Dos tests exactos de OPENAI-002: 2 passed, 12.40s, rc0. No se repitieron suites sin una nueva raz?n.
5. `ruff check --no-cache src scripts tests`: All checks passed; `mypy --cache-dir=.codex-tmp/mypy-astra-20261015 src`: Success, 113 source files. Comando secuencial terminado rc0; mensajes individuales satisfactorios.
6. `python -B scripts/sync_agent_instructions.py --check`: synchronized, rc0. `python -B scripts/validate_claude_model_routing.py`: OK, rc0.
7. `python -B -m pip check`: No broken requirements found, rc0.
8. `gh run list --branch main --limit 1 --json headSha,status,conclusion,url,updatedAt`: failure/completed para d985ef8, actualizaci?n 2026-10-12T13:36:56Z. `gh run view` y logs de job contrastados. No atribuir esos resultados a HEAD 65368c8.
9. Get-ScheduledTask/Get-ScheduledTaskInfo: Backfill 12 octubre, Capture Close 15 octubre, Dashboard/Diario 14 octubre, Validate OOS 1 octubre: todos LastTaskResult=0. Solo consulta, no ejecuci?n.
10. Git status antes/despu?s de validar: mismos 14 modificados y 2 untracked; base no cambi?.

Incidencias de herramientas: dos arranques de shell sandbox fallaron `helper_unknown_error: setup refresh had errors`; se solicit? escalaci?n de lectura y ejecuci?n. El prompt no estaba en ra?z, se localiz? con rg. Un comando Python -c perdi? comillas en PowerShell (NameError) y una expresi?n jq perdi? comillas; ambos son fallos del arn?s, no del proyecto. `.dockerignore` no existe y el nombre inicialmente supuesto check_model_routing.py tampoco; se localiz? el validador real con rg. No son hallazgos por s? mismos.

## Descartes, pendientes y plan

DISMISSED: los 22 setup errors iniciales no son regresi?n; la repetici?n completa pasa. No se confirma que la liquidaci?n operativa sufra OPENAI-001: tiene controles distintos y sus pruebas seleccionadas pasan. La exclusi?n de dependencias transitivas en selecci?n heavy es expl?cita y CI conserva suite completa; no se reporta como bug por s? sola. No se infiere seguridad ni rentabilidad de tests verdes.

NOT_VERIFIABLE: exclusividad de audit/latest; CI de HEAD; vulnerabilidades actuales (pip check no es pip-audit); modelos/producci?n OOS, impactos sobre datos hist?ricos; duraci?n completa del hook; suite global; comparaci?n de todos los IDs hist?ricos. No hay hallazgos INFERRED promovidos a confirmados.

Pr?ximo paso de coordinaci?n: aclarar si la sesi?n Claude escribe auditor?a. Si no, preservar ?ntegramente audit/latest en audit/audit-2026-09-23, verificar inventario y SHA256, inicializar manifest de ronda nueva y trasladar este diagn?stico a entregables can?nicos preservando lo anterior. Si s?, identificar ronda/base/coordinador antes de integrarse. Con un ?nico auditor, consolidar solo despu?s de la coordinaci?n, declarando ausencia de segunda opini?n. No se han creado FINDINGS/BACKLOG ni alterado MANIFEST.

Remediaci?n propuesta (no autorizada por esta auditor?a): P2 OPENAI-001 corregir identidad y a?adir tests discriminantes; P2 OPENAI-002 hacer reproducible el checkout/fixtures y validar CI. No hay P0/P1 confirmados. Ninguna correcci?n se implement?.
