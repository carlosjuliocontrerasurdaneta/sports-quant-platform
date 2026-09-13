# Validaciones ejecutadas — Auditoría integral 2026-09-13

Todas de solo lectura o aisladas. Ninguna llamada externa de pago, ninguna
escritura en `data/` (verificado por mtimes), ningún cambio de configuración.

| # | Comando | Propósito | Resultado | Efectos observados | Limitaciones |
|---|---|---|---|---|---|
| 1 | `git rev-parse --is-inside-work-tree` | estado Git | `fatal: not a git repository` | ninguno | — |
| 2 | verificación SHA-256 contra `audit/latest/POST-REMEDIATION-HASHES.json` (comando documentado en el propio JSON) | integridad de partida | 4 rutas fuera: `.claude/.tests-pending`, `.claude/memory/project-decisions.md`, `.claude/memory/session-summaries.md`, `Obsidian/Bitácora/2026-09-11.md` | ninguno | — |
| 3 | verificación SHA-256 contra `BUILD_INFO.json` | divergencia respecto al paquete | 654 hashes: 92 divergen, 0 faltan, 15 nuevos | ninguno | — |
| 4 | `gh auth status`; `gh repo list`; `gh run list --branch main --limit 8`; `gh issue list --label ci-rojo`; `gh api repos/…/branches`, `…/commits`, `…/git/trees/a401f06?recursive=1` + SHA-1 de blob local | estado real del CI y comparación árbol↔`main` | `main = a401f06`, 8/8 runs `success`, 2 issues `ci-rojo` cerrados; 538 iguales / 94 difieren / 41 sólo locales | ninguno (lectura) | — |
| 5 | `ruff check src scripts tests` | lint | `All checks passed!` (exit 0) | ninguno | — |
| 6 | `mypy src` | tipos | `Success: no issues found in 101 source files` (exit 0) | `.mypy_cache` ya existía | — |
| 7 | `PYTHONPATH=src pytest -q -m "not slow" -p no:cacheprovider --basetemp=<scratchpad>` | suite rápida | **1741 passed, 225 deselected, 396,58 s** (exit 0) | escrituras sólo en `data/predictions/demo/`, `data/calibration/demo/` | — |
| 8 | `PYTHONPATH=src pytest -q -m slow -p no:cacheprovider --basetemp=<scratchpad>` | suite lenta | **224 passed, 1 skipped, 725,12 s** (exit 0) | ídem | skip: `node` ausente |
| 9 | `Get-ScheduledTask`/`Get-ScheduledTaskInfo` (SQP_*), `Get-CimInstance Win32_Process` | inventario y estado de tareas | ver EXECUTIVE_SUMMARY; `SQP_Validate_OOS_Cdev` rc 1; `SQP_Capture_Close_Cdev` rc 0x800710E0 | ninguno | log operativo del Programador vacío |
| 10 | `Settings.load()` programático (sin imprimir secretos) | configuración efectiva | valores en EXECUTIVE_SUMMARY; `.env` presente, clave configurada | carga `.env` en el proceso auxiliar | `.env` no leído como texto |
| 11 | escaneos programáticos de `data/bets/settled_*.csv`, `data/calibration/graded_*.csv`, `data/predictions/archive/*.csv`, `data/historical/results_*.csv` (sólo agregados) | AUD-MED-001/002/003/004, AUD-FP-007 | 1.360 liquidadas (0 duplicadas, 0 pnl NaN); 24.324 graduadas; reval 195/369 vs 2/115; 22 líneas de cuarto (1 mal graduada); 150/730 unidades sin veredicto (132 + 18) | ninguno | 6 filas sin marcador histórico |
| 12 | `structural_defect` sobre los 6 `data/models/*_calibration_*.joblib` live | estado de calibradores | 5 sanos; `wnba_totals_iso` colapsado (0,490) e inerte | `joblib.load` (deserialización local) | — |
| 13 | medición `pd.concat` de `data/odds/odds_mlb_*.csv` | AUD-LOW-003 | 1.587.980 filas, 9,1 s, 342 MB | ninguno | — |
| 14 | tamaños por familia de artefactos (`glob` + `getsize`) | AUD-LOW-002 | ver FINDINGS | ninguno | — |
| 15 | verificación de frontmatter de 26 skills y 27 agentes; búsqueda de rutas referenciadas inexistentes en `.claude/**/*.md` | sistema de Skills | 1 BOM (descartado); 2 nombres de fichero ≠ `name` (funcionan); 12 rutas históricas muertas | ninguno | — |
| 16 | grep dirigidos: `requests.get` sin timeout, `shell=True`, `yaml.load`, `eval`, `pickle`, claves literales | seguridad | 0 hallazgos reales (1 falso positivo) | ninguno | — |
| 17 | mtimes de `data/**` tras las suites | aislamiento de tests | 16 ficheros bajo `demo/`; 3 no-demo tocados por la captura de cierre real (08:06) | ninguno | — |

**No ejecutado, y por qué**: `codex review` (cuota de pago), `pip-audit` (red),
`VALIDATE_OOS.bat` (escribe informes/logs en producción; pendiente del
operador, B-01), cualquier script de backfill/run (cuota de API), lectura de
`logs/**` y `.env` (regla `deny`).

---

# Fase 5 — Validación final (2026-09-13, tras las correcciones)

Línea base (`MANIFEST.json` → `tests_initial`): fast 1741 passed / slow 224 passed, 1 skipped; ruff y mypy limpios.

| # | Comprobación | Comando | Resultado | Clasificación |
|---|---|---|---|---|
| F1 | Prueba específica AUD-MED-001 | `pytest tests/test_revalidation.py` | 24 passed | PASO |
| F2 | Prueba específica AUD-MED-002 | `pytest tests/test_settle_candidates.py` | 32 passed | PASO |
| F3 | Prueba específica AUD-MED-003 | `pytest tests/settlement/test_superseded_picks.py` | 4 passed | PASO |
| F4 | Prueba específica AUD-MED-004 | `pytest tests/test_cleanup.py tests/settlement/test_settle_tennis_e2e.py` | 23 + 11 passed | PASO |
| F5 | Candado AUD-MED-005 + simulación del BAT real con stubs (scratchpad) | `pytest tests/test_run_status.py`; `cmd /c DIARIO_COMPLETO.bat` con `SETTLE_ALL`/`RUN_DIARIO_ALL` simulados | 63 passed; ruta OK: exit 0, 3×`daily_picks` + `tipster` + `health`, 3 `--clear`; ruta run-fallo: exit 1, mismas 4 vistas, `--fail`, 0 `--clear` | PASO |
| F6 | Pruebas AUD-MED-007 | `pytest tests/test_hook_targets.py tests/test_claude_model_routing.py tests/test_claude_system_contract.py` | 32 + 63 passed (tras redactar el mensaje del hook sin el literal `codex review`: los 2 candados textuales fallaron primero y se corrigió el hook, no el test); `bash -n` del hook OK | PASO (REGRESIÓN_INTRODUCIDA corregida en la misma fase) |
| F7 | Prueba AUD-HIGH-002 (script real de PowerShell en root temporal) | `pytest tests/test_open_dashboard.py` | 4 passed; parser de PowerShell sin errores | PASO |
| F8 | Pruebas AUD-LOW-001/002/003 | `pytest tests/test_cleanup.py tests/test_line_movement.py` | 23 + 14 passed | PASO |
| F9 | Estáticas | `ruff check src scripts tests` / `mypy src` | exit 0 / exit 0 (101 ficheros) | PASO |
| F10 | Suite rápida completa | `PYTHONPATH=src pytest -q -m "not slow" -p no:cacheprovider --basetemp=<scratchpad>/pytest-fast2` | 1787 passed, 225 deselected, 329 s (la primera pasada dio 2 failed por F6; corregido y re-ejecutados los ficheros afectados en verde) | PASO |
| F11 | Suite lenta completa | `PYTHONPATH=src pytest -q -m slow -p no:cacheprovider --basetemp=<scratchpad>/pytest-slow2` | 224 passed, 1 skipped, 591 s, exit 0 | PASO |
| F12 | Revisión independiente escalón `fable` de AUD-MED-002/003/004 (contrato del ledger) | subagente `general-purpose`, `model: fable`, solo lectura | 0 defectos CONFIRMADOS; 6 puntos DESCARTADOS con evidencia; 1 INFERIDO menor (duplicar el literal de `HALF_RESULTS` en `bankroll.py`) → aplicado (`from sqp.settlement.settle import HALF_RESULTS`), sin ciclo de import, 74 tests en verde | PASO |
| F13 | Diff final | `git diff --check` sobre el repositorio reconstituido | sin errores de espacio en blanco; avisos CRLF→LF esperados por `.gitattributes` (`text=auto eol=lf`) | PASO |
| F14 | Coherencia de configuración / manifiestos / lockfile | inspección: `configs/default.yaml`, `pyproject.toml`, `requirements.lock` sin cambios en esta fase | sin cambios | PASO |
| F15 | Ficheros `.bat` (no cubiertos por pytest salvo candados) | simulación F5 para `DIARIO_COMPLETO.bat`; el resto no se tocó | — | PASO (DIARIO) / NO_EJECUTADA (resto, sin cambios) |
| F16 | Reconstitución del repositorio (AUD-HIGH-001) | `git init`; `remote add`; `fetch`; `update-ref`+`symbolic-ref`; `read-tree HEAD`; `git status` | 107 M + 32 ?? (incluye esta fase); ningún fichero de `data/`, `logs/`, `.env` ni `settings.local.json` | PASO |
| F17 | Commit + push de la rama + PR | ver MANIFEST.json (`git_commit`, `pr_url`) | — | ver MANIFEST.json |

**Regresiones introducidas**: una (F6, dos candados textuales del hook de revisión cruzada), corregida en la misma fase. **Fallos preexistentes**: ninguno. **No ejecutado**: `codex review` (cuota), `pip-audit` (red), `VALIDATE_OOS.bat` (operador, B-01), cambio del Programador de tareas (operador).
