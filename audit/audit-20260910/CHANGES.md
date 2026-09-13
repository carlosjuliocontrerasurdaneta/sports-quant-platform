# Cambios — Fase 4, auditoría integral 2026-09-10

Autorización: aprobación explícita del operador de **todos los hallazgos
confirmados** más las mejoras sustentadas por la evidencia de la auditoría.
Base: paquete `sports-quant-platform-local-optimization-20260910`, íntegro
(654/654 SHA-256) al empezar.

**82 ficheros modificados, 3 ficheros de test nuevos.** Ni un cambio de
parámetro de riesgo, `pick_mode`, `shadow_mode`, calibrador, umbral de gate,
modelo, estrategia ni dato histórico de picks. La única escritura sobre datos
fue retirar dos filas fabricadas (AUD-HIGH-005), con copia de seguridad.

## Efecto del hook de formato

El hook `PostToolUse` (`.claude/hooks/post-edit-format.sh`) ejecuta
`ruff check --fix` tras cada `Edit`/`Write`. Intervino de forma observable una
vez: retiró un `from sqp.config import ROOT` que quedó sin uso en
`tests/test_probable_pitchers_series.py` (F401). Se revisó el diff: no tocó
lógica en ningún fichero.

## HIGH

| ID | Cambio | Ficheros |
|---|---|---|
| **AUD-HIGH-001** | 21 comprobaciones `if errorlevel 1` → `if %ERRORLEVEL% neq 0` en 9 BATs (`>= 1` no ve códigos negativos). La rama del `git fetch` pasa a comparación EXACTA (`=="124"` / `not =="0"`), que separa el 124 del plazo del 128 de git. Candado de clase nuevo que recorre los BAT del disco y prohíbe la forma antigua (ignorando líneas `REM`). | 9 `.bat`, `tests/test_run_status.py` |
| **AUD-HIGH-002** | Sin cambio de código: la causa raíz (KI-034, liga sin resultados) ya estaba corregida en `scripts/validate_oos.py:225-237`. Falta cerrar el ciclo ejecutando la puerta. | — |
| **AUD-HIGH-003** | Subrutina `:salud` que ejecuta `scripts/health_check.py`, cableada en las **cuatro** salidas del orquestador (correcta + `:error_arbol` + `:error_settle` + `:error_run`), best-effort y sin alterar el código de salida. Candado que exige su presencia en las tres ramas de error. | `DIARIO_COMPLETO.bat`, `tests/test_run_status.py` |
| **AUD-HIGH-004** | Los dos asserts por subcadena de `inspect.getsource` sustituidos por tests de comportamiento: cliente falso con `cache_ttl=21600` → se exige 5400; contraprueba de que un TTL ya estricto NO se relaja; espía sobre la construcción real del cliente de cierre. Docstring corregido: la garantía de `force_refresh` cubre la ruta de producción, no la inyección. | `tests/test_frescura_cuotas_diario.py` |
| **AUD-HIGH-005** | `_attach_probable_pitchers` acepta `root=` (default: `ROOT`), así que el destino de escritura deja de ser un global. Fixture `autouse` que redirige `daily.ROOT` en todo el módulo de tests. Regresión que exige que la escritura caiga en el root inyectado y NO en el del módulo. **Dato**: retiradas 2 filas sintéticas ("Game1/Game2 Home Ace", `confirmed_at_utc` 2026-08-23T02:03:09Z) de `data/historical/pitcher_confirmation_log_mlb.csv` (231 → 229 filas), con copia en `.pre-AUD-HIGH-005-20260910.bak`. | `src/sqp/pipeline/daily.py`, `tests/test_probable_pitchers_series.py`, 1 CSV |

## MEDIUM

- **AUD-MED-001**: `BetCandidate` gana `home`/`away` (default `""`, compatible hacia atrás); `daily` los rellena; `_attach_event_meta` pasa a RELLENAR y no PISAR, para que un evento ausente del payload de /scores no borre una identidad que el pick sí tenía. La guarda anti-fabricación de `settle._grade` queda activa en la ruta del dinero.
- **AUD-MED-002**: `_league_meta` valida el id contra `[a-z0-9_]+` (el id viene de una respuesta remota y compone rutas). `_active_tennis` filtra con el mismo alfabeto y AVISA de lo descartado, para no tumbar el run ni perder un torneo en silencio. 15 tests.
- **AUD-MED-003 / -004**: reescrito el bloque de `shadow_mode` en `configs/default.yaml` (nombraba al gate de CLV como barrera vinculante estando desactivado; lo es `prediction_gate`); anotada en el pre-registro del 2026-08-16 la supersesión de la unidad de inferencia del 2026-09-06.
- **AUD-MED-007**: documentada en `pyproject.toml` la rotura real de `--cov` en 3.14 y que la cobertura sólo se mide en la pata 3.12.
- **AUD-MED-008**: `labels.cargar_stream_servido` como cargador canónico; los tres consumidores delegan. Se adopta el comportamiento tolerante (una liga ilegible no quita de la lista a las demás) y se registra un aviso.
- **AUD-MED-009**: `sports-analytical-system` y `edge-ranking` alineadas con `configs/default.yaml`; retirado `profit_garantizado`; `edge-ranking` reescrita para cubrir los 6 deportes y no truncar la lista.
- **AUD-MED-010**: `full-audit` declara `audit/latest/` como su entregable y obliga a preservar la ronda anterior.
- **AUD-MED-011**: 4 tests para las ramas de movimiento adverso, velocidad y dispersión entre casas, cada una cruzando y sin cruzar su umbral, más la no-op con coeficientes a 0.
- **AUD-MED-012**: `ml_train._persist` escribe el sidecar `.sha256`; `ml_predict._check_hash` pasa de avisar-y-cargar a **negarse**. 3 tests, incluida la contraprueba del artefacto legado sin sidecar.
- **AUD-MED-013**: `.mypy_cache/` y `.ruff_cache/` a `.gitignore`.
- **AUD-MED-014**: `.claude/CLAUDE.md` recoge la excepción de los loops, que es lo que fija el test de contrato.
- **AUD-MED-015**: documentado en el punto del import diferido que sostiene el ciclo de 5 módulos.
- **AUD-MED-016**: 3 asserts tautológicos endurecidos (valor exacto de la penalización, `math.isfinite` + rango, y el test de consola que no tenía ningún assert).
- **AUD-MED-017**: `shell=True` retirado de los dos lanzadores; el shim `.cmd` se invoca por `%COMSPEC% /c` sólo cuando corresponde. `timeout` añadido al lanzador V1.
- **AUD-MED-018**: `backtesting.tuning.temporal_cutoff` como implementación canónica; los dos scripts OOS delegan. 6 tests, incluido uno de clase que detecta una recopia.
- **AUD-MED-019**: `IMPLEMENTACION.md` dice ahora que el guard NO protege un árbol extraído del ZIP y avisa de respaldar `data/` y `.env`.
- **AUD-MED-020** (nuevo, Fase 4): `snapshot_v2._run` deja de heredar `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE`.

## LOW (aplicados)

Falso positivo del hook de secretos sobre marcadores en español (con
contraprueba de que sigue detectando un secreto real); hora real 12:00 corregida
en 4 ficheros; contrato de aborto de `README.md` precisado; rutas
`historical/`/`exports/` → `data/…` en 3 ficheros; referencia rota al protocolo
Obsidian; afirmación obsoleta sobre los hooks declarados; aviso al caer a
`python` del PATH en los 8 BATs; `permissions: contents: read` en CI;
`pytest-cov`/`coverage` pineados en el lock; `weather_timeout_s` → mayúsculas;
`tests/settlement/__init__.py`; `clv_gate` con JSON de raíz no-dict;
`promote_calibration` verifica el digest; frontmatter YAML válido en los 60
ficheros de agentes y skills.

## Lo que se decidió NO tocar

- **Pin de las acciones de CI a SHA**: requiere red para obtener los digests. No
  se inventan. Queda abierto.
- **Contrato de `temporal_cutoff` con lista vacía**: sigue lanzando `IndexError`.
  Lo cambié y un test existente lo cazó; el hallazgo aprobado era la
  DUPLICACIÓN, no la semántica, y `validate_oos.py` ya evita llegar ahí.
- **`AGENTS Tipster.md`**: no se elimina (5 referencias por nombre y sin Git para
  revertir). Se marca la fuente canónica y la dirección de propagación.
- **`docs/superpowers/`, `docs/AUDIT-2026-06-14.md`, `audit/*`**: conservados.
- **Parámetros de riesgo, gates, calibradores, modelos y datos históricos de
  picks**: intactos, salvo las 2 filas fabricadas de AUD-HIGH-005.
