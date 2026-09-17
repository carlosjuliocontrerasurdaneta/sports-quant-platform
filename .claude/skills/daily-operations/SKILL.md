---
name: daily-operations
description: >
  Review daily operations or inspect the pipeline structure for a selected league
  (including MLB): BAT/scripts, configuration, dependencies, recent logs, generated
  picks and settlement. Use for operational status or "cómo funciona el pipeline",
  not matchup probabilities. Includes the compatible daily-run, settle-bets and
  mlb-pipeline entrypoints.
---

# Daily Operations

En la revisión diaria ligera, analizar:

- `RUN_DIARIO_ALL.bat` (run diario multi-liga agendado) y `SETTLE_ALL.bat` (liquidación + auditoría)
- BATs y scripts llamados por ellos (`run_all.py`, `settle_all.py`)
- Logs más recientes (solo el final del archivo): `logs\run_diario.log`, `logs\settle_all.log`, `logs\backfill.log`

## Inspección estructural por liga

Para «cómo funciona el pipeline», «flujo MLB» o dependencias operacionales,
delimitar liga y reconstruir BAT → scripts → configuración → módulos llamados.
Inspeccionar `src/sqp/` solo donde sea necesario para comprobar el comportamiento
que los wrappers delegan. Identificar descarga, features, entrenamiento, generación
y settlement, con sus entradas, salidas, orden y autorizaciones.
Entregar flujo, archivos implicados, dependencias y riesgos con evidencia.
No ejecutar el pipeline ni consultar proveedores por el solo hecho de inspeccionarlo.

`mlb-pipeline` es el alias compatible para esta modalidad con alcance `mlb`;
el procedimiento se mantiene aquí. Para partidos/probabilidades usar `quant-*`;
para decisiones estructurales de diseño usar `sports-quant-platform-architect`.

## Restricciones de datos

Nunca **volcar a contexto**:

- `data/`
- `data/historical/`
- `data/odds/`
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
