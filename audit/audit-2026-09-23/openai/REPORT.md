# Diagnóstico independiente — OpenAI

Ronda: **audit-2026-09-23**. Base: **main@7bd565e19606a70b37f704ca44cdc41e168ba274**. Alcance: auditoría integral por inventario y revisión selectiva de rutas críticas; no es una inspección exhaustiva de cada línea.

## Resultado

**9 defectos confirmados: CRITICAL 0, HIGH 3, MEDIUM 5, LOW 1. P0: 0; P1: 3.** Todos tienen confianza HIGH y evidencia REPRODUCED. No se emite PASS.

**844 pruebas focalizadas aprobadas**, Ruff sin errores, MyPy sin errores en 106 archivos y dependencias instaladas sin incompatibilidades detectadas por pip check. Los tests existentes no cubrían los escenarios reproducidos. El estado remoto de CI sigue NOT_VERIFIABLE; no se ejecutó la suite completa ni una operación productiva de apuestas.

Los P1 afectan al orden y la concurrencia del gate y a la liquidación de candidatos con resultados históricos disponibles. El registro operativo observado el 2026-09-23T10:57:52Z tenía 49 mercados y **0 autorizados**, generado el 2026-09-22T15:15:26.544326Z. Esto limita la activación inmediata de los defectos del gate, pero no corrige sus causas. No se ha demostrado pérdida económica real.

| ID | Severidad | Prioridad | Hallazgo |
|---|---|---|---|
| OPENAI-001 | HIGH | P1 | El gate se actualiza después de generar los picks que debía bloquear |
| OPENAI-002 | HIGH | P1 | Una actualización concurrente puede desarmar el pestillo sin liberación humana |
| OPENAI-003 | HIGH | P1 | Se anulan candidatos aunque su resultado histórico esté disponible |
| OPENAI-004 | MEDIUM | P2 | La calibración de cuartos asiáticos aprende un objetivo distinto del precio |
| OPENAI-005 | MEDIUM | P2 | El análisis de ROI realizado elimina medias pérdidas y puede invertir el signo |
| OPENAI-006 | MEDIUM | P2 | Tres stores históricos pierden escrituras concurrentes |
| OPENAI-007 | MEDIUM | P2 | Un error HTTP de boxscore borra FIP históricos válidos |
| OPENAI-008 | MEDIUM | P2 | El hook descarta una revisión fallida sin salida ni reintento |
| OPENAI-009 | LOW | P3 | La simulación Poisson trata los cuartos asiáticos como apuestas binarias |

## Alcance, independencia y preservación

- Se ejecutó el prompt `audits/prompts/auditoria-openai-astra.md`, AGENTS.md, el contrato canónico y las nueve referencias de full-audit aplicables al inventario, evidencia, cuantitativo, orquestación, skills y limpieza. CLAUDE.md se inspeccionó como instrucción contextual del proyecto.
- La ronda ya estaba inicializada y esperaba OpenAI. No se reinició, archivó de nuevo ni consolidó: existe un auditor Claude de esta misma ronda y esta invocación es el diagnóstico del segundo auditor. El coordinador debe integrar estos entregables en MANIFEST; **no se modificó el manifest ni los archivos de Claude**.
- Cambios locales iniciales: MANIFEST y los dos entregables Claude modificados; `audit/audit-2026-09-22-r2/` sin seguimiento. No son cambios de este auditor. El HEAD permaneció en la base indicada; no se atribuye una regresión a un diff no solicitado.
- Los archivos anteriores de `latest/openai/` eran copias obsoletas del informe **audit-2026-09-18**, no un diagnóstico de esta ronda. Se comprobó igualdad SHA256 de 2/2 archivos contra `audit/audit-2026-09-22-r2/openai/` al inicio y antes del reemplazo. REPORT: `a593000e9f5644a6b34879c980b4ea90a96bd3617118d043030da1b4221db863`; EVIDENCE: `88219ecaaa2dfae87cfe4e028f149d53529c985288dd10554a9b3c24865057af`. No se sobrescribió el histórico.
- Se delegaron áreas independientes: cuantitativo, datos y operación/contratos. El principal revisó las rutas causales y controles, ejecutó los dos casos del gate y confirmó de nuevo los tres casos cuantitativos. La coincidencia entre revisores no se usó como prueba por sí sola.
- No se leyó el informe Claude actual. Las conclusiones propias y los nueve IDs se fijaron a las **2026-09-23T11:08:01.358Z** antes de leer las fuentes históricas. El manifest y comentarios del código contienen referencias a auditorías previas; se trataron como contexto secundario y no como demostración.
- No hubo cambios de código, tests, configuración, credenciales o datos de apuestas; tampoco instalaciones, llamadas a proveedores, commits, pushes, despliegues o correcciones. Los fixtures y cachés se limitaron al scratch autorizado. **Efecto incidental confirmado:** los imports usaron el logger real y añadieron mensajes a `logs/sqp.log` (se localizaron cinco mensajes con la ruta del arnés del gate). No se borró ni restauró el log; no puede atribuirse toda su actividad concurrente a esta auditoría. Las últimas pruebas históricas y reproducciones cuantitativas deshabilitaron el handler de archivo en memoria.
- No se actualizó current-task/Obsidian: la regla específica de diagnóstico permite escribir únicamente los entregables de la fase. No se ejecutó bookkeeping fuera de ese alcance.

## Inventario y matriz de cobertura

Inventario observado: 106 Python en src, 67 Python en scripts y 147 archivos test_*.py; package Python 3.14.4 local, CLI/BAT/PowerShell/Bash, YAML/JSON, CSV y artefactos de modelos, GitHub Actions, Docker y contratos .claude. Las cifras cuentan archivos, no cobertura de líneas.

| Área | Criticidad | Estado | Componentes y método | Evidencia | Límites |
|---|---|---|---|---|---|
| Arquitectura y ejecución | P0 | REVISADA_PARCIALMENTE | daily, run_all, BAT diario; reconstrucción y prueba real con proveedores sintéticos | V02, R-GATES | Sin ejecución del diario productivo ni todas las combinaciones de deportes. |
| Riesgo, gates y frescura | P0 | REVISADA | prediction_gate, kelly, bankroll, degradation, revalidation, intraday; lectura, tests e intercalado | V02, R-GATES; registro actual 49 mercados, 0 permitidos | No se mide incidencia productiva; no se prueba cada combinación de configuración. |
| Liquidación y ROI | P0 | REVISADA | runner, settle, backfill_teams, settlement_math; código, callers y fixtures | V05, R-DATA-A, R-QUANT-ROI | Sin regraduación ni reconciliación de todos los datos reales. |
| Persistencia y concurrencia | P0 | REVISADA | atomic, lock, odds/served/results/starters/FIP stores; lectura y escrituras en scratch | V05, R-DATA-B/C | Sin simulación de caída eléctrica ni estrés completo multiproceso. |
| Probabilidades, simulación y backtests | P0 | REVISADA_PARCIALMENTE | distributions, engine, roi_engine, tuning, Monte Carlo; cutoffs y casos límite | V03/V04, R-QUANT-MC | No backtest económico completo ni afirmación de rentabilidad. |
| Calibración y promoción | P0 | REVISADA | calibrator/data/pergame/metrics; splits por evento, staging, objetivos y consumidores | V03/V04, R-QUANT-CAL | Sin entrenar/promover modelos reales ni estimar daño de modelos instalados. |
| Features y ML | P0/P1 | REVISADA_PARCIALMENTE | builders/mlb/temporal, ml_train/ml_predict y evaluación shadow/blocks; fuentes y tests | V03/V04 | rest_form/weather/park/starters/independent por interfaces; disponibilidad histórica precisa y todos los modelos no verificados. |
| APIs, cuota y caché | P1 | REVISADA_PARCIALMENTE | Odds API/cache/date_window/ESPN/MLB; errores, reintentos y offline con mocks | V05, R-DATA-C | Sin llamadas a proveedores ni certificación de cuotas/esquemas/disponibilidad vivos. |
| Configuración, instalación y dependencias | P1 | REVISADA_PARCIALMENTE | pyproject, lock, Makefile, Dockerfile, configs y setup_local | V06-V11; Python 3.14.4 | Sin instalación/build Docker ni base actual de vulnerabilidades. |
| Seguridad y secretos | P0 | REVISADA_PARCIALMENTE | redacción, detector, targets, permisos CI y superficies de shell/deserialización | V06, V12 | Sin escaneo histórico exhaustivo de secretos ni prueba de explotación; no se imprimieron secretos. |
| CI remoto | P1 | NO_VERIFICABLE | ci.yml inspeccionado; consulta del estado intentada | V13: gh ausente | Checks locales no prueban CI verde. |
| Tareas programadas | P1 | REVISADA | BAT/PowerShell y consulta de acciones/últimos resultados con aprobación | V15/V16: cuatro tareas principales rc0; Dashboard rc267014 | Foto puntual; no se ejecutaron tareas ni se certifica la próxima ejecución. |
| Observabilidad y estado | P1 | REVISADA_PARCIALMENTE | monitoring/health/run_status, registry y logs por agregados | V05, V15; gate generado 2026-09-22T15:15:26.544326Z observado 2026-09-23T10:57:52Z | Sin auditoría exhaustiva de logs; emisiones incidentales de pruebas identificadas. |
| Hooks, skills, loops, prompts y routing | P1/P2 | REVISADA_PARCIALMENTE | settings, hooks reales en harness, generador, routing, contrato y referencias full-audit | V06,V09,V10,V18,R-HOOK | Sin ejecutar todos los loops ni el servicio de revisión/modelos externos. |
| Reportes, utilidades y experimentos | P2/P3 | REVISADA_PARCIALMENTE | edge_information/model_vs_market_report, gate_status, informes y scripts de soporte | R-QUANT-ROI,V18; lint/tipos globales | HTML/JS completo, todos los scripts de investigación y UI no revisados exhaustivamente. |
| Históricos, binarios, cachés y limpieza | P3 | EXCLUIDA | Inventario y preservación por hash; no retirada de archivos | 2/2 antiguos entregables OpenAI iguales al archivo preservado | Sin limpieza ni deserializar artefactos; ausencia de referencias no se usa para autorizar borrado. |
| Pagos, autenticación web pública y SQL | — | NO_APLICABLE | No identificados como arquitectura primaria del sistema inspeccionado | Inventario Python/CLI/CSV | No constituye inventario de servicios externos desconocidos. |

Las tareas se consultaron con aprobación tras un rechazo inicial del sandbox, sin ejecutarlas. Backfill, Capture_Close, Diario_Completo y Validate_OOS mostraban último resultado 0; Dashboard mostraba 267014. Las acciones apuntan a este repositorio. Son estados puntuales con fechas en EVIDENCE, no una garantía de continuidad; el código de Dashboard por sí solo no se eleva a defecto.

## Hallazgos confirmados

### OPENAI-001 — El gate se actualiza después de generar los picks que debía bloquear

- **Severidad HIGH; confianza HIGH; evidencia REPRODUCED; prioridad P1.**
- **Archivo/línea:** `scripts/run_all.py:209`. Referencias: `scripts/run_all.py:239`, `scripts/run_all.py:310`, `src/sqp/pipeline/daily.py:651`.
- **Categoría:** Riesgo / orden de ejecución
- **Activación:** Tras liquidar, un mercado previamente autorizado ya no cumple el criterio; el run diario genera candidatos antes de actualizar el registro.
- **Problema:** run_league consume el registro anterior. La actualización del prediction gate se ejecuta al final, dentro de la generación de informes; --no-report incluso la omite.
- **Evidencia concreta:** Arnés con run_all.main y run_league reales, proveedores sintéticos y ROOT aislado: 4 candidatos con stake positivo, total 13.56; al terminar los tres mercados NBA tienen allowed=false y latched=true; exit 0.
- **Esperado:** Aplicar el veredicto actualizado con la información liquidada antes de dimensionar y publicar los picks; un flag de presentación no debe omitir el control.
- **Observado:** El registro termina cerrado, pero quedan 4 picks accionables generados contra la autorización de ayer.
- **Causa raíz:** La actualización del control de riesgo está situada después de su consumidor y subordinada a if not args.no_report.
- **Consecuencia:** Se publica exposición real en un mercado que ya perdió la autorización; el cierre final no revoca esos candidatos.
- **Controles existentes:** Shadow, pausas y límites de exposición pueden reducir o anular el stake; la revalidación de precios no vuelve a consultar este gate. En el registro real observado no había mercados autorizados, por lo que no se acredita activación productiva actual.
- **Corrección mínima:** Actualizar y validar el gate tras cargar los resultados liquidados y antes del loop de ligas, independientemente de los informes. Un fallo debe conservar la denegación segura; no reutilizar autorizaciones antiguas.
- **Pruebas necesarias:** Integración allowed ayer / falla hoy, camino --no-report y fallo de actualización. Comprobar que se conservan los picks con stake 0 y que el informe coincide con el registro.
- **Criterio de aceptación:** Ningún candidato nuevo conserva stake positivo para un mercado denegado por la evaluación vigente.
- **Limitaciones:** Proveedores y servicios auxiliares sustituidos; no se apostó ni se demostró pérdida económica. Se relajó el cap de plausibilidad en el fixture existente para aislar el gate, sin cambiar configuración productiva.
- **Reproducción:** R-GATES, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-002 — Una actualización concurrente puede desarmar el pestillo sin liberación humana

- **Severidad HIGH; confianza HIGH; evidencia REPRODUCED; prioridad P1.**
- **Archivo/línea:** `src/sqp/risk/prediction_gate.py:473`. Referencias: `src/sqp/risk/prediction_gate.py:507`, `src/sqp/risk/prediction_gate.py:554`, `src/sqp/risk/prediction_gate.py:570`, `scripts/update_prediction_gate.py:103`.
- **Categoría:** Concurrencia / autorización de riesgo
- **Activación:** Dos actualizaciones del mismo registro se solapan; ambas leen el estado abierto. La evaluación que debe cerrar se escribe primero y una evaluación anterior se publica después.
- **Problema:** El reemplazo atómico no serializa lectura, aplicación del pestillo, escritura y rastro. run_all y update_prediction_gate son consumidores alcanzables sin lock compartido.
- **Evidencia concreta:** Intercalado controlado con dos hilos y funciones reales: B deja allowed=false, latched=true, p=0.522284; A reescribe después allowed=true, latched=false, p=8.4101e-12. No se llamó release_prediction_gate_latch.
- **Esperado:** Una vez armado, el pestillo permanece cerrado hasta una liberación humana explícita.
- **Observado:** El segundo reemplazo elimina el pestillo y reabre el mercado automáticamente.
- **Causa raíz:** Lectura-modificación-escritura del estado persistente sin exclusión mutua; atomic_write_json protege cada archivo, no la transacción.
- **Consecuencia:** Se vulnera la regla de no reentrada y se puede autorizar stake después de una salida obligatoria; el log puede seguir registrando el cierre ya borrado.
- **Controles existentes:** Temporales únicos, fsync, sentinel de lectura ilegible y lógica _apply_latch. Ninguno cubre dos lecturas válidas concurrentes. El registro actual observado no tiene mercados abiertos.
- **Corrección mínima:** Usar un lock compartido para la transacción de actualización y liberación, incluyendo estado y rastro; mantener la evaluación costosa fuera cuando sea seguro y aplicar el resultado al estado releído bajo el lock.
- **Pruebas necesarias:** Dos escritores con barreras y decisiones contrapuestas; actualización concurrente con liberación y bloqueo; demostrar conservación del pestillo y del rastro.
- **Criterio de aceptación:** Sin liberación humana, ningún escritor que leyó un estado anterior puede sustituir latched=true por false.
- **Limitaciones:** Intercalado determinista en un proceso; demuestra la carrera pero no mide su frecuencia en producción.
- **Reproducción:** R-GATES, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-003 — Se anulan candidatos aunque su resultado histórico esté disponible

- **Severidad HIGH; confianza HIGH; evidencia REPRODUCED; prioridad P1.**
- **Archivo/línea:** `src/sqp/settlement/runner.py:673`. Referencias: `src/sqp/settlement/runner.py:663`, `src/sqp/settlement/runner.py:675`.
- **Categoría:** Integridad financiera / liquidación
- **Activación:** Candidato de deporte de equipo fuera de la ventana del feed, con al menos 3 días desde inicio, resultado histórico inequívoco y feed vivo saludable con otro evento.
- **Problema:** El fallback de ResultsStore gradúa el stream servido, pero no los candidatos. Estos pasan de scores vivos incompletos a stale_void.
- **Evidencia concreta:** fetch_and_settle real con ROOT temporal: WNBA, stake 100, resultado histórico 70-80. El candidato queda void / pnl 0 / stale_void; el mismo evento servido queda loss.
- **Esperado:** Liquidar el candidato como loss con pnl -100 usando el resultado histórico disponible.
- **Observado:** Se persiste void y pnl 0 mientras el stream servido se liquida correctamente.
- **Causa raíz:** _grade_served_from_history actualiza únicamente el stream separado; no enriquece los resultados usados por settle_candidates.
- **Consecuencia:** El ledger y la banca omiten ganancias o pérdidas reales. La deduplicación posterior por DEDUP_KEY no incluye result, por lo que una corrección ordinaria del mismo pick se descarta.
- **Controles existentes:** El guard de scores vacíos evita anulaciones masivas y tenis sí dispone de fallback; ninguno cubre este caso de equipos con feed no vacío.
- **Corrección mínima:** Intentar también el histórico para candidatos pendientes antes de anularlos; priorizar feed válido y conservar rechazo de emparejamientos ambiguos.
- **Pruebas necesarias:** Candidato y served del mismo evento antiguo: win/loss, three-way, doubleheader ambiguo, feed saludable ajeno y segunda pasada idempotente.
- **Criterio de aceptación:** No se produce stale_void si existe un resultado histórico inequívoco que permite graduar el pick.
- **Limitaciones:** Fixture sintético; no se midió cuántos registros reales fueron afectados ni se regraduaron datos productivos.
- **Reproducción:** R-DATA-A, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-004 — La calibración de cuartos asiáticos aprende un objetivo distinto del precio

- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** `src/sqp/calibration/calibrator.py:656`. Referencias: `src/sqp/markets/settlement_math.py:29`, `src/sqp/models/distributions.py:285`, `src/sqp/pipeline/probabilities.py:194`.
- **Categoría:** Cuantitativo / calibración
- **Activación:** Entrenamiento por liga/mercado con líneas x.25/x.75 y resultados half_win o half_loss.
- **Problema:** El fit y sus métricas excluyen todas las medias liquidaciones. El precio analítico representa win_units/(win_units+loss_units), no P(full win | full win o full loss).
- **Evidencia concreta:** 100 eventos Over 2.25: 60 win, 20 loss, 20 half_loss y p=2/3. Al interceptar la entrada al fit llegan 80 filas con media del target 0.75; el contrato exige 60/(60+20+10)=0.6666667.
- **Esperado:** Ajuste y validación coherentes con las unidades ganadas/perdidas de la liquidación.
- **Observado:** Se eliminan selectivamente 20 resultados y se cambia el objetivo a 0.75.
- **Causa raíz:** Filtro binario win/loss heredado en train_market_calibrators, sin ponderación de medias liquidaciones.
- **Consecuencia:** Se pueden entrenar y evaluar calibradores contra un objetivo sesgado y luego aplicarlos a probabilidades de cuartos. El servicio calibra por liga/mercado sin distinguir la línea.
- **Controles existentes:** Split por evento, mínimos de eventos, ECE/Brier, monotonía/extremos/resolución, staging y promoción supervisada. Ninguno corrige el target filtrado antes del split.
- **Corrección mínima:** Incluir las medias con target direccional y peso 0.5 en fit y métricas; alternativamente excluir todos los cuartos tanto del entrenamiento como de la aplicación hasta soportar su semántica.
- **Pruebas necesarias:** Caso 60/20/20, espejo half_win, spreads y totals, ponderación del holdout y regresión para enteros/medios.
- **Criterio de aceptación:** Fit y métricas reproducen el contrato de win_units/loss_units y no seleccionan la muestra según si el resultado fue parcial.
- **Limitaciones:** Se interceptó el fit y se deshabilitó la revalidación del registro en memoria para no escribir artefactos. No se acredita que un calibrador defectuoso esté promovido ni su daño económico.
- **Reproducción:** R-QUANT-CAL, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-005 — El análisis de ROI realizado elimina medias pérdidas y puede invertir el signo

- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** `src/sqp/evaluation/edge_information.py:101`. Referencias: `src/sqp/evaluation/edge_information.py:120`, `scripts/model_vs_market_report.py:138`, `scripts/research/measure_price_floor_preregistration.py:125`, `src/sqp/settlement/settle.py:133`.
- **Categoría:** Cuantitativo / evaluación de estrategias
- **Activación:** edge_ladder o edge_signal evalúan una política con half_win/half_loss.
- **Problema:** prepare conserva solo win/loss y calcula el ROI sobre el subconjunto sobreviviente; las medias tienen P&L real y forman parte del denominador canónico.
- **Evidencia concreta:** Una victoria y 10 half_loss, cuota 2, stake plano: edge_ladder reporta n_rows=1, n_events=1, roi_flat=1.0; el ROI contractual es (1-10*0.5)/11=-0.3636364.
- **Esperado:** Incluir el P&L parcial y la unidad apostada correspondiente; aquí -36.36% sobre 11 apuestas.
- **Observado:** ROI +100% sobre una sola apuesta.
- **Causa raíz:** Proyección binaria compartida por métricas de acierto y métricas económicas, con exclusión dependiente del resultado.
- **Consecuencia:** Los informes y experimentos de suelo de precio pueden valorar favorablemente una política perdedora.
- **Controles existentes:** Deduplicación por pick, finitud y bootstrap agrupado por evento; operan después de haber eliminado las medias y no evitan el sesgo.
- **Corrección mínima:** Usar la semántica canónica de liquidación para ROI y denominadores; separar explícitamente la muestra/definición del acierto binario.
- **Pruebas necesarias:** Fixtures con ambas medias, mezcla con win/loss/push/void y comparación de ROI con realized_roi_parts a stake unitario; comprobar escalera, señal e intervalos.
- **Criterio de aceptación:** El ROI de cada subconjunto económico coincide con el ledger canónico; las medias no desaparecen del conteo de apuestas resueltas.
- **Limitaciones:** No se recalcularon conclusiones de experimentos productivos. El hallazgo se refiere al ROI realizado; no se sustituye el criterio EV esperado del prediction gate.
- **Reproducción:** R-QUANT-ROI, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-006 — Tres stores históricos pierden escrituras concurrentes

- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** `src/sqp/storage/results_store.py:57`. Referencias: `src/sqp/storage/starters.py:130`, `src/sqp/storage/starter_fip.py:34`.
- **Categoría:** Concurrencia / integridad de datos
- **Activación:** Dos backfills del mismo store y liga se solapan, por ejemplo el manual y el programado.
- **Problema:** Ambos hacen lectura, merge y reemplazo completo sin lock compartido.
- **Evidencia concreta:** Intercalado A prepara, B persiste, A persiste: en ResultsStore, StartersStore y StarterFIPStore ambos retornan éxito, pero ['seed','A','B'] termina como ['seed','A'].
- **Esperado:** Conservar la unión de las escrituras completadas.
- **Observado:** B desaparece silenciosamente en los tres stores.
- **Causa raíz:** El reemplazo atómico no serializa la transacción completa de lectura-modificación-escritura; los callers tampoco añaden exclusión.
- **Consecuencia:** Pérdida de resultados, abridores o FIP usados por los modelos; requiere reingestión.
- **Controles existentes:** Temporales únicos, fsync, os.replace y deduplicación secuencial. Evitan truncados/duplicados, no actualizaciones perdidas.
- **Corrección mínima:** Adquirir locked(p) alrededor de lectura, merge y escritura; crear antes el directorio y mantener los fetches fuera del lock.
- **Pruebas necesarias:** Dos escritores con barrera por store, unión de claves distintas, política de actualización de la misma clave y timeout seguro.
- **Criterio de aceptación:** Ninguna operación completada desaparece por otra escritura concurrente de claves distintas.
- **Limitaciones:** Intercalado controlado en un proceso, no medición de incidencia en producción.
- **Reproducción:** R-DATA-B, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-007 — Un error HTTP de boxscore borra FIP históricos válidos

- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** `src/sqp/providers/mlb_statsapi.py:123`. Referencias: `src/sqp/storage/starter_fip.py:34`.
- **Categoría:** Integración externa / integridad de datos
- **Activación:** Reingestión de un juego existente cuyo boxscore responde HTTP 500 con JSON de error sin teams.
- **Problema:** La llamada .json() no comprueba el estado HTTP. El error se convierte en una fila con nombres y FIP vacíos que reemplaza la fila válida.
- **Evidencia concreta:** Schedule simulado 200 y boxscore 500 {'message':'Internal Server Error'}; el proveedor emite ambos FIP=None y save sustituye los valores previos 3.2/4.1 por NaN.
- **Esperado:** Rechazar o reintentar la respuesta fallida y preservar el registro anterior.
- **Observado:** El backfill devuelve una actualización vacía y se pierden ambos FIP.
- **Causa raíz:** Omisión de raise_for_status/validación de estructura en boxscore, combinada con keep='last' incondicional.
- **Consecuencia:** Un fallo transitorio destruye observaciones históricas y altera consumidores futuros del store.
- **Controles existentes:** Schedule usa _get_with_retry, pero boxscore no; su try/except no detecta un HTTP de error cuyo JSON se decodifica. pitcher_bound=0.0 en ratings limita impacto inmediato en picks, no la pérdida de datos.
- **Corrección mínima:** Usar el helper de HTTP/reintentos y validar que el payload sea un boxscore antes de emitir una fila; una respuesta fallida no debe convertirse en actualización vacía.
- **Pruebas necesarias:** Reingestión con datos previos ante 429/500 JSON, timeout, payload inválido y boxscore válido.
- **Criterio de aceptación:** Los fallos del proveedor preservan datos previos; los boxscores válidos siguen actualizando.
- **Limitaciones:** Transporte simulado, sin llamada a MLB ni cuantificación de filas reales afectadas.
- **Reproducción:** R-DATA-C, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-008 — El hook descarta una revisión fallida sin salida ni reintento

- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** `.claude/hooks/crossreview-on-stop.sh:96`. Referencias: `.claude/hooks/crossreview-on-stop.sh:17`, `.claude/hooks/crossreview-on-stop.sh:101`, `.claude/settings.json:1`.
- **Categoría:** Operación / control de revisión independiente
- **Activación:** Hay marcador pendiente, Git y Codex resolubles, pero codex review termina con código no cero y sin stdout/stderr.
- **Problema:** La salida vacía retorna antes de evaluar rc, después de eliminar el marcador.
- **Evidencia concreta:** Cuerpo real del hook en scratch, funciones Git/Codex simuladas; Codex devuelve 7 sin salida: hook_exit=0, stdout='', stderr='', marker_exists=false.
- **Esperado:** Comunicar que la revisión no se ejecutó y conservar/restaurar el marcador, como hace su rama de fallo con texto.
- **Observado:** Éxito silencioso y revisión pendiente perdida.
- **Causa raíz:** Se comprueba la ausencia de texto antes del código de salida.
- **Consecuencia:** El cambio de riesgo queda sin revisión cruzada y el siguiente turno no la reintenta.
- **Controles existentes:** El hook está cableado a Stop, conserva rc y recupera fallos con texto. Esa rama queda omitida en el caso reproducido; CI no repone esta revisión.
- **Corrección mínima:** Procesar primero rc!=0. Definir además qué hacer con rc=0 y salida vacía, sin tratarlo implícitamente como evidencia de revisión.
- **Pruebas necesarias:** Hook real con (7,''), error con texto y veredicto válido; comprobar aviso y persistencia del marcador. Cubrir explícitamente el contrato (0,'').
- **Criterio de aceptación:** Una revisión fallida nunca pierde silenciosamente el marcador y puede reintentarse.
- **Limitaciones:** No se invocó el servicio Codex ni se observó este disparador en un turno productivo.
- **Reproducción:** R-HOOK, con comando, salida y código de salida en EVIDENCE.json.

### OPENAI-009 — La simulación Poisson trata los cuartos asiáticos como apuestas binarias

- **Severidad LOW; confianza HIGH; evidencia REPRODUCED; prioridad P3.**
- **Archivo/línea:** `src/sqp/simulation/monte_carlo.py:53`. Referencias: `src/sqp/simulation/monte_carlo.py:57`, `src/sqp/models/distributions.py:285`.
- **Categoría:** Matemáticas / API de simulación
- **Activación:** simulate_poisson_game recibe spreads o totals x.25/x.75.
- **Problema:** Las comparaciones directas contra la línea fraccionaria ignoran las medias victorias/derrotas; total!=2.25 siempre se cumple con marcadores enteros.
- **Evidencia concreta:** lambda_home=1.5, lambda_away=1, total=2.25, 500000 simulaciones, seed=42: MC Over=0.45649 frente a 0.5233048136583535 del analítico contractual (reproducción final del agente principal).
- **Esperado:** Probabilidad de decisión ponderada por unidades ganadas/perdidas, consistente con la liquidación asiática.
- **Observado:** Diferencia de 6.68 puntos porcentuales por semántica, no fluctuación muestral.
- **Causa raíz:** La simulación no divide la línea ni acumula unidades parciales.
- **Consecuencia:** La API y el oráculo usado para contrastes de auditoría devuelven probabilidades incorrectas para cuartos.
- **Controles existentes:** Seed y pruebas de enteros/medios; no cubren cuartos. Solo se encontraron consumidores en tests/API, no en el pipeline productivo.
- **Corrección mínima:** Compartir la semántica de unidades parciales con settlement_math o rechazar explícitamente cuartos hasta soportarlos.
- **Pruebas necesarias:** Comparar ambos lados de spreads/totals .25/.75 con el analítico dentro del error Monte Carlo y conservar los casos enteros/medios.
- **Criterio de aceptación:** La simulación y el contrato analítico coinciden dentro del error muestral.
- **Limitaciones:** Sin impacto productivo o pérdida económica demostrados; por ello LOW.
- **Reproducción:** R-QUANT-MC, con comando, salida y código de salida en EVIDENCE.json.

## Validación ejecutada

Makefile se inspeccionó: check encadena lint, types y test. Se ejecutaron herramientas por separado con cachés aisladas, sin instalar ni ejecutar los BAT productivos. Los comandos literales, códigos y arneses están en EVIDENCE.json.

| Control | Resultado |
|---|---|
| Pipeline/riesgo/frescura/revalidación | 216 passed |
| Cuantitativo, grupo 1 | 99 passed |
| Cuantitativo, grupo 2 | 101 passed |
| Datos, liquidación y proveedores | 302 passed |
| Hooks, routing, sincronización e instalación | 118 passed |
| Contratos históricos y gate_status | 8 passed |
| Ruff | exit 0, All checks passed |
| MyPy | exit 0, 106 archivos sin problemas |
| Sync y routing | exit 0 ambos |
| pip check | exit 0, sin incompatibilidades detectadas |
| CI remoto | ENVIRONMENTAL_FAILURE: gh ausente; NOT_VERIFIABLE |
| Programador de tareas | Acceso inicial denegado; reintento aprobado exit 0 |

La primera batería dio **72 passed y 45 errores de setup** por WinError 5 al gestionar `.codex-tmp/pytest` preexistente. Se repitió su alcance, ampliado, con un basetemp nuevo; terminó en 216 passed. Los 72 no se suman otra vez. Un selector de prueba histórica incorrecto del auditor produjo “no tests ran”; se corrigió y las 8 pruebas pasaron. Ambos incidentes están conservados, sin atribuirlos al código ni ocultarlos como resultados verdes.

Las reproducciones se ejecutaron con éxito del arnés y observaron resultados incorrectos del producto. Esto no contradice que las pruebas existentes pasen: faltan casos discriminantes. No se demostró NEW_REGRESSION causada por cambios de esta auditoría; se revisó el snapshot existente.

## Comparación histórica posterior al diagnóstico

Fuentes explícitas:

- `audit/audit-2026-09-22-r2/FINDINGS.md`, identidad audit-2026-09-22-r2, SHA256 `2105cdbf7868431f255fd28d3d8716c1dee4eaddada598d250be3f9802652f19`.
- `audit/audit-2026-09-22-r2/openai/REPORT.md`, identidad interna **audit-2026-09-18**, SHA256 `a593000e9f5644a6b34879c980b4ea90a96bd3617118d043030da1b4221db863`. La ubicación archivada no cambia su ronda.

| Identidad histórica | Estado revalidado | Evidencia y límite |
|---|---|---|
| audit-2026-09-22-r2 / AUD-001 | CORREGIDO_EN_EL_ESTADO_INSPECCIONADO | git status no muestra cambios en src/scripts/configs/BAT que activen el guard; solo entregables de auditoría preexistentes. La condición local descrita dejó de estar presente. No predice el estado del árbol ni el resultado de una ejecución futura. |
| audit-2026-09-22-r2 / AUD-002 | CORREGIDO_PARA_EL_DISPARADOR_ORIGINAL | _load_previous_state estricto, sentinel y recuperación conservadora; tests completos prediction_gate y degradation aprobados en V02. La carrera independiente OPENAI-002 de esta ronda sigue abierta; no equivale a pérdida de estado por registro ilegible. |
| audit-2026-09-22-r2 / AUD-003 | CORREGIDO | Código actual distingue K< n <=50 como tolerancia informativa y >50 como error; pruebas específicas de ambas ramas aprobadas en V02. No se revalida ni modifica la decisión estadística del pre-registro. |
| audit-2026-09-22-r2 / AUD-004 | CORREGIDO | full-audit enlaza audit-workflow, conserva guardrails y verification-gate; sync/routing V06/V09/V10 y contratos V18 aprobados. No se ejecutaron loops mutadores. |
| audit-2026-09-18 / OPENAI-001 | CORREGIDO | gate_status usa verdict_table/market_allowed del registro y evaluate_markets para progreso; seis tests CLI en V18 aprobados. No se invocó el CLI contra servicios externos. |
| audit-2026-09-18 / OPENAI-002 | CORREGIDO_PARA_LA_RAIZ_JSON | load_prediction_gate verifica isinstance(payload,dict); pruebas de registros inválidos aprobadas en V02. No certifica validación completa de todos los campos internos; el endurecimiento de tipos internos se conserva como observación separada. |
| audit-2026-09-18 / OPENAI-003 | CORREGIDO | run_all anuncia gate_allowed_markets después de escribir. R-GATES observó 'ninguno' con registro final cerrado, aunque descubrió un defecto distinto de orden en los picks. OPENAI-001 actual tiene otra causa: generación anterior a la actualización. |

Los nueve IDs actuales no tienen equivalencia confirmada con esos siete defectos históricos. Son **nuevos respecto de las fuentes comparadas**, no necesariamente introducidos recientemente en Git. La carrera del gate había quedado como NOT_VERIFIABLE en el informe r18; ahora está reproducida como OPENAI-002. No se renumeran IDs de rondas anteriores. Esta comparación no reabre ni certifica todos los hallazgos de rondas más antiguas citadas indirectamente por esas fuentes; su cierre queda NOT_VERIFIABLE en este trabajo.

## Candidatos no confirmados, descartes y limitaciones

- **NOT_VERIFIABLE:** estado remoto de CI, vulnerabilidades actuales de dependencias, contratos y disponibilidad vivos de proveedores, configuración efectiva heredada por cada proceso programado, todos los modelos instalados y la rentabilidad/impacto económico real. No se instalaron herramientas ni se usaron servicios de pago para suplirlos.
- **INFERRED:** disponibilidad temporal exacta dentro del día para calibradores/features históricos. Se verificaron cortes por fecha y agrupación por evento, pero no se reconstruyó cada timestamp de conocimiento; no se confirma leakage sin ese dato.
- **NOT_VERIFIABLE como extensión del contrato:** tratamiento de medias liquidaciones en el test de signo del prediction gate. El pre-registro describe una evaluación binaria; se observó el filtro, pero no se inventó una nueva regla estadística ni se confundió EV esperado con ROI realizado. OPENAI-005 confirma específicamente un ROI realizado cuyo contrato sí es conocido.
- **INFERRED / endurecimiento:** un registro editado con allowed="false" se considera truthy; R-GATES lo demostró en scratch. Los escritores inspeccionados emiten booleanos y no se estableció un productor legítimo que escriba ese tipo incorrecto. Se conserva la observación, sin elevarla a un décimo defecto operacional confirmado.
- **DISMISSED:** pérdida concurrente en _persist_settled/backfill_settled_file: el lock ya abarca su lectura y escritura. Payload completamente vacío que anule masivamente: scores_trusted lo bloquea. Salida de red bajo OFFLINE_MODE: guard presente. Temporales fijos en atomic: nombres únicos y fsync comprobados.
- **DISMISSED:** leakage por actualización secuencial dentro de un mismo día en builders/backtests revisados: pending/flush evita usar el resultado de ese día. Contaminación entre lados del mismo evento en split de calibración: group_col presente. No implica que toda la disponibilidad histórica esté certificada.
- **DISMISSED:** test demo de calibration_live sin aislamiento: tiene fixture global isolated_pipeline_outputs. Supuesta exposición de literales del detector: sus salidas redactadas y tests no imprimen el secreto. Desincronización actual de prompts/routing: checks aprobados.
- Limpieza: no se identificó un elemento con evidencia suficiente para autorizar eliminación. Se conservan compatibilidad, históricos y artefactos; no se propone borrar por antigüedad o falta de referencias textuales.
- No se ejecutó toda la suite, cobertura instrumental, build Docker, todos los loops, pruebas de UI ni reentrenamiento/backtest productivo. Las áreas parciales no equivalen a una revisión exhaustiva. Datos agregados de la revisión cuantitativa: 27 graded CSV, 30.921 filas, 586 líneas de cuarto y 14 medias liquidaciones; no se volcaron datasets al contexto ni se reconciliaron todos sus resultados.

## Plan priorizado y criterios de cierre

1. **P1 — OPENAI-001/002:** corregir la ubicación y serialización del gate; validar primero los dos arneses, luego integración live, fallos y --no-report. No cambiar umbrales ni liberar mercados durante la corrección. La concurrencia y el orden son causas distintas y ambos criterios deben cumplirse.
2. **P1 — OPENAI-003:** usar el histórico antes del stale_void; validar candidato/served e idempotencia. Determinar por separado y con autorización si existen voids productivos que requieren reconciliación; este diagnóstico no los modifica.
3. **P2 — OPENAI-004/005:** alinear targets, pesos y métricas económicas de medias liquidaciones con el contrato canónico. Validar ambos lados/mercados antes de considerar reentrenamiento o promoción.
4. **P2 — OPENAI-006/007:** serializar stores y rechazar errores de boxscore antes de emitir filas. Mantener fetch fuera del lock; comprobar preservación e idempotencia.
5. **P2 — OPENAI-008:** corregir el orden de comprobaciones del hook y añadir casos de fallo sin salida.
6. **P3 — OPENAI-009:** ajustar la simulación de cuartos y su prueba discriminante.
7. Completar consulta de CI y auditoría de dependencias actuales en un entorno con herramientas disponibles; cubrir áreas parciales según criticidad. No interpretar un test verde como ausencia de defectos o evidencia de rentabilidad.

**Estado final: DIAGNÓSTICO COMPLETADO CON HALLAZGOS. Tres P1 pendientes; sin remediación ejecutada.** La consolidación de ambos auditores y la actualización coordinada del manifest son fases posteriores; este informe no las suplanta.

