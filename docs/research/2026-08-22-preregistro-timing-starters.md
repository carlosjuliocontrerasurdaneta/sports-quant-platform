# Pre-registro: Experimento de timing — starters MLB vs movimiento de línea

**Fecha de pre-registro:** 2026-08-22  
**Autor:** Carlos Contreras (pre-registrado antes de analizar los datos)  
**Script de análisis:** `scripts/timing_experiment.py`  
**Commit de referencia:** pendiente (debe commitearse antes del primer análisis)

---

## Hipótesis

El sistema captura abridores confirmados (home + away) de MLB antes de que el
mercado de moneyline mueva su precio en una cantidad estadísticamente significativa.

Si la hipótesis es correcta, `t_starter_ingested < t_primera_movida_significativa`
para una mayoría de partidos, con una mediana positiva del delta en minutos.

---

## Definiciones exactas (fijadas antes de ver los datos)

### Muestra válida

Solo partidos donde `ingested_at` se produjo en los 5 días calendario anteriores
al `commence_time` del evento (excluye el backfill histórico, donde `ingested_at`
refleja la fecha de ingesta masiva, no el descubrimiento en tiempo real).

Filtro: `0 < (commence_time - ingested_at) <= 120 horas`

### Movida significativa de línea

Se calcula en el mercado `h2h` de The Odds API (bookmaker: Pinnacle cuando
disponible, caso contrario media de los bookmakers que cotizan ambos lados).

1. Convertir `price_decimal` a probabilidad sin vig por el método de suma inversa.
2. Tomar la primera snapshot del evento como precio de apertura `p0`.
3. Una "movida significativa" ocurre cuando `|p_t - p0| >= 0.03` (3 pp) en dos
   snapshots consecutivas. Se registra el timestamp de la primera de esas dos.
4. Si el evento no tiene movida ≥ 0.03 antes del `commence_time`, se descarta
   de la muestra (no hay señal que medir).

### Métrica primaria

`delta_min = t_primera_movida_significativa - ingested_at` en minutos.

- `delta_min > 0` → el sistema conocía el starter ANTES de que el mercado moviera.
- `delta_min < 0` → el mercado movió ANTES de que el sistema registrara el starter.

### Estadísticos a reportar

- `n` total de partidos en muestra válida
- `n_con_movida` (partidos con movida ≥ 0.03)
- Mediana de `delta_min` con intervalo de confianza bootstrap 95%
- Percentiles 10/25/75/90 de `delta_min`
- Fracción de partidos donde `delta_min > 0`

### Criterio de decisión (pre-registrado)

| Resultado | Condición |
|---|---|
| VENTAJA_TEMPORAL | mediana `delta_min > 60 min` Y fracción con `delta > 0 >= 0.60` Y `n >= 30` |
| MARGINAL | mediana `delta_min > 0` pero < 60 min O fracción < 0.60 |
| SIN_VENTAJA | mediana `delta_min <= 0` |
| MUESTRA_INSUFICIENTE | `n_con_movida < 30` |

Solo `VENTAJA_TEMPORAL` justifica construir una estrategia de timing sobre starters.
`MARGINAL` justifica extender la muestra. `SIN_VENTAJA` cierra esta hipótesis.

---

## Trampas a vigilar

1. **Ingesta en batch vs tiempo real**: verificar que `ingested_at` del período
   reciente no refleje re-ingestas masivas con timestamp de hoy.
2. **Movidas por otras causas**: un starter confirmado no es la única razón para
   que una línea se mueva. El experimento mide correlación temporal, no causalidad.
3. **Bookmaker selection bias**: distintos bookmakers mueven en momentos distintos;
   el análisis debe ser consistente en la selección.
4. **n insuficiente**: la temporada MLB 2026 en el sistema comienza en 2026-03; los
   datos de timing real (no backfill) pueden ser escasos.

---

## Qué NO mide este experimento

- Si la movida fue causada por el starter (puede haber otras causas).
- Si ese timing es suficiente para ejecutar apuestas antes del movimiento.
- Rentabilidad. Una ventaja temporal de 90 minutos no implica profit.
