# Auditoría técnica independiente — OpenAI Astra

Fecha: 2026-09-14. Repositorio: `C:/dev/3/sports-quant-platform`.
Base inspeccionada: `8503b7a63acdac017b50e1559a3044581b44cc9e`.

## 1. Resumen ejecutivo

Se confirman cuatro defectos **MEDIUM**, todos **REPRODUCED**, con confianza **HIGH**: contaminación temporal en backtests, candidatos archivados de tenis sin liquidación, pérdida de actualizaciones concurrentes en logs y fallo de una respuesta HTTP válida por errores de creación de la caché. No hay hallazgos CRITICAL/HIGH/LOW confirmados ni prioridades P0/P1.

La revisión cubrió los flujos críticos y sus controles, con tres revisiones paralelas especializadas y revalidación independiente del agente principal. No constituye certificación de rentabilidad ni de ausencia universal de defectos. No se corrigió código ni se modificaron datos operativos.

Validación final: **2013 passed, 1 skipped** en la suite aislada completa; Ruff y MyPy correctos; `pip check` sin incompatibilidades y `pip-audit` sin vulnerabilidades conocidas en el lock consultado. La única omisión es deliberada y está identificada en la sección 19. Los cuatro defectos se reprodujeron fuera de los escenarios cubiertos por la suite existente.

## 2. Alcance

Auditoría integral del estado actual, según `audits/prompts/auditoria-openai-astra.md`, no revisión de un diff particular. Git mostró inicialmente únicamente `?? audits/`; esos archivos sin seguimiento precedían esta auditoría. No había cambios rastreados que separar del código base. El entregable y las reproducciones temporales son las únicas escrituras deliberadas de auditoría; las pruebas amplias ejecutan escrituras propias dentro de una copia aislada.

Se localizó `AGENTS.md` en la raíz, aplicable a todo el repositorio. La consulta de las rutas ascendentes C:/AGENTS.md, C:/dev/AGENTS.md y C:/dev/3/AGENTS.md no encontró archivos. La búsqueda de instrucciones descendientes devolvió únicamente el de raíz; se registró acceso denegado al caché `.pytest_cache`. El prompt específico autoriza guardar este informe y define el alcance integral. Se preservaron las reglas de evidencia, solo lectura del proyecto y terminología de severidad/confianza de AGENTS.

## 3. Metodología

Lectura de README, manifiesto, configuración, Makefile, Dockerfile, CI, contratos de configuración y pricing independiente; mapa de archivos; reconstrucción de flujos; búsqueda de controles compensatorios; pruebas estrechas antes de ampliar; reproducciones locales sin red real. Se delegaron cuantitativa, pipeline/datos y seguridad/operaciones. El principal inspeccionó las causas y ejecutó nuevamente los cuatro escenarios en `.codex-tmp/astra_reproduce.py`.

Solo REPRODUCED y STATICALLY_VERIFIED se consideran defectos confirmados. Las sospechas sin ruta causal completa se separan. La puntuación es exactamente `(I×30+A×20+P×20+E×15+R×10+C×5)/4`; confianza y prioridad se valoran por separado. Los rangos del prompt se expresan mediante CRITICAL/HIGH/MEDIUM/LOW, como exige AGENTS.

## 4. Limitaciones

- No se ejecutaron trabajos live ni se consumieron cuotas deportivas; tampoco se cambiaron credenciales ni se inspeccionaron valores de `.env`.
- No se verificaron las tareas realmente instaladas, ACL de producción, estado remoto de CI, despliegues ni respuestas actuales de proveedores.
- No se cuantificó el sesgo agregado del backtest sobre el histórico real ni la cantidad real de picks de tenis afectados. Los escenarios reproducidos demuestran activación, no prevalencia.
- La suite amplia se aisló copiando 626 archivos rastreados, excluyendo `audit/` y `audits/`, sin `.git`, `.env` ni datos operativos. Esto introduce límites para pruebas dependientes de contexto Git o datos externos.
- Git advirtió falta de acceso al ignore global. La búsqueda exhaustiva de instrucciones tuvo una denegación sobre `.pytest_cache`.
- No se midió cobertura de líneas, benchmark general ni se construyó Docker. Se distingue lectura estática de ejecución real.
- El subagente de seguridad agotó su cuota antes de su consolidación final; sus observaciones recibidas fueron revisadas y el único defecto propuesto se reprodujo nuevamente por el principal.

## 5. Inventario

| Componente | Ubicación y función |
|---|---|
| Aplicación | Paquete Python `src/sqp`, Python >=3.11; entorno local Python 3.14 |
| Entradas | `scripts/run_all.py`, `run_daily.py`, `settle_all.py`, `capture_closing_odds.py`, BAT de operación |
| Dominio | Event, EventOdds, MarketLine, EstimatedProbabilities, BetCandidate |
| Modelos | Elo, distribuciones por familia, scoring, parque, descanso, FIP; ruta ML experimental |
| Mercados/riesgo | No-vig, EV, Kelly, caps, bankroll, prediction gate, degradación y revalidación |
| Datos | CSV/JSON en `data/`, stores y escrituras atómicas; no se localizó base SQL ni migraciones SQL |
| Evaluación | Backtesting, calibración, model-vs-market, CLV y métricas por segmento |
| Integraciones | The Odds API, MLB Stats API, ESPN, Open-Meteo opcional |
| Presentación | Reportes Markdown/HTML y dashboard local; no servidor API propio localizado |
| Automatización | Windows BAT/PowerShell y Task Scheduler; GitHub Actions; Docker de demo |
| Dependencias | NumPy, pandas, SciPy, scikit-learn, joblib, requests, PyYAML, dotenv; constraints lock |

## 6. Cobertura

| Área | Estado | Evidencia de inspección |
|---|---|---|
| Arquitectura/configuración | Inspeccionado | README, pyproject, config, registry, contratos, entradas |
| Modelos y matemáticas | Inspeccionado | distributions, adapters, Elo, settlement_math, independent, Kelly |
| Backtests/calibración | Inspeccionado | engine, roi_engine, calibrator/data/pergame, tests de paridad/corte |
| Pipeline/frescura | Inspeccionado | daily en rutas principales, closing_capture, intraday, revalidation |
| Liquidación/storage | Inspeccionado | runner/settle, served/odds/results/atomic/lock, starters/FIP |
| Seguridad/proveedores | Inspeccionado | clientes, retries, caché, redacción de errores, serialización |
| APIs propias/auth/sesiones/CORS | No localizado | Aplicación de lotes y HTML local; no endpoints de servidor identificados |
| Observabilidad | Inspeccionado | logging, run_status/health y llamadas del pipeline |
| CI/Docker/scripts | Inspeccionado estáticamente | workflow, Dockerfile, Makefile, scripts operativos seleccionados |
| ML y features | Inspección parcial | builders, train, particiones temporales; ruta experimental sin consumidor live |
| Documentación auxiliar | Localizado/seleccionado | Contratos centrales leídos; no cada bitácora ni cada archivo de automatización |
| Infraestructura real/red/datos completos | Excluido de ejecución | Seguridad de revisión y límites declarados |
| Auditorías ajenas | Excluido | No se leyeron `audits/claude/`, `audits/consolidated/` ni informes de `audit/` |

“Inspeccionado” identifica componentes efectivamente leídos, no auditoría línea por línea de todos sus archivos.

## 7. Arquitectura

El flujo operativo consume cuotas, construye estimaciones por adaptador, aplica benchmark no-vig, calibración y restricciones de riesgo, persiste predicciones/candidatos y genera reportes. La liquidación consume resultados y alimenta ledger y stream graduado; este último aporta evidencia para calibración y gates. La captura de cierre y revalidación son entradas adicionales que comparten almacenamiento con el run diario.

El disco local es el límite de consistencia principal. La atomicidad de un reemplazo y la exclusión entre transacciones son controles diferentes: el primero existe ampliamente, el segundo no cubre todos los read-modify-write. La metadata de un evento está repartida entre candidatos, predicciones vigentes e históricos, lo que explica ASTRA-02.

## 8. Estado técnico

Ruff no detectó infracciones y MyPy informó éxito en 101 archivos fuente. Las primeras 161 pruebas del núcleo pasaron. `pip check` no encontró incompatibilidades declaradas. El detalle final de la suite y auditoría de dependencias se registra en las secciones 19–20. Estos controles no refutan los escenarios ausentes de la suite que se detallan a continuación.

## 9. Tabla maestra

| ID | Título | Severidad | Puntuación | Prioridad | Confianza | Evidencia |
|---|---|---|---:|---|---|---|
| ASTRA-01 | Backtest usa resultados posteriores del mismo día | MEDIUM | 62.50 | P2 | HIGH | REPRODUCED |
| ASTRA-02 | Pick archivado de tenis no obtiene metadata para liquidar | MEDIUM | 58.75 | P2 | HIGH | REPRODUCED |
| ASTRA-03 | Append concurrente pierde registros de revalidación | MEDIUM | 50.00 | P2 | HIGH | REPRODUCED |
| ASTRA-04 | Creación de caché aborta respuesta HTTP válida | MEDIUM | 42.50 | P2 | HIGH | REPRODUCED |

## 10. Hallazgos por severidad

### ASTRA-01 — Backtest usa resultados posteriores del mismo día

- Categoría: Defecto confirmado. Área: lógica cuantitativa/backtesting.
- Severidad MEDIUM; puntuación 62.50; prioridad P2; confianza HIGH; evidencia REPRODUCED.
- Ubicación: `src/sqp/backtesting/roi_engine.py:277` (ordenación), `:375` (`adapter.observe(r)`); actualización inmediata también en `src/sqp/backtesting/engine.py:108`. Contexto: `results_store.py` conserva fecha diaria y ordena por día.
- Escenario/activación: dos encuentros del mismo día, con horas explícitas, cuyos IDs ordenan el partido de las 20:00 antes del de las 10:00. Se entrega al motor la lista cronológica `[early, late]`.
- Problema y causa raíz: el motor reordena por fecha/equipos/ID/marcador y observa cada resultado inmediatamente. El orden determinista no acredita disponibilidad al corte.
- Esperado: cambiar exclusivamente el resultado posterior no altera la probabilidad anterior.
- Observado/evidencia directa: resultado de late 10–0 produce `early=0.5632`; late 0–10 produce `early=0.5416`. La estimación de late permanece 0.5526 en la reproducción original. Datos deportivos y cuotas de early permanecen idénticos.
- Impacto/consecuencia: métricas y probabilidades de backtest contaminadas; pueden orientar evaluaciones y ajustes de parámetros con información aún no disponible. Magnitud histórica agregada no establecida.
- Controles existentes: `_prior_games` excluye mismo día en ajustes auxiliares, pero no en estado del adaptador; `_match_result` evita dobles jornadas ambiguas, pero acepta las horas explícitas del escenario. `tests/test_backtest_parity.py:258` replica expresamente la actualización Elo del mismo día, por lo que no discrimina este error. Gates de staking no corrigen el backtest.
- Matriz: I=3, evidencia cuantitativa alterada; A=2, motores de backtest y consumidores; P=2, depende del orden/disponibilidad; E=3, datos diarios e IDs ordinarios; R=2, corregir y recalcular; C=3, controles no cubren estado principal.
- Cálculo: `(3×30+2×20+2×20+3×15+2×10+3×5)/4 = 62.50`.
- Fix mínimo/recomendación: con datos diarios, estimar el bloque completo del día antes de observar resultados; para actualización intradía exigir instante verificable de disponibilidad, no inferirlo del ID o del inicio.
- Aceptación: cualquier cambio o permutación de resultados no disponibles al corte deja invariantes las probabilidades previas.
- Tests necesarios: IDs inversos con horas, mismo día sin horas, invariancia moneyline/totals y control positivo donde resultados de días anteriores sí afectan al modelo.

### ASTRA-02 — Pick archivado de tenis sin metadata para liquidar

- Categoría: Defecto confirmado. Área: liquidación/integridad de datos.
- Severidad MEDIUM; puntuación 58.75; prioridad P2; confianza HIGH; evidencia REPRODUCED.
- Ubicación: `src/sqp/settlement/runner.py:564`–581, `_settle_tennis`; recuperación de candidatos archivados en `:509`.
- Escenario/activación: un candidato abandona la lista antes del partido, queda archivado y su evento desaparece de las predicciones vigentes. ESPN entrega el ganador correcto y las predicciones archivadas conservan jugadores/fecha.
- Problema y causa raíz: se recupera el candidato mediante `_con_superseded`, pero scores, start_times y metadata se construyen solo desde predicciones vigentes. BetCandidate tampoco conserva start_time.
- Esperado: el candidato recuperado se liquida con el resultado disponible y conserva trazabilidad/idempotencia.
- Observado/evidencia directa: `superseded_candidates` encuentra 1 candidato; `_settle_tennis` devuelve `[]`. Control discriminante del principal: colocar la metadata histórica en el fichero vigente, sin cambiar candidato ni proveedor, produce `win`, PnL 10.0 y persistencia.
- Impacto/consecuencia: falta evidencia de resultado; con stake real, el ledger omite ganancia o pérdida. Sin fecha también falla la vía de expiración. La búsqueda superseded tiene horizonte finito, por lo que esperar no garantiza recuperación.
- Controles existentes: archivo conserva datos recuperables; protección contra sobrescribir eventos ya comenzados no cubre eventos retirados antes de comenzar. Gates pueden mantener stake cero, pero no rescatan la evidencia. El fallback de resultados históricos también usa exclusivamente `preds` vigente.
- Matriz: I=2, pérdida de liquidación condicionada; A=2, settlement/evidencia/ledger; P=3, refrescos normales; E=3, evento desplazado; R=2, metadata archivada recuperable; C=2, recuperación de candidatos incompleta.
- Cálculo: `(2×30+2×20+3×20+3×15+2×10+2×5)/4 = 58.75`.
- Fix mínimo/recomendación: recuperar metadata archivada para los candidatos superseded y usar la unión en score mapping, antigüedad y enrichment; definir precedencia por identidad/generación.
- Aceptación: evento ausente del fichero vigente pero presente en archivo y con resultado válido obtiene grado, PnL y metadata correctos, exactamente una vez.
- Tests necesarios: E2E anterior, variante sin fichero vigente, pérdida/ganancia y segunda ejecución idempotente.

### ASTRA-03 — Append concurrente pierde registros de revalidación

- Categoría: Defecto confirmado. Área: concurrencia/observabilidad/integridad.
- Severidad MEDIUM; puntuación 50.00; prioridad P2; confianza HIGH; evidencia REPRODUCED.
- Ubicación: `src/sqp/pipeline/revalidation.py:71`–87, `_append_log`; llamada fuera del lock de candidatos en `:354`. El helper también sirve al observatorio intradía.
- Escenario/activación: dos procesos, por ejemplo ejecución manual y programada, solapan lectura y reemplazo del mismo log.
- Problema y causa raíz: read-modify-write sin lock del log. Un nombre temporal único y `os.replace` no serializan la transacción.
- Esperado: ambas filas nuevas sobreviven junto al histórico.
- Observado/evidencia directa: intercalado determinista A lee/prepara, B completa append, A reemplaza. Resultado `['prior','writer-A']`; falta writer-B. Ambas escrituras utilizan el helper atómico real; solo se instrumentó el punto de intercalado.
- Impacto/consecuencia: rastro incompleto de revocaciones o muestras intradía, con CSV válido y sin error visible. No se demostró pérdida de stakes en este escenario.
- Controles existentes: lock del CSV de candidatos queda fuera de esta operación; atomicidad/fsync protege cada escritura, no su combinación. Una política IgnoreNew de una tarea no excluye una invocación manual concurrente.
- Matriz: I=2, pérdida de evidencia; A=2, logs y análisis consumidores; P=2, solapamiento posible; E=2, requiere concurrencia; R=2, recuperación desde evidencia secundaria; C=2, atomicidad parcial.
- Cálculo: `(2×30+2×20+2×20+2×15+2×10+2×5)/4 = 50.00`.
- Fix mínimo/recomendación: lock propio por fichero que abarque lectura, unión de columnas y reemplazo.
- Aceptación: escritores solapados conservan todas las filas y columnas sin datos truncados ni sobrescritura silenciosa.
- Tests necesarios: intercalado determinista de dos escritores, con y sin evolución de esquema; prueba de timeout segura del lock.

### ASTRA-04 — Creación de caché aborta respuesta HTTP válida

- Categoría: Defecto confirmado. Área: robustez/proveedores.
- Severidad MEDIUM; puntuación 42.50; prioridad P2; confianza HIGH; evidencia REPRODUCED.
- Ubicación: `src/sqp/providers/odds_cache.py:81`, `FileCache.put`; consumidor `src/sqp/providers/odds_api.py:214`–215.
- Escenario/activación: directorio de caché no creable por ACL o componente de ruta que es un archivo, tras una respuesta HTTP válida en un endpoint cacheado. La caché está conectada por defecto al cliente.
- Problema y causa raíz: `mkdir` está fuera del `try` de escritura best-effort, por lo que su OSError se propaga y aborta `_get` antes de devolver el payload.
- Esperado: una avería de caché no descarta una respuesta HTTP válida; se conserva la cuota capturada y se entrega el dato.
- Observado/evidencia directa: con Session falsa HTTP 200 y cabecera `x-requests-last: 6`, y un archivo real en la ruta padre de caché dentro del scratch, `_get` lanza FileExistsError. Se observa una petición realizada y coste 6 capturado, pero no retorna el payload. No hubo red ni credenciales reales. El subagente reprodujo además PermissionError controlado.
- Impacto/consecuencia: pierde la respuesta ya obtenida y la liga puede fallar en ese run; posteriores reintentos consumen recursos sin necesidad. La persistencia de cuota en consumidores que se ejecuta después del fetch también puede omitirse; no se cuantificó gasto real.
- Controles existentes: el except ya captura TypeError/OSError de `write_text`; no incluye creación del directorio. Retries HTTP no solucionan un fallo posterior de filesystem.
- Matriz: I=2, operación válida fallida; A=2, clientes/pipeline; P=1, fallo excepcional del directorio; E=2, condición específica del filesystem; R=1, corregir ruta/permisos y reintentar; C=2, best-effort parcial.
- Cálculo: `(2×30+2×20+1×20+2×15+1×10+2×5)/4 = 42.50`.
- Fix mínimo/recomendación: incluir `mkdir` dentro del mismo bloque protegido de escritura best-effort.
- Aceptación: error de creación de caché no cambia payload devuelto ni headers de cuota después de HTTP 200.
- Tests necesarios: FileExistsError y PermissionError en mkdir a través de `_get`/fetch_odds; control de escritura de caché sana.

## 11. Seguridad

Se inspeccionaron redacción de errores con apiKey, hosts de proveedores, timeouts/retries, validaciones y carga de artefactos locales. No se identificó un secreto confirmado ni una explotación confirmada. `joblib` exige confianza en artefactos locales; no se demostró que una entrada remota no confiable alcance esos loaders.

Candidato **INFERRED**, no defecto confirmado: interpolación de league/market en `innerHTML` de filtros del dashboard (`html_report.py:1175`, `:1474`, `:1495`). Falta demostrar una ruta de entrada no confiable que pueda controlar esos valores, considerando registro/configuración y productores. Nombres de equipos y JSON tienen controles de escape en otras rutas. No se asigna severidad de defecto ni se contabiliza como hallazgo.

## 12. Arquitectura: límites y acoplamiento

Los adaptadores separan familias deportivas y el núcleo comparte pricing/riesgo. La lectura/escritura directa de CSV conecta múltiples procesos y requiere contratos transaccionales explícitos. ASTRA-02 demuestra un contrato de metadata incompleto, y ASTRA-03 una frontera de exclusión incompleta. No se reportan complejidad, duplicación o tamaño de módulos por sí solos.

## 13. Lógica y exactitud

Se verificaron fórmulas de EV, Kelly, no-vig, distribuciones y cinco estados de liquidación del modo independiente. Este modo congela entradas antes de cuotas y declara sus límites. Las probabilidades condicionadas a no-push son coherentes con las evaluaciones binarias que excluyen pushes. ASTRA-01 es el defecto temporal demostrado. No se inventaron umbrales de freshness ni de aprobación: se contrastaron configuración y código.

## 14. Datos

Los stores aplican deduplicación y algunos locks, y los helpers atómicos usan temporales únicos/fsync. Los controles del bankroll rechazan importes indeterminados en movimientos que afectan saldo. ASTRA-02 afecta completitud de settlement y ASTRA-03 completitud de logs.

Se localizaron otros read-modify-write sin lock en ResultsStore, StartersStore y StarterFIPStore. Su similitud es evidencia estática de una clase a revisar, pero no se añadieron hallazgos independientes sin reconstruir y reproducir cada escenario operativo. No se afirma corrupción histórica por esas rutas.

## 15. APIs

Se revisaron clientes HTTP salientes, estados de error, cuota, retries y caché; no hay API HTTP propia localizada. ASTRA-04 rompe la degradación prometida de la caché. Validación contra payloads reales actuales y contratos externos completos: **NOT_VERIFIABLE** en esta ejecución, al no realizarse consultas deportivas live.

## 16. Rendimiento

Se inspeccionaron cálculos vectorizados y límites de recursos del pricing independiente, así como límites de red. No se efectuó benchmark de volumen ni perfilado; por tanto no se afirma capacidad máxima ni ausencia de cuellos de botella. No se convirtió una posible optimización en defecto.

## 17. Concurrencia

La exclusión de candidatos y odds es explícita, y el timeout del lock aborta en lugar de continuar sin protección. ASTRA-03 reproduce el límite que queda fuera de esa protección. No se demostró deadlock ni se ejecutó stress contra datos operativos.

## 18. Robustez

Se comprobaron controles que aplazan anulaciones ante respuestas de resultados vacías, dedup de liquidación, fallback histórico y aislamiento demo. Los dos huecos concretos son recuperación incompleta de metadata (ASTRA-02) y best-effort incompleto de caché (ASTRA-04).

## 19. Pruebas

- Núcleo: `161 passed in 101.52s`; odds, Kelly, prediction gate, pricing independiente y settlement math.
- Ruff: `All checks passed!`.
- MyPy: `Success: no issues found in 101 source files`.
- Primera suite aislada: `1181 passed, 833 errors in 356.83s`. Clasificación **ENVIRONMENTAL_FAILURE**: faltaba el padre del basetemp. No hubo fallos de assertions en esa ejecución.
- Segunda suite aislada: **`2013 passed, 1 skipped in 1670.76s (0:27:50)`**, código de salida 0. Los 833 errores de preparación del primer intento quedaron resueltos creando el directorio padre del basetemp; no son defectos del proyecto. No hubo NEW_REGRESSION ni PRE_EXISTING_FAILURE de assertions en la ejecución final. Las cuatro reproducciones de defectos son evidencia separada de esta suite.
- Omisión verificada con ejecución estrecha y `-rs`: `test_every_finding_slot_tolerates_hostile_text[severity]`, `tests/test_review_v2.py:228`, declara `severity is a closed enum, not free text`. Es una exclusión deliberada del caso parametrizado; no se cuenta como prueba aprobada.
- Reproducciones del principal: los cuatro escenarios de `.codex-tmp/astra_reproduce.py` terminaron con código 0 y comprobaron los resultados incorrectos mediante assertions. Incluye control positivo de liquidación de tenis.

Los tests de backtest parity no discriminan ASTRA-01 porque incorporan el mismo comportamiento del motor en su esperado. Las cuatro regresiones propuestas cubren invariantes observables, no una preferencia de implementación. No se modificaron tests del proyecto.

## 20. Dependencias

Manifiesto y lock inspeccionados. `python -m pip check`: `No broken requirements found`. Se auditó el lock con `pip-audit 2.10.1`, `--no-deps --disable-pip`, sin instalación/resolución de paquetes. El primer intento fue bloqueado por el sandbox al conectar a PyPI (WinError 10013), clasificado ENVIRONMENTAL_FAILURE; la repetición autorizada finalizó con código 0 y `No known vulnerabilities found`. Es el resultado de la herramienta para los paquetes consultados, no una garantía de seguridad ni un análisis de dependencias ajenas al lock.

La coherencia de dependencias instaladas no prueba ausencia de vulnerabilidades. No se consideró antigüedad de versiones como defecto ni se usaron avisos históricos escritos en comentarios como prueba de vulnerabilidad actual.

## 21. Infraestructura

CI declara matriz Python 3.11–3.14 en Ubuntu, Windows 3.12, lint, tipos, pruebas y auditoría de dependencias; permisos de contenido de lectura y job específico de alerta. Docker usa usuario sin privilegios y está documentado como entorno demo, no réplica de producción. Makefile fue inspeccionado: `make check` llama pytest sin basetemp, por lo que se ejecutaron sus controles separadamente con opciones compatibles con esta revisión. No se instalaron tareas ni se construyó o publicó imagen.

## 22. Observabilidad

Logging comparte handler dentro del proceso, run_status/health dan señales operativas y el workflow contiene alerta para CI rojo. ASTRA-03 confirma que un log válido puede estar incompleto bajo concurrencia. La eficacia real de alertas remotas y la rotación entre procesos no se certifican con esta inspección.

## 23. Deuda técnica

No se agregan hallazgos por estilo, TODO, documentación extensa o refactors opcionales. Como trabajo derivado de causas confirmadas: centralizar contratos de disponibilidad temporal y de metadata histórica, y revisar transacciones read-modify-write restantes. No son defectos adicionales contabilizados.

## 24. Fortalezas

Controles de finitud y límites de probabilidad/stake; gates por defecto restrictivos; muestra independiente por evento para inferencia; calibración temporal; separación de probabilidad, mercado, edge y ROI; aislamiento demo; escritura atómica y locks en rutas críticas; fallos explícitos de integridad del bankroll; comprobaciones de payload antes de anulaciones; tests extensos de regresiones específicas.

## 25. Riesgos

Confirmados: métricas históricas contaminadas, picks sin grado, evidencia concurrente perdida y fallos evitables de ingestión. No verificables: prevalencia en datos reales, seguridad más allá de los avisos conocidos consultados, salud de servicios y tareas instaladas. Inferido: ruta potencial de inyección HTML sin origen no confiable demostrado. Descartado: sospecha de cálculo erróneo de `ROOT.parents[2]` y sospecha de pérdida de fechas por mezcla Z/+00:00; la inspección/reproducción refutó ambas.

## 26. Plan de remediación

P0: ninguno. P1: ninguno. P2: corregir ASTRA-01 y recalcular evaluaciones afectadas; recuperar metadata para ASTRA-02 y auditar candidatos archivados; serializar append de ASTRA-03; proteger mkdir de ASTRA-04. La implementación y cualquier reparación de datos deben ser una tarea separada; no se realizaron durante esta auditoría.

## 27. Criterios de aceptación

Cerrar cada hallazgo únicamente cuando pase su reproducción convertida en regresión, el control positivo correspondiente y los checks pertinentes. Para ASTRA-01 exigir invariancia temporal, no solo igualdad con una implementación que comparte el defecto. Para ASTRA-02 exigir persistencia e idempotencia. Para ASTRA-03 exigir conservación de ambos escritores. Para ASTRA-04 exigir devolución de respuesta válida bajo fallo de caché. Recalcular evidencia histórica no equivale a autorización para apostar.

## 28. Comparación histórica

Al terminar la inspección principal se consultó exclusivamente la existencia del informe OpenAI anterior: `audits/openai/latest.md` no existía y `audits/openai/history/` no contenía archivos. No hubo informe que archivar ni comparación histórica verificable. Los cuatro hallazgos son nuevos en este informe; no se afirma que sean regresiones recientes. Las referencias a auditorías presentes en comentarios del código no se usaron como sustituto de evidencia.

## 29. Conclusiones

La auditoría confirma cuatro defectos MEDIUM con reproducciones y controles discriminantes. No corresponde PASS. El código funcional y los datos operativos permanecen sin correcciones. La cobertura es amplia sobre flujos principales, con límites expresos sobre servicios, histórico completo y despliegue. No se infiere rentabilidad, precisión futura ni ausencia de otros defectos.

Comprobación final del workspace: `git diff --name-only` sin salida y `git status --short` mantiene únicamente `?? audits/`, presente desde el inicio y ahora con este entregable. No hubo cambios rastreados ni operaciones Git de publicación o modificación del repositorio revisado.

## 30. Anexo de comandos y reproducibilidad

Comandos efectivamente ejecutados, agrupados sin repetir cada consulta de lectura:

```powershell
Get-Content -LiteralPath auditoria-openai-astra.md
# No existía en raíz; se localizó mediante rg.
rg --files --hidden -g '*auditoria*' -g 'AGENTS.md'
Get-Content -LiteralPath audits/prompts/auditoria-openai-astra.md
Get-Content -LiteralPath AGENTS.md
git status --short
git rev-parse --show-toplevel
git log -1 --format='%H %s'
git diff --stat
git ls-files -z
rg --files --hidden --no-ignore -g AGENTS.md ...
# Lecturas Get-Content y búsquedas rg sobre src, scripts, tests,
# README, IMPLEMENTACION, pyproject, requirements.lock, configs, CI y contratos.

$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/astra-core tests/test_odds.py tests/test_kelly.py tests/test_prediction_gate.py tests/test_independent_pricing.py tests/test_settlement_math.py
ruff check --no-cache src scripts tests
mypy --cache-dir .codex-tmp/astra-mypy src
python -m pip check
python -m pip_audit --version
python -m pip_audit -r requirements.lock --no-deps --disable-pip --cache-dir .codex-tmp/astra-pip-audit --progress-spinner off

# Copia aislada: script Python por stdin obtuvo git ls-files y copió 626
# archivos rastreados, excluyendo audit/ y audits/, mediante shutil.copyfile.
# CWD: .codex-tmp/astra-isolated
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-astra-all > ..\astra-pytest-all.txt 2>&1
New-Item -ItemType Directory -Path .codex-tmp -Force
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-astra-all > .codex-tmp/astra-pytest-retry.txt 2>&1

# CWD raíz; no red ni datos operativos:
python -B .codex-tmp/astra_reproduce.py
python -m pytest -q -rs -p no:cacheprovider --basetemp=.codex-tmp/astra-skip 'tests/test_review_v2.py::test_every_finding_slot_tolerates_hostile_text[severity]'
```

El primer comando de lectura falló por ruta inexistente. Las escrituras PowerShell de temporales y consulta de red requirieron repetición con autorización tras denegación del sandbox. Las reproducciones iniciales de los subagentes se ejecutaron mediante `python -B -` con snippets equivalentes y scratch propio; el script consolidado permite repetir las cuatro sin modificar código del proyecto.

Diagnóstico de duración: se consultaron el log con `Get-Content -Tail`, procesos Python con `Get-Process` y nombres/fechas de directorios temporales con `Get-ChildItem ... | Sort-Object LastWriteTime`. Esta última lectura necesitó autorización por ACL del scratch creado fuera del sandbox. Una consulta auxiliar `Get-CimInstance Win32_Process` fue denegada y no se usó como evidencia. La validación del propio informe con Python comprobó la secuencia de 30 secciones, cuatro fichas y los cuatro cálculos de puntuación.

Evidencia temporal: `.codex-tmp/astra_reproduce.py`, `.codex-tmp/astra-confirm-ogedqjc_/`, `.codex-tmp/astra-pytest-all.txt` y `.codex-tmp/astra-isolated/.codex-tmp/astra-pytest-retry.txt`. El script usa una carpeta nueva por ejecución y proveedor HTTP/ESPN falso. No usar sus datos sintéticos como métricas del sistema real.
