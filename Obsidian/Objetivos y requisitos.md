---
tags: [objetivos, requisitos, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Objetivos y requisitos

## Objetivo del sistema

Plataforma Python de analítica cuantitativa deportiva (MLB, NBA/WNBA, NFL, NHL, soccer multi-liga, tenis ATP/WTA) que:

1. **Estima probabilidades pregame** calibradas por evento y mercado (h2h, spreads, totals).
2. **Detecta edges** contra las cuotas de mercado (The Odds API) separando probabilidad estimada, implícita no-vig, edge y ROI esperado estimado.
3. **Gestiona riesgo** (Kelly fraccionado con caps por apuesta, por día por liga y global; banca dinámica por ledger).
4. **Se audita a sí misma**: liquidación idempotente, ROI realizado por liga/mercado, CLV contra cierre capturado, backtesting walk-forward y validación OOS.

**El objetivo NO es apostar cuanto antes**: es acumular evidencia de ventaja real (CLV mediano positivo + calibración que pase gates OOS) antes de arriesgar capital. Estado actual: [[Estado del proyecto|SHADOW MODE]].

## Requisitos funcionales vigentes

- Run diario orquestado (`DIARIO_COMPLETO.bat`: settle → run encadenado) + captura horaria de cierre + backfill/refresh semanal + OOS mensual. Ver [[Arquitectura/Automatización y operación]].
- Todo pick se registra aunque no sea accionable (stream servido para calibración sin sesgo de selección).
- Promoción de calibradores y salida del shadow mode son **decisiones humanas explícitas**, nunca automáticas.
- Reporte HTML autónomo (sin assets externos) con picks, auditoría, patrones e historial filtrable.

## Restricciones y reglas duras

- **Disciplina OOS**: ninguna señal/parámetro/calibrador se activa sin batir al baseline fuera de muestra (regla aplicada: abridor MLB rechazado, rest/B2B rechazado, park factor aceptado).
- **Integridad de datos**: raw preservado, append-only, dedup por clave con game_id, nunca rellenar datos ausentes con defaults.
- **Anti-leakage**: features solo con información disponible pregame; validación temporal, nunca splits aleatorios.
- **Cuota de API**: The Odds API con presupuesto limitado; todo gasto de créditos históricos se autoriza explícitamente.
- **Veracidad**: nunca prometer profit; siempre "probabilidad estimada".

## Criterio de éxito (regla de salida del shadow)

Un (liga, mercado) se promueve a stake real solo si:
1. Su **CLV mediano es positivo** sobre ≥30 apuestas liquidadas emparejadas a cierre capturado (gate automático `clv_gate.json`, ver [[Conocimiento/CLV y selección adversa]]), y
2. La calibración pasa el **gate de Brier OOS** tras ~100 picks liquidados en shadow.
