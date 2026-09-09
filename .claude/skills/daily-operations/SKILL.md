---
name: daily-operations
description: Use this skill to review the daily operational run of the Sports Quant Platform — RUN_DIARIO_ALL.bat, SETTLE_ALL.bat, the BAT/scripts they call, and the most recent logs — without scanning large data directories. Covers pipeline status, generated picks, settlement/liquidación, errors, dependencies and failure risks. (Absorbe los antiguos skills daily-run y settle-bets.)
---

# Daily Operations

Analizar únicamente:

- `RUN_DIARIO_ALL.bat` (run diario multi-liga agendado) y `SETTLE_ALL.bat` (liquidación + auditoría)
- BATs y scripts llamados por ellos (`run_all.py`, `settle_all.py`)
- Logs más recientes (solo el final del archivo): `logs\run_diario.log`, `logs\settle_all.log`, `logs\backfill.log`

Nunca **volcar a contexto**:

- `data/`
- `historical/`
- `exports/`
- Modelos no relacionados con la ejecución del día

**Matiz que esta prohibición necesita** (auditoría del sistema de skills,
2026-09-08, H05). La prohibición es sobre **cargar datasets en contexto**, no
sobre verificarlos. Redactada como prohibición absoluta era incumplible junto
con los propios loops de esta skill: `quant/01` exige comprobar que
`predictions_<liga>.csv` es legible y no trae duplicados, y `quant/03` exige la
reconciliación contra `settled_<liga>.csv`. Un control que exige verificar lo
que prohíbe mirar deja al agente bloqueado o declarando un PASS que no midió.

Rige el mismo criterio que el `CLAUDE.md` de la raíz, que es la autoridad:
**los escaneos programáticos de datasets completos están permitidos cuando son
necesarios, siempre que a contexto vuelvan solo agregados, esquemas, muestras o
hallazgos.** Es decir:

- **Revisión ligera** (el modo por defecto de esta skill): BAT, scripts y la
  cola de los logs. No se toca `data/`.
- **Ejecución de un loop de validación**: se permite comprobación programática
  acotada de los artefactos que el loop nombra — conteos, duplicados, esquema,
  legibilidad, sellos temporales—, devolviendo cifras, nunca filas.

Entregar:

1. Secuencia de ejecución y dependencias entre pasos
2. Estado del pipeline
3. Picks generados
4. Errores detectados
5. Posibles puntos de fallo y riesgos
6. Próxima acción recomendada

## Liquidación (absorbe el antiguo skill settle-bets)

Al revisar la liquidación (`SETTLE_ALL.bat` → `scripts/settle_all.py`):

- Entradas: picks pendientes en `data/bets/`, resultados de proveedores.
- Proceso: emparejado resultado↔pick, grading win/loss/push, void por
  expiración (stale void: partidos cancelados/pospuestos sin score),
  auditoría acumulada `data/bets/audit_AAAAMMDD.md`.
- Salidas: settled_*.csv, auditoría markdown, CLV diario (ver skill
  clv-shadow-exit para la evaluación del gate).
- Riesgos: liga auto-saltada del run si tiene picks comenzados sin liquidar;
  corridas idempotentes (re-correr no debe duplicar).
- No abrir históricos completos: usar solo el final de los logs y encabezados.

## Loop de referencia

Antes de ejecutar, leer y seguir el loop correspondiente:
- Predicción diaria → `.claude/loops/quant/01-daily-prediction.md`
- Liquidación post-partido → `.claude/loops/quant/03-postgame-settlement.md`
