# Integración Claude ↔ Codex en este proyecto

---

## ¿Qué es la integración?

Claude y Codex son dos instancias de modelos distintos que actúan como **revisores independientes** del mismo cambio de código. El sistema garantiza que ninguno puede aprobar un cambio sin que el otro lo haya revisado sobre exactamente el mismo árbol de trabajo.

Hay **tres formas**, y solo una de ellas se activa sin que nadie la invoque:

| # | Forma | Se activa |
|---|---|---|
| 1 | Flujo manual de implementación (Opus→Codex) | Cuando tú lo pides |
| 2 | Cross Review Protocol V2 (`scripts/ai/`) | `/cross-review` |
| 3 | **Centinela automático** (`.claude/hooks/`) | **Sola**, al tocar código de riesgo |

La Forma 1 es Claude usando a Codex como implementador. Las Formas 2 y 3 son lo
contrario: Codex revisando a Claude. La Forma 3 es la que protege el código del
dinero en el día a día, y es la única que no depende de que alguien se acuerde
de invocarla.

---

## Forma 1: Flujo manual de implementación (Opus → Codex)

```
Opus: PLAN.md  →  Codex implementa  →  Sonnet revisa  →  commit
```

**Quién hace qué:**

| Actor | Rol | Herramienta |
|---|---|---|
| Claude (Opus) | Decide qué cambiar, escribe el plan | Escribe `PLAN.md` |
| Codex | Ejecuta los cambios en los archivos | `mcp__codex__codex` |
| Claude (Sonnet) | Lee el diff y verifica | Lee `REVIEW.md` |

**Notas:**
- `PLAN.md` y `REVIEW.md` son artefactos **temporales y sin versionar** — se sobrescriben cada ciclo. Cerrar el ciclo anterior antes de escribir uno nuevo.
- Codex opera en el mismo worktree local; no tiene acceso a secretos ni a servicios de pago.
- Claude (Sonnet) nunca aprueba un cambio sin leer el diff real.

---

## Forma 2: Cross Review Protocol V2 (revisión formal)

```
Claude revisa el diff  +  Codex revisa el mismo diff  →  consenso JSON
```

**Flujo:**
1. El launcher congela el árbol de revisión (`review_tree`) en un snapshot inmutable.
2. Claude y Codex reciben exactamente el mismo snapshot — ninguno ve el árbol en vivo.
3. Cada revisor emite un veredicto JSON: `APPROVE`, `REQUEST_CHANGES`, o `BLOCK`.
4. El launcher corre `pytest`/`ruff`/`mypy` y estampa los resultados reales en el JSON — un revisor no puede declarar tests pasados si no pasaron.
5. El consenso requiere que ambos aprueben; uno solo no es suficiente.

**Cuándo usarlo:** cambios de riesgo medio-alto — nuevos modelos, cambios de calibración, modificaciones al pipeline de predicción.

**Cómo invocarlo:** `/cross-review`, definido en `.claude/commands/cross-review.md`. No es un skill.

---

## Forma 3: Centinela automático (la única que se activa sola)

```
tocas código de riesgo  →  se arma el centinela  →  al cerrar el turno Codex
revisa el diff  →  su veredicto vuelve al modelo y bloquea el cierre
```

Nadie la invoca. Vive en `.claude/settings.json` → `hooks` y consta de dos piezas:

| Hook | Evento | Qué hace |
|---|---|---|
| `.claude/hooks/mark-crossreview-pending.sh` | `PostToolUse`, matcher `Edit\|Write\|Bash` | Si el fichero tocado cae en el ámbito vigilado, deja el centinela `.claude/.crossreview-pending` |
| `.claude/hooks/crossreview-on-stop.sh` | `Stop` (sin matcher, timeout 600 s) | Si el centinela existe, ejecuta `codex review` y devuelve `exit 2`: el turno no puede cerrarse hasta atender o **refutar** cada hallazgo |

**Ámbito vigilado — deliberadamente estrecho:** `configs/`, `src/sqp/risk/` y
`src/sqp/calibration/`. Es el código donde un error cuesta dinero. A diferencia
de `mark-tests-pending`, este hook **no** usa la red de seguridad `--with-git`:
sobre-disparar tests es gratis, sobre-disparar una revisión de pago no lo es.
Solo se atiende a lo que el comando **nombra**.

**Qué revisa.** El hook corre en el `Stop`, y para entonces el trabajo del turno
puede estar ya commiteado. El alcance se elige en cascada:

1. `--uncommitted` si queda algo sin commitear **dentro del ámbito vigilado**;
2. si no, `--base <upstream>` — los commits por delante del upstream, es decir
   lo que todavía no ha pasado por ninguna puerta;
3. si no hay upstream (rama local nueva, clon sin remoto), `--commit HEAD`.

Las instrucciones del revisor **no viajan en el prompt**: viven en `AGENTS.md`,
que Codex carga solo. Los selectores de alcance y el `[PROMPT]` posicional son
mutuamente excluyentes en la CLI, y duplicar las instrucciones es justo la
deriva entre copias que este repositorio lleva meses pagando.

**Distingue hallazgos de fallos de entorno.** `codex review` puede salir con
código 0 habiendo abortado, así que se comprueban las dos vías: el código de
salida y los patrones conocidos (`usage limit`, `Review was interrupted`,
`failed to refresh available models`, rate limit, 401, `ECONNREFUSED`). Ante un
fallo de entorno el aviso lleva un encabezado **distinto** — «la revisión
cruzada NO se ejecutó» —, **no bloquea** (`exit 0`, porque el modelo no puede
arreglar una cuota agotada) y **repone el centinela**: la revisión queda
aplazada al turno siguiente, nunca saltada en silencio.

**Qué binario usa.** El `codex` del `PATH`, vía `command -v codex` — y desde el
2026-09-09 **la Forma 2 resuelve por la misma vía**. No siempre fue así: el
lanzador fijaba `%APPDATA%\npm\codex.cmd` y las dos mitades de la integración llevaban un mes
revisando con instalaciones distintas (`0.147.0` contra `0.153.4`). El fallo era
asimétrico —desinstalar el shim de npm rompía la Forma 2 y dejaba la Forma 3 en
pie, así que la integración *parecía* viva con la mitad muerta— y sobrevivió
porque `codex_command()` no tenía ni una prueba. Hoy el shim sigue siendo el
respaldo cuando el `PATH` no da nada, pero ya no manda, y un test lee **los dos
ficheros** para que ninguna de las dos mitades pueda volver a fijar una ruta.
Ver `KI-046`.

**Historial, porque la lección importa.** Esta forma estuvo **rota durante meses
sin que nadie lo supiera**: los patrones emparejaban con barra normal y en
Windows el harness entrega la ruta con contrabarra, así que no disparaba nunca
(`KI-031`, resuelto el 2026-09-05). Debajo escondía una invocación inválida que
tampoco se había ejecutado jamás. Después vino que un fallo de infraestructura
se presentara bajo el encabezado de hallazgos (`KI-035`, 2026-09-06) y que el
matcher filtrara por nombre de herramienta, de modo que editar con `sed` o un
heredoc no armaba nada (`AUD-MED-002`, 2026-09-07). Un `PASS` es peor que no
ejecutar la revisión: se lee como «revisado y limpio».

**Está funcionando.** Primer disparo automático confirmado el 2026-09-06 sobre
un turno que editó `src/sqp/calibration/`. El 2026-09-08 encontró que el banner
de frescura del tablero solo se evaluaba al generar el HTML —y `report_latest.html`
es estático, así que el aviso no podía aparecer nunca justo en la parada que
existe para señalar—. La mitad de aquel arreglo era decorativa, y lo dijo Codex,
no Claude.

---

## Configuración que puedes cambiar

| Qué | Dónde | Cómo |
|---|---|---|
| Modelo activo del proyecto | `.claude/settings.json` → `"model"` | Edit directo o `/model opus` en sesión |
| Modelo global por defecto | `~/.claude/settings.json` | Edit directo |
| Permisos de comandos | `.claude/settings.json` → `permissions.allow/deny` | Edit directo o skill `update-config` |
| Skills del proyecto | `.claude/skills/<nombre>/SKILL.md` | Crear/editar archivos markdown |
| Hooks automáticos | `.claude/settings.json` → `hooks` | Edit directo o skill `update-config` |
| Loops operacionales | `.claude/loops/` y `.claude/loops/quant/` | Editar los `.md` correspondientes |
| Backlog autónomo | `.claude/automation/backlog.md` | Añadir filas con status `ready` |
| Política de autonomía | `.claude/automation/autonomy-policy.md` | Editar con cuidado — rige lo que Claude puede hacer sin aprobación |

---

## Cuándo usar cada forma

| Situación | Forma recomendada |
|---|---|
| Implementar un feature planificado | Forma 1 (Opus→Codex) |
| Corregir un bug menor | Claude solo (Sonnet) |
| Tocar `configs/`, `src/sqp/risk/` o `src/sqp/calibration/` | Forma 3 — automática, no hay nada que hacer |
| Cambio en calibración o modelo | Forma 2 (Cross Review); la Forma 3 se dispara además sola |
| Auditoría completa del sistema | `/full-audit` con subagentes especializados |
| Incidente en producción | Skill `quant-incident` → aprobación humana |

---

## Flujo Opus → Codex paso a paso

1. Abre una sesión con Claude (Opus recomendado para el plan).
2. Claude escribe `PLAN.md` con las tareas numeradas.
3. Dile a Codex: *"implementa el plan en PLAN.md"*.
4. Codex modifica los archivos; escribe `REVIEW.md` con el resumen.
5. Claude (Sonnet) lee `REVIEW.md` y el diff real (`git diff`).
6. Si está conforme, Claude hace el commit (requiere aprobación explícita).
7. Borra `PLAN.md` y `REVIEW.md` al cerrar el ciclo.
