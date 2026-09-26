# Pre-registro — ¿el pronóstico del tiempo mejora los totales MLB?

**Fecha:** 2026-09-26. Escrito **antes** de descargar ningún dato de clima y antes
de mirar ninguna relación entre clima y carreras. Lo único consultado hasta ahora
es la forma de las dos APIs (una llamada de prueba a cada una) y el recuento de
partidos por temporada del histórico. Orden del operador: «Sí, lanza la medición
del clima».

## La pregunta

El sistema tiene un factor clima programado y apagado (`configs/default.yaml`,
bloque `weather:`: `enabled: false`, `wind_coef_totals: 0.0`,
`precip_coef_totals: 0.0`, `wind_threshold_kmh: 20.0`). Su forma funcional
(`src/sqp/features/weather.py::weather_p_adjustment`) es:

    Δp(Over) = wind_coef · max(0, viento_kmh − 20) + precip_coef · precip_mm
    Δp(Under) = −Δp(Over)

sumado a la probabilidad del modelo y acotado a [0,01; 0,99]
(`adjust_model_probability`). Nunca se ha medido. Este documento fija qué tendría
que pasar para darle coeficientes distintos de 0.

**Se mide esa forma funcional y ninguna otra.** Temperatura, dirección del viento
y humedad quedan fuera: añadir variables después de ver los datos sería buscar
una señal a medida.

## Lo que ya se sabe (y va en contra)

- El consenso de mercado ya incorpora el pronóstico: las casas lo publican. Con
  `market_shrink = 0,5`, la ganancia posible en la probabilidad servida es como
  mucho la mitad de la que se mida aquí.
- Siete mediciones previas no encontraron ventaja sobre el feed público de
  cuotas (memoria del proyecto, 2026-08-05 a 2026-09-07).

## Datos

- **Partidos:** histórico MLB (`ResultsStore("mlb")`) con fecha entre 2024-01-01 y
  2026-09-24. El límite inferior no es una elección: es el primer día con
  pronósticos archivados en la API de Open-Meteo que se usa (abajo).
- **Hora, estadio y techo de cada partido:** API pública del calendario MLB
  (`statsapi.mlb.com/api/v1/schedule`, `hydrate=venue(location,fieldInfo)`),
  enlazada por `gamePk` = `game_id`. Da la hora de inicio en UTC, las
  coordenadas del estadio **de ese partido** (así cubre las sedes temporales y
  los cambios de estadio: Athletics en Oakland/Sacramento, Rays en 2025) y
  `roofType`.
- **Universo evaluado:** solo estadios con `roofType == "Open"`. `Dome` y
  `Retractable` se excluyen: con techo retráctil no se sabe si estaba abierto.
- **Clima:** Open-Meteo *Previous Runs API*
  (`previous-runs-api.open-meteo.com/v1/forecast`), variables
  `wind_speed_10m_previous_day1` y `precipitation_previous_day1`: el **pronóstico
  emitido 24 h antes** para la hora del partido, en UTC, a la hora más próxima al
  inicio. **No** se usa el endpoint de archivo (clima observado), porque sería
  información que no existía antes del partido. En producción el pick se genera
  entre ~4 h y varios días antes, así que 24 h es una aproximación razonable del
  plazo real.
- **Partidos sin pronóstico:** reciben Δp = 0, igual que en producción cuando
  falla la consulta. Se cuentan y se informa la cobertura.

## Modelo y métrica

- **Base:** configuración de producción de MLB en `49a6181`
  (`_league_meta("mlb")`: `pitcher_bound 0.05`, `tilt_scale 0.4`,
  `park_bound 0.10`). Walk-forward de `sqp.backtesting.engine`, con todo el
  histórico desde 2023 como calentamiento. `P(Over)` contra las líneas fijas
  **7,5 / 8,5 / 9,5** (`total_lines`). Con líneas de medio punto no hay empujes.
- **Tratamiento:** `P'(Over) = clip(P(Over) + Δp, 0,01, 0,99)` con la fórmula de
  arriba y el umbral de 20 km/h de la configuración, que no se ajusta.
- **Métrica primaria:** log loss medio de `P(Over)` sobre las tres líneas,
  tratamiento menos base, en los partidos de estadio abierto del periodo de
  test.

## Estimación y validación

Los dos coeficientes se estiman minimizando el log loss medio de las tres líneas
**solo en el periodo de entrenamiento**, sin restricción de signo. Dos
particiones temporales:

| Partición | Entrenamiento | Test |
|---|---|---|
| A | temporada 2024 | temporada 2025 |
| B | 2024 + 2025 | 2026 (hasta el 24/09) |

## Criterio de aceptación (todas a la vez)

1. Δ log loss **≤ −0,002** sobre el test combinado (A + B). Es el mismo margen
   que usaron las decisiones del abridor (2026-06-12, 2026-06-16).
2. Δ log loss **< 0** en cada partición por separado.
3. ECE combinada del tratamiento **≤** la de la base.
4. Los coeficientes estimados en B son **negativos** (viento y lluvia bajan el
   Over). Un signo positivo sería una señal espuria de la muestra.

Si falla cualquiera: **no se activa**, los coeficientes siguen en 0 y el
resultado se commitea igual.

## Si se acepta: lo que haría falta antes de activarlo

No se toca producción en esta medición. Activar requiere un cambio aparte, con
aprobación:

- filtrar por techo: hoy `get_event_weather` se aplicaría también a estadios con
  cúpula;
- coordenadas por partido y no por equipo (`configs/venues.yaml` fija los
  Athletics en Sacramento en todas las temporadas);
- `weather.enabled: true` y los coeficientes estimados en la partición B.

## Informes secundarios (no deciden nada)

- Δ log loss solo en los partidos con Δp ≠ 0.
- Cobertura: partidos del universo, con pronóstico y excluidos por techo.

## Compromisos

Una sola ejecución. Los scripts viven en `scripts/research/`. NFL y NCAAF quedan
fuera: no hay coordenadas de estadio en `venues.yaml`, y desde 2024 la muestra de
NFL es de unos 780 partidos.
