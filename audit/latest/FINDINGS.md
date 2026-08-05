# Hallazgos — Auditoría integral 2026-08-04

Severidades: CRÍTICO / ALTO / MEDIO / BAJO / INFORMATIVO.
Estados: corregido · parcial · requiere decisión humana · no corregible
automáticamente · no confirmado.

## CRÍTICO

### C-2 · `Settings.load()` fallaba-abierto ante config ausente
- **Componente:** `src/sqp/config.py`
- **Evidencia:** `if cfg_path.exists():` envolvía todo el bloque de carga. Defaults
  del dataclass verificados: `shadow_mode` = `_env_flag("SHADOW_MODE") is True`
  → `False`; `clv_gate_enabled` = `False` ("OFF by default"); `max_plausible_edge`
  = `0.15` frente a `0.075` en `configs/default.yaml:16`; `paused_markets` = `{}`.
  `configs/default.yaml:100` declara `shadow_mode: true`.
- **Impacto:** un config no resuelto produce apuestas reales, sin gate de CLV, sin
  pausas y con el doble de tolerancia a edges implausibles, sin ningún warning.
- **Causa raíz:** misma clase de fail-open que B-08 (auditoría 2026-07-29), ya
  corregida para las env vars y no corregida en la ruta de archivo.
- **Explotabilidad real:** latente. `sqp` no está instalado (`ModuleNotFoundError`
  sin `PYTHONPATH`); CI usa `pip install -e` (editable), que preserva `parents[2]`.
  El gatillo es `pip install .` no editable, habilitado por
  `pyproject.toml:26-27` (`packages.find where=["src"]`).
- **Corrección:** `load()` lanza `FileNotFoundError` con mensaje explícito.
- **Pruebas:** `tests/test_config.py::test_missing_config_file_fails_fast_instead_of_disarming_risk`.
- **Estado:** corregido.

## ALTO

### A-1 · El estado se declara sin verificarlo (fallo de proceso, recurrente)
- **Componente:** `Obsidian/Bitácora/2026-08-04.md`, `.claude/automation/runtime/current-task.md`
- **Evidencia:** la bitácora afirmaba "Suite completa verde" (real: 5 failed, 612
  passed) y "Ruff y Mypy: no ejecutados porque no están instalados" (real:
  ruff 0.15.14 y mypy 2.1.0 instalados y limpios). `current-task.md` cerró con
  `Result: PASS`.
- **Impacto:** cualquier lector, humano o agente, opera sobre un estado falso. Es
  el tercer caso en tres días (con la deriva del `pick_mode` del 07-31).
- **Causa raíz:** no existe obligación de pegar la salida real del comando junto
  a la afirmación. `STATES.md` ya prohíbe declarar `PASS` sin evidencia
  observable; la regla existía y no se aplicó.
- **Corrección:** bitácora del día corregida con las salidas reales; regla
  reforzada por escrito; `current-task.md` actualizado con esta auditoría.
- **Estado:** corregido (documental). La reincidencia solo se elimina con un
  control automático — ver `BACKLOG.md` B-1.

### A-2 · Deriva config↔política del modelo principal
- **Componente:** `.claude/settings.json`, `.claude/automation/MODEL_ROUTING.md`
- **Evidencia:** `settings.json` = `claude-opus-5`; `MODEL_ROUTING.md:11`
  autorizaba `claude-fable-5` "por decisión humana explícita".
  `test_claude_model_routing.py` fallaba — el test detectó la deriva.
- **Impacto:** la política de modelos no describía la configuración real.
- **Contexto verificado:** la autorización de Fable 5 (mismo día) se registró con
  riesgo declarado en `.claude/memory/architecture-log.md:171` ("no se verificó
  la disponibilidad externa del identificador contra una instalación real"), y el
  2026-07-30 se había detectado que la cuenta no tenía créditos de Fable 5.
- **Corrección:** decisión del operador → `claude-opus-5`. Alineados
  `MODEL_ROUTING.md`, `Registro de decisiones.md`, `project-decisions.md` y el
  test. **El test no se aflojó**: es el único mecanismo que detecta esta deriva.
- **Estado:** corregido.

## MEDIO

### M-1 · `settle_all.py` abortaba el día por cualquier fallo de liquidación
- **Componente:** `scripts/settle_all.py`
- **Evidencia:** `return 1 if failures else 0`; `DIARIO_COMPLETO.bat:24`
  (`if errorlevel 1 goto :error_settle`) aborta el run diario.
- **Impacto:** una cuota agotada o un 5xx en una liga sin picks en riesgo costaba
  un día completo de operación en todas las ligas. Bajo shadow el stake es 0, así
  que el coste es evidencia, que es el recurso escaso (gate de CLV vacío, gate
  intradía en INSUFICIENTE con n=22/30).
- **Causa raíz:** el abort global era redundante con el guard M2 por liga que
  `scripts/run_all.py:142-159` ya aplica.
- **Corrección:** aborta solo si una liga fallida retiene picks comenzados sin
  liquidar (`unsettled_completed_picks`); reporte de auditoría a best-effort.
- **Pruebas:** 3 en `tests/test_orchestrator_safety.py`.
- **Estado:** corregido.

### M-2 · 54 filas servidas pendientes fuera de la ventana de scores
- **Componente:** datos servidos (chile 42, tennis_atp_canadian_open 12)
- **Evidencia:** `scripts/health_check.py` → `WARN (0 errors, 2 warnings)`.
- **Impacto:** filas que no se gradúan sesgan por supervivencia la muestra de
  auditoría (CLV, Brier, hit rate).
- **Causa raíz:** no confirmada. Es la misma clase que M-01 (cerrado el 08-02 con
  el fallback desde `data/historical/`), pero son instancias nuevas, lo que
  sugiere falta de backfill o ausencia de vendor de resultados para esas ligas.
  **No puedo confirmar cuál de las dos sin ejecutar backfill**, que está fuera de
  mi autonomía por consumo de cuota.
- **Estado:** requiere decisión humana.

## BAJO

### B-1 · Un CSV ilegible era indistinguible de uno ausente en el health check
- **Componente:** `src/sqp/monitoring/health.py` (`_rows`)
- **Evidencia:** `except Exception: return None`, sin log. El `None` cae en la
  misma rama que "ausente" (línea 126), así que **el estado nunca fue erróneo**,
  pero el operador leía "no stored results" ante un archivo corrupto.
- **Impacto:** diagnóstico incorrecto; "nunca ingerido" y "ingerido y ahora
  corrupto" requieren reparaciones distintas.
- **Corrección:** `log.warning` con la ruta y la excepción.
- **Pruebas:** `tests/test_health.py::test_corrupt_results_file_is_logged_not_silently_counted_as_absent`.
- **Estado:** corregido.

### B-2 · Parche residual sin trackear ni ignorar en la raíz
- **Componente:** `claude-loops-remediation-20260804.patch`, `.gitignore`
- **Evidencia:** `git apply --check` falla en todos los hunks → ya aplicado; su
  contenido está en el commit `2a293cb`. No estaba cubierto por `.gitignore`.
- **Impacto:** riesgo de commit accidental de un residuo de ~1.800 líneas.
- **Corrección:** `*.patch` añadido a `.gitignore`. **El archivo no se borró**:
  es untracked, por tanto irrecuperable, y no fue creado en esta sesión.
- **Estado:** parcial — el borrado requiere decisión humana.

## INFORMATIVO

### I-1 · `ruff format --check` reformatearía 192 de 209 archivos
- **Evidencia:** `ruff format --check .` → "192 files would be reformatted, 17
  files already formatted". El CI (`.github/workflows/ci.yml`) ejecuta
  `ruff check src scripts tests`, **no** `ruff format`.
- **Conclusión:** `ruff format` no es un estándar de este proyecto. Aplicarlo sería
  un refactor cosmético masivo sin beneficio verificable y contra la regla de
  cambios quirúrgicos. **No corregido deliberadamente.**
- **Estado:** no corregible automáticamente (decisión de estilo del operador).

### I-2 · "Reglas comunes" duplicado literalmente en 14 archivos de loop
- **Evidencia:** `grep -lc "## Reglas comunes"` sobre `.claude/loops/` → 14.
- **Impacto:** una regla que cambie exige 14 ediciones coherentes.
- **Estado:** no corregido — ver `BACKLOG.md` B-3 (el bloque se acaba de
  remediar el 08-04; reescribir 14 archivos hoy es churn de alto riesgo).

### I-3 · Los loops no declaran artefactos, inputs ni transición al siguiente loop
- **Evidencia:** estructura real verificada en
  `.claude/loops/quant/09-champion-challenger.md`: Reglas comunes / Objetivo /
  Criterio previo obligatorio / Flujo. `STATES.md` sí define PASS, DEGRADED,
  BLOCKED y DONE con condiciones exactas, precedencia y umbrales anclados al
  código, y los loops lo referencian en vez de redefinirlo.
- **Estado:** no corregido — ver `BACKLOG.md` B-4.

## Verificado sin hallazgos

- **Secretos:** barrido sobre los 443 archivos trackeados con patrones de
  api_key/secret/token/password y base64/hex largos → sin coincidencias (el único
  match es un hash de commit en `MANIFEST.json`). La redacción de la query del
  proveedor está **implementada y verificada en código**
  (`src/sqp/providers/odds_api.py:132-144`, "query redacted"), no solo documentada.
- **Artefactos versionados:** ningún `.pyc`, `.csv`, `.parquet`, modelo, log ni
  dato trackeado; solo `.gitkeep`. `.git` = 5.8 MB. `.env` no trackeado (solo
  `.env.example`). `settings.local.json` y `*.backup-*` correctamente ignorados.
- **Dependencias:** los 8 paquetes de terceros importados en `src/` están
  declarados en `pyproject.toml`; `pip check` limpio; lock usado como constraints
  en CI; `requires-python >=3.11` coherente con `target-version = "py311"` de ruff.
- **Excepciones:** 0 `except:` desnudos; 1 solo `except ...: pass`
  (`odds_api.py:159`, parseo de cabeceras de cuota — benigno); los manejadores
  amplios revisados fallan al lado seguro y con log
  (`ml_train.py` respalda y avisa, `feature_store.py` fuerza reconstrucción,
  `features/common.py` devuelve un default documentado).
- **Integridad referencial de `.claude`:** 24 rutas en `model-routing.json`; todos
  los loops referenciados existen; todos los agentes referenciados existen.
- **Orquestación BAT:** `DIARIO_COMPLETO.bat` encadena SETTLE_ALL → RUN_DIARIO_ALL
  con `if errorlevel 1` tras cada paso; el orden documentado coincide con el real.

## No verificable en esta auditoría

- **Tareas del Task Scheduler de Windows:** no puedo confirmar esto desde el
  repositorio. Las 6 tareas documentadas en `Obsidian/Estado del proyecto.md` no
  se comprobaron contra el sistema operativo.
- **Contenido de `data/`, `historical/`, `logs/`, `exports/`:** no escaneados por
  regla permanente del proyecto. Los hallazgos de datos se limitan a lo que el
  health check y el código exponen.
- **Validez predictiva de cualquier modelo:** ver `QUANT_REVIEW.md`.
