# Daily Prediction Loop

## Reglas comunes

- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` segun las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.

## Objetivo
Generar probabilidades estimadas reproducibles y congelar snapshots antes del inicio de cada evento.

## Precondiciones
- La liquidación del día anterior ya corrió. **El run diario SOBRESCRIBE
  `data/predictions/candidates_*.csv`**, así que ejecutarlo antes de liquidar
  destruye la cohorte pendiente (queda recuperable en `data/predictions/archive/`,
  pero el orden correcto es el inverso). Ver `README.md`, "Orden crítico".
- `configs/default.yaml` legible y `Settings.validate()` sin error.

## Inputs
- Cuotas de The Odds API (proveedor de **pago**).
- `data/historical/results_<liga>.csv` para el ajuste de ratings.

## Comandos
1. `python scripts/claude_project_health.py` y `python scripts/health_check.py`.
2. Verificar frescura de datos, cuotas, lesiones y alineaciones.
3. `DIARIO_COMPLETO.bat` — encadena SETTLE → RUN en el orden seguro (auditoría
   2026-07-29, K-001: este loop indicaba `RUN_DIARIO_ALL.bat`, que invierte el
   orden crítico documentado en el README). **Consume cuota de API de pago:
   requiere aprobación humana salvo que corra como la tarea programada ya
   aprobada** (`.claude/automation/autonomy-policy.md`). Usar
   `RUN_DIARIO_ALL.bat` por separado solo si la liquidación ya se ejecutó.
4. Validar probabilidades `[0,1]`, duplicados, signos y timestamps.
5. Congelar event_id, mercado, línea, cuota, probabilidad, edge, fuentes y versiones.

## Artefactos
- `data/predictions/predictions_<liga>.csv` y `candidates_<liga>.csv`
- `data/predictions/report_<día>.md` y el dashboard HTML
- `data/calibration/served_<liga>.csv` (stream servido, base del calibrador)

## Validaciones
Pruebas focalizadas de pipeline, odds, edge y decisión.

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos de este loop:
- `BLOCKED`: el batch termina con código ≠ 0; leakage detectado; evento ya
  iniciado; datos críticos no frescos; `predictions_<liga>.csv` ausente o ilegible.
- `DEGRADED`: una liga se omitió por el guard de cuota o por un fallo transitorio
  del proveedor y el resto se generó. Nombrar la liga y la causa.
- `PASS`: artefactos escritos para todas las ligas activas y validaciones en verde.

## Acciones que requieren aprobación humana
Desactivar `shadow_mode`, cambiar stakes o bankroll, ampliar exposición, o gastar
cuota de API fuera de la ejecución programada.
