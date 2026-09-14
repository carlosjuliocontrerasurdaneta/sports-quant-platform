# Remediación controlada — 2026-09-14

## 1. Resumen

Fuente histórica: `audits/consolidated/latest.md`. Se procesaron sus 13 IDs, sin abrir una auditoría general. Nueve defectos tienen cambios implementados y validaciones dirigidas satisfactorias; **AUD-002 sigue confirmado y bloqueado** por insuficiencia de identidad entre fuentes. AUD-011–013 siguen como investigaciones bloqueadas, no como defectos confirmados.

Las correcciones quedan **pendientes de validación independiente mediante `verificar-remediacion.md`**. No se declara el proyecto completamente corregido. No se ejecutaron escrituras sobre datos de apuestas, parámetros operativos, modelos persistidos ni informes anteriores; tampoco se hicieron commits, push, despliegues o llamadas a proveedores deportivos reales. Se observaron dos cambios concurrentes de artefactos fuera de las raíces de prueba, detallados en la sección 12.

**Estado de este registro:** ejecución terminada. Suite global completada sobre snapshot aislado; sus tres fallos de fixture fueron corregidos y revalidados dentro de las 225 pruebas conjuntas del estado final. No se presenta aquella ejecución global como una única pasada completamente verde.

## 2. Estado inicial

- Raíz: `C:/dev/3/sports-quant-platform`; rama `main`; HEAD `8503b7a63acdac017b50e1559a3044581b44cc9e`.
- Working tree inicial: `.claude/automation/runtime/current-task.md` modificado (19 líneas preexistentes) y `audits/` sin seguimiento. Esos cambios no son producto de esta remediación.
- SHA256 inicial del consolidado: `8b88fb605d327f31d53b7a952ada0e37c8d8775b67aa9b582ee7e5d046122e2b`.
- SHA256 inicial de current-task: `5bb35247e23385c67d7fa2a739531f94404699582975d3059526f4e05bc94565`.
- Se leyeron `AGENTS.md`, `CLAUDE.md`, el prompt de remediación, el consolidado, `pyproject.toml`, `Makefile`, CI y las convenciones de Obsidian.
- Convenciones: cambios locales mínimos; Ruff sin reformateo general; mypy; pytest con `-p no:cacheprovider` y `--basetemp`; setuptools como backend de construcción. CI incluye Linux Python 3.11–3.14 y Windows 3.12. No se requieren dependencias nuevas ni migraciones de datos para los nueve cambios.
- Línea base disponible de la auditoría anterior, mismo HEAD: 2013 passed, 1 skipped en copia aislada; Ruff y mypy satisfactorios. No se atribuye esa ejecución a esta fase.
- Entorno Windows/Python 3.14.4. Git avisa que no puede leer el ignore global del usuario. Algunas ejecuciones desde copias aisladas no pudieron crear temporales por el sandbox: se clasificaron `ENVIRONMENTAL_FAILURE` y se repitieron con autorización.
- No existía un informe `audits/remediation/latest.md` anterior que archivar.

## 3. Hallazgos procesados

Lotes independientes por causa: AUD-001; AUD-002 (investigación de identidad, sin edición); AUD-003; AUD-004; AUD-005; AUD-006; AUD-007; AUD-008; AUD-009; AUD-010. Finalmente se revalidaron las condiciones faltantes de AUD-011–013. No se agruparon cambios de seguridad con los cuantitativos.

Cada lote usa los archivos enumerados abajo como alcance; su objetivo y aceptación son el comportamiento descrito. Los riesgos específicos y pruebas también se registran por ID. El análisis de los contratos precedió a cada cambio. Las regresiones se ejecutaron contra la versión corregida y, cuando corresponde, contra una copia cuyo código productivo se verificó idéntico a HEAD para comprobar que discriminan el defecto.

## 4. Hallazgos corregidos en código

### AUD-001 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED. `observe` actualizaba inmediatamente el adaptador, permitiendo que el resultado de otro encuentro del mismo día alterara una probabilidad anterior.
- **Causa raíz:** orden de filas confundido con disponibilidad del resultado final.
- **Archivos modificados:** `src/sqp/backtesting/engine.py`, `src/sqp/backtesting/roi_engine.py`, `tests/test_audit_temporal.py`, `tests/test_backtest_parity.py`, `tests/test_backtest_markets.py`.
- **Cambio:** retener resultados del día y observarlos únicamente al pasar al siguiente día. El motor de calibración ordena por fecha. El inicio del encuentro no se trata como hora de disponibilidad de su resultado.
- **Regresión:** nueva prueba parametrizada con/sin hora; IDs inversos; cambio del resultado posterior; probabilidades de moneyline y totales invariantes; control positivo con resultado del día anterior. Se corrigió el oráculo de paridad que observaba explícitamente el mismo día. El fixture de mercados ahora genera fechas consecutivas: antes ciclaba meses fuera de orden mientras sus asserts usaban `rows[60:]`. Se conservaron los asserts de marcador, pushes y sesgo.
- **Validaciones:** V01: 14 passed; V10: 13 passed. Las pruebas temporales fallan contra HEAD, incluida la divergencia 0.5632→0.5416 de ROI.
- **Aceptación:** cumplida para corte diario y controles ejecutados. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** no hay disponibilidad intradía acreditada; la política es conservadora por día. Las cifras históricas deben recalcularse antes de usarse para aprobar modelos; no se recalcularon ni publicaron cifras operativas.

### AUD-003 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED. Candidatos recuperados del archivo no encontraban jugadores/fecha si faltaba su evento en las predicciones vigentes.
- **Causa raíz:** recuperación de candidatos desacoplada de la metadata archivada.
- **Archivos modificados:** `src/sqp/settlement/runner.py`, `tests/settlement/test_settle_tennis_e2e.py`.
- **Cambio:** recuperar metadata por ID de evento de predicciones archivadas dentro del mismo horizonte de candidatos. El snapshot vigente tiene precedencia; en su ausencia se usa el archivo más reciente. Esa unión alimenta score mapping, expiración y enriquecimiento. Se elimina la salida prematura por ausencia del archivo vigente.
- **Regresión:** nueva, parametrizada con archivo vigente ajeno o sin archivo vigente; win/loss, PnL, game_date, persistencia y segunda llamada sin duplicados.
- **Validaciones:** V02: 17 passed, incluyendo superseded e idempotencia.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** las predicciones históricas no llevan `generated_at`; se ordenan por día de archivo, sin inventar correspondencia exacta de generación. Persisten la retención finita y el comportamiento best-effort ante archivos ilegibles. No se liquidaron apuestas reales como parte de la prueba.

### AUD-004 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED, condicionado a coeficientes no cero.
- **Causa raíz:** omisión de argumentos de penalización en ROI.
- **Archivos modificados:** `src/sqp/backtesting/roi_engine.py`, `tests/test_audit_penalties.py`.
- **Cambio:** calcular dispersión mediante el helper productivo y pasar dispersión, coeficiente y umbral al penalizador. Rechazar explícitamente movimiento/velocidad no cero: la API del benchmark recibe un snapshot por evento, sin trayectoria para calcularlos.
- **Regresión:** nueva; diferencia de stake contrastada con la fórmula independiente de Kelly y desviación estándar; coeficiente cero de control; rechazo de cada término sin trayectoria.
- **Validaciones:** V03: 33 passed. Contra HEAD, la reducción de stake es 0 en vez de aproximadamente 31.38 unidades sintéticas; tampoco se rechazan las configuraciones no representables.
- **Aceptación:** cumplida por aplicación de datos disponibles y rechazo explícito de los ausentes. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** el benchmark continúa excluyendo calibradores actuales, caps entre ligas y otras condiciones ya documentadas. No se modificaron coeficientes de producción.

### AUD-005 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED. Dos append podían leer el mismo estado y perder una escritura.
- **Causa raíz:** atomicidad del reemplazo sin exclusión de la transacción completa.
- **Archivos modificados:** `src/sqp/pipeline/revalidation.py`, `tests/test_audit_log_concurrency.py`.
- **Cambio:** lock propio del archivo de log alrededor de lectura, unión de esquema y escritura atómica; directorio creado previamente.
- **Regresión:** nueva; dos hilos, primer escritor detenido tras construir su snapshot y segundo append intercalado; sobreviven ambas filas y sus columnas distintas.
- **Validaciones:** V04: 1 passed; V07 incluye pruebas relacionadas de revalidación.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** se conserva el timeout y la semántica del lock canónico; no se garantiza éxito ante contención permanente.

### AUD-006 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED mediante lectores reales Windows.
- **Causa raíz:** `os.replace` fallaba inmediatamente frente a handles lectores sin permiso de borrado compartido.
- **Archivos modificados:** `src/sqp/storage/atomic.py`, `tests/test_audit_atomic_readers.py`.
- **Cambio:** reintentos de reemplazo durante un máximo de dos segundos para WinError 5/32/33, conservando el error al agotarse el plazo y la limpieza del temporal. Otros errores no se reintentan. La prueba real estableció que MoveFileEx devuelve WinError 5 en esta máquina, por lo que limitarse a 32/33 era insuficiente.
- **Regresión:** nueva; CSV y JSON, lector liberado únicamente después del primer fallo nativo de reemplazo, lector permanente, archivo previo intacto, temporales eliminados y denegación no Windows sin reintento. Se sustituyó el temporizador inicial: bajo carga podía liberar el lector antes del reemplazo y permitir que HEAD pasara sin reintentar.
- **Validaciones:** V05: 25 passed después de ajustar los códigos a la evidencia real; versión determinista: 5 passed. Contra HEAD, las dos variantes transitorias fallan con WinError 5, y los dos controles permanentes pasan.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** una denegación permanente WinError 5 tarda hasta dos segundos adicionales en propagarse. No se cambian permisos ni se garantiza publicar contra un lector que nunca cierra.

### AUD-007 — P2 / MEDIUM

- **Estado inicial:** Confirmado, STATICALLY_VERIFIED y reproducción controlada de fallo de mkdir.
- **Causa raíz:** creación del directorio fuera del bloque best-effort.
- **Archivos modificados:** `src/sqp/providers/odds_cache.py`, `tests/test_odds_cache.py`.
- **Cambio:** incluir `mkdir` en el mismo try que la escritura de caché.
- **Regresión:** nueva para FileExistsError y PermissionError; respuesta HTTP 200 conservada, una llamada y cuota registrada. El roundtrip de caché sana existente también pasa.
- **Validaciones:** V07 incluye los 12 tests de caché. El fake devuelve 3 créditos de consumo y 100 restantes; no se consumieron créditos reales.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** la caché sigue siendo auxiliar y best-effort; no se cambió su formato ni política TTL.

### AUD-008 — P3 / MEDIUM

- **Estado inicial:** Confirmado, STATICALLY_VERIFIED; seis módulos de pruebas invocaban demo con el ROOT productivo.
- **Causa raíz:** salidas globales sin aislamiento por prueba.
- **Archivos modificados:** `tests/conftest.py`, `tests/test_pipeline_demo.py`, `tests/test_calibration_live.py`, `tests/test_accuracy_mode.py`, `tests/test_team_scoring.py`, `tests/test_line_movement.py`, `tests/test_revalidation.py`, `tests/test_audit_pipeline_isolation.py`.
- **Cambio:** fixture explícito por módulo afectado, ROOT de salidas por tmp_path y ajuste de las lecturas de resultados en esos tests. `CONFIG_DIR` y el ROOT canónico de configuración permanecen intactos.
- **Regresión:** nueva; centinelas externos demo/live intactos, generación dentro del fixture y dos procesos publicando simultáneamente a raíces independientes.
- **Validaciones:** V07: 89 passed; V09: 2 passed.
- **Aceptación:** cumplida en los módulos identificados y las comprobaciones de aislamiento. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** futuras pruebas deben solicitar el fixture si llaman al pipeline; no se impone un monkeypatch indiscriminado a todos los módulos de la aplicación.

### AUD-009 — P3 / LOW

- **Estado inicial:** Confirmado, REPRODUCED con literales sintéticos.
- **Causa raíz:** filtro de ruido aplicado a toda la línea, incluidos comentarios.
- **Archivos modificados:** `.claude/hooks/check-secrets.sh`, `.claude/hooks/_secret_literals.py`, `tests/test_audit_hooks.py`.
- **Cambio:** extracción de valores por helper Python, placeholders evaluados solo sobre esos valores; conservación de detección por prefijos sin distinguir mayúsculas. La salida informa número de línea y omite el literal.
- **Regresión:** nueva; hook real Git Bash sobre Python/BAT/YAML con y sin comentario `example`; placeholders españoles/ingleses y referencias a entorno permitidos.
- **Validaciones:** V08: 43 passed junto a derivación de destinos.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** sigue siendo un detector heurístico local, no autenticación ni auditoría histórica de secretos.

### AUD-010 — P3 / LOW

- **Estado inicial:** Confirmado, STATICALLY_VERIFIED; heredocs de instalación sobrescribían controles recientes.
- **Causa raíz:** dos fuentes divergentes para los hooks.
- **Archivos modificados:** `instalar-candados.sh`, `tests/test_audit_hooks.py`.
- **Cambio:** usar exclusivamente hooks versionados del paquete; comprobar sus archivos y `_targets.py`, habilitar ejecución y mostrar cableado incluyendo Bash. Un paquete incompleto falla explícitamente. No se regeneran ni pisan hooks locales desde copias congeladas.
- **Regresión:** nueva; ejecutar instalador en árbol temporal, conservar bytes de los tres hooks y verificar que una escritura Bash arma el marcador. No se invoca Codex externo ni se modifica settings real.
- **Validaciones:** V08: 43 passed.
- **Aceptación:** cumplida. **Estado final:** Pendiente de validación independiente.
- **Riesgo residual:** el instalador requiere el paquete con sus hooks versionados; no es un bootstrap autónomo de un único archivo.

## 5. Hallazgos ya corregidos al inicio

Ninguno. No se atribuyeron fixes anteriores a esta sesión.

## 6. Hallazgos bloqueados

### AUD-002 — P2 / MEDIUM

- **Estado inicial:** Confirmado, REPRODUCED de nuevo: entradas h1/D, r2/D+1, r3/D+2 producen únicamente h1/r3.
- **Causa raíz:** descarte por proximidad de fecha/equipos sin identidad entre proveedores.
- **Archivos modificados:** ninguno para este ID.
- **Verificación:** `_merge_results` sigue usando `_adjacent_days`. `ResultsStore.COLUMNS` y `_LOAD_COLS` no preservan hora de inicio ni ID cruzado; MLB expone día oficial y gamePk mientras las filas recientes usan otro ID. El test UTC exige fusionar filas que, con los campos disponibles, también podrían representar dos partidos distintos con idéntico marcador.
- **Cambio/prueba de regresión:** no implementados por incertidumbre material. Reproducción conservada en `.codex-tmp/recheck_merge.py`; pruebas existentes revisadas en `tests/test_results_backfill.py`.
- **Aceptación:** NO cumplida. **Estado final:** Bloqueado.
- **Información necesaria:** identidad cruzada o contrato de reconciliación respaldado por proveedor y persistido en las filas; alternativamente decisión explícita para tratar eventos ambiguos. No se inventó una ventana de seis horas ni se usó igualdad de marcadores como identidad.
- **Riesgo residual:** continúa la pérdida de un resultado reciente en la frontera demostrada. Esto impide declarar cerrada toda la remediación cuantitativa.

### AUD-011 — P3 / investigación, sin severidad confirmada

- **Estado inicial:** Requiere información adicional, INFERRED. Lectura de cuotas bajo lock confirmada estáticamente; no se dispone de una carga representativa que reproduzca retención superior al timeout.
- **Causa raíz del supuesto defecto:** no establecida más allá de la duración potencial de la sección crítica.
- **Archivos/cambios:** ninguno. Se releyeron la sección crítica y el lock canónico. La rama de ruptura de lock vivo en Windows continúa refutada en el consolidado; no se extrapola a POSIX.
- **Regresión:** no procede inventar una carga ni un umbral operativo nuevo. Se conserva la cobertura de locks existente.
- **Aceptación:** no cumplida. **Estado final:** Bloqueado. Falta medición de retención/contención bajo carga representativa y autorización específica si requiere operación sobre servicios.
- **Riesgo residual:** posible timeout operativo no cuantificado; no corrupción confirmada.

### AUD-012 — P3 / investigación, sin severidad confirmada

- **Estado inicial:** Requiere información adicional, INFERRED. La carga legacy sin sidecar sigue siendo compatibilidad explícita, protegida por `test_un_artefacto_legado_sin_sidecar_sigue_cargando`.
- **Causa raíz del supuesto defecto:** frontera de confianza no establecida; un hash adyacente no autentica a quien puede modificar ambos archivos.
- **Archivos/cambios:** ninguno; no se reescriben sidecars ni se deshabilitan modelos sanos.
- **Regresión:** existente para legado y hashes, sin nuevo contrato de seguridad inventado.
- **Aceptación:** no cumplida. **Estado final:** Bloqueado. Faltan procedencia, permisos, actor adversario y política de admisión/migración aprobada.
- **Riesgo residual:** confianza local de artefactos no auditada como frontera de seguridad en esta fase.

### AUD-013 — P3 / investigación, sin severidad confirmada

- **Estado inicial:** Requiere información adicional, INFERRED. Se releyeron `fillSelect`, tags y el productor `build_model_map`; existen sinks sin escape y mercados productivos de conjunto cerrado.
- **Causa raíz del supuesto defecto:** ruta adversaria completa no acreditada, no basta ver interpolación.
- **Archivos/cambios:** ninguno. No se declara XSS reproducido ni se cambia una política de entrada sin contrato.
- **Regresión:** no añadida; requiere ruta productor→serialización→DOM y canario inocuo en navegador, no búsqueda de cadenas en HTML.
- **Aceptación:** no cumplida. **Estado final:** Bloqueado. Falta demostrar origen no confiable admitido y efecto en DOM, o contrato que descarte la ruta.
- **Riesgo residual:** interpolaciones observadas pendientes de análisis de confianza.

## 7. Hallazgos no aplicables

Ninguno de los 13 IDs se reclasificó como no aplicable. Los descartes del consolidado no se convirtieron en trabajo adicional.

## 8. Cambios realizados

Nueve correcciones de código/pruebas detalladas arriba y notas de Obsidian de esta sesión: `Obsidian/Bitácora/2026-09-14.md`, `Obsidian/Bitácora.md`, `Obsidian/Tareas.md` y `Obsidian/Errores y lecciones/Errores detectados y soluciones.md`. Sin migración, reparación del ledger, recalibración, cambios a configuración de riesgo ni modificaciones a CI. Se mantuvo el consolidado como fuente histórica. Scratch y copias de validación permanecen bajo `.codex-tmp/`; pip también utilizó su caché estándar durante el build autorizado.

## 9. Pruebas de regresión

Nuevas: `test_audit_temporal.py`, `test_audit_penalties.py`, `test_audit_log_concurrency.py`, `test_audit_atomic_readers.py`, `test_audit_pipeline_isolation.py`, `test_audit_hooks.py`, y casos adicionales en caché y settlement de tenis. Ajustadas: oráculo temporal y fechas del fixture de mercados, conservando los invariantes válidos. No se eliminaron tests para obtener verde.

La copia anterior usada para pruebas rojas verificó seis módulos productivos contra `git show HEAD:<ruta>` antes de ejecutarlas. Resultado: 17 failed y 4 passed esperados; tres fallos adicionales de la comprobación de hook corresponden a la nueva redacción de valores, no al bypass por comentario. Una repetición del test atómico reforzado produjo 2 failed y 2 passed esperados. Los errores de setup por permisos no se cuentan como detecciones de defecto.

## 10. Validaciones ejecutadas

| Ref | Alcance | Resultado |
|---|---|---|
| V01 | Temporal + paridad | 14 passed |
| V02 | Tenis e2e + superseded | 17 passed |
| V03 | Penalizadores + ROI + paridad | 33 passed |
| V04 | Append concurrente | 1 passed |
| V05 | Lectores Windows + storage | 25 passed |
| V07 | Seis módulos demo aislados + caché | 89 passed |
| V08 | Hooks reales + targets | 43 passed |
| V09 | Aislamiento/centinelas/procesos | 2 passed |
| V10 | Mercados backtest + calibración por partido | 13 passed |
| V11 | Ruff: src scripts tests y helper de secretos | All checks passed |
| V12 | mypy src | Success, 101 source files |
| V13 | git diff --check | Sin errores; avisos CRLF/LF |
| V14 | Suite global aislada | 2036 passed, 1 skipped, 3 failed en 1252.59 s; los 3 fallos son el fixture cronológico anterior y pasan en V17 |
| V15 | Regresiones contra HEAD anterior | 17 failed / 4 passed esperados; atomicidad determinista: 2 failed / 2 passed esperados |
| V16 | Wheel offline sin dependencias | Construido `sqp-1.0.0-py3-none-any.whl`, SHA256 `8d72b67defbb0e71dc939212f92d20e4c5dae585ad143a0fddf6154476a31b14` |
| V17 | Reejecución dirigida conjunta del estado final (21 archivos) | 225 passed en 88.15 s |

Las cifras de filas anteriores son ejecuciones solapadas; no se suman como tests únicos. La suite global arrancó antes de corregir las fechas de `test_backtest_markets.py`, reforzar el test atómico y añadir el test de aislamiento de procesos. Estos cambios posteriores, el ajuste de mayúsculas del detector y todos los componentes afectados se verificaron juntos en V17 sobre la raíz final. No se repitieron las pruebas de integración Git ya satisfactorias, ajenas a esos cambios. El skip global corresponde a `test_review_v2.py` para `severity`, enum cerrado que no admite el caso de texto hostil; es el skip conocido de la línea base. No se ejecutaron proveedores reales, instalación productiva de hooks, OOS con datos privados ni acciones Git remotas.

## 11. Fallos preexistentes y fallos durante la validación

- `ENVIRONMENTAL_FAILURE`: sandbox denegó temporales en la primera suite aislada y en la primera ejecución roja; también la carpeta del wheel. Se repitieron con autorización. La ejecución global inicial se interrumpió al diagnosticar los setup errors; no cuenta como revisión suficiente.
- Fallos de construcción de tests corregidos: caso sin hora inicialmente chocaba con el rechazo legítimo de dobleheader ambiguo; llamada `_get` con argumento posicional inválido; fixture de hook sin archivo tocado; ubicación de `pytestmark` causaba E402. No se atribuyen al código previo.
- `NEW_REGRESSION` de compatibilidad del fixture al integrar AUD-001: tres asserts de mercados usaban fechas desordenadas y una partición por posición. Se corrigieron las fechas del fixture; el código conserva el corte cronológico y las comprobaciones funcionales originales. Son exactamente los únicos tres fallos de V14 y pasan en V10/V17; no quedan fallos de validación atribuibles a esos cambios pendientes de resolver.
- El primer reintento de atomicidad contemplaba solo WinError 32/33: la prueba con lector real expuso WinError 5; corregido antes de cerrar el lote.
- No hay evidencia de otros tests preexistentes fallidos sobre el HEAD inicial. AUD-002 es un defecto preexistente confirmado aún abierto.

## 12. Riesgos residuales

Los cuatro bloqueos se detallan arriba. Las nueve correcciones necesitan revisión independiente. No se repararon omisiones históricas del ledger ni se evaluó impacto retrospectivo sobre modelos/ROI; los tests sintéticos no acreditan rentabilidad. No se probó el reintento nativo en POSIX porque allí la semántica de lectores difiere. El CI multiintérprete no se ejecutó localmente.

Control de artefactos: de 2369 archivos preexistentes de `data/predictions` y `data/bets` cuyo hash se guardó antes de la validación global, dos cambiaron durante la sesión: `candidates_tennis_wta_guadalajara_open.csv` (17:30:11 hora local) e `intraday_edge_log.csv` (17:30:12). Ninguna prueba ejecutada en la raíz escribe esa liga ni ese log productivo; el resto del trabajo global corre en copias aisladas. El horario es compatible con una captura/revalidación operativa concurrente, **INFERRED**, pero no se afirma quién escribió: `Get-ScheduledTaskInfo` fue denegado, **NOT_VERIFIABLE**. No se restauraron esos archivos ni se confundieron con cambios de código de esta remediación. Los otros 2367 hashes permanecieron iguales en la comprobación. Por ello no se declara que todo el árbol de datos haya permanecido estático.

## 13. Tabla maestra

`PVI` = Pendiente de validación independiente. Las listas exactas de archivos y pruebas están en cada ficha.

| ID | Prioridad | Severidad | Estado inicial | Estado final | Archivos modificados | Tests | Criterio de aceptación |
|---|---|---|---|---|---|---|---|
| AUD-001 | P2 | MEDIUM | Confirmado | PVI | 2 motores + 3 tests | V01/V10 | Cumplido: corte diario |
| AUD-002 | P2 | MEDIUM | Confirmado | Bloqueado | Ninguno | Reproducción persiste | No: identidad insuficiente |
| AUD-003 | P2 | MEDIUM | Confirmado | PVI | runner + tenis e2e | V02 | Cumplido: archivo e idempotencia |
| AUD-004 | P2 | MEDIUM | Confirmado | PVI | roi_engine + penalties | V03 | Cumplido: paridad/rechazo |
| AUD-005 | P2 | MEDIUM | Confirmado | PVI | revalidation + concurrency | V04/V07 | Cumplido: no lost update |
| AUD-006 | P2 | MEDIUM | Confirmado | PVI | atomic + readers | V05 | Cumplido: reintento acotado |
| AUD-007 | P2 | MEDIUM | Confirmado | PVI | odds_cache + tests | V07 | Cumplido: payload/cuota |
| AUD-008 | P3 | MEDIUM | Confirmado | PVI | conftest + 7 tests | V07/V09 | Cumplido: salidas aisladas |
| AUD-009 | P3 | LOW | Confirmado | PVI | hook + helper + tests | V08 | Cumplido: valor sin comentario |
| AUD-010 | P3 | LOW | Confirmado | PVI | instalador + tests | V08 | Cumplido: fuente única |
| AUD-011 | P3 | No asignada | Requiere información adicional | Bloqueado | Ninguno | Sin carga representativa | No verificable |
| AUD-012 | P3 | No asignada | Requiere información adicional | Bloqueado | Ninguno | Compatibilidad existente | Falta política de confianza |
| AUD-013 | P3 | No asignada | Requiere información adicional | Bloqueado | Ninguno | Sin reproducción DOM | Falta ruta adversaria |

## 14. Cambios pendientes de verificación independiente

Revisar AUD-001 y AUD-003–010 mediante `verificar-remediacion.md`, sobre el diff final y las regresiones, sin tomar este informe como aprobación independiente. AUD-002 debe desbloquearse antes de declarar resuelta la integridad de resultados; AUD-011–013 requieren información adicional, no cierre por ausencia de reproducción.

Comprobación final: los hashes del consolidado y de `.claude/automation/runtime/current-task.md` coinciden con los iniciales. Ruff, mypy y `git diff --check` satisfactorios tras las últimas ediciones de código. Se solicitó información sobre identidad entre proveedores para AUD-002 durante la sesión; no se recibió un contrato que permitiera desbloquearlo antes de cerrar este registro.

## 15. Anexo de comandos

Todos los pytest dirigidos se ejecutaron con `python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/<nombre único>`, desde la raíz, salvo la suite global y la prueba roja, cuyo cwd fue la copia aislada y cuyos temporales autorizados usaron ruta absoluta dentro del workspace.

```text
V01 tests/test_audit_temporal.py tests/test_backtest_parity.py
V02 tests/settlement/test_settle_tennis_e2e.py tests/settlement/test_superseded_picks.py
V03 tests/test_audit_penalties.py tests/test_roi_engine.py tests/test_backtest_parity.py
V04 tests/test_audit_log_concurrency.py
V05 tests/test_audit_atomic_readers.py tests/test_storage.py
V07 tests/test_pipeline_demo.py tests/test_calibration_live.py tests/test_accuracy_mode.py tests/test_team_scoring.py tests/test_line_movement.py tests/test_revalidation.py tests/test_odds_cache.py
V08 tests/test_audit_hooks.py tests/test_hook_targets.py
V09 tests/test_audit_pipeline_isolation.py
V10 tests/test_backtest_markets.py tests/test_pergame_calibration.py
python -m ruff check src scripts tests .claude/hooks/_secret_literals.py
python -m mypy src
git diff --check
git diff --stat
git status --short
Get-FileHash audits/consolidated/latest.md
Get-FileHash .claude/automation/runtime/current-task.md
python .codex-tmp/prepare_remediation_validation.py
python -m pytest -q -p no:cacheprovider --basetemp=C:/dev/3/sports-quant-platform/.codex-tmp/remediation-full-approved
python .codex-tmp/prepare_red_validation.py
python -m pytest -q --tb=short -p no:cacheprovider --basetemp=C:/dev/3/sports-quant-platform/.codex-tmp/remediation-red-approved tests/test_audit_temporal.py tests/test_audit_penalties.py tests/test_audit_log_concurrency.py tests/test_audit_atomic_readers.py tests/test_odds_cache.py tests/settlement/test_settle_tennis_e2e.py tests/test_audit_hooks.py -k 'daily_batch or missing_trajectory or books_dispersion or concurrent_appends or reader_contention or successful_fetch_survives or superseded_tennis or comments_do_not or reinstall_preserves'
python .codex-tmp/recheck_merge.py
python -m pip wheel --no-deps --no-build-isolation --no-index --wheel-dir .codex-tmp/wheel .
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/remediation-final-targeted tests/test_audit_temporal.py tests/test_audit_penalties.py tests/test_audit_log_concurrency.py tests/test_audit_atomic_readers.py tests/test_audit_pipeline_isolation.py tests/test_audit_hooks.py tests/test_backtest_parity.py tests/test_backtest_markets.py tests/test_pergame_calibration.py tests/test_roi_engine.py tests/test_storage.py tests/test_pipeline_demo.py tests/test_calibration_live.py tests/test_accuracy_mode.py tests/test_team_scoring.py tests/test_line_movement.py tests/test_revalidation.py tests/test_odds_cache.py tests/test_hook_targets.py tests/settlement/test_settle_tennis_e2e.py tests/settlement/test_superseded_picks.py
python .codex-tmp/recheck_final_artifacts.py
```
