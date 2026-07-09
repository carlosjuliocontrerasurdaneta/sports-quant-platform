---
tags: [modelo, señales, sqp]
creada: 2026-07-08
actualizada: 2026-07-08
---

# Señales por deporte

Regla de activación: una señal solo se enciende si **bate al baseline fuera de muestra** (held-out incluido). La regla funcionó en ambos sentidos — aceptó una, rechazó dos.

## ✅ ACTIVA: Park factor MLB → totals (2026-06-22)

- `sqp/models/park.py::ParkFactors`: carreras en juegos de LOCAL vs de VISITA del mismo equipo (aísla el parque del nivel ofensivo). Regresado por muestra, acotado, walk-forward (leakage-safe). Escala AMBAS lambdas → mueve Over/Under, no el moneyline.
- Evidencia OOS: totals ROI −17.1% → **+2.8%** (bound 0.10); MLB global +2.4% → +7.8%; held-out confirma (−15.9% → +3.8%/+7.0%).
- Config: `mlb.park_bound: 0.10` en `ratings.yaml`; mlb/totals des-pausado (van juntos).

## ❌ RECHAZADAS (infra queda dormida, no-op)

| Señal | Veredicto | Evidencia |
|---|---|---|
| **Abridor MLB v1 (RA)** | Rechazada 2026-06-12 | cualquier peso empeora el log loss monotónicamente; la señal RA mezcla bullpen y ofensa rival. `pitcher_bound: 0.0` |
| **Abridor MLB v2 (FIP)** | Rechazada 2026-06-16 | solo empata al baseline (−0.0007 log loss < margen 0.002); ECE empeora. NO volver a perseguirlo (refutado dos veces) |
| **Rest/B2B basketball** | Rechazada 2026-06-22 | fuerte en ventana completa pero NO generaliza en held-out (WNBA spreads −38%→−48% con el mejor parámetro); no-monótona; n minúsculo. `rest_points_per_day: 0.0` |

## Otros ajustes de modelo activos

- **tilt_scale MLB 0.4** (era 0.8): el fix real de la sobreconfianza MLB per-game — Brier 0.2474 bate baseline 0.2491.
- **Dixon-Coles** (`dc_rho` por liga soccer): corrige el empate subestimado del Poisson independiente (Liga MX −0.10).
- **Decaimiento por recencia 180d** en tasas de anotación (2026-07-04): corrigió el sesgo Under de WNBA (avg_total 171 verificado).
- **Tenis**: Elo de jugador tour-wide desde ESPN. Su mala precisión es **inadecuación del modelo Elo**, no datos obsoletos (verificado 2026-07-04). Corre en shadow.
- Ventaja local Elo y dc_rho tuneados por liga en `configs/leagues/ratings.yaml` (18 ligas; MLB validado OOS como generalizante).

Relacionado: [[Conocimiento/Validación OOS]], [[Errores y lecciones/Lecciones aprendidas]].
