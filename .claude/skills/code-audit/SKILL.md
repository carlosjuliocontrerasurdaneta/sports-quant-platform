---
name: code-audit
description: Use this skill for targeted code audits in the Sports Quant Platform, including Python quality, pipeline safety, error handling, testing, security, and maintainability.
---

# Code Audit

Revisión focalizada del diff, archivos o módulos solicitados. Leer las secciones
comunes y «Diagnóstico independiente» del
[contrato de auditoría](../../automation/audit-workflow.md).

Aplicar sus criterios de evidencia, severidad, formato y seguridad al alcance
pedido; inspeccionar callers solo cuando aporten evidencia de corrección.
No iniciar una auditoría integral ni cargar todas sus referencias por defecto.
Para áreas especializadas, consultar únicamente la referencia pertinente de
`../full-audit/references/`. No cargar datasets completos en contexto.

Entregar archivos inspeccionados, hallazgos, evidencia, corrección mínima,
validaciones y limitaciones. Si solo se pidió revisión conversacional, responder
en conversación; no crear una ronda persistida sin necesidad o petición.
