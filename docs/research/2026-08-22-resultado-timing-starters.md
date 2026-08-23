# Resultado: Experimento de timing — starters MLB vs movimiento de línea

**Fecha:** 2026-08-22  
**Pre-registro:** docs/research/2026-08-22-preregistro-timing-starters.md  
**Script:** `scripts/timing_experiment.py`  
**Veredicto:** BLOQUEADO — pero revela el siguiente paso concreto

---

## Hallazgos

### Hallazgo 1 (CRÍTICO): los starters no se capturan en tiempo real

Todos los 1,045 abridores MLB de la temporada 2026 tienen el mismo
`ingested_at`: **2026-06-13 00:52:11+00:00** — un backfill masivo único.

El sistema nunca registró cuándo aprendió por primera vez quién lanzaba.
Sin ese timestamp no hay experimento de timing: no se puede comparar
"cuándo lo supo el sistema" con "cuándo movió el mercado".

### Hallazgo 2: estructura del mercado MLB pre-partido (agosto 2026)

Sobre 301 eventos MLB con snapshots pre-partido:

| Métrica | Valor |
|---|---|
| Eventos con movida >= 3pp pre-partido | 26 (8.6%) |
| Mediana: mins antes del commence cuando mueve | 235 min (3.9 h) |
| p25 | 127 min |
| p75 | 451 min |
| Apertura de línea -> primera movida: mediana | 1,081 min (18 h) |

**Interpretación:** cuando el mercado mueve pre-partido, lo hace típicamente
3–4 horas antes del partido, después de que la línea estuvo abierta ~18 horas
sin moverse. El run diario se ejecuta a las 11:00 AM, que para partidos
nocturnos (7–10 PM) equivale a 8–11 horas de adelanto sobre el commence.
Eso es más que la mediana de movida (3.9 h), pero sin el timestamp real
del sistema no se puede confirmar si hay ventaja.

### Hallazgo 3: predictions_mlb.csv SÍ contiene home_pitcher/away_pitcher

Las predicciones archivadas (`data/predictions/archive/predictions_mlb_FECHA.csv`)
contienen pitcher confirmado al momento del run diario. La fecha del archivo
es el proxy de timestamp. Esto es información real-time capturada diariamente
que podría usarse para el experimento — pero falta el timestamp exacto de
generación (solo existe la fecha del archivo, no la hora).

---

## Brecha de infraestructura a cerrar

Para ejecutar el experimento completo se necesita ONE única adición:

**Guardar `pitcher_confirmed_at` con timestamp UTC preciso en cada run diario.**

Lugar natural: `StartersStore.save()` ya graba `ingested_at`. El problema es
que el backfill sobreescribió todos los timestamps con la fecha de backfill.

Solución mínima: añadir un archivo de log separado en
`data/historical/pitcher_confirmation_log_mlb.csv` con columnas:

```
run_date, game_date, home, away, home_pitcher, away_pitcher, confirmed_at_utc
```

Cada ejecución de `fetch_probable_pitchers()` añade una fila SOLO cuando
el pitcher es nuevo o cambió respecto al día anterior (upsert por cambio).
Después de 30+ partidos el experimento es ejecutable.

---

## Veredicto de la hipótesis

La hipótesis original ("el sistema captura abridores antes de que el mercado
mueva") **no puede verificarse ni falsificarse** con la infraestructura actual.

No es MUESTRA_INSUFICIENTE — es ausencia de medición. La brecha es
estructural: el sistema nunca registró cuándo aprendió el pitcher.

---

## Siguiente acción (concreta, aprobable)

Implementar `pitcher_confirmation_log_mlb.csv` en el run diario:

1. En `scripts/run_all.py` (o `pipeline/daily.py`), tras el fetch de pitchers,
   llamar a una función `log_pitcher_confirmation(league, rows, run_ts)`.
2. La función abre/crea `data/historical/pitcher_confirmation_log_mlb.csv`
   y añade filas solo para pitchers nuevos o cambiados.
3. Acumular >= 30 partidos (aprox. 10–15 días hábiles de MLB).
4. Re-ejecutar `scripts/timing_experiment.py`.

**Costo estimado:** ~40 líneas de código + 2 semanas de acumulación.

---

## Lo que este experimento ya aportó

Aunque el veredicto es BLOQUEADO, el análisis reveló que:

1. El sistema tiene un gap de observabilidad: sabe los pitchers pero no CUÁNDO los supo.
2. El mercado MLB mueve pre-partido en el 8.6% de los casos, con mediana 3.9 h antes.
3. El run diario a las 11 AM estaría estructuralmente adelantado a esa ventana —
   si el sistema capturara el timestamp de confirmación, el experimento sería positivo
   o negativo con 30 partidos.

Estos son los únicos tres hechos que emergen de los datos disponibles.
No se afirma ventaja; se afirma que la medición correcta todavía no existe.
