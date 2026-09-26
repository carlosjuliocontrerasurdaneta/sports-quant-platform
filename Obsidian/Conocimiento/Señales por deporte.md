---
tags: [modelo, señales, sqp]
creada: 2026-07-08
actualizada: 2026-09-26
---

# Señales por deporte

Regla de activación: una señal solo se enciende si **bate al baseline fuera de muestra** (held-out incluido). La regla funcionó en ambos sentidos — aceptó una, rechazó dos.

## ✅ ACTIVA: Park factor MLB → totals (2026-06-22)

- `sqp/models/park.py::ParkFactors`: carreras en juegos de LOCAL vs de VISITA del mismo equipo (aísla el parque del nivel ofensivo). Regresado por muestra, acotado, walk-forward (leakage-safe). Escala AMBAS lambdas → mueve Over/Under, no el moneyline.
- Evidencia OOS: totals ROI −17.1% → **+2.8%** (bound 0.10); MLB global +2.4% → +7.8%; held-out confirma (−15.9% → +3.8%/+7.0%).
- Config: `mlb.park_bound: 0.10` en `ratings.yaml`; mlb/totals des-pausado (van juntos).

## ✅ ACTIVA: Descanso/back-to-back NBA → h2h y spreads (2026-09-26)

- `RestModel` en el adaptador: `nba.rest_points_per_day: 0.795` (tope de 4 días). Solo NBA; `rest_days_coef` sigue en 0.
- Pre-registro con revisión Fable, ejecución única: **ACEPTA 5/5**. Δ log loss en afectados −0,00224 (IC95 [−0,00371; −0,00076]); `c` estable 0,81 / 0,88 / 0,80 en las tres particiones.
- Advertencias de Fable: el criterio 1 pasa por poco; parte del efecto es sesgo de ventaja de campo (estimado junto al intercepto, `c` ≈ 0,5-0,6); 2025-26 salió ligeramente positiva. Pendiente: recalibrar `nba_h2h/nba_spreads` en staging y re-medir `margin_sigma`. `docs/research/2026-09-26-resultado-descanso-basket.md`

## ❌ RECHAZADAS (infra queda dormida, no-op)

| Señal | Veredicto | Evidencia |
|---|---|---|
| **Abridor MLB v1 (RA)** | Rechazada 2026-06-12 → **ACTIVADA 2026-09-26 por orden del operador** (`pitcher_bound: 0.05`) | En junio, cualquier peso empeoraba el log loss. Re-medida el 26/09 con 9.629 juegos: bound 0.05 −0,00087 log loss y ECE 0,0077→0,0061; bound ≥0,20 empeora. **No alcanza el margen 0,002**: activa por orden, no por evidencia concluyente. Ver [[Bitácora/2026-09-26]] |
| **Abridor MLB v2 (FIP)** | Rechazada 2026-06-16 | solo empata al baseline (−0.0007 log loss < margen 0.002); ECE empeora. NO volver a perseguirlo (refutado dos veces) |
| **Clima MLB (viento/lluvia → totals)** | Rechazada 2026-09-26 | Pre-registro con revisión Fable: 0/5 criterios. Δ log loss en afectados **+0,0075** (IC95 [+0,0014; +0,0148]): empeora. Un intercepto constante lo supera; el ajuste de 2024 absorbía sesgo de nivel. `docs/research/2026-09-26-resultado-clima-mlb.md` |
| **Rest/B2B basketball** | Rechazada 2026-06-22 → **NBA ACTIVADA 2026-09-26** (ver arriba); WNBA/NCAAB sin base | fuerte en ventana completa pero NO generaliza en held-out (WNBA spreads −38%→−48% con el mejor parámetro); no-monótona; n minúsculo. `rest_points_per_day: 0.0` |

## Otros ajustes de modelo activos

- **tilt_scale MLB 0.4** (era 0.8): el fix real de la sobreconfianza MLB per-game — Brier 0.2474 bate baseline 0.2491.
- **Dixon-Coles** (`dc_rho` por liga soccer): corrige el empate subestimado del Poisson independiente (Liga MX −0.10).
- **Decaimiento por recencia 180d** en tasas de anotación (2026-07-04): corrigió el sesgo Under de WNBA (avg_total 171 verificado).
- **Tenis**: Elo de jugador tour-wide desde ESPN. Su mala precisión es **inadecuación del modelo Elo**, no datos obsoletos (verificado 2026-07-04). Corre en shadow.
- Ventaja local Elo y dc_rho tuneados por liga en `configs/leagues/ratings.yaml` (18 ligas; MLB validado OOS como generalizante).

Relacionado: [[Conocimiento/Validación OOS]], [[Errores y lecciones/Lecciones aprendidas]].
