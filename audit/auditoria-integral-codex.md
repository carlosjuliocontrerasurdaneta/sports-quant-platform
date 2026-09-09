# Auditoría integral independiente — Sports Quant Platform

**Fecha:** 6 de septiembre de 2026  
**Auditor:** Codex  
**Repositorio:** `C:\dev\3\sports-quant-platform`  
**Estado auditado:** `01993fd7d33f86d8c13a7f9d05715a2fc6091107`, más los deltas externos delimitados en §2.2  
**Dictamen:** **NO PASS: seis defectos confirmados y limitaciones de verificación explícitas.**

## 1. Dictamen ejecutivo

La revisión identifica **tres hallazgos HIGH y tres MEDIUM**, todos con confianza HIGH y evidencia REPRODUCED. Afectan a la integridad de la banca, la concurrencia de la liquidación, la independencia estadística del gate, el emparejamiento del backtest, la invalidación de features y la frescura de cuotas en modo offline.

No se demostró un incidente CRITICAL, una pérdida efectiva de datos operativos durante esta auditoría ni una explotación de seguridad. Los escenarios adversos se ejecutaron exclusivamente con datos sintéticos en directorios temporales. Los defectos describen capacidades de fallo del código actual; no prueban que sus consecuencias hayan ocurrido en producción.

La suite existente termina en **1.547 pruebas aprobadas y una omitida**. Ruff no encuentra incidencias y MyPy valida los 98 archivos de fuente sin errores. La cobertura de líneas de `sqp` es **89,64 %**. Estos resultados son compatibles con los seis defectos: las pruebas existentes no discriminan las condiciones que los activan.

El registro operativo tiene **41 mercados, ninguno autorizado**. Los **134 candidatos** almacenados, generados el 5 de septiembre, suman stake cero. Esta situación limita la exposición económica inmediata, pero el gate es precisamente uno de los controles afectados y no sustituye la corrección de los problemas contables.

El proyecto dispone de una arquitectura modular, separación demo/live, controles de exposición, escrituras atómicas, validación temporal y una suite amplia. Las debilidades confirmadas se concentran en las fronteras entre componentes: validación por archivo frente a validación por movimiento; atomicidad frente a exclusión mutua; línea cotizada frente a ensayo independiente; determinismo frente a identidad del partido; fuente principal frente a dependencias de caché; y lectura offline frente a precio accionable.

## 2. Alcance, preservación y metodología

### 2.1 Alcance autorizado

La solicitud expresa de auditoría integral define como alcance el proyecto completo, no un diff concreto. Por tanto, se incluyen defectos presentes en el estado actual aunque sean anteriores a esta sesión. No se atribuyen a un commit particular sin evidencia causal.

Se inspeccionaron arquitectura, dominio, configuración, proveedores, modelos deportivos, probabilidades, calibración, evaluación, riesgo, persistencia, liquidación, backtesting, informes, automatización, CI, pruebas y documentación operativa.

“Integral” significa cobertura de todas esas áreas mediante inventario, inspección dirigida, pruebas y contraste de datos. No significa demostración formal de cada línea, certificación de cada proveedor ni validación de rentabilidad futura. Las verificaciones no realizadas se identifican expresamente.

### 2.2 Estado del repositorio

Al comienzo, Git mostraba únicamente un archivo local no versionado:

- `audit/model_vs_market_20260906.md`.

Se conservó intacto. El informe solicitado ya existía, fechado el 5 de septiembre; se reemplaza con esta evaluación actualizada. No se reutilizaron sus resultados como evidencia de ejecución de esta sesión.

Se copiaron **529 archivos versionados**, incluyendo 272 archivos Python, a:

`C:\Users\Richard\AppData\Local\Temp\sqp-auditoria-20260906-8iecekla`

La copia excluyó datos operativos, logs, secretos y directorios documentales no necesarios para las pruebas. Se conservaron los archivos de configuración y los contratos auxiliares necesarios para la suite. Un manifiesto SHA-256 permitió comparar posteriormente los archivos copiados con los originales: **ninguna diferencia en la comprobación intermedia posterior a la suite completa**. HEAD permaneció en el commit indicado.

En la comprobación final aparecieron dos modificaciones externas a esta auditoría: `src/sqp/providers/odds_cache.py` y `tests/test_odds_cache.py`. Añaden un piso de cero a la edad de caché y una prueba con mtime posterior al reloj. Se inspeccionó el diff y se validó una segunda copia temporal: **14 pruebas aprobadas y Ruff sin incidencias**. El resultado de 1.547 pruebas y la cobertura pertenecen a la instantánea original; no se presentan como una ejecución completa sobre este delta. La rama offline sigue usando TTL infinito, expresamente conservado por la nueva prueba, por lo que AUD-06 permanece aplicable. Las demás rutas de los hallazgos no cambian.

Después aparecieron otros dos cambios externos: `src/sqp/calibration/calibrator.py` y `tests/test_calibrator.py`. La promoción pasa a denegar metadatos OOS ausentes/ilegibles, salvo override explícito con force. Se inspeccionó su implementación y se ejecutaron las pruebas de promoción sobre la segunda copia: **9 aprobadas, 32 deseleccionadas; Ruff sin incidencias**. Esta corrección queda documentada como cambio externo validado, no como un séptimo defecto pendiente ni como una modificación realizada por Codex. El cierre cubre la instantánea original y estos cuatro archivos de delta; cambios posteriores requieren otra revisión.

La única escritura deliberada en el proyecto original es este informe. No se hicieron commits, cambios de rama, push, despliegues, modificaciones de credenciales ni ejecuciones del pipeline live contra proveedores. Las pruebas que crean repositorios Git de ejemplo lo hacen en el área temporal.

### 2.3 Inventario

Conteo de archivos relevantes por extensión y líneas físicas, incluyendo comentarios:

| Área | Archivos | Líneas |
|---|---:|---:|
| `src` | 98 | 16.175 |
| `scripts` | 61 | 9.228 |
| `tests` | 115 | 22.136 |
| `configs` | 5 | 582 |
| `.github` | 1 | 142 |
| `.claude`, excluyendo el plugin vendorizado superpowers-main | 197 | 10.324 |

Los conteos de scripts incluyen archivos no Python. Se inventariaron además los BAT, Dockerfile, Makefile, manifiestos de dependencias y documentación; no se confunde su inventario con cobertura ejecutada.

### 2.4 Criterios de evidencia

Se aplican los estados de AGENTS.md: REPRODUCED, STATICALLY_VERIFIED, TOOL_DETECTED, INFERRED, NOT_VERIFIABLE y DISMISSED. Solo los dos primeros pueden fundamentar defectos confirmados.

Los hallazgos siguientes tienen resultados observados en ejecuciones controladas. Cuando se sustituyó un proveedor, adaptador o punto de intercalado, se indica qué parte se simuló y qué lógica real produjo el fallo.

## 3. Hallazgos confirmados

### AUD-20260906-01 — Una corrupción parcial del ledger infla la banca

| Campo | Resultado |
|---|---|
| Severidad | **HIGH** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivo | `src/sqp/risk/bankroll.py` |
| Líneas relevantes | 53, 121–125, 127–147 y 223 |
| Activación | Un archivo conserva al menos un PnL numérico, pero otra pérdida contiene un valor ilegible; alternativamente, una retirada tiene un `amount` ilegible. |

**Problema y causa raíz.** `_exigir_pnl_legible` rechaza el archivo únicamente cuando no existe ningún PnL numérico. Si queda uno válido, `realized_pnl` convierte los restantes valores inválidos a NaN y después a cero. `adjustments_total` aplica también `to_numeric(errors="coerce").fillna(0.0)`, sin una validación equivalente por movimiento. La protección frente a un CSV totalmente ilegible no cubre la corrupción parcial.

**Evidencia y comportamiento observado.**

| Caso sintético | Estado válido | Estado tras sustituir un importe por `ERROR` |
|---|---:|---:|
| Banca inicial 1.000; dos pérdidas de −400 | 200 | **600** |
| Banca inicial 1.000; retirada de −400 | 600 | **1.000** |

La llamada real a `apply_dynamic_bankroll` aceptó los **600** del primer caso. No se lanzó `LedgerIntegridadError`, por lo que no se activó la salida conservadora que pone la banca a cero.

**Comportamiento esperado.** Una pérdida o retirada cuyo importe no puede determinarse debe invalidar el saldo verificable, no convertirse en un movimiento de importe cero. Debe preservarse la distinción con los casos legítimos de push/void documentados por el proyecto.

**Consecuencia.** Kelly y los límites de exposición pueden dimensionarse sobre capital sobreestimado. La misma conversión también altera curvas y resúmenes contables. No se encontró esta corrupción en las 1.228 liquidaciones operativas examinadas.

**Corrección mínima propuesta.** Validar importes finitos por fila y según su tipo de movimiento antes de sumar. Ante una pérdida, ganancia o ajuste indeterminado, lanzar `LedgerIntegridadError` indicando archivo y fila; conservar el tratamiento explícito de los estados que admiten cero. No reparar ni completar importes silenciosamente.

**Pruebas necesarias.** Mezcla de PnL válido e inválido; una retirada ilegible entre ajustes válidos; importes NaN/inf; push/void legítimos; comprobación de que `apply_dynamic_bankroll` no devuelve una banca inflada. Las pruebas actuales de ParserError y archivo totalmente inválido no cubren estas variantes.

### AUD-20260906-02 — La liquidación puede perder escrituras concurrentes

| Campo | Resultado |
|---|---|
| Severidad | **HIGH** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivo | `src/sqp/settlement/runner.py` |
| Líneas relevantes | 216–252; lectura de `prior` en 232 y persistencia en 249/251 |
| Activación | Dos liquidaciones de la misma liga se solapan y persisten conjuntos distintos de filas nuevas. |

**Problema y causa raíz.** `_persist_settled` ejecuta lectura, deduplicación, combinación y reemplazo sin adquirir el lock compartido. El temporal único y `os.replace` protegen frente a archivos a medio escribir, pero no impiden que un escritor sustituya el resultado completo de otro. Ni `settle_all.py` ni `settle_bets.py` añaden exclusión alrededor de esa transacción.

**Evidencia.** Se mantuvo intacta la implementación de `_persist_settled` y se instrumentó su llamada a `_atomic_write_csv` para producir un intercalado determinista: A prepara su escritura, B liquida y persiste, A termina. Ambas llamadas finalizan correctamente.

| Resultado | Esperado | Observado |
|---|---|---|
| Eventos persistidos | A y B | **Solo A** |
| Saldo con inicial 1.000 y dos pérdidas de −400 | 200 | **600** |

La ejecución controla el orden de las operaciones; no mide la frecuencia de la carrera en el planificador real.

**Comportamiento esperado.** Serializar la transacción completa por archivo y volver a leer el estado después de adquirir el lock, preservando la unión de liquidaciones e idempotencia.

**Consecuencia.** Pérdida de movimientos del ledger y alteración de banca, ROI y evidencia de calibración. Puede activarse al solapar una liquidación manual con otra ejecución. No se verificó que tal solapamiento haya ocurrido en producción.

**Corrección mínima propuesta.** Usar `locked(out)` desde antes de comprobar/leer el archivo hasta completar la deduplicación y escritura. Mantener el temporal único. Revisar los demás escritores del mismo archivo para que participen en el mismo protocolo.

**Pruebas necesarias.** Dos escritores con una barrera controlada después de la lectura: filas distintas deben sobrevivir; filas repetidas deben aparecer una sola vez. Probar tanto archivo inicialmente ausente como existente y el timeout sin entrada a la sección crítica.

### AUD-20260906-03 — El gate cuenta varias líneas del mismo partido como ensayos independientes

| Campo | Resultado |
|---|---|
| Severidad | **HIGH** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivo | `src/sqp/risk/prediction_gate.py` |
| Líneas relevantes | 172–212, especialmente 208/212; recuento y test en 215–225 |
| Activación | Un evento aporta más de una línea de spreads o totals dentro del mismo mercado evaluado. |

**Problema y causa raíz.** El agrupamiento por `(event_id, market, line)` elimina repeticiones y lados complementarios de una misma línea, pero deja varias unidades del mismo partido. Sus resultados dependen del mismo marcador: dos totales distintos son sucesos anidados, no ensayos independientes. `binomtest` trata esas unidades como observaciones independientes.

No se propone fusionar las líneas por valor absoluto ni confundir contratos de apuestas distintos. El defecto está en la unidad de inferencia estadística, no en conservar la identidad de las cotizaciones.

**Evidencia operativa.** En el historial posterior al preregistro:

| Segmento | Unidades contadas | Partidos |
|---|---:|---:|
| WNBA totals | 66 | 39 |
| WNBA spreads | 67 | 39 |
| NCAAF totals | 39 | 15 |
| MLS spreads | 46 | 30 |
| MLB totals | 174 | 166 |

**Reproducción.** Se generaron 150 eventos, cada uno con líneas 3,5 y 4,5, lados Over/Under, probabilidades complementarias 0,8/0,2, cuotas 1,8/3,0 y probabilidades de mercado 0,625/0,375. El resultado es compatible con ganar ambos Overs. Se conservaron los valores canónicos: mínimo 300 y alpha 0,05/41.

- Con una línea por evento: `n=150`, `allowed=False`, `muestra_insuficiente`.
- Con las dos líneas: **`n=300`, `allowed=True`**, EV medio 0,02 y p-valor aproximadamente `4,909e-91`.
- No se añadió ningún partido independiente.

**Comportamiento esperado.** La replicación de exposición al mismo marcador no debe hacer cumplir un mínimo de evidencia independiente ni fabricar precisión estadística.

**Consecuencia.** Autorización prematura de mercados y posible consumo prematuro de su test único de entrada. Bonferroni y el pestillo no corrigen una unidad estadística inválida. Actualmente todos los mercados operativos siguen denegados.

**Corrección mínima propuesta.** Mantener las líneas en los datos, pero construir una contribución por evento para el test, con una regla fijada de antemano; alternativamente, utilizar una inferencia que trate el evento como grupo dependiente. Documentar/preregistrar el cambio sin elegirlo por el resultado favorable de la muestra observada. No cambiar arbitrariamente los umbrales.

**Pruebas necesarias.** Añadir líneas y snapshots del mismo evento no puede aumentar el número de eventos independientes. Cubrir totales anidados, handicaps que cruzan cero y lados complementarios. Revisar `tests/test_prediction_gate.py:185`: hoy exige `n=2` para dos líneas del mismo evento y consolida precisamente la confusión entre contrato distinto y ensayo independiente.

### AUD-20260906-04 — El backtest cruza resultados de partidos del mismo día

| Campo | Resultado |
|---|---|
| Severidad | **MEDIUM** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivo | `src/sqp/backtesting/roi_engine.py` |
| Líneas relevantes | 134–161, 228–233 y 325 |
| Activación | Dos partidos de la misma pareja y orientación comparten fecha, y el orden de `game_id` no coincide con el cronológico. |

**Problema y causa raíz.** Los resultados se ordenan por fecha, equipos e identificador; el matcher asigna codiciosamente el evento de cuotas más temprano aún disponible. No utiliza el instante del resultado ni demuestra la correspondencia entre identificadores de proveedores. El orden resultante es determinista, pero puede ser incorrecto.

**Evidencia.** Dos eventos sintéticos, a las 10:00 y 18:00, tienen resultados locales de 10–0 y 0–10, respectivamente. El identificador del segundo ordena antes que el del primero. Se empleó un adaptador de probabilidades constantes para aislar el emparejamiento; selección, liquidación y PnL utilizaron el código real.

| Evento | Resultado esperado del pick local | Resultado observado |
|---|---|---|
| 10:00 | win, +20 | **loss, −20** |
| 18:00 | loss, −20 | **win, +20** |

El rastro muestra además que el resultado de las 18:00 se incorpora mediante `adapter.observe` antes de estimar el evento de las 18:00. Con un adaptador que aprende de esas filas, esa ruta permite contaminación por el resultado del propio evento.

**Comportamiento esperado.** Una correspondencia demostrada por identidad/tiempo, o abstención explícita si el vínculo es ambiguo. El histórico consumido por el modelo debe ser anterior al corte de la predicción.

**Consecuencia.** Etiquetas y PnL por apuesta incorrectos; posible sesgo cuantitativo. En esta reproducción el PnL agregado se cancela por simetría: no se afirma que el ROI total haya cambiado. Con precios, selecciones o stakes diferentes esa cancelación no está garantizada.

**Corrección mínima propuesta.** Conservar y usar identidad y tiempos verificables; no resolver ambigüedades por orden de ID. Si el histórico solo tiene día, omitir emparejamientos ambiguos y evitar actualizaciones intradía cuyo orden no pueda demostrarse. `history_scores_map` ya adopta una abstención conservadora ante dobles jornadas ambiguas.

**Pruebas necesarias.** IDs no cronológicos, horas explícitas, doble jornada sin hora verificable, cuotas asimétricas y comprobación del conjunto de resultados observado antes de cada estimación. La invariancia al barajar la entrada no demuestra que el emparejamiento sea correcto.

### AUD-20260906-05 — Actualizar abridores no invalida la caché de features MLB

| Campo | Resultado |
|---|---|
| Severidad | **MEDIUM** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivo | `src/sqp/storage/feature_store.py` |
| Líneas relevantes | 58–68, 71–79 y 116–139 |
| Activación | Existe un dataset MLB cacheado y cambia `starters_mlb.csv` sin cambiar `results_mlb.csv`; se reconstruye sin `force=True`. |

**Problema y causa raíz.** `_mlb_results_df` consume resultados y abridores. Sin embargo, `_source_hash` solo incorpora el archivo de resultados. El manifest no refleja todas las entradas que determinan el dataset.

**Evidencia.** Se construyó un dataset de cuatro partidos con el mismo abridor y luego se sustituyó el abridor del cuarto partido:

| Resultado | Caché reutilizada | Reconstrucción forzada |
|---|---|---|
| Abridor local | Pitcher H | New starter |
| Inicios previos del abridor | **3** | **0** |

Después de la actualización, `dataset_is_current` devolvió **True**.

**Comportamiento esperado.** Invalidar y reconstruir el dataset cuando cambia cualquiera de sus fuentes relevantes, incluidas correcciones y nuevas incorporaciones de abridores.

**Consecuencia.** Entrenamientos o comparaciones ML pueden usar identidad y estadísticas obsoletas sin aviso. El subsistema ML está documentado como experimental y no alimenta actualmente los candidatos; ese hecho limita la exposición inmediata. `force=True` evita el problema en una ejecución concreta.

**Corrección mínima propuesta.** Incorporar el contenido y la presencia/ausencia de `starters_mlb.csv` a la huella de entradas MLB. Revisar que la huella de código cubra también los helpers que realmente transforman esas entradas.

**Pruebas necesarias.** Dataset vigente tras construcción; invalidación al corregir un abridor, añadir el archivo antes ausente o cambiar una dependencia relevante; reutilización cuando nada cambia; equivalencia con reconstrucción forzada.

### AUD-20260906-06 — Offline omite el límite de frescura y permite candidatos live con cuotas vencidas

| Campo | Resultado |
|---|---|
| Severidad | **MEDIUM** |
| Confianza | **HIGH** |
| Evidencia | **REPRODUCED** |
| Archivos | `src/sqp/providers/odds_api.py`; `src/sqp/pipeline/daily.py` |
| Líneas relevantes | `odds_api.py:143`; `daily.py:245–269`, 615–624 y 689 |
| Activación | Ejecución live con `OFFLINE_MODE` activo y respuesta cacheada de un evento futuro más antigua que la política de frescura. |

**Problema y causa raíz.** El pipeline acota `client.cache_ttl`, pero `OddsAPIClient._get` lo sustituye por infinito en modo offline. La antigüedad original no se propaga para impedir el uso como precio accionable; el candidato recibe un sello de generación nuevo y etiqueta real.

**Contrato.** El límite procede de `revalidation_price_max_age_min`, con valor canónico de 90 minutos. `tests/test_frescura_cuotas_diario.py` declara expresamente que un precio no accionable para mantener un pick tampoco lo es para crearlo.

**Evidencia.** Ejecución real de `run_league`, con cliente offline y caché temporal de **240 minutos**, para un evento que empieza dos horas después. Solo se sustituyó el adaptador por una salida fiable y constante de 0,55/0,45; no hubo red.

- El log anuncia que reduce el TTL de 21.600 a **5.400 segundos**.
- El cliente devuelve igualmente la respuesta de cuatro horas.
- Se persiste un candidato con **stake 20**, `data_label="real"` y `generated_at` actual.

Los gates se desactivaron en esta configuración sintética para aislar la frescura. Con el registro operativo actual, el gate evita stake positivo; no impide por sí mismo presentar cuotas viejas como salida recién generada.

**Comportamiento esperado.** Offline puede permitir consultar una respuesta antigua, pero no convierte su precio en accionable para la ruta live.

**Consecuencia.** Picks y decisiones basados en cuotas que incumplen la política del proyecto. Puede afectar stakes cuando los restantes controles permiten el mercado.

**Corrección mínima propuesta.** Separar la lectura offline de la autorización del precio: propagar el instante de captura y aplicar la misma comprobación de antigüedad antes de producir un candidato accionable, o restringir explícitamente ese replay a una salida sin stake y correctamente identificada.

**Pruebas necesarias.** Integración cliente–pipeline con caché por debajo y por encima del límite, modo offline/live y evento futuro. Las pruebas que buscan el texto `client.cache_ttl = acotado` en el fuente no prueban que ese valor gobierne la lectura efectiva.

## 4. Resultados por componente

| Componente | Verificaciones y conclusión |
|---|---|
| Arquitectura y dominio | Entidades y adaptadores separan evento, línea, probabilidad y candidato. La ruta de servicio usa adaptadores deportivos; la inferencia ML sigue separada. No se confirmó un defecto adicional de composición. |
| Configuración | YAML seguro, precedencia de entorno, validación de modo/banca y rechazo de configuración ausente. La política versionada activa prediction gate, banca dinámica y calibración; desactiva shadow, CLV gate y promoción automática. No se leyó el contenido secreto de .env: no se certifican todos los valores efectivos del entorno. |
| Proveedores | Se revisaron Odds API, ESPN, MLB Stats API, caché, retries, fechas y mapeos. Se ejercitaron mediante tests/mocks. Se confirmó AUD-06; disponibilidad, cuotas y respuestas actuales de proveedores externos no se verificaron. |
| Mercados | Conversión de cuotas, descarte de precios no finitos, mercados completos para retirar vig, orientación del spread y probabilidades compartidas live/backtest cubiertos por código y suite. No se confirmó un nuevo defecto en esas primitivas. |
| Modelos deportivos | Elo, márgenes normales, Poisson/binomial negativa, ajustes Dixon-Coles/correlación, scoring, descanso, parques, abridores y tenis revisados mediante implementación y pruebas. Se preserva el carácter estimado de las probabilidades. Las aproximaciones documentadas no se reportan como bugs sin demostrar incumplimiento. |
| Simulación | Pruebas analíticas/Monte Carlo aprobadas. Esto valida coherencia de fórmulas bajo fixtures, no exactitud predictiva empírica de cada liga. |
| Features y ML | Builders temporales, separación de etiquetas, pipelines de entrenamiento, TimeSeriesSplit y comparación por holdout inspeccionados. AUD-05 invalida la afirmación de que la caché siempre refleja sus fuentes. No se entrenaron nuevos modelos sobre datos operativos. |
| Calibración | Split por evento, separación temporal, colapso de repeticiones, objetivo adjusted_probability, staging, gates estructurales y promoción revisados. La selección de la observación reciente usa served_at. CLI y staging diario comparten ahora objetivo. No se demuestra rentabilidad por una mejora de ECE/Brier. |
| Gate y evaluación | Hay preregistro, Bonferroni, test único de entrada y pestillo. La dependencia residual entre líneas invalida parte de la evidencia estadística: AUD-03. Bootstrap por evento en evaluación es una defensa distinta y no repara automáticamente el test de signo. |
| Riesgo y banca | Kelly valida finitud de banca/probabilidad/precio, con límites por apuesta y exposición. AUD-01 muestra que sigue faltando integridad contable por movimiento. |
| Persistencia | Temporales únicos, fsync y reemplazo atómico mejoran durabilidad y evitan archivos parciales. El lock ya aborta al agotar espera. AUD-02 demuestra que un consumidor contable importante no lo utiliza. |
| Liquidación | Grading por mercado, pushes, voids, identidad normalizada, deduplicación y conciliación de esquema revisados. El fallback histórico se abstiene ante ambigüedad. No se ejecutó liquidación operativa. |
| Backtesting | Walk-forward, periodo OOS, probabilidad compartida y caps revisados. Las limitaciones documentadas de calibración/gates/clima frente a producción no se confunden con paridad completa. AUD-04 afecta identidad y temporalidad del replay. |
| CLV y revalidación | Cierre anterior al comienzo, filtro canónico de 90 minutos, finitud de agregados y revocación conservadora revisados. No se inventaron ventanas alternativas ni se afirmó cobertura universal de cierres. |
| Informes y dashboard | Pruebas de historial, vistas de decisión, filtros, diagnósticos y HTML aprobadas. Se inspeccionó el escape del JSON embebido y de textos de tabla. No se realizó navegación interactiva ni una prueba de explotación en navegador. |
| Operación | BAT encadena settle antes de run, aborta en fallos bloqueantes y registra centinelas. Se revisaron presupuesto, archivo, limpieza y apertura de dashboard. La consulta al planificador no produjo información utilizable; no se certifican tareas instaladas. |
| CI y empaquetado | Makefile inspeccionado; check equivale a lint, tipos y tests. CI declara Linux 3.11–3.14 y Windows 3.12. Docker ejecuta con usuario no root. No se construyó la imagen ni se consultó el último run remoto de CI. |
| Automatización de revisión | Se inventariaron scripts y contratos, se inspeccionaron protocolo/procedencia y puntos de ejecución, y se ejecutaron sus tests. No se lanzaron revisores externos, agentes ni publicaciones/issues. |
| Documentación | README, contratos de configuración, preregistros, instrucciones y reportes previos contrastados con código. Algunos comentarios describen estados históricos; solo se reportan como defectos las consecuencias de corrección demostradas arriba. |

## 5. Datos operativos: comprobaciones directas

Se utilizaron `pandas.read_csv`, lectura JSON y hashes. No se invocaron sobre producción los loaders que pueden poner archivos en cuarentena o reparar registros.

### 5.1 Ledger

- 27 archivos de liquidación; **1.228 filas**, todas etiquetadas `real`.
- 746 loss, 464 win y 18 push.
- PnL acumulado: **−84,25**.
- Dos ajustes manuales con suma **0**.
- Con la banca inicial versionada de 1.000, el saldo aritmético es **915,75**; no se presenta como verificación del valor BANKROLL efectivo en .env.
- Cero errores de parseo, PnL no finitos, stakes negativos/no finitos o cuotas no utilizables en estos archivos.

“Real” es una etiqueta de procedencia, no prueba de ejecución en una casa de apuestas. Tampoco debe interpretarse el hit rate agregado como rentabilidad: muchas observaciones tienen stake cero.

### 5.2 Stream servido y graduado

| Control | Servido | Graduado |
|---|---:|---:|
| Filas | 23.905 | 20.048 |
| Duplicados por evento/mercado/selección/línea/día de generación | 0 | 0 |
| generated_at inválido | 0 | 0 |
| start_time inválido | 0 | 0 |
| Generación igual o posterior al inicio | 0 | 0 |
| model_probability fuera de [0,1] o ausente | 0 | 0 |

Los 23 archivos graduados contienen 1.620 eventos: 10.547 loss, 8.953 win, 286 push y 262 void. El número de filas no equivale a tamaño muestral independiente.

La ausencia de generación posterior al inicio verifica esos sellos, no la disponibilidad histórica de cada feature ni la antigüedad de cada cotización subyacente.

### 5.3 Históricos, candidatos y registros

Se inspeccionaron 21 archivos `results_*.csv`: no contienen duplicados bajo la clave disponible `(date, home, away, game_id)`. Las fechas máximas varían por temporada y fuente; no se declara “obsoleto” un histórico solo porque una liga esté fuera de temporada. Las fuentes por tour de tenis y por liga de equipos son distintas.

Los candidatos actuales son 134 filas de 14 archivos no vacíos, generadas el 5 de septiembre, con stake agregado cero. El registro de prediction gate fue generado el **5 de septiembre a las 15:11:26 UTC**, conserva 41 entradas y no autoriza ninguna.

El registro de calibración enumera `mlb_h2h_pergame`, `mlb_spreads`, `mlb_totals` y `wnba_spreads`; sus cuatro artefactos existen. Solo se encontró sidecar SHA-256 para wnba_spreads y coincide. Los otros tres carecen de esa evidencia de integridad, una situación admitida por compatibilidad legacy. No se interpretó la ausencia como prueba de manipulación.

La clave `mlb_h2h_pergame` no equivale a `mlb_h2h`: la ruta estándar construye `league_market`. Por tanto, cuatro entradas en el registro no significan cuatro calibradores aplicados a los mercados estándar. No se deserializaron esos artefactos de producción para esta auditoría.

## 6. Validación ejecutada y clasificación

Entorno: **Windows, Python 3.14.4**, NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, scikit-learn 1.9.0, pytest 9.0.3, Ruff 0.15.14 y MyPy 2.1.0.

Todos los comandos de test/lint/tipos siguientes se ejecutaron en la copia temporal.

| Validación | Resultado | Clasificación |
|---|---|---|
| Pruebas focalizadas: bankroll, storage, calibration_data y html_report | **80 passed** en 21,24 s | Sin fallo final |
| `ruff check --no-cache src scripts tests` | All checks passed | Sin fallo |
| `mypy --cache-dir nul src` | Sin incidencias en 98 archivos | Sin fallo |
| Suite completa con cobertura | **1.547 passed, 1 skipped** en 2.286,82 s | Sin fallo |
| Delta externo final: tests de caché y frescura; Ruff de los dos archivos modificados | **14 passed** en 20,35 s; Ruff sin incidencias | Sin fallo en el alcance del delta |
| Segundo delta externo: selección de pruebas de promoción y Ruff | **9 passed, 32 deselected** en 12,47 s; Ruff sin incidencias | Sin fallo en el alcance del delta |
| Seis escenarios adversos de este informe | Comportamientos incorrectos observados | **PRE_EXISTING_FAILURE** del estado auditado |
| pip-audit sobre requirements.lock | Consulta incompleta por permisos/red y posterior ConnectionResetError | **ENVIRONMENTAL_FAILURE**; seguridad de dependencias **NOT_VERIFIABLE** |
| Consulta de tareas SQP instaladas | Sin resultado utilizable, código de salida 1 | **NOT_VERIFIABLE** |

Comando de suite completa:

```powershell
python -B -m pytest -q --tb=short -p no:cacheprovider --basetemp ./audit-pytest-full --cov=sqp --cov-report=term --cov-report=json:audit-coverage.json
```

La omisión corresponde al caso parametrizado que intenta tratar severity como texto libre, cuando es un enum cerrado: `tests/test_review_v2.py:228`. No se contabiliza como prueba aprobada.

La primera ejecución focalizada utilizó el directorio temporal predeterminado de pytest y terminó con 9 passed y 71 errores de preparación por acceso denegado a `pytest-of-Richard`. Dos intentos elevados no localizaron las rutas relativas de tests. La ejecución posterior con basetemp específico dentro de la copia aislada resolvió el problema. Son fallos del entorno/ejecución, no regresiones atribuidas al código.

Una consulta de Git desde un subproceso temporal detectó propiedad distinta del repositorio. La verificación posterior usó `git -c safe.directory=...` solo para esa invocación: no se cambió configuración global. Las advertencias de permisos del ignore global no se clasifican como defectos del proyecto.

No se ejecutó `make check` porque ya se habían ejecutado sus tres verificaciones con opciones de aislamiento. No se instalaron ni actualizaron dependencias.

### 6.1 Cobertura y sus límites

Se ejecutaron **6.358 de 7.093 líneas instrumentables** de `src/sqp`; 735 quedaron sin ejecutar. La medición es de líneas, no de ramas. No incluye una medición independiente de cobertura de los scripts.

| Módulo | Cobertura aproximada |
|---|---:|
| distributions, Monte Carlo, métricas de calibración | 100 % |
| adapters | 99 % |
| probabilities | 98 % |
| bankroll | 95 % |
| roi_engine | 95 % |
| prediction_gate | 94 % |
| feature_store | 92 % |
| html_report | 91 % |
| calibrator | 89 % |
| settlement.runner | 87 % |
| revalidation | 87 % |
| pipeline.daily | 85 % |
| espn_tennis | 76 % |
| ml_predict | 71 % |
| mlb_statsapi | 43 % |

La cobertura alta de bankroll y del gate no impidió los hallazgos. Son necesarios oráculos de corrección e integración: ejecutar una línea de código no valida todas sus precondiciones.

## 7. Seguridad, sospechas descartadas y aspectos no verificables

### 7.1 Seguridad

Se inspeccionaron los usos de subprocess, deserialización joblib, YAML, peticiones HTTP y generación HTML en fuente/scripts. No se confirmó en esas rutas un nuevo caso de ejecución arbitraria o exposición de credenciales. Esta afirmación no equivale a un escaneo exhaustivo del historial Git ni a una prueba de penetración.

La clave Odds API se añade a la petición; los errores de conexión se resumen y los errores HTTP se vuelven a emitir con query redactada. YAML usa carga segura. No se encontró `shell=True` en el barrido de fuente/scripts. Se revisaron las capacidades de escritura del workflow de alerta; no se activó el envío de issues.

Joblib presupone artefactos locales de confianza. La comprobación de hash es informativa y puede permitir carga aun cuando falle. Sin demostrar entrada de artefactos controlados por un atacante, no se convierte esa observación en una vulnerabilidad explotable confirmada.

### 7.2 Registro de candidatos no confirmados

| Candidato | Estado | Resolución |
|---|---|---|
| El lock permite entrar sin exclusión al agotar timeout | **DISMISSED** para el código actual | Ahora lanza LockNoAdquiridoError y las pruebas pasan. AUD-02 afecta a un escritor que no adquiere ese lock. |
| Un lock vivo envejecido permite una segunda entrada en Windows | **DISMISSED** para la reproducción realizada | Al envejecer controladamente su mtime, Windows impidió borrar el archivo abierto con WinError 32. No se reprodujo doble entrada. |
| Recuperación de locks viejos bajo semántica POSIX | **NOT_VERIFIABLE** | No se ejecutó una reproducción Linux. El comportamiento observado en Windows no valida POSIX. |
| CLI manual y staging diario calibran variables diferentes | **DISMISSED** | Ambos usan adjusted_probability en fuentes servidas; backtest conserva su semántica explícita. |
| La promoción omite el control de muestra cuando faltan metadatos OOS | **DISMISSED** para el delta de cierre | La instantánea inicial tenía esa omisión; la corrección externa inspeccionada ahora deniega metadatos ausentes/ilegibles. Las pruebas de promoción y del override explícito pasan. |
| La última observación de calibración se decide solo por fecha del partido | **DISMISSED** | El código actual incorpora served_at para el desempate y la suite focalizada pasa. |
| BANKROLL=inf atraviesa Settings y Kelly | **DISMISSED** | Las guardas actuales verifican finitud. Esto no resuelve los importes ilegibles de AUD-01. |
| Registro de modelos manipulado o artefactos comprometidos | **NOT_VERIFIABLE** | No hay evidencia de ataque; tres sidecars faltan por una compatibilidad admitida. |
| Dashboard completamente libre de XSS | **NOT_VERIFIABLE** | Se verificaron escapes y tests de HTML, pero no todos los sinks dinámicos en un navegador con entradas hostiles. |
| Dependencias sin vulnerabilidades conocidas al 6 de septiembre | **NOT_VERIFIABLE** | pip-audit no completó la consulta. El resultado limpio de una auditoría anterior no se hereda. |
| Disponibilidad real, esquema actual y presupuesto de proveedores | **NOT_VERIFIABLE** | No se consumieron APIs de pago ni se ejercitó integración live. |
| Ejecución actual de tareas, último CI remoto y restauración de backups | **NOT_VERIFIABLE** | No se obtuvo evidencia operativa suficiente ni se realizaron restauraciones. |
| Rentabilidad futura o calibración válida bajo cambios de régimen | **NOT_VERIFIABLE** | Las pruebas de software y los agregados históricos no la demuestran. |

## 8. Plan de corrección y pruebas de aceptación

| Orden | Trabajo propuesto | Criterio verificable de cierre |
|---|---|---|
| 1 | AUD-01: integridad por movimiento contable | Ninguna pérdida/retirada ilegible aumenta el saldo; el pipeline trata la banca como no verificable. |
| 2 | AUD-02: exclusión transaccional de liquidaciones | Dos escritores concurrentes conservan todas las filas nuevas, sin duplicados ni pérdida de PnL. |
| 3 | AUD-03: unidad independiente del gate | Variar el número de líneas del mismo partido no aumenta el número de eventos independientes ni abre el gate por duplicación. |
| 4 | AUD-06: frescura independiente del modo de acceso | Una caché más vieja que la política no produce candidatos accionables live, incluso offline. |
| 5 | AUD-04: emparejamiento e información disponible al corte | Dobles jornadas con IDs no cronológicos se asignan correctamente o se omiten por ambigüedad; no se observa el propio resultado antes de estimarlo. |
| 6 | AUD-05: huella completa de features | Cambiar abridores invalida la caché y la reconstrucción normal coincide con force=True. |

No se aplicaron estas correcciones. Para el criterio estadístico, la revisión del preregistro debe separar diseño de evaluación y evitar elegir una regla por su resultado favorable retrospectivo.

Tras implementar, ejecutar primero los escenarios discriminantes de cada hallazgo y después la suite completa, Ruff y MyPy. La validación de proveedores, dependencias, navegador y tareas debe completarse por separado, con resultados registrados; no queda sustituida por los tests unitarios.

## 9. Trazabilidad de las reproducciones

Los resultados detallados se guardaron en la copia temporal, fuera del proyecto:

- `audit-source-manifest.json`: hashes de los archivos fuente copiados.
- `audit-coverage.json`: cobertura de la suite completa.
- `audit-data-results.json`: inventario y agregados de datos/registros.
- `audit-data-quality.json`: controles de fechas, duplicados y probabilidades.
- `audit-adverse-results.json`: corrupción parcial, retirada, líneas correlacionadas y pérdida de escritura.
- `audit-backtest-results.json`: traza de estimación/observación y resultados cruzados.
- `audit-feature-results.json`: caché frente a reconstrucción forzada.
- `audit-offline-results.json`: precio vencido utilizado por run_league.

Los archivos temporales son evidencia auxiliar y pueden caducar por mantenimiento del sistema. Las entradas, resultados, causas y pasos esenciales se incluyen en este informe para no depender exclusivamente de ellos.

El delta externo final se validó en `C:\Users\Richard\AppData\Local\Temp\sqp-audit-delta-20260906-1hp7yoi5`, con `tests/test_odds_cache.py` y `tests/test_frescura_cuotas_diario.py`. No se suman sus 14 casos a los 1.547 de la suite como si fueran pruebas distintas: hay solapamiento.

En esa segunda copia se incorporó después el delta de calibración y se ejecutó `pytest ... tests/test_calibrator.py -k promot`: 9 pruebas aprobadas y 32 deseleccionadas. Tampoco se suman estos casos al total de la suite. Las referencias de líneas del informe corresponden al código de la instantánea original, salvo las menciones explícitas a los deltas.

### Reproducción compacta de AUD-01

Ejecutar solo en un entorno aislado con `src` en PYTHONPATH:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from sqp.risk.bankroll import BankrollLedger

with TemporaryDirectory() as td:
    root = Path(td)
    bets = root / "data" / "bets"
    bets.mkdir(parents=True)
    (bets / "settled_mlb.csv").write_text(
        "pnl,data_label,result,stake\n"
        "-400,real,loss,400\n"
        "ERROR,real,loss,400\n",
        encoding="utf-8",
    )
    print(BankrollLedger(root, 1000).current_balance())
    # Observado: 600. El saldo no es verificable.
```

### Reproducción compacta de AUD-03

```python
import pandas as pd
from sqp.risk.prediction_gate import evaluate_markets

rows = []
for event in range(150):
    for line in (3.5, 4.5):
        for side, p, price, fair, result in (
            ("Over", 0.8, 1.8, 0.625, "win"),
            ("Under", 0.2, 3.0, 0.375, "loss"),
        ):
            rows.append(dict(
                league="mlb", market="totals",
                event_id=f"e{event}", game_date="2026-09-01",
                line=line, selection=side, model_probability=p,
                price_decimal=price, implied_probability_novig=fair,
                result=result,
            ))
df = pd.DataFrame(rows)
print(evaluate_markets(df)[["n", "allowed"]])
print(evaluate_markets(df[df.line == 3.5])[["n", "allowed"]])
# Dos líneas: n=300, allowed=True.
# Una línea: n=150, allowed=False. Son los mismos 150 partidos.
```

## 10. Conclusión

El estado auditado supera las puertas automatizadas existentes, pero **no satisface todavía una conclusión incondicional de corrección integral**. Seis casos reproducidos muestran que pueden sobreestimarse saldos, perderse liquidaciones, autorizarse evidencia estadística dependiente, cruzarse resultados de backtest, reutilizarse features obsoletas y tratarse cuotas vencidas como accionables.

La prioridad es corregir los controles que gobiernan integridad contable y autorización, conservando los datos y el rastro de evidencia. El informe no recomienda activar mercados ni modificar umbrales a partir de estos experimentos. El cierre requiere las pruebas de aceptación indicadas y completar las verificaciones externas que quedaron pendientes.
