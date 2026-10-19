# VALIDATION — remediación de la ronda `audit-2026-10-18`

Evidencia real ejecutada por el implementador (Opus) entre el 2026-10-18 y el 2026-10-19. No sustituye a la verificación independiente.

## Global (sobre el árbol final del commit)

| Comando | Resultado |
|---|---|
| `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-r1018-full3` (suite completa) | **3367 passed, 1 skipped, 6 warnings, rc=0** (47 min 49 s). Los 6 warnings son el `RuntimeWarning` esperado de `tie_adds_goal` con totales sintéticos de exactamente 1,0 en `tests/test_market_tuning.py` |
| `ruff check src scripts tests` | All checks passed |
| `mypy src` | Success: no issues found in 114 source files |
| `python scripts/sync_agent_instructions.py --check` | synchronized |
| `python scripts/scan_tracked_secrets.py` | Sin literales de credencial en los ficheros rastreados (rc 0) |
| `pip-audit -r requirements.lock --no-deps --disable-pip` | No known vulnerabilities found |

## Historial de ejecuciones intermedias (lo que falló y cómo se resolvió)

| Ejecución | Resultado | Clasificación |
|---|---|---|
| Suite completa n.º 1 (con `timeout 3000`) | Cortada en torno al 60 % por el timeout; host cargado por la revisión de Fable | ENVIRONMENTAL_FAILURE: sin veredicto |
| Hook Stop (suite rápida) tras AUD-001 | `test_nhl_tilt_activation::test_lower_tilt_shrinks_the_favourite_without_moving_the_total`: 0,5464 frente a 0,5536 | NEW_REGRESSION, prevista por el modelo: con el gol de empate, el total depende del reparto. Test ajustado con revisión de Fable |
| Suite completa n.º 2 | **17 failed, 3344 passed, 1 skipped** | NEW_REGRESSION: guarda de saturación (`test_market_tuning`, 7) y mediciones congeladas (`measure_totals_recency` 6, `measure_tilt_nhl` 3, `measure_adjustment_battery` 1). Resueltas en la tercera ronda (`CHANGES.md`) |
| Ficheros afectados tras la tercera ronda | battery + recency + tilt + distributions + results_backfill: 236 passed | — |
| Suite completa n.º 3 | 3367 passed, 1 skipped | PASS |

## Pruebas discriminantes por ID (fallan antes y pasan después)

Comprobado cambiando temporalmente el fichero corregido por su versión de `HEAD` y restaurándolo después.

| ID | Antes (HEAD) | Después |
|---|---|---|
| AUD-004 | `test_aud004_escapes_are_blocked`: 9 de 9 fallan | 104 passed (fichero completo, primera ronda); 19 passed en `-k aud004` tras la segunda |
| AUD-007 | `test_crossreview_lento_*` falla | 6 passed (`-k crossreview`) |
| AUD-012 y AUD-006 (hook) | `-k "aud012 or scanned_too"`: 10 fallan | 78 passed (test_audit_hooks + test_hook_targets) |
| AUD-011 | `test_la_suite_no_escribe_en_el_log_de_produccion` falla | 4 passed |
| AUD-016 | `test_the_lock_pins_the_whole_installed_closure` falla con el lock anterior | 1 passed |
| AUD-003 | `-k aud003`: 5 fallan | 21 passed en la primera ronda; 46 passed con distribuciones tras la segunda |

Otros:
- **AUD-001:** error de P(Over) frente al histórico NHL (n=4.658) por debajo de 2 pp en 4,5/5,5/6,5/7,5: −0,017, −0,005, −0,001 y +0,011. Antes llegaba a 4,5 pp.
- **AUD-002, 008, 009, 010, 013, 014, 005 y 017:** tests nuevos en verde. El vigilante de AUD-005 se ejecutó en vivo: «El run diario se lanzo en su disparador».

## Mediciones sobre datos reales (solo agregados)

- **AUD-003:** filas descartadas al leer: mlb 15, ncaab 31, wncaab 95, atp 2, wta 3, ligamx 1 y ucl 1. El partido 716404 queda en 2023-10-02, la fecha de la reanudación.
- **AUD-008:** filas de línea de cuarto antes del corte: 572, con 8 medias liquidaciones. Después del corte: 284, con 80. En el ledger hay 58 filas de cuarto y se excluyen 27.
- **AUD-001:** λ medio NHL 6,158; factor de ritmos reglamentarios c = 0,973.

## Acciones externas verificadas

- `gh api … security_and_analysis`: `secret_scanning: enabled` y `secret_scanning_push_protection: enabled`.
- `gh issue close 4` hecho; `gh issue list --label ci-rojo --state open` devuelve `[]`.

## No verificado

- CI en GitHub con el lock ampliado y los jobs nuevos: no hubo push.
- `logs/` y `.env`: lectura denegada por permisos.
- Instantánea H de recencia: inexistente (KI-075).
