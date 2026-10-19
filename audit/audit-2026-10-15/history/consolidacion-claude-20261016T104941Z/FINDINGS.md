# Consolidacion - audit-2026-10-15

Diagnostico y consolidacion terminados; remediacion NO ejecutada. No PASS.
Base: 65368c815530bf179c5780db78a9fe196996802d (main + cambios locales registrados).
12 defectos confirmados: CRITICAL 0, HIGH 1, MEDIUM 5, LOW 6. P0 0; P1 1 (AUD-003).
Los IDs completos incluyen round_id; no equivalen a IDs iguales de septiembre.

## Alcance, independencia y procedencia

Auditoria integral por areas con profundidad parcial: ver matriz en [informe OpenAI](openai/REPORT.md).
OpenAI fijo sus dos conclusiones antes de leer conclusiones Claude. Se declara exposicion inicial a metadatos/conclusiones historicas de septiembre.
Claude dejo su diagnostico terminado en pending, misma base y alcance; el coordinador lo adopta a esta ronda y conserva sus bytes y metadatos originales (round_id null, proposed audit-2026-10-15). No se atribuye a Claude una nueva ejecucion.
Los 17 candidatos Claude se revisaron contra codigo/controles; no se aceptan automaticamente sus severidades o afirmaciones productivas.
Fuentes: [OpenAI](openai/REPORT.md), [Claude](claude/REPORT.md), evidencias JSON adyacentes y [reproducciones adicionales](openai/CONSOLIDATION_REPRODUCTIONS.json).
La ronda anterior completa se preservo en audit/audit-2026-09-23 con 41 rutas y hashes iguales.
CHANGES.md, VALIDATION.md, STATUS.md y VERIFICATION.md que aun existen en latest pertenecen a septiembre: NO describen remediacion ni verificacion de esta ronda. Ver MANIFEST.json.

## Resumen de confirmados

| ID | Severidad | Confianza | Evidencia | Prioridad | Titulo |
|---|---|---|---|---|---|
| AUD-001 | MEDIUM | HIGH | REPRODUCED | P2 | El backtest asigna cuotas del dia siguiente al resultado anterior |
| AUD-002 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | CI exige un tag que checkout no obtiene |
| AUD-003 | HIGH | HIGH | REPRODUCED | P1 | Un mercado h2h de dos vias incorpora Draw y cuotas incompatibles |
| AUD-004 | MEDIUM | HIGH | REPRODUCED | P2 | Capture close comunica exito tras fallar una etapa habilitada |
| AUD-005 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | Liquidacion tenis confia en resultados parciales de un proveedor degradado |
| AUD-006 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | Los hooks posteriores omiten modificaciones hechas por PowerShell |
| AUD-007 | LOW | HIGH | REPRODUCED | P3 | El log de pitchers duplica entradas identicas con ausentes |
| AUD-008 | LOW | HIGH | REPRODUCED | P3 | La captura supera el limite diario de creditos |
| AUD-009 | LOW | HIGH | REPRODUCED | P3 | Merge de resultados descarta partidos consecutivos reales |
| AUD-010 | LOW | HIGH | STATICALLY_VERIFIED | P3 | Cross-review pierde su pendiente si falta el ejecutable |
| AUD-011 | LOW | HIGH | REPRODUCED | P3 | Tres pruebas de no-repositorio heredan Git del workspace |
| AUD-012 | LOW | HIGH | STATICALLY_VERIFIED | P3 | La cache da por persistido un snapshot que pudo fallar |

## AUD-001 - El backtest asigna cuotas del dia siguiente al resultado anterior

- **Alias de origen:** OPENAI-001
- **Categoria:** Integridad cuantitativa
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P2
- **Archivo / lineas relevantes:** src/sqp/backtesting/roi_engine.py:179-198; caller :334
- **Activacion:** Mismos equipos en dias consecutivos y cuotas solo del segundo partido.
- **Problema:** El matching tolerante consume el evento equivocado.
- **Evidencia concreta:** openai/REPRODUCTION-OPENAI-001.json; matcher y liquidacion reales con adaptador determinista.
- **Esperado:** Emparejar la identidad correcta: +20 para junio 11, o abstenerse.
- **Observado:** Junio 10 consume odds-jun11, registra -20; junio 11 queda sin cuotas.
- **Causa raiz:** Busqueda voraz +/-1 dia antes de reservar coincidencias exactas.
- **Consecuencia:** PnL y muestra de backtesting incorrectos.
- **Correccion minima propuesta:** Resolver identidad/calendario y reservar matches exactos antes de fallback ambiguo.
- **Pruebas necesarias:** Series consecutivas, cuota faltante, orden de filas, UTC y abstencion.
- **Criterio de aceptacion:** Emparejar la identidad correcta: +20 para junio 11, o abstenerse.
- **Controles compensatorios:** Settlement productivo usa otra ruta de identidad.
- **Limitaciones:** Reproduccion sintetica; impacto historico real no cuantificado; no implica perdida monetaria live.
- **Estado de remediacion:** OPEN

## AUD-002 - CI exige un tag que checkout no obtiene

- **Alias de origen:** OPENAI-002 + CLAUDE-002; consecuencia CLAUDE-003
- **Categoria:** CI y pruebas
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** STATICALLY_VERIFIED
- **Prioridad:** P2
- **Archivo / lineas relevantes:** .github/workflows/ci.yml (checkout); tests/research/test_measure_tier_a_gap.py:521-524,1073
- **Activacion:** Checkout limpio de CI sin prereg-tier-a-t0.
- **Problema:** Dos tests de integracion Git requieren un tag local ausente del fetch.
- **Evidencia concreta:** Run 38256027979 sobre d985ef8: 2 failed, 3004 passed, 83 skipped; checkout --no-tags --depth=1; los dos tests pasan localmente con tag.
- **Esperado:** Checkout reproducible con objetos requeridos y pruebas discriminantes aprobadas; escaneo de seguridad ejecutado.
- **Observado:** Fallan tests en los cinco jobs; paso posterior pip-audit queda skipped.
- **Causa raiz:** Dependencia de estado Git local no declarada/adquirida por CI.
- **Consecuencia:** CI bloqueada y control de vulnerabilidades sin evidencia actual.
- **Correccion minima propuesta:** Proveer referencias verificables necesarias en CI o aislar fixture unitario; conservar comprobacion de ancla real separada.
- **Pruebas necesarias:** Clone limpio sin tags; adquisicion explicita; tag incorrecto debe fallar; verificar ejecucion pip-audit.
- **Criterio de aceptacion:** Checkout reproducible con objetos requeridos y pruebas discriminantes aprobadas; escaneo de seguridad ejecutado.
- **Controles compensatorios:** Tag existe localmente, dos pruebas locales pasan.
- **Limitaciones:** Run remoto no es HEAD local. No afirmar vulnerabilidades ni publicar tags como parte de esta auditoria.
- **Estado de remediacion:** OPEN

## AUD-003 - Un mercado h2h de dos vias incorpora Draw y cuotas incompatibles

- **Alias de origen:** CLAUDE-001
- **Categoria:** Probabilidades y equivalencia de mercado
- **Severidad:** HIGH
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P1
- **Archivo / lineas relevantes:** src/sqp/pipeline/probabilities.py:35-59,97-135
- **Activacion:** Evento NHL con cotizaciones h2h Home/Away y otra casa que incluye Draw.
- **Problema:** Consenso pierde identidad de casa/contrato y no-vig permite mas de dos desenlaces con three_way=False.
- **Evidencia concreta:** openai/CONSOLIDATION_REPRODUCTIONS.json: Home=.4495528625890095, Away=.396861815660444, Draw=.15358532175053535.
- **Esperado:** Dos desenlaces complementarios suman 1 con cuotas del mismo contrato, o mercado rechazado.
- **Observado:** Home+Away=.8464146782494535 en modo dos vias.
- **Causa raiz:** Agrupacion solo market/outcome/point; validacion len(keys)<required en vez de conjunto exacto.
- **Consecuencia:** Benchmark de probabilidad y edge materialmente sesgados; contaminacion posible de stream servido/calibracion.
- **Correccion minima propuesta:** Separar contratos por casa antes del consenso, exigir lados exactos y aplicar elegibilidad coherente en conteos, ejecucion y revalidacion.
- **Pruebas necesarias:** Mixto dos/tres vias, solo dos, futbol tres, casa incompleta, conteos y precios ejecutables.
- **Criterio de aceptacion:** Dos desenlaces complementarios suman 1 con cuotas del mismo contrato, o mercado rechazado.
- **Controles compensatorios:** Gates limitan stakes; no reparan probabilidades servidas.
- **Limitaciones:** No se verificaron cifras reales 320/335 del informe origen ni ROI monetario. Semantica reglamentaria externa no necesaria para demostrar el defecto matematico.
- **Estado de remediacion:** OPEN

## AUD-004 - Capture close comunica exito tras fallar una etapa habilitada

- **Alias de origen:** CLAUDE-006
- **Categoria:** Observabilidad y propagacion de errores
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P2
- **Archivo / lineas relevantes:** scripts/capture_closing_odds.py:55-56,89-90,106-108; src/sqp/pipeline/closing_capture.py:164-165; CAPTURE_CLOSE.bat
- **Activacion:** Excepcion en revalidacion habilitada o captura por liga.
- **Problema:** Warning capturado seguido de return 0; el BAT interpreta exito y limpia estado.
- **Evidencia concreta:** Revalidacion simulada lanza RuntimeError(controlled revalidation failure), main() devuelve 0.
- **Esperado:** Estado degradado observable y rc no exitoso cuando falla una etapa requerida.
- **Observado:** rc=0 a pesar de excepcion; resumen por liga no distingue fallos.
- **Causa raiz:** Errores convertidos en warnings sin estado agregado de fallo.
- **Consecuencia:** Control operativo verde aunque evidencia de cierre/revalidacion falte.
- **Correccion minima propuesta:** Acumular fallos por etapa/liga y propagar codigo o contrato de degradacion al BAT.
- **Pruebas necesarias:** Fallo de captura, revalidacion, starters y exito; sentinel no se limpia en fallo.
- **Criterio de aceptacion:** Estado degradado observable y rc no exitoso cuando falla una etapa requerida.
- **Controles compensatorios:** Logs contienen warning; siguientes ejecuciones pueden recuperar.
- **Limitaciones:** Reproduccion sin red; no se ejecuto BAT ni se alteraron sentinelas productivos.
- **Estado de remediacion:** OPEN

## AUD-005 - Liquidacion tenis confia en resultados parciales de un proveedor degradado

- **Alias de origen:** CLAUDE-007
- **Categoria:** Integridad de liquidacion
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** STATICALLY_VERIFIED
- **Prioridad:** P2
- **Archivo / lineas relevantes:** src/sqp/providers/espn_tennis.py:119-151; src/sqp/settlement/runner.py:944-982
- **Activacion:** Una ventana falla tras reintentos, otra devuelve ganador; pick vencido sin resultado en historico.
- **Problema:** No se comunica la ventana fallida y bool(usable) habilita stale_void.
- **Evidencia concreta:** _fetch devuelve [] tras fallo; fetch_results conserva otras ventanas; results_trusted=bool(usable) permite _void_stale_served y _with_stale_voids.
- **Esperado:** Fallo de cobertura conocido impide anular los picks afectados y se comunica degradacion.
- **Observado:** Una respuesta parcial se considera fiable para expiracion.
- **Causa raiz:** Contrato de proveedor omite estado de completitud; consumidor confunde algun resultado con cobertura sana.
- **Consecuencia:** Anulacion persistida de un pick resuelto pero temporalmente no observable.
- **Correccion minima propuesta:** Propagar failed_windows y usarlo para confianza/expiracion y estado del backfill.
- **Pruebas necesarias:** Una ventana 503 y otra valida; pick vencido, historico presente/ausente; ninguna anulacion atribuible a ventana fallida.
- **Criterio de aceptacion:** Fallo de cobertura conocido impide anular los picks afectados y se comunica degradacion.
- **Controles compensatorios:** Payload totalmente vacio bloquea voids; fallback historico recupera resultados ya descargados.
- **Limitaciones:** Ruta confirmada estaticamente; no end-to-end ni incidencia productiva demostrada; no es defecto solo por nombres derivados aceptados.
- **Estado de remediacion:** OPEN

## AUD-006 - Los hooks posteriores omiten modificaciones hechas por PowerShell

- **Alias de origen:** CLAUDE-008
- **Categoria:** Gobierno de agentes
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** STATICALLY_VERIFIED
- **Prioridad:** P2
- **Archivo / lineas relevantes:** .claude/settings.json:1 (PostToolUse matcher Edit|Write|Bash)
- **Activacion:** Herramienta llamada PowerShell modifica archivos vigilados sin Edit/Write/Bash posterior.
- **Problema:** No dispara secretos, tests-pending ni crossreview-pending.
- **Evidencia concreta:** Matcher excluye PowerShell aunque PreToolUse y permisos lo incluyen.
- **Esperado:** Las herramientas de escritura admitidas disparan los controles previstos.
- **Observado:** PowerShell queda fuera del matcher.
- **Causa raiz:** Lista de herramientas incompleta en PostToolUse.
- **Consecuencia:** Cambios pueden cerrar turno sin controles automaticos previstos.
- **Correccion minima propuesta:** Agregar PowerShell a los tres hooks y comprobar extraccion de rutas.
- **Pruebas necesarias:** Contrato de matchers y evento PowerShell con Set-Content sobre ruta vigilada.
- **Criterio de aceptacion:** Las herramientas de escritura admitidas disparan los controles previstos.
- **Controles compensatorios:** Un Edit/Write/Bash posterior puede recoger cambios por Git; fable_gate protege algunos commits.
- **Limitaciones:** No reproducido mediante harness real; se confirma la configuracion condicional, no ejecucion concreta.
- **Estado de remediacion:** OPEN

## AUD-007 - El log de pitchers duplica entradas identicas con ausentes

- **Alias de origen:** CLAUDE-009 (solo duplicacion)
- **Categoria:** Integridad del registro
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** src/sqp/storage/starters.py:78-79
- **Activacion:** Misma fila tres veces, un pitcher presente y otro None.
- **Problema:** Lectura CSV convierte ausente a NaN y comparacion por str detecta cambio falso.
- **Evidencia concreta:** Reproduccion aislada append_counts_identical_input=[1,1,1].
- **Esperado:** Una primera entrada; llamadas identicas siguientes agregan cero.
- **Observado:** Cada llamada agrega una fila.
- **Causa raiz:** Comparacion None frente a NaN sin normalizacion.
- **Consecuencia:** Registro de confirmacion/timing inflado.
- **Correccion minima propuesta:** Normalizar valores ausentes antes de comparar.
- **Pruebas necesarias:** None/NaN/vacio y cambio real de pitcher.
- **Criterio de aceptacion:** Una primera entrada; llamadas identicas siguientes agregan cero.
- **Controles compensatorios:** No se establecio consumo operativo por pipeline de este log.
- **Limitaciones:** Concurrencia sin lock separada como INFERRED; no se confunde con StartersStore.save previamente corregido.
- **Estado de remediacion:** OPEN

## AUD-008 - La captura supera el limite diario de creditos

- **Alias de origen:** CLAUDE-011
- **Categoria:** Cuota de proveedor
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** src/sqp/pipeline/closing_capture.py:119-151
- **Activacion:** Gasto299, limite300, siguiente peticion cuesta3.
- **Problema:** Solo valida gasto pasado antes de iniciar una peticion.
- **Evidencia concreta:** Mock sin API: actual_total302, cap300.
- **Esperado:** No iniciar una peticion cuyo coste previsto exceda el saldo del limite.
- **Observado:** Gasto acumulado302.
- **Causa raiz:** Falta reserva/estimacion previa del coste.
- **Consecuencia:** Exceso de cuota sobre el limite configurado.
- **Correccion minima propuesta:** Comprobar coste conservador antes de pedir y reconciliar coste real.
- **Pruebas necesarias:** Saldo menor/igual/mayor al coste, varias ligas, reanudacion diaria.
- **Criterio de aceptacion:** No iniciar una peticion cuyo coste previsto exceda el saldo del limite.
- **Controles compensatorios:** Tope previo y min_remaining limitan consumo ulterior.
- **Limitaciones:** No gasto real. No se adopta cota universal de seis creditos sin contrato demostrado.
- **Estado de remediacion:** OPEN

## AUD-009 - Merge de resultados descarta partidos consecutivos reales

- **Alias de origen:** CLAUDE-012
- **Categoria:** Integridad de datos de entrenamiento
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** src/sqp/pipeline/daily.py:104-131
- **Activacion:** Historico con A/B dia10 y feed reciente A/B dia11, historico retrasado.
- **Problema:** Dedup por pareja +/-1 dia considera el partido nuevo ya existente.
- **Evidencia concreta:** Reproduccion retiene solo game_id old y elimina new.
- **Esperado:** Conservar ambos partidos distintos.
- **Observado:** Un resultado reciente real desaparece del merge.
- **Causa raiz:** Equivalencia temporal demasiado amplia sin identidad exacta.
- **Consecuencia:** Ratings pierden un resultado disponible en ese run.
- **Correccion minima propuesta:** Priorizar ID/calendario exacto; fallback no debe absorber otro partido de una serie.
- **Pruebas necesarias:** Serie dias consecutivos, dobles jornadas y verdadero desplazamiento UTC.
- **Criterio de aceptacion:** Conservar ambos partidos distintos.
- **Controles compensatorios:** Backfill previo de DIARIO normalmente actualiza el historico.
- **Limitaciones:** Activacion condicionada a historico retrasado; posible antecedente legacy sin identidad revalidada. Diferente fix/caller de AUD-001.
- **Estado de remediacion:** OPEN

## AUD-010 - Cross-review pierde su pendiente si falta el ejecutable

- **Alias de origen:** CLAUDE-016
- **Categoria:** Gobierno de agentes
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** STATICALLY_VERIFIED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** .claude/hooks/crossreview-on-stop.sh:17-18
- **Activacion:** Marker pendiente y codex no disponible en PATH.
- **Problema:** Borra marker antes de command -v; sale cero sin aviso.
- **Evidencia concreta:** rm -f marker seguido de command -v codex || exit 0; ramas posteriores de error no se alcanzan.
- **Esperado:** Avisar revision no ejecutada y conservar pendiente para reintento.
- **Observado:** Pendiente eliminado silenciosamente.
- **Causa raiz:** Comprobacion de dependencia posterior a limpieza irreversible del estado pendiente.
- **Consecuencia:** Cambio sensible queda sin revision y sin reintento automatico.
- **Correccion minima propuesta:** Verificar ejecutable antes de borrar; advertir y conservar marker.
- **Pruebas necesarias:** PATH sin codex con marker, fallos y salida vacia existentes.
- **Criterio de aceptacion:** Avisar revision no ejecutada y conservar pendiente para reintento.
- **Controles compensatorios:** Rama posterior de fallos de codex ya restaura marker.
- **Limitaciones:** No se invoco codex ni se modificaron markers reales.
- **Estado de remediacion:** OPEN

## AUD-011 - Tres pruebas de no-repositorio heredan Git del workspace

- **Alias de origen:** CLAUDE-017
- **Categoria:** Aislamiento de tests
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** tests/test_fable_gate.py:770-780; tests/test_measure_tilt_nhl.py:305-316
- **Activacion:** Basetemp dentro de .codex-tmp conforme a AGENTS.md.
- **Problema:** No ejecutar git init no implica que tmp_path este fuera de todo repositorio.
- **Evidencia concreta:** 3 failed20.60s; con GIT_CEILING_DIRECTORIES=C:/dev/3/sports-quant-platform/.codex-tmp:3 passed6.89s.
- **Esperado:** Fixtures reproducen un directorio sin repositorio incluso dentro del scratch autorizado.
- **Observado:** git_head devuelve HEAD padre; git_status devuelve cadena vacia; hook retorna0 en vez de2.
- **Causa raiz:** Git asciende buscando .git del proyecto.
- **Consecuencia:** Falsos rojos ambientales degradan la auditoria y pueden confundirse con regresiones.
- **Correccion minima propuesta:** Aislar busqueda Git en fixture/subproceso mediante GIT_CEILING_DIRECTORIES.
- **Pruebas necesarias:** Tres casos bajo scratch interno y fixture con repo propio; mantener restricciones de escritura.
- **Criterio de aceptacion:** Fixtures reproducen un directorio sin repositorio incluso dentro del scratch autorizado.
- **Controles compensatorios:** Clasificacion ENVIRONMENTAL_FAILURE evita atribucion incorrecta al producto.
- **Limitaciones:** No mover basetemp a TEMP: viola restriccion conocida KI-037. Ningun test fue modificado.
- **Estado de remediacion:** OPEN

## AUD-012 - La cache da por persistido un snapshot que pudo fallar

- **Alias de origen:** CLAUDE-013 (solo contrato de persistencia)
- **Categoria:** Persistencia de evidencia
- **Severidad:** LOW
- **Confianza:** HIGH
- **Estado de evidencia:** STATICALLY_VERIFIED
- **Prioridad:** P3
- **Archivo / lineas relevantes:** src/sqp/providers/odds_api.py:158-162,212-215; src/sqp/pipeline/daily.py:773-779
- **Activacion:** Cache se escribe correctamente, append_snapshot falla y reintento llega dentro del TTL con las mismas cuotas.
- **Problema:** Cache hit se trata como prueba de que snapshot ya existe.
- **Evidencia concreta:** _get escribe cache antes de retornar; daily persiste despues, solo si not last_response_cached.
- **Esperado:** Reintento recupera snapshot faltante sin duplicar ni cambiar timestamp original.
- **Observado:** Rama cache omite append_snapshot y anuncia snapshot already persisted sin verificarlo.
- **Causa raiz:** Acoplamiento implicito entre cache de respuesta y confirmacion de almacenamiento distinto.
- **Consecuencia:** Hueco condicional en evidencia OOS/cierre de cuotas.
- **Correccion minima propuesta:** Confirmar persistencia por identidad o persistir idempotentemente preservando timestamp de adquisicion.
- **Pruebas necesarias:** Fallo controlado del primer append, reintento cacheado, cero snapshot duplicado y fecha original.
- **Criterio de aceptacion:** Reintento recupera snapshot faltante sin duplicar ni cambiar timestamp original.
- **Controles compensatorios:** Un fetch posterior fuera del TTL puede aportar otro snapshot, no el omitido.
- **Limitaciones:** No se forzo fallo de disco productivo. Riesgo adicional de write_text no atomico queda INFERRED y no es segundo defecto.
- **Estado de remediacion:** OPEN

## Discrepancias, observaciones y descartes

| Origen | Resolucion | Motivo |
|---|---|---|
| OPENAI-001 | AUD-001 | Confirmado por reproduccion; no extrapolar a settlement live. |
| OPENAI-002 / CLAUDE-002 | AUD-002 MEDIUM/P2 | Misma causa; CI bloqueada sin demostrar impacto HIGH en produccion. No basta eliminar asercion o saltar test. |
| CLAUDE-001 | AUD-003 HIGH/P1 | Confirmacion matematica independiente; cifras de datos reales y ROI del origen no revalidadas. |
| CLAUDE-003 | Integrado parcialmente en AUD-002 | pip-audit skipped es consecuencia. Version no fijada sin fallo demostrado: observacion DISMISSED como defecto independiente. |
| CLAUDE-004 | NOT_VERIFIABLE como defecto | Falta contrato que exija publicacion remota de tags; conservar anclas y evaluar respaldo operativo. No se publica nada. |
| CLAUDE-005 | DISMISSED como defecto | Commits locales ahead no prueban por si solos violacion de contrato de despliegue. CI de HEAD sigue NOT_VERIFIABLE. |
| CLAUDE-006 | AUD-004 | Fallo de revalidacion reproducido, sin invocar BAT. |
| CLAUDE-007 | AUD-005 | Verificado estaticamente con condicion de historico ausente; no se adopta reproduccion ajena como propia. |
| CLAUDE-008 | AUD-006 | Configuracion confirmada; harness real no ejercitado. |
| CLAUDE-009 | AUD-007 | Duplicacion reproducida; carrera concurrente adicional INFERRED, no confirmada. |
| CLAUDE-010 | INFERRED | Presupuesto por cliente confirmado, pero no contrato duro de latencia global ni impacto operativo medido; comentar por cliente/por run merece aclaracion. |
| CLAUDE-011 | AUD-008 | Exceso299+3>300 reproducido; no asumir cota universal de6. |
| CLAUDE-012 | AUD-009 | Merge distinto del matcher backtest; prueba independiente. |
| CLAUDE-013 | AUD-012 parcial | Contrato cache/persistencia confirmado; corrupcion por escritura no atomica queda INFERRED sin ejecucion. |
| CLAUDE-014 | DISMISSED como defecto activo | No se acredita productor NaN que atraviese controles existentes; hardening opcional P4. |
| CLAUDE-015 | NOT_VERIFIABLE | Vigencia de IDs no contrastada contra fuente oficial; sin uso operativo demostrado, no se confirma. |
| CLAUDE-016 | AUD-010 | Rama missing executable distinta de fallo no-cero ya corregido. |
| CLAUDE-017 | AUD-011 | Reproducido y aislado dentro del scratch permitido; rechazada recomendacion de usar TEMP fuera del sandbox. |

Otros candidatos de origen (carreras de locks/logs, probabilidad complementaria latente, semantica de prorroga de futbol) permanecen INFERRED/NOT_VERIFIABLE; no se elevan a confirmados. No hubo consulta externa para validar contratos deportivos o modelos que aqui quedan no confirmados.

## Validacion y clasificacion

OpenAI: 415 tests distintos aprobados en diagnostico (77 hooks/routing,212 core,54 integracion,2 CI-local,70 historico), mas3 pruebas de aislamiento aprobadas bajo control Git:418 distintos con resultado final satisfactorio. Los3 inicialmente fallan bajo el comando prescrito: ENVIRONMENTAL_FAILURE, causa de AUD-011; no NEW_REGRESSION del producto. El control de entorno NO es una correccion de tests.
Primer intento previo:55 passed y22 setup errors por padre temporal ausente; ENVIRONMENTAL_FAILURE, luego77 passed con padre creado. Comandos/resultados en openai/EVIDENCE.json y CONSOLIDATION_REPRODUCTIONS.json.
Ruff sin cache, MyPy113 archivos, sync de instrucciones, routing y pip check satisfactorios. No sustituyen escaneo de vulnerabilidades.
Claude informa suite3 failed,3201 passed,1 skipped; procedencia secundaria, no suite ejecutada por OpenAI. Tres fallos se reprodujeron independientemente como aislamiento ambiental.
CI remota inspeccionada:2 failed,3004 passed,83 skipped en d985ef8; PRE_EXISTING_FAILURE respecto al trabajo local de hooks, no nueva regresion atribuida. CI del HEAD local NOT_VERIFIABLE.
Cinco reproducciones controladas adicionales (probabilidades, pitchers, merge, presupuesto, CLI) pasan sus aserciones de activacion del defecto; no son pruebas de correccion del producto.

## Historico, limites y siguiente fase

Nueve causas del informe OpenAI de septiembre se revalidaron tras fijar diagnostico: controles presentes y70 tests seleccionados, segun matriz del informe fuente. No cierre masivo de IDs legacy no examinados. Las afirmaciones de persistencia del otro informe no reemplazan esa revalidacion. AUD-009 tiene posible antecedente sin identidad demostrada.
No suite completa propia, escaneo de vulnerabilidades actual, CI de HEAD, cuantificacion economica productiva, pentest, garantias de rentabilidad ni cobertura total. Datos/logs productivos no se alteraron; las reproducciones usan temporales y mocks, sin servicios de pago.
Solo se escribieron entregables/historicos de auditoria y temporales permitidos. Cambios locales ajenos conservados y registrados. La siguiente fase es remediacion separada, con criterios del BACKLOG; no se ejecuta implicitamente por este diagnostico.
