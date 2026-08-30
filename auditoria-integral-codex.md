# Auditoría integral independiente — Sports Quant Platform

**Fecha:** 2026-08-28  
**Auditor:** Codex  
**Repositorio:** `C:\dev\3\sports-quant-platform`  
**Rama y revisión:** `main`, `cb42fed`  
**Estado respecto del remoto:** 10 commits por delante de `origin/main` (`53ce230`)  
**Resultado:** **NO PASS — 1 hallazgo MEDIUM**

## Resumen ejecutivo

Se auditó de forma independiente la arquitectura, configuración, código fuente, scripts operacionales, controles de calidad y pruebas del proyecto. La revisión prestó especial atención a ingestión de cuotas y resultados, timestamps, vigencia de cuotas, cálculo no-vig, probabilidades, calibración, aislamiento temporal, backtesting, sizing Kelly, gates de riesgo, settlement, persistencia concurrente y exposición de secretos.

Se encontró un defecto concreto: la configuración local activa un modelo distinto del autorizado por la política versionada y hace fallar el test contractual correspondiente. No se encontró evidencia concreta de defectos críticos o altos, ni de leakage temporal, look-ahead bias, contaminación train/test, cálculo probabilístico inválido, uso de cuotas posteriores al comienzo o exposición de credenciales en archivos versionados.

La suite rápida restante pasa por completo: **1098 pruebas aprobadas**. El test integral se detiene en el único fallo descrito tras **229 pruebas aprobadas**. `ruff` pasa. `mypy` no pudo producir un resultado por un problema de acceso a su base de caché local, no por un diagnóstico de tipos del código.

## Hallazgos

### SQP-AUD-001 — MEDIUM — La configuración activa contradice la política autorizada y rompe la puerta de pruebas

- **Severidad:** MEDIUM
- **Archivo:** `.claude/settings.json`, línea 1
- **Código relevante:** `"model":"claude-opus-5"`
- **Contrato relacionado:** `tests/test_claude_model_routing.py`, líneas 45–49, exige `settings["model"] == "claude-fable-5"`.
- **Problema:** el modelo configurado para la conversación principal es `claude-opus-5`, mientras la política versionada y su test de bloqueo establecen `claude-fable-5` como selección autorizada.
- **Evidencia:** `pytest -q -x`, con `TEMP` redirigido a un directorio accesible del workspace, produjo:

  ```text
  FAILED tests/test_claude_model_routing.py::test_main_model_matches_the_authorized_policy
  AssertionError: assert 'claude-opus-5' == 'claude-fable-5'
  1 failed, 229 passed
  ```

  Además, `git diff -- .claude/settings.json` confirma que el cambio no está confirmado: el valor versionado es `claude-fable-5` y el working tree contiene `claude-opus-5`.
- **Consecuencia:** la puerta `pytest`/`make check` está roja y la ejecución interactiva usa una política de routing distinta de la declarada. Esto elimina la garantía de que un cambio del modelo principal sea deliberado y sincronizado con documentación y pruebas.
- **Corrección propuesta:** decidir explícitamente cuál política es la autorizada y aplicar una de estas opciones de forma atómica:
  1. restaurar `"model":"claude-fable-5"` en `.claude/settings.json`; o
  2. si el cambio a Opus 5 fue autorizado, actualizar conjuntamente `CLAUDE.md`, `docs/MODEL-ROUTING.md` y los literales/expectativas de `tests/test_claude_model_routing.py`, dejando registrada la decisión.

## Alcance revisado

### Arquitectura y caminos operacionales

- `src/sqp/providers`: cuotas, resultados, ventanas UTC, caché y reintentos.
- `src/sqp/features` y `src/sqp/models`: construcción de variables, ratings, distribuciones y modelos ML.
- `src/sqp/calibration` y `src/sqp/evaluation`: calibradores, métricas, comparación modelo/mercado y bootstrap.
- `src/sqp/backtesting`: selección de snapshots pre-partido, replay, tuning y ROI.
- `src/sqp/pipeline`: generación diaria, probabilidades, captura de cierre, revalidación y limpieza.
- `src/sqp/risk`: Kelly, bankroll, degradación, CLV gate y prediction gate.
- `src/sqp/settlement` y `src/sqp/storage`: grading, voids, persistencia, escrituras atómicas y locking.
- `src/sqp/audit` y `src/sqp/monitoring`: reportes, dashboard, cobertura y estado del run.
- `scripts`, `configs`, `.github/workflows/ci.yml`, `Dockerfile`, `Makefile`, `pyproject.toml` y tests.

### Riesgos cuantitativos comprobados

- El backtest selecciona el último snapshot cuya captura es **estrictamente anterior** a `commence_time`; no se observó evidencia de uso de cuotas posteriores al inicio.
- Los flujos OOS separan resultados anteriores al cutoff para selección/congelación y evalúan desde el cutoff; no se observó evidencia concreta de contaminación train/test.
- Las probabilidades no-vig requieren mercados complementarios completos y validan entradas finitas/positivas; no se observó un cálculo inválido reproducible.
- El prediction gate colapsa repeticiones diarias y caras dependientes a unidades por evento/mercado/línea antes del test binomial; evita tratar filas duplicadas como ensayos independientes.
- Las mediciones de ROI colapsan el stream servido a una fila por apuesta y conservan la primera observación, evitando ponderar una apuesta por sus días dentro del horizonte.
- Los timestamps críticos se normalizan a UTC y las vistas que requieren calendario del operador convierten a fecha local de forma explícita.
- El sizing Kelly limita la fracción aplicada y devuelve stake cero cuando el edge no supera el mínimo.

Estas comprobaciones no generaron hallazgos porque no se obtuvo evidencia concreta de comportamiento incorrecto.

## Seguridad y confiabilidad

- `.env` está ignorado y no aparece entre los archivos versionados; `.env.example` sí está versionado.
- No se encontraron claves, tokens o contraseñas evidentes en `src`, `scripts`, `configs`, CI o Docker.
- Los errores de conexión del proveedor evitan incluir la URL con `apiKey` en el mensaje de excepción.
- Se observaron cargas `joblib` desde artefactos locales del proyecto; no se identificó un camino concreto que permita a un origen no confiable suministrar esos archivos, por lo que no se reporta como defecto.
- La persistencia incluye primitivas de escritura atómica y lock; no se reprodujo corrupción ni carrera concreta.

## Validación ejecutada

| Comando | Resultado |
|---|---|
| `make check` | No ejecutable: `make` no está instalado en el entorno Windows. Se ejecutaron sus tres puertas por separado. |
| `ruff check src scripts tests` | **PASS** — `All checks passed!` |
| `pytest -q -x` | **FAIL** — 1 fallo contractual, 229 aprobadas; detalle en SQP-AUD-001. |
| `pytest -q -m "not slow" --ignore=tests/test_claude_model_routing.py` | **PASS** — 1098 aprobadas, 224 deseleccionadas, 1 warning de caché. |
| `mypy src --show-traceback` | **NO CONCLUYENTE** — `sqlite3.OperationalError: unable to open database file` al abrir el metastore de `.mypy_cache`; no llegó a diagnosticar el código. |

La primera ejecución de `pytest` produjo errores de setup porque el directorio TEMP por defecto no era accesible dentro del sandbox. Al redirigir `TEMP`/`TMP` a `.codex-tmp` dentro del workspace, esos errores desaparecieron. Por tanto, no se atribuyen al proyecto.

## Cobertura y limitaciones

- No se ejecutaron las 224 pruebas marcadas `slow` hasta su finalización; el resultado completo queda limitado por el tiempo de ejecución disponible.
- El chequeo estático de tipos queda pendiente hasta reparar permisos/estructura de `.mypy_cache` o ejecutar `mypy` con una caché accesible.
- No se hicieron llamadas reales a proveedores pagos ni se modificaron credenciales o datos de producción.
- No se modificó código. El único archivo creado por la auditoría es este informe.
- Se preservaron sin cambios las modificaciones de usuario observadas en `.claude/settings.json`, `docs/MODEL-ROUTING.md`, `src/sqp/audit/html_report.py`, `NOTAS.md` y `tests/test_calibradores_pendientes.py`. Algunas aparecieron mientras la auditoría estaba en curso; no se atribuyeron a Codex ni se incluyeron retroactivamente en la validación ya ejecutada.

## Conclusión

El núcleo deportivo y cuantitativo presenta una cobertura de pruebas amplia y controles explícitos frente a varios riesgos históricos del proyecto. Sin embargo, el repositorio no puede considerarse `PASS` mientras la configuración activa contradiga su política autorizada y mantenga roja la suite contractual. Corregido SQP-AUD-001, deben repetirse `pytest -q`, `ruff check src scripts tests` y `mypy src` en un entorno con cachés accesibles antes de aceptar la revisión.

