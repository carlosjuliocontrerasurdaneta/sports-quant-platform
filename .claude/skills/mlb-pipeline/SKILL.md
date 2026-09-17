---
name: mlb-pipeline
description: >
  Inspeccionar la estructura operacional del pipeline MLB (scripts, configs, BATs)
  minimizando consumo de contexto — "cómo funciona el pipeline de béisbol",
  "flujo MLB", "dependencias del run diario MLB". NO usar para análisis de
  partidos, probabilidades o calibración MLB (eso es quant-baseball-mlb).
---

# MLB Pipeline — alias de compatibilidad

Leer y seguir [daily-operations](../daily-operations/SKILL.md), modalidad
«Inspección estructural por liga», con alcance `mlb`.

Conservar este nombre para invocaciones existentes; el procedimiento se mantiene
solo en `daily-operations`. No usar para probabilidades de partidos ni calibración:
esas solicitudes pertenecen a `quant-baseball-mlb` y los loops de calibración.
