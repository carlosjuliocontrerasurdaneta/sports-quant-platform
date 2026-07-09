---
tags: [clv, riesgo, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
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
- Sin registro / sin entrada / muestra fina → stake 0 con flag `clv_gate`.
- Config: `clv_gate: {enabled: true, min_n: 30}` en `configs/default.yaml`; env vars `CLV_GATE_ENABLED` / `CLV_GATE_MIN_N` ganan.
- Mientras `shadow_mode: true` el gate es invisible (shadow ya pone todo en 0); al levantar el shadow se convierte en la regla vinculante **por mercado**: implementa "promover a stake real solo con CLV mediano positivo" de forma granular, no todo-o-nada.

Relacionado: [[Estado del proyecto]], [[Conocimiento/Calibración]], [[Objetivos y requisitos]].
