# Current Task

Status: closed
Result: DEGRADED (los tres IDs corregidos y verificados; el run diario programado
se ejecutó a las 11:01 sobre el árbol a medio editar y quedó incompleto — sin
capital en riesgo, pero requiere decisión del operador)
Primary loop: `audit.md`
Skill: `full-audit` (fase 4: corrección)
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`) + 3 subagentes escalados a `claude-fable-5`
Date: 2026-09-02

## Objective

Corregir los hallazgos que el operador autorizó por ID tras la auditoría
integral del 2026-09-02: **AUD-MED-006 (#4)**, **AUD-HIGH-001 (#5)** y
**AUD-HIGH-003 (#9)** en la primera tanda; **AUD-HIGH-002 (#1, void de tenis)**
autorizado después. Los cinco restantes (#2 lock, #3 rendimiento de cuotas,
#6 degradación, #7 config, #8 cableado de hooks) **no** están autorizados.

`AUD-HIGH-002` NO se escaló a Fable pese a que la clase 5 del disparador nombra
`settlement`: no diseña criterio nuevo, replica un guard ya aprobado, revisado y
con tests (`scores_trusted`, N-A-3) en la rama que se lo dejó fuera, con el fallo
ya reproducido. Decisión declarada al operador antes de ejecutar, con la opción
de redespachar.

`AUD-HIGH-001` es el mismo problema que la iteración del 2026-08-31 registró
como Grupo B / `N-A-5` ("normalizar la duplicación en el punto de lectura
compartido"), que quedó esperando decisión del operador. Esa decisión llegó hoy.

## Registro de escalado de modelo (REGLA DE DESPACHO, regla 1)

Los tres IDs caen en las clases del disparador, así que se despachan con
`model: "fable"` pese a que la ruta `full-audit` es `opus`. Registro exigido por
`.claude/automation/MODEL_ROUTING.md`:

| ID | Clases del disparador | Modelo |
|---|---|---|
| AUD-MED-006 (#4) | 3 (cifras publicables: ROI de backtest) | `claude-fable-5` |
| AUD-HIGH-001 (#5) | 2 (parámetros de modelo/gate), 3 (ECE/Brier publicables), 5 (contrato de staging/promoción) | `claude-fable-5` |
| AUD-HIGH-003 (#9) | 1 (irreversible: autoriza stake real), 2 (gate), 5 (contrato de `prediction_gate.json`) | `claude-fable-5` |

La sesión principal sigue en `claude-opus-5` (política autorizada 2026-08-30).
Editar `CLAUDE.md` no cambia el modelo de una sesión en curso, y el único
mecanismo real de escalado es el parámetro `model` de `Agent`.

## Subordinación a la medición

Vinculante para los tres subagentes: **ningún escalón de modelo sustituye una
medición**. Mediciones de partida entregadas, obtenidas en las fases 1-2:

- Historia de calibración graduada: 18.229 filas / 1.709 eventos = **10,67x**;
  `mls|h2h` 1.350 filas / 70 eventos = **19,29x** (mediana 21 filas/evento);
  `brasileirao|h2h` 20,04x; `mlb|*` ~2,05x.
- Grupos que pasan `min_n=40`: 47 por filas, **18 por eventos**.
- `data/bets/prediction_gate.json` (2026-09-01): 41 grupos, `allowed: []`,
  `min_n` 300, `alpha` 0,05.
- `configs/default.yaml`: todos los coeficientes de features a 0,0 hoy
  (`streak_coef` estuvo en 0,01 del 2026-08-23 al 2026-09-01).

## Acceptance criteria

- [ ] Solo se modifican los archivos del alcance de cada ID; sin refactors ajenos.
- [ ] Ningún VALOR de parámetro de riesgo cambia (`min_n`, `alpha`,
      `kelly_fraction`, `min_edge`, umbrales, coeficientes): se corrige el
      MECANISMO, no la política.
- [ ] Retrocompatibilidad de artefactos persistidos verificada con datos reales.
- [ ] Cada corrección con prueba discriminante (falla antes, pasa después).
- [ ] Validación final integrada contra la línea base.
- [ ] Sin commit, push, merge ni despliegue. `NOTAS.md` intacto.

## Línea base (fase 1, 2026-09-02)

| Comando | Salida | Código |
|---|---|---|
| `pytest -q` | 1463 passed, 1 skipped (839,58 s) | 0 |
| `ruff check src scripts tests` | All checks passed! | 0 |
| `mypy src` | no issues found in 98 source files | 0 |

## Validación final (fase 5, 2026-09-02)

| Comando | Salida | Código |
|---|---|---|
| `pytest -q` | **1481 passed, 1 skipped** (1.030 s) | 0 |
| `ruff check src scripts tests` | All checks passed! | 0 |
| `mypy src` | no issues found in 98 source files | 0 |
| verificación propia del gate sobre `data/` real | 41 grupos, `allowed: []`, 0 pestillos, 41/41 migrados | 0 |
| stake comprometido por el run de hoy | **0,00 en 148 filas / 12 ligas** | 0 |

+18 tests sobre la línea base (1463 → 1481). Sin regresiones atribuibles.

## Run programado durante la remediación (resuelto, sin incidente)

`SQP_Diario_Completo_Cdev` (11:00 diaria) se ejecutó sobre el árbol a medio
editar mientras los subagentes modificaban `daily.py` y `probabilities.py`.

**Terminó correctamente a las 15:38:59**, con todos sus artefactos:
`pick_history.csv`, reentreno a staging (13 candidatos), `report_20260902.html`
y `report_latest.html`. Tardó 4 h 38 min contra los 22 min de ayer, por
contención de CPU/memoria con tres agentes cargando repetidamente los 328 MB de
`odds_mlb_*` y con la suite completa de 17 min.

**Impacto sobre capital: ninguno.** Los 148 picks de hoy salieron con stake 0
(gate de predicción + pausas), verificado fila a fila.

CORRECCIÓN DE UN DIAGNÓSTICO PROPIO ERRÓNEO: a las 11:37 se declaró el run
"muerto sin traceback, probablemente por memoria". Era falso — seguía corriendo.
Causa del error: `ps` de Git Bash no enumera procesos nativos de Windows, así que
un proceso del Programador de tareas es invisible ahí; hay que usar `tasklist`.
Detalle en `Obsidian/Bitácora/2026-09-02.md`.

Coste operativo introducido por #4: `build_pick_history` medido sin contención en
**232 s** (el agente midió mlb 30,2 s → 74,7 s, 2,47x). El run diario gana del
orden de dos minutos.

## Estado del sistema (sin cambios)

`shadow_mode: false` · `kelly_fraction: 0.08` · `min_edge: 0.02` ·
bankroll inicial 1000, dinámico · `max_plausible_edge: 0.075` ·
`calibration.auto_promote: false` · `prediction_gate.enabled: true` con
`allowed: []` (default-deny efectivo).
Sin ventaja predictiva demostrada.

## Iteración anterior

El registro de la auditoría del 2026-08-31 (iteración 3/8, resultado `DEGRADED`,
58 hallazgos, Grupo A corregido) vive en `audit/latest/` y en
`Obsidian/Bitácora/2026-08-30.md`.
