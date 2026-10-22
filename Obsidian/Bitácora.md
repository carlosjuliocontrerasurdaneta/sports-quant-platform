---
tags: [bitacora, moc, sqp]
creada: 2026-07-08
actualizada: 2026-10-22
---

# Bitácora — índice

Diario cronológico del proyecto: una nota por día con trabajo relevante, en `Bitácora/AAAA-MM-DD.md`. Cada entrada resume qué cambió, por qué, con qué commits y qué notas de la bóveda se actualizaron.

## Entradas

- [[Bitácora/2026-10-22]] — verificación independiente de `audit-2026-10-18`: APTO CON PENDIENTES (Fable); `certifi` a 2026.10.19 por GHSA-6q48-6c7w-9gw2; liquidación del 21-10 fallida, pendiente del operador.
- [[Bitácora/2026-10-20]] — line shopping activado con Pinnacle (operador en Chile; PokerStars no la cubre el proveedor); Fable APTO y addenda de régimen de `execution_price`.
- [[Bitácora/2026-10-18]] — auditoría integral `audit-2026-10-18` (17 hallazgos, 1 HIGH: NHL totals con el empate reglamentario como 2k) y remediación completa autorizada; Fable APTO CON CAMBIOS; secret scanning y push protection activados en GitHub; addenda de régimen en cinco pre-registros.
- [[Bitácora/2026-10-11]] — KI-071 corregido en código (`ed81aaa`): picks desplazados que se liquidaban dos veces y `void` fabricado por falta de local y visitante; 18 filas duplicadas pendientes de reparar con autorización. KI-066 verificado; KI-072 abierto (postemporada MLB con ratings congelados).
- [[Bitácora/2026-10-10]] — recencia del adaptador de totales: pre-registro (`027c019`), script (`f315f4c`) y fase H única (`e3f5469`): NBA y NFL ACEPTA, NHL RECHAZA por H5; Fable APTO; nada activado hasta la fase M (2027-01-31). NBA pretemporada: no hay calibradores NBA que recalibrar; `margin_sigma` medido (12,86 histórico, se queda en 13,0; deriva de época 14,4–14,8 pendiente de pre-registro).
- [[Bitácora/2026-10-09]] — batería de ajustes ejecutada: Enmienda 3 (dedupe de 15 gamePk MLB), 4/24 ACEPTA (totales NBA/NFL, ajustes 4 y 10); Fable: válido pero no activable (empeora contra la línea del mercado); propuesta de recencia en el adaptador de totales.
- [[Bitácora/2026-10-08]] — script de la batería de ajustes (6 ajustes × 4 ligas, Holm K=24) con `--pre`, `--parity-only` y modo completo; Enmiendas 1 y 2 del pre-registro; Fable APTO; nada medido todavía.
- [[Bitácora/2026-10-03]] — script de medición del pre-registro del tier A (`--contar` / `--medir`, 82 tests, tres rondas de Fable); primer `--contar` oficial con n = 0.
- [[Bitácora/2026-10-02]] — filtro por tier del Tipster (A/B/C/NO BET) y tarjeta de probabilidad prometida en la pestaña Historial; primera lectura: tier A acierta 47,7 % frente a 56,8 % prometido (386 picks); picks repetidos del ledger colapsados en el Historial; KI-071 abierto.
- [[Bitácora/2026-09-25]] — verificación de `audit-2026-09-22-r2`: APTO CON PENDIENTES; KI-061 corregido (la degradación con el registro ilegible no pausaba mercados); KI-062 (test de contención medido en intentos, no en reloj); el gate evalúa 52 cortes, por encima del límite de 50.
- [[Bitácora/2026-09-24]] — verificación de `audit-2026-09-23`: NO APTO por AUD-003; identidad exacta de eventos aplicada (ESPN resuelto, MLB fuera del fallback hasta KI-059) tras tres rondas de revisión Fable.
- [[Bitácora/2026-09-23]] — ronda `audit-2026-09-23` con dos auditores (Claude 5 + OpenAI 9 → 14 AUD); remediación: 13 implementados sin commit, AUD-003 bloqueado por FABLE-001 (el fallback histórico liquidaba picks sin jugar con el marcador de otro partido de la serie).
- [[Bitácora/2026-09-17]] — `SQP_Validate_OOS_Cdev` lanzada a mano: rc=0, 33/34 ligas validadas, sin overfit sistemático pero MLB/NHL mejor con historia completa; marcador modelo-vs-mercado: mercado mejor (Brier), selección con delta −6,45 % IC95 que roza el cero.
- [[Bitácora/2026-09-16]] — (a) correcciones de prompts/skills/loops y rediseño de fuentes únicas con generación y compatibilidad (83 pruebas, sin commit ese día; commiteado el 17/09 en `f93bdc1`); (b) directorio de producción restaurado desde copia del 14/09 (15 y 16/09 sin run); rama `codex/feature-signal-shadow` en verde tras renombrar `surface_elo`; la rama toca builders/mlb/ml_train (clase model-change, no mergeable sin champion-challenger); cross-review V2 INCOMPLETE: CLAUDE CLEAN, CODEX sin cuota.
- [[Bitácora/2026-09-14]] — remediación del consolidado: nueve correcciones implementadas, una bloqueada por identidad de eventos y tres investigaciones pendientes; verificación independiente requerida.

- [[Bitácora/2026-09-13]] — auditoría integral + remediación: repositorio reconstituido en producción (94+41 ficheros fuera de `main`), 4 de 7 días sin run, revalidación ciega tras las 00:00Z, líneas de cuarto, picks desplazados fuera del ledger, hooks armados por lecturas.
- [[Bitácora/2026-09-10]] — PMF vectorizada, validación de parámetros, pricing independiente con freeze, instalación portable y paquete local probado. Sin cambios a riesgo ni publicación GitHub.
- [[Bitácora/2026-09-09]] — diagnóstico de la integración Claude↔Codex: las tres vías operativas, la Forma 3 (centinela automático) documentada por fin; divergencia de binarios y PAT en claro fuera del repo.
- [[Bitácora/2026-08-04]] — auditoría y remediación integrada de `.claude`: routing, Fable 5, estados, permisos, health check y promoción humana por defecto.
- [[Bitácora/2026-08-02]] — auditoría integral, cierre de filas servidas pendientes y observatorio intradía v2.
- [[Bitácora/2026-07-14]] — pestaña Diagnóstico en el dashboard (auto-pausas del monitor de degradación + segmentos flageados).
- [[Bitácora/2026-07-13]] — consolidación de skills; revisión integral de calibración + gate `extreme_ok` (mlb_h2h LIVE); monitor de degradación con auto-pausa; diagnóstico por segmentos; auditoría full + remediación; limpieza de copias legacy.
- [[Bitácora/2026-07-12]] — filtro de frescura del cierre (≤90 min) en la auditoría CLV; lock del odds store; `stale_void`; retención de artefactos; candidato mlb_spreads obsoleto.
- [[Bitácora/2026-07-11]] — filtro por condición Home/Away y tarjeta % aciertos en la pestaña Historial del dashboard.
- [[Bitácora/2026-07-08]] — gate de CLV por mercado; KI-017 y KI-018 cerrados; scheduler final; bóveda Obsidian creada.

## Historia previa a la bóveda

El detalle de las sesiones 2026-06-12 → 2026-07-02 vive en `.claude/memory/session-summaries.md` (backfill de históricos, tuning de 18 ligas, señales por deporte, penalización de EV, banca dinámica, calibración por grupo, auditorías). Los hitos estructurales están sintetizados en [[Decisiones/Registro de decisiones]] y [[Errores y lecciones/Errores detectados y soluciones]]; los eventos que llevaron al shadow mode (2026-06-30 → 07-04) en [[Conocimiento/Calibración]] y [[Conocimiento/CLV y selección adversa]].
