---
name: audit-remediation
description: Aplica las correcciones aprobadas de una auditoría integral previa y ejecuta la validación final. Usar SOLO después de que el usuario haya aprobado explícitamente hallazgos concretos de un informe de full-audit, identificándolos por ID, por grupo inequívoco o como "todos los hallazgos confirmados". No usar para diagnosticar, para auditar ni para corregir nada que no tenga aprobación registrada.
argument-hint: "[IDs aprobados]"
---

# Audit Remediation

Fases 4–5 del procedimiento de auditoría. La skill `full-audit` diagnostica y se
detiene; ésta corrige. Están separadas a propósito: una necesita no poder
escribir y la otra necesita escribir, y mezclarlas hace que la garantía de solo
lectura de la auditoría dependa de la disciplina en vez de la estructura.

## Requisito de entrada

No continuar sin las tres cosas:

1. un informe de auditoría legible en `audit/latest/` (al menos `FINDINGS.md` y `BACKLOG.md`);
2. aprobación explícita del usuario que identifique el alcance;
3. los IDs aprobados, resueltos contra `FINDINGS.md`.

Si el informe no existe o la aprobación es ambigua, **detenerse y pedirla**. Una
aprobación de una auditoría anterior no cubre hallazgos nuevos. "Adelante" sin
referencia a IDs no es alcance: preguntar cuáles.

## Fase 4 — Corrección autorizada

1. Confirmar el alcance autorizado y enumerar los IDs.
2. Releer las instrucciones aplicables y `references/` de `full-audit` si hace falta el registro del hallazgo.
3. Volver a inspeccionar Git: estado, cambios preexistentes y solapamientos con lo que se va a tocar.
4. Enumerar archivos afectados y el parche mínimo por ID.
5. Modificar únicamente lo aprobado.

Preservar comportamiento válido, configuración no relacionada, interfaces
públicas, compatibilidad, schemas, modelos, estrategias, parámetros, criterios
de decisión y datos históricos, salvo autorización específica para cambiarlos.

Prohibido sin autorización específica: refactors masivos, limpieza cosmética,
cambios oportunistas, eliminar archivos untracked o ambiguos, migraciones
irreversibles, acciones externas, commits, pushes, merges, releases y
deployments.

**Efecto conocido del entorno.** El hook `PostToolUse` de este repositorio
ejecuta `ruff check --fix` sobre cada archivo tras `Edit`/`Write`
(`.claude/hooks/post-edit-format.sh`). Cada parche llevará por tanto los
autofixes seguros de lint que ese hook aplique, aunque no formen parte del
cambio mínimo. No es evitable desde aquí y no invalida la corrección, pero
**debe declararse en `CHANGES.md`** en lugar de presentar el diff como si fuera
sólo el parche. Revisar el diff final para confirmar que el hook no tocó lógica.

Cambiar parámetros de riesgo, `pick_mode`, `shadow_mode`, promover modelos o
consumir API de pago exige aprobación humana separada e independiente de la
aprobación de la corrección, aunque un hallazgo lo recomiende.

## Fase 5 — Validación final

Tras cada conjunto lógico de correcciones:

1. prueba específica del hallazgo;
2. pruebas del componente;
3. validaciones estáticas (`ruff check src scripts tests`, `mypy src`);
4. regresión relevante;
5. suite completa si es viable (`pytest -q`);
6. revisión del diff;
7. coherencia de configuración, manifiestos y lockfiles;
8. búsqueda de regresiones.

Los scripts operacionales no Python (`.bat`) no los cubre ninguna de estas
comprobaciones: validarlos aparte o declararlo `NO_EJECUTADA`.

Clasificar cada comprobación como `PASO`, `FALLO`, `FALLO_PREEXISTENTE`,
`REGRESIÓN_INTRODUCIDA` o `NO_EJECUTADA`. Registrar el **código de salida real**,
no una impresión: el modo de fallo recurrente de este repositorio es declarar
verde un estado que no se comprobó.

Separar siempre los fallos preexistentes de las regresiones introducidas.
Comparar contra la línea base registrada por la auditoría en `MANIFEST.json`
(`tests_initial`). Si no hay línea base, capturarla **antes** de corregir.

No afirmar éxito global si una validación crítica no se ejecutó.

## Entregables

Actualizar en `audit/latest/`:

- `CHANGES.md`: IDs corregidos, cambio aplicado, archivos, diff resumido, efecto del hook de formato, y lo que se decidió no tocar;
- `VALIDATION.md`: comandos, códigos de salida y clasificación de cada comprobación;
- `FINDINGS.md`: estado de cada ID (corregido, parcial, requiere decisión humana, no corregible automáticamente);
- `MANIFEST.json`: `files_modified`, `tests_final`, `final_result` y `final_result_rationale`.

Después, el bookkeeping obligatorio de `CLAUDE.md`: notas Obsidian de la misma
sesión, `.claude/memory/known-issues.md` para lo que quede abierto y
`.claude/automation/runtime/current-task.md` con el resultado según
`.claude/loops/quant/STATES.md`. Es bookkeeping, no amplía el alcance técnico.
Si la ubicación o convención no puede determinarse con seguridad, reportar la
limitación en vez de adivinar.

## Corrección completa

Declararla sólo si se trataron únicamente IDs autorizados; las pruebas
específicas se ejecutaron o su imposibilidad quedó documentada; no hay
regresiones atribuibles conocidas; se revisó el diff final; se documentaron
riesgos y limitaciones; se separaron fallos preexistentes de regresiones
introducidas; y el bookkeeping se completó o se declaró imposible.

No confundir corregir con haber demostrado que el sistema funciona. Una
corrección validada arregla un defecto; no acredita ventaja predictiva ni
rentabilidad.
