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

## Loop: Daily Prediction Loop

## Reglas comunes

- Cumplir `.claude/CLAUDE.md`, `.claude/ORCHESTRATOR.md` y `.claude/automation/autonomy-policy.md`.
- Ejecutar `/memoria-cargar` al inicio y actualizar `.claude/automation/runtime/current-task.md`.
- No promover modelos, calibradores ni cambios de producción sin aprobación humana explícita.
- No usar información posterior al inicio del evento para evaluar o reconstruir una predicción previa.
- Mantener snapshots inmutables, trazabilidad de versiones y evidencia de cada comando.
- Presupuesto predeterminado: 8 iteraciones; detenerse ante guardrails o evidencia insuficiente.
- Finalizar con `/verification-gate` y `/memoria-guardar`.
- Cerrar declarando `PASS`, `DEGRADED`, `BLOCKED` o `DONE` según las definiciones exactas de `.claude/loops/quant/STATES.md`, con la evidencia que lo justifica en `current-task.md`.

## Objetivo
Generar probabilidades estimadas reproducibles y congelar snapshots antes del inicio de cada evento.

## Precondiciones
- La cohorte anterior debe liquidarse antes de generar la nueva. **El run diario
  SOBRESCRIBE `data/predictions/candidates_*.csv`**, así que ejecutarlo antes de
  liquidar destruye la cohorte pendiente (queda recuperable en
  `data/predictions/archive/`, pero el orden correcto es el inverso). Ver
  `README.md`, "Orden crítico".
- Registrar si la liquidación ya se ejecutó para evitar repetirla.
- `configs/default.yaml` legible y `Settings.validate()` sin error.

## Inputs
- Cuotas de The Odds API (proveedor de **pago**).
- `data/historical/results_<liga>.csv` para el ajuste de ratings.

## Comandos
1. `python scripts/claude_project_health.py` y `python scripts/health_check.py`.
2. Verificar frescura de datos, cuotas, lesiones y alineaciones.
3. Elegir exactamente una ruta:
   - Si la liquidación todavía no se ejecutó, usar `DIARIO_COMPLETO.bat`, que
     encadena SETTLE → RUN en el orden seguro.
   - Si la liquidación ya se ejecutó y quedó evidencia, usar únicamente
     `RUN_DIARIO_ALL.bat`; no repetir settlement.
   Ambas rutas consumen cuota de API de pago y requieren aprobación humana salvo
   que corran como una tarea programada ya aprobada.
4. Validar probabilidades `[0,1]`, duplicados, signos y timestamps.
5. Congelar event_id, mercado, línea, cuota, probabilidad, edge, fuentes y versiones.

## Artefactos
Los artefactos por liga son obligatorios para las ligas seleccionadas para
ejecución. Registrar por separado las ligas activas excluidas por el guard de
cuota; no usar sus archivos antiguos como evidencia de generación actual.

- `data/predictions/predictions_<liga>.csv` y `candidates_<liga>.csv`
- `data/predictions/report_<día>.md` y el dashboard HTML
- `data/calibration/served_<liga>.csv` (stream servido, base del calibrador)

## Validaciones
Pruebas focalizadas de pipeline, odds, edge y decisión.

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos de este loop:
- `BLOCKED`: el batch termina con código ≠ 0; leakage detectado; evento ya
  iniciado; datos críticos no frescos; `predictions_<liga>.csv` de una liga
  seleccionada ausente o ilegible. Un fallo transitorio del proveedor que
  provoca salida ≠ 0 sigue siendo `BLOCKED`, aunque otras ligas se generen.
- `DEGRADED`: una liga activa se omitió por el guard de cuota, todos los comandos
  requeridos terminaron con código 0 y las ligas seleccionadas dejaron los
  artefactos actuales y validaciones satisfactorias. Nombrar ligas omitidas,
  causa, ligas generadas y sus conteos. Si no se generó ninguna liga activa,
  no se cumplió el objetivo: `BLOCKED`.
- `PASS`: artefactos escritos para todas las ligas activas y validaciones en verde.

## Acciones que requieren aprobación humana
Cambiar stakes, bankroll o exposición; modificar `prediction_gate` (el gate rector
actual — `shadow_mode` fue levantado el 2026-08-16 y ya no es el control activo);
o gastar cuota de API fuera de la ejecución programada.

## Loop: Postgame Settlement Loop

## Objetivo
Liquidar picks de forma determinista contra el snapshot original.

## Precondiciones
- Existe el snapshot de la cohorte. Un archivo de candidatos vacío es un caso
  válido y debe cerrar con evidencia de `n_emitidos = 0`; un snapshot ausente es
  `BLOCKED`.
- Debe correr ANTES del run diario del día (ver loop 01, orden crítico).

## Comandos
1. `SETTLE_ALL.bat`. **Consume cuota de proveedores externos: requiere aprobación
   humana salvo que corra como la tarea programada ya aprobada.**
2. Verificar resultado oficial y reglas del mercado.
3. Clasificar `WIN`, `LOSS`, `PUSH`, `VOID` o `PENDING`.
4. Evitar doble liquidación (dedup en `sqp.settlement.runner`).
5. Reconciliar `emitidos = WIN + LOSS + PUSH + VOID + PENDING`.
6. Guardar score, proveedor y regla aplicada.

## Artefactos
- `data/bets/settled_<liga>.csv` cuando existen liquidaciones persistidas.
- `data/calibration/served_<liga>.csv` con las filas graduadas cuando existe
  stream servido para la cohorte.
- Para una cohorte vacía inicial, ambos archivos pueden no existir. Registrar
  en `current-task.md` la ruta y legibilidad del snapshot, `n_emitidos = 0` y
  ausencia comprobada de pendientes tanto servidos como archivados/desplazados.
  Un CSV ilegible o un snapshot ausente no demuestran una cohorte vacía.

## Criterios de salida
Definiciones exactas en `.claude/loops/quant/STATES.md`. Específicos:
- `BLOCKED`: score inconsistente, identidad de equipo/jugador ambigua, snapshot
  ausente, o la reconciliación no cuadra.
- `DEGRADED`: quedan `PENDING` por resultados aún no publicados; registrar cuántos
  y de qué liga.
- `PASS`: reconciliación cuadrada, sin pendientes y artefactos aplicables
  legibles. Para una cohorte válida con `n_emitidos = 0` y sin pendientes
  servidos ni archivados/desplazados, basta la evidencia de vacío anterior;
  no exigir ni crear un `settled_<liga>.csv` o stream servido artificial.
- `DONE`: además, la cohorte finita queda cerrada sin pendientes y se cumplen las
  condiciones generales de `DONE`.
