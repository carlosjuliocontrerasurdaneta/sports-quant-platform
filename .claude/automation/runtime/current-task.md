# Current Task

Status: closed
Result: DEGRADED (iteración 3: correcciones del Grupo A verificadas; cobertura
sigue PARCIAL por features/providers/deportes y backtesting, y quedan 3
decisiones del Grupo B sin resolver)
Primary loop: `audit.md`
Skill: `full-audit` → `audit-remediation`
Iteration: 3 / 8
Owner: 3 especialistas de solo lectura en paralelo (fase 1) + revalidación propia (fase 2)
Date: 2026-08-31 (iteración 3: cierre de la cobertura PARCIAL del camino del dinero)

## Objective

Auditoría integral del repositorio completo y corrección de los hallazgos
confirmados, con la mejora limitada a lo sustentado por evidencia obtenida
durante la auditoría. Sin commit, push, deploy, consumo de API de pago ni
modificación de stakes, bankroll, `pick_mode` o `shadow_mode`.

## Acceptance criteria

- [x] Instrucciones del repositorio y `known-issues.md` leídas antes de auditar.
- [x] Línea base ejecutada y registrada ANTES de corregir.
- [x] Hallazgos clasificados con evidencia, causa raíz, corrección y estado.
- [x] Cada hallazgo activo revalidado por un segundo método.
- [x] Validación final ejecutada y comparada contra la línea base.
- [x] Entregables regenerados en `audit/latest/`.
- [x] Ninguna acción que requiriera autorización humana.
- [ ] Cobertura COMPLETA — **no alcanzada**, declarada `PARCIAL`.

## Comandos ejecutados y códigos de salida

| Comando | Salida | Código |
|---|---|---|
| `pytest tests/ -q` (línea base) | 3 failed, 1375 passed, 1 skipped | 1 |
| `ruff check src scripts tests` | All checks passed! | 0 |
| `mypy src` | no issues found in 98 source files | 0 |
| `pip check` | No broken requirements found. | 0 |
| `scripts/health_check.py` | WARN (0 errors, 1 warning) | 0 |
| `pytest tests/test_claude_system_contract.py -q` | 15 passed | 0 |
| `pytest tests/ -q` (final) | 1 failed, 1377 passed, 1 skipped | 1 |
| `python -m pip_audit -s osv -r requirements.lock` | No known vulnerabilities found | 0 |
| reproducción de `_independent_units` por tipo de mercado | spreads=2 unidades, h2h/totals=1 | 0 |
| reproducción de `_max_drawdown` | reporta -200, real -300 | 0 |
| `pytest tests/ -q` (tras cerrar KI-021) | **1378 passed, 1 skipped** | 0 |
| `pytest tests/ -q` (it. 3, tras el Grupo A) | **1390 passed, 1 skipped** (1.146 s) | 0 |
| `ruff check` / `mypy src` (it. 3, tras el Grupo A) | All checks passed! / 98 files, 0 issues | 0 |

`pip-audit` YA EJECUTADO el 2026-08-31 (2.10.1 disponible en el entorno): sin
vulnerabilidades conocidas. Cierra la limitación que dejó la iteración 1.

## Artefactos producidos

- `audit/latest/EXECUTIVE_SUMMARY.md`
- `audit/latest/FINDINGS.md`
- `audit/latest/VALIDATION.md`
- `audit/latest/CHANGES.md`
- `audit/latest/QUANT_REVIEW.md`
- `audit/latest/BACKLOG.md`
- `audit/latest/MANIFEST.json`
- `Obsidian/Bitácora/2026-08-30.md`

## Métricas observadas con su n

- Suite: 1375 → **1378** aprobados; 3 → **0** fallos, sobre 1379 tests.
- `mypy`: 98 archivos, 0 issues.
- Repositorio: 588 archivos trackeados, 275 módulos Python, 44.072 líneas.
- Commits desde la última auditoría con informe persistido: **179**.
- Loops con bloque de guardarraíles idéntico: **11 de 11** (antes 10 de 11).
- Filas servidas irrecuperables acumuladas: **152**.

## Justificación del resultado `DEGRADED`

No es `PASS` porque queda una limitación acotada y nombrada: la cobertura es
`PARCIAL` (los gates de riesgo y el pipeline diario no recibieron la lectura
línea a línea que el procedimiento exige para marcar `REVISADA`). Según
`STATES.md`, una limitación no crítica, acotada y registrada es `DEGRADED`.

El fallo preexistente ya no cuenta: KI-021 se cerró el 2026-08-30 por decisión
del operador y la suite quedó completamente verde.

No es `BLOCKED` porque el objetivo se cumplió: los hallazgos confirmados se
corrigieron y la corrección quedó verificada. La decisión pendiente es posterior
y se registra abajo, no bloquea lo ya completado.

## Iteración 3 — resultado

Cerrados los puntos 3 y 4 de la lista de decisiones anterior: las ~2.700 líneas
pendientes están leídas línea a línea y los 8 `.bat` revisados (sin defecto; la
única omisión de errorlevel está documentada como deliberada).

**58 hallazgos nuevos**: 5 ALTO, 26 MEDIO, 23 BAJO, 13 INFORMATIVO, más 15
sospechas descartadas con evidencia.

**Fase 4 ejecutada** con el Grupo A aprobado por el operador: `N-A-1`, `N-A-2`,
`N-A-3`, `R-B-1`, `N-M-6`. Cuatro módulos tocados
(`pipeline/cleanup.py`, `storage/served_store.py`, `settlement/runner.py`,
`risk/bankroll.py`), 13 pruebas añadidas y 1 reescrita. Grupo B **no tocado**:
sigue esperando decisión.

Dos afirmaciones de los especialistas corregidas a la baja en fase 2: la
duplicación del stream graduado es **2,31x** (medición propia), no 3,84x; y
`FS-01` baja de ALTO a MEDIO porque la rama ML no tiene llamador en producción.

## Next decision

Requieren aprobación humana, ninguna ejecutada. Ordenadas por relación
impacto/riesgo:

**Grupo A — corregibles sin decisión de negocio (parche mínimo, riesgo bajo):**

1. `N-A-1` — la poda borra ficheros sin liquidar cuando ningún pick tiene stake,
   que es el 100% del estado actual. Es el más urgente del grupo: destruye
   evidencia graduable de forma irrecuperable y hoy está armado.
2. `N-A-3` — una respuesta vacía del proveedor anula en masa y de forma
   irreversible. Guard de salud del payload antes de anular.
3. `N-A-2` — cuarentena del `served_*.csv` corrupto en vez de tratarlo como
   vacío para siempre.
4. `R-B-1` (iteración 2) — `max_drawdown` subestima. Cambio de una línea.
5. `N-M-6` — `event_id` sin validar en un guard que corre fuera de todo `try`
   antes del bucle de ligas.

**Grupo B — alteran un criterio pre-registrado o un contrato con test: exigen
decisión del operador y enmienda, no parche silencioso:**

6. `R-A-1` (iteración 2) — spreads duplica `n` en el prediction gate.
7. `N-A-4` — el cap global de exposición se define por día de generación y no
   por vigencia. Invalida `tests/test_daily_exposure.py:120-129`. Alternativa de
   coste cero: sólo loguear la exposición viva frente al cap.
8. `N-A-5` — normalizar la duplicación en el punto de lectura compartido. Baja
   la n y sube los p-valores de los informes históricos.

**Grupo C — cobertura que sigue abierta:**

9. Features, providers y adaptadores por deporte: nunca fueron alcance primario
   de ninguna iteración.
10. Backtesting y walk-forward: `COBERTURA_NO_VERIFICABLE`.

KI-021 ya no está aquí: se cerró el 2026-08-30 con Opus 5 en las cuatro puntas.

## Estado del sistema (sin cambios)

`shadow_mode: false` · `kelly_fraction: 0.08` · `min_edge: 0.02` ·
bankroll inicial 1000, dinámico · `max_plausible_edge: 0.075` ·
`calibration.auto_promote: false`.
Sin ventaja predictiva demostrada.
