---
name: mlb-pipeline
description: Analizar el pipeline MLB minimizando consumo de contexto.
---

# MLB Pipeline

Objetivo:
Entender el flujo MLB sin recorrer el repositorio completo.

Procedimiento:

1. Inspeccionar únicamente:
   - bat_scripts/
   - scripts/
   - config/

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