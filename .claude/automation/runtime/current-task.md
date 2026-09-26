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
