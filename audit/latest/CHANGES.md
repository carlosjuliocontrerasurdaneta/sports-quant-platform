# Cambios aplicados — Remediación de la auditoría 2026-09-06

Fase 4 de `full-audit` → `audit-remediation`. Autorización del operador:
**«todos los confirmados»**, resuelto contra `FINDINGS.md` como los ocho IDs
`AUD-MED-001..003` y `AUD-LOW-001..005`.

**Explícitamente NO autorizado y NO hecho:** leer `logs/` para diagnosticar el
fallo del 2026-09-01; las eliminaciones de limpieza `CL-01/02/03`; los inferidos
`AUD-INF-001/002`; los seis hallazgos de la auditoría concurrente de Codex.
Sin commits, sin push, sin cambios de parámetros de riesgo, sin promoción de
modelos, sin consumo de API de pago, sin tocar el Programador de tareas.

---

## Por ID

### AUD-MED-001 — caché de cuotas

`src/sqp/providers/odds_cache.py` · `tests/test_odds_cache.py`

```diff
-if ttl != float("inf") and (time.time() - f.stat().st_mtime) >= ttl:
+if ttl != float("inf") and max(0.0, time.time() - f.stat().st_mtime) >= ttl:
```

Una edad negativa (mtime por delante del reloj) no la caducaba ningún `ttl`.
Test nuevo `test_file_cache_expires_when_mtime_is_ahead_of_the_clock`, que fija
el caso que el test de borde existente no puede producir (congela el reloj *y*
el mtime al mismo valor).

### AUD-MED-002 — puerta de promoción de calibradores

`src/sqp/calibration/calibrator.py` · `tests/test_calibrator.py`

Nueva `_motivo_muestra_insuficiente(key, min_n_val)`, **default-deny**: un
metadato de staging ausente o ilegible ya no salta el control de muestra. El
guard pasa de `if meta is not None:` a un motivo explícito registrado en el log.
`_load_staging_meta` documenta que `None` significa «no se sabe», nunca «no hace
falta comprobarlo». 3 tests nuevos (ausente, corrupto, contraprueba con `force`).

### AUD-MED-003 — centinela de fallo de las etapas fuera de la cadena diaria

`scripts/run_status.py` · `src/sqp/monitoring/run_status.py` ·
`src/sqp/monitoring/health.py` · `VALIDATE_OOS.bat` · `BACKFILL_ALL.bat` ·
`CAPTURE_CLOSE.bat` · `REFRESH_ML.bat` · `tests/test_run_status.py`

- `STAGES` pasa de `{settle, run}` a seis etapas.
- Las cuatro BAT registran su fallo (`--fail --stage …`) y limpian su propia
  etapa al terminar bien (`--clear --only-stage …`), igual que las dos que ya lo
  hacían.
- El health check nombra la etapa **y el BAT a re-ejecutar** (`_BAT_POR_ETAPA`).
- Tests: se sustituyó el assert por subcadena `"run diario"` —que dejó de ser
  cierto y que además no comprobaba nada útil— por un localizador estable, y se
  añadieron dos: uno por etapa comprobando que el aviso nombra su BAT, y otro que
  impide que `STAGES` y `_BAT_POR_ETAPA` deriven (viven en módulos distintos).

**Nota de diseño:** `REFRESH_ML.bat` es manual desde el 2026-08-29, así que su
fallo no es invisible como el de los otros tres. Se le añadió el centinela igual
(su último resultado bajo el Programador fue `0xC000013A`), y se autolimpia en la
siguiente ejecución correcta.

### AUD-LOW-001 — integridad del calibrador

`src/sqp/calibration/calibrator.py` · `src/sqp/calibration/pergame.py` ·
`tests/test_calibrator.py`

`_load_calibrator` devuelve `None` cuando el digest del sidecar no cuadra, en vez
de avisar y cargar igualmente. Se añadieron las dos comprobaciones de `None` que
faltaban (`apply_calibration`, `_staged_pergame_predict`); `calibrator_defect` y
`calibrator_resolution` ya lo absorbían. Sin sidecar sigue cargando. 2 tests.

### AUD-LOW-002 — hook de secretos

`.claude/hooks/check-secrets.sh`

`*.md` fuera de la lista de exclusión. Verificado end-to-end (un `.md` con
`sk-…` → `exit 2`; uno legítimo → `exit 0`) y medido el coste: **0 coincidencias
sobre los 297 `.md` rastreados**.

### AUD-LOW-003 — siete textos desfasados

`src/sqp/storage/lock.py` · `src/sqp/audit/html_report.py` · `.gitignore` ·
`REPO_DESCRIPTION.md` · `README.md` · `CAPTURE_CLOSE.bat`

Sólo comentarios y documentación; ningún cambio de comportamiento. Los 120 s de
`LOCK_TIMEOUT_S` **se conservan** a propósito (el margen sobra y sobrar es la
dirección segura en una puerta que ahora aborta); lo que se corrigió es la
justificación, que citaba una espera de red que ya no ocurre. Los horarios pasan
a UTC.

### AUD-LOW-004 — Dockerfile

`Dockerfile`

Se declara que la imagen es de demo y referencia, que su intérprete (3.11, el
suelo de `pyproject`) **no** es el de producción (3.14), y que ningún paso de CI
la construye. **No se cambió la imagen base:** alinearla a 3.14 exige construirla
para validarla, y esta sesión no puede. Queda en `BACKLOG.md`.

### AUD-LOW-005 — corte temporal de las features pregame

`src/sqp/features/rest_form.py` · `src/sqp/pipeline/probabilities.py` ·
`tests/test_rest_form_cutoff.py` (nuevo)

- Helper `_hasta(results, reference_date)`; `reference_date: str | None = None`
  añadido a las diez features que no lo tenían; mismo criterio de corte que
  `team_rest_days` (el propio día queda fuera).
- `AdjustmentContext` transporta `ref_date` y `build_adjustment_context` lo pasa
  a **todas**, no sólo a `team_rest_days`.
- Divisor de las cuatro tasas de victoria: filas realmente leídas en vez de
  `len(recent)`, con el mismo umbral de 2.
- 10 tests nuevos, incluida la demostración de que sobre una lista ya recortada
  el filtro es un **no-op exacto**.

---

## Efecto del hook de formato

El `PostToolUse` del repositorio ejecuta `ruff check --fix` sobre cada archivo
editado con `Edit`/`Write`, así que los parches llevan además sus autofixes
seguros de lint. Revisado el diff final: **el hook no tocó lógica**. La única
huella observable es la eliminación de una línea en blanco dentro del docstring
de `AdjustmentContext` en `pipeline/probabilities.py`.

`src/sqp/features/rest_form.py` se transformó con un script Python ejecutado vía
Bash (diez firmas idénticas), así que **ese archivo no pasó por el hook**; se le
aplicaron `ruff` y `mypy` manualmente, ambos limpios.

## Archivo modificado por un tercero durante la sesión

`auditoria-integral-codex.md` aparece modificado (+439/−235, mtime 10:58). **No
lo tocó esta sesión**: un proceso externo de Codex reescribió su informe con una
auditoría nueva del mismo commit. Se ha leído, no se ha editado, y **no se
commitea** — la regla vigente prohíbe editarlo, borrarlo o commitearlo sin
autorización expresa. Sus seis hallazgos están resumidos al final de
`FINDINGS.md`.

`audit/model_vs_market_20260906.md` sigue sin rastrear y sin tocar: ya estaba ahí
al abrir la sesión.

## Lo que se decidió no tocar

| Qué | Por qué |
|---|---|
| Causa raíz del fallo de `VALIDATE_OOS` del 2026-09-01 | requiere `logs/`, denegado por permisos |
| Base 3.11 del `Dockerfile` | cambiarla exige construir la imagen para validarla |
| `CL-01/02/03` (≈205 MB de residuo ignorado) | eliminaciones no autorizadas |
| `AUD-INF-001/002` | inferidos: falta la condición necesaria |
| Los seis hallazgos de Codex del 2026-09-06 | fuera de la aprobación de esta sesión |
| `LOCK_TIMEOUT_S = 120` | el margen es deliberado; sólo cambió su justificación |
