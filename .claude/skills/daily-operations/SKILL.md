---
name: daily-operations
description: Use this skill to review the daily operational run of the Sports Quant Platform — RUN_DIARIO_ALL.bat, the BAT/scripts it calls, and the most recent logs — without scanning large data directories. Covers pipeline status, generated picks, errors, dependencies and failure risks. (Absorbe el antiguo skill daily-run.)
---

# Daily Operations

Analizar únicamente:

- `RUN_DIARIO_ALL.bat` (run diario multi-liga agendado) y `SETTLE_ALL.bat` (liquidación + auditoría)
- BATs y scripts llamados por ellos (`run_all.py`, `settle_all.py`)
- Logs más recientes (solo el final del archivo): `logs\run_diario.log`, `logs\settle_all.log`, `logs\backfill.log`

Nunca inspeccionar:

- `data/`
- `historical/`
- `exports/`
- Modelos no relacionados con la ejecución del día

Entregar:

1. Secuencia de ejecución y dependencias entre pasos
2. Estado del pipeline
3. Picks generados
4. Errores detectados
5. Posibles puntos de fallo y riesgos
6. Próxima acción recomendada
