# Hallazgos — Auditoría integral 2026-09-08

Severidades e IDs según `.claude/skills/full-audit/references/evidence-findings.md`.
Estado de evidencia: `REPRODUCIDO` / `VERIFICADO_ESTÁTICAMENTE` / `INFERIDO` /
`NO_VERIFICABLE` / `DESCARTADO`. Sólo los dos primeros son **confirmados**.

Base: `62108b1`, árbol de trabajo limpio al abrir. Suite de partida
**1636 passed, 1 skipped** (1136,89 s), `ruff` y `mypy` limpios.

> `CLAUDE_CODE_REVIEW.md` y `QUANT_REVIEW.md` de este directorio pertenecen al
> ciclo **2026-09-06** y no se han reescrito: este ciclo no generó revisiones
> equivalentes. El resto de artefactos de `audit/latest/` sí corresponden al
> 2026-09-08.

---

## Estado de los hallazgos

| ID | Sev. | Evidencia | Estado |
|---|---|---|---|
| AUD-HIGH-001 | HIGH | REPRODUCIDO | **corregido y verificado en producción** |
| AUD-HIGH-002 | HIGH | REPRODUCIDO + VERIFICADO_ESTÁTICAMENTE | **corregido** (la alarma ya dispara sobre el estado real) |
| AUD-HIGH-003 | HIGH | REPRODUCIDO | **corregido** |
| AUD-MED-001 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (validado en banco aislado, 5 casos) |
| AUD-MED-002 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-MED-003 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (6 sitios) |
| AUD-MED-004 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (validado en banco aislado) |
| AUD-LOW-001 | LOW | VERIFICADO_ESTÁTICAMENTE | **no corregido** — requiere `git pull`, fuera de la autorización de corrección |
| AUD-LOW-002 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| CODEX-01 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** — defecto en mi arreglo de AUD-HIGH-002, hallado por la revisión cruzada |
| CODEX-02 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** — defecto en mi arreglo de AUD-MED-004, hallado por la revisión cruzada |
| AUD-INF-001 | MEDIUM (potencial) | INFERIDO | **no corregido** — falta condición necesaria (POSIX no ejecutable aquí) |

Limpieza: **L-1, L-3, L-4, L-5 ejecutadas**; **L-2 parcial** (ACL denegada);
**L-6, L-7, L-8 conservadas** por decisión de la auditoría.

---

## AUD-HIGH-001 — La rotación de `sqp.log` estaba rota y descartaba cada registro

**Componente:** `src/sqp/logging_config.py:32-45`.

`get_logger(name)` creaba un `RotatingFileHandler` **nuevo por cada nombre de
logger**; hay ~50 nombres distintos en 53 llamadas, todos sobre `logs/sqp.log`.
Con decenas de descriptores abiertos, `doRollover()` cerraba sólo el suyo y
`os.rename` fallaba con `WinError 32`. Y como el rollover ocurre **dentro** del
`try` de `emit`, al lanzar se saltaba la escritura: **el registro se perdía**.

**Evidencia.** `sqp.log` congelado en 4.999.946 B contra `maxBytes` 5.000.000,
con `sqp.log.3` presente y `.1`/`.2` ausentes; primer `WinError 32` el
2026-09-06 23:30:44; 1.002 bloques `--- Logging error ---` en `run_diario.log`.
Reproducción aislada: 1 handler → 3 backups, 0 errores; 2 handlers → 0 backups,
**162 registros perdidos de 200**.

**Corrección.** Una única instancia de `RotatingFileHandler` por proceso,
memoizada y compartida por todos los loggers. Se comparte el **objeto** en vez
de reorganizar la jerarquía padre/hijos para no alterar ninguna otra semántica
(niveles, propagación, riesgo de líneas duplicadas). `logging.Handler` lleva su
propio lock.

**Verificado en producción:** tras el cambio, `sqp.log` **rotó** (`sqp.log.1` =
4.999.946 B, nuevo `sqp.log` = 871 B) y desaparecieron los tracebacks.

**Pruebas:** `tests/test_logging_config.py` (3).

---

## AUD-HIGH-002 — Producción llevaba 48 h parada sin que ningún control lo dijera

**Componentes:** `src/sqp/monitoring/health.py`, `src/sqp/audit/html_report.py`.

Las dos superficies de alarma leían **sólo** `logs/last_run_status.json`, que
escribe el propio proceso que falla desde la rama `:error` de su BAT. No existía
ninguna comprobación independiente de si el pipeline había producido algo.

**Evidencia (2026-09-08).** `SQP_Diario_Completo_Cdev` última ejecución
2026-09-07 12:00:01 → `0x1`; `SQP_Capture_Close_Cdev` 2026-09-08 10:30:02 →
`0x1`; `logs/last_run_status.json` **inexistente**; informe de salud
`WARN, 0 errors`; último run completo el **2026-09-06 12:01**; todos los
artefactos (`candidates_*`, `predictions_*`, `report_latest.html`,
`prediction_gate.json`) sellados el 2026-09-06.

**Corrección.** `pipeline_liveness(root)` mide la antigüedad del artefacto más
reciente de `data/predictions/predictions_*.csv` y devuelve el desfase si supera
`RUN_MAX_AGE_DAYS`. El informe de salud lo eleva a **ERROR**; el banner del
tablero lo consume **antes** que el centinela.

- El testigo es `predictions_*` y no `candidates_*` porque `_finalize` lo escribe
  **siempre** (los candidates se borran si quedan vacíos) y **antes** de
  construir el tablero, de modo que en un run sano el banner ya ve el sello nuevo.
- `RUN_MAX_AGE_DAYS = 1.5` **no es un umbral inventado**: sale de la cadencia
  declarada (tarea diaria a las 12:00). Un artefacto sano tiene 0–24 h; si se
  pierde un run llega a ~47 h. 36 h es el punto medio: no dispara porque el run
  de hoy aún no haya llegado, y avisa como mucho ~12 h después de perder uno.
- La **ausencia total** de artefactos no es fallo: no distingue «nunca ha
  corrido» de un clon recién hecho.

**Verificado:** `pipeline_liveness` devuelve 2,0 días sobre producción y
`health_check.py` pasa de `WARN, 0 errors` a `ERROR (1 errors, 5 warnings)`.

**Corrección posterior — la mitad del arreglo era decorativa.** La revisión
cruzada de Codex señaló que `_run_alert_banner()` sólo se evalúa **mientras se
escribe el HTML**, y `report_latest.html` es un fichero estático que el operador
abre desde un bookmark: si el pipeline deja de correr, la página no se regenera
y ese banner **no puede aparecer nunca**, justo en la parada que existe para
señalar. Era correcto. La página lleva ahora su sello UTC y el umbral, y evalúa
la frescura **en el navegador** al abrirla y cada 60 s.

**Pruebas:** `tests/test_health.py` (5), `tests/test_run_status.py` (3),
`tests/test_html_report.py` (5, tres de ellas ejecutando el JS real con Node:
la misma página sin regenerar avisa a los 2 días y no avisa a las 24 h).

---

## AUD-HIGH-003 — Un ajuste de banca con la cabecera derivada se evaporaba

**Componente:** `src/sqp/risk/bankroll.py:252`.

`adjustments_total()` validaba el **valor** del importe pero no la **presencia**
de su columna: con `amount` renombrada devolvía `0.0` en silencio. Es el hueco
que `_exigir_pnl_legible` ya cierra en `settled_*.csv`, dejado abierto en el
otro sumando del saldo. El error va **siempre hacia arriba**: lo que se registra
ahí son correcciones y retiradas, y de esa cifra cuelgan Kelly y el cap diario.

**Evidencia (reproducida).** Banca 1.000 con una pérdida de −100 y una retirada
de −400: esquema correcto → 500; con `amount` renombrada a `importe` → **900**.
El fichero **existe en producción** con dos filas reales y se mantiene a mano.

**Corrección.** Con filas y sin columna `amount`, `LedgerIntegridadError`
nombrando el fichero y las columnas leídas. Cabecera sin filas sigue siendo cero
legítimo. `apply_dynamic_bankroll` ya capturaba la excepción y cae a banca 0.

**Pruebas:** `tests/test_bankroll.py` (5).

---

## AUD-MED-001 — `DIARIO_COMPLETO.bat` no dejaba rastro en ningún log

Todos sus `echo` iban a la consola, y bajo el Programador de tareas no hay
consola: el guard de árbol, los marcadores de etapa y las **tres ramas de
error** se perdían enteros. Por eso la causa raíz del fallo del 2026-09-07 es
indeterminable.

**Corrección.** Subrutina `:log` que escribe en consola **y** en
`logs\diario_completo.log` (rotado con `rotate_log.cmd`), aplicada al guard, a
las etapas y a las tres ramas de error, que además vuelcan ahí su `git status` y
la llamada al centinela.

La redirección va **delante** del `echo` (`>>fichero echo %~1`): con
`echo %~1>>fichero`, si el mensaje termina en dígito cmd lo lee como descriptor
y se lo come del texto — y las líneas del aviso de árbol atrasado terminan en un
SHA.

**Pruebas:** `tests/test_run_status.py` (3 de contrato) + banco aislado.

---

## AUD-MED-002 — `ServedStore` escribía sin lock

`append_graded` es un read-modify-write que **reemplaza el fichero entero** y
corría sin exclusión: la misma carrera que Codex reprodujo en `_persist_settled`
(AUD-20260906-02, HIGH) y que allí se corrigió. Los dos ficheros se escriben en
el mismo pase de liquidación, y ni `settle_all.py` ni `settle_bets.py` añaden
exclusión externa.

**Corrección.** `with locked(path)` alrededor de la transacción completa en
`append_graded` y en `append_served`, leyendo `prior` **dentro** del lock.

**Nota de diseño encontrada al probar:** el lock **no es reentrante**. Un
intercalado real exige un segundo proceso; llamar al store desde dentro de su
propia sección crítica aborta con `LockNoAdquiridoError` a los 120 s. Es el
comportamiento correcto, y la prueba se diseñó en consecuencia: comprueba que el
`.lock` está tomado **en el instante de la escritura**, que es lo único que
distingue «toma el lock» de «lo toma demasiado tarde».

**Pruebas:** `tests/test_served_store.py` (4).

---

## AUD-MED-003 — La escritura atómica canónica estaba aplicada en 1 de 6 sitios

`storage/atomic.py` existe por el temporal **único** por proceso (causa raíz
secundaria de AUD-002) y por el `fsync`. Seis sitios lo reimplementaban a mano
con `.csv.tmp` fijo. La corrección se había aplicado **en uno**:
`revalidation.py:407`, con un comentario explicando por qué el temporal a mano
está mal — y 165 líneas antes, en el mismo módulo y sobre el mismo
`candidates_<liga>.csv`, seguía el temporal a mano.

**Corregidos los seis:** `revalidation.py:74` y `:239`,
`prediction_gate.py:408`, `degradation.py:212`, `calibrator.py:830` y `:910`.
Cinco de ellos no participan en ningún lock.

**Pruebas:** `tests/test_storage.py` (2), una de ellas un contrato de fuente que
impide que el idioma vuelva (ignorando comentarios: la razón del cambio se
documenta con esas mismas palabras).

---

## AUD-MED-004 — El guard miraba si el árbol estaba sucio, no si estaba atrasado

Producción ejecuta el árbol de trabajo. El 2026-09-08 este clon iba **8 commits
por detrás de `origin/main`** sin que nada lo dijera: una sesión de remediación
entera del 2026-09-07, publicada desde otro clon, con correcciones de código en
`src/sqp/config.py`, `markets/line_movement.py`, `pipeline/budget.py`,
`pipeline/probabilities.py`, los hooks y `configs/default.yaml`.

> **Corrección del propio informe.** La fase de diagnóstico dijo «2 commits».
> Era un dato mal inferido: `git fetch --dry-run` imprime un rango de refs, no
> un conteo, y sólo inspeccioné los dos commits de cabeza. Al traerlos se contó
> de verdad: son **8**. El hallazgo no cambia — el árbol estaba atrasado y nada
> lo señalaba —; la magnitud sí, y a peor.

**Corrección.** Tras el guard de árbol sucio, `DIARIO_COMPLETO.bat` compara
`HEAD` con `@{u}` y avisa si difieren, indicando el comando para ver qué falta.

- **Avisa, no aborta**: detener el pipeline del dinero por un commit de
  documentación sería un modo de fallo nuevo y desproporcionado.
- **Hace `git fetch`**: sin él se compararía contra una referencia obsoleta, que
  es exactamente el estado que produjo el hallazgo.
- Acotado con `GIT_HTTP_LOW_SPEED_LIMIT/TIME` para que una red caída no cuelgue
  el run, y **falla abierto** igual que el guard existente.

**Corrección posterior.** Codex señaló que `GIT_HTTP_LOW_SPEED_LIMIT/TIME`
acota la velocidad de **transferencia HTTP**, no la espera de un gestor de
credenciales ni la duración del subproceso: bajo el Programador de tareas, sin
escritorio, un git que pidiera credenciales habría **bloqueado la liquidación**
— un aviso consultivo parando el pipeline del dinero. Era correcto. Se añadieron
`GIT_TERMINAL_PROMPT=0`, `GCM_INTERACTIVE=never`, `GIT_ASKPASS` y un **plazo de
pared duro** (`WaitForExit` + `Kill`, `SQP_FETCH_TIMEOUT_MS`, 20 s por defecto).
Medido con un git que se cuelga 120 s y plazo de 8 s: **aborta a los 8,7 s con
código 124** y continúa; con git real, 0 en 0,9 s.

**Pruebas:** `tests/test_run_status.py` (4 de contrato; la del plazo se
reescribió — Codex la calificó, con razón, de comprobar sólo que existieran los
nombres de las variables) + banco aislado (6 casos).

---

## AUD-LOW-001 — NO CORREGIDO

El `crossreview-on-stop.sh` de este árbol revisa sólo `HEAD`. Ya está corregido
en `origin/main` (`c28ee6a`). **La corrección es traer el commit, no editar el
fichero**, y un `git pull` es un merge: la skill `audit-remediation` lo excluye
expresamente de la autorización de corrección. Ver `BACKLOG.md`.

---

## AUD-LOW-002 — Frontmatter alineado con el directorio

`memoria-persistente-pro` → `memoria-persistente`; `mlb-pipeline-inspect` →
`mlb-pipeline`. Verificado: 0 desajustes en las 35 skills. El harness recargó
ambas con el nombre corregido durante la sesión.

---

## AUD-INF-001 — NO CORREGIDO (inferido)

Lock caducado sin heartbeat: bajo semántica POSIX, una sección crítica de más de
`LOCK_STALE_S=300 s` puede ser robada, y el titular original borra después el
`.lock` del segundo, en cascada. En Windows —el SO de producción— el `unlink`
falla y degrada a espera, que es correcto. No se corrige porque falta una
condición necesaria: no hay reproducción POSIX posible en esta máquina y la
sección crítica más larga medida está en decenas de segundos. Ver `BACKLOG.md`.

---

## Falsos positivos descartados (resumen)

Los seis hallazgos de Codex del 2026-09-06 están **cerrados con pruebas
discriminantes**; los calibradores live y de staging (16 artefactos
deserializados) **no tienen defecto estructural**; `pip-audit` está **verde** en
CI; el routing de modelos valida `OK`; **0 referencias de ruta rotas** en 200+
ficheros de instrucciones; sin secretos versionados; todas las llamadas HTTP con
timeout; 0 `datetime.now()` naive. Detalle completo en el informe de sesión.
