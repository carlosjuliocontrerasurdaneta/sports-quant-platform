# Validación — Fase 5, auditoría integral 2026-09-10

Entorno: Windows 11, **Python 3.14.4** (el intérprete real de producción), numpy
2.4.4, pandas 3.0.2, scipy 1.17.1, scikit-learn 1.9.0, pytest 9.0.3, ruff 0.15.14,
mypy 2.1.0. Coinciden **exactamente** con `requirements.lock`.

Línea base (antes de tocar nada): **1929 passed, 1 failed, 1 skipped** en
2.422,71 s. El fallo de partida se investigó y era ambiental (ver más abajo).

## Comandos y códigos de salida reales

| # | Comando | Resultado | Código | Clasificación |
|---|---|---|---|---|
| 1 | `python -m ruff check src scripts tests` | All checks passed | **0** | PASO |
| 2 | `python -m mypy src` | no issues in 101 source files | **0** | PASO |
| 3 | `python -m pytest -q -p no:cacheprovider --basetemp=<exclusivo>` (suite completa) | **1964 passed, 1 failed, 1 skipped** en 1.595,72 s | 0 | ver nota (A) |
| 4 | `python -m pytest -q -m "not slow" --basetemp=<exclusivo>` (tras corregir (A)) | **1741 passed, 225 deselected** en 508,34 s | **0** | PASO |
| 5 | `pytest tests/test_prediction_gate.py tests/test_config_yaml_keys.py tests/test_audit_2026_07_29.py` | 93 passed | **0** | PASO — cierra (A) |
| 6 | Verificación de integridad contra `BUILD_INFO.json` antes de la Fase 4 | 654/654, 0 divergencias, 0 faltantes | 0 | PASO |
| 7 | Banco `cmd.exe` con las **líneas reales parcheadas** de `DIARIO_COMPLETO.bat` | `-1073741510` → ABORTA; `0` → continúa; fetch: 124→plazo, 128→fallo, 0→sin aviso | 0 | PASO |
| 8 | Mutación del techo de frescura (comentar `client.cache_ttl = acotado`) | test en ROJO; restaurado por SHA-256 → verde | — | PASO (discriminante) |
| 9 | `bash -n instalar-candados.sh` + los 7 hooks | sintaxis OK | **0** | PASO |
| 10 | Parser de PowerShell sobre los 2 `.ps1` editados | sintaxis OK | **0** | PASO |
| 11 | Hook `check-secrets.sh`: marcador vs secreto real | marcador → 0, secreto → 2 | — | PASO (contraprueba) |
| 12 | `schtasks /query` (solo lectura) | 5 tareas `SQP_*` | **0** | PASO |
| 13 | `cmd /c VALIDATE_OOS.bat` | — | — | **NO_EJECUTADA** |

### (A) El único fallo, y su tratamiento

`tests/test_prediction_gate.py::test_ningun_documento_presenta_el_alpha_de_familia_como_umbral_por_mercado`.

**REGRESIÓN_INTRODUCIDA**, y mía: al reescribir el bloque de `shadow_mode` de
`configs/default.yaml` (AUD-MED-003) escribí el umbral como `p < 0,05/41`, y el
candado —correctamente— lee ahí el alpha de FAMILIA presentado como umbral por
mercado. Corregido: ahora dice `p < 0,00122`, nombrando aparte el reparto de
Bonferroni. Verificado en verde por los comandos 4 y 5.

La corrección de la corrección la detectó un candado de clase que el propio
proyecto ya tenía escrito. Funcionó exactamente para lo que existe.

### Fallo de la línea base: era ambiental

`test_snapshot_v2.py::test_staged_mode_survives_into_both_trees` falló en la
suite de partida con `git write-tree failed (128): not a git repository`, y
pasaba aislado y con su módulo completo. Diagnóstico: el agente de QA de esta
misma auditoría ejecutó pytest contra el **mismo `--basetemp`** mientras mi suite
estaba en vuelo, y pytest borra y recrea ese directorio al arrancar: le quitó los
repositorios git a mitad de ejecución. **Confirmado**: en la ejecución final con
`basetemp` exclusivo ese test **pasa**. Clasificación: `ENVIRONMENTAL_FAILURE`,
no defecto del proyecto. AUD-MED-005 se mueve a falsos positivos descartados.

## Cobertura de tests

1.931 tests de partida → **1.966** (+35). La suite tarda 26:35 sin contención
(40:22 con ella). `-m "not slow"` deselecciona 225 y corre en 8:28.

## Validaciones NO ejecutadas, y por qué

- **`VALIDATE_OOS.bat`**: bloqueada por el clasificador de permisos de la sesión.
  No se rodeó. Es la validación operativa de AUD-HIGH-002 y queda como B-01.
- **Suite completa después del arreglo de (A)**: se corrió la vía rápida (1.741
  tests, 0 fallos) y los tests específicos del fallo. Los 225 `slow` se
  validaron por módulo durante la Fase 4 (`test_snapshot_v2.py`: 35 passed,
  exit 0) pero **no se re-ejecutaron todos juntos** tras el último cambio, que
  es un comentario de YAML. Se declara en vez de darse por hecho.
- **`pip-audit`**: requiere red.
- **Estado del CI**: sin `.git`, no verificable.
- **Cobertura (`--cov`)**: rota en 3.14 (numpy). Se mide en la pata 3.12 del CI.
- **Docker**: no se construyó la imagen.

## Lo que esta validación NO acredita

No se midió Brier, ECE, CLV, hit rate observado ni ROI realizado, y no se afirma
nada sobre ninguno. Una suite verde acredita que los defectos corregidos no
reaparecen; **no acredita ventaja predictiva ni rentabilidad**.
