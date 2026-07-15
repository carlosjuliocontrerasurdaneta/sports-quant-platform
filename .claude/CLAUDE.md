# Sports Quant Platform

Plataforma Python de analítica cuantitativa deportiva (MLB, NBA, NFL, NHL):
ETL, feature engineering, modelado probabilístico, calibración, edge,
gestión de riesgo y backtesting. Código en `src/` (paquete `sqp`),
scripts en `scripts/`, tests en `tests/`.

## Reglas permanentes

- No escanear `data/`, `historical/`, `logs/` ni `exports/` (también bloqueado vía permisos `deny`).
- No abrir CSV ni Parquet completos: usar encabezados, muestras (`nrows`) o esquemas.
- No analizar modelos no relacionados con la tarea.
- No generar documentación salvo solicitud explícita (excepción: la bóveda Obsidian, ver abajo).
- Preferir modificaciones locales y lectura selectiva.

## Control de costos

Antes de abrir archivos: identificar candidatos, abrir el mínimo posible,
detenerse cuando exista evidencia suficiente. Priorizar glob, búsqueda,
encabezados y firmas de funciones sobre lectura completa. No releer
archivos ya analizados en la sesión salvo que hayan cambiado.

## Lenguaje obligatorio en outputs de apuestas

- Siempre "probabilidad estimada", nunca certezas ni profit garantizado.
- Separar: probabilidad estimada, probabilidad implícita, edge, ROI esperado estimado y ROI realizado.

## Memoria persistente

- Al iniciar sesión de trabajo: ejecutar `/memoria-cargar`.
- Al cerrar sesión con trabajo relevante: ejecutar `/memoria-guardar`.

## Segundo cerebro Obsidian (obligatorio desde 2026-07-08)

La bóveda `Obsidian/` es la fuente central de conocimiento del proyecto.
Todo cambio relevante (feature, fix, decisión, hallazgo, config de producción,
resultado de validación) debe reflejarse en la MISMA sesión:

1. Entrada en `Obsidian/Bitácora/AAAA-MM-DD.md` (qué, por qué, commits).
2. Actualizar las notas temáticas afectadas y su frontmatter `actualizada:`.
3. `Estado del proyecto.md` solo si cambia el estado operativo; `Tareas.md` siempre que aplique.
4. Committear la bóveda junto con el trabajo que documenta.

Convenciones y estructura: `Obsidian/Metodología de documentación.md`.
NUNCA abrir la raíz del repo como bóveda (solo `Obsidian/`).

## Entorno

- Windows + PowerShell. Tests: `PYTHONPATH=src pytest tests/ -q`.
- Ejecución diaria orquestada por `RUN_DIARIO_ALL.bat` (multi-liga, reporte consolidado); liquidación/auditoría por `SETTLE_ALL.bat`.

## Sistema operativo autónomo

- Orquestación: `.claude/ORCHESTRATOR.md`.
- Decisión y límites: `.claude/automation/`.
- Loops especializados: `.claude/loops/`.
- Para clasificar una tarea: `/route-task`.
- Para evaluar salud: `/project-health`.
- Para mantenimiento autónomo acotado: `/autopilot`.
- Antes de declarar finalización: `/verification-gate`.

La autonomía siempre está limitada por `.claude/automation/autonomy-policy.md`.
