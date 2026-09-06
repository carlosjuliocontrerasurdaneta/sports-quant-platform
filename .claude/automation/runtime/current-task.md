# Current Task

Status: closed
Result: DEGRADED (los ocho IDs autorizados corregidos y validados; suite
1547 → 1575 aprobados, 0 fallos; limitaciones acotadas y registradas: el
Dockerfile no se pudo construir, y `logs/`/`.env` quedaron excluidos por
permisos, lo que deja sin diagnosticar el fallo de VALIDATE_OOS del 2026-09-01)
Primary loop: `audit.md`
Skills: `full-audit` (fases 0–3) → `audit-remediation` (fases 4–5)
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`), sin delegación
Date: 2026-09-06

## Objective

Auditoría integral del repositorio y, tras aprobación explícita del operador
(«todos los confirmados»), corregir los ocho IDs confirmados: **AUD-MED-001**
(caché de cuotas), **AUD-MED-002** (puerta de promoción de calibradores),
**AUD-MED-003** (centinela de las BAT fuera de la cadena diaria), y
**AUD-LOW-001..005**.

## Escalado de modelo

**No se escaló a `claude-fable-5-1` ni se delegó en subagentes.** Justificación
frente a las cinco clases del disparador de `MODEL_ROUTING.md`:

- *Parámetros de riesgo/modelo/estrategia/umbral/gate*: **AUD-MED-002 toca una
  puerta de promoción**, que es la clase más cercana. No la activa: no diseña
  criterio nuevo ni mueve ningún umbral — `min_n_val` sigue siendo 30 y
  `AUTO_PROMOTE_MIN_N_VAL` no cambia. Sólo corrige que un metadato ilegible
  saltara el guard existente, con el fallo ya reproducido antes de tocar nada y
  la reproducción invertida después. Es aplicar el criterio ya aprobado al caso
  que se le escapaba.
- *Trabajo irreversible*: ninguno. Sin commits, sin push, sin borrados, sin
  tocar producción ni el Programador de tareas.
- *Contradecir una decisión registrada*: ninguna. `LOCK_TIMEOUT_S = 120` se
  **conserva** deliberadamente (sólo se corrigió su justificación), y el
  fallback de `picks_vigentes_unicos` (decisión del 2026-08-28) no se toca.
- *Cambiar el contrato de un artefacto persistido*: `STAGES` se amplía de dos a
  seis valores, que es **aditivo** — `record_run_failure` ya fusionaba por etapa
  y `read_run_status` ya toleraba nombres arbitrarios.
- *Cifras publicables*: ninguna. No se afirma ventaja predictiva ni rentabilidad.

Ante la duda se sube, y aquí la duda estaba en AUD-MED-002: se resolvió a la
baja porque la reproducción precedió al parche y la clase de trabajo es «cerrar
un agujero de un guard existente», no «decidir un umbral». Queda declarado.

## Resultado

- 8 IDs tratados, **y sólo ellos**.
- `pytest`: 1575 passed, 1 skipped, exit 0 (línea base 1547/0/1).
- `ruff check src scripts tests` y `mypy src`: exit 0.
- +28 tests, que cuadran uno a uno con lo añadido.
- 1 regresión introducida (assert por subcadena en `test_run_status.py`),
  detectada y corregida antes de la validación final.

## Siguiente decisión del operador

1. **Empujar** el arreglo de AUD-MED-001: el CI de `main` sigue rojo hasta
   entonces (issue #1 abierto). No se commiteó nada — no estaba autorizado.
2. **KI-032** (HIGH, Codex): la corrupción parcial del ledger infla la banca.
   Fuera de la aprobación de hoy; primer punto del backlog.
3. **KI-033**: los otros cinco hallazgos de Codex del 2026-09-06.
4. **KI-034**: autorizar la lectura de `logs/validate_oos.log` para diagnosticar
   el fallo del 2026-09-01. La tarea es mensual: no se reintenta hasta el
   2026-10-01.
5. **KI-035**: el hook de revisión cruzada presenta un error de infraestructura
   con el encabezado de hallazgos.
6. **B-4**: ~205 MB de residuo ignorado por git, pendiente de autorización.

Detalle completo en `audit/latest/{FINDINGS,CHANGES,VALIDATION,BACKLOG}.md` y
`MANIFEST.json`.
