---
name: mlb-pipeline-inspect
description: >
  Inspeccionar la estructura operacional del pipeline MLB (scripts, configs, BATs)
  minimizando consumo de contexto — "cómo funciona el pipeline de béisbol",
  "flujo MLB", "dependencias del run diario MLB". NO usar para análisis de
  partidos, probabilidades o calibración MLB (eso es quant-baseball-mlb).
---

# MLB Pipeline Inspect

Objetivo:
Entender el flujo operacional MLB sin recorrer el repositorio completo.

Procedimiento:

1. Inspeccionar únicamente:
   - scripts/ (run_all.py, settle_all.py, train_calibration.py, etc.)
   - configs/

2. Identificar:
   - descarga de datos
   - generación de features
   - entrenamiento
   - generación de picks
   - settle

3. No abrir:
   - data/
   - historical/
   - exports/

4. Entregar:

- Flujo
- Archivos implicados
- Dependencias
- Riesgos detectados