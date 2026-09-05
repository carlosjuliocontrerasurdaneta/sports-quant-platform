# Auditoría integral independiente — Sports Quant Platform

**Fecha:** 2026-09-05  
**Auditor:** Codex  
**Repositorio:** `C:\dev\3\sports-quant-platform`  
**Resultado:** **NO PASS — seis defectos confirmados y limitaciones de validación explícitas.**

## 1. Dictamen ejecutivo

La auditoría identificó **dos hallazgos HIGH y cuatro MEDIUM**, todos con confianza HIGH. Cinco se activaron mediante ejecuciones controladas; el sexto, relativo a inyección en el dashboard, quedó verificado por el código y por el análisis del HTML generado. No se demostró un incidente CRITICAL ni pérdida efectiva de dinero o datos en producción.

Los problemas de mayor impacto son la reconstrucción de una banca artificialmente elevada cuando un CSV de liquidaciones resulta ilegible y la pérdida de actualizaciones que permite el mecanismo de bloqueo al expirar su espera. Los restantes afectan la seguridad del dashboard, la selección temporal de observaciones para calibrar, la aceptación de una banca infinita y la divergencia entre entrenamiento manual y diario.

El registro operativo de predicción examinado contiene **41 mercados, ninguno autorizado**. Ese estado reduce la exposición inmediata a los defectos de dimensionamiento; no elimina sus rutas de activación cuando se autoricen mercados o se usen otros entrypoints/configuraciones.

La revisión no se limitó a los cambios locales: la solicitud expresa de auditoría integral define como alcance el proyecto completo. Los defectos se presentan como problemas del estado auditado, sin atribuirlos a los cambios que estaban pendientes al comenzar.

**Validaciones:** **1.517 pruebas aprobadas y 1 omitida** en la suite completa; Ruff y MyPy sin incidencias; pip-audit sin vulnerabilidades conocidas reportadas para el lock. Estos resultados no invalidan los casos adversos de la sección 3.

## 2. Alcance, identidad de la revisión y método

### 2.1 Estado de Git y preservación del entorno

Al inicio se observó HEAD `33f3c262903faaf61787ba4a98892744d13893cb` y cinco modificaciones locales previas:

- `.claude/skills/full-audit/references/discovery-coverage.md`.
- `.github/workflows/ci.yml`.
- `NOTAS.md`.
- `scripts/claude_project_health.py`.
- `tests/test_claude_system_contract.py`.

Durante la auditoría, actividad externa avanzó HEAD a `ad764f23cb4b6e8ebdae775e01662158d204e700` y dejó únicamente `NOTAS.md` modificado antes de escribir este informe. Codex no hizo commits, cambios de rama, push, restauraciones ni operaciones de limpieza.

Se creó una copia temporal de los archivos versionados disponibles, incluyendo el contenido local modificado, para ejecutar pruebas sin escribir sobre el proyecto operativo. Ubicación:

`C:\Users\Richard\AppData\Local\Temp\sqp-audit-497953f85cf5451385476406165dcaa6`

Se excluyeron datos operativos, logs, secretos y carpetas de conocimiento no necesarias para las pruebas. Una comparación posterior por contenido de archivos Python/YAML de `src`, `scripts`, `tests`, `configs` y `.github` no detectó diferencias entre esa copia y el proyecto. Por tanto, el avance externo de HEAD no invalidó las validaciones sobre esos archivos.

El copiado inicial por `git ls-files` tuvo errores de representación en nombres Unicode de documentos auxiliares. Se registra como limitación del inventario documental copiado, no como defecto del proyecto; los archivos de código/configuración comparados sí coincidieron.

La única escritura deliberada sobre el proyecto es la actualización de este informe, expresamente solicitada por el usuario. Se reemplaza el informe anterior de agosto con esta evaluación independiente.

### 2.2 Método y evidencia

Se combinaron:

1. Inspección de arquitectura, configuración y contratos documentados.
2. Lectura dirigida de implementaciones, consumidores y pruebas por componente.
3. Validación de sintaxis/lint, tipos y comportamiento en copia aislada.
4. Casos adversos controlados que verifican consecuencias concretas.
5. Lectura directa de CSV y JSON operativos para medir calidad de datos, sin invocar cargadores que reparan, renombran o ponen archivos en cuarentena.
6. Consulta de vulnerabilidades de las versiones fijadas, sin instalar o actualizar dependencias.

Se aplican los estados de AGENTS.md: únicamente `REPRODUCED` y `STATICALLY_VERIFIED` se contabilizan como defectos confirmados. Un test verde no constituye por sí solo una prueba de corrección completa; una advertencia de una herramienta tampoco se transforma automáticamente en un hallazgo.

### 2.3 Inventario y profundidad

| Área | Archivos inventariados | Líneas físicas |
|---|---:|---:|
| Python en `src/sqp` | 98 | 15.837 |
| Python en `scripts` | 58 | 9.131 |
| Python en `tests` | 115 | 21.558 |
| YAML en `configs` | 5 | 582 |

Las cifras son inventario, no cobertura de ejecución ni una afirmación de lectura manual línea por línea. La cobertura fue por componentes y rutas de riesgo, complementada por las validaciones automatizadas. No se calculó un porcentaje de cobertura durante esta auditoría.

## 3. Hallazgos confirmados

| ID | Severidad | Confianza | Evidencia | Problema |
|---|---|---|---|---|
| AUD-001 | HIGH | HIGH | REPRODUCED | Un CSV ilegible puede inflar la banca disponible |
| AUD-002 | HIGH | HIGH | REPRODUCED | El timeout del bloqueo permite perder actualizaciones |
| AUD-003 | MEDIUM | HIGH | STATICALLY_VERIFIED | Datos externos se insertan como código/HTML en el dashboard |
| AUD-004 | MEDIUM | HIGH | REPRODUCED | El colapso de calibración no garantiza conservar el último servicio |
| AUD-005 | MEDIUM | HIGH | REPRODUCED | La configuración admite banca infinita y Kelly devuelve stake infinito |
| AUD-006 | MEDIUM | HIGH | REPRODUCED | El CLI de calibración entrena sobre una probabilidad distinta del flujo diario |

### AUD-001 — El saldo aumenta cuando las pérdidas se vuelven ilegibles

- **Severidad:** HIGH.
- **Confianza:** HIGH.
- **Estado de evidencia:** REPRODUCED.
- **Archivo y código relevante:** `src/sqp/risk/bankroll.py:43`, captura de `EmptyDataError/ParserError` seguida de `continue`; `:77`, suma del saldo; `:149`, aplicación al dimensionamiento dinámico. La lectura de ajustes en `:71` presenta el mismo patrón de devolver cero.
- **Activación:** un archivo `settled_*.csv` que contiene pérdidas deja de ser parseable y se vuelve a calcular la banca. Para producir exposición real adicional deben estar permitidos el mercado y el staking.
- **Problema:** datos contables desconocidos se interpretan como ausencia de movimientos. El saldo resultante tiene apariencia de cifra válida aunque ya no esté respaldado por todo el ledger.
- **Evidencia:** en un directorio temporal se escribió una liquidación real con PnL −400 y banca inicial 1.000. El saldo fue 600. Al agregar una fila con más campos que la cabecera, pandas produjo el error de parsing que el código omite; `current_balance()` pasó a devolver 1.000.
- **Comportamiento esperado:** señalar que el saldo es indeterminado y detener el dimensionamiento dependiente de él, o usar una política explícita de último saldo verificado cuya integridad pueda acreditarse.
- **Comportamiento observado:** el saldo subió **600 → 1.000 sin depósito ni ganancia**. No hubo error propagado ni advertencia desde esa rama.
- **Causa raíz:** el manejo de errores de lectura equipara corrupción con contribución contable cero.
- **Consecuencia:** sobreestimación material del capital disponible y de los límites/stakes que se derivan de él. En el ejemplo, el saldo utilizable se sobreestima un 66,7 %. No se observó un CSV de liquidaciones corrupto en el barrido operativo.
- **Corrección mínima propuesta:** propagar un error de integridad identificando el archivo y hacer que los entrypoints de staking rechacen una banca no verificable. Aplicar el mismo criterio al archivo de ajustes. Conservar los datos para diagnóstico.
- **Pruebas necesarias:** integrar lectura de un ledger corrupto con `apply_dynamic_bankroll` y comprobar que no se autoriza stake; cubrir pérdidas, retiradas, CSV truncado y columnas contables ausentes. `tests/test_bankroll.py::test_corrupt_or_empty_file_is_skipped` valida actualmente el comportamiento de omisión, por lo que debe revisarse su contrato y no solamente agregarse otro test que lo repita.

### AUD-002 — La exclusión mutua desaparece precisamente cuando hay contención

- **Severidad:** HIGH.
- **Confianza:** HIGH.
- **Estado de evidencia:** REPRODUCED.
- **Archivo y código relevante:** `src/sqp/storage/lock.py:55`–`61`: al alcanzar el deadline se hace `break` y después `yield` sin haber adquirido el lock. Consumidores: `pipeline/daily.py`, `pipeline/revalidation.py`, `storage/odds_store.py` y contadores de cierre.
- **Activación:** un escritor retiene el bloqueo más que el timeout de otro escritor. Es una condición concreta del flujo: `revalidate_pitchers` mantiene el bloqueo durante `fetch_probables(day)` (`src/sqp/pipeline/revalidation.py:277`, `:319`), mientras el proveedor admite llamadas de 60 segundos y el timeout del lock es 30 segundos.
- **Problema:** el segundo escritor entra en una sección supuestamente exclusiva y ambos pueden operar sobre versiones distintas del mismo CSV.
- **Evidencia:** con un lock adquirido se leyó una fila `old`. Dentro de otra adquisición con `timeout_s=0`, que activó inmediatamente la misma rama de timeout, se escribió una fila `new`. El primer escritor persistió después su copia anterior. El resultado final fue únicamente `old`; `new` desapareció. Se observó el warning `proceeding WITHOUT lock`.
- **Comportamiento esperado:** el escritor que no obtiene exclusión no debe ejecutar una actualización del recurso protegido; debe reintentar o devolver un fallo explícito.
- **Comportamiento observado:** se permitió escribir y la nueva actualización se perdió. La prueba usa un intercalado determinista en un único proceso para activar la lógica de exclusión; no pretende medir la frecuencia de carreras entre procesos en producción.
- **Causa raíz:** priorizar la continuidad del pipeline sobre la garantía de exclusión, mientras los consumidores siguen usando operaciones read-modify-write. El nombre temporal fijo `.csv.tmp` añade otra colisión posible cuando se solapan escrituras.
- **Consecuencia:** pérdida de candidatos recién generados, revocaciones o cambios de exposición, e inconsistencias en datos/contadores compartidos. No se demostró que haya ocurrido ya en los archivos operativos.
- **Corrección mínima propuesta:** hacer que el timeout impida entrar en la sección crítica. Sacar las consultas de red de esa sección cuando sea posible, releer/revalidar el estado al adquirir el lock y evitar temporales compartidos. Usar un mecanismo de bloqueo con semántica comprobable para procesos vivos.
- **Pruebas necesarias:** dos escritores coordinados, uno demorado, verificando que ninguna actualización se pierde; una revocación concurrente con generación; colisión de temporales; timeout sin escritura. Las pruebas actuales de `test_storage.py` y `test_odds_store.py` esperan explícitamente degradar sin lock y no demuestran conservación de actualizaciones.

### AUD-003 — Inyección de JavaScript/HTML en el reporte interactivo

- **Severidad:** MEDIUM.
- **Confianza:** HIGH.
- **Estado de evidencia:** STATICALLY_VERIFIED.
- **Archivo y código relevante:** `src/sqp/audit/html_report.py:823` serializa con `json.dumps(..., ensure_ascii=False)`; `:837` inserta `payload` sin escape contextual; `:980` lo coloca dentro de un `<script>`. En `:1058` y `:1281`, el formateador de texto devuelve el valor original y las tablas lo insertan mediante `innerHTML`.
- **Activación:** un valor textual procedente del proveedor o de los CSV, por ejemplo el nombre de un equipo, contiene una secuencia de cierre de script o marcado HTML activo; el usuario abre el reporte generado.
- **Problema:** serializar JSON no es escapar datos para el contexto HTML de una etiqueta script. Además, el renderizado de celdas interpreta los textos como marcado.
- **Evidencia:** se construyó la plantilla con un valor inocuo de prueba `</script><script>window.auditMarker=1</script>`. El parser HTML reconoció **dos elementos script**, incluido uno independiente cuyo contenido era `window.auditMarker=1`. Las rutas de `innerHTML` constituyen un segundo punto de interpretación de datos.
- **Comportamiento esperado:** representar esos caracteres como texto/datos, sin crear elementos ni ejecutar código.
- **Comportamiento observado:** el documento generado incorpora una nueva etiqueta script a partir del dato. No se abrió el payload en un navegador ni se ejecutó JavaScript durante la auditoría; la explotación queda demostrada estáticamente por el contexto HTML.
- **Causa raíz:** falta de separación entre serialización JSON, escape de HTML y construcción del DOM.
- **Consecuencia:** ejecución de JavaScript en el contexto del reporte, alteración visual de picks o navegación/conexiones no deseadas. No se demuestra acceso remoto al filesystem, robo de credenciales ni control actual de los proveedores por un atacante.
- **Corrección mínima propuesta:** neutralizar `<` al serializar el JSON embebido —por ejemplo con el escape JSON `\u003c`— y construir textos/atributos con APIs DOM como `textContent` y `setAttribute`, sin interpolar valores no confiables en HTML o handlers inline.
- **Pruebas necesarias:** nombres con `</script>`, etiquetas con eventos, comillas y caracteres especiales; comprobar que permanecen como texto y que no se crean scripts/event handlers adicionales. Cubrir ambas tablas, filtros y atributos dinámicos.

### AUD-004 — Se pierde el timestamp necesario para elegir la observación más reciente

- **Severidad:** MEDIUM.
- **Confianza:** HIGH.
- **Estado de evidencia:** REPRODUCED.
- **Archivo y código relevante:** `src/sqp/calibration/data.py:40` no conserva `generated_at` en `TRAINING_COLS`; `:108` obtiene `date` de la fecha del partido. `src/sqp/calibration/calibrator.py:571` ordena por `date` y `:595` conserva `groupby("_unit").last()`.
- **Activación:** varias observaciones del mismo evento/selección/línea, generadas en fechas distintas, llegan en un orden que no es el cronológico de generación. La unión de liquidaciones y stream servido y los historiales inyectables no garantizan ese orden.
- **Problema:** la implementación promete conservar la última observación por frescura de features, pero todas las observaciones del mismo evento tienen la misma fecha de partido. Tras descartar el timestamp de generación, no puede determinar cuál es la última.
- **Evidencia:** para 40 eventos se proporcionaron dos observaciones: probabilidad 0,8 generada el 31 de agosto y 0,2 generada el 30, ambas con partido el 1 de septiembre. Se pasó el dataset por la proyección real y se interceptó la entrada a entrenamiento, evitando crear modelos. Las **40 observaciones retenidas fueron 0,2**, aunque la más reciente era 0,8.
- **Comportamiento esperado:** conservar 0,8 para cada unidad, independientemente del orden de llegada, manteniendo la fecha del partido para el split temporal.
- **Comportamiento observado:** se eligió la fila antigua; el historial proyectado ya no contenía `generated_at`.
- **Causa raíz:** utilizar un único campo de fecha para dos semánticas distintas: ordenar eventos para validación y ordenar servicios dentro de un evento.
- **Consecuencia:** entrenamiento y métricas del gate sobre una observación distinta de la que declara el contrato, con dependencia del orden de las fuentes. No se cuantificó el impacto sobre métricas de los calibradores actualmente desplegados ni se afirma fuga de etiquetas por esta causa.
- **Corrección mínima propuesta:** conservar un timestamp de generación normalizado a UTC; seleccionar por ese timestamp dentro de cada unidad, con desempate explícito; mantener `game_date/date` por separado para agrupar y separar eventos temporalmente.
- **Pruebas necesarias:** permutar el orden de las mismas observaciones, intercambiar las fuentes y comprobar invariancia; cubrir múltiples días de servicio, dos lados del mismo mercado y timestamps equivalentes en distintos formatos.

### AUD-005 — Se aceptan valores no finitos en la banca

- **Severidad:** MEDIUM.
- **Confianza:** HIGH.
- **Estado de evidencia:** REPRODUCED.
- **Archivo y código relevante:** `src/sqp/config.py:220` convierte `BANKROLL` con `float`; `:340` solo comprueba `self.bankroll <= 0`. `src/sqp/risk/kelly.py:14` calcula el stake sin validar finitud de la banca.
- **Activación:** configuración `BANKROLL=inf`, admitida por la conversión estándar, y un candidato con probabilidad/precio que permite stake positivo.
- **Problema:** la validación declara comprobar seguridad de configuración pero acepta una cantidad monetaria infinita.
- **Evidencia:** `Settings.load()` aceptó `BANKROLL=inf`; con probabilidad 0,6, cuota 2 y parámetros de riesgo cargados, Kelly devolvió un porcentaje aproximado de 0,016 y un stake no finito.
- **Comportamiento esperado:** rechazar la configuración antes de evaluar o persistir candidatos.
- **Comportamiento observado:** `settings_accepted=true`, `bankroll_finite=false`, `stake_finite=false`.
- **Causa raíz:** comparaciones de rango que no excluyen explícitamente infinitos/NaN en campos sin cota superior, junto con falta de validación defensiva en el cálculo monetario.
- **Consecuencia:** stakes, sumas de exposición o PnL no finitos si esa configuración llega a una ruta autorizada. El ejemplo se ejecutó en un entorno temporal; no se detectó esa configuración en producción ni se leyó el contenido del `.env` operativo.
- **Corrección mínima propuesta:** exigir `math.isfinite` además del rango en los campos numéricos de configuración y en los valores monetarios recibidos por Kelly; revisar también los campos de frescura y penalización que solo usan comparaciones de signo.
- **Pruebas necesarias:** `nan`, `inf` y `-inf` en banca, límites y parámetros de frescura; verificar rechazo temprano y ausencia de salidas no finitas. Los controles existentes sobre precios inválidos no cubren este origen.

### AUD-006 — El entrenamiento manual usa un objetivo distinto al servido

- **Severidad:** MEDIUM.
- **Confianza:** HIGH.
- **Estado de evidencia:** REPRODUCED.
- **Archivo y código relevante:** `scripts/train_calibration.py:85`, selección de `prob_col` antes de llamar a `train_market_calibrators`: las fuentes `combined/settled/served` usan `model_probability`. Contratos relacionados: `calibration/data.py::stage_calibrators_from_settled` usa `adjusted_probability`, y `pipeline/daily.py:760` entrega `_p_adj` a `pipeline/probabilities.py::_decision_probability` para calibrarla.
- **Activación:** ejecutar el CLI manual sobre un historial con `adjusted_probability != model_probability`, condición presente en 2.216 filas del stream graduado examinado.
- **Problema:** el camino manual y el diario ajustan curvas sobre variables distintas, aunque ambos producen candidatos para los mismos mercados.
- **Evidencia:** se invocó `main()` del CLI con loader simulado y una fila con modelo 0,4/ajustada 0,7. Se interceptó la llamada de entrenamiento: `CLI_TRAIN_TARGET model_probability`. No se entrenó ni promovió ningún modelo. La lectura directa de datos reales corroboró que la distinción no es meramente nominal.
- **Comportamiento esperado:** las fuentes de servicio usan `adjusted_probability` con el fallback legacy ya definido por la proyección, igual que el flujo diario. El backtest puede conservar su semántica explícitamente distinta.
- **Comportamiento observado:** el CLI selecciona `model_probability`, incluso cuando dispone de la columna ajustada.
- **Causa raíz:** la selección del objetivo en el entrypoint no se actualizó junto con el contrato de entrenamiento/servicio.
- **Consecuencia:** candidatos manuales y métricas OOS que no representan el mismo objetivo que el entrenamiento diario; una promoción posterior puede aplicar una curva aprendida sobre otra variable. La promoción automática está desactivada en el YAML, lo que reduce la exposición inmediata.
- **Corrección mínima propuesta:** cambiar el objetivo de las fuentes serve-anchored a `adjusted_probability` y compartir la decisión con el flujo diario; mantener el fallback de esquemas antiguos y ajustar la documentación del CLI.
- **Pruebas necesarias:** invocar el entrypoint con probabilidades cruda y ajustada deliberadamente distintas; comprobar el campo realmente entregado al trainer; cubrir fuentes combined, served, settled y backtest.

## 4. Resultados por componente

| Componente | Verificación realizada | Resultado y límites |
|---|---|---|
| Dominio y configuración | Entidades, precedence env/YAML, rangos, modos, configuración ausente | La ausencia de YAML falla explícitamente; booleanos no reconocidos no anulan silenciosamente el YAML. AUD-005 afecta finitud. No se inspeccionó el contenido del .env operativo. |
| Cuotas y proveedores | Odds API, caché, retries, parsing, resultados ESPN/MLB, persistencia | Hay timeouts y redacción de query en errores HTTP/conexión; modo offline bloquea la salida a la red. Se preservan cuotas crudas inválidas y se filtran al calcular consenso. Disponibilidad y exactitud del vendor en vivo no comprobadas. |
| Mercados | Conversión de cuotas, no-vig proporcional/power, consenso, spreads complementarios, edge y penalizaciones | Se verificó el rechazo de precios no finitos y el tratamiento de mercados incompletos. No se encontró un defecto adicional confirmado en las fórmulas/rutas examinadas. |
| Modelos y adaptadores | Elo, Normal, Poisson/NegBin, Dixon-Coles, correlación, park/starter, familias deportivas | Se revisaron actualización secuencial, probabilidades condicionadas a no-push y configuración por familia. La validez predictiva por liga no se deduce de las pruebas de implementación. |
| Simulación | Monte Carlo Normal/Poisson y pruebas asociadas | Implementación con semillas y salidas probabilísticas; no se ejecutó un benchmark independiente de todos los parámetros/regímenes. |
| Features y ML experimental | Rolling features antes de observar resultados, selección de columnas, pipelines y TimeSeriesSplit | Hay separación de labels y transformaciones dentro del pipeline. El módulo ML no alimenta directamente los picks de producción. Disponibilidad intradía exacta y validación OOS de todos los modelos históricos no acreditadas. |
| Calibración | Proyección served/settled, dedup, split por evento, gates, registro y aplicación | Controles de ECE/Brier y estructura de curvas. AUD-004 y AUD-006. El agrupamiento por evento evita separar sus dos lados entre train y validación; no equivale a probar independencia de todo el proceso de investigación. |
| Backtesting y tuning | Walk-forward, matching de resultados/cuotas, cierre prepartido, OOS, comparación/blend | El ROI replay ordena resultados y comparte ajustes con servicio; usa un proxy de cierre y omite algunas decisiones de producción por diseño. No certifica el rendimiento económico de la política operativa completa. |
| Riesgo y banca | Kelly, caps por liga/global, gates CLV/predicción, degradación, ledger | Gate ausente/ilegible se trata como denegación en las rutas inspeccionadas. AUD-001, AUD-002 y AUD-005 afectan garantías monetarias/de persistencia. |
| Liquidación | Identidad de equipos, h2h/1X2/spreads/totals, push/void, expiración y dedup | Guards contra líneas no finitas y selección no reconocida; pruebas unitarias/integrales. No se conciliaron todas las filas con extractos de una casa de apuestas. |
| Storage | CSV atómico, fsync, locks, snapshots, esquemas, stream servido, features | Escritura temporal+replace reduce truncados, pero no ofrece por sí sola serialización. AUD-002. No se simularon cortes de energía ni fallos reales del filesystem. |
| Evaluación y reportes | Brier, log-loss, ECE, CLV, bootstrap por cluster, segmentación, tipster, HTML | Se observaron filtros de CLV no finito y agrupación para bootstrap. AUD-003 afecta el reporte interactivo. No hubo validación visual completa en navegador. |
| Operación y monitoreo | BAT, run_all/settle_all, cierre, budgets, run_status, health y purga | Orden settle→run y manejo de etapas fallidas inspeccionados; purga limitada a familias de artefactos. No se ejecutaron tareas programadas, purgas ni pipelines live. |
| Automatización de revisión | Protocolo de procedencia, launcher, snapshot, tests contractuales, health | El protocolo distingue ausencia/fallo de ejecución de revisión limpia. Se examinaron los cambios de alarma CI; no se abrieron issues ni se invocaron revisores externos. |
| Empaquetado/CI | pyproject, lock, Makefile, Dockerfile, workflow | CI declara Python 3.11–3.14 en Linux y una pata Windows 3.12. Docker usa usuario sin privilegios. Validación local en Windows/Python 3.14; sin build Docker ni réplica de toda la matriz. |
| Documentación | README, contratos operativos/cuantitativos y comentarios de implementación | Se usaron como contratos a contrastar, no como evidencia de que correcciones históricas ya funcionen. Las discrepancias que afectan comportamiento se documentan en hallazgos; no se cuentan preferencias editoriales. |

## 5. Inspección de datos operativos

El barrido fue de solo lectura y no representa un snapshot transaccional: otro proceso podía actualizar los archivos entre lecturas.

| Conjunto | Archivos | Filas | Errores de lectura |
|---|---:|---:|---:|
| `data/bets/settled_*.csv` | 27 | 1.205 | 0 |
| `data/calibration/graded_*.csv` | 23 | 19.333 | 0 |
| `data/predictions/candidates_*.csv` | 14 | 144 | 0 |
| `data/historical/results_*.csv` | 21 | 130.144 | 0 |
| `data/odds/odds_*.csv` | 75 | 5.545.502 | 0 |

Resultados concretos:

- En liquidaciones, stream graduado y candidatos no se encontraron probabilidades **presentes y numéricamente convertibles** fuera de [0, 1] ni duplicados por la clave completa `event_id/market/selection/line/generated_at`. Este control no demuestra unicidad a otras granularidades.
- Las liquidaciones tenían 94 valores ausentes de `calibrated_probability`. El stream graduado tenía 14.953 valores ausentes de `adjusted_probability`. Existen fallbacks de esquema legacy; la ausencia no se clasificó por sí sola como defecto. No se afirma que todas las probabilidades de esos registros hayan sido calibradas.
- En 2.216 filas graduadas la probabilidad ajustada difiere de la cruda: evidencia de la relevancia de AUD-006.
- Las cuotas contienen 3.293 precios no utilizables. No se encontraron timestamps de captura/inicio inválidos en el barrido con parsing UTC de formatos mixtos.
- Hay 288.725 filas capturadas en o después del inicio que la propia fila reporta. Su presencia en el archivo crudo no prueba look-ahead: `load_closing_odds` filtra capturas estrictamente anteriores al comienzo y el pipeline restringe la acción sobre eventos comenzados. No se consideraron esas filas como picks accionables ni se midió aquí cada replay histórico.
- El registro de calibración contenía cuatro entradas con artefactos existentes: `mlb_h2h_pergame`, `mlb_spreads`, `mlb_totals` y `wnba_spreads`. Solo el último disponía de sidecar SHA-256 y coincidía. Los otros tres no tienen una comparación de hash disponible. La presencia de una entrada no demuestra que tenga consumidores ni que su curva sea válida.
- El gate local de predicción contenía 41 entradas, cero permitidas y cero latched. Se leyó su estado; no se modificó ni recalculó.

## 6. Validaciones ejecutadas

Entorno principal: Windows, Python **3.14.4**. Versiones observadas: pytest **9.0.3**, Ruff **0.15.14**, MyPy **2.1.0**, NumPy **2.4.4**, pandas **3.0.2**, SciPy **1.17.1**, scikit-learn **1.9.0**, pip-audit **2.10.1**.

| Validación | Resultado | Clasificación |
|---|---|---|
| Pruebas iniciales config/odds/vig/Kelly | 38 aprobadas en la repetición aislada | Sin fallo final |
| Ruff: `python -m ruff check --no-cache src scripts tests` | All checks passed | Sin diagnóstico |
| MyPy: `python -m mypy --cache-dir nul src` | Sin incidencias en 98 archivos fuente | Sin diagnóstico |
| Suite completa | 1.517 passed, 1 skipped; 1.457,58 s (24 min 17 s), salida 0 | Sin fallos de suite; una prueba omitida |
| pip-audit del lock | No known vulnerabilities found, salida 0 | Sin vulnerabilidad conocida reportada |
| Casos adversos de esta auditoría | AUD-001/002/004/005/006 reproducidos; AUD-003 verificado en HTML | Defectos confirmados según sección 3 |
| Consulta del último CI remoto | `gh` no disponible en PATH ni en la ruta de instalación habitual | ENVIRONMENTAL_FAILURE; estado remoto NOT_VERIFIABLE |

**Detalle de la prueba omitida:** `tests/test_review_v2.py::test_every_finding_slot_tolerates_hostile_text[severity]`, con omisión explícita en `tests/test_review_v2.py:228`. El motivo es `severity is a closed enum, not free text`: el campo `severity` solo admite valores definidos (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), por lo que no corresponde aplicarle este caso parametrizado de texto libre adverso. Es una omisión deliberada del test, no un fallo ni un problema del entorno. Se confirmó posteriormente en la copia temporal con `python -m pytest -q -rs -p no:cacheprovider --basetemp audit-skip-check "tests/test_review_v2.py::test_every_finding_slot_tolerates_hostile_text[severity]"`: **1 skipped in 0.56s**, salida 0.

Comando de la suite completa, dentro de la copia:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --basetemp audit-suite-temp
```

Comando de auditoría de dependencias, también dentro de la copia:

```text
python -m pip_audit -r requirements.lock --no-deps --disable-pip --cache-dir audit-vuln-cache --progress-spinner off --timeout 10
```

La primera ejecución de las pruebas iniciales dio **37 passed, 1 error** porque pytest no podía acceder a su directorio temporal compartido (`WinError 5`). Se repitió con permiso de ejecución ampliado y un `--basetemp` propio: **38 passed**. Se clasifica el intento inicial como **ENVIRONMENTAL_FAILURE**, no como regresión.

La primera consulta pip-audit falló por bloqueo de sockets del sandbox (`WinError 10013`). Se repitió mediante el mecanismo de permisos y terminó correctamente. No se ejecutó `--fix`, resolución de paquetes ni actualización de dependencias. El resultado cubre los paquetes expresamente fijados en el archivo, no componentes transitivos ausentes de ese inventario, herramientas globales o imágenes base.

`make check` se inspeccionó y equivale a lint, types y test. Se usaron los comandos directamente para controlar cachés y ubicación de salidas, evitando repetir validaciones equivalentes.

No se detectó una NEW_REGRESSION atribuible a las modificaciones locales del inicio. Los seis defectos son del estado del proyecto examinado; no se hizo bisección histórica para fechar su introducción.

## 7. Candidatos descartados y cuestiones no verificables

### 7.1 Sospechas descartadas

| Sospecha | Estado | Motivo |
|---|---|---|
| Todo precio crudo inválido contamina el consenso | DISMISSED | `is_usable_price` se aplica en consenso, conteo y de-vig |
| Toda captura posterior al comienzo se usa como cierre | DISMISSED | El selector exige captura anterior al inicio y usa la hora de inicio más recientemente reportada |
| Las dos caras de un evento se separan entre train/validación de calibración | DISMISSED | El trainer de mercados transmite `group_col="event_id"` al split |
| Cualquier registro ausente de gate permite staking | DISMISSED | Las rutas revisadas diferencian gate apagado de registro vacío y deniegan este último |
| Los modelos ML experimentales gobiernan los picks diarios | DISMISSED | La ruta operativa inspeccionada genera probabilidades con adaptadores/simulación; inferencia ML permanece separada |
| Los datos legacy sin probabilidad calibrada prueban corrupción | DISMISSED | El proyecto dispone de fallbacks; la ausencia requiere contexto, no constituye por sí sola un resultado inventado |

### 7.2 Límites relevantes

- **NOT_VERIFIABLE — exactitud del mundo real:** no se consultaron Odds API, ESPN o MLB para reconciliar cada resultado/cuota. Los tests y el parsing no demuestran que el proveedor haya publicado información correcta.
- **NOT_VERIFIABLE — rentabilidad y calibración prospectiva:** no se reentrenaron todos los modelos ni se ejecutaron todos los scripts de investigación con datos reales. No se certifica ROI futuro, calibración por liga ni superioridad sobre mercado.
- **NOT_VERIFIABLE — disponibilidad intradía histórica:** los resultados persistidos conservan principalmente fecha de partido; no basta para acreditar el instante exacto en que cada resultado/starter/feature estuvo disponible. Se revisó el orden de actualización, pero no se certifica ausencia universal de look-ahead en dobles jornadas o replays.
- **NOT_VERIFIABLE — multiplicidad y selección de investigación:** splits por evento y bootstrap por cluster son controles útiles; no bastan para acreditar que cada configuración/promoción resultó de un procedimiento prospectivo sin reutilización de muestras. Esa trazabilidad no se reconstruyó íntegramente.
- **NOT_VERIFIABLE — artefactos desplegados:** no se deserializaron modelos operativos para verificar todas las curvas. Tres entradas carecen de sidecar de hash. La existencia del archivo y un hash, cuando existe, no autentican por sí solos su procedencia.
- **NOT_VERIFIABLE — entorno efectivo y scheduler:** no se abrió el `.env`, no se alteraron credenciales y no se inspeccionaron/ejecutaron todas las tareas instaladas del Programador de Windows. La configuración versionada no se equipara a la configuración efectiva de producción.
- **NOT_VERIFIABLE — remoto y despliegue:** sin CLI GitHub disponible, no se confirmó el último resultado de Actions, protecciones de rama ni entrega de las nuevas alertas. Tampoco se construyó la imagen Docker ni se ejecutó la matriz completa de sistemas/versiones.
- **NOT_VERIFIABLE — seguridad exhaustiva:** el control de archivos sensibles versionados no encontró `.env`, `.env.local`, `.env.production`, `*.pem` o `*.key` dentro del patrón consultado. No equivale a un escaneo de secretos de toda la historia Git ni a una auditoría de permisos de equipos/servicios.
- **NOT_VERIFIABLE — recuperación y visualización:** no hubo simulación de apagado abrupto, restauración desde backup o pruebas visuales completas en navegador. Las garantías de exclusión sí se activaron de forma controlada en AUD-002.

No se emite un PASS incondicional sobre ninguna de esas áreas.

## 8. Orden propuesto de corrección y criterios de cierre

1. **Integridad monetaria:** corregir AUD-001 y AUD-005, de modo que una banca desconocida/no finita no se convierta en una cantidad válida para apostar.
2. **Escrituras concurrentes:** corregir AUD-002 y demostrar preservación de actualizaciones y revocaciones con dos escritores. Un warning no es criterio de aceptación.
3. **Dashboard:** corregir AUD-003 en el JSON embebido y en todas las interpolaciones DOM afectadas; probar cargas de texto adversas.
4. **Calibración:** corregir AUD-004 y AUD-006 conjuntamente, conservando las dos semánticas temporales y un único objetivo de entrenamiento para las fuentes servidas. Comparar el dataset resultante antes de entrenar/promover.
5. **Revalidación:** ejecutar las pruebas específicas nuevas y las puertas existentes; documentar por separado la evidencia OOS y la decisión de promoción si los candidatos cambian.

Estos pasos son propuestas de remediación, no cambios realizados por la auditoría. No se recomienda promover automáticamente los modelos ni reconstruir datos operativos sin una tarea de implementación y revisión de sus resultados.

## 9. Conclusión

El proyecto dispone de una base amplia de pruebas, controles explícitos de riesgo y mecanismos de trazabilidad. Las validaciones automatizadas no detectaron los seis problemas demostrados, en parte porque algunas pruebas consolidan comportamientos de degradación que permiten perder garantías de integridad.

El resultado de esta auditoría es **NO PASS**. El cierre requiere corregir y verificar los seis hallazgos, manteniendo separadas la corrección del software, la integridad de los datos y la evidencia cuantitativa prospectiva. Este informe no certifica seguridad absoluta ni rentabilidad.
