# Diagnóstico independiente — OpenAI

Ronda: **audit-2026-09-18**. Base: **59521643440213f6a7982b10e71d349a8d8dd088**. Inspección: 2026-09-18, hasta aproximadamente 03:15 UTC. Alcance integral por inventario, con revisión selectiva de rutas críticas; no equivale a revisión exhaustiva de cada archivo.

## Resultado

**3 defectos confirmados: CRITICAL 0, HIGH 0, MEDIUM 2, LOW 1. P0: 0; P1: 0.** Dos reproducciones controladas y una demostración estática. Los defectos afectan a la consulta/observabilidad del prediction gate y a su tolerancia a registros inválidos. No se demostró una autorización indebida de stake por el pipeline real.

**306 tests focalizados aprobados** (210 + 96), Ruff satisfactorio y MyPy satisfactorio en 105 archivos. No se emite PASS: hay defectos y faltan pruebas del estado efectivo de CI, tareas programadas y ejecución completa de hooks.

La configuración efectiva de esta sesión es shadow_mode=false, prediction_gate_enabled=true, clv_gate_enabled=false, calibration_enabled=true, calibration_auto_promote=false, revalidation_enabled=true y frescura de revalidación=90 minutos. No se extrapola este entorno al proceso del Programador de tareas.

## Alcance, independencia y seguridad

- Se leyeron AGENTS.md, el contrato canónico de auditoría y las referencias audit-areas, discovery-coverage, quant-ml y skills-instructions. No se delegó ni se ejecutaron servicios de pago, instalaciones, commits, pushes o despliegues.
- El HEAD coincide con la base coordinada. Al comenzar había eliminaciones de entregables anteriores de audit/latest, MANIFEST modificado y audit/audit-2026-09-16 sin seguimiento. Son cambios preexistentes de preparación de ronda, no cambios del auditor.
- No se modificó el MANIFEST ni se leyó audit/latest/claude/. El subdirectorio openai no contenía REPORT.md ni EVIDENCE.json previos que preservar.
- Durante el análisis principal no se leyeron informes históricos. Una búsqueda de referencias a gate_status alcanzó incidentalmente .claude/memory/project-decisions.md:282, que menciona una divergencia histórica de ese script. La sospecha ya se había obtenido leyendo el código; se declara esta exposición secundaria y se confirma únicamente con ejecución propia. El manifest también contiene contexto agregado del coordinador, sin detalle de defectos.
- Las conclusiones propias se fijaron antes de consultar por términos el FINDINGS.md preservado de audit-2026-09-16. Esa comparación fue limitada, no una nueva verificación completa del backlog.
- Los únicos entregables escritos deliberadamente son este informe y EVIDENCE.json. Las validaciones crearon temporales/caché de tipos bajo .codex-tmp, conforme a la excepción de validación. Además, los módulos importados por pytest usan el logger real: hubo actividad contemporánea en logs/sqp.log y es posible atribuirle mensajes de las pruebas, pero no separar todos sus bytes de actividad concurrente. Es un efecto incidental de la validación; no se borró ni restauró el log. La lectura posterior de configuración deshabilitó el handler de archivo en memoria.
- No se leyeron ni mostraron valores de secretos. git ls-files .env indica que .env no está versionado; esto no sustituye un escaneo histórico completo. Los datos se recorrieron mediante agregados/streaming, sin volcarlos al contexto.

## Inventario y cobertura

Inventario observado excluyendo __pycache__: 105 archivos Python en src, 65 Python/3 PowerShell/1 CMD en scripts, 145 Python en tests, 5 YAML en configs, 52 Markdown en .claude/skills y 2 Python/7 shell en .claude/hooks. También hay BAT operativos, workflow GitHub Actions, Dockerfile, artefactos joblib, CSV/JSON y documentación. Las cantidades describen archivos, no cobertura de líneas.

| Área / criticidad | Componentes y método | Estado y evidencia efectiva | Límites |
|---|---|---|---|
| Arquitectura y ejecución / P0 | daily.py, run_all.py, DIARIO_COMPLETO.bat; reconstrucción de captura→predicción→gates→persistencia→liquidación | REVISADA_PARCIALMENTE; guard previo a sobrescribir picks y carga de gates inspeccionados | No se ejecutó el diario real |
| Probabilidades, riesgo y frescura / P0 | prediction_gate, clv_gate, kelly, revalidation; código, reproducción y tests | REVISADA_PARCIALMENTE; casos focalizados aprobados; 90 min leídos de Settings.load | No todas las distribuciones/deportes ni ejecución real |
| Temporalidad y backtests / P0 | temporal.py, ml_train, engine, roi_engine; tests de cutoff, rest/form y audit_temporal | REVISADA_PARCIALMENTE; splits diarios en ML y actualización por lote diario en backtests | Sin backtest completo ni rentabilidad validada |
| Calibración y promoción / P0 | data.py, calibrator.py, pergame; inspección de dedup, agrupación por evento, staging, sidecars y muestra | REVISADA_PARCIALMENTE; tests de proyección de entrenamiento pasan; auto_promote desactivado en esta sesión | No se reentrenó ni se promovió; ver incertidumbre temporal |
| Liquidación y ROI / P0 | settle.py, settlement_math, consumidores; tests de ROI realizado | REVISADA_PARCIALMENTE; pruebas de resultados parciales y denominador común aprobadas | Sin regraduar datos reales |
| Persistencia y concurrencia / P0 | atomic.py, lock.py, served_store; tests Windows de lectores y storage | REVISADA_PARCIALMENTE; pruebas de contención y reemplazo atómico pasan | No estrés multiproceso de todos los escritores ni simulación de corte eléctrico |
| APIs y cuota / P1 | odds_api, cache y revalidation; lectura de reintentos, redacción de query, modo offline y tests mock | REVISADA_PARCIALMENTE; tests de reintentos pasan | Sin llamadas externas; no se certifica disponibilidad/cuota actual |
| Datos operativos / P0 | CSV graded y candidates, streaming con csv.DictReader | REVISADA_PARCIALMENTE; 26.774 filas graduadas, 182 candidatas; sin stake positivo en candidatas; una fila sin implied_probability_novig interpretable en cada conjunto | Sin comprobar cada resultado contra proveedor ni cargar datasets completos |
| Seguridad / P0 | .env tracking, redacción de errores, sidecars y permisos CI | REVISADA_PARCIALMENTE; .env no versionado, HTTP errors redactan query; sidecar incorrecto bloquea carga ML | Sin análisis de historial de secretos, ACL externas o prueba de explotación; hash local no autentica origen |
| Dependencias / P1 | pyproject, lock, Dockerfile | REVISADA_PARCIALMENTE; Python 3.14.4; restricciones y versiones declaradas inspeccionadas | No pip-audit actual, no instalación ni build Docker |
| CI / P1 | ci.yml; intento de gh run list | NO_VERIFICABLE para estado: gh no disponible, exit 1. Configuración revisada: Python 3.11–3.14, Windows 3.12, lint/tipos/tests/auditoría de dependencias | No inferir CI verde de checks locales |
| Hooks / P1 | settings.json, run-tests-on-stop, crossreview-on-stop, require-dispatch-model, targets | REVISADA_PARCIALMENTE; tests de targets/cableado pasan; timeouts configurados 600 s en Stop | No se invocaron hooks mutadores ni revisión externa; duración/veredicto real del último Stop no verificable. core.hooksPath sin valor y .git/hooks sólo samples |
| Tareas programadas / P1 | BAT y scripts; consulta Get-ScheduledTask | NO_VERIFICABLE para estado: acceso denegado HRESULT 0x80041003, exit 1 | Logs tienen actividad, pero no prueban código de salida/estado de la tarea |
| Gates persistidos / P0 | JSON actuales, agregados | REVISADA_PARCIALMENTE: prediction 2026-09-17T15:09:35Z, 48 mercados, 0 allowed, todos muestra_insuficiente; CLV 15:09:33Z, 50 mercados, 0 allowed; degradación generado 15:01:16Z, 58 entradas | No se recalculó el gate desde todos los datos ni se certificó su siguiente ejecución |
| Observabilidad / P1 | logs por últimas 2.000 líneas y metadatos | REVISADA_PARCIALMENTE; capture_close llega a 2026-09-18 00:00:10; diario a 2026-09-17 12:10:25; sin bloques Logging error en las colas examinadas | Timestamps del log no normalizados a UTC; colas contienen errores históricos y mensajes de validación; conteos no equivalen a incidentes nuevos |
| Skills, prompts, routing / P2 | audit-workflow, model-routing, skill clv-shadow-exit, consumidores y tests | REVISADA_PARCIALMENTE;  tests sync/routing y targets pasan; referencia a gate_status activa y defectuosa | No se validó disponibilidad real de modelos ni se ejecutaron loops |
| Utilidades, reportes y modelos experimentales / P2–P3 | Inventario; gate_status revisado; ML inferencia leído | REVISADA_PARCIALMENTE; modelos ML separados de la ruta simulada de picks según código/consumidores inspeccionados | No revisión completa de HTML/JS, utilidades de limpieza o ejemplos |
| Caches, binarios, históricos y datos masivos | Inventario y metadatos | EXCLUIDA su revisión exhaustiva por seguridad y coste | No deserializar modelos ni ejecutar limpieza |
| Web pública, pagos y migraciones SQL | No identificados como arquitectura primaria del flujo inspeccionado | NO_APLICABLE a este alcance operativo | No equivale a inventario de infraestructura externa |

## Hallazgos confirmados

### OPENAI-001 — La consulta del prediction gate evalúa otro criterio y anuncia aprobaciones falsas

- **Categoría:** corrección cuantitativa / información operativa.
- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/líneas:** scripts/gate_status.py:41–86 y :100; referencia operativa en .claude/skills/clv-shadow-exit/SKILL.md:61. Contrato en src/sqp/risk/prediction_gate.py:_usable, _independent_units, _decide y _apply_latch.
- **Activación:** consultar el estado con pick_history que satisface el test de aciertos del script pero no el test pareado del modelo, o con repeticiones/fechas fuera de ventana/estado de entrada bloqueado.
- **Problema y causa raíz:** la vista reconstruye otra regla: usa pick_history y estimated_probability, cuenta filas y aciertos contra 0,5 y promedia p−1/cuota. El gate real usa stream graduado, model_probability, comparación de errores Brier frente a no-vig por evento, ventana posterior al pre-registro, EV por unidad, test único y pestillo. Compartir MIN_N y ALPHA no hace equivalentes los procedimientos.
- **Evidencia concreta:** main() ejecutado con read_csv y exists sustituidos en memoria; 300 filas de un mismo evento, win, p_model=p_estimada=0,7, p_mercado=0,8 y cuota=1,5. La consola imprime PASAN EL GATE, n=300, hit_rate=1, mean_ev=0,0333. evaluate_markets sobre las mismas filas devuelve n=1, wins=0, p_value=1, ev_flat=0,05 y allowed=false, muestra_insuficiente.
- **Esperado:** presentar la decisión final persistida y, si se calcula progreso, usar la evaluación canónica con la muestra apropiada, claramente separada del estado final.
- **Observado:** autorización aparente de un mercado cuya muestra no basta y cuyo modelo pierde frente al mercado.
- **Consecuencia:** diagnóstico operativo falso y posible decisión humana equivocada. No se demostró stake real autorizado: el consumidor daily usa el gate canónico.
- **Controles existentes:** daily y el registro siguen denegando; todos los mercados del registro actual están denegados.
- **Corrección mínima:** leer load_prediction_gate para el estado final; reutilizar evaluate_markets sobre el stream graduado para progreso. Eliminar la regla paralela del script.
- **Pruebas y aceptación:** CLI con eventos repetidos, favoritos acertados peor que no-vig, fecha anterior al cutoff, test consumido y pestillo. Nunca anunciar aprobación cuando market_allowed del registro sea falso; distinguir evaluación provisional de autorización.
- **Limitaciones:** reproducción sintética, sin modificar pick_history real; no se atribuye una decisión humana o pérdida económica observada.

### OPENAI-002 — JSON con raíz no objeto rompe la denegación por defecto

- **Categoría:** robustez / disponibilidad.
- **Severidad MEDIUM; confianza HIGH; evidencia REPRODUCED; prioridad P2.**
- **Archivo/línea:** src/sqp/risk/prediction_gate.py:544; llamada en src/sqp/pipeline/daily.py:641.
- **Activación:** prediction_gate.json existe y contiene JSON válido con raíz lista, número o null, por corrupción semántica o edición/recuperación incorrecta.
- **Problema:** el cargador aplica .get a json.loads sin comprobar dict. El except sólo captura OSError y JSONDecodeError.
- **Evidencia concreta:** Path.exists y read_text sustituidos en memoria para devolver []; load_prediction_gate lanza AttributeError: 'list' object has no attribute 'get'. La llamada a este cargador en daily no tiene una recuperación local a {}.
- **Esperado:** devolver {} y continuar con stake cero, según docstring y comentario del consumidor.
- **Observado:** excepción que aborta la ruta de generación de esa liga; el orquestador puede contener el fallo a su nivel, pero no generar las predicciones esperadas.
- **Causa raíz:** validación sintáctica sin validación del tipo de raíz.
- **Consecuencia:** indisponibilidad condicionada de generación de predicciones; no apertura del gate.
- **Controles existentes:** persistencia atómica reduce truncamientos, JSON sintácticamente inválido ya se captura y clv_gate.load_clv_gate sí comprueba isinstance(payload, dict). Ninguno evita esta raíz válida de tipo incorrecto.
- **Corrección mínima:** validar raíz antes de .get y retornar {} si no es dict; validar también entradas antes de consumirlas, sin ampliar la autorización.
- **Pruebas y aceptación:** [], null, 1, cadena, JSON roto y markets de tipo incorrecto deben denegar sin excepción; caso objeto válido conserva comportamiento.
- **Limitaciones:** el registro operativo inspeccionado es un objeto válido. No se observó el disparador en producción ni se manipuló archivo real.

### OPENAI-003 — El log diario confunde evaluación estadística con autorización final

- **Categoría:** observabilidad.
- **Severidad LOW; confianza HIGH; evidencia STATICALLY_VERIFIED; prioridad P3.**
- **Archivo/líneas:** scripts/run_all.py:305–313.
- **Activación:** evaluate_markets aprueba estadísticamente, pero el registro previo tiene test de entrada consumido sin pasar o pestillo que impide reentrada.
- **Problema:** después de write_prediction_gate, la lista anunciada como “habilitados para stake real” se calcula desde decided, obtenido antes de aplicar _apply_latch.
- **Evidencia concreta:** una decisión allowed=true con n=300 y un previo allowed=false, entry_test_at=2026-09-16 se transforma mediante _apply_latch en allowed=false, reason=agotado_test_unico. El código del log sigue leyendo el true de la tabla original. Se ejecutó esta transformación en memoria; no se ejecutó run_all completo.
- **Esperado:** informar el allowed final persistido, separándolo de la elegibilidad estadística.
- **Observado:** camino estático inequívoco hacia mensaje de habilitación falsa.
- **Causa raíz:** se utiliza el resultado anterior a la aplicación del estado persistente.
- **Consecuencia:** el operador recibe un veredicto incorrecto en el log aunque el pipeline conserve stake cero.
- **Controles existentes:** write_prediction_gate y daily respetan el estado final; update_prediction_gate.py ya diferencia ambas fases y lee el registro tras escribir.
- **Corrección mínima:** construir ok desde load_prediction_gate/market_allowed después de la escritura; mantener la tabla sólo como progreso.
- **Pruebas y aceptación:** capturar el log con estado anterior agotado y latched; la lista anunciada debe coincidir exactamente con mercados autorizados por el registro.
- **Limitaciones:** activación no presente en el registro actual, donde todos carecen de muestra. No se reprodujo el CLI completo.

## Incertidumbres y descartes

- **NOT_VERIFIABLE:** estado remoto de CI; última ejecución/resultado de tareas; ejecución efectiva y duración de hooks Stop; vulnerabilidades actuales de dependencias; equivalencia de configuración de esta sesión con producción programada.
- **INFERRED:** train_calibration divide por grupos de evento ordenados por fecha y puede poner distintos eventos del mismo día a ambos lados; todavía falta reconstruir su cutoff de disponibilidad real y una evaluación discriminante con datos y horarios. No se confirma leakage ni se asigna severidad.
- **NOT_VERIFIABLE:** concurrencia completa de escritura/liberación del prediction gate. Las escrituras atómicas no prueban serialización de read-modify-write; no se demostró un intercalado operativo ni se ensayó sobre datos reales.
- **DISMISSED:** la divergencia de gate_status no prueba bypass del gate del pipeline: daily carga la implementación canónica.
- **DISMISSED:** no hay evidencia de fallo funcional en las 52 incidencias iniciales de pytest: ocurrieron preparando basetemp y desaparecieron al aislar el directorio.
- **DISMISSED:** los conteos de ERROR/WARNING del log no son defectos nuevos por sí solos; mezclan historia, controles deliberados y potenciales emisiones de pruebas.
- Sin afirmación de rentabilidad, de ausencia total de secretos, ni de cobertura completa por aprobar tests.

## Validaciones

| Comando / alcance | Exit | Resultado / clasificación |
|---|---:|---|
| python --version | 0 | Python 3.14.4 |
| python -B -m ruff check --no-cache src scripts tests | 0 | All checks passed |
| python -B -m mypy --no-incremental --cache-dir=.codex-tmp/mypy-openai-20260918 src | 0 | 105 archivos, sin errores |
| pytest focalizado, 9 archivos, -p no:cacheprovider --basetemp=.codex-tmp/pytest | 1 | 158 passed, 52 setup errors; ENVIRONMENTAL_FAILURE, WinError 5 al gestionar el basetemp existente |
| Mismos 9 archivos, --basetemp=.codex-tmp/pytest-openai-20260918 | 0 | 210 passed, 44,38 s |
| 7 archivos adicionales, --basetemp=.codex-tmp/pytest-openai-storage-20260918 | 0 | 96 passed, 59,04 s |
| Reproducciones Python en memoria, comando completo en EVIDENCE | 0 | OPENAI-001/002 reproducidos; transformación que sustenta OPENAI-003 |
| gh run list --branch main --limit 3 --json ... | 1 | ENVIRONMENTAL_FAILURE: ejecutable no disponible |
| Get-ScheduledTask y Get-ScheduledTaskInfo | 1 | ENVIRONMENTAL_FAILURE: acceso denegado |
| Git status de src/scripts/tests/configs/BAT/manifiestos al cierre técnico | 0 | Sin cambios; advertencias de acceso al ignore global |
| Agregados de datos y gates; Settings.load con logger de archivo deshabilitado | 0 | Resultados descritos arriba |

Se usaron directorios temporales exclusivos tras comprobar el fallo del nombre canónico, sin eliminar residuos ni cambiar permisos. La batería inicial y la repetida son la misma: **no sumar 158 a los 306 tests únicos aprobados**. No hay NEW_REGRESSION demostrada; es auditoría de snapshot, no atribución a un diff.

Los 9 archivos iniciales son test_prediction_gate, test_temporal_cutoff, test_rest_form_cutoff, test_finite_prices, test_revalidation, test_settlement_math, test_odds_api_retry, test_agent_instruction_sync y test_claude_model_routing. Los 7 adicionales son test_audit_atomic_readers, test_storage, test_calibration_data, test_realized_roi_consistency, test_audit_temporal, test_live_gate_integration y test_hook_targets.

## Comparación histórica posterior

Fuente consultada por búsquedas acotadas: audit/audit-2026-09-16/FINDINGS.md; SHA256 7a2da7bc2e68a9b418f3fc0fdf8c29329229c1b7d9cad27241c744bac0c92d1b. IDs se conservan como identidad de aquella ronda, sin reutilizarlos en ésta.

- Los tres OPENAI de esta ronda no tienen correspondencia identificada en la tabla de siete AUD de esa fuente. Son nuevos en esta ronda, **no necesariamente nuevos en el repositorio**; la referencia incidental de memoria indica antecedentes de gate_status, cuyo ID exacto no se verificó.
- audit-2026-09-16 / AUD-004: persiste el síntoma ambiental de basetemp inaccesible. La ruta/causa de permisos interna exacta no se revalidó; no se intentó corregirla.
- audit-2026-09-16 / AUD-002: los consumidores actuales delegan ROI en realized_roi_parts y su suite focalizada pasa. Evidencia favorable al arreglo de esa ruta; no cierre formal de todos sus criterios.
- AUD-001, AUD-003, AUD-005, AUD-006 y AUD-007 de aquella ronda: no se revalidaron todos sus criterios; **NOT_VERIFIABLE como cierre histórico**. No se importan como defectos confirmados actuales.

## Plan y riesgos residuales

1. **P2 — OPENAI-001:** sustituir la consulta paralela por estado/progreso canónicos y probar las cinco divergencias. No cambiar umbrales ni desbloquear mercados.
2. **P2 — OPENAI-002:** validar el esquema mínimo del registro; probar default-deny con raíces no objeto.
3. **P3 — OPENAI-003:** emitir en el log el veredicto persistido; probar test agotado y pestillo.
4. Recuperar visibilidad de CI y tareas desde un entorno con acceso, sin inferir éxito de los logs. Medir hooks en su harness real.
5. Programar validación temporal de calibradores y revisión restante de reportes/utilidades; comprobar dependencias con una fuente actual cuando esté disponible.

La auditoría no autoriza remediación. No hay P0/P1 confirmado en esta revisión, pero las limitaciones operativas impiden certificar disponibilidad o estado global del sistema.

