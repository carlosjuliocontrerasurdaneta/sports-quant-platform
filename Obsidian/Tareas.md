---
tags: [tareas, sqp]
creada: 2026-07-08
actualizada: 2026-07-13
---

# Tareas

Pendientes activos del proyecto, por prioridad. Al completar una: marcarla, anotar el commit y reflejar el cambio en la [[Bitácora]].

## En curso (fase shadow — el sistema trabaja solo)

- [ ] **Evaluar la regla de salida del shadow** (CLV mediano + Brier). Volumen cumplido (n=191 con cierre genuino al 07-12, tras el filtro de frescura ≤90 min); falta que algún (liga, mercado) logre mediana > 0 con n≥30 (el más cercano: WTA Wimbledon h2h, n=21) y que un calibrador pase el gate de Brier. El run diario + captura horaria lo hacen automáticamente; revisar la auditoría CLV periódicamente.
- [x] 2026-07-12 — ~~Revisar/promover el candidato de calibración MLB spreads~~. Obsoleto: staging está vacío — el candidato del 07-01 no se regenera con los gates vigentes (iso mejora ECE 0.1461→0.1076 pero empeora Brier OOS; beta falla Brier+monotonía). Nada que promover; ver [[Bitácora/2026-07-12]].

## Backlog

- [ ] Perf (auditoría 07-12): `load_closing_odds` concatena todos los meses de odds por llamada; filtrar por rango de meses relevante cuando el histórico crezca.
- [ ] Seguimiento del quota-guard del proveedor de odds (follow-up de closing-capture).
- [ ] KI-002: verificar nombres ESPN vs Odds API en soccer cuando el Apertura MX reactive la liga (~post 19-jul); re-validar dc_rho de UCL/Chile con temporada nueva.
- [ ] KI-006 (parcial): moneyline MLB/NHL sigue sin señal específica validada (abridor refutado ×2 — no re-perseguir; portero NHL sin construir, alto riesgo de rechazo).
- [ ] KI-005: vendor de resultados para Frauen-Bundesliga.
- [ ] NFL OOS: requiere mejora `--start/--end` en `backfill_historical_odds.py` (ventana Sept 2025–Feb 2026); sin gasto hasta decidirlo.
- [ ] KI-016: decidir si `run_daily.py` se deprecia o queda como herramienta manual/demo.

## Completadas recientemente

- [x] 2026-07-13 — Diagnóstico automático por segmentos (`sqp/audit/segments.py`): favorito/underdog, lado, banda de prob., banda de línea; flags de sobre/subconfianza y Brier vs mercado; integrado al run diario. Dry-run: 22/94 segmentos flageados. Ver [[Bitácora/2026-07-13]].
- [x] 2026-07-13 — Monitor de degradación por (liga, mercado) con auto-pausa gated (`sqp/risk/degradation.py`): Brier vs mercado o ROI plano bajo umbral → pausa; histéresis para reanudar; unión con `paused_markets`. Dry-run: pausaría mlb_spreads, tenis Wimbledon h2h x2 y wnba_totals. Ver [[Bitácora/2026-07-13]].
- [x] 2026-07-13 — Auditoría full + remediación de los 4 hallazgos menores: gate SESSIONNAME en DIARIO_COMPLETO.bat, helper `rest_days` unificado en features/common.py (+2 tests), docstring de budget.py y comentario de .gitignore al día. 361/361 verdes. Ver [[Bitácora/2026-07-13]].
- [x] 2026-07-12 — Retención de artefactos (hallazgo 4 de la auditoría): `purge_old_artifacts` (allowlist estricta: `archive/`, `clv_*.md`, `.closing_credits_*`; 90 días) + `scripts/purge_artifacts.py`, cableado best-effort en `BACKFILL_ALL.bat` semanal.
- [x] 2026-07-12 — Auditoría full del proyecto + fixes: lock anti-concurrencia en el odds store + Capture_Close desfasada a :30; void por expiración (`stale_void`, 3 días) para partidos cancelados; `requirements.lock.txt`. Ver [[Bitácora/2026-07-12]].
- [x] 2026-07-12 — Auditoría de la masa de CLV=0 y filtro de frescura del cierre (≤90 min) en la auditoría CLV; el gate deja de estar sesgado a mediana 0. Ver [[Bitácora/2026-07-12]].
- [x] 2026-07-11 — Port del linaje Nc2 a `C:\dev` (5 commits `a2027b9`..`96d8535`: eventos independientes en calibración, `beat_close` estricto, mediana real de consenso, scoping por día, exit codes, `Settings.validate()`) y retiro de la copia paralela de `C:\Nueva carpeta (2)` (tareas `_Nc2` eliminadas, respaldo en `C:\ZIP`).
- [x] 2026-07-11 — Filtro por condición Home/Away + tarjeta % aciertos en pestaña Historial del dashboard.
- [x] 2026-07-08 — Gate de CLV por (liga, mercado) (`bc27252`).
- [x] 2026-07-08 — KI-018: "nan" en columna Línea (`11bd999`).
- [x] 2026-07-08 — KI-017: e2e de liquidación de tenis (`7471ce4`).
- [x] 2026-07-08 — Scheduler final: DIARIO_COMPLETO único orquestador (`fa59ff2`).
- [x] 2026-07-08 — Bóveda Obsidian como segundo cerebro.
