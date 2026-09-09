---
name: clv-shadow-exit
description: Use this skill to run or review the CLV audit and the real-stake eligibility of a (league, market) — "evaluar CLV", "¿salimos del shadow mode?", CLV gate status, beat-close rate, or whether any market qualifies for real stake. Encodes the freshness filter and BOTH gates: prediction_gate is the governing exit rule since 2026-08-16 and clv_gate is currently disabled, so the verdict is derived from the effective configuration, never assumed.
---

# CLV & Shadow Exit

Evaluación repetible del Closing Line Value y del estado de las puertas de
stake real.

> **La regla de salida rectora YA NO es el CLV.** Desde el 2026-08-16 la
> sustituye el **prediction gate** (`configs/default.yaml`, bloque
> `prediction_gate`, con el razonamiento completo en su comentario y en
> `docs/research/2026-08-16-preregistro-regla-de-salida.md`). Este documento es
> de julio y afirmaba lo contrario; corregido en la auditoría del 2026-09-08.
>
> **Nunca declarar elegibilidad para stake real basándose solo en el CLV.**
> Antes de emitir un veredicto hay que LEER qué puerta está habilitada — no
> asumirlo desde aquí: `clv_gate.enabled` y `prediction_gate.enabled` en
> `configs/default.yaml`, con precedencia de entorno según
> `docs/CONFIG-PRECEDENCE.md`, y lo que efectivamente carga
> `src/sqp/pipeline/daily.py`. Estado en el momento de escribir esto:
> `shadow_mode: false`, `clv_gate.enabled: false`, `prediction_gate.enabled: true`.
>
> El CLV sigue siendo **evidencia independiente y valiosa** del proceso: mide si
> se batió al cierre. Simplemente no es, hoy, quien autoriza el dinero.

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
  `SHADOW_EXIT_MIN_N` (100) y mediana CLV > 0. Histórico: el shadow ya está
  levantado (`shadow_mode: false`).
- **Prediction gate (regla RECTORA desde 2026-08-16)**: un (liga, mercado) lleva
  stake real solo si cumple LAS DOS condiciones, sobre muestra FUERA DE MUESTRA
  (solo `game_date` posterior al pre-registro): (1) su modelo puro bate al
  mercado evento a evento — test de signo pareado, unilateral, empates
  excluidos, `n >= PREDICTION_GATE_MIN_N` (300) y `p < PREDICTION_GATE_ALPHA`
  (0,05); y (2) su EV a stake plano es positivo. Constantes en
  `src/sqp/risk/prediction_gate.py`; registro `data/bets/prediction_gate.json`,
  reescrito por `scripts/update_prediction_gate.py`. Default-deny.
  Consulta rápida del estado: `python scripts/gate_status.py`.
- **Las dos puertas son default-deny y se acumulan**: un mercado necesita que la
  puerta HABILITADA lo permita. Un CLV mediano positivo con el prediction gate
  denegando **no** hace elegible al mercado.

## Entregar

1. **Qué puerta está habilitada**, leída de la configuración efectiva, antes de
   cualquier veredicto.
2. n emparejadas vs sin cierre (frescura), mediana CLV %, beat_close_rate.
3. Estado del **prediction gate**: mercados evaluados, cuántos permitidos, y el
   `n` máximo alcanzado frente a `min_n`.
4. Estado del **clv_gate**: permitidos y con qué n — etiquetado como secundario
   mientras `clv_gate.enabled` sea `false`.
5. Veredicto de elegibilidad para stake real: cumple / no cumple **según la
   puerta habilitada**, con los números de ambas.
6. Si no cumple: qué falta (muestra o señal) y ritmo estimado de acumulación.

## Reglas

- No abrir históricos completos ni `data/` a ciegas: usar el reporte
  markdown y el json del gate, no los CSV crudos.
- CLV positivo ≠ ganancia garantizada: reportar como evidencia de proceso,
  separada del ROI realizado.
- No presentar el CLV como la regla vinculante mientras `prediction_gate` sea la
  puerta habilitada, ni al revés: el veredicto se deriva de la configuración
  leída, nunca de lo que diga este documento de memoria.
- No relajar umbrales (min_n, frescura) para forzar una salida: la salida
  del shadow mode es decisión del usuario con esta evidencia delante.
