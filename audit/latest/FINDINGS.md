# Hallazgos — Auditoría integral 2026-09-06

Severidades e IDs según `.claude/skills/full-audit/references/evidence-findings.md`.
Estado de evidencia: `REPRODUCIDO` / `VERIFICADO_ESTÁTICAMENTE` / `INFERIDO` /
`NO_VERIFICABLE` / `DESCARTADO`. Sólo los dos primeros son **confirmados**.

Alcance: repositorio completo. Resultado de cobertura: **REVISADA** salvo dos
áreas `EXCLUIDA` por política de permisos (`logs/`, `.env`) y una
`REVISADA_PARCIALMENTE` (contenido de datos operativos). Matriz completa en
`VALIDATION.md`.

Base: `01993fd` (+1 commit local sobre `origin/main`). Suite de partida
**1547 passed, 1 skipped**, `ruff` y `mypy` limpios.

---

## Estado de los hallazgos

| ID | Sev. | Evidencia | Estado |
|---|---|---|---|
| AUD-MED-001 | MEDIUM | REPRODUCIDO | **corregido** |
| AUD-MED-002 | MEDIUM | REPRODUCIDO | **corregido** |
| AUD-MED-003 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (diagnóstico del fallo concreto: pendiente, ver `BACKLOG.md`) |
| AUD-LOW-001 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-LOW-002 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-LOW-003 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido** (7 instancias) |
| AUD-LOW-004 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido parcialmente** — se corrigió la afirmación falsa; alinear la imagen con 3.14 requiere una construcción que esta sesión no puede validar |
| AUD-LOW-005 | LOW | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-INF-001 | HIGH (potencial) | INFERIDO | **no corregido** — falta condición necesaria |
| AUD-INF-002 | LOW | INFERIDO | **no corregido** — falta condición necesaria |

Ningún hallazgo `CRITICAL` ni `HIGH` confirmado en esta auditoría. Ver la
sección final: una auditoría independiente de Codex sobre el mismo commit,
escrita durante esta sesión, sí reporta tres HIGH que **no están en este alcance**.

---

## MEDIUM

### AUD-MED-001 · La caché de cuotas sirve una entrada caducada cuando el `mtime` va por delante del reloj

- **Evidencia:** `REPRODUCIDO` · **Confianza:** HIGH
- **Componente:** `src/sqp/providers/odds_cache.py:42`
- **Activación:** `time.time()` devuelve un instante anterior al `st_mtime` del
  fichero → la edad sale negativa → ningún `ttl` la caduca, ni `0`.
- **Reproducción:** forzando `os.utime(f, (time.time()+0.5, ...))`, la edad daba
  `−0,4996 s` y `c.get(k, ttl=0)` devolvía `{'v': 1}` en vez de `None`.
- **Causa raíz:** `(time.time() - st_mtime) >= ttl` sin acotar por abajo. En
  Windows ese reloj y el `mtime` de NTFS no comparten fuente ni granularidad. El
  arreglo del 2026-08-05 cambió `>` por `>=` y cerró `age == 0`, dejando abierto
  `age < 0`. El test de borde congela el reloj con `monkeypatch`, así que por
  construcción no podía producirlo.
- **Consecuencia:** el CI de `main` estaba **ROJO** desde el 2026-09-05T22:01
  (run 33994699340, `test-windows`: `1 failed, 1546 passed`) — la puerta de
  desarrollo cerrada. En producción el impacto es acotado: con `cache_ttl` de
  21600 s sólo importa ante un salto de reloj hacia atrás (NTP), que serviría
  cuotas pasadas de su TTL.
- **Corrección aplicada:** `max(0.0, time.time() - st_mtime)`. Acotar por abajo
  es la dirección segura: como mucho se refresca de más.
- **Prueba añadida:** `test_file_cache_expires_when_mtime_is_ahead_of_the_clock`.

### AUD-MED-002 · La promoción de calibradores instalaba en producción sin comprobar la muestra

- **Evidencia:** `REPRODUCIDO` · **Confianza:** HIGH
- **Componente:** `src/sqp/calibration/calibrator.py`, `promote_calibrators`
- **Activación:** una clave en el registro de staging cuyo `<key>_n_val.json`
  falta o no parsea.
- **Reproducción** (mismo candidato, **1 evento** de validación OOS):

  | Caso | Antes | Después |
  |---|---|---|
  | meta con `n_val_events=1` | rechazado | rechazado |
  | **sin** fichero de meta | **PROMOVIDO** | rechazado |
  | meta JSON corrupto | **PROMOVIDO** | rechazado |

- **Causa raíz:** `_load_staging_meta` devuelve `None` tanto para «no existe»
  como para «ilegible», y el guard estaba escrito `if meta is not None:`. Un
  **default-allow** dentro de la única puerta cuyo propósito declarado es «el
  guard que habría dejado fuera al candidato `n_val=9` del 2026-07-02», y
  contrario al resto del proyecto (`clv_gate` y `prediction_gate` deniegan por
  defecto ante un registro ausente).
- **La ventana no es teórica:** `train_calibration` llama a `_set_best_method`
  **antes** de `_write_staging_meta`; una interrupción entre ambas deja
  exactamente una clave staged sin metadato.
- **Ruta de exposición:** `scripts/promote_calibration.py --yes`.
  `auto_promote_calibrators` no estaba afectado (prefiltra por su cuenta).
- **Corrección aplicada:** `_motivo_muestra_insuficiente`, default-deny, con el
  motivo en el log. `force` sigue pudiendo saltarlo (es el guard de muestra, no
  el de defecto estructural, que no se salta ni con `force`).
- **Pruebas añadidas:** 3 (meta ausente, meta corrupto, contraprueba con `force`).
  No existía ninguna: `grep n_val_events tests/` sólo cubría metadatos presentes.

### AUD-MED-003 · Tres tareas programadas fallaban en silencio; la validación OOS lleva rota desde el 2026-09-01

- **Evidencia:** `VERIFICADO_ESTÁTICAMENTE` (la brecha) + estado observado (el fallo)
- **Componentes:** `VALIDATE_OOS.bat`, `BACKFILL_ALL.bat`, `CAPTURE_CLOSE.bat`,
  `REFRESH_ML.bat`, `scripts/run_status.py`
- **Estado observado** (`Get-ScheduledTaskInfo`, 2026-09-06):
  `SQP_Validate_OOS_Cdev` → `last=2026-09-01 12:00`, **`rc=0x1`**, `next=2026-10-01`.
- **Evidencia de la brecha:** sólo `SETTLE_ALL`, `RUN_DIARIO_ALL` y
  `DIARIO_COMPLETO` invocaban `run_status.py`; los demás terminaban su rama
  `:error` con un `echo`. Y `--stage` sólo admitía `{settle, run}`, así que ni
  siquiera podían registrarse. **Nada** lee `LastTaskResult` (`grep` sobre `src`,
  `scripts`, `*.ps1`, `*.bat`): el centinela es el único mecanismo.
- **Consecuencia:** la validación OOS mensual —la que vigila que los parámetros
  sigan generalizando— lleva cinco días fallada sin que el health check, el
  banner del tablero ni ninguna alarma lo señalen, y no se reintenta hasta el
  2026-10-01. Es el modo de fallo que `sqp/monitoring/run_status.py:3` documenta
  («el 2026-07-29 terminó con `LastTaskResult = 1` y nadie se enteró»),
  reaparecido en las tareas que quedaron fuera de la cadena diaria.
- **Corrección aplicada:** `STAGES` con seis etapas; las cuatro BAT registran
  fallo y limpian su propia etapa al terminar bien; el health check nombra la
  etapa y **el BAT a re-ejecutar**.
- **Pendiente:** la causa raíz del fallo del 2026-09-01 sigue
  **`NO_VERIFICABLE`**. `main()` devuelve 1 tanto por excepción como por la rama
  benigna «liga sin cuotas de cierre»; comprobado hoy que de **33 ligas
  descubiertas, 0** carecen de cierre utilizable, así que esa rama no lo
  explicaría hoy. Requiere `logs/validate_oos.log`, denegado por permisos.

---

## LOW

### AUD-LOW-001 · La verificación de integridad avisaba y cargaba igualmente

`_load_calibrator` registraba «integrity check FAILED … loading anyway» y hacía
`joblib.load` de todas formas: un control cuyo veredicto no cambia nada. Y
`joblib.load` es deserialización de pickle, así que cargar un artefacto que se
sabe alterado es lo contrario de lo que conviene hacer con ese indicio.

**Corregido:** devuelve `None` y el mercado se sirve **en crudo**, que es el
comportamiento seguro por defecto del módulo. Los tres consumidores ya absorbían
`None` como «sin modelo legible»; se añadió la comprobación que faltaba en
`apply_calibration` y en `pergame._staged_pergame_predict`. Sin sidecar sigue
cargando (compatibilidad con modelos anteriores al digest). 2 pruebas nuevas.

### AUD-LOW-002 · El hook de secretos no miraba ningún `.md`, y los `.md` sí se versionan

`check-secrets.sh` excluía `*.md` junto a los directorios de datos. Pero
`Obsidian/` y `docs/` **están rastreados por git**: una clave pegada en una nota
llegaba al commit. El patrón 4 del propio hook (`sk-…`, `Bearer …`) está pensado
justo para prosa.

**Corregido:** exclusión retirada. Medido antes de aplicarlo: **0 coincidencias
sobre los 297 `.md` rastreados**, así que no introduce falsos positivos.
Verificado end-to-end que un `.md` con `sk-…` ahora sale con `exit 2`.

### AUD-LOW-003 · Siete textos describían un estado que el código ya no tiene

Una sola causa raíz: comentarios y documentos que no se movieron con el código.

| Ubicación | Afirmaba | Realidad |
|---|---|---|
| `storage/lock.py` | los 120 s son por `fetch_probables` dentro del lock | `d27fdd4` sacó la red de la sección crítica |
| `audit/html_report.py` | «Existe aparte de *Picks del Día*» | `fae6cdc` fundió las dos vistas |
| `.gitignore` | el test carga `route-model.py` vía `importlib` | el test afirma que **no existe** |
| `REPO_DESCRIPTION.md` | tarea diaria «11:00» | 15:00 UTC; la hora local cambió con el horario de verano |
| `REPO_DESCRIPTION.md` | `settle_all.py --days-from 2` | el BAT usa `3` |
| `README.md` | `--days-from 2` | ídem |
| `CAPTURE_CLOSE.bat` + `REPO_DESCRIPTION.md` | captura «horaria» | `Repetition.Interval = PT30M` |

**Corregido** en los siete sitios. Los horarios pasan a expresarse en **UTC**: la
máquina opera en `Pacific SA Standard Time`, que cambia de −04:00 a −03:00, así
que la hora local de un `.bat` no es un dato estable.

### AUD-LOW-004 · El `Dockerfile` afirmaba una paridad que no tiene y nadie lo construye

`FROM python:3.11-slim` con el comentario «mismas versiones que produccion/CI»,
cuando producción corre 3.14 (los `.bat` fijan `SQP_PYTHON` a Python314, y por
eso CI añadió esa pata). Además `ci.yml` no tiene ningún paso de docker build.

**Corregido parcialmente:** se declara explícitamente que la imagen es de **demo
y referencia**, no réplica de producción, y que nadie la construye. **No** se
alineó la base a 3.14: cambiar la imagen base sin poder construirla introduciría
un riesgo no validado, y un `Dockerfile` roto es peor que uno desfasado. Queda
en `BACKLOG.md`.

### AUD-LOW-005 · Diez features no recibían fecha de corte; la protección contra fuga vivía entera en el llamador

`team_rest_days` recibía `reference_date` y descartaba `d >= ref`. Sus diez
hermanas (`team_recent_form`, `team_streak`, `team_avg_margin`, `team_over_rate`,
`team_h2h_form`, `team_avg_total`, …) tomaban «las últimas n» de la lista que les
dieran. `build_adjustment_context` recibía `ref_date` y **sólo se lo pasaba a
`team_rest_days`**.

**No había fuga activa**, y así se verificó: los dos únicos consumidores recortan
antes —el backtest con `roi_engine._prior_games` (`d < rd`, estrictamente
anterior) y el run diario con partidos ya terminados—, y además la capa está
inerte (todos los coeficientes a 0 desde el 2026-09-01). El riesgo era que un
tercer consumidor introdujera look-ahead en diez features a la vez, sin aviso.

**Defecto asociado, éste sí real:** las cuatro tasas de victoria dividían por
`len(recent)` pero saltaban con `continue` las filas de marcador ilegible, así
que esas contaban como **derrota**. Con 4 victorias y una fila rota, un equipo
con pleno salía 0,80.

**Corregido:** helper `_hasta()`, `reference_date` opcional en las diez, y
`ref_date` propagado desde `AdjustmentContext`. Divisor = filas realmente leídas,
con el mismo umbral de 2. **10 pruebas nuevas**, incluida la que demuestra que
sobre una lista ya recortada el filtro es un **no-op exacto** — que es lo que
hace seguro añadirlo a un pipeline en producción.

---

## Inferidos (no confirmados, no corregidos)

**AUD-INF-001 · Carrera del lock huérfano.** `storage/lock.py` rompe un `.lock`
a los 300 s y el titular, al salir, hace `lock.unlink()` sin comprobar que siga
siendo suyo: podría borrar el candado de un tercero. *Falta la condición
necesaria:* no se encontró ninguna sección crítica capaz de superar 300 s desde
que `d27fdd4` sacó la red fuera. Severidad potencial HIGH, confianza LOW.

**AUD-INF-002 · Temporales de nombre fijo.** `clv_gate.write_clv_gate` y los dos
escritores de `promotion_log.csv` usan `with_suffix(".tmp")` fijo, el patrón que
`atomic_write_csv` abandonó por colisión entre escritores concurrentes. *Falta
la condición:* los tres los escribe un único proceso diario.

---

## Falsos positivos descartados

| Sospecha | Evidencia que la refutó |
|---|---|
| `_json_para_script` definido y nunca usado → AUD-003 sin cerrar | se invoca en `html_report.py:926`; el primer `grep` usó un nombre equivocado |
| `discover_leagues_with_odds` rompe con ids con `_` (`frauen_bundesliga`) | usa `rsplit("_", 1)`: parte por el último separador |
| La tarea diaria se desplazó de 11:00 a 12:00 | horario de verano de Chile; `StartBoundary 12:00-03:00` mantiene la hora UTC |
| `train_calibration` degrada a split por filas si falta `group_col` | los tres llamadores construyen `event_id` explícitamente |
| El backtest evalúa las features de ajuste con partidos futuros | `_prior_games` filtra `d < rd` |
| `run-tests-on-stop.sh` no limpia el centinela al fallar | correcto: el trabajo sigue pendiente, y `stop_hook_active` evita el bucle |
| `promote_calibrators` copia el modelo sin validar el sidecar | `calibrator_defect` lo bloquea antes, incluso con `force` |
| La suite escribe en el árbol `data/` real (detectado en fase 5: 37 ficheros con mtime posterior a la apertura) | Aislación deliberada y **consistente**. De los 37, la mayoría son del `SQP_Capture_Close_Cdev` de las 10:30/11:00 (producción normal, ajena a esta sesión). El resto los escriben los tests `slow` que llaman a `run_league(..., mode="demo")` con el `Settings.load()` real, y caen bajo `data/predictions/demo/` y `data/calibration/demo/`. **Los 11 puntos de lectura de vistas y pipeline usan `glob()` no recursivo, nunca `rglob()`**, así que el subárbol `demo/` es estructuralmente invisible; además esas filas llevan `data_label == "demo_synthetic"` y `bankroll._settled` sólo suma `"real"`. Verificado en `audit/report.py:83`, `html_report.py:591,719`, `calibration/data.py:183`, `cleanup.py:99`, `closing_capture.py:35`, `daily.py:319`, `intraday_scan.py:89`, `revalidation.py:171`, `served_store.py:75,81` |

---

## Auditoría independiente concurrente (FUERA de este alcance)

Durante esta sesión (mtime **10:58**, sin intervención de esta sesión) un proceso
externo de Codex reescribió `auditoria-integral-codex.md` con una auditoría nueva
del **mismo commit** `01993fd`, fechada 2026-09-06. Reporta **tres HIGH y tres
MEDIUM**, todos `REPRODUCED`, y corrobora la misma línea base (1547 passed, 1
skipped; ruff y mypy limpios; cobertura 89,64 %).

| ID Codex | Sev. | Asunto |
|---|---|---|
| AUD-20260906-01 | HIGH | Corrupción **parcial** del ledger infla la banca (`_exigir_pnl_legible` sólo actúa si NO queda ningún PnL numérico) |
| AUD-20260906-02 | HIGH | La liquidación puede perder escrituras concurrentes |
| AUD-20260906-03 | HIGH | El gate cuenta varias líneas del mismo partido como ensayos independientes |
| AUD-20260906-04 | MEDIUM | El backtest cruza resultados de partidos del mismo día |
| AUD-20260906-05 | MEDIUM | Actualizar abridores no invalida la caché de features MLB |
| AUD-20260906-06 | MEDIUM | Offline omite el límite de frescura y permite candidatos live con cuotas vencidas |

**No están corregidos: quedan fuera de la aprobación de esta sesión**, que cubría
los confirmados de *este* informe. Se comprobó que **ninguno colisiona** con los
parches aplicados:

- El de offline (`06`) actúa en `odds_api.py:143` (`ttl = inf` en modo offline),
  no en la línea de `odds_cache.py` que se cambió; con `ttl = inf` la condición
  de caducidad ni se evalúa, así que el nuevo `max(0.0, …)` no lo altera.
- El del backtest (`04`) es un defecto del *matcher* y de `adapter.observe`,
  mecanismo distinto del de AUD-LOW-005; el cambio de features es un no-op sobre
  la salida de `_prior_games`.
- Los otros cuatro tocan ficheros que esta sesión no modificó.

**AUD-20260906-01 es un hallazgo legítimo que esta auditoría no encontró:** se
leyó `bankroll.py` y se dio por suficiente el guard de `_exigir_pnl_legible`, que
sólo cubre el fichero **totalmente** ilegible. La corrupción parcial atraviesa el
`fillna(0.0)` y convierte una pérdida en un movimiento de cero. Recomendación:
tratarlo como el primer punto del siguiente ciclo.
