# Hallazgos — Auditoría integral 2026-08-02

Severidades: CRÍTICO · ALTO · MEDIO · BAJO · INFORMATIVO.
Estados: **Corregido** · **Requiere decisión humana** · **Backlog** · **No confirmado**.

Contexto: la auditoría 2026-07-29/31 corrigió 24 hallazgos hace 4 días; esta
pasada audita lo cambiado desde entonces + consistencia global. No se
encontraron hallazgos CRÍTICOS.

## ALTO

| ID | Componente | Descripción | Evidencia | Impacto | Corrección | Estado |
|---|---|---|---|---|---|---|
| A-01 | Documentación (README, Obsidian, memoria) | El revert `accuracy`→`edge` del 2026-07-31 (commit `f6c2130`) no se documentó en ninguna parte: README decía "modo precisión activo en producción", `Estado del proyecto.md` (actualizada 2026-07-28) igual, `Tareas.md` con tareas vivas del modo revertido, sin entrada de bitácora, y la memoria del asistente igual de desactualizada. Viola la regla del proyecto "todo cambio relevante se refleja en la MISMA sesión". | `configs/default.yaml:72` (`mode: edge`) vs `README.md:114` (antes), `Obsidian/Estado del proyecto.md:16` (antes) | Humanos y agentes operando sobre un estado falso del sistema de selección de picks | README + Estado + Tareas + bitácora nueva + memoria del asistente sincronizados | **Corregido** |

## MEDIO

| ID | Componente | Descripción | Evidencia | Impacto | Corrección | Estado |
|---|---|---|---|---|---|---|
| M-01 | Operación / settlement | 87 filas servidas pendientes de liquidar más allá de la ventana de 3 días del feed de scores (brasileirao 73, mlb 12, tennis_atp_washington_open 2): no se graduarán nunca desde el run diario | `scripts/health_check.py` → WARN (salida transcrita en VALIDATION.md) | Sesgo de supervivencia en la muestra de auditoría/calibración; métricas de hit rate y CLV calculadas sobre muestra incompleta | Comandos exactos en BACKLOG.md; el settle consume cuota del API | **Requiere decisión humana** |
| M-02 | `.claude/automation/runtime/current-task.md` | Tarea "in-progress" (auditoría 2026-07-29) que en realidad se cerró y mergeó el 2026-07-31 — loop aparentemente activo pero terminado | El archivo decía `Status: in-progress` con checkboxes pendientes que sí se completaron | El orquestador/loops leerían una tarea fantasma como activa | Cerrada con historial; tarea actual registrada | **Corregido** |

## BAJO

| ID | Componente | Descripción | Evidencia | Impacto | Corrección | Estado |
|---|---|---|---|---|---|---|
| B-01 | `src/sqp/models/ml_train.py:79` | `_register` descartaba un `registry.json` corrupto con `except Exception: reg = []` y lo sobrescribía — pérdida silenciosa del historial de entrenamientos | Código previo al fix | Pérdida de datos sin rastro ante corrupción (viola data-integrity-rules) | Backup `registry.json.corrupt-<ts>` + WARNING; test `test_register_corrupt_registry_backed_up_not_silently_discarded` (TDD) | **Corregido** |
| B-02 | `.claude/memory/roadmap.md` | Referenciaba `docs/loop-mandate-precision.md` y `docs/loop-progress.md`, eliminados deliberadamente en `f43ba00` | `ls` → No such file; `git log f43ba00` | Índice de roadmap con enlaces muertos | Referencias retiradas con nota | **Corregido** |
| B-03 | `.github/workflows/ci.yml:20` | Comentario "pyproject requires >=3.10" obsoleto (es `>=3.11` desde M-15, 2026-07-24) | pyproject.toml:7 | Confusión menor al mantener la matriz de CI | Comentario corregido | **Corregido** |

## INFORMATIVO (verificado, sin acción)

| ID | Tema | Detalle |
|---|---|---|
| I-01 | Secretos | Sin secretos en archivos trackeados. El único match del patrón (`audit/latest/VALIDATION.md` anterior) es un placeholder `abcd…` (22 chars) que documentaba la prueba del hook check-secrets. `.env` deny-listed y fuera de git. |
| I-02 | Dependencias | Los 8 paquetes de terceros importados (numpy, pandas, scipy, sklearn, joblib, requests, yaml, dotenv) están declarados en pyproject; lock como constraints en CI; `pip check` limpio. |
| I-03 | `ruff format` | Reformatearía 186/203 archivos: el proyecto nunca adoptó `ruff format` (CI/Makefile solo corren `ruff check`). No es hallazgo; no se hizo reformateo masivo. |
| I-04 | Binomial negativa (fa503f9) | Parametrización verificada: `nbinom.pmf(i, k, k/(k+λ))` preserva media λ con varianza λ(1+λ/k). Correcta. |
| I-05 | `except Exception` en src | Los 15 restantes son fallbacks documentados con degradación segura (reporte HTML, apertura de navegador, parse de fechas → neutral, health check) — revisados también por la auditoría 07-29 (obs 1863). Sin cambios (principio quirúrgico). |
| I-06 | Permisos `.claude/settings.json` | Deny protege `data/`, `.env`, `git reset --hard`; `git push` fuera de la deny-list por decisión documentada 2026-07-31 (gobernanza por política). Único diff preexistente: renombre de modelo del harness. |
| I-07 | BATs | `DIARIO_COMPLETO.bat` garantiza settle→run con abort si falla settle; intérprete fijo con fallback; rotación de logs; centinela de fallo + limpieza (S-1). Correcto. |
| I-08 | Commits post-auditoría | Los 10 commits desde `4fdf671` llevan cada uno tests y validación en el mensaje (562→581 tests). Espíritu TDD verificado. |
