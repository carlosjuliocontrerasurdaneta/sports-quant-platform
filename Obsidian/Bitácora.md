---
tags: [bitacora, moc, sqp]
creada: 2026-07-08
actualizada: 2026-07-14
---

# Bitácora — índice

Diario cronológico del proyecto: una nota por día con trabajo relevante, en `Bitácora/AAAA-MM-DD.md`. Cada entrada resume qué cambió, por qué, con qué commits y qué notas de la bóveda se actualizaron.

## Entradas

- [[Bitácora/2026-07-14]] — pestaña Diagnóstico en el dashboard (auto-pausas del monitor de degradación + segmentos flageados).
- [[Bitácora/2026-07-13]] — consolidación de skills; revisión integral de calibración + gate `extreme_ok` (mlb_h2h LIVE); monitor de degradación con auto-pausa; diagnóstico por segmentos; auditoría full + remediación; limpieza de copias legacy.
- [[Bitácora/2026-07-12]] — filtro de frescura del cierre (≤90 min) en la auditoría CLV; lock del odds store; `stale_void`; retención de artefactos; candidato mlb_spreads obsoleto.
- [[Bitácora/2026-07-11]] — filtro por condición Home/Away y tarjeta % aciertos en la pestaña Historial del dashboard.
- [[Bitácora/2026-07-08]] — gate de CLV por mercado; KI-017 y KI-018 cerrados; scheduler final; bóveda Obsidian creada.

## Historia previa a la bóveda

El detalle de las sesiones 2026-06-12 → 2026-07-02 vive en `.claude/memory/session-summaries.md` (backfill de históricos, tuning de 18 ligas, señales por deporte, penalización de EV, banca dinámica, calibración por grupo, auditorías). Los hitos estructurales están sintetizados en [[Decisiones/Registro de decisiones]] y [[Errores y lecciones/Errores detectados y soluciones]]; los eventos que llevaron al shadow mode (2026-06-30 → 07-04) en [[Conocimiento/Calibración]] y [[Conocimiento/CLV y selección adversa]].
