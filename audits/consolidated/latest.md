# Backlog técnico consolidado de auditoría

Fecha: 2026-09-14. Repositorio: `C:/dev/3/sports-quant-platform`.
Código revisado: `8503b7a63acdac017b50e1559a3044581b44cc9e`.
Protocolo: `audits/prompts/auditoria-consolidacion.md`; reglas de evidencia y seguridad: `AGENTS.md`.

## 1. Resumen ejecutivo

Se consolidan **10 defectos confirmados: 8 MEDIUM y 2 LOW**, todos con confianza HIGH. **CRITICAL: 0; HIGH: 0; P0: 0; P1: 0.** Otros tres asuntos quedan pendientes de validación, sin puntuación de defecto. Se descartan tres entradas de Claude como defectos actuales, conservando los hechos y oportunidades que las motivaron.

El backlog contiene 13 tickets: 10 correcciones respaldadas por evidencia y 3 investigaciones. No se sumaron automáticamente los 12 hallazgos puntuados de Claude y los 4 de OpenAI. Se revisaron sus causas, controles y contratos. Se reejecutaron las cuatro reproducciones OpenAI y se añadieron verificaciones de los hallazgos exclusivos de Claude, con controles discriminantes. Las **76 pruebas dirigidas pasaron**.

Hay defectos que alteran la evidencia cuantitativa y la completitud de liquidación aun si los gates mantienen apuestas con stake cero. No corresponde concluir que el estado de la suite, o un gate cerrado, prueba ausencia de errores de probabilidades y datos. No se implementó ninguna corrección ni se cambiaron parámetros, datos operativos o tareas programadas.

## 2. Fuentes analizadas

Se leyeron ambos informes completos, incluyendo tablas, fichas, observaciones y anexos. Fuente definitiva: implementación y tests actuales; los informes son secundarios.

| Fuente | Identificación |
|---|---|
| Claude | `audits/claude/latest.md`, 2026-09-14, commit 8503b7a; 12 hallazgos puntuados y 10 observaciones |
| OpenAI | `audits/openai/latest.md`, 2026-09-14, mismo commit; 4 defectos y candidatos no confirmados |
| Código/contratos | `src/sqp`, tests dirigidos, `configs/default.yaml`, instalador/hooks, CI, `IMPLEMENTACION.md`, metadata de `BUILD_INFO.json` |
| Validación previa reutilizada | Suite aislada OpenAI: 2013 passed, 1 skipped; Ruff/MyPy y pip-audit correctos. Ejecutada en esta conversación, no repetida como si fuera una validación nueva |

SHA-256 de fuentes al consolidar:

```text
Claude: c234937ef00e14b5f7be2198f331ff265244bafa3d013c12371acd78bd0e0a1c
OpenAI: 09fd43bdf8268090db457cd07e287ef670e326783ccbf8e30230fc35ed766dff
```

El estado inicial y final de Git incluye una modificación **preexistente** en `.claude/automation/runtime/current-task.md` y `?? audits/`. La consolidación no alteró ese archivo ni los informes fuente. Su hash de control es `5bb35247e23385c67d7fa2a739531f94404699582975d3059526f4e05bc94565`.

## 3. Metodología de consolidación

Se normalizaron causas, no títulos. Los problemas de orden temporal y de penalización omitida afectan al mismo backtest, pero requieren correcciones diferentes y se mantienen separados. Igualmente, un reemplazo fallido en Windows, un append sin exclusión y la antigüedad de un lock no son la misma causa raíz.

Se usaron los estados REPRODUCED, STATICALLY_VERIFIED, INFERRED y DISMISSED. Solo los dos primeros sostienen defectos confirmados. La categoría cruzada «No verificable» abarca aquí candidatos INFERRED cuya condición de activación relevante no está demostrada; no equivale a refutación.

Puntuación recalculada a partir del alcance adoptado: `(I×30+A×20+P×20+E×15+R×10+C×5)/4`. Rangos: 90–100 CRITICAL, 70–89.9 HIGH, 40–69.9 MEDIUM, 15–39.9 LOW; 0–14.9 informativo. Confianza separada. Los tres candidatos pendientes no reciben puntuaciones fingidamente precisas mientras falten condiciones esenciales.

Validaciones nuevas:

```powershell
python -B .codex-tmp/astra_reproduce.py
python -B .codex-tmp/consolidation_reproduce.py
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/consolidation-pytest tests/test_results_backfill.py tests/test_backtest_parity.py tests/test_storage.py tests/test_hook_targets.py
```

Resultado: ambas reproducciones terminaron con código 0, verificando las anomalías esperadas y sus controles; pytest: **76 passed in 21.05s**. No hubo NEW_REGRESSION, PRE_EXISTING_FAILURE ni ENVIRONMENTAL_FAILURE en estos comandos de consolidación. Los defectos se activan en escenarios adicionales, no como fallos de la suite existente.

También se ejecutaron `git status --short`, `git diff --stat`, `git diff --name-only`, `git rev-parse HEAD`, búsquedas `rg`, lecturas `Get-Content`, comprobaciones de existencia de consolidación anterior, hashes con Python y conteo de nombres de artefactos/sidecars. El detector de secretos se ejecutó mediante Git Bash únicamente contra un fichero sintético en scratch; no se invocaron instaladores, hooks que llaman a revisores, proveedores reales ni operaciones Git de mutación del proyecto.

## 4. Limitaciones

- No se verificó prevalencia histórica de los defectos ni impacto agregado sobre ROI/Brier. Los escenarios sintéticos prueban causalidad, no frecuencia real.
- No se revalidaron horarios actuales del Programador, logs operativos, ACL de producción ni estado remoto de CI. El fallo de lectura/escritura se reprodujo sobre el Windows actual con ficheros temporales.
- No se consumieron cuotas deportivas ni se leyeron secretos. Los 13 artefactos joblib y su sidecar se contaron por metadata; no se deserializaron modelos reales.
- La revisión no prueba seguridad del modelo de confianza de los CSV ni del origen de todos los artefactos. Son asuntos explícitos en AUD-012/013.
- La validación completa previa y el análisis de dependencias se reutilizan con atribución. No se repitió la suite de 28 minutos porque no hubo cambios funcionales desde esa validación; la única modificación rastreada es el registro de tarea preexistente.
- Git advierte acceso denegado al ignore global. No impide distinguir el diff rastreado.

## 5. Estado técnico general

El proyecto cuenta con controles de probabilidades, gates restrictivos, deduplicación, temporales atómicos, locks y pruebas extensas. Esas fortalezas conviven con diez defectos concretos. La atomicidad no implica éxito ante lectores Windows ni serialización de read-modify-write; walk-forward por filas tampoco acredita disponibilidad intradía.

No se adopta la afirmación global de Claude «ningún defecto altera hoy probabilidades ni liquidación»: contradice su propia reproducción de `_merge_results` y los escenarios OpenAI revalidados. Tampoco se afirma que haya stakes reales afectados: eso depende del estado operativo y de los gates, no medido en esta consolidación.

## 6. Métricas

| Métrica | Cantidad | Definición |
|---|---:|---|
| Entradas puntuadas originales | 16 | 12 Claude + 4 OpenAI |
| Defectos confirmados consolidados | 10 | AUD-001–010 |
| Tickets totales de referencia | 13 | 10 defectos + 3 investigaciones |
| CRITICAL / HIGH | 0 / 0 | Defectos confirmados |
| MEDIUM / LOW / informativos | 8 / 2 / 0 | Defectos confirmados; investigaciones sin score |
| P0 / P1 | 0 / 0 | Sin emergencia confirmada |
| P2 | 7 | AUD-001–007 |
| P3 correctivos | 3 | AUD-008–010 |
| P3 investigación | 3 | AUD-011–013, no activar corrección automática |
| Confirmado por ambos | 0 | No hay dos fichas formales equivalentes confirmadas |
| Parcialmente coincidente confirmado | 1 | AUD-008: Claude ficha, OpenAI observación y aislamiento |
| Exclusivos Claude confirmados | 5 | AUD-002,004,006,009,010 |
| Exclusivos OpenAI confirmados | 4 | AUD-001,003,005,007 |
| Falsos positivos Claude descartados | 3 | C-AUD-009,010,011 como defectos actuales |
| Falsos positivos OpenAI descartados | 0 | Cuatro fichas revalidadas |
| No verificables | 3 | AUD-011–013; coincidencia parcial de HTML incluida aquí |
| Discrepancias documentadas | 8 | D-01–D-08 en sección 14; no se cuenta cada ausencia como discrepancia |
| Nuevos / persistentes / corregidos / regresiones | 10 / 0 / 0 / 0 | Sobre defectos confirmados respecto a consolidación previa inexistente |

Los tres tickets de investigación también son nuevos, pero no se suman al conteo de defectos nuevos. Estas métricas describen el proyecto y la adjudicación; no comparan calidad de modelos auditores.

## 7. Tabla maestra consolidada

Prefijo **C-** en origen identifica IDs del informe Claude y evita confundirlos con IDs consolidados. La tabla se ordena por prioridad; dentro de P3 se separa trabajo confirmado de investigación.

| ID | Hallazgo | Origen | Categoría | Área | Puntuación | Severidad | Prioridad | Confianza | Estado | Ubicación |
|---|---|---|---|---|---:|---|---|---|---|---|
| AUD-001 | Resultado posterior altera estimación anterior | OpenAI ASTRA-01 | Defecto confirmado | Backtesting | 62.50 | MEDIUM | P2 | HIGH | Abierto | roi_engine.py:277,375 |
| AUD-002 | Dedup elimina partido de día consecutivo | C-AUD-002 | Defecto confirmado | Datos/modelado | 58.75 | MEDIUM | P2 | HIGH | Abierto | daily.py:114 |
| AUD-003 | Tenis archivado carece de metadata para liquidar | OpenAI ASTRA-02 | Defecto confirmado | Settlement | 58.75 | MEDIUM | P2 | HIGH | Abierto | runner.py:564–581 |
| AUD-004 | Backtest omite penalizadores configurados | C-AUD-001 | Defecto confirmado condicionado | Backtesting | 51.25 | MEDIUM | P2 | HIGH | Abierto | roi_engine.py:355 |
| AUD-005 | Append concurrente pierde rastro de revalidación | OpenAI ASTRA-03 | Defecto confirmado | Concurrencia | 50.00 | MEDIUM | P2 | HIGH | Abierto | revalidation.py:71–87 |
| AUD-006 | Lector Windows hace fallar publicación | C-AUD-003 | Defecto confirmado condicionado | Robustez | 47.50 | MEDIUM | P2 | HIGH | Abierto | daily.py:439; atomic.py:45 |
| AUD-007 | Fallo de mkdir de caché pierde respuesta válida | OpenAI ASTRA-04 | Defecto confirmado | Proveedores | 42.50 | MEDIUM | P2 | HIGH | Abierto | odds_cache.py:81 |
| AUD-008 | Tests sobrescriben artefactos demo del checkout | C-AUD-005 + observación OpenAI §3/4/19 | Defecto de aislamiento | Pruebas | 52.50 | MEDIUM | P3 | HIGH | Abierto | test_pipeline_demo.py:15; conftest.py |
| AUD-009 | Comentario suprime detección de clave literal | C-AUD-012 | Defecto confirmado | Seguridad | 38.75 | LOW | P3 | HIGH | Abierto | check-secrets.sh:36,64 |
| AUD-010 | Instalador reinstala hooks anteriores | C-AUD-007 | Defecto confirmado | Gobernanza | 37.50 | LOW | P3 | HIGH | Abierto | instalar-candados.sh:90–140 |
| AUD-011 | Duración de sección crítica requiere medición | C-AUD-004, alcance reducido | Riesgo potencial | Concurrencia | N/V | No asignada | P3 investigación | LOW | Pendiente de validación | revalidation.py:267–292; lock.py |
| AUD-012 | Confianza en artefactos sin sidecar | C-AUD-006 | Riesgo potencial | Modelos/seguridad | N/V | No asignada | P3 investigación | LOW | Pendiente de validación | calibrator.py:257–263 |
| AUD-013 | Interpolaciones HTML sin origen hostil demostrado | C-AUD-008 + OpenAI §11 | Riesgo potencial | Dashboard | N/V | No asignada | P3 investigación | LOW | Pendiente de validación | html_report.py:1244–1247,1495,1550 |

## 8. P0

Ninguno. No se demostró emergencia ni daño sistémico que justifique cambios inmediatos en datos o producción.

## 9. P1

Ninguno. La existencia de serialización pickle o una carrera potencial, por sí sola, no acredita ejecución arbitraria explotable ni corrupción masiva.

## 10. P2 — Correcciones verificadas

### AUD-001 — Disponibilidad temporal del estado del backtest

- **Origen/clasificación:** Exclusivo OpenAI, ASTRA-01. Categoría defecto confirmado; área backtesting; MEDIUM, 62.50, P2, confianza HIGH, **REPRODUCED**, estado Abierto.
- **Ubicación/código:** `src/sqp/backtesting/roi_engine.py:277` ordena por fecha/equipos/ID/marcador; `:375` observa inmediatamente cada resultado. `src/sqp/backtesting/engine.py:108` comparte actualización inmediata.
- **Activación:** entrada cronológica con early 10:00, late 20:00, mismo par/día e IDs inversos.
- **Problema/esperado/observado:** cambiar solo el resultado de late no debería alterar early. Reejecución actual: early pasa de **0.5632 a 0.5416** cuando late cambia 10–0 a 0–10.
- **Causa raíz:** orden por fila confundido con disponibilidad de información. El estado del adaptador incorpora un resultado futuro.
- **Impacto:** evidencia cuantitativa contaminada; no se midió dirección ni magnitud agregada de sesgo de ROI.
- **Controles:** `_prior_games` filtra ajustes auxiliares, no el adaptador; matching de dobles jornadas no evita la reproducción con horas explícitas; test de paridad replica actualización intradía.
- **Matriz nueva:** I3, altera evidencia; A2, motores/consumidores; P2, orden específico; E3, IDs/datos corrientes; R2, recalcular; C3, controles no cubren estado. `(90+40+40+45+20+15)/4=62.50`.
- **Fix mínimo:** estimar por bloque diario antes de observar resultados si faltan tiempos de disponibilidad; conservar actualización intradía solo cuando se acredite el corte real.
- **Aceptación/regresión:** invariancia al modificar/reordenar resultados posteriores, tanto con horas como sin ellas; control de que un resultado del día previo sí modifica estimaciones. No basta ordenar por hora de inicio: inicio no equivale a resultado disponible.

### AUD-002 — Unión entre fuentes elimina una serie consecutiva

- **Origen/clasificación:** Exclusivo Claude C-AUD-002. Defecto confirmado; datos/modelado; MEDIUM, 58.75, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación/código:** `src/sqp/pipeline/daily.py:92–121`, descarte por `history_days` y `_adjacent_days` en 114–117.
- **Activación:** histórico D con A/B 3–2 y recientes D+1 A/B 1–5, D+2 A/B 4–0.
- **Esperado:** tres encuentros distintos. **Observado:** sobreviven `h1` de D y `r3` de D+2; desaparece `r2` de D+1. Reproducción nueva sobre código actual.
- **Causa raíz:** proximidad de día/equipos se usa como identidad entre proveedores; IDs no comparables no justifican eliminar un partido diferente.
- **Impacto:** modelo entrenado sin resultado reciente disponible; evidencia servida puede cambiar. No se adopta «ocurre en cada serie» sin medir fronteras del histórico/fetch.
- **Controles:** histórico acaba recuperando filas; tests de drift UTC y dobleheader no cubren esta frontera.
- **Matriz nueva:** I2, incompletitud del fit; A2, ingestión/modelo; P3, condición normal de refresco; E3, frontera específica; R2, reconciliar/recalcular; C2, backfill parcial. `(60+40+60+45+20+10)/4=58.75`.
- **Fix mínimo:** reconciliación por identidad/evento y fecha oficial cuando esté disponible; preservar encuentros distintos y tratar ambigüedad explícitamente. **No adoptar automáticamente ±6 horas ni marcador idéntico como identidad**, propuestos por Claude: no hay contrato canónico para ese umbral y dos partidos pueden acabar igual.
- **Aceptación/regresión:** conservar D/D+1/D+2, mantener un único evento ante verdadero drift UTC y no fusionar juegos diferentes con el mismo marcador. Si no hay información suficiente, declarar la ambigüedad; no borrar silenciosamente.

### AUD-003 — Tenis superseded no recupera metadata histórica

- **Origen/clasificación:** Exclusivo OpenAI ASTRA-02. Defecto confirmado; settlement; MEDIUM, 58.75, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `src/sqp/settlement/runner.py:509,564–581`.
- **Activación:** candidato archivado antes de comenzar, evento ausente del fichero vigente de predicciones y resultado ESPN disponible.
- **Esperado:** liquidación con metadata del evento archivado. **Observado:** candidato recuperado=1, liquidación `[]`; restaurar solo metadata en predicciones vigentes produce `win / PnL 10.0`. Reproducción actual con proveedor falso.
- **Causa raíz:** `_con_superseded` rescata candidatos, pero score mapping, start_times y enrichment dependen de `preds` vigente.
- **Impacto:** falta resultado en evidencia y, si hay stake real, movimiento en ledger; la ruta de expiración también necesita fecha.
- **Controles:** archivos preservan metadata, guard de eventos ya comenzados no cubre retiro previo; gates reducen exposición, no corrigen evidencia.
- **Matriz nueva:** I2, falta liquidación; A2, evidencia/ledger; P3, refrescos; E3, retiro previo; R2, recuperar archivos; C2, recuperación parcial. `(60+40+60+45+20+10)/4=58.75`.
- **Fix mínimo:** unir metadata archivada de los candidatos recuperados, con precedencia por identidad/generación; emplearla en mapping, expiración y enrichment.
- **Aceptación/regresión:** ganar/perder correctamente con evento ausente del vigente, incluso sin fichero vigente; persistencia e idempotencia al repetir.

### AUD-004 — Penalizadores configurados omitidos en ROI

- **Origen/clasificación:** Exclusivo Claude C-AUD-001. Defecto confirmado condicionado; backtesting; MEDIUM, 51.25, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `src/sqp/backtesting/roi_engine.py:355–360` frente a `src/sqp/pipeline/daily.py:860–874`; contrato en `src/sqp/markets/edge.py:35–90`.
- **Activación:** coeficiente no cero, como `books_spread_penalty=0.5`, con dispersión entre casas. Configuración versionada actual los mantiene en cero.
- **Esperado:** el benchmark aplica el coeficiente o rechaza/declarara explícitamente que no puede representarlo. **Observado:** llamada real del backtest no pasa ese coeficiente; edge ajustado **0.27099912178008023**, frente a **0.23020449978854862** al aplicar los argumentos usados por producción sobre iguales inputs. La instrumentación usa el helper real en ambos casos.
- **Causa raíz:** faltan los kwargs y datos de dispersión/movimiento/velocidad en el backtest.
- **Impacto:** evalúa otra política si se activa el término. No se afirma que ROI siempre mejore por omitir penalización: el signo depende de resultados y selección. La reproducción demuestra la divergencia de edge, no el ROI global.
- **Controles:** coeficientes cero neutralizan hoy; paridad de helpers de probabilidad no cubre estas llamadas. La exclusión documentada de calibrador/global caps no declara estos términos.
- **Matriz nueva:** I2, política condicionada; A2, benchmark y evaluación; P2, requiere activar; E2, configuración explícita; R2, recalcular; C3, paridad incompleta. `(60+40+40+30+20+15)/4=51.25`.
- **Fix mínimo:** pasar/calcular dispersión disponible y compartir construcción de argumentos; para movimiento/velocidad sin trayectoria histórica suficiente, fallar o marcar benchmark no comparable. Nunca consultar información posterior para suplirla.
- **Aceptación/regresión:** igualdad funcional de edge/stake con coeficientes no cero y datos idénticos, control cero y caso de datos históricos insuficientes. No imponer grep o identidad de helper como único criterio.

### AUD-005 — Log append sin exclusión

- **Origen/clasificación:** Exclusivo OpenAI ASTRA-03. Defecto confirmado; concurrencia/observabilidad; MEDIUM, 50.00, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `src/sqp/pipeline/revalidation.py:71–87`, llamada fuera de lock en 354; también usado para observatorio intradía.
- **Activación:** dos escritores completan read-modify-write solapados.
- **Esperado:** prior+A+B. **Observado:** `['prior','writer-A']`; writer-B desaparece. Intercalado instrumentado con escrituras atómicas reales, repetido en consolidación.
- **Causa raíz:** la operación completa carece de lock; el reemplazo único no fusiona estados leídos antes.
- **Impacto:** rastro incompleto y métricas basadas en muestras perdidas; no se demuestra pérdida de stakes en este escenario.
- **Controles:** fsync y atomicidad individual; lock de candidatos no abarca el log.
- **Matriz nueva:** I2/A2/P2/E2/R2/C2: evidencia perdida, consumidores múltiples, solapamiento específico, recuperabilidad parcial y atomicidad sin transacción. `(60+40+40+30+20+10)/4=50.00`.
- **Fix mínimo:** lock del fichero de log desde lectura hasta reemplazo.
- **Aceptación/regresión:** escritores sincronizados conservan ambas filas, incluido cambio de columnas; timeout visible y seguro. No confundir con AUD-006/AUD-011.

### AUD-006 — Publicación aborta ante lector Windows

- **Origen/clasificación:** Exclusivo Claude C-AUD-003. Defecto confirmado condicionado; robustez; MEDIUM, 47.50, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `src/sqp/pipeline/daily.py:439`, `_finalize`; `src/sqp/storage/atomic.py:45`; lectores de predicciones en closing_capture/revalidation.
- **Activación:** destino predictions abierto por lector sin permiso de borrado compartido mientras se publica la nueva versión.
- **Esperado:** contención transitoria coordinada o reintentada de forma acotada. **Observado:** `_finalize` lanza PermissionError; contenido anterior conservado. Al cerrar lector, misma llamada termina correctamente. Reproducción nueva del camino `_finalize`, no solo del helper.
- **Causa raíz:** reemplazo sin recuperación de sharing violation y sin coordinación del fichero predictions.
- **Impacto:** liga no publica nueva predicción en ese intento; puede marcar fallo del run. No se acreditó incidente real ni frecuencia de solapes programados.
- **Controles:** atomicidad preserva anterior, error visible; lock de candidatos no protege predictions ni lectores externos.
- **Matriz nueva:** I2, publicación fallida; A2, liga/orquestación; P2, lector concurrente; E2, sharing específico; R1, reintento; C2, fallo conservador. `(60+40+40+30+10+10)/4=47.50`.
- **Fix mínimo:** reintento limitado para sharing violation transitoria y coordinación de lectores/escritor internos si procede. No cambiar horarios como sustituto de corrección ni pedir éxito con un lector que nunca cierra.
- **Aceptación/regresión:** lector se libera durante plazo acotado → publica sin pérdida; lector permanente → error claro al agotar plazo, anterior intacto y temporal limpio. Mover solo el escritor bajo un lock no coordina lectores que no lo toman.

### AUD-007 — Crear caché rompe fetch válido

- **Origen/clasificación:** Exclusivo OpenAI ASTRA-04. Defecto confirmado; proveedores; MEDIUM, 42.50, P2, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `src/sqp/providers/odds_cache.py:81`; `odds_api.py:214–215`.
- **Activación:** parent de caché es archivo o mkdir denegado, después de HTTP 200.
- **Esperado:** payload válido devuelto aunque caché falle. **Observado:** FileExistsError, una llamada y seis créditos registrados en cliente, sin retorno de datos. Proveedor falso, ningún crédito real.
- **Causa raíz:** mkdir fuera del try best-effort.
- **Impacto:** fetch falla por un recurso auxiliar; reintento desperdicia respuesta anterior. No es la observación Claude O-10 sobre JSON parcialmente escrito: distinta causa y fix.
- **Controles:** captura OSError de write_text, no de mkdir; cuota se captura antes del fallo.
- **Matriz nueva:** I2/A2/P1/E2/R1/C2: fallo condicionado de ingestión, poco frecuente, recuperable y protección parcial. `(60+40+20+30+10+10)/4=42.50`.
- **Fix mínimo:** incluir mkdir en el try de persistencia best-effort.
- **Aceptación/regresión:** HTTP 200 conserva payload y cuota ante FileExistsError/PermissionError de mkdir; caché sana sigue escribiendo.

## 11. P3/P4 — Aislamiento y controles locales

### AUD-008 — Suite comparte artefactos demo del checkout

- **Origen/clasificación:** Parcialmente coincidente: C-AUD-005 y OpenAI §3/4/19. Claude lo puntúa; OpenAI detecta las escrituras y aísla la suite, sin ficha de defecto. Defecto de aislamiento; pruebas; MEDIUM, 52.50, P3, HIGH, **STATICALLY_VERIFIED**, Abierto.
- **Ubicación:** `tests/test_pipeline_demo.py:15,24,73,115`, `tests/test_calibration_live.py:134` y otros sitios enumerados por Claude; `_finalize` en `daily.py:425–439`; `tests/conftest.py` sin redirección del ROOT.
- **Activación:** ejecutar los tests demo contra un checkout con artefactos demo propios o simultáneamente con otra ejecución.
- **Esperado:** fixtures/resultados de tests aislados de artefactos del operador. **Observado estáticamente:** llamadas sin tmp_path/monkeypatch alcanzan el ROOT del paquete y sobrescriben `data/predictions/demo`; no se reprodujo contra datos reales para probarlo.
- **Causa raíz:** tests usan rutas globales de aplicación como salida compartida.
- **Impacto:** la demo del operador queda reemplazada por fixtures y ejecuciones compiten. **No se confirma contaminación live actual**: el código sí separa demo/live.
- **Controles:** carpeta demo y archivo previo; aislamiento externo usado en auditoría evita el daño, pero no cambia cómo se ejecuta normalmente la suite.
- **Matriz nueva:** I1, solo demo; A1, artefactos aislados; P4, ocurre al ejecutar; E4, comando normal; R1, regenerar; C2, separación live. `(30+20+80+60+10+10)/4=52.50`. El rango MEDIUM resulta de la fórmula obligatoria aun con impacto inmediato menor.
- **Fix mínimo:** inyectar rutas temporales en tests afectados; fixture compartido donde no cambie el contrato de pruebas que necesitan archivos del repo. Evitar parchear ciegamente todos los globals.
- **Aceptación/regresión:** suite no modifica artefactos preexistentes demo/live; test con datos centinela fuera del sandbox de prueba e instancias concurrentes independientes.

### AUD-009 — Filtro de ruido oculta secreto literal

- **Origen/clasificación:** Exclusivo Claude C-AUD-012. Defecto confirmado; seguridad; LOW, 38.75, P3, HIGH, **REPRODUCED**, Abierto.
- **Ubicación:** `.claude/hooks/check-secrets.sh:36,64`.
- **Activación:** literal que cumple detector acompañado por comentario con palabra `example`.
- **Esperado:** mismo literal detectado con/sin comentario. **Observado:** hook real en Git Bash devuelve 2 sin comentario y 0 al añadir `# replaces the example key`. Solo se usó una cadena sintética de prueba.
- **Causa raíz:** `grep -vE` descarta la línea completa en lugar del valor coincidente.
- **Impacto:** falso negativo de control local; no se afirma filtración real ni historial libre de secretos, no reescaneado en consolidación.
- **Controles:** .gitignore de .env no cubre una clave en un fichero de código; patrón de detección funciona en el control sin comentario.
- **Matriz nueva:** I2, omisión de detección; A1, hook; P1, coincidencia específica; E2, comentario; R2, revisar/rotar si hubiera exposición; C1, otras barreras parciales. `(60+20+20+30+20+5)/4=38.75`.
- **Fix mínimo:** filtrar placeholders sobre el valor capturado, no sobre comentarios. Añadir otra herramienta de CI es opcional, no requisito para cerrar esta causa.
- **Aceptación/regresión:** literal sintético alertado con comentario example; placeholders auténticos y referencias a entorno no alertados; probar asignaciones de Python/BAT/YAML.

### AUD-010 — Instalador revierte controles de hooks

- **Origen/clasificación:** Exclusivo Claude C-AUD-007. Defecto confirmado; gobernanza; LOW, 37.50, P3, HIGH, **STATICALLY_VERIFIED**, Abierto.
- **Ubicación:** `instalar-candados.sh:90–140`, heredocs HOOK2/HOOK3; `.claude/hooks/mark-crossreview-pending.sh:19` y `crossreview-on-stop.sh` actuales.
- **Activación:** ejecutar el instalador existente sobre la configuración vigente.
- **Esperado:** instalar controles actuales sin perder cobertura. **Observado estáticamente:** sobrescribe HOOK2 con lector exclusivo de `tool_input.file_path`, mientras el hook actual deriva destinos Bash mediante `_targets.py`; HOOK3 contiene invocación y selección de alcance antiguas.
- **Causa raíz:** dos copias divergentes del código de instalación/runtime.
- **Impacto:** ediciones Bash pueden dejar de marcar revisión; se pierden controles actuales. No se ejecutó el instalador ni se lanzó una revisión externa para demostrarlo.
- **Controles:** backups antes de sobrescritura; instalación manual, no diaria.
- **Matriz nueva:** I1, control local; A1; P2, reinstalación posible; E3, script listo; R1, backup; C1. `(30+20+40+45+10+5)/4=37.50`.
- **Fix mínimo:** instalador use fuente única o verifique equivalencia semántica con hooks actuales.
- **Aceptación/regresión:** instalar en árbol temporal conserva derivación de rutas Bash y selección de alcance vigente; stubs locales evitan llamadas de pago. No exigir identidad textual si hay diferencias legítimas de empaquetado.

No hay P4 correctivos confirmados. Las oportunidades generales descartadas se documentan en sección 15, sin convertirlas en obligaciones técnicas.

## 12. Coincidencias

- **AUD-008:** coincidencia parcial respaldada por código entre aislamiento identificado por Claude y la decisión explícita OpenAI de usar copia temporal.
- **AUD-013:** coincidencia parcial de observaciones sobre HTML, todavía no verificable como vulnerabilidad explotable.
- Ambos describen atomicidad/locks y suite verde; eso no confirma ningún defecto por voto.
- No fusionar C-AUD-001 con ASTRA-01: argumentos de penalización frente a estado temporal. No fusionar C-AUD-003/004 con ASTRA-03: contención de fichero, caducidad del lock y actualización perdida son diferentes.

## 13. Hallazgos exclusivos y trazabilidad completa

| Entrada original | Resultado consolidado | Clasificación cruzada |
|---|---|---|
| C-AUD-001 | AUD-004 | Exclusivo Claude |
| C-AUD-002 | AUD-002 | Exclusivo Claude |
| C-AUD-003 | AUD-006 | Exclusivo Claude |
| C-AUD-004 | AUD-011; rama de ruptura Windows refutada | No verificable en alcance residual |
| C-AUD-005 | AUD-008 | Parcialmente coincidente |
| C-AUD-006 | AUD-012 | No verificable como explotación |
| C-AUD-007 | AUD-010 | Exclusivo Claude |
| C-AUD-008 | AUD-013 | No verificable; observación parcial OpenAI |
| C-AUD-009 | Sin ticket correctivo | Falso positivo Claude como defecto actual |
| C-AUD-010 | Sin ticket correctivo | Falso positivo Claude como exigencia al árbol actual |
| C-AUD-011 | Sin ticket correctivo | Falso positivo Claude como defecto demostrado |
| ASTRA-01 | AUD-001 | Exclusivo OpenAI |
| ASTRA-02 | AUD-003 | Exclusivo OpenAI |
| ASTRA-03 | AUD-005 | Exclusivo OpenAI |
| ASTRA-04 | AUD-007 | Exclusivo OpenAI |

Las diez observaciones Claude también fueron adjudicadas: O-1 identidad de selección heredada, sin nueva ruta productiva demostrada; O-2 p_eff fuera de rango absorbida por Kelly, no defecto adicional; O-3 K y multiplicidad, requiere contrato estadístico específico, no se altera por esta consolidación; O-4/O-6 estado de tareas, no revalidado; O-5 aviso de intérprete, riesgo operativo sin incidente acreditado; O-7 override explícito, no defecto por existir; O-8/O-9 forma de tests, sin fallo adicional demostrado; O-10 escritura no atómica de caché, observación de coste distinta de AUD-007 y no promovida a defecto. No se suman estas notas como tickets ni como falsos positivos puntuados.

## 14. Discrepancias entre auditores

### D-01 — Fuga temporal

Claude concluye que no detectó fuga porque el backtest es walk-forward. OpenAI presenta cambio de early al modificar late. Código revisado: orden por IDs y observe inmediato. Reproducción actual respalda AUD-001: walk-forward por filas no garantiza corte temporal. La conclusión global de ausencia de fuga se rechaza.

### D-02 — Ruptura del lock vivo en Windows

Claude propone pérdida de candidatos después de 300 segundos por borrado del lock vivo. OpenAI señala controles del lock pero no ese defecto. Código actual conserva descriptor abierto y captura PermissionError al unlink. Reproducción: mtime envejecido 600 segundos, stale_s=300 y timeout=0; segundo acceso lanza LockNoAdquiridoError y el lock sigue presente. Se refuta esa rama en Windows; la medición de retenciones largas queda en AUD-011. No confundir con la pérdida reproducida del log sin lock (AUD-005).

### D-03 — Paridad condicionada y signo de ROI

Claude puntúa C-AUD-001 en 63.8 como riesgo no ejecutado; OpenAI no lo reporta. Se confirma mediante llamada real que `books_spread_penalty` no llega al helper y cambia edge cuando se aplica. Se adopta defecto condicionado 51.25 con alcance menor: coeficientes cero neutralizan configuración versionada y no puede asegurarse que ROI sea siempre más optimista. La reproducción no requiere activar configuración del proyecto.

### D-04 — Sidecar como barrera de seguridad

Claude propone rechazar artefactos sin sidecar. OpenAI no acredita entrada maliciosa a loaders locales. Código y test de compatibilidad permiten explícitamente artefactos legados. Metadata actual confirma 13 joblib y 1 sidecar, registro de 4 entradas, pero no una frontera de permisos que convierta el hash adyacente en autenticación. Resultado AUD-012, no vulnerabilidad confirmada ni autorización para apagar calibradores.

### D-05 — XSS y origen del campo market

Claude afirma escenario con mercado hostil del proveedor; OpenAI mantiene inferencia sin origen controlable. Se verificaron interpolaciones, `_picks_records`, `_todos_records` y `build_model_map`: producción construye keys h2h/spreads/totals desde el modelo, por lo que una key arbitraria del proveedor no llega automáticamente a la salida. CSV editado localmente es otra frontera de confianza, aún no acreditada. Resultado AUD-013; no se afirma XSS confirmado. Un test de buscar la cadena en el HTML fuente no valida cómo el navegador interpreta el DOM.

### D-06 — Deuda y artefactos históricos como defectos

Claude puntúa ciclo de imports, manifiesto/parche históricos y cobertura/hardening de CI; OpenAI no los trata como defectos demostrados. Se contrastan diferimiento intencional, contrato del paquete/base_commit y matriz CI. Se descartan tres como defectos actuales bajo AGENTS; las oportunidades siguen disponibles. Detalle en sección 15.

### D-07 — Motivo de la prueba omitida

Claude atribuye su único skip a `test_open_dashboard.py`; OpenAI lo identifica en `test_review_v2.py:228`. Esa parametrización omite incondicionalmente severity por enum; open_dashboard tiene cuatro tests sujetos al mismo skipif Windows/PowerShell. No se adopta la atribución de Claude: el log y ejecución estrecha previos OpenAI prueban el skip del enum en este entorno. Se registra como error de evidencia del informe, **no otro defecto del proyecto ni otro falso positivo contabilizado**.

### D-08 — «No altera probabilidades/liquidación»

Claude afirma ausencia global de impacto actual, aunque C-AUD-002 describe pérdida de resultados para ratings. OpenAI confirma falta de liquidación de tenis. Código actual y reproducciones de ambas rutas respaldan AUD-002/003. Se rechaza la afirmación global; se conserva la limitación de que no se cuantificó impacto histórico ni staking real. Gates cerrados no neutralizan pérdida de evidencia.

## 15. Falsos positivos descartados

Aquí «falso positivo» significa **adopción como defecto actual no respaldada**, no que todos los hechos descriptivos del auditor fueran falsos.

1. **C-AUD-009 — Ciclo de imports. DISMISSED como defecto.** `daily.py:757–773` conserva el import diferido precisamente para evitar inicialización circular; los imports y pruebas actuales funcionan. El escenario que falla exige mover ese import en un refactor futuro. No hay impacto actual ni riesgo material adicional demostrado. Simplificar dependencias es una oportunidad; no imponer AST/Tarjan o cero ciclos como contrato nuevo.
2. **C-AUD-010 — BUILD_INFO/OPTIMIZATION obsoletos. DISMISSED como obligación de reflejar HEAD.** `BUILD_INFO.json` identifica bundle 20260910 y base_commit específico; `IMPLEMENTACION.md:96–109` dice que el parche se construyó contra esa base y que árboles posteriores pueden requerir integración manual, con `git apply --check`. No hay consumidor funcional de esos artefactos en scripts/tests. Hash distinto a HEAD o fallo de reverse-check en otro árbol no prueba un defecto del paquete histórico. No se adopta borrarlos o regenerarlos para HEAD; validar el bundle histórico sería otra comprobación.
3. **C-AUD-011 — CI/hardening. DISMISSED como defecto demostrado.** Matriz Windows 3.12 y Linux 3.14, tags mutables y pip-audit flotante son hechos verificables; no se aportó ni reprodujo regresión exclusiva Windows+3.14, compromiso de acción o build roto. El alcance demo de Docker es explícito. Son mejoras opcionales. La frase «ningún .ps1 se ejecuta» además es demasiado amplia: `tests/test_open_dashboard.py` ejecuta el script real en sandbox de prueba.

No hay ficha OpenAI descartada. La rama de ruptura de lock de C-AUD-004 está refutada, pero la entrada completa se conserva para investigación de duración: no se cuenta dos veces como falso positivo completo y no verificable. Estos descartes son sobre el código actual; no autorizan ignorar patrones futuros.

## 16. No verificables — Tickets de investigación

### AUD-011 — Duración real del lock de revalidación

Origen C-AUD-004; categoría riesgo potencial; área concurrencia; P3 investigación; confianza LOW; **INFERRED**; clasificación cruzada No verificable; estado Pendiente de validación. Ubicación `revalidation.py:267–292`, `lock.py:36–37,68–95`.

Hecho: `_league_odds` se ejecuta dentro del lock cuando hay evaluables. No acreditado: una carga actual que supere el timeout de 120 segundos. Rama refutada: borrar un lock vivo retenido por este código en Windows después de 300 segundos. No transferir esa refutación a POSIX, que no fue ejecutado.

Impacto residual hipotético: espera excesiva/timeout operativo. Score/severidad: **no asignados**; no usar la puntuación original de corrupción para una espera aún no medida. Recomendación: medir duración y contención con cargas representativas y read-only, luego acotar sección crítica si evidencia lo justifica. Aceptación de investigación: tiempo por fase y ruta de timeout reproducidos; regresión de titular vivo que permanece excluyente. No se exige heartbeat ni cambio de scheduler sin demostrar necesidad.

### AUD-012 — Modelo de confianza de artefactos legados

Origen C-AUD-006; riesgo potencial; seguridad/modelos; P3 investigación; LOW; **INFERRED**; No verificable como explotación; Pendiente de validación. Ubicación `calibrator.py:70–80,257–263`, `tests/test_ml_models.py:133`.

Hecho: falta sidecar permite cargar por compatibilidad; 13 joblib/1 sidecar observados por metadata. No acreditado: actor o fuente no confiable con acceso a artefactos pero fuera de la frontera del código ejecutado. Un digest adyacente que el mismo actor puede reescribir no autentica origen.

Score/severidad no asignados. Recomendación: establecer procedencia, permisos y contrato de confianza antes de cambiar carga; si se migra, verificar artefactos y planificar continuidad. Aceptación: política aprobada que distingue legado legítimo/alteración, sin apagar silenciosamente modelos sanos. Tests: mismatch, legado permitido por contrato y artefacto fuera de frontera admitida. No se marca Aceptado como riesgo por decisión del auditor; eso requiere decisión del responsable.

### AUD-013 — Entrada no confiable a sinks HTML

Origen C-AUD-008 y candidato OpenAI §11; riesgo potencial; dashboard/seguridad; P3 investigación; LOW; **INFERRED**; No verificable; Pendiente de validación. Ubicación `html_report.py:1175,1244–1247,1474,1495,1550`.

Hecho: varios sinks interpolan campos sin esc. No acreditado: recorrido desde entrada adversaria aceptada hasta ejecución en navegador; fechas y motivos se construyen internamente y keys de mercado de producción provienen de mapa cerrado. CSV manipulado necesita contrato de confianza explícito.

Score/severidad no asignados. Recomendación: rastrear productor→serialización→DOM y usar texto seguro en los sinks si procede. Aceptación: reproducción de ruta real o descarte por validación de origen; test de navegador/DOM con canario inocuo y sin red, no solo búsqueda de una cadena en JSON embebido. No agrupar mecánicamente campos con orígenes diferentes.

## 17. Causas raíz principales

1. **Información y disponibilidad distintas:** AUD-001 confunde orden con corte; AUD-002 usa día/equipos como identidad; AUD-003 depende de metadata vigente para un evento histórico.
2. **Contratos parcialmente propagados:** AUD-004 no transporta términos del penalizador; AUD-007 deja una operación fuera del best-effort; AUD-010 tiene dos fuentes de hooks divergentes.
3. **Estado compartido sin frontera completa:** AUD-005 protege escritura pero no transacción; AUD-006 no maneja lector concurrente; AUD-008 comparte salidas demo entre tests y operador.
4. **Filtrado demasiado amplio:** AUD-009 suprime evidencia por texto ajeno al valor sensible.

No se propone una refactorización masiva de estas cuatro familias: los diez fixes pueden revisarse y validarse por separado.

## 18. Plan de remediación por fases

| Fase | Tickets | Acción |
|---|---|---|
| 0 — Emergencia | Ninguno | Sin intervención operativa inmediata |
| 1 — Riesgo elevado | Ninguno | Sin P1/HIGH confirmado |
| 2 — Estabilización | AUD-001–007 | Corregir temporalidad, identidad y metadata; paridad de penalizadores; append, contención y caché |
| 3 — Calidad estructural | AUD-008–010 | Aislar tests y reparar controles concretos de secretos/instalación |
| 3 — Investigación | AUD-011–013 | Recabar condición faltante antes de asignar severidad o implementar política nueva |
| 4 — Mejoras | Sin obligación | Considerar simplificación de imports/CI/documentación según prioridades del responsable |

Orden P2: AUD-001, AUD-002, AUD-003, AUD-004, AUD-005, AUD-006, AUD-007. Dentro de P3 correctivo: AUD-008, AUD-009, AUD-010. AUD-008 puede adelantarse como habilitador para ejecutar regresiones del pipeline sin tocar artefactos, aunque tenga prioridad operativa menor.

AUD-001 y AUD-002 deben resolverse antes de usar una nueva medición histórica como criterio de aprobación de modelos; AUD-004 añade la condición de paridad cuando se ensayan coeficientes. AUD-003 requiere inventario de candidatos pendientes antes de cualquier reparación de datos. La corrección del código no autoriza automáticamente reescribir ledger, promover modelos, cambiar stakes ni mover tareas.

Cada implementación futura: seleccionar ticket, revalidar, cambio mínimo, test discriminante, validación relevante, criterio de aceptación y estado Pendiente de validación/Corregido solo con evidencia. No hay ticket marcado Corregido durante esta consolidación.

## 19. Pruebas de regresión recomendadas

| Ticket | Invariante verificable |
|---|---|
| AUD-001 | Resultado posterior no modifica estimación previa; dato previo sí puede hacerlo |
| AUD-002 | Encuentros consecutivos distintos conservados; duplicado real UTC reconciliado |
| AUD-003 | Candidato archivado se liquida sin metadata vigente; segunda ejecución idempotente |
| AUD-004 | Penalizador no cero modifica benchmark como producción, o declara dato insuficiente |
| AUD-005 | Ambos append concurrentes sobreviven con unión de esquema |
| AUD-006 | Lector transitorio permite publicación al liberar; permanente falla acotadamente |
| AUD-007 | Fallo de mkdir de caché conserva payload HTTP válido y cuota |
| AUD-008 | Datos demo/live centinela ajenos a fixture permanecen intactos |
| AUD-009 | Comentario example no suprime literal; placeholder auténtico no alerta |
| AUD-010 | Instalación aislada conserva cobertura Bash y alcance de revisión vigente |
| AUD-011–013 | Primero reproducir condición faltante; no escribir tests que inventen el contrato |

Reproducciones conservadas en `.codex-tmp/astra_reproduce.py` y `.codex-tmp/consolidation_reproduce.py`; scratch nuevo de consolidación: `.codex-tmp/consolidate-s0f1xf2o/`. La segunda usa inputs deportivos sintéticos, instrumenta kwargs del helper real, mantiene un lector real Windows, envejece únicamente un lock temporal y ejecuta el detector sobre un literal artificial. No llama a APIs deportivas. La suite dirigida verde no cierra estos tickets: sus escenarios nuevos siguen reproduciendo anomalías.

## 20. Comparación histórica

Después de consolidar el estado actual se comprobó `audits/consolidated/latest.md`: no existía. `audits/consolidated/history/` no contenía informes. No hubo archivo previo que archivar ni estado histórico que revalidar.

Diez defectos confirmados nuevos para esta primera consolidación; tres investigaciones nuevas. Persistentes, corregidos y regresiones: cero identificados. «Nuevo» significa nuevo en el backlog consolidado, no introducido por el último commit. Las fuentes son del mismo HEAD; esta tarea no es revisión de una regresión entre versiones.

## 21. Conclusiones

Este informe es el backlog técnico de auditoría de referencia: diez correcciones confirmadas, tres investigaciones y tres entradas descartadas como defectos actuales. Ocho discrepancias quedan justificadas por evidencia y contratos, sin voto entre auditores ni promedio de severidades.

No corresponde PASS ni implementación automática. Los informes fuente, el archivo de tarea preexistente y el código del proyecto se preservan. Las próximas acciones deben seguir los criterios individuales, especialmente invariancia temporal, identidad de encuentros, liquidación idempotente y conservación de escrituras concurrentes.
