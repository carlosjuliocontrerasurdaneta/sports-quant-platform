# Current Task

Status: closed
Result: DEGRADED
Primary loop: `audit.md`
Skills: `full-audit` (fases 0-3) → `audit-remediation` (fases 4-5)
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`); revisión independiente en `fable` de los cambios de contrato del ledger
Date: 2026-09-13

## Routing

Modo no orquestado en las fases 0–3 (validación independiente por segundo
método en la misma sesión). En la Fase 4, escalón `fable` (parámetro
`model: "fable"` de `Agent`, según la REGLA DE DESPACHO de `MODEL_ROUTING.md`)
para revisar AUD-MED-002 (`half_win`/`half_loss`) y AUD-MED-003/004 (picks
`superseded`, fallback histórico de tenis): clase de escalado «cambiar el
contrato de un artefacto persistido» (`settled_*.csv`). Veredicto: 0 defectos
confirmados; 1 sugerencia menor aplicada. No se tocó ningún parámetro de
riesgo, modelo, estrategia, umbral ni gate, y no se contradijo ninguna decisión
registrada (AUD-MED-006 registra la vigente, no la cambia).

## Objetivo

Auditoría integral del proyecto y aplicación de las correcciones aprobadas
(«todos los hallazgos confirmados y las mejoras demostradas»).

## Resultado: por qué DEGRADED y no PASS

Se cumplen: comandos requeridos con exit 0 (ruff, mypy, fast 1787 passed,
slow 224 passed / 1 skipped), artefactos obligatorios escritos y legibles
(`audit/latest/{FINDINGS,BACKLOG,CHANGES,VALIDATION,EXECUTIVE_SUMMARY}.md`,
`MANIFEST.json`), repositorio Git reconstituido y rama publicada. Lo que impide
`PASS`, dicho sin esconderlo:

- **AUD-HIGH-002 (2b)**: las 5 tareas del Programador siguen en «Solo
  interactivo»; cambiarlas exige orden explícita del operador. Sin eso, un día
  sin sesión sigue sin producir picks (ahora al menos con aviso al logon).
- **`VALIDATE_OOS.bat` sigue sin ejecutarse** (B-01, `rc 1` del 01-09).
- **`wnba_totals_calibration_iso.joblib`** (colapsado, inerte) no se movió a
  `retired/`: escritura en `data/` bloqueada por el clasificador de permisos.
- El ledger histórico **no se regraduó** (1 línea de cuarto mal graduada, 150
  picks sin veredicto): la corrección aplica hacia delante; regraduar el pasado
  es decisión aparte.
- `codex review` y `pip-audit` no ejecutados (cuota / red).

## Siguiente acción

Del operador: (1) abrir/mergear el PR `prod/remediacion-20260913` → `main` y
comprobar el CI sobre él; (2) decidir el modo de inicio de sesión de las
tareas; (3) `! cmd /c VALIDATE_OOS.bat`; (4) mover el `.joblib` retirado;
(5) aprobar el MCP `graphify` o retirar la instrucción de `.claude/CLAUDE.md`.

---

## Registro de enrutamiento — auditoría independiente `audits/` (2026-09-14)

Tarea: `audits/prompts/auditoria-claude-code-opus-5.md` (solo lectura; informe en
`audits/claude/latest.md`). Sesión principal en `claude-opus-5`. Despachos con el
parámetro `model` de `Agent`, según la REGLA DE DESPACHO:

- `fable` — lógica cuantitativa (fuga, calibración, gates, liquidación): clase
  «parámetros de riesgo/modelo/umbral/gate» (el informe alimenta la remediación).
- `opus` — datos/proveedores/robustez: **abortado por el API (HTTP 429, límite
  semanal) sin producir salida**; el área la cubrió la sesión principal.
- `opus` — operaciones/infraestructura/seguridad.
- `sonnet` — calidad de la suite de pruebas (ingeniería normal).

No se tocó ningún parámetro de riesgo, modelo, estrategia, umbral ni gate; no
se contradijo ninguna decisión registrada (O-3 del informe deja constancia de la
tolerancia K=41/50 sin cambiarla).

---

## Registro — auditoría integral ronda `audit-2026-09-16` (2026-09-17)

Status: remediación cerrada, pendiente de verificación independiente ·
Result: 7 confirmados (HIGH 1, MEDIUM 4, LOW 2) → 6 corregidos + 1 mitigado
(AUD-004) · Loop: `audit.md` · Skills: `full-audit` (0–3) → `audit-remediation`
(4–5) · Owner: sesión principal `claude-opus-5` · Autorización: «Sí, hazlo»
sobre todos los confirmados, incluido commit+push.

Routing: diagnóstico no orquestado (validación por segundo método en la misma
sesión). **Escalado a `fable`** (`Agent`, `model: "fable"`) para la revisión
independiente de AUD-001, clase «parámetro de modelo» (probabilidad servida de
las líneas asiáticas de cuarto): 0 defectos, barrido de 18.432 combinaciones,
1 sugerencia menor aplicada (`is_quarter_line` compartido) y 1 hallazgo
adyacente sin ticket (`normal_margin_probs`, Δ ≤ 0,25 pp). AUD-005 se resolvió
en la variante «aviso» para no contradecir la decisión registrada `9dfb4cc`;
cablear el line shopping queda como decisión del operador. Ningún parámetro
de riesgo, umbral ni gate cambió.

Commits: `f93bdc1`, `4f06b4f`, `31cfdb0` (merge) · push `a2ee66c..31cfdb0` ·
CI run 35224249563. Producción (`C:\dev\3`) sigue en `a2ee66c`: `git pull`
pendiente del operador. Entregables en `audit/latest/`.

---

## Registro — auditoría diaria 2026-09-17 (loop `04-daily-audit`)

Status: closed · Result: DEGRADED · Loop: `04-daily-audit.md` · Skill:
`daily-audit` · Owner: sesión principal `claude-opus-5` (sin escalado: lectura
y medición, ningún parámetro tocado).

Comandos y códigos: tareas del Programador hoy — `SQP_Diario_Completo_Cdev`
12:00:01 rc=0, `SQP_Dashboard_Cdev` 12:10 rc=0, `SQP_Capture_Close_Cdev` 21:00
rc=0, `SQP_Validate_OOS_Cdev` 00:00 rc=0 (`Get-ScheduledTaskInfo`). Cálculo
propio: `scratchpad/daily_audit_20260917.py` (rc=0) con las definiciones
canónicas `load_all_settled`/`graded_in_window` (`sqp.audit.report`),
`decision_prob` (`sqp.evaluation.labels`) y `sqp.calibration.metrics`.

Artefactos leídos (todos presentes, legibles y generados hoy 12:01–12:09):
`data/bets/audit_20260917.md`, `segment_diagnostics_20260917.md`,
`segment_diagnostics_latest.csv`, `prediction_gate.json` (48 cortes, 0
habilitados, min_n=300), `degradation_pause.json` (11 mercados en pausa),
`clv_gate.json`, `data/output/pipeline_health.json` (status OK).

Cohorte congelada: liquidado hoy (`settled_at` 2026-09-17) → 27 filas: 25
graduadas (6 win / 19 loss), 2 void, 0 con stake > 0. Partidos del 14–15/09
(24) más 3 rezagados del US Open (4–5/09). Sin liquidaciones el 15 ni el 16/09
(producción restaurada el 16/09 20:35; KI-050), sin picks pendientes de
partidos ya jugados en el `ServedStore`.

Métricas (probabilidad de decisión): global n=25 hit 0,240 vs punto de
equilibrio 0,350 (−11,0 pp), p_est media 0,392 → gap −0,152, Brier 0,2237 vs
mercado 0,2002, log loss 0,637, ECE 0,210, ROI plano −23,4 %. Ventanas móviles
por fecha de partido: 7d n=256 gap −0,137 Brier 0,2257/0,2051; 30d n=699 gap
−0,122; 60d n=1047 gap −0,097 Brier 0,2190/0,2061 ECE 0,098. Ningún segmento
liga|mercado ni banda de hoy alcanza n≥15.

Limitación (DEGRADED): todos los segmentos del día están por debajo de
`n >= 15` (`segments.py`); solo el agregado es evaluable. `logs/` no legible
desde la sesión (deny del clasificador): no se inspeccionó el log de
liquidación, se verificó por `ServedStore.pending` y `LastTaskResult`.

Derivado al loop 05 (sin concluir): `tennis_wta_guadalajara_open|h2h` 0/8 con
p_est 0,392 y Brier mercado 0,097 (patrón de sobreconfianza en underdogs de
tenis ya flagueado en 60d en 5 torneos); `mlb` 0/4, `nfl` 0/2.

Tarea del 18/09 (líneas de cuarto de fútbol tras AUD-001): 0 spreads de
fútbol generados desde el 16/09 con resultado; no evaluable todavía.

Next decision: ninguna acción de gate, pausa ni calibrador (prohibidas sin
aprobación; ninguna la requiere hoy). Codex con cuota (operador, 17/09):
reactivar el review gate y repetir el cross-review de
`codex/feature-signal-shadow` — tarea aparte de este loop.

---

## Registro — auditoría integral ronda `audit-2026-09-18` (2026-09-18)

Status: remediación aplicada, pendiente de verificación independiente ·
Result: 7 confirmados (MEDIUM 4, LOW 3; P0/P1: 0) → 6 corregidos + 1 parcial
(AUD-004: código sí; host bloqueado por elevación) · Loop: `audit.md` ·
Skills: `full-audit` (0–3) → `audit-remediation` (4–5) · Owner: sesión
principal `claude-opus-5` · Autorización: «si, hazlo» · Segunda opinión: SÍ
(auditor OpenAI, `openai/REPORT.md`, 3 hallazgos; Claude 4; conjuntos disjuntos).

Routing: diagnóstico y remediación en `claude-opus-5` sin subagentes;
`fable` (parámetro `model` de `Agent`, agente `independent-code-reviewer`) para
revisar AUD-003, clase «cambiar el contrato de un artefacto persistido /
parámetro de modelo» (registro live de calibración + promoción). Decisión
del ejecutor bajo la orden global: DEMOVER `mlb_h2h_pergame` (cero cambio en
lo servido), no adoptar; la adopción bajo `mlb_h2h` sigue en `Tareas.md:104`.
Ningún umbral de riesgo/gate cambiado; no se contradijo ninguna decisión
registrada. Bloqueado: `wevtutil sl Microsoft-Windows-TaskScheduler/Operational
/e:true` (elevación; clasificador denegó) — lo ejecuta el operador.

Criterios de aceptación (verification-gate): por ID en
`audit/latest/CHANGES.md`; evidencia en `audit/latest/VALIDATION.md`; estado en
`audit/latest/STATUS.md`. Validación global: suite completa, ruff, mypy,
`git diff --check`, prompts sincronizados. Siguiente: verificación
independiente (`audits/prompts/verificar-remediacion.md`).

---

## Registro de enrutamiento — pre-registro del suelo de precio (2026-09-19)

Sesión principal en `claude-opus-5`, sin despachos. Pregunta del operador
(«¿qué falta para cumplir el objetivo? elige las mejores opciones») resuelta
**midiendo primero**: la ventana del pre-registro del 2026-08-25 alcanzó la
muestra (824 picks / 424 eventos) y se ejecutó una sola vez con el diseño
congelado (`scripts/research/measure_price_floor_preregistration.py`,
resultado en `docs/research/2026-09-19-resultado-suelo-de-precio.md`).

- Clase de la medición: lectura de datos guardados; ningún parámetro de
  riesgo, modelo, umbral ni gate tocado; nada desplegado. No dispara escalado.
- Clase de la interpretación (primaria ACEPTA, contraprueba NO → no se adopta)
  y de la priorización estratégica que sale de ella: **estrategia**. Es
  materia del escalón `fable` según la REGLA DE DESPACHO. Queda registrada aquí
  como decisión provisional de la sesión `opus`, **pendiente de revisión en
  `fable` antes de que ninguna de sus consecuencias toque `configs/` o
  producción**. Ninguna lo hace hoy.

## Registro de enrutamiento — line shopping cableado como capa de ejecución (2026-09-19)

Orden del operador («Sí, hazlo», tras elegir el orden de frentes). Sesión
principal `claude-opus-5`. Clase de escalado: **cambiar el contrato de un
artefacto persistido** (`served_*.csv` y `candidates_*.csv` ganan
`execution_price`/`execution_book`; cierra AUD-005 del 17/09). Despacho
`Agent(model="fable")` para revisión independiente solo lectura del diff antes
del commit. No se toca ningún parámetro de riesgo, modelo, umbral ni gate:
`price_decimal`, no-vig, edge, selección, stake y liquidación siguen sobre la
mediana del consenso; `execution.books` queda vacío (default-deny).
Veredicto `fable`: **aprobar**, 0 defectos P0/P1/MEDIUM, 1 LOW cosmético (fallback
defensivo inalcanzable en `daily.py`, se conserva). Codex: sin hallazgos.
## Registro de enrutamiento — actualización del modelo principal a Opus 5.5 (2026-09-22)

Orden directa del operador: «Actualizar el modelo a claude 5.5». Owner: sesión
principal, corriendo en `claude-opus-5`. **Sin despachos ni subagentes.**

Clase de escalado aplicable: la tarea toca **parámetros de modelo** y
**contradice una decisión previa registrada** (`claude-opus-5` como modelo
principal, 2026-08-30) — dos de las cinco clases. No se escaló a `fable` porque
no hay margen de juicio que escalar: el operador fijó el destino y el único
trabajo de razonamiento era verificar el identificador y mover el candado
entero. Lo que sí se aplicó de la política es su lección explícita del
2026-09-03: **el dato se verificó contra la documentación viva**
(`platform.claude.com`, modelos y precios, 2026-09-22), no contra la tabla
cacheada de la skill `claude-api`, que marca Opus 5.5 como «launching».

Resultado de la verificación: `claude-opus-5-5` es el ID correcto ($4/$20 por
MTok, caché $0,20, 1M de contexto, 128K de salida, `effort` por defecto
`medium`, retirada no antes del 2027-09-22). La documentación oficial recomienda
*"start with Claude Opus 5.5 for most workloads"* y reserva Fable 5.1 para
*"demanding reasoning and long-horizon agentic work"*, que es exactamente la
separación punto-de-partida/techo que este proyecto ya tenía escrita. En esa
misma página **`claude-opus-5` ya figura como legacy**.

Alcance movido (candado de cuatro puntas, entero y en un acto): `settings.json`,
`.claude/automation/MODEL_ROUTING.md`, `docs/MODEL-ROUTING.md`,
`tests/test_claude_model_routing.py` y `scripts/validate_claude_model_routing.py`,
más el principio rector de `CLAUDE.md`. **No se movió el techo** (`claude-fable-5-1`),
ni el escalón de las rutas (`sonnet` por defecto; `opus`/`haiku` en sus
excepciones), ni la política de subagentes, ni el disparador de escalado.

Limitación declarada: editar `settings.json` **no** cambia el modelo de esta
sesión, que terminó en `claude-opus-5`. El valor nuevo rige en la siguiente
sesión, o antes con `/model claude-opus-5-5`. Tampoco se verificó por observación
a qué modelo resuelve hoy el alias `opus` del parámetro `model` de `Agent` (enum
`sonnet|opus|haiku|fable`): la regla 2 de despacho sigue pasando el alias, y
comprobar a qué resuelve exige la misma verificación por transcript que se hizo
con `fable` el 2026-09-04.

## Registro de enrutamiento — remediación de la ronda `audit-2026-09-23` (2026-09-23)

Orden del operador: ejecutar íntegramente `audits/prompts/corregir-auditoria.md`
(skill `audit-remediation`) sobre `audit/latest/FINDINGS.md` de la ronda
`audit-2026-09-23`. Alcance interpretado: **todos los confirmados**
(AUD-001…AUD-014), la única lectura de «íntegramente» que no deja IDs sin
tratar; se declara en `audit/latest/CHANGES.md`.

Owner: sesión principal en `claude-opus-5-5` (implementación). Clases de
escalado presentes: **gates de riesgo** (AUD-001/002/005/013), **ledger y
settlement** (AUD-003/004/012), **parámetros de modelo** (AUD-007) y **cifras
publicables** (AUD-006/008). Por la regla 1 de despacho, la **revisión
independiente** del diff se despacha con `model: "fable"` (subagente
`independent-code-reviewer`), mismo patrón que la ronda del 2026-09-13. No se
toca ningún umbral, pre-registro, registro productivo del gate ni dato de
`data/`.

## Registro de enrutamiento — verificación independiente de `audit-2026-09-23` (2026-09-24)

Orden del operador: ejecutar íntegramente `audits/prompts/verificar-remediacion.md`. La sesión principal (`claude-opus-5-5`) fue la IMPLEMENTADORA, así que no puede verificarse a sí misma. La verificación se despachó a un agente nuevo `independent-code-reviewer` con `model: "fable"` (regla 1 de despacho: gates, ledger, calibración, cifras publicables), de solo lectura sobre `1a0f746`. La sesión principal solo redactó `VERIFICATION.md`, `STATUS.md` y el manifest a partir de su evidencia.

Veredicto: **NO APTO** (AUD-003, P1, bloqueado). 12 verificados-corregidos, 1 mitigado, 0 regresiones. Nuevo preexistente: KI-058.

Incidencia del verificador: hasta 7 llamadas reales a `codex review` sobre un repo vacío del scratchpad, por un PATH mal formado; puede haber consumido cuota de Codex.

## Registro de enrutamiento — activación del abridor MLB (2026-09-26)

Orden del operador: «Activa el factor del abridor en MLB». Cae en DOS clases del disparador: (2) parámetro de modelo y (4) contradice decisiones registradas (2026-06-12, 2026-06-16). **Fallo de despacho:** la sesión principal (`claude-opus-5-5`) midió, decidió e implementó (`49a6181`) sin escalar ni registrar aquí. La revisión cruzada de Codex (stop hook) no sustituye al escalón Fable. Corrección a posteriori: revisión independiente del commit despachada con `model: "fable"` (subagente `independent-code-reviewer`), solo lectura.

## Registro de enrutamiento — re-medición del descanso/back-to-back en basket (2026-09-26)

Orden del operador: repartir por modelo según complejidad y fortaleza. Plan de despacho:
1. **Haiku**: inventario acotado (implementación del descanso, evidencia del 2026-06-22, datos disponibles). Ruta `documentation`/lookup.
2. **Fable** (regla 1: parámetro de modelo + contradice la decisión del 2026-06-22): redacta el pre-registro.
3. **Sonnet** (regla 2, ingeniería normal): scripts de medición según el pre-registro.
4. **Fable**: revisión del código antes de ejecutar e interpretación del veredicto (cifras publicables).
5. **Opus** (principal): orquesta, ejecuta la corrida única, commitea y comunica.

## Cola aprobada por el operador (2026-09-26)

1. Descanso/back-to-back en basket (en curso: inventario Haiku).
2. **Batería de los 10 ajustes de la capa de features** (aprobada: «Sí, añade la batería a la cola»). Un solo pre-registro con corrección de Holm; descarte razonado de los redundantes (1 rest, 5 streak, 6-7 off_def) escrito ANTES de medir; mismos criterios que el clima (walk-forward, margen 0,002, control de intercepto). Reparto: Haiku inventario, Fable pre-registro y veredicto, Sonnet scripts, Opus orquesta.

## Registro de enrutamiento — candado pre-commit de revisión Fable (2026-09-26)

Orden del operador: «Sí, implementa el candado pre-commit». Cambio de política de modelos aprobado explícitamente. Reparto: diseño en Opus (principal); implementación de hook, config y tests en **Sonnet**; revisión del código y del diseño en **Fable** ANTES de cablearlo en `settings.json` y commitear; cableado, documentación en `MODEL_ROUTING.md` y commit en Opus.

FABLE-REVIEW: 2026-09-26 | veredicto: APTO PARA CABLEAR (2.ª ronda; 1.ª APTO CON CAMBIOS, 10 cambios aplicados + huecos A y B) | rutas: .claude/hooks/fable_gate.py, .claude/automation/fable-gate.json, tests/test_fable_gate.py
FABLE-REVIEW: 2026-09-26 | veredicto: APTO CON CAMBIOS aplicados (script del descanso; enmiendas E1-E6) | rutas: scripts/research/measure_rest_basketball.py, docs/research/2026-09-26-preregistro-descanso-basket.md
FABLE-REVIEW: 2026-09-26 | veredicto: APTO CON CONDICIONES (activar rest_points_per_day=0.795 solo nba, tras los addenda previos en gate K=52 y «el modelo manda»; rest_days_coef en 0; recalibrar nba_h2h/nba_spreads; re-medir margin_sigma; test de back-to-back) | rutas: configs/leagues/ratings.yaml, docs/research/2026-09-26-resultado-descanso-basket.md

## Registro de enrutamiento — «Clima y Parque» (2026-09-26, tarde)

Orden del operador: «Clima y Parque. Continúa». Reapertura del clima MLB con una forma funcional DISTINTA: viento según la orientación del estadio (a favor o en contra del jardín central). Reparto: **Haiku** viabilidad (dirección del viento en la Previous Runs API y rumbos home→CF con fuente); **Fable** pre-registro (incluye si reutilizar la muestra 2024-26 ya usada en el test rechazado es admisible y cómo se corrige la multiplicidad frente a ese test); **Sonnet** scripts; **Fable** revisión y veredicto; **Opus** orquesta y commitea. Push de los 17 commits de la sesión hecho (`921572d..3648b17`), CI `36266777058`.

## Cola aprobada — features por deporte (2026-09-26, «Sí, házlo»)

1. **NHL: portero titular + calidad del portero** (en curso). Reparto: Haiku viabilidad (API NHL, históricos, sello temporal del anuncio del portero) → Fable pre-registro (disponibilidad en el corte del pick: el run es a las 12:00 y el portero se confirma horas antes del partido) → Sonnet ingesta y scripts → Fable revisión y veredicto → Opus orquesta y commitea.
2. **NBA: pace, ratings ofensivo/defensivo y lesionados** (octubre).
3. **MLB: bullpen** (preparado para 2027).
En paralelo: barrido de nombres de equipo (Hawái NCAAF) y orientación de estadios («Clima y Parque»). Sigue en cola: batería de los 10 ajustes.
FABLE-REVIEW: 2026-09-26 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas) | rutas: docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-09-26 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas; test en 2027) | rutas: docs/research/2026-09-26-preregistro-clima-parque-mlb.md
FABLE-REVIEW: 2026-09-26 | veredicto: APTO (sustitución completa en la vía de respaldo, abstención conservada, idéntico sin alias, sin re-liquidación, sin fusiones en los datos; huecos de test menores no bloqueantes) | rutas: configs/leagues/team_aliases.yaml, configs/venues.yaml, src/sqp/settlement/runner.py, src/sqp/backtesting/roi_engine.py, tests/test_team_alias_mismatches.py, tests/settlement/test_team_alias_settlement.py
FABLE-REVIEW: 2026-09-26 | veredicto: APTO CON CONDICIONES (código apto; (a) y (c) de la Enmienda 1 corregidos con el texto indicado; lanzar el backfill con --end 2026-09-25 fijo) | rutas: src/sqp/storage/, src/sqp/providers/nhl_api.py, src/sqp/providers/espn_goalies.py, src/sqp/sports/nhl_goalie_matching.py, src/sqp/pipeline/goalie_backfill.py, src/sqp/pipeline/goalie_probables_capture.py, docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-09-26 | veredicto: APTO | rutas: docs/research/2026-09-25-repreregistro-gate-k52.md, docs/research/2026-08-26-preregistro-el-modelo-manda.md
FABLE-REVIEW: 2026-09-26 | veredicto: APTO | rutas: src/sqp/pipeline/goalie_backfill.py, scripts/backfill_goalies_nhl.py
FABLE-REVIEW: 2026-09-26 | veredicto: APTO (limitaciones: Start-Process y git -c alias, evasión deliberada; bloqueo de más con '| git commit' citado) | rutas: .claude/hooks/fable_gate.py, tests/test_fable_gate.py
FABLE-REVIEW: 2026-09-27 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas) | rutas: docs/research/2026-09-27-preregistro-bateria-ajustes.md
FABLE-REVIEW: 2026-09-27 | veredicto: APTO (fusionar; reanudar solo con el proceso actual terminado y el mismo rango) | rutas: src/sqp/pipeline/goalie_backfill.py, scripts/backfill_goalies_nhl.py
FABLE-REVIEW: 2026-09-27 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas) | rutas: docs/research/2026-09-27-preregistro-descanso-nhl.md
FABLE-REVIEW: 2026-09-29 | veredicto: APTO (fusión; modo completo condicionado a enmienda de recuentos/hash y --pre regenerado) | rutas: src/sqp/models/rest.py, src/sqp/sports/adapters.py, scripts/research/measure_rest_nhl.py, tests/test_rest.py, tests/test_rest_poisson_adapter.py, tests/test_measure_rest_nhl.py
FABLE-REVIEW: 2026-09-29 | veredicto: APTO (enmienda de recuentos prescrita por Fable antes del modo completo) | rutas: docs/research/2026-09-27-preregistro-descanso-nhl.md
FABLE-REVIEW: 2026-09-29 | veredicto: APTO (RECHAZA verificado; efecto real bajo el margen, concentrado en back-to-back; rest_elo_per_day sigue en 0) | rutas: docs/research/2026-09-29-resultado-descanso-nhl.md
FABLE-REVIEW: 2026-09-29 | veredicto: APTO (enmienda 2 redactada por Fable antes de implementar la medición) | rutas: docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-09-29 | veredicto: APTO (decisiones del operador sobre opciones propuestas por Fable en la enmienda 2) | rutas: docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-09-30 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas) | rutas: docs/research/2026-09-29-preregistro-tilt-nhl.md
FABLE-REVIEW: 2026-09-30 | veredicto: APTO CON CAMBIOS aplicados (SystemExit de la paridad del informe 4 capturado con test; explicación del EE §9.2 corregida) | rutas: scripts/research/measure_tilt_nhl.py, tests/test_measure_tilt_nhl.py
FABLE-REVIEW: 2026-09-30 | veredicto: APTO (enmienda de recuentos y procedencia prescrita por Fable antes del modo completo) | rutas: docs/research/2026-09-29-preregistro-tilt-nhl.md
FABLE-REVIEW: 2026-09-30 | veredicto: APTO CON CONDICIONES (activar tilt_scale=0.439 solo nhl tras addenda previos; sin recalibración; enmiendas de base del portero y la batería; test de activación) | rutas: configs/leagues/ratings.yaml, docs/research/2026-09-30-resultado-tilt-nhl.md
FABLE-REVIEW: 2026-09-30 | veredicto: APTO (addenda de régimen prescritos por Fable en el dictamen de activación del tilt NHL) | rutas: docs/research/2026-09-25-repreregistro-gate-k52.md, docs/research/2026-08-26-preregistro-el-modelo-manda.md
FABLE-REVIEW: 2026-09-30 | veredicto: APTO (enmienda 3 redactada por Fable tras activar tilt 0,439) | rutas: docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-10-01 | veredicto: APTO (decisión del operador sobre la opción de la enmienda 3; alternativa equivalente a la suspensión de tareas) | rutas: docs/research/2026-09-26-preregistro-portero-nhl.md
FABLE-REVIEW: 2026-10-01 | veredicto: APTO | rutas: src/sqp/features/rest_form.py, src/sqp/pipeline/probabilities.py, tests/test_rest_form_index_equivalence.py
FABLE-REVIEW: 2026-10-02 | veredicto: APTO CON CAMBIOS (revision de solo lectura del pre-registro; los 12 hallazgos los aplico Fable antes del commit; codigo _unique_settled_picks: APTO, H1-H3 aplicados) | rutas: docs/research/2026-10-02-preregistro-brecha-tier-a.md, src/sqp/audit/report.py
FABLE-REVIEW: 2026-10-03 | veredicto: APTO (script measure_tier_a_gap tras dos rondas: APTO CON CAMBIOS 11 hallazgos aplicados, APTO con 3 bajos aplicados; Addendum 1: APTO CON CAMBIOS, 2 correcciones de texto aplicadas, solo anade) | rutas: scripts/research/measure_tier_a_gap.py, tests/research/, docs/research/2026-10-02-preregistro-brecha-tier-a.md, docs/research/2026-10-02-preregistro-brecha-tier-a.contar.jsonl

## Registro de enrutamiento — script de la batería de ajustes (2026-10-08)

Orden del operador: «Sí, arranca con el punto 3» (escribir `scripts/research/measure_adjustment_battery.py` según `docs/research/2026-09-27-preregistro-bateria-ajustes.md`). La base del pre-registro (`f9658ce`) quedó desfasada por `c390c2f` (tilt NHL 0,439); el dictamen Fable del 2026-09-30 exige enmendar la base de la batería. Reparto: **Fable** redacta la enmienda de base (clase: pre-registro) → **Sonnet** implementa script y tests (`--pre`, `--parity-only`, modo completo; sin ejecutar el modo completo ni `--pre` oficial) → **Fable** revisa el código ANTES del commit → **Opus** orquesta y commitea (sin push). El modo completo NO se ejecuta en esta tarea.
- Decisión del operador (2026-10-08): «Sí, mantén la instantánea con --data-root». Queda aprobada la extensión a la batería del mecanismo de instantánea de entradas (Enmienda 1, propuesta por Fable).
FABLE-REVIEW: 2026-10-08 | veredicto: APTO (ronda 2 + correcciones de orden de captured_lines, ingesta del 27 y data-root fuera de data/; pre-registro: Enmiendas 1 y 2) | rutas: scripts/research/measure_adjustment_battery.py, tests/research/test_measure_adjustment_battery.py, docs/research/2026-09-27-preregistro-bateria-ajustes.md
- Cierre (2026-10-08): commit `8117d9c`, sin push. `--pre` y modo completo NO ejecutados; pendiente la decisión del operador sobre `audit/model_vs_market_20261001.md` (bloquea `--pre`).
FABLE-REVIEW: 2026-10-09 | veredicto: APTO (Enmienda 3 redactada por Fable: NHL +12 y MLB +13 atribuidas, dedupe de 15 gamePk MLB; codigo del filtro: APTO, 3 hallazgos no bloqueantes; ncaab -31 y wncaab -95 descartes del mismo dia en el informe 9 a declarar en el resultado) | rutas: scripts/research/measure_adjustment_battery.py, tests/research/test_measure_adjustment_battery.py, docs/research/2026-09-27-preregistro-bateria-ajustes.md
FABLE-REVIEW: 2026-10-09 | veredicto: APTO CON CONDICIONES (resultado valido, sin fuga ni defecto E10; 4 ACEPTA en totales nba/nfl adj4 y adj10 no activables: el informe 7 empeora el log loss con la linea del mercado; via propuesta: pre-registro de recencia del adaptador de totales, decision del operador) | rutas: docs/research/2026-10-09-resultado-bateria-ajustes.md

## Registro de enrutamiento — pre-registro de recencia del adaptador de totales (2026-10-09)

Orden del operador: «Sí, que Fable redacte el pre-registro de recencia». Fable redacta (clase: pre-registro, reabre la decisión NHL del 2026-08-18); el operador aprobó las 6 recomendaciones de la §17 («Aprobar todas (Recommended)»). Siguiente: script `measure_totals_recency.py` (Sonnet) con revisión Fable antes del commit, pendiente de orden.
FABLE-REVIEW: 2026-10-09 | veredicto: APTO (pre-registro redactado por Fable; decisiones del operador resueltas) | rutas: docs/research/2026-10-09-preregistro-recencia-totales.md
FABLE-REVIEW: 2026-10-09 | veredicto: APTO CON CAMBIOS aplicados (ronda 1: F1-F6 aplicados por Sonnet; ronda 2: F1-F6 conformes, G1-G3 aplicados por Opus tal como los prescribio Fable, 73 tests; Enmienda 1 (a)-(p) y addendum (q) redactados por Fable, solo anaden) | rutas: scripts/research/measure_totals_recency.py, tests/research/test_measure_totals_recency.py, docs/research/2026-10-09-preregistro-recencia-totales.md

## Registro de enrutamiento — fase H de recencia (2026-10-10)

Orden del operador: «Continúa» (tras «el siguiente paso, cuando lo ordenes: --pre y fase H»). Opus ejecutó --pre (pre_H_f315f4c.json) y la fase H única (H_f315f4c.json, sha256 32a0e9e3f3a216c9dfff41fc7f0d33be8df38954ea3e23f063d1cf205348b1ac) sobre C:\dev\3\snapshots\bateria-ajustes-20261008, HEAD f315f4c, sin commits entre ambos. Fable redacta y verifica el informe (clase: veredicto, cifras publicables).
FABLE-REVIEW: 2026-10-10 | veredicto: APTO (ejecucion valida; NBA y NFL ACEPTA, NHL RECHAZA por H5; procedencia y Holm recalculados; nada se activa hasta la fase M) | rutas: docs/research/2026-10-10-resultado-recencia-totales-H.md

## Registro de enrutamiento — KI-071 (2026-10-11)

Diagnóstico de Opus (solo lectura). Implementación de Sonnet en src/sqp/settlement/runner.py, con 4 tests nuevos: pytest completo 3088 passed, ruff y mypy limpios. Revisión de Fable antes del commit: APTO CON CAMBIOS; los cambios eran documentales (alcance real de 9 identidades y 18 filas en KI-071; riesgos residuales de tenis y del lookback) y ya están aplicados en known-issues.md. La reparación del ledger queda pendiente de autorización del operador.
FABLE-REVIEW: 2026-10-11 | veredicto: APTO CON CAMBIOS aplicados (documentales en KI-071) | rutas: src/sqp/settlement/runner.py, tests/settlement/test_superseded_picks.py
FABLE-REVIEW: 2026-10-13 | veredicto: APTO CON CAMBIOS aplicados (pre-registro peso del mercado por segmento redactado por Fable y aprobado por el operador; addendum de unidad de MM con los 3 cambios de la revision: exclusion por pick entero, DE de potencia no re-estimada, transparencia de la cota por convexidad) | rutas: docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md, docs/research/2026-08-26-preregistro-el-modelo-manda.md, scripts/model_vs_market_report.py
FABLE-REVIEW: 2026-10-13 | veredicto: APTO (addendum (2) de ejecucion de MM redactado por Fable; literales de penalizacion verificados contra Settings.load por Opus: 0,35 / 0,06+0,02 / books<2 +0,015; ningun criterio cambiado) | rutas: docs/research/2026-08-26-preregistro-el-modelo-manda.md
FABLE-REVIEW: 2026-10-13 | veredicto: APTO CON CAMBIOS (revision Fable del script measure_segment_market_weight: bloqueante 2 exige fijar el formato de la tabla de regimen de s antes de T0; addendum (1) redactado por Opus con el formato y la precedencia de la columna market_shrink; no cambia criterios) | rutas: docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md
FABLE-REVIEW: 2026-10-13 | veredicto: APTO CON CAMBIOS (columna market_shrink: valor identico a _decision_probability en todas las ramas, migracion sin riesgo nuevo, ningun consumidor roto; aplicado test MARKET_SHRINK=0; pendientes no bloqueantes: test de la rama sin no-vig y migracion con el orden real de cabecera 9d6fe725) | rutas: src/sqp/storage/served_store.py, src/sqp/pipeline/daily.py, tests/test_served_market_shrink.py
