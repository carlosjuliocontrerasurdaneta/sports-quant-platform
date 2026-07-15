# Current Task

Status: done
Loop: feature
Iteration: 6 / 8
Owner: principal-orchestrator

## Objective

Palanca de velocidad de información contra la selección adversa (autorización
total del operador, 2026-07-14 PM): snapshot completo de liga en la captura,
observatorio de edge intradía (medición pura) y captura cada 30 min.

## Acceptance criteria

- [x] Captura persiste snapshot completo y reporta bet_events (test RED→GREEN).
- [x] `log_intraday_edges` loguea edge h2h servido-vs-consenso fresco sin crear
      picks ni tocar stakes (4 tests nuevos).
- [x] Flag `intraday_scan_enabled`: OFF en Settings() directo, ON via yaml,
      env gana.
- [x] Suite completa verde + ruff + mypy.
- [x] Trigger PT30M con StartWhenAvailable y duración indefinida intactos.

## Evidence log

- pytest: 407/407 (antes 403; +4 intradía, contrato de captura actualizado).
- ruff: All checks passed. mypy: 84 archivos sin issues.
- Scheduler verificado: Interval=PT30M, StartWhenAvailable=True, NextRun 21:30.
- Gasto de cuota acotado sin cambios: ligas-con-pick-inminente + cap 300/día
  + min_remaining 100 (el fetch de liga completa ya se pagaba; solo se dejó
  de descartar su contenido).

## Risks and approvals

- Cuota: pases 2× en ventanas con eventos inminentes; cap diario inalterado.
- Experimentos en curso no contaminados: no se crean picks; el log intradía
  es archivo nuevo, aparte del flujo settle/gate.
- Autorización del operador: total (sesión 2026-07-14 PM), incluye commit,
  push y cambio de scheduler.

## Next decision

Acumular 2–4 semanas de `intraday_edge_log.csv` y del snapshot completo;
luego: (a) análisis CLV intradía vs 11:00 (decide #4 ofensiva), (b) re-correr
`clv_by_line_movement.py` con trayectorias densas.
