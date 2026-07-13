---
name: clv-shadow-exit
description: Use this skill to run or review the CLV audit and the shadow-mode exit evaluation — "evaluar CLV", "¿salimos del shadow mode?", CLV gate status, beat-close rate, or whether any (league, market) qualifies for real stake. Encodes the freshness filter and the exit rule so the evaluation is repeatable.
---

# CLV & Shadow Exit

Evaluación repetible del Closing Line Value y de la regla de salida del
shadow mode. El CLV es la métrica de gating de la plataforma: un mercado
solo puede llevar stake real si su CLV mediano es positivo con muestra
suficiente.

## Fuentes (no recalcular a mano)

- `python scripts/clv_analysis.py` → `daily_clv()` en `src/sqp/audit/clv.py`
  (también corre dentro del run diario).
- Salidas: reporte `data/bets/clv_AAAAMMDD.md` + registro del gate
  `data/bets/clv_gate.json` (allow-list que consume el run diario).

## Parámetros vigentes (verificar en `src/sqp/audit/clv.py` y `src/sqp/config.py`)

- **Frescura del cierre**: solo se emparejan snapshots a ≤90 min del inicio
  (`CLOSE_MAX_AGE_MIN = 90`). Sin esto el CLV=0 masivo era un artefacto de
  cierres viejos — reportes anteriores a 2026-07-12 NO son comparables.
- **Gate por (liga, mercado)**: mediana CLV > 0 sobre ≥ `clv_gate_min_n`
  (default 30) apuestas liquidadas emparejadas. Default-deny: sin registro,
  sin entrada o muestra fina → stake 0, flag `clv_gate`.
- **Salida del shadow mode (global)**: `shadow_clv_ok` = n emparejadas ≥
  `SHADOW_EXIT_MIN_N` (100) y mediana CLV > 0. El gate por mercado queda POR
  DEBAJO del shadow mode: al levantar el shadow, el clv_gate pasa a ser la
  regla de salida vinculante por mercado (`clv_gate_enabled` en yaml).

## Entregar

1. n emparejadas vs sin cierre (frescura), mediana CLV %, beat_close_rate.
2. Estado del gate: qué (liga, mercado) están permitidos y con qué n.
3. Veredicto shadow-exit: cumple / no cumple, con los números.
4. Si no cumple: qué falta (muestra o CLV) y ritmo estimado de acumulación.

## Reglas

- No abrir históricos completos ni `data/` a ciegas: usar el reporte
  markdown y el json del gate, no los CSV crudos.
- CLV positivo ≠ ganancia garantizada: reportar como evidencia de proceso,
  separada del ROI realizado.
- No relajar umbrales (min_n, frescura) para forzar una salida: la salida
  del shadow mode es decisión del usuario con esta evidencia delante.
