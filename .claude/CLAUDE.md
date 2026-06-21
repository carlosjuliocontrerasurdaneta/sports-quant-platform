# Sports Quant Platform

Plataforma Python de analítica cuantitativa deportiva (MLB, NBA, NFL, NHL):
ETL, feature engineering, modelado probabilístico, calibración, edge,
gestión de riesgo y backtesting. Código en `src/` (paquete `sqp`),
scripts en `scripts/`, tests en `tests/`.

## Reglas permanentes

- No escanear `data/`, `historical/`, `logs/` ni `exports/` (también bloqueado vía permisos `deny`).
- No abrir CSV ni Parquet completos: usar encabezados, muestras (`nrows`) o esquemas.
- No analizar modelos no relacionados con la tarea.
- No generar documentación salvo solicitud explícita.
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

## Entorno

- Windows + PowerShell. Tests: `PYTHONPATH=src pytest tests/ -q`.
- Ejecución diaria orquestada por `RUN_DIARIO_ALL.bat` (multi-liga, reporte consolidado); liquidación/auditoría por `SETTLE_ALL.bat`.
