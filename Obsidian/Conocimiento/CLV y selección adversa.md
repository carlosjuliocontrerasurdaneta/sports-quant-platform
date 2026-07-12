---
tags: [clv, riesgo, sqp]
creada: 2026-07-08
actualizada: 2026-07-12
---

# CLV y selección adversa

**CLV (Closing Line Value)** = valor de la cuota tomada vs la cuota de cierre. Es LA métrica de gating del proyecto desde el 2026-06-30: mide si los picks capturan valor real contra el mercado, independientemente de la varianza de resultados.

## El hallazgo que lo motivó (2026-06-30)

Barrido de shrink sobre apuestas MLB reales (n=71): incluso con s=1.0 (probabilidad justa del mercado pura, sin modelo) se pierde — 0.524 estimado vs 0.465 observado. Conclusión: el edge está **adversamente seleccionado** (CLV negativo); el problema no es solo sobreconfianza del modelo sino QUÉ picks selecciona. La calibración no puede arreglar eso; el CLV sí lo detecta.

## Infraestructura

- **Captura de cierre**: tarea horaria `Capture_Close` (live desde ~2026-06-28) → el CLV es medible hacia adelante.
- **Auditoría CLV diaria**: integrada al run diario (commit `7c539a4`); empareja apuestas liquidadas con el cierre capturado y calcula CLV por segmento (liga, mercado).
- **Gate de CLV por (liga, mercado)** (2026-07-08, commit `bc27252`): `src/sqp/risk/clv_gate.py` + registro `data/bets/clv_gate.json` reescrito por la auditoría diaria.

## El gate de CLV (regla de salida por mercado)

Allow-list **default-deny** para stake real:

- Un (liga, mercado) solo puede llevar stake si su **CLV mediano > 0** sobre **≥ 30** apuestas liquidadas emparejadas a cierre capturado.
- **Filtro de frescura del cierre (2026-07-12)**: solo cuenta como "cierre" un snapshot capturado a **≤ 90 min** del comienzo (`CLOSE_MAX_AGE_MIN` en `sqp/audit/clv.py`); sin captura fresca la apuesta queda como `sin_cierre`.
- Sin registro / sin entrada / muestra fina → stake 0 con flag `clv_gate`.
- Config: `clv_gate: {enabled: true, min_n: 30}` en `configs/default.yaml`; env vars `CLV_GATE_ENABLED` / `CLV_GATE_MIN_N` ganan.
- Mientras `shadow_mode: true` el gate es invisible (shadow ya pone todo en 0); al levantar el shadow se convierte en la regla vinculante **por mercado**: implementa "promover a stake real solo con CLV mediano positivo" de forma granular, no todo-o-nada.

## Auditoría de la masa de CLV=0 (2026-07-12)

Síntoma: mediana de CLV exactamente 0.0000 en casi todos los mercados con solo ~23% batiendo el cierre → >50% de las apuestas tenían CLV exactamente cero.

Causa raíz: `load_closing_odds` tomaba "el último snapshot antes del comienzo" **sin importar su antigüedad**. Para apuestas sin captura fresca (todas las previas a que `Capture_Close` entrara en vivo ~07-01, y las que escapan a la ventana/presupuesto), el "cierre" era el snapshot matinal — el mismo del que salió el precio de entrada → **CLV ≡ 0 por construcción**. Números de la auditoría (n=457 emparejadas): 59.3% con CLV=0; antigüedad mediana del "cierre" ~2.8 h, p75 >10 h; en el 58% de las apuestas el cierre tenía >90 min. La cobertura de cierre genuino mejora por semana (W24 17% → W27 69%), confirmando el corte del 07-01.

Efecto: la masa de ceros sesgaba la mediana del gate hacia 0 — hacía la regla de salida **incumplible e irrefutable a la vez**.

Fix (mismo día): `max_age_min` en `load_closing_odds` (default `None`, sin cambio para el backtest de ROI) + `CLOSE_MAX_AGE_MIN = 90` en la auditoría CLV. Con el filtro: n=191 emparejadas, batió-el-cierre 23%→41%, %CLV=0 baja a ~25% (líneas genuinamente sin movimiento a granularidad de consenso mediano). Ningún mercado pasa aún el gate; el más cercano es WTA Wimbledon h2h (mediana +0.46%, n=21 de 30). MLB/WNBA siguen con CLV medio negativo — la selección adversa persiste con medición honesta.

Relacionado: [[Estado del proyecto]], [[Conocimiento/Calibración]], [[Objetivos y requisitos]].
