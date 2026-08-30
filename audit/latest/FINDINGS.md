# Hallazgos — Auditoría integral 2026-08-30

Severidades: CRÍTICO / ALTO / MEDIO / BAJO / INFORMATIVO.
Estados de evidencia según `.claude/skills/full-audit/references/taxonomy.md`.

Alcance: repositorio completo. Resultado de cobertura: **PARCIAL** (ver
`VALIDATION.md`).

## ALTO

### A-1 · `audit.md` rompe dos contratos del sistema de loops

- **Estado:** `REPRODUCIDO` · **Confianza:** ALTA · **Categoría:** regresión introducida
- **Componente:** `.claude/loops/audit.md`
- **Evidencia:** `pytest tests/ -q` → `3 failed, 1375 passed, 1 skipped`. Dos
  fallos son de este archivo:
  - `tests/test_claude_system_contract.py::test_general_loops_share_an_identical_guardrail_block`
  - `tests/test_claude_system_contract.py::test_all_general_loops_finish_through_verification_gate`
- **Comprobación independiente:** extracción programática del bloque
  `## Common guardrails` de los 11 archivos de `.claude/loops/*.md`: 10 comparten
  un bloque byte-idéntico de 5 viñetas; `audit.md` es la única desviación (4
  viñetas, dos de ellas propias) y el único sin `/verification-gate`.
- **Esperado vs observado:** el contrato exige bloque idéntico en todos los loops
  y cierre por `/verification-gate`. `audit.md` incumple ambos.
- **Causa raíz:** el archivo se creó el 2026-08-29 durante la reestructuración de
  la skill `full-audit` redactando guardarraíles a medida en vez de reutilizar el
  bloque canónico, y sin ejecutar la suite completa después.
- **Impacto:** suite en rojo. El contrato existe porque cada loop se carga solo y
  debe ser autocontenido; el riesgo que vigila no es la duplicación sino la
  deriva, que es exactamente lo que se introdujo.
- **Solución mínima:** restaurar el bloque canónico literal bajo
  `## Common guardrails`, mover las restricciones específicas de auditoría a una
  sección propia fuera de ese encabezado, y cerrar por `/verification-gate`.
- **Riesgo de regresión:** nulo sobre código de producción; el archivo es
  instruccional. Lo cubren los dos tests que hoy fallan.

## MEDIO

### M-1 · La auditoría del 2026-08-29 no dejó ningún artefacto persistido

- **Estado:** `VERIFICADO_ESTATICAMENTE` · **Confianza:** ALTA · **Categoría:** trazabilidad
- **Componente:** `audit/latest/`, `.claude/skills/full-audit/references/taxonomy.md`
- **Evidencia:** el último commit que toca `audit/latest/` es `84e5c72`
  (2026-08-05) y `audit/latest/FINDINGS.md` se titulaba "Auditoría integral
  2026-08-04". Entre el 2026-08-28 y el 2026-08-29 hay commits que corrigen
  `AUD-HIGH-001`, `AUD-MED-002`, `AUD-LOW-001`, `AUD-LOW-002` y `AUD-LOW-003`.
- **Esperado vs observado:** seis correcciones referencian IDs de una auditoría
  cuyo informe no existe en el repositorio; los IDs no resuelven contra ningún
  documento.
- **Causa raíz:** hasta el 2026-08-29 la skill `full-audit` prohibía escribir
  cualquier archivo salvo un informe expresamente autorizado, y no definía
  destino; el estado de la auditoría vivía sólo en el contexto de la sesión.
- **Impacto:** no hay línea base ni registro revisable de la auditoría más
  reciente. `git log` documenta los arreglos, no la evidencia ni lo descartado.
- **Efecto secundario detectado:** coexisten dos esquemas de ID. Los artefactos
  persistidos usan `C-n/A-n/M-n/B-n/I-n`; la auditoría del 2026-08-29 usó
  `AUD-<NIVEL>-NNN`. `taxonomy.md` fija el primero por ser el de los artefactos,
  pero debe registrar la equivalencia para que los IDs históricos —que aparecen
  en mensajes de commit y en `known-issues.md`— sigan siendo resolubles.
- **Solución mínima:** la causa raíz ya está corregida (persistencia incremental
  obligatoria en la skill reestructurada, más este informe). Resta documentar la
  equivalencia de esquemas en `taxonomy.md`.

## BAJO

### B-1 · La revalidación del registro live no corre si no hay historial graduado

- **Estado:** `INFERIDO` · **Confianza:** BAJA · **Categoría:** robustez
- **Componente:** `src/sqp/calibration/data.py`, `src/sqp/calibration/calibrator.py:573`
- **Evidencia:** `revalidate_live_registry()` se invoca al final de
  `train_market_calibrators` (`calibrator.py:573`). La cadena diaria es
  `run_all.py:325` → `stage_calibrators_from_settled` → `train_market_calibrators`.
  Pero `stage_calibrators_from_settled` retorna `[]` **antes** de llamar a
  `train_market_calibrators` si `calibration_enabled` es falso o si
  `load_calibration_training_history()` viene vacío.
- **Condición de activación:** historial graduado vacío o ilegible mientras el
  registro live sigue sirviendo calibradores.
- **Por qué la confianza es BAJA:** no se ha observado. Con
  `calibration_enabled=false` los calibradores live no se aplican, así que esa
  rama es inocua; la rama de historial vacío exige cero apuestas liquidadas, algo
  que no ocurre en producción. No se ha construido un caso que lo active.
- **Decisión:** **no se corrige.** La necesidad no está sustentada por evidencia
  observada, sólo por lectura del flujo de control. Queda registrado para que una
  auditoría futura lo evalúe con datos, no para actuar sobre una hipótesis.

## INFORMATIVO

### I-1 · Fallo preexistente no atribuible a esta auditoría

`tests/test_claude_model_routing.py::test_main_model_matches_the_authorized_policy`
falla porque `.claude/settings.json` declara `claude-opus-5` mientras `HEAD`
declara `claude-fable-5`. Verificado con `git show HEAD:.claude/settings.json`:
la divergencia ya estaba en el árbol de trabajo al abrir la sesión del
2026-08-29, y no era deriva accidental sino un cambio deliberado aplicado a
medias: `settings.json` y `docs/MODEL-ROUTING.md` en Opus 5, la política y el
literal del test en Fable 5.

**CERRADO el 2026-08-30 por decisión del operador:** Opus 5 en las cuatro
puntas. Se alinearon `.claude/automation/MODEL_ROUTING.md` y los dos literales
de `tests/test_claude_model_routing.py`. La suite queda **completamente verde:
1378 passed, 0 fallos**. La jerarquía de capacidad no cambia —`claude-fable-5` >
`claude-opus-5` > `sonnet` > `haiku`— y sigue afirmada por su propio test: lo que
cambió es el punto de partida, no el techo.

Nota de proceso: el candado de tres puntas hizo exactamente lo que se diseñó para
hacer. Sostuvo la suite en rojo hasta que un humano decidió, en vez de dejar que
un cambio a medias pasara inadvertido. Ver `known-issues.md` KI-021.

### I-2 · `shadow_mode: false` es deliberado

`configs/default.yaml:167` tiene `shadow_mode: false`. No es deriva: el flag se
levantó el 2026-08-16 por decisión registrada (`src/sqp/audit/html_report.py:79`).
Se anota porque implica que el sistema dimensiona stakes reales, lo que eleva la
importancia de los gates de riesgo.

## Descartados con evidencia

| Sospecha | Por qué se descartó |
|---|---|
| `revalidate_live_registry()` sería código muerto: no aparecía en ningún llamador de producción. | Falso positivo de mi propia búsqueda, que excluía el módulo que la define. `grep` sobre el repo completo la encuentra en `calibrator.py:573`, dentro de `train_market_calibrators`, alcanzable desde el run diario (`run_all.py:325`). |
| El guard de `price_decimal <= 1.0` seguiría pendiente, según `KI-019`. | Resuelto. `is_usable_price` (`src/sqp/markets/odds.py:7`) rechaza `None`, NaN, ±inf y todo precio ≤ 1.0, y lo consumen `edge.py:65`, `odds.py:31,38` y `probabilities.py:35,62`. |
| Secretos versionados. | Barrido sobre archivos trackeados sin coincidencias; sólo `.env.example` está en git. |
| Peticiones HTTP sin timeout. | Cero `requests.get/post` sin `timeout` en `src` y `scripts`. |
| Incoherencia manifiesto/lock. | `pip check` → "No broken requirements found." |
| Deriva de calidad estática. | `ruff check src scripts tests` → "All checks passed!"; `mypy src` → "no issues found in 98 source files". |
