---
name: audit-remediation
description: Aplica hallazgos de auditoría autorizados por ID, grupo inequívoco o todos los confirmados. Acepta el informe canónico o una fuente histórica explícita de Claude/OpenAI. Usar para remediación, no para diagnóstico ni verificación independiente; la autorización de la sesión determina el alcance.
argument-hint: "[IDs aprobados]"
---

# Audit Remediation

Entrada para implementar hallazgos ya revisados y autorizados. Leer
[el contrato de auditoría](../../automation/audit-workflow.md), secciones
comunes y «Remediación autorizada», antes de editar.

## Entrada

- Informe identificable y alcance autorizado en la sesión: IDs, grupo inequívoco
  o todos los confirmados. Resolver contra los IDs reales, no contra títulos.
- Para rondas nuevas: `audit/latest/FINDINGS.md`, `BACKLOG.md`, `MANIFEST.json`.
- Para rondas existentes: aceptar la fuente legacy explícita conforme al contrato,
  preservando IDs y originales. No exigir una conversión manual como precondición.

Si falta evidencia o fuente, documentarlo; si el alcance no puede resolverse,
pedir la información necesaria. No repetir una aprobación ya inequívoca.

## Ejecución

Revalidar el árbol y cada hallazgo, capturar línea base, corregir por lotes mínimos,
probar comportamiento y revisar diff. Aplicar el procedimiento canónico completo.
Declarar los efectos realmente observados de hooks/autofixes, sin asumir que una
herramienta de otro agente los ejecuta. No promover modelos ni operar producción
por el solo hecho de que un informe recomiende hacerlo.

Escribir `CHANGES.md`, `VALIDATION.md`, `STATUS.md` y actualizar el manifest de la
ronda. Preservar `FINDINGS.md` como línea base; usar `STATUS.md` para el progreso.
Cumplir el bookkeeping de implementación requerido por `CLAUDE.md`.

La verificación independiente es la fase «Verificación independiente» del mismo
contrato, accesible también desde `audits/prompts/verificar-remediacion.md`.
No sustituirla por la afirmación del implementador de que los tests pasaron.
