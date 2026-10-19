# Consolidacion - audit-2026-10-15

Diagnostico y consolidacion terminados; remediacion NO ejecutada. No PASS.
Base: 65368c815530bf179c5780db78a9fe196996802d (main + cambios locales registrados).
13 defectos confirmados: CRITICAL 0, HIGH 1, MEDIUM 6, LOW 6. P0 0; P1 1 (AUD-003).
Los IDs completos incluyen round_id; no equivalen a IDs iguales de septiembre.

**Revision 2 (2026-10-16, consolidacion independiente Claude).** Conserva AUD-001..012 con sus IDs y
contenido, anade AUD-013 (CLAUDE-003, antes integrado en AUD-002) y precisa evidencia de AUD-002/003.
La version 1 (OpenAI, 2026-10-15T21:23Z) esta preservada byte a byte en
`history/consolidacion-claude-20261016T104941Z/`. Metodo, conflicto de interes y discrepancias:
seccion «Revision 2» al final.

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
| AUD-013 | MEDIUM | HIGH | REPRODUCED | P2 | pip-audit depende del exito de pytest y no corre desde 2026-09-26 |

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

- **Alias de origen:** OPENAI-002 + CLAUDE-002 (relacionado: AUD-013 / CLAUDE-003 desde la revision 2)
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
- **Revision 2:** evidencia adicional de origen REPRODUCED (CLAUDE-002: clon `--no-tags --depth 1` de 65368c8, 2 failed; se conserva el estado STATICALLY_VERIFIED de la v1 porque la consolidacion no repitio el clon). Revalidado 2026-10-16: `ci.yml:34,91` sin `fetch-depth`/tags; `git_tag_message` (`scripts/research/measure_tier_a_gap.py:224-228`) devuelve `""` con un tag inexistente (rc 0 de `git tag -l`), por lo que `assert msg is not None` pasa y falla `None == 0.075` (no es un falso verde). 0 tags `prereg*` en origin, 2 locales; ultimos runs de main d985ef8 y f128483 en failure. Matiz de correccion: publicar los tags NO basta con `checkout@v4` por defecto (depth 1, sin tags); hace falta adquirirlos explicitamente. Un `skip` silencioso esconderia el ancla: si se usa, con mensaje explicito y verificacion de integracion separada. Severidad: se mantiene MEDIUM frente al HIGH de CLAUDE-002 (controles compensatorios comprobados: produccion ejecuta el arbol local, suite local verde salvo AUD-011, alerta de CI rojo abierta). Primero del bloque P2: desbloquea AUD-013.
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
- **Revision 2 (cifras reales revalidadas):** agregado programatico de `data/calibration/served_nhl.csv` (columnas `event_id, market, selection, implied_probability_novig, generated_at`; pares h2h por (event_id, generated_at)): **346 pares, 331 suman < 0,95, mediana 0,8477**, rango 2026-09-23 -> 2026-10-15 (el origen, un dia antes, daba 320/335). Reproduccion sintetica con funciones reales: Home .4608 + Away .383 = .8438 (Draw .1562). Controles comprobados: `data/bets/prediction_gate.json` (2026-10-15T15:05Z) `nhl|h2h` `allowed=false`, `n=107`, `wins=48`, `p=0,877`, `muestra_insuficiente`, `min_n=300`: sin stake real. Se mantiene HIGH/P1: los controles evitan el dano monetario, no la contaminacion; `p_decision` mezcla el fair sesgado con `market_shrink` (probabilities.py:220-221; `market_shrink` efectivo 0,5 en las 80 filas h2h NHL que ya lo persisten, 612 anteriores sin la columna), sesgando la probabilidad servida (metrica rectora de acierto observado vs prometido), el benchmark del test de entrada unico y el precio con el que `settle.py:161` liquida (ROI realizado NHL h2h sobrestimado). No verificado: el test de signo renormalizado (47/105 vs 41/105) del origen.
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

## AUD-013 - pip-audit depende del exito de pytest y no corre desde 2026-09-26

- **Alias de origen:** CLAUDE-003 (coincidencia parcial con la consecuencia descrita en OPENAI-002). Nuevo en la revision 2; en la v1 estaba integrado en AUD-002.
- **Categoria:** CI / dependencias / estado efectivo de controles
- **Severidad:** MEDIUM
- **Confianza:** HIGH
- **Estado de evidencia:** REPRODUCED (estado de los pasos en `gh run view 38256027979 --json jobs`, segun CLAUDE-003) y STATICALLY_VERIFIED (revision 2)
- **Prioridad:** P2 (tras AUD-002)
- **Archivo / lineas relevantes:** .github/workflows/ci.yml:75-83 (paso pip-audit dentro del job `test`, despues de Pytest, sin `if: always()`; `pip install pip-audit` sin version)
- **Activacion:** Cualquier fallo de pytest en una pata Linux del job `test`.
- **Problema:** El control documentado como «BLOCKING since 2026-07-02» (ci.yml:75) se omite cada vez que falla un test ajeno a las dependencias.
- **Evidencia concreta:** pip-audit `skipped` en 3.11, 3.12, 3.13 y 3.14 del run 38256027979; ultimo run verde de main 2026-09-26 (3648b17). El job Windows no tiene el paso.
- **Esperado:** El escaneo de vulnerabilidades se ejecuta y publica resultado con independencia del resultado de pytest.
- **Observado:** Sin evidencia de escaneo en main desde 2026-09-26.
- **Causa raiz:** Acoplamiento de pasos: un control de seguridad independiente depende del exito de otro control.
- **Consecuencia:** Una vulnerabilidad nueva en `requirements.lock` pasaria inadvertida mientras CI siga rojo por cualquier motivo. Corregir AUD-002 lo reactiva solo mientras CI este verde; el acoplamiento persiste.
- **Correccion minima propuesta:** Job propio para pip-audit (o `if: always()` en el paso) y version fijada de pip-audit.
- **Pruebas necesarias:** Run con un test rojo deliberado en una rama: pip-audit sigue ejecutandose y su veredicto es visible.
- **Criterio de aceptacion:** pip-audit con estado `success`/`failure` (nunca `skipped`) en todos los runs de main.
- **Controles compensatorios:** Ninguno local (pip check no es pip-audit). La alerta de CI rojo avisa del fallo de pytest, no de la omision del escaneo.
- **Limitaciones:** Estado actual de vulnerabilidades NOT_VERIFIABLE (requiere red). Version sin fijar: sin fallo demostrado; forma parte de la correccion, no es defecto aparte.
- **Estado de remediacion:** OPEN

## Discrepancias, observaciones y descartes

| Origen | Resolucion | Motivo |
|---|---|---|
| OPENAI-001 | AUD-001 | Confirmado por reproduccion; no extrapolar a settlement live. |
| OPENAI-002 / CLAUDE-002 | AUD-002 MEDIUM/P2 | Misma causa; CI bloqueada sin demostrar impacto HIGH en produccion. No basta eliminar asercion o saltar test. |
| CLAUDE-001 | AUD-003 HIGH/P1 | Confirmacion matematica independiente; cifras de datos reales y ROI del origen no revalidadas. |
| CLAUDE-003 | v1: integrado parcialmente en AUD-002. **v2: AUD-013 MEDIUM/P2** | Causa (acoplamiento de pasos) y correccion distintas de AUD-002; sobrevive a su arreglo. Version no fijada: parte de la correccion, no defecto aparte. |
| CLAUDE-004 | NOT_VERIFIABLE como defecto (v1 y v2) | Falta contrato que exija publicacion remota de tags. v2: el commit H de `prereg-tier-a-t0` YA esta en origin (`git merge-base --is-ancestor` rc 0) y el valor 0.075 del mensaje del tag consta en `tests/research/test_measure_tier_a_gap.py` de origin/main: respaldo externo del ancla y del valor. El H de `prereg-peso-mercado-h` (107e9b7) NO esta en origin: riesgo operativo de perdida del clon, ver O-R2-1. |
| CLAUDE-005 | DISMISSED como defecto (v1 y v2) | Commits locales ahead no prueban por si solos violacion de contrato de despliegue; suite local verde. Observacion operativa O-R2-1. |
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

## Revision 2 - consolidacion independiente Claude (2026-10-16)

**Procedencia y conflicto de interes.** Coordinador `claude-opus-5-5`, autor tambien de CLAUDE-001..017: conflicto de interes declarado. Mitigacion: adjudicacion independiente de severidades por `claude-fable-5-1` (agente `review-adjudicator`, solo lectura, sin acceso a esta consolidacion v1 ni a `history/`), y revalidacion propia contra codigo. Orden: (1) lectura completa de las fuentes, (2) revalidacion, (3) veredicto del adjudicador, (4) conclusiones fijadas, y solo despues (5) lectura de la v1 y comparacion. Fuentes y hashes sin cambios respecto a `source_reports` del manifest: `openai/REPORT.md` f9a08cbc…, `openai/EVIDENCE.json` abf922f3…, `openai/REPRODUCTION-OPENAI-001.json` 7be79840…, `claude/REPORT.md` 7e550acc…, `claude/EVIDENCE.json` 1ade1970…. Misma base (65368c8) y alcance integral en ambos; `src/`, `scripts/`, `configs/` y `.github/` sin cambios respecto a HEAD el 2026-10-16 (solo la remediacion KI-073 sin commit en `tests/` y `.claude/hooks`, excluida).

**Revalidaciones de la revision 2** (scratchpad `consol_repro.py`, `python -I -B`, rc 0; sin escrituras en el repo):

| Hallazgo | Comando / evidencia | Resultado |
|---|---|---|
| AUD-003 | `_consensus_lines` + `_novig_probs` sinteticos; agregado de `served_nhl.csv`; `prediction_gate.json` | .8438; 346 pares, 331 < 0,95, mediana 0,8477; gate cerrado n=107 |
| AUD-001 | `_match_index`/`_match_result` con BOS-TB 10 y 11 de junio, cuotas solo del 11 | `{'2026-06-10': 'odds-jun11', '2026-06-11': None}` |
| AUD-002 | `ci.yml`, `git_tag_message`, `git tag -l`, `git ls-remote --tags origin`, `gh run list --branch main --limit 3` | Ver ficha; d985ef8 y f128483 failure |
| AUD-013 | `ci.yml:75-83` | Sin `if: always()`; version sin fijar |
| AUD-004 | `scripts/capture_closing_odds.py:55-56,89-90,106-108` | `return 0` incondicional |
| AUD-005 | `espn_tennis.py:149-151`, `runner.py:945` | `return []` sin `failed_windows`; `results_trusted = bool(usable)` |
| AUD-006 | `.claude/settings.json` | PostToolUse `Edit\|Write\|Bash`; PreToolUse `Bash\|PowerShell` |
| CLAUDE-004 | `git merge-base --is-ancestor` de cada tag frente a origin/main; `git show origin/main:tests/...` | tier-a H en origin (rc 0); peso-mercado H no (rc 1); 0.075 en origin |

No se repitieron las reproducciones de AUD-007..012 (se conservan las de la v1 y las fuentes).

**Discrepancias con el adjudicador Fable y su resolucion.** El adjudicador coincidio en AUD-001 (MEDIUM/P2, separado de AUD-009), AUD-002 (MEDIUM, primero de P2), AUD-003 (HIGH/P1), AUD-004..012 y CLAUDE-014/015. Discrepo en:
- CLAUDE-004+005: el adjudicador los fusionaba como MEDIUM/P2 por la perdida del valor `max_plausible_edge` si se pierde el clon. **No se adopta**: la comprobacion posterior muestra que el commit H de tier A y el valor 0.075 ya estan en origin; queda solo el riesgo operativo de `prereg-peso-mercado-h`, sin contrato que exija publicacion (O-R2-1).
- CLAUDE-010: el adjudicador proponia LOW STATICALLY_VERIFIED. **No se adopta**: el codigo esta confirmado pero la consecuencia (alargamiento del run) no esta demostrada ni hay contrato de latencia global; se mantiene INFERRED como en la v1.

**Discrepancias con la v1.** Solo CLAUDE-003 (nuevo AUD-013, motivo en la tabla de discrepancias). Se precisan sin cambiar ID, severidad ni prioridad: AUD-002 (evidencia de origen, el «assert que no discrimina» no produce falso verde, publicar tags no basta) y AUD-003 (cifras reales revalidadas, estado del gate, `market_shrink` efectivo). Resto sin cambios. Matiz del adjudicador a AUD-004: `clv_gate` esta desactivado (`configs/default.yaml`, `enabled: false`), asi que el dano actual recae sobre la revalidacion y el guard de abridores, no sobre el gate de CLV.

**Observaciones de la revision 2 (no defectos).**
- O-R2-1: `main` lleva 10 commits sin push, entre ellos el H de `prereg-peso-mercado-h` (107e9b7) y 904af27 (codigo de produccion). Riesgo de perdida del clon y de falta de validacion externa; accion del operador tras AUD-002. Sin contrato incumplido demostrado.
- O-R2-2: AUD-001 y AUD-009 comparten clase (tolerancia ±1 dia por pareja sin identidad); remediar con criterio comun pero por separado. Los consumidores de investigacion de AUD-001 (`measure_adjustment_battery.py`, `measure_rest_basketball.py`) sostienen decisiones registradas (descanso NBA, bateria de ajustes); si el defecto llego a activarse en esas mediciones es NOT_VERIFIABLE y conviene revisarlo tras la correccion.

**Metricas de la revision 2.** Candidatos fuente: 19 (17 Claude + 2 OpenAI). Confirmados: 13 IDs consolidados (16 IDs fuente; OPENAI-002 y CLAUDE-002 fusionados). Origen: ambos 1 (AUD-002); exclusivo OpenAI 1 (AUD-001); exclusivo Claude 11. No confirmados: CLAUDE-010 INFERRED; CLAUDE-004 y CLAUDE-015 NOT_VERIFIABLE; CLAUDE-005 y CLAUDE-014 DISMISSED como defectos; no hay falsos positivos puros. La cantidad de hallazgos por auditor no mide su calidad. Cobertura: la union de las matrices de ambos informes; siguen sin revisar a fondo `clv_gate`, `backtesting/engine.py`/`tuning.py`, la mayor parte de `evaluation/*`, `sports/adapters.py` y `goalie_backfill.py`.

**Limitaciones de la revision 2.** Sin suite completa nueva (la de la fuente Claude, 3201 passed / 3 ENVIRONMENTAL_FAILURE, es de 2026-10-15 sobre la misma base). CI de HEAD, pip-audit, impacto economico y test de signo renormalizado: NOT_VERIFIABLE. Ningun fichero fuera de `audit/latest/` (FINDINGS, BACKLOG, MANIFEST e `history/consolidacion-claude-20261016T104941Z/`) fue escrito. La consolidacion no autoriza correcciones.
