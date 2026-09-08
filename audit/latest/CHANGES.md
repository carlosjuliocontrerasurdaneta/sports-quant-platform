# Cambios aplicados — Fase 4 de la auditoría 2026-09-08

Autorización: el operador aprobó expresamente Fases 4 y 5 sobre «todas las
correcciones correspondientes a los hallazgos confirmados» y «todas las mejoras
cuya necesidad y beneficio hayan quedado demostrados mediante la evidencia
obtenida durante la auditoría».

IDs tratados: **AUD-HIGH-001, AUD-HIGH-002, AUD-HIGH-003, AUD-MED-001,
AUD-MED-002, AUD-MED-003, AUD-MED-004, AUD-LOW-002** y la limpieza **L-1, L-3,
L-4, L-5** (L-2 parcial). No se tocó nada fuera de esa lista.

Base: `62108b1`, árbol limpio al empezar.

---

## Código

| ID | Archivo | Cambio |
|---|---|---|
| AUD-HIGH-001 | `src/sqp/logging_config.py` | `_shared_file_handler()`: una única instancia de `RotatingFileHandler` por proceso, memoizada (incluido el `None` cuando no hay `logs/`), compartida por todos los loggers. `get_logger` deja de crear una por nombre. |
| AUD-HIGH-002 | `src/sqp/monitoring/health.py` | Constante `RUN_MAX_AGE_DAYS = 1.5` (derivada de la cadencia diaria) y función pública `pipeline_liveness(root, max_age_days)`. `generate_health_report` añade un **ERROR** cuando dispara y expone `pipeline_liveness` en el informe JSON. |
| AUD-HIGH-002 | `src/sqp/audit/html_report.py` | `_run_alert_banner` evalúa primero `pipeline_liveness` y emite su propio banner; el de etapa queda como segunda fuente. Nuevo import de `sqp.monitoring.health`. |
| CODEX-01 | `src/sqp/audit/html_report.py` | Contenedor `#stale-alert` + bloque JS que embebe el sello UTC de la página y `RUN_MAX_AGE_DAYS`, y pinta el aviso de tablero rancio **en el navegador**, al abrir y cada 60 s. Es lo único que puede avisar cuando la página no se regenera. |
| CODEX-02 | `DIARIO_COMPLETO.bat` | El fetch pasa a ser no interactivo (`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`, `GIT_ASKPASS`) y con **plazo de pared duro** vía `Start-Process` + `WaitForExit(SQP_FETCH_TIMEOUT_MS)` + `Kill`; exit 124 se avisa y se continúa. |
| AUD-HIGH-003 | `src/sqp/risk/bankroll.py` | `adjustments_total`: con filas y sin columna `amount`, `LedgerIntegridadError` nombrando fichero y columnas leídas. Cabecera sin filas sigue devolviendo `0.0`. |
| AUD-MED-002 | `src/sqp/storage/served_store.py` | `append_graded` y `append_served` envuelven la transacción completa en `with locked(path)`, leyendo `prior` dentro. Nuevo import de `sqp.storage.lock`. |
| AUD-MED-003 | `src/sqp/pipeline/revalidation.py` | Sitios `:74` (log de revalidación) y `:239` (`candidates_<liga>.csv`) pasan a `atomic_write_csv`. |
| AUD-MED-003 | `src/sqp/risk/prediction_gate.py` | `_append_latch_log` pasa a `atomic_write_csv` (+ import). |
| AUD-MED-003 | `src/sqp/risk/degradation.py` | `append_degradation_log` pasa a `atomic_write_csv` (+ import). |
| AUD-MED-003 | `src/sqp/calibration/calibrator.py` | Los dos escritores del log de promoción pasan a `atomic_write_csv` (+ import). |

## Scripts operacionales

| ID | Archivo | Cambio |
|---|---|---|
| AUD-MED-001 | `DIARIO_COMPLETO.bat` | `mkdir logs` + `rotate_log.cmd logs\diario_completo.log`; subrutina `:log` (consola **y** fichero, con la redirección **delante** del `echo`); guard, etapas `[1/2]`/`[2/2]`/`[3/3]`, cierre OK y las tres ramas de error escriben ahí; `:error_*` vuelcan además `git status` y la llamada al centinela. |
| AUD-MED-004 | `DIARIO_COMPLETO.bat` | Bloque `[0b]`: `git fetch` acotado por `GIT_HTTP_LOW_SPEED_LIMIT/TIME`, comparación `HEAD` vs `@{u}`, aviso con ambos SHA y el comando de diagnóstico. Avisa y continúa; falla abierto sin upstream, sin git o si el fetch falla. |

## Sistema de instrucciones

| ID | Archivo | Cambio |
|---|---|---|
| AUD-LOW-002 | `.claude/skills/memoria-persistente/SKILL.md` | `name: memoria-persistente-pro` → `memoria-persistente`. |
| AUD-LOW-002 | `.claude/skills/mlb-pipeline/SKILL.md` | `name: mlb-pipeline-inspect` → `mlb-pipeline`. |

## Pruebas añadidas (todas discriminantes del hallazgo)

| Archivo | Casos | Cubre |
|---|---|---|
| `tests/test_logging_config.py` *(nuevo)* | 3 | AUD-HIGH-001 |
| `tests/test_health.py` | +5 | AUD-HIGH-002 (liveness, umbral, contraprueba de ausencia, artefacto más reciente) |
| `tests/test_run_status.py` | +10 | AUD-HIGH-002 (banner, precedencia), AUD-MED-001 (3), AUD-MED-004 (4) |
| `tests/test_bankroll.py` | +5 | AUD-HIGH-003 |
| `tests/test_served_store.py` | +4 | AUD-MED-002 (lock tomado en el instante de la escritura, idempotencia, liberación ante fallo) |
| `tests/test_storage.py` | +2 | AUD-MED-003 (contrato de fuente + PID en el temporal) |
| `tests/test_html_report.py` | +5 | CODEX-01 (sello y umbral embebidos, reevaluación periódica, y **3 ejecutando el JS real con Node**: página de hoy sin aviso, la misma página +2 días con aviso, borde 24 h/37 h) |

## Limpieza ejecutada

| ID | Ruta | Resultado |
|---|---|---|
| L-1 | `.claude/reviews/runtime/v2/scratch/work/` (8 repos git de scratch) | eliminado |
| L-3 | `.claude/settings.local.json.backup-audit-20260623` (7.359 B) | eliminado |
| L-4 | `__pycache__/` (raíz) | eliminado |
| L-5 | `audit/reproductions/__pycache__/` | eliminado |
| L-2 | `.codex-tmp/run-20260809T124242-*`, `run-20260809T141756-*` | **PARCIAL**: sus subdirectorios `pytest/test_*` tienen ACL denegada a esta sesión y no se pudieron borrar. Limitación ya declarada como `NO_VERIFICABLE` en la fase de diagnóstico. |
| L-6, L-7, L-8 | `graphify-out/<fecha>/`, `audit/00-13 + FINAL-AUDIT.md`, `audit/full-audit-SKILL-reemplazado-*` | **CONSERVADOS** por decisión de la auditoría |

Ninguna ruta eliminada estaba versionada (`git ls-files` sobre las cinco: 0
resultados). `git status` tras la limpieza no muestra ningún borrado de fichero
rastreado.

---

## Segunda pasada: los dos defectos que encontró la revisión cruzada

El hook `crossreview-on-stop` lanzó a Codex sobre los cambios de este turno y
reportó **dos MEDIUM `STATICALLY_VERIFIED` en mis propias correcciones**. Se
verificaron los dos y **los dos eran correctos**; no se refutó ninguno.

1. **El banner de liveness era decorativo.** `_run_alert_banner()` sólo se
   evalúa mientras se escribe el HTML, y `report_latest.html` es estático: si el
   pipeline deja de correr, la página no se regenera y el aviso no puede
   aparecer **nunca**, justo en la parada que existe para señalar. La mitad
   servidor del arreglo sólo cubre «el run terminó pero una etapa falló».
   Corregido evaluando la frescura en el navegador.
2. **El `git fetch` podía bloquear el pipeline.** `GIT_HTTP_LOW_SPEED_LIMIT/TIME`
   acota la velocidad de transferencia HTTP, no la espera de un gestor de
   credenciales ni la duración del subproceso. Bajo el Programador de tareas, sin
   escritorio, un git que pidiera credenciales habría bloqueado la liquidación —
   un aviso consultivo parando el pipeline del dinero. Corregido con tres
   candados no interactivos y un plazo de pared real.

Codex señaló además que la prueba del plazo «sólo comprobaba que existieran los
nombres de las variables de entorno»: verificaba la intención, no el
comportamiento. Reescrita para exigir el mecanismo, y respaldada por una
ejecución real (git colgado 120 s, plazo 8 s → **exit 124 a los 8,7 s**).

## Efecto del hook de formato

`.claude/hooks/post-edit-format.sh` ejecuta `ruff check --fix` sobre cada
archivo `.py` tras `Edit`/`Write`. Se revisó el diff completo: **no aplicó
ningún autofix**; todo el diff corresponde al parche mínimo y a sus comentarios.
Un único detalle de estilo introducido a mano y deliberadamente no revertido:
en `calibrator.py` el nuevo import queda antes de `sqp.logging_config` en vez de
en orden alfabético. Ruff no tiene activadas las reglas `I`, pasa limpio, y
reordenar sería limpieza cosmética fuera del alcance autorizado.

---

## Lo que se decidió NO tocar

- **AUD-LOW-001** (`crossreview-on-stop.sh` revisa sólo `HEAD`): ya corregido en
  `origin/main` por `c28ee6a`. La corrección es **traer el commit**, y un `git
  pull` es un merge, expresamente excluido de la autorización de corrección por
  la skill `audit-remediation`. Editar el fichero a mano crearía una divergencia
  con el remoto — justo el modo de fallo que este repositorio lleva meses
  documentando.
- **AUD-INF-001** (lock POSIX sin heartbeat): `INFERIDO`, no confirmado. La
  skill prohíbe corregir sobre inferencias.
- **Paso 0 operativo** (relanzar `DIARIO_COMPLETO.bat` para recuperar los dos
  días perdidos): consume cuota de API de pago y escribe datos de producción.
  `audit-remediation` exige para eso una aprobación humana **separada e
  independiente** de la aprobación de la corrección.
- **Commit de estos cambios**: prohibido sin autorización específica. **Tiene
  consecuencia operativa inmediata** — ver `BACKLOG.md`.
- `.env`, `logs/` (más allá de lectura), datos operativos, parámetros de riesgo,
  `shadow_mode`, `pick_mode`, umbrales, calibradores y Programador de tareas:
  intactos.
