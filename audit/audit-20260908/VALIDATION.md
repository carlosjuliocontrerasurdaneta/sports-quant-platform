# Validación — Auditoría y remediación 2026-09-08

Clasificación por comprobación: `PASO` / `FALLO` / `FALLO_PREEXISTENTE` /
`REGRESIÓN_INTRODUCIDA` / `NO_EJECUTADA`. Se registra el **código de salida
real**, no una impresión.

Entorno: Windows 11, Python 3.14.4, pytest 9.0.3, Ruff 0.15.14, MyPy 2.1.0,
Node v24.18.0.

---

## Línea base (Fase 0, antes de tocar nada)

| Comando | Resultado | Exit | Clasificación |
|---|---|---|---|
| `python -B -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/audit-pytest --tb=line` | **1636 passed, 1 skipped** en 1136,89 s | 0 | `PASO` |
| `ruff check --no-cache src scripts tests` | All checks passed | 0 | `PASO` |
| `mypy --cache-dir=.codex-tmp/mypy src` | Sin incidencias en 98 ficheros | 0 | `PASO` |

---

## Validación final (Fase 5)

| # | Comando / comprobación | Resultado | Exit | Clasificación |
|---|---|---|---|---|
| 1 | `ruff check --no-cache src scripts tests` | All checks passed | 0 | `PASO` |
| 2 | `mypy --cache-dir=.codex-tmp/mypy src` | Sin incidencias en 98 ficheros | 0 | `PASO` |
| 3 | `pytest ... --basetemp=.codex-tmp/audit-final` (tras las correcciones, antes de la revisión cruzada) | **1666 passed, 1 skipped** en 1314,37 s | 0 | `PASO` |
| 4 | `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/audit-final2 --tb=short` (final, tras atender a Codex) | **1671 passed, 1 skipped** en 1016,86 s | 0 | `PASO` |
| 5 | Importación de los 9 módulos tocados (detección de ciclos) | «todos los módulos importan sin ciclo» | 0 | `PASO` |

### Validaciones específicas por hallazgo

| ID | Comprobación | Resultado | Clasificación |
|---|---|---|---|
| AUD-HIGH-001 | `tests/test_logging_config.py` (3) | 3 passed | `PASO` |
| AUD-HIGH-001 | **Verificación en producción**: estado de `logs/sqp.log*` antes y después | antes: `sqp.log` 4.999.946 B congelado, `.3` presente, `.1`/`.2` ausentes. Después: **`sqp.log.1` = 4.999.946 B, `sqp.log` = 871 B** (rotó) y 0 tracebacks | `PASO` |
| AUD-HIGH-001 | Reproducción aislada `scratchpad/repro/rot.py` | 1 handler → 3 backups / 0 errores; 2 handlers → 0 backups / 162 registros perdidos | `PASO` |
| AUD-HIGH-002 | `tests/test_health.py` (+5), `tests/test_run_status.py` (+3) | passed | `PASO` |
| AUD-HIGH-002 | **Verificación contra el estado real**: `python scripts/health_check.py` | antes `WARN (0 errors, 5 warnings)`, exit 0 → después **`ERROR (1 errors, 5 warnings)`, exit 1**, nombrando `predictions_brasileirao.csv` y 2,0 días | `PASO` |
| AUD-HIGH-002 | `pipeline_liveness(Path('.'))` sobre producción | `{'age_days': 2.0, 'artifact': 'predictions_brasileirao.csv', 'n_artifacts': 28, 'max_age_days': 1.5}` | `PASO` |
| AUD-HIGH-002 | **Banner client-side** (`tests/test_html_report.py`, 5, tres con Node) | página de hoy → sin aviso; **misma página +2 días → «2.0 dias» + `DIARIO_COMPLETO.bat`**; borde 24 h → sin aviso, 37 h → aviso | `PASO` |
| AUD-HIGH-003 | `tests/test_bankroll.py` (+5) | passed | `PASO` |
| AUD-HIGH-003 | Reproducción original `scratchpad/repro/adj.py` | caso C pasó de **saldo 900 silencioso** a `LedgerIntegridadError`; caso D (cabecera sin filas) sigue devolviendo 0,0 | `PASO` |
| AUD-HIGH-003 | Ledger real tras el cambio | `current_balance = 915.75`, sin excepción | `PASO` |
| AUD-MED-001 | `tests/test_run_status.py` (3 de contrato) | passed | `PASO` |
| AUD-MED-002 | `tests/test_served_store.py` (+5 casos) | passed | `PASO` |
| AUD-MED-003 | `tests/test_storage.py` (+2) | passed; 0 sitios con `.csv.tmp` a mano en `src/sqp` | `PASO` |
| AUD-MED-004 | `tests/test_run_status.py` (4 de contrato, uno reescrito tras la revisión cruzada) | passed | `PASO` |
| AUD-LOW-002 | Barrido de las 35 skills | 0 desajustes nombre/directorio | `PASO` |

### Validación de los `.bat` — banco git aislado

Los `.bat` **no los cubre ninguna puerta automática** (CI corre en Linux salvo una
pata Windows que sólo lanza pytest). Se validaron ejecutándolos en repositorios
git desechables bajo el scratchpad, con `SETTLE_ALL`, `RUN_DIARIO_ALL`,
`run_status.py`, `daily_picks.py` y `tipster_report.py` sustituidos por stubs:
**no se tocó producción ni se gastó cuota**.

| Caso | Esperado | Observado | Clasificación |
|---|---|---|---|
| 1. Árbol limpio y al día | corre entero, exit 0 | `[1/2] [2/2] [3/3] === DIARIO COMPLETO: OK ===`, exit 0, log escrito | `PASO` |
| 2. Remoto por delante, ref local obsoleta | avisa y continúa | `[AVISO] EL ARBOL NO ESTA AL DIA` con ambos SHA completos, exit 0 | `PASO` |
| 3. Árbol sucio | aborta antes de liquidar, con rastro | exit 1 y el motivo + `git status` + centinela **escritos en el log** | `PASO` |
| 4. Sin remoto | no comprueba, no falla | `[INFO] sin rama upstream`, exit 0 | `PASO` |
| 5. Liquidación falla | aborta antes del run | `*** ERROR EN LA LIQUIDACION ***`, centinela `stage=settle`, exit 1 | `PASO` |
| 6. **`git fetch` colgado 120 s, plazo 8 s** | aborta el fetch y continúa | **exit 124 a los 8,7 s, proceso matado**; con git real, exit 0 en 0,9 s | `PASO` |

Verificación colateral del caso 3: el guard detectó `SETTLE_ALL.bat` modificado,
confirmando que el patrón `*.bat` del pathspec funciona.

---

## Revisión cruzada independiente (Codex, hook `crossreview-on-stop`)

Codex revisó los cambios de este turno y reportó **dos defectos MEDIUM,
`STATICALLY_VERIFIED`, en mis propias correcciones**. Se comprobaron los dos y
**los dos eran correctos**. No se refutó ninguno.

| Hallazgo de Codex | Verificación | Resolución |
|---|---|---|
| El banner de liveness sólo se evalúa al **generar** el HTML; `report_latest.html` es estático y un pipeline parado nunca lo regenera, así que el aviso no aparecería justo en la parada que existe para señalar | Confirmado leyendo `html_dashboard`: `_run_alert_banner()` se interpola una vez en el template | **Corregido**: la página lleva ahora su sello UTC y el umbral, y evalúa la frescura **en el navegador** al abrir y cada 60 s. 5 pruebas nuevas, 3 de ellas ejecutando el JS real con Node |
| `GIT_HTTP_LOW_SPEED_LIMIT/TIME` acota la velocidad de transferencia HTTP, **no** la espera de un gestor de credenciales ni la duración del subproceso; bajo el Programador de tareas un git que pida credenciales bloquearía la liquidación | Confirmado: son variables de transferencia; no hay plazo de pared | **Corregido**: `GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`, `GIT_ASKPASS=echo` y un plazo de pared duro con `WaitForExit` + `Kill`. Medido: **124 a los 8,7 s** con un git que se cuelga 120 s. La prueba de contrato, que Codex calificó de insuficiente, se reescribió para exigir el mecanismo y no los nombres de variable |

---

## Separación de fallos

- **`FALLO_PREEXISTENTE`**: ninguno. La línea base terminó en 0 fallos.
- **`REGRESIÓN_INTRODUCIDA`**: ninguna. Todas las pruebas de la línea base
  siguen pasando; el delta es sólo de pruebas **añadidas**.
- **Fallos durante el desarrollo, resueltos antes de cerrar** (se registran por
  transparencia, no son estado final):
  1. Una prueba de concurrencia mal diseñada por mí llamaba al store desde
     dentro de su propia sección crítica: colgó 120 s y abortó con
     `LockNoAdquiridoError`. **El lock funcionaba; la prueba estaba mal.**
     Rediseñada.
  2. Tres pruebas de contrato de BAT fallaron por escapes de Python (`\d`) y por
     prohibir una cadena que el propio comentario necesita citar. Corregidas
     ignorando líneas `REM`, igual que el escaneo de fuente ignora `#`.
  3. El arnés de Node caía en la zona muerta temporal al declarar `const Date`
     en el ámbito donde se leía. Reescrito con ámbito de función.
  4. `ruff E402` por imports a mitad de fichero al ampliar `test_html_report.py`.
     Movidos a la cabecera.

## Validaciones NO ejecutadas

| Comprobación | Motivo |
|---|---|
| Ejecución real de `DIARIO_COMPLETO.bat` en producción | Consume cuota de API de pago y escribe datos de producción: exige aprobación humana separada (`BACKLOG.md` B-1) |
| `.bat` en CI | CI corre en Linux salvo una pata Windows que sólo lanza pytest (`BACKLOG.md` B-6) |
| `pip-audit` local | Sin red; se usa el resultado **verde** del CI del 2026-09-07 (run 34163648093, las 4 patas Linux) |
| Reproducción POSIX del lock (`AUD-INF-001`) | La máquina es win32 (`BACKLOG.md` B-3) |
| Contenido completo de `logs/` y `.env` | Denegados a la sesión por `.claude/settings.json` |
| Construcción de la imagen Docker | Ningún paso de CI la construye; limitación heredada del ciclo anterior |

## Resultado final

**`DEGRADED`** según `.claude/loops/quant/STATES.md`.

Se cumplen (a), (b) y (c) de `PASS`: todos los comandos requeridos terminaron con
código 0 (pytest **1671 passed / 0 failed / 1 skipped**, ruff, mypy), las
validaciones específicas de cada hallazgo se ejecutaron, y los artefactos
obligatorios están escritos y son legibles.

Es `DEGRADED` y no `PASS` por tres limitaciones acotadas, no críticas y
registradas:

1. **L-2 quedó parcial**: dos directorios de `.codex-tmp` no se pudieron borrar
   por ACL denegada a la sesión (`BACKLOG.md` B-4).
2. **AUD-LOW-001 no se corrigió**: su remedio es un `git pull`, y la skill
   excluye merges de la autorización de corrección (`BACKLOG.md` B-2).
3. **Los `.bat` no los cubre ninguna puerta automática**: se validaron en un
   banco git aislado con 6 casos, pero CI no los ejecuta (`BACKLOG.md` B-6).

No procede `BLOCKED`: ninguna de las tres impide el objetivo aprobado, y las
acciones que sí requieren aprobación humana posterior (recuperar el servicio,
traer los commits) están registradas como siguiente decisión, que es
exactamente lo que `STATES.md` permite dejar fuera de `BLOCKED`.

Delta de la suite: **1636 → 1671** (+35 pruebas), 0 fallos en ambos extremos.
Ninguna prueba de la línea base dejó de pasar: no hay
`REGRESIÓN_INTRODUCIDA` ni `FALLO_PREEXISTENTE`.
