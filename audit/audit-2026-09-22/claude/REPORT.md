# Informe de diagnóstico — auditor Claude — ronda `audit-2026-09-22`

- **Auditor:** `claude-opus-5`, sesión principal, sin subagentes.
- **Base:** `9fa276a` (rama `main`), árbol de trabajo limpio al inicio.
- **Fecha UTC:** 2026-09-22.
- **Autorización:** activación de la skill `full-audit`. Autoriza **diagnóstico,
  validación y planificación**. No autoriza modificar el proyecto. No se modificó
  `src/`, `scripts/`, `configs/`, `tests/`, `*.bat`, `data/` ni `logs/`.
- **Segunda opinión:** no hubo. No se solicitó ni se ejecutó un auditor OpenAI
  para esta ronda. `audit/latest/openai/` conserva el informe de la ronda
  `audit-2026-09-18` y **no forma parte de esta ronda**.

---

## 1. Resumen

El repositorio llega a esta ronda en buen estado estructural: `ruff` y `mypy`
limpios, CI verde sobre el commit base, `pip-audit` sin vulnerabilidades
conocidas, las cinco tareas programadas sin fallo, y el gate de predicción,
el monitor de degradación y los candados de presupuesto funcionando y
produciendo veredicto fechado. Las siete IDs de la ronda anterior se revalidaron
una por una: **seis están corregidas con evidencia**, y una (`AUD-004`) persiste
por una condición del host que exige elevación.

Se confirman **ocho defectos**: 4 MEDIUM y 4 LOW. Ninguno produce hoy un número
incorrecto en la salida de apuestas. Los tres de mayor consecuencia son, los
tres, **controles que se creen activos y no lo están**:

- **CLAUDE-007 (P1).** El hook `Stop` que ejecuta la suite tiene un presupuesto
  de 600 s y su comando tarda **796 s** medidos. El harness lo mata, el veredicto
  nunca llega, y el centinela sobrevive al corte: cada turno que toque código
  gasta 10 minutos para no decir nada.
- **CLAUDE-001 (P2).** El gate de predicción reparte su alpha de familia entre
  K=41 cortes y hoy evalúa **49**; la alarma que debía avisarlo sólo salta por
  encima de 50, así que **nunca ha saltado** y está a un corte de hacerlo.
- **CLAUDE-008 (P2).** La revisión cruzada de Codex **no se ejecuta**: el
  runtime abre hilo, devuelve salida vacía y sale con código 1. Se descubrió al
  intentar cerrar esta misma sesión, y obligó a **retirar un descarte** de la
  primera pasada de este informe (§6): había dado por buena la CLI con
  `--version`, que es inventario, no estado.

Los dos primeros son la misma enfermedad que este repositorio lleva meses
documentando en sus propios comentarios: un umbral fijado una vez contra una
magnitud que sigue creciendo. El tercero es la otra enfermedad crónica que el
repositorio también tiene catalogada: un control que dice algo distinto de lo
que mide.

Lo que esta auditoría **no** demuestra: que el código esté libre de defectos, que
la suite verde acredite corrección, ni que exista ventaja predictiva. El ROI
realizado acumulado del ledger es **negativo** (§7).

---

## 2. Alcance, método y exclusiones

Inventario primero, después profundidad por criticidad (P0 → P3), y para cada
**control** dos preguntas separadas: si existe y está bien configurado, y si
**está pasando ahora mismo**.

**Exclusiones declaradas.**

| Excluido | Motivo |
|---|---|
| Contenido completo de `data/` y `logs/` | Regla de `CLAUDE.md` y `deny` de `.claude/settings.json`. Sólo escaneos programáticos que devuelven agregados. |
| `.env` | Lectura denegada por la política de permisos (el control funcionó). La configuración efectiva se obtuvo instanciando `Settings.load()` e imprimiendo sólo valores no secretos. |
| Llamadas a proveedores externos | Prohibidas durante el diagnóstico. **Cero créditos consumidos.** |
| Construcción de la imagen Docker | Ninguna puerta del proyecto la construye; se revisó estáticamente. |

**Preservación de la ronda anterior.** `audit/latest` → `audit/audit-2026-09-18`,
11 ficheros, sha256 idénticos uno a uno. Verificado antes de escribir nada en
`latest`.

**Contaminación de contexto.** Ninguna durante la fase principal. Del manifest
previo sólo se leyeron metadatos de ronda (id, fecha, base) para la preservación.
Los informes de la ronda 18 se leyeron **después** de fijar las conclusiones
propias, para la comparación histórica (§8).

---

## 3. Inventario

**Dominio.** Plataforma cuantitativa deportiva: estima probabilidades calibradas
para moneyline / hándicap / totales en deportes de equipo y tenis, las compara
con el precio sin vig del consenso, dimensiona stake por Kelly fraccional y
liquida contra marcadores reales.

| Elemento | Medida |
|---|---|
| Paquete Python | `src/sqp`, 106 módulos, 20.185 líneas, Python 3.14.4 en producción (CI 3.11–3.14) |
| Scripts | 55 en `scripts/` + 9 en `scripts/ai/` + 9 en `scripts/research/` + 3 PowerShell/CMD |
| Entradas BAT | 10 en la raíz; `DIARIO_COMPLETO.bat` (18 KB) es el orquestador diario |
| Configuración | `configs/default.yaml`, `configs/venues.yaml`, `configs/leagues/{ratings,soccer,team_aliases}.yaml`, `.env` (no versionado), `.env.example` |
| Dependencias | 8 runtime + 4 dev en `pyproject.toml`; `requirements.lock` como fichero de restricciones |
| Persistencia | CSV/Parquet/joblib bajo `data/`, escritura atómica (`storage/atomic.py`) con bloqueo (`storage/lock.py`) |
| Proveedores externos | The Odds API (cuotas y marcadores), ESPN (resultados y tenis), MLB StatsAPI (abridores), Open-Meteo (clima, deshabilitado) |
| Modelos | scikit-learn `.joblib` por (liga, mercado) + calibradores beta/isotónicos; registro append-only `data/models/registry.json` (68 entradas) |
| Pruebas | 147 ficheros `test_*.py`, 2264 pruebas recolectadas, marcador `slow` |
| CI | `.github/workflows/ci.yml`: matriz 3.11–3.14, `ruff`, `mypy` (3.12), `pytest`, cobertura (3.12), `pip-audit` bloqueante, job Windows, notificador de fallo |
| Programación | 5 tareas `SQP_*_Cdev` en el Programador de tareas de Windows (S4U + WakeToRun) |
| Sistema de agentes | 34 skills, 22 agentes, 8 comandos, 7 hooks, `ORCHESTRATOR.md`, `automation/` (contrato de auditoría, routing de modelo, guardarraíles) |
| Documentación | `README.md`, `AGENTS.md`, `CLAUDE.md`, `IMPLEMENTACION.md`, `REPO_DESCRIPTION.md`, `docs/research/` (15 pre-registros), bóveda `Obsidian/` |

**Estratificación.**

- **P0** — `pipeline/daily.py`, `pipeline/probabilities.py`, `markets/{edge,vig,odds,settlement_math}.py`, `risk/{kelly,prediction_gate,degradation,bankroll}.py`, `settlement/{settle,runner}.py`, `calibration/`, `storage/{atomic,lock}.py`.
- **P1** — `providers/`, `pipeline/{closing_capture,revalidation,intraday_scan,team_totals_capture,cleanup}.py`, `monitoring/health.py`, `backtesting/`, BAT de producción, CI, tareas programadas.
- **P2** — `scripts/` operativos, `audit/`, `evaluation/`, sistema de skills/agentes/hooks.
- **P3** — `scripts/research/`, `examples/`, `Dockerfile`, `graphify-out/`, históricos de `audit/`.

---

## 4. Matriz de cobertura

`FULL AUDIT` = toda área inventariada tiene disposición explícita. No significa
que toda área se haya podido validar dinámicamente.

| Área | Prio | Estado | Componentes | Método | Validación / **estado del control** | Limitaciones |
|---|---|---|---|---|---|---|
| Arquitectura y contratos | P0 | REVISADA | `pipeline/`, `markets/`, `risk/`, `settlement/`, `domain/models.py` | Lectura del flujo cuotas → consenso → no-vig → probabilidad → edge → stake → liquidación | Fronteras limpias; `probabilities.py` es punto único de verdad para el run y el backtest (`build_model_map`) | — |
| Lógica, unidades y casos límite | P0 | REVISADA | `markets/edge.py`, `risk/kelly.py`, `settlement/settle.py`, `pipeline/probabilities.py` | Lectura línea a línea + reproducciones acotadas | `e = p·d − 1` coherente en todo el árbol; Kelly protege no-finitos, `p∉(0,1)`, `d≤1`, banca ≤0; `_grade` no fabrica resultado ante línea no finita, selección no reconocida ni línea asiática de cuarto | — |
| Leakage temporal / target | P0 | REVISADA | `features/temporal.py`, `features/builders.py`, `risk/prediction_gate.py` | Lectura + verificación del corte de información | `daily_splits` nunca parte un día; `holdout_start` exige cronología; el gate exige `game_date > VALIDATION_START` estricto y colapsa a una unidad por (evento, mercado) | — |
| Calibración | P0 | REVISADA_PARCIALMENTE | `calibration/` (1086+245+202+71 líneas), `data/models/calibration_methods.json` | Lectura del registro vivo + contraste con `promotion_log.csv` y el disco | Registro vivo = `{mlb_spreads: beta, mlb_totals: isotonic, wnba_spreads: beta}`; la clave sandbox `mlb_h2h_pergame` ya **no** está (AUD-003 corregido) | No se re-entrenó ni se midió ECE/Brier OOS en esta ronda: exigiría ejecutar entrenamiento, fuera del alcance de solo lectura |
| Gate de predicción | P0 | REVISADA | `risk/prediction_gate.py`, `data/bets/prediction_gate.json` | Lectura + **estado vivo** | **Estado 2026-09-21T15:08:25Z: 49 cortes, 0 `allowed`, 0 `latched`, 49/49 `muestra_insuficiente`.** Default-deny efectivo → **CLAUDE-001** | — |
| Monitor de degradación | P0 | REVISADA | `risk/degradation.py`, `degradation_pause.json`, `degradation_log.csv` | Lectura + contraste estado vivo ↔ log append-only | **59 cortes, 12 pausados**; cada `pause` del log tiene `paused=true` vivo y cada `resume`, `false`. Sin contradicción | — |
| Gestión de banca y staking | P0 | REVISADA | `risk/bankroll.py`, `risk/kelly.py` | Lectura + reproducción sobre el ledger real | Ledger íntegro (1984 filas); guardas de integridad activas → **CLAUDE-005** | — |
| Liquidación | P0 | REVISADA | `settlement/settle.py`, `settlement/runner.py`, 10 tests dedicados | Lectura + suite | Definición canónica única de ROI realizado (`realized_roi_parts`) enrutada en `audit/report.py`, `audit/html_report.py`, `backtesting/roi_engine.py` y `settlement/runner.py`; **no** en `risk/bankroll.py` → **CLAUDE-005** | — |
| Atomicidad y concurrencia | P0 | REVISADA | `storage/atomic.py`, `storage/lock.py` | Lectura + ejecución dirigida | Reintento acotado a 2,0 s para violaciones de uso compartido de Windows; temporal único por proceso y llamada; fsync antes del rename → **CLAUDE-004** (el test, no la implementación) | — |
| Capa de ejecución (line shopping) | P0 | REVISADA | `pipeline/probabilities._execution_prices`, `pipeline/daily.run_league`, `config.ExecutionConfig`, `storage/served_store.COLUMNS` | Lectura del commit `6575fa8` + configuración efectiva | `execution.books = []` en producción → **capa inerte**: `execution_price` repite la mediana. El no-vig nunca se calcula sobre precios best-of-N. Claves de `_execution_prices` idénticas a las de `_consensus_lines` (verificado) | Cobrar realmente al precio de ejecución sigue sin cablear, por decisión explícita del operador |
| Derivados Fase 1 (`team_totals`) | P1 | REVISADA | `pipeline/team_totals_capture.py`, `scripts/collect_team_totals_mlb.py` | Lectura + agregados de las 1128 filas capturadas + líneas de log filtradas | Invariantes pre-registrados **se cumplen**: Over+Under = 1.000000 exacto en las 204 selecciones; 0 filas con `captured_at ≥ commence_time`; adelanto mediano 7,53 h. Presupuesto y cobertura → **CLAUDE-002**, **CLAUDE-003**, **CLAUDE-006** | Si el 2026-09-21 la MLB jugó realmente 3 partidos no es verificable en local: el almacén de resultados llega al 2026-09-20 |
| Integraciones externas | P1 | REVISADA_PARCIALMENTE | `providers/` (5 clientes) | Lectura estática | **Todas** las llamadas HTTP llevan `timeout`; `mlb_statsapi._get` lo impone por defecto; reintentos con backoff lineal y presupuesto total de espera por conexión; 429 reintentado; caché TTL 1200 s < frescura exigida 90 min | No se ejecutó ninguna llamada real: prohibido durante el diagnóstico |
| Configuración | P1 | REVISADA | `config.py`, `configs/*.yaml`, variables de entorno | `Settings.load()` efectivo | Precedencia env > yaml > default coherente; `mode=demo` es el default seguro y los BAT pasan `--mode live` explícitamente; 32 coeficientes de ajuste a 0,0 (decisión del 2026-09-01) | Los valores de `.env` no se inspeccionaron directamente (denegado por política) |
| Dependencias | P1 | REVISADA | `pyproject.toml`, `requirements.lock` | `pip-audit -r requirements.lock` | **Sin vulnerabilidades conocidas** (rc 0) | `pytest-cov`/`coverage` no están pineados en el lock y por tanto no los audita `pip-audit` (limitación ya documentada en `pyproject.toml`) |
| Seguridad y secretos | P1 | REVISADA | Todo el árbol versionado, `.gitignore`, hooks | Búsqueda de literales + verificación de seguimiento en Git | Ningún secreto versionado; `.env` y `*.env` ignorados; clave de API sólo por entorno; `deny` de permisos bloquea lectura de `.env` y `logs/` (**comprobado en vivo**: dos comandos denegados) | — |
| Pruebas | P1 | REVISADA | 147 ficheros, 2264 pruebas | Suite completa + reejecución aislada | **1 failed, 2263 passed, 1 skipped** en 4031 s. El fallo es un assert de reloj de pared bajo carga; 5/5 aislado en verde → `ENVIRONMENTAL_FAILURE` + **CLAUDE-004** | — |
| CI/CD | P1 | REVISADA | `.github/workflows/ci.yml` | Lectura + **estado del control** | `gh run list --branch main`: **verde** sobre el commit base (`35426317559`, 2026-09-19). Matriz 3.11–3.14 incluye el intérprete real de producción; `pip-audit` bloqueante | — |
| Tareas programadas | P1 | REVISADA | 5 tareas `SQP_*_Cdev` | `Get-ScheduledTaskInfo` + `pipeline_health.json` | **Ninguna en fallo.** `Capture_Close` en `Running` con rc 267009 = `SCHED_S_TASK_RUNNING`, arrancada hacía 1 min: no es cuelgue. `Dashboard` sin `NextRunTime` porque su disparador es el inicio de sesión | El **historial** del Programador sigue deshabilitado → AUD-004 **persistente** (§8) |
| Observabilidad | P1 | REVISADA | `monitoring/health.py`, `monitoring/run_status.py`, `data/output/pipeline_health.json` | Lectura + estado vivo | `status: WARN` con 0 errores y 1 aviso (historial del Programador). `pipeline_liveness: null` = pipeline vivo, comprobación independiente del centinela | Que features a 28 d y 26 ligas sin calibrador no generen aviso es **decisión registrada del operador** (B-9, 2026-09-09), no un descuido |
| Datos y persistencia | P1 | REVISADA_PARCIALMENTE | `storage/`, `data/` | Escaneos programáticos con retorno de agregados | Integridad del ledger verificada; contadores de crédito por colector con prefijo propio; escritura atómica y bloqueo en toda ruta de dinero | Los datasets completos no se cargaron a contexto por regla del proyecto |
| Rendimiento | P2 | REVISADA_PARCIALMENTE | Rutas críticas del run diario | Lectura + tiempos de la suite | Sin patrón N+1, sin recursos sin cerrar, sin recálculo redundante en la ruta de picks | No se perfiló el run diario: exigiría ejecutarlo contra el proveedor |
| Skills, agentes, comandos, routing | P2 | REVISADA | 34 skills, 22 agentes, 8 comandos, `ORCHESTRATOR.md`, `automation/` | Script propio de frontmatter y referencias + `sync_agent_instructions.py --check` | Frontmatter válido en las 34 skills; `--check` devuelve `synchronized`; **ninguna referencia rota** a rutas `.claude/` vigentes | Los dos agentes cuyo `name` difiere del fichero (`00-principal-orchestrator`, `01-repository-cartographer`) usan prefijo ordinal deliberado: no es defecto |
| Hooks | P2 | REVISADA | 7 hooks en `.claude/settings.json` + el gate `Stop` del plugin `codex` | Lectura + comprobación de centinelas + **ejecución** del runtime de Codex | Cableados y sin centinelas huérfanos (`.tests-pending` y `.crossreview-pending` ausentes) → **CLAUDE-007** (presupuesto de tiempo). El runtime de Codex **no funciona**: reproducido → **CLAUDE-008** | La primera pasada dio por buena la CLI con `command -v` y `--version`, que es **inventario, no estado**; corregido al ejercitarla (ver CLAUDE-008) |
| Limpieza y racionalización | P2 | REVISADA | Todo el árbol | Búsqueda de huérfanos + historial Git | `.claude/loops/` conserva sólo router y `STATES.md`, ambos referenciados y vivos; `registry.json` es append-only y sus rutas antiguas son historia legítima; sin backups accidentales ni artefactos de build versionados | `mlb_totals_calibration_beta.joblib` queda en disco sin estar en el registro vivo: **NO_VERIFICABLE** como eliminable (puede ser respaldo deliberado) |
| Documentación | P2 | REVISADA_PARCIALMENTE | `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/research/` | Contraste con el código | Los pre-registros son citables y sus constantes coinciden con el código; los comentarios del código citan auditoría y fecha | No se verificó comando a comando todo el `README` |
| Código generado / vendorizado | P3 | NO_APLICABLE | — | — | No hay código vendorizado ni generado en ruta ejecutable | — |
| Infraestructura declarativa | P3 | NO_APLICABLE | `Dockerfile` | Lectura | Declara explícitamente que es entorno de demo y que nadie la construye | — |
| Cuota real del proveedor | P1 | NO_VERIFICABLE | The Odds API | — | Consultarla exige una llamada externa, prohibida en diagnóstico | Relevante para **CLAUDE-002** |
| Calendario MLB del 2026-09-21 | P1 | NO_VERIFICABLE | — | Almacén local de resultados | El almacén llega al 2026-09-20 | Relevante para **CLAUDE-002** |

---

## 5. Hallazgos confirmados

### CLAUDE-001 — El gate de predicción reparte alpha entre 41 cortes y evalúa 49

| | |
|---|---|
| **Categoría** | Cuantitativo — validez del criterio pre-registrado |
| **Severidad** | MEDIUM |
| **Confianza** | HIGH |
| **Evidencia** | `STATICALLY_VERIFIED` (código + artefacto vivo + pre-registro) |
| **Prioridad** | P2 |

**Archivo/línea.** `src/sqp/risk/prediction_gate.py:102-113` (constantes) y
`:452-466` (la alarma y el volcado). Artefacto:
`data/bets/prediction_gate.json`. Pre-registro:
`docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md:115-125`.

**Activación.** Cada ejecución diaria del gate, ya hoy.

**Problema.** El pre-registro del 2026-09-04 fijó `K = 41` y derivó
`alpha_corte = 0,05 / 41 = 0,00122`. El universo evaluado ha crecido a **49
cortes**. El reparto de Bonferroni sigue dividiendo entre 41, así que la cota de
error de familia real es `49 × 0,05/41 = 0,0598`, un **19,5 % por encima** del
0,05 declarado. La alarma que debía delatarlo (`len(markets) > 50`) **no ha
saltado nunca** y está a un corte de hacerlo.

**Evidencia concreta.**

```
data/bets/prediction_gate.json  (generated_at 2026-09-21T15:08:25.900901+00:00)
  family_alpha        = 0.05
  k_bonferroni        = 41
  alpha               = 0.0012195121951219512
  n_cortes_evaluados  = 49      <-- 41 en el pre-registro
  min_n               = 300
  markets             = 49 entradas; allowed 0; latched 0; 49/49 muestra_insuficiente
```

```python
# src/sqp/risk/prediction_gate.py
PREDICTION_GATE_K = 41
PREDICTION_GATE_ALPHA = PREDICTION_GATE_FAMILY_ALPHA / PREDICTION_GATE_K
PREDICTION_GATE_K_REPREGISTRO = 50
...
if len(markets) > PREDICTION_GATE_K_REPREGISTRO:   # 49 > 50 es False
```

**Esperado.** Que la cota de error de familia declarada (0,05) se sostenga, o
que el sistema avise antes de dejar de sostenerse.

**Observado.** Cota real 0,0598, sin aviso, y el registro publica los dos
números contradictorios (`k_bonferroni: 41`, `n_cortes_evaluados: 49`) sin que
nada los compare.

**Causa raíz.** El umbral de alarma se fijó en un **valor absoluto** (50) en vez
de compararse con `PREDICTION_GATE_K`. El margen del +22 % se pensó como holgura
de re-pre-registro; en la práctica se convirtió en una franja donde el criterio
ya está incumplido y nadie lo dice.

**Consecuencia.** El día que un corte alcance `n ≥ 300`, **gasta su único test
de entrada** con un alpha que sobregira el presupuesto de la familia. Como el
test de entrada es irrepetible sin liberación humana, un falso positivo ahí
autoriza stake real sobre una puerta que el ruido abrió.

**Controles compensatorios.** Hoy los 49 cortes están en `muestra_insuficiente`
y ninguno es elegible; `allowed` y `latched` están ambos vacíos. El riesgo es
**inminente, no actual**.

**Corrección mínima propuesta.** *No es un cambio de código que una auditoría
pueda decidir*: `K` y `alpha` son parámetros de un criterio pre-registrado, y
`CLAUDE.md` clasifica «risk/model/strategy/threshold/gate parameters» como
escalación al operador. Se proponen, para que el operador elija:

1. **Sólo instrumentación (no toca el criterio):** que la alarma dispare con
   `len(markets) > PREDICTION_GATE_K`, no con `> 50`, y que el volcado incluya
   la cota real `n_cortes_evaluados × alpha`.
2. **Re-pre-registro:** fijar `K` al universo actual antes de que ningún corte
   sea elegible, documentándolo como hizo el pre-registro del 2026-09-04.

**Pruebas necesarias.** Un test que fije que con `len(markets) > K` se emite el
aviso, y otro que fije la relación `alpha = family_alpha / K` y la cota
publicada. Ambos en `tests/test_prediction_gate.py`, junto a los candados que ya
fijan `PREDICTION_GATE_K == 41`.

**Criterio de aceptación.** El registro publica la cota real de error de familia
y el aviso se emite en cuanto el universo supera el `K` con el que se repartió
el alpha, con los 49 cortes actuales.

**Limitaciones.** No es verificable desde el repositorio por qué el universo
creció de 41 a 49 (altas de ligas/torneos, mercados nuevos): exigiría el
historial de `prediction_gate.json`, que no se versiona.

---

### CLAUDE-002 — La captura Fase 1 de `team_totals` no tiene control de cobertura

| | |
|---|---|
| **Categoría** | Cuantitativo / observabilidad — integridad de una medición pre-registrada |
| **Severidad** | MEDIUM |
| **Confianza** | MEDIUM |
| **Evidencia** | `INFERRED` (la caída está reproducida; su causa, no) |
| **Prioridad** | P2 |

**Archivo/línea.** `src/sqp/pipeline/team_totals_capture.py:201-210` (filtro de
horizonte) y `:282-285` (el único resumen). `scripts/collect_team_totals_mlb.py`.

**Activación.** Cada ejecución diaria en la que el proveedor devuelva menos
eventos de los que la liga juega.

**Problema.** La Fase 1 existe para **acumular muestra fuera de muestra**. El
módulo registra cuántos eventos capturó, pero nada lo compara con la jornada
esperada ni avisa si se hunde. La cobertura observada cayó de 15 eventos a 3 en
un día, sin motivo de parada y sin que ningún control lo señalara.

**Evidencia concreta.** Agregados de `data/odds/team_totals_mlb_202609.csv` y
líneas de resumen filtradas de `logs/sqp.log`:

```
día         eventos  filas  créditos   motivo de parada registrado
2026-09-19    13      480      46      tope de créditos alcanzado (46/45)
2026-09-20    15      540      30      (ninguno)
2026-09-21     3      108       6      (ninguno)          <-- 80 % menos
```

Almacén local de resultados MLB: 15 partidos el 19-09 y 15 el 20-09. Seis
créditos = tres peticiones, luego `upcoming` traía realmente tres eventos: no
fue el presupuesto (6 ≪ 45) ni `requests_remaining` (habría dejado `stop`), ni
eventos ya comenzados (dejan línea de log propia, ausente ese día).

**Esperado.** Que una caída de cobertura del 80 % en la recolección de un
pre-registro activo deje rastro accionable.

**Observado.** Una línea INFO indistinguible de un día normal.

**Causa raíz.** El resumen es **descriptivo**, no comparativo: no existe
expectativa contra la que contrastar (partidos de la jornada, media móvil de
eventos capturados) ni umbral que dispare.

**Consecuencia.** La muestra fuera de muestra de la Fase 1 puede degradarse
durante días sin que nadie lo note, y una muestra recogida con cobertura
irregular introduce **selección no aleatoria**: los días con pocos eventos no
son un subconjunto aleatorio de los partidos.

**Controles compensatorios.** Ninguno. `health_check` no mira esta familia.

**Corrección mínima propuesta.** Registrar en el resumen los eventos
**candidatos** (`len(upcoming)`) junto a los capturados, y emitir `WARNING`
cuando los capturados caigan por debajo de una fracción de la mediana reciente
de la propia serie. Alternativa equivalente: añadir la cobertura de `team_totals`
a `monitoring/health.py` como aviso accionable.

**Pruebas necesarias.** Un test que fije que con `upcoming` no vacío y cero o
pocas capturas se emite el aviso, y que el resumen incluye el número de
candidatos.

**Criterio de aceptación.** Reproducir el día 2026-09-21 con el resumen nuevo y
comprobar que emite aviso.

**Limitaciones — `NOT_VERIFIABLE`.** Si la MLB jugó realmente tres partidos el
2026-09-21 no se puede comprobar en local: el almacén de resultados llega al
2026-09-20 y consultar el proveedor está prohibido en diagnóstico. **El hallazgo
no depende de esa respuesta**: sea cual sea, la ausencia de control de cobertura
sobre una medición pre-registrada es el defecto.

---

### CLAUDE-003 — El tope diario de créditos de `team_totals` se rebasa

| | |
|---|---|
| **Categoría** | Corrección — guardarraíl de presupuesto |
| **Severidad** | LOW |
| **Confianza** | HIGH |
| **Evidencia** | `REPRODUCED` (en los logs de producción) |
| **Prioridad** | P3 |

**Archivo/línea.** `src/sqp/pipeline/team_totals_capture.py:45` (`MAX_CREDITS_PER_DAY = 45`)
y `:227-231` (la comprobación).

**Activación.** Cuando el gasto acumulado del día llega a 44 y queda al menos un
evento por pedir.

**Problema.** El tope se comprueba **antes** de emitir la petición, pero cada
petición cuesta 2 créditos (`us,eu`). Con 44 gastados la comprobación
`44 >= 45` es falsa, se emite la petición y el día cierra en 46. El propio log
imprime la infracción.

**Evidencia concreta.**

```
logs/sqp.log  2026-09-19 03:01:00
  team_totals: [mlb] 23 eventos, 46 filas, 46 creditos (46 hoy / 46 mes);
               parada: tope de creditos alcanzado (46/45 hoy, 46/1400 mes)
data/odds/.team_totals_credits_2026-09-19  ->  46
```

**Esperado.** `spent_day ≤ 45`, que es lo que el pre-registro declara.

**Observado.** 46, y un mensaje que se anuncia a sí mismo como «tope alcanzado»
con el tope ya rebasado.

**Causa raíz.** Comprobación post-hoc de un contador que avanza a saltos de 2
contra un límite impar. La guarda mide «¿ya me pasé?» en vez de «¿me pasaré si
pido esto?».

**Consecuencia.** Sobregiro acotado de 1 crédito diario (~2,2 %). El impacto
económico es despreciable; lo que importa es que **es un guardarraíl que no
sostiene su cota declarada**, en un módulo cuyo gasto se autorizó
explícitamente con esa cota.

**Controles compensatorios.** El tope mensual (1400) y `MIN_REMAINING` (500)
siguen actuando; el sobregiro no puede acumularse más allá de 1/día.

**Corrección mínima propuesta.** Comprobar el coste **previsto** antes de pedir
(`already_day + spent + COSTE_POR_EVENTO > MAX_CREDITS_PER_DAY` → parar), o
declarar el tope en número de eventos en vez de créditos. La segunda opción
elimina la clase entera de error.

**Pruebas necesarias.** Un test con `MAX_CREDITS_PER_DAY` impar y coste 2 que
fije que el gasto final nunca supera el tope.

**Criterio de aceptación.** El contador diario nunca excede `MAX_CREDITS_PER_DAY`
para ningún coste por petición.

---

### CLAUDE-004 — Aserción de reloj de pared que vuelve no determinista la puerta principal de calidad

| | |
|---|---|
| **Categoría** | Pruebas — determinismo |
| **Severidad** | LOW |
| **Confianza** | HIGH |
| **Evidencia** | `STATICALLY_VERIFIED` + fallo observado y reejecución aislada |
| **Prioridad** | P3 |

**Archivo/línea.** `tests/test_audit_atomic_readers.py:49`
(`assert time.monotonic() - started < 4`), contra
`src/sqp/storage/atomic.py:29` (`deadline = time.monotonic() + 2.0`).

**Activación.** Máquina cargada: 2 s de reintentos + serialización + fixtures
superan los 4 s.

**Problema.** La aserción fija un presupuesto absoluto de 4 s sobre una
implementación cuyo propio plazo de reintentos es 2,0 s. El margen es de 2×,
insuficiente en una máquina que ejecuta a la vez el pipeline diario. El fichero
razona explícitamente que un temporizador de reloj de pared es frágil («A
wall-clock timer could close before a slow writer reaches replace») y aun así
conserva uno en la aserción.

**Evidencia concreta.**

```
Suite completa (2026-09-22, con la tarea diaria y el dashboard en paralelo):
  1 failed, 2263 passed, 1 skipped in 4031.25s
  tests/test_audit_atomic_readers.py::test_reader_contention_preserves_atomicity[False-csv]
  assert (178638.3850894 - 178633.8996062) < 4     -> 4.485 s

Reejecución aislada, 5 veces:  4 passed en 11.03 / 10.06 / 12.50 / 8.82 / 12.14 s
```

Para referencia, la misma suite tardó 838,74 s en la ronda `audit-2026-09-18`:
esta ejecución fue **4,8× más lenta** por contención de la máquina.

**Esperado.** Que la suite dé el mismo veredicto en la misma base.

**Observado.** Rojo bajo carga, verde aislado, sin que nada haya cambiado en el
código.

**Causa raíz.** Se mide tiempo absoluto de pared en lugar de la propiedad que
interesa: que `_replace` **no reintente indefinidamente** y respete su plazo.

**Consecuencia.** La suite es la puerta que el hook `run-tests-on-stop.sh`
convierte en bloqueo de turno (`exit 2`). Un rojo aleatorio bloquea un turno sin
defecto que corregir — y, peor en este repositorio, entrena a leer un rojo como
ruido.

**Controles compensatorios.** Ninguno; el test no está marcado `slow` ni
tolerado.

**Corrección mínima propuesta.** Medir sólo la llamada a `publish()` y acotarla
en términos del plazo de la implementación (p. ej. `< 2.0 + holgura`, con la
holgura declarada), o sustituir la medida de pared por un reloj inyectado que
cuente los reintentos. **No** relajar la aserción a un número mayor sin
vincularla al plazo real: eso reproduce el defecto más lejos.

**Pruebas necesarias.** La propia prueba, reescrita; conviene ejecutarla bajo
carga artificial para comprobar que ya no depende del reloj de pared.

**Criterio de aceptación.** 20 ejecuciones consecutivas en verde con la máquina
cargada.

---

### CLAUDE-005 — `bankroll.summary()` es el único consumidor de ROI realizado fuera de la definición canónica

| | |
|---|---|
| **Categoría** | Cuantitativo — coherencia de métricas de apuestas |
| **Severidad** | LOW |
| **Confianza** | HIGH |
| **Evidencia** | `STATICALLY_VERIFIED` (divergencia **latente**, reproducida como nula hoy) |
| **Prioridad** | P3 |

**Archivo/línea.** `src/sqp/risk/bankroll.py:333-350` (numerador
`realized_pnl()`, definido en `:225-233`), frente a
`src/sqp/settlement/settle.py:133-140` (`realized_roi_parts`).

**Activación.** Cuando alguna fila liquidada con `result` fuera de
`{win, loss, half_win, half_loss}` traiga `pnl ≠ 0`.

**Problema.** `AUD-002` (ronda 2026-09-17) estableció **una sola** definición de
ROI realizado: numerador y denominador sobre el **mismo** conjunto de filas, el
de stake arriesgado. Cuatro consumidores la respetan importando
`realized_roi_parts` (`audit/report.py`, `audit/html_report.py`,
`backtesting/roi_engine.py`, `settlement/runner.py`). `bankroll.summary()` no:
suma `pnl` sobre **todas** las filas liquidadas y lo divide por el stake de
**sólo** las filas con stake arriesgado, y además reimplementa el filtro en
línea (`df["result"].isin(["win", "loss", *HALF_RESULTS])`) en vez de llamar a
`staked_mask`.

**Evidencia concreta.** Reproducción sobre el ledger real:

```
filas liquidadas: 1984  (loss 1172, win 748, push 32, void 27, half_win 5)
pnl de TODAS las filas   (numerador de bankroll) : -84.25
pnl canónico (stake arriesgado)                  : -84.25
pnl de filas FUERA del conjunto con stake        :   0.00  (n = 59)
stake canónico                                   :  552.14
ROI bankroll  : -0.152588      ROI canónico : -0.152588      DIVERGE HOY: False
```

**Esperado.** Un solo camino a la métrica canónica.

**Observado.** Dos caminos que hoy coinciden **por accidente de los datos**:
`settle_candidates` asigna `pnl = 0.0` a `push` y `void`, así que los 59
registros fuera del conjunto aportan cero.

**Causa raíz.** La remediación de `AUD-002` enrutó los consumidores que
calculaban mal el número, pero no el que ya daba el número correcto por
casualidad.

**Consecuencia.** Latente. Una corrección manual de `pnl` sobre un `void`, o un
tipo de resultado futuro que arriesgue stake parcialmente, haría divergir **sólo
el panel de banca y el dashboard** del resto del sistema, en silencio y con la
misma etiqueta.

**Controles compensatorios.** Ninguno detecta la divergencia; ningún test la
fija.

**Corrección mínima propuesta.** Sustituir en `bankroll.summary()` el numerador
y el filtro por `realized_roi_parts(df)` / `staked_mask`, preservando las claves
de salida (`realized_pnl` sigue siendo el pnl total del ledger si se usa para el
saldo; el ROI pasa a usar el numerador canónico).

**Pruebas necesarias.** Un test con una fila `void` de `pnl ≠ 0` que fije que
`bankroll.summary()["realized_roi"]` coincide con `realized_roi_parts`.

**Criterio de aceptación.** El test falla antes del cambio y pasa después, y el
ROI del ledger real no se mueve (−0,1526).

---

### CLAUDE-006 — `.team_totals_credits_*` crece sin techo: la lista de purga no lo incluye

| | |
|---|---|
| **Categoría** | Limpieza / retención |
| **Severidad** | LOW |
| **Confianza** | HIGH |
| **Evidencia** | `STATICALLY_VERIFIED` |
| **Prioridad** | P3 |

**Archivo/línea.** `src/sqp/pipeline/cleanup.py:250-262` (lista blanca de
`purge_old_artifacts`), frente a
`src/sqp/pipeline/team_totals_capture.py:48` (`CREDITS_PREFIX = ".team_totals_credits_"`).

**Activación.** Cada día de captura crea un contador nuevo que nadie borra.

**Problema.** La lista blanca de purga contempla `.closing_credits_*` pero no la
familia `.team_totals_credits_*`, introducida el 2026-09-19. Es exactamente la
causa raíz —familias que crecen sin techo— que `AUD-LOW-002` (2026-09-13) llevó
a crear las entradas de purga.

**Evidencia concreta.**

```python
# cleanup.py
"closing_credits": (root / "data" / "odds", ".closing_credits_*"),
# no existe una entrada equivalente para ".team_totals_credits_*"
```

```
data/odds/.team_totals_credits_2026-09-19   ->  46
data/odds/.team_totals_credits_2026-09-20   ->  30
data/odds/.team_totals_credits_2026-09-21   ->   6
```

**Esperado.** Retención de 90 días, como el resto de contadores diarios.

**Observado.** Crecimiento indefinido: ~365 ficheros/año en `data/odds/`.

**Causa raíz.** El colector nuevo copió el mecanismo de contadores por prefijo
(bien) sin extender la lista de retención (olvido).

**Consecuencia.** Ruido acumulativo en el directorio de cuotas. Sin impacto
funcional: `spent_this_month` sólo consulta el mes corriente, así que purgar por
encima de 90 días es seguro.

**Corrección mínima propuesta.** Añadir
`"team_totals_credits": (root / "data" / "odds", ".team_totals_credits_*")` a
`families`.

**Pruebas necesarias.** Extender el test de `purge_old_artifacts` con la familia
nueva y un contador del mes corriente que **no** debe borrarse.

**Criterio de aceptación.** Un contador de hace 100 días se purga; uno de este
mes sobrevive y `spent_this_month` sigue devolviendo el total correcto.

---

### CLAUDE-007 — El hook `Stop` de pruebas no cabe en su timeout: la puerta no emite veredicto

| | |
|---|---|
| **Categoría** | Control — presupuesto de tiempo |
| **Severidad** | **MEDIUM** |
| **Confianza** | HIGH |
| **Evidencia** | `REPRODUCED` (medido con el comando exacto del hook) |
| **Prioridad** | **P1** |

**Archivo/línea.** `.claude/settings.json` (hook `Stop`, `"timeout": 600`) y
`.claude/hooks/run-tests-on-stop.sh` (última línea ejecutable:
`PYTHONPATH=src pytest tests/ -q -x --maxfail=1 -m "not slow"`).

**Activación.** Cualquier turno en el que `mark-tests-pending.sh` deje el
centinela, es decir, **cualquier turno que edite `src/`, `tests/` o `scripts/`**.

**Problema.** El subconjunto `not slow` tarda hoy **796 s**; el presupuesto del
hook son **600 s**. El harness mata el hook antes de que termine, así que el
veredicto **nunca llega** y el turno cierra en verde con la suite sin comprobar.
Es, literalmente, la avería que el propio fichero documenta haber sufrido el
2026-09-04 —entonces con `timeout` 300 s contra 1028 s de trabajo—, reaparecida
por el otro extremo: aquel día se arregló el comando (se añadió `-m "not slow"`)
y se subió el presupuesto a 600 s sobre una medición de **270,73 s**. La suite
ha crecido desde entonces y el presupuesto no se movió con ella.

**Evidencia concreta.**

```
$ PYTHONPATH=src python -m pytest tests/ -q -x --maxfail=1 -m "not slow" \
      -p no:cacheprovider --basetemp=.codex-tmp/aud0922-notslow
2040 passed, 225 deselected in 796.09s (0:13:16)
RC=0
```

```json
// .claude/settings.json
{ "Stop": [ { "hooks": [ { "command": ".../run-tests-on-stop.sh", "timeout": 600 } ] } ] }
```

Serie histórica del mismo subconjunto, con el número de pruebas:

| Fecha | Pruebas `not slow` | Duración | % del presupuesto de 600 s |
|---|---|---|---|
| 2026-09-04 | 1269 | 270,73 s | 45 % |
| 2026-09-18 (ronda anterior) | 1967 | 489,76 s | 82 % |
| **2026-09-22 (esta ronda)** | **2040** | **796,09 s** | **133 %** |

**Esperado.** Que el hook termine dentro de su presupuesto y devuelva `exit 0`
(verde) o `exit 2` (bloqueo con el fallo pegado).

**Observado.** El comando necesita un 33 % más de tiempo del que tiene.

**Causa raíz.** El presupuesto de tiempo del control es una **constante fijada
una vez** contra una suite que crece de forma continua. Nada mide la relación
entre ambos, así que el margen se consume en silencio: del 45 % al 82 % y de ahí
a rebasarlo.

**Consecuencia — doble, y la segunda es peor.**

1. **La puerta no protege.** El veredicto no llega; el turno cierra en verde
   aunque la suite esté rota.
2. **Y además cuesta 10 minutos por turno.** `rm -f "$marker"` está **sólo** en
   la rama de éxito (línea final del script). Si el harness mata el hook, el
   centinela `.claude/.tests-pending` sobrevive, así que el turno siguiente
   vuelve a lanzar la suite, vuelve a agotar los 600 s y vuelve a no decir nada.
   El control no se auto-recupera: se atasca gastando el presupuesto completo en
   cada turno.

**Controles compensatorios.** CI sí ejecuta la suite entera (incluidos los
`slow`) en las patas 3.11/3.13/3.14 y estaba **verde** sobre el commit base. La
protección existe, pero **aguas abajo**: llega al publicar, no al cerrar el
turno, que es justo cuando este hook debía cazar el fallo.

**Condiciones de la medición — declaradas.** Se midió con la máquina en reposo
relativo (la suite completa y `pip-audit` ya habían terminado; la tarea
`SQP_Capture_Close_Cdev` corre 1 min cada 30). La suite completa de esta sesión
tardó 4031 s frente a los 838 s de la ronda 18, así que **parte** de la
diferencia es carga de máquina. El hallazgo no depende de cuánta: incluso
tomando la medición más favorable disponible (489,76 s, ronda 18), el margen era
del 18 % sobre una suite que ha sumado 73 pruebas `not slow` desde entonces, y
el hook se ejecuta precisamente en la máquina real, con su carga real.

**Corrección mínima propuesta.** Dos cambios, ninguno de los cuales debilita la
puerta:

1. Subir el `timeout` del hook a un valor con margen medido (p. ej. 1200 s) —y
   dejar escrito, como ya hace el fichero, contra qué medición se fijó.
2. Mover `rm -f "$marker"` **fuera** de la rama de éxito, o registrar el intento,
   para que un hook matado no condene al turno siguiente a repetir el gasto
   completo sin veredicto.

Una tercera opción, más duradera pero de más alcance: que el hook acote su
propio trabajo (p. ej. ejecutar sólo las pruebas alcanzadas por los ficheros
tocados) en lugar de perseguir a una suite que seguirá creciendo.

**Pruebas necesarias.** No es código del paquete, así que la validación es la
medición: ejecutar el comando exacto del hook y comprobar que cabe en el
presupuesto con holgura declarada. Conviene además un candado que compare
`timeout` con la duración medida más reciente, al estilo de los candados que el
proyecto ya usa en `tests/test_claude_system_contract.py`.

**Criterio de aceptación.** El comando del hook termina dentro de su `timeout`
con al menos un 30 % de margen en la máquina real, y un hook interrumpido no
deja el centinela bloqueando el turno siguiente.

---

### CLAUDE-008 — La revisión cruzada de Codex no se ejecuta: el runtime devuelve vacío

| | |
|---|---|
| **Categoría** | Control — revisión independiente |
| **Severidad** | MEDIUM |
| **Confianza** | HIGH |
| **Evidencia** | `REPRODUCED` |
| **Prioridad** | P2 |

**Archivo/línea.** `.claude/hooks/crossreview-on-stop.sh` (consumidor del
proyecto) y el gate `Stop` del plugin `codex`
(`~/.claude/plugins/cache/openai-codex/codex/1.0.6/scripts/stop-review-gate-hook.mjs:99-128`).
Runtime: `scripts/codex-companion.mjs`.

**Activación.** Cada cierre de turno con el centinela puesto. **Observado en
vivo durante esta misma auditoría**, al intentar cerrar la sesión.

**Problema.** El runtime de Codex está instalado y responde a `--version`, pero
**una tarea real falla**: abre hilo, devuelve salida vacía y sale con código 1.
La revisión independiente —el control al que este repositorio atribuye haber
cazado tres defectos que la revisión Claude-sobre-Claude no vio— **no se está
ejecutando**.

**Evidencia concreta.** Reproducido con una tarea trivial:

```
$ codex --version
codex-cli 0.155.1                     <-- instalado y responde

$ node .../scripts/codex-companion.mjs task --json "ping: responde OK"
{ "status": 1, "threadId": "01a0c972-...", "rawOutput": "", "touchedFiles": [], "reasoningSummary": [] }
RC=1                                   <-- hilo abierto, salida VACIA, codigo 1
```

Coherente con el otro síntoma observado al arrancar la sesión: el servidor MCP
`codex` falló con `CONNECTION_CLOSED`. `~/.codex/auth.json` existe (4000 bytes,
2026-09-16). Las dos vías —MCP y CLI— fallan; el binario, no.

**Esperado.** Que la revisión se ejecute, o que su no ejecución se anuncie sin
ambigüedad.

**Observado.** El gate del plugin devolvió:

> `The stop-time Codex review task failed: (node:9752) [DEP0190] DeprecationWarning: Passing args to a child process with shell option true…`

La rama de fallo compone el mensaje con
`String(result.stderr || result.stdout).trim()`, y lo único que el hijo escribió
en `stderr` fue **un aviso de obsolescencia de Node inofensivo**. Así que el
gate presenta como «causa del fallo» un mensaje que no tiene nada que ver con
la causa, y la causa real —salida vacía con código 1— queda oculta.

**Causa raíz.** Dos, apiladas:

1. **La de fondo:** el runtime de Codex no completa tareas en esta máquina
   (causa exacta no determinable desde el repositorio: el runtime no emite
   diagnóstico).
2. **La que la esconde:** el gate del plugin usa como detalle del error el
   primer `stderr` no vacío, sin distinguir un aviso de un fallo. Es
   exactamente el patrón `KI-035` que este repositorio ya documentó y corrigió
   en su propio `crossreview-on-stop.sh` —«un fallo de INFRAESTRUCTURA llegaba
   disfrazado de veredicto»— reaparecido en el hook del plugin, que no está bajo
   control del proyecto.

**Consecuencia.** Todo cambio de riesgo cierra turno **sin revisión de un
tercero**. Y los dos consumidores se comportan de forma opuesta ante el mismo
fallo:

- `crossreview-on-stop.sh` (del proyecto) **degrada bien**: detecta el fallo de
  infraestructura, imprime «LA REVISION CRUZADA NO SE EJECUTO», repone el
  centinela y sale con 0 sin bloquear.
- El gate del plugin **bloquea el cierre del turno** con un mensaje cuya causa
  declarada es falsa.

**Controles compensatorios.** CI ejecuta la suite completa al publicar. No
sustituye a la revisión independiente: son controles distintos.

**Corrección mínima propuesta.** No es código del repositorio, así que el
proyecto no puede arreglar la causa de fondo. Lo que sí está en su mano:

1. **Diagnosticar el runtime** fuera de un turno (reautenticar `codex`,
   comprobar cuota, reinstalar el plugin) y **confirmar con una tarea real**,
   no con `--version`.
2. **Mientras no funcione**, decidir explícitamente entre desactivar el gate
   `Stop` del plugin —que hoy bloquea sin aportar revisión— o dejarlo y asumir
   el bloqueo. El del proyecto puede quedarse: degrada correctamente.
3. Registrar el estado en `known-issues.md` junto a `KI-055`, que ya recoge la
   caída del MCP: son el mismo problema visto por dos vías.

**Pruebas necesarias.** Una comprobación de **estado**, no de configuración:
ejercitar el runtime con una tarea trivial y exigir `status: 0` con
`rawOutput` no vacío. `command -v codex` y `codex --version` **no** valen — es
precisamente el error que cometí en la primera pasada de esta auditoría.

**Criterio de aceptación.** `codex-companion.mjs task --json "…"` devuelve
`status: 0` con salida no vacía, y un turno con cambios de riesgo produce un
veredicto real.

**Corrección a mi propio informe.** En la primera pasada marqué el área de hooks
como `REVISADA` apoyándome en que la CLI `codex` estaba disponible, y descarté
la caída del MCP razonando que «el hook usa la CLI, no el MCP». **Era
inventario presentado como estado**: la disponibilidad del binario no dice nada
sobre si el control pasa. El propio contrato de esta auditoría advierte de ese
error —«inventariar un control no es comprobarlo»— y lo cometí. La matriz de
cobertura y el descarte correspondiente quedan corregidos.

---

## 6. Candidatos descartados

Se conservan porque su descarte es informativo.

| Candidato | Por qué se descarta |
|---|---|
| `grade_captures` lanzaría `TypeError` cuando ninguna fila es graduable (columna `team_runs` de `None` comparada con `point`) | **Reproducido y refutado**: con pandas 3.0.2 devuelve `team_runs=None`, `result=None` sin excepción. Probados los tres casos (ninguna graduable, todas, mezcla). |
| `data/models/registry.json` apunta a árboles retirados (`OneDrive/Proyectos/5`, `C:\dev\sports-quant-platform`) | Es un registro **append-only**: 68 entradas, 32 con rutas históricas y las 36 vigentes (incluidas las 3 últimas) apuntando a `C:\dev\3`. La historia no es deriva. |
| El estado de la pausa por degradación contradiría su log append-only | **Refutado con medición**: 12 de 59 cortes pausados; cada `pause` del log tiene `paused=true` en el estado vivo y cada `resume`, `false`. Una primera lectura mía buscó claves inexistentes (`status`/`state`); corregida. |
| `.claude/loops/` sería residuo de la fusión del 2026-09-18 | Conserva sólo `quant/00-quant-operations-router.md` y `quant/STATES.md`, ambos referenciados por `.claude/CLAUDE.md`, `ORCHESTRATOR.md` y el bloque común de las skills quant. Vivos. |
| Tres agentes apuntan a loops borrados (`backtest.md`, `refactor.md`, `release.md`) | La cita es de **procedencia**, no puntero: `## Checklist (antes \`.claude/loops/refactor.md\`)`. El contrato `test_no_skill_still_points_at_a_deleted_loop` ya lo fija. |
| `health_check` no avisa de features a 28 días ni de 26 ligas sin calibrador | **Decisión registrada del operador** (B-9, 2026-09-09), razonada en el propio código: la tarea que refrescaba esos datasets se retiró y un aviso sin dueño posible entrena a ignorar los que sí lo tienen. |
| `pipeline_liveness: null` sería un control que no informa | `None` es su valor de «sin problema»; el pipeline produjo artefactos dentro de `RUN_MAX_AGE_DAYS`. |
| `SQP_Capture_Close_Cdev` con `LastTaskResult` 267009 estaría en fallo | `267009 = 0x41301 = SCHED_S_TASK_RUNNING`. Arrancó a las 09:30:01 y la consulta fue a las 09:31:11: un minuto, no un cuelgue. |
| `SQP_Dashboard_Cdev` sin `NextRunTime` estaría desprogramada | Su disparador es de **inicio de sesión** (`MSFT_TaskLogonTrigger`, `Delay PT1M`); no tener próxima ejecución es lo correcto. |
| ~~El servidor MCP `codex` caído dejaría sin revisión cruzada~~ | **DESCARTE RETIRADO.** Lo razoné como «el hook usa la CLI, no el MCP» apoyándome en `command -v codex` y `--version`. Al ejercitar el runtime con una tarea real, falla igual: salida vacía y código 1. Promovido a **CLAUDE-008**. |
| `execution_price` podría ejecutar a precios peores que la mediana sin avisar | Cierto por diseño y documentado, pero **inerte**: `execution.books = []` en producción, así que `execution_price` repite la mediana en todas las filas. Se registra como observación (§7), no como defecto. |
| `_execution_prices` podría no casar claves con `_consensus_lines` y degradar en silencio | **Verificado**: ambas construyen la clave como `(ln.market, ln.outcome, ln.point)` y aplican el mismo predicado `is_usable_price`. |
| Secretos versionados | Ninguno. `.env` y `*.env` ignorados; sin literales en código; la clave sólo por entorno; el `deny` de permisos bloqueó en vivo dos intentos de lectura. |
| Llamadas HTTP sin timeout | Ninguna. `mlb_statsapi._get` impone el suyo por defecto precisamente para el llamador que lo olvide. |

---

## 7. Observaciones informativas

No son defectos. Son hechos medidos que el operador debería tener delante.

**Rendimiento realizado (ledger completo, `data/bets/settled_*.csv`).**

| Métrica | Valor |
|---|---|
| Filas liquidadas | 1984 |
| Filas con stake arriesgado | 1925 (`win` 748, `loss` 1172, `half_win` 5) |
| Stake total arriesgado | 552,14 |
| Pnl realizado | **−84,25** |
| **ROI realizado** | **−15,26 %** |
| Tasa de acierto observada (`win`/(`win`+`loss`)) | 38,96 % |

Son **ROI realizado** y **tasa de acierto observada** sobre el histórico
liquidado, no una probabilidad estimada, ni una probabilidad implícita, ni un
edge, ni un ROI esperado, ni una promesa de rentabilidad. Una tasa de acierto no
es un enunciado de rentabilidad.

**Estado de las puertas.**

- Gate de predicción: **0 de 49** cortes habilitados para stake real; los 49 en
  `muestra_insuficiente`; ningún pestillo armado. Default-deny efectivo.
- Gate de CLV: **deshabilitado** (`clv_gate_enabled = False`), coherente con la
  decisión del 2026-08-16 de que la regla rectora es el gate de predicción.
- Monitor de degradación: **12 de 59** cortes auto-pausados —`ncaaf|h2h`,
  `ncaaf|spreads`, `ncaaf|totals`, `mls|h2h`, `mls|spreads`, `wnba|h2h`,
  `wnba|totals`, `mlb|totals` y 4 de tenis—. El control actúa.
- Line shopping: **inerte** (`execution.books = []`). `price_decimal`, no-vig,
  edge, selección, stake y liquidación siguen sobre la mediana del consenso,
  como declara el commit `6575fa8`.

**Invariantes de la Fase 1 de derivados que sí se cumplen.** Over + Under =
`1.000000` exacto en las 204 selecciones; **0** filas con
`captured_at ≥ commence_time` (KI-019); adelanto mediano de captura 7,53 h; sólo
líneas de medio punto; ningún precio degenerado.

**Antigüedad de artefactos.** Features a 28,1 días; modelos MLB a 28 días y
NBA/NFL/NHL a 42. No genera aviso por decisión del operador (§6). Se consigna
para que la decisión se revise con el dato delante, no para reabrirla.

**Deuda menor sin consecuencia demostrada.** `data/models/mlb_totals_calibration_beta.joblib`
está en disco sin figurar en `calibration_methods.json` (que resuelve
`isotonic` para ese mercado). Podría ser respaldo deliberado de una promoción
anterior: **`NO_VERIFICABLE`** como eliminable, y por la regla de seguridad no
entra en ningún plan de borrado.

---

## 8. Comparación histórica (ronda `audit-2026-09-18`)

Revalidada **cada ID contra el código actual**, después de fijar las conclusiones
propias.

| ID | Estado en esta ronda | Evidencia |
|---|---|---|
| `AUD-001` — `gate_status.py` evaluaba otra regla y anunciaba «PASAN EL GATE» | **CORREGIDO** | `scripts/gate_status.py` ya no reconstruye regla paralela: importa `evaluate_markets`, `load_prediction_gate`, `market_allowed`, `PREDICTION_GATE_ALPHA` y `PREDICTION_GATE_MIN_N` del módulo canónico y separa veredicto persistido de progreso estadístico. |
| `AUD-002` — raíz JSON no objeto rompía el default-deny | **CORREGIDO** | `prediction_gate.load_prediction_gate:551` y `degradation.load_degradation_registry:186` comprueban `isinstance(payload, dict)` **antes** del `.get`, y devuelven `{}` si `markets` no es dict. |
| `AUD-003` — clave sandbox `mlb_h2h_pergame` en el registro live | **CORREGIDO** | `data/models/calibration_methods.json` = `{mlb_spreads: beta, mlb_totals: isotonic, wnba_spreads: beta}`; `promotion_log.csv:102` registra la degradación fechada 2026-09-18. |
| `AUD-004` — historial del Programador de tareas deshabilitado | **PERSISTENTE** | `data/output/pipeline_health.json` (2026-09-21): `scheduled_tasks.history_enabled = false` y el aviso sigue emitiéndose. La remediación añadió **detección**, no la habilitación (exige proceso elevado). Sigue sin haber rastro diagnosticable de una tarea que no llegue a lanzarse. |
| `AUD-005` — el log anunciaba habilitados desde `decided` (pre-pestillo) | **CORREGIDO** | `scripts/run_all.py:310-318` lee el veredicto con `gate_allowed_markets(...)` del registro recién escrito; `decided` queda sólo para el resumen de progreso. |
| `AUD-006` — la captura de cierre pedía 3 mercados también en tenis | **CORREGIDO** | `pipeline/daily.markets_for_family:63-71` devuelve `"h2h"` para tenis, y `closing_capture:145` la usa. Regla única para run y captura. |
| `AUD-007` — `check-secrets.sh` marcaba código fuente citado como secreto | **CORREGIDO** | `.claude/hooks/_secret_literals.py` añade `_symbolic()`, que descarta asignaciones reflexivas y trunca el valor en la primera secuencia de escape literal. Sin reincidencia en esta sesión. |

**Balance:** 6 corregidos, 1 persistente, 0 regresiones, 0 no verificables.
Ninguna de las correcciones de la ronda 18 introdujo un defecto nuevo detectable
en esta auditoría.

---

## 9. Validaciones ejecutadas

| Comando | Código | Resultado | Clasificación |
|---|---|---|---|
| `ruff check src scripts tests` | 0 | `All checks passed!` | OK |
| `mypy src` | 0 | `Success: no issues found in 106 source files` | OK |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-aud0922` | 1 | **1 failed, 2263 passed, 1 skipped** en 4031,25 s | `ENVIRONMENTAL_FAILURE` (ver CLAUDE-004) |
| El mismo test, aislado, ×5 | 0 | `4 passed` en 11,03 / 10,06 / 12,50 / 8,82 / 12,14 s | OK |
| `pip-audit -r requirements.lock` | 0 | `No known vulnerabilities found` | OK |
| `scripts/sync_agent_instructions.py --check` | 0 | `Agent instructions: synchronized` | OK |
| `gh run list --branch main --limit 8` | 0 | Último run `35426317559` **success** sobre el commit base | OK — **CI verde** |
| `Get-ScheduledTask SQP_* \| Get-ScheduledTaskInfo` | 0 | 5 tareas, ninguna en fallo | OK |
| `PYTHONPATH=src pytest tests/ -q -x --maxfail=1 -m "not slow"` (comando exacto del hook `Stop`) | 0 | **2040 passed, 225 deselected en 796,09 s** frente a un `timeout` de 600 s | OK el comando, **FALLA el control** → CLAUDE-007 |

---

## 10. Plan priorizado

Ninguna corrección está autorizada por esta auditoría. El orden atiende a
impacto y dependencia, no a esfuerzo.

| Orden | ID | Prio | Cambio mínimo | Archivos | Autorización |
|---|---|---|---|---|---|
| 1 | CLAUDE-007 | **P1** | Subir el `timeout` a un valor con margen medido y sacar `rm -f "$marker"` de la rama de éxito | `.claude/settings.json`, `.claude/hooks/run-tests-on-stop.sh` | Alcance ordinario |
| 2 | CLAUDE-001 | P2 | Elegir entre (a) alarma con `> PREDICTION_GATE_K` + publicar la cota real, o (b) re-pre-registrar `K`. **Decisión del operador**, no de la auditoría | `src/sqp/risk/prediction_gate.py`, `tests/test_prediction_gate.py`, `docs/research/` si se re-pre-registra | **Escalación**: parámetro de gate (`CLAUDE.md`) |
| 3 | CLAUDE-008 | P2 | Diagnosticar el runtime de Codex con una tarea **real** y decidir qué hacer con el gate `Stop` del plugin mientras no funcione | Fuera del repositorio (runtime/plugin) + `.claude/memory/known-issues.md` | Alcance ordinario |
| 4 | CLAUDE-002 | P2 | Registrar candidatos vs capturados y avisar ante caída de cobertura | `src/sqp/pipeline/team_totals_capture.py`, `tests/test_team_totals_capture.py` | Alcance ordinario |
| 5 | CLAUDE-004 | P3 | Acotar la prueba al plazo de la implementación en vez de al reloj de pared | `tests/test_audit_atomic_readers.py` | Alcance ordinario |
| 6 | CLAUDE-003 | P3 | Comprobar el coste **previsto** antes de pedir | `src/sqp/pipeline/team_totals_capture.py`, tests | Alcance ordinario |
| 7 | CLAUDE-005 | P3 | Enrutar `bankroll.summary()` por `realized_roi_parts` / `staked_mask` | `src/sqp/risk/bankroll.py`, `tests/test_bankroll.py` | Alcance ordinario |
| 8 | CLAUDE-006 | P3 | Añadir la familia `.team_totals_credits_*` a la lista de purga | `src/sqp/pipeline/cleanup.py`, tests | Alcance ordinario |
| — | `AUD-004` (r18) | P2 | Habilitar el historial del Programador (`wevtutil sl ... /e:true`) | Host, no repositorio | **Proceso elevado** |

**Por qué CLAUDE-007 va primero.** Es el único que deja **inoperativa** una
puerta de calidad hoy mismo, y además grava cada turno con 600 s sin devolver
veredicto. Los demás tienen consecuencia latente o acotada; éste está activo.

---

## 11. Riesgos residuales y limitaciones

1. **Sin segunda opinión.** Esta ronda tiene un solo auditor. La consolidación
   lo declara. No se inventó informe del auditor ausente.
2. **La cuota real del proveedor no es verificable** sin una llamada externa
   prohibida en diagnóstico. Relevante para CLAUDE-002.
3. **El calendario MLB del 2026-09-21 no es verificable en local**: el almacén de
   resultados llega al 2026-09-20.
4. **La calibración no se midió fuera de muestra** en esta ronda: exigiría
   entrenar, fuera del alcance de solo lectura. El estado del registro vivo sí
   se verificó.
5. **`.env` no se inspeccionó**; la configuración efectiva se obtuvo por
   `Settings.load()` sin imprimir secretos.
6. **`data/` y `logs/` no se cargaron completos** por regla del proyecto; todo lo
   afirmado sobre ellos procede de escaneos programáticos que devuelven agregados.
7. **Bookkeeping excluido y declarado**: no se actualizó
   `.claude/automation/runtime/current-task.md`, `Obsidian/` ni
   `.claude/memory/`. El contrato declara el diagnóstico de solo lectura del
   proyecto salvo los entregables de la fase; escribir ahí sería escribir fuera
   del destino autorizado. Corresponde a una fase de remediación autorizada.
8. **Auditoría completa ≠ código correcto.** La suite verde no acredita
   corrección, las pruebas no ejecutadas no están aprobadas, y **nada aquí
   demuestra ventaja predictiva ni rentabilidad**.
