# Entregables

## Ubicación

Destino canónico: **`audit/latest/`**, sobrescribiendo la auditoría anterior.
Ya está versionado y es el formato que consumen las auditorías previas del
repositorio. No escribir informes en la raíz del repositorio ni inventar nombres
nuevos: el histórico se conserva por Git, no por sufijos de fecha.

Escribir estos artefactos es bookkeeping obligatorio de la skill, no requiere
autorización adicional, y es la única excepción a la regla de solo lectura junto
con `.claude/automation/runtime/current-task.md`.

Ningún otro archivo del proyecto puede modificarse durante las fases 0–3.

## Artefactos

| Archivo | Contenido |
|---|---|
| `EXECUTIVE_SUMMARY.md` | Propósito, alcance, arquitectura, estado, riesgos principales, conclusión y limitaciones. |
| `FINDINGS.md` | Hallazgos agrupados por severidad (`CRÍTICO`, `ALTO`, `MEDIO`, `BAJO`, `INFORMATIVO`), con el registro completo de `taxonomy.md`. Incluye la sección de descartados con la evidencia que los refutó. |
| `VALIDATION.md` | Matriz de cobertura y tabla de validaciones: comando o método, propósito, resultado, código de salida, efectos secundarios y limitaciones. |
| `QUANT_REVIEW.md` | Revisión cuantitativa: leakage, calibración, backtesting, odds freshness, tamaño muestral y separación experimentación/producción, con la `n` de cada métrica. |
| `BACKLOG.md` | Plan priorizado: IDs, archivos previstos, cambio mínimo, riesgo, pruebas, criterio de aceptación y orden. |
| `MANIFEST.json` | Metadatos de la ejecución (esquema abajo). |
| `CHANGES.md` | **Sólo lo produce `audit-remediation`.** No escribir durante las fases 0–3. |

Un artefacto que no aplique se escribe igualmente declarando por qué está vacío.
Un archivo ausente es indistinguible de un paso omitido.

## Esquema de `MANIFEST.json`

Mantener las claves existentes para que las auditorías sean comparables:

`audit_id`, `started_utc`, `finished_utc`, `branch`, `base_commit`,
`commit_created`, `python_version`, `platform`, `git_state_initial`,
`git_state_final`, `tests_initial`, `tests_final`, `commands_executed`
(cada uno con `cmd` y `result`), `tools_unavailable`, `tools_not_run`,
`findings_by_severity`, `findings_by_status`, `files_modified`,
`authorization_required_actions_taken`, `risk_parameters_changed`,
`shadow_mode_changed`, `models_promoted`, `paid_api_used`, `coverage_result`,
`final_result`, `final_result_rationale`, `predictive_edge_demonstrated`.

En una auditoría sin corrección, `files_modified` contiene únicamente los
artefactos de `audit/latest/` y `current-task.md`, y
`authorization_required_actions_taken` debe quedar vacío. Si no lo está, la
skill se violó.

`predictive_edge_demonstrated` es `false` salvo que exista una medición fuera de
muestra que lo sostenga. No es un campo optimista.

## Registrar un resultado no observado es el fallo recurrente

No escribir en `VALIDATION.md` ni en `MANIFEST.json` el resultado de un comando
que todavía está corriendo. Si hay que dejar la fila puesta, marcarla
`NO_EJECUTADA` y actualizarla cuando exista el código de salida real. Este
repositorio ya cerró una auditoría en `PASS` con la suite en rojo por hacer
exactamente eso.

## Lenguaje obligatorio

Se aplica `.claude/rules/betting-output-rules.md`: separar probabilidad
estimada, probabilidad implícita, edge, hit rate observado frente a prometido,
ROI esperado estimado y ROI realizado. Nunca prometer rentabilidad. Una
auditoría `COMPLETA` significa que se auditó con evidencia, no que el sistema
gane dinero.

## Resumen en conversación

Además de los archivos, entregar en la respuesta: resumen ejecutivo, matriz de
cobertura, hallazgos confirmados por severidad, no confirmados, descartados
relevantes, validaciones ejecutadas, plan priorizado y riesgos pendientes.
Quien aprueba debe poder decidir sin abrir los archivos.
