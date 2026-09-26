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

---

## Enmiendas previas a la ejecución (2026-09-26, revisión independiente de Fable 5.1)

Revisión en solo lectura: **APTO CON CAMBIOS**. Se aplican todos. Se redactan **antes** de la ejecución y **antes** de unir clima con carreras. La descarga ya hecha con el texto original **se descarta** y se repite con estas reglas. Donde chocan con el texto de arriba, mandan estas.

**E1. Clima (fuente y hora).** `models=gfs_seamless` fijo. Es el modelo de la API con archivo de pronósticos previos más largo (temperatura desde 2021), y la primera fecha con datos que devuelva para viento y lluvia se registra en el informe. `wind_speed_unit=kmh`, `timezone=UTC`. Se toma la **hora truncada** del inicio (`dt.hour`, la regla de `weather._hourly_at` en producción), no la más próxima. Si se activa, producción debe pasar el mismo `models`.

**E2. Base con abridores.** Las filas de `ResultsStore("mlb")` se enriquecen con `StartersStore.attach` y `StarterFIPStore.attach`, igual que en la re-medición del abridor. Se informa la cobertura. Limitación: son los abridores anunciados que guarda el histórico, y afectan igual a los dos brazos.

**E3. Universo.** Además de `roofType == "Open"`, se excluyen de los dos brazos:
- `roofType` ausente;
- partidos con menos de 9 entradas completas, salvo los que terminan en la parte alta de la 9.ª porque gana el local. Las casas anulan los totales de partidos acortados. Si solo se excluyeran los que tienen menos de 8,5 entradas, el coeficiente de lluvia ganaría log loss por un canal que no paga;
- partidos suspendidos y reanudados otro día.
Los aplazados ya faltan del histórico: es un sesgo de selección benigno, porque en producción esos picks se anulan. `roofType` es metadato actual del estadio: cubre bien las sedes de cada partido, no reformas del techo.

**E4. Alineación.** La base se reconstruye con el mismo orden que `engine.walk_forward_backtest`. El script comprueba con aserciones que la probabilidad de cada línea coincide con la del motor (tolerancia 1e-12) y aborta si no.

**E5. Brazo de control.** Además de la base (Δp = 0), un brazo `Δp = c` constante para todos los partidos del universo, estimado en el mismo entrenamiento. El tratamiento debe batirlo en el test (criterio 5). Se informa el `bias` de la base por partición. Motivo: sin intercepto, un coeficiente negativo puede ganar log loss solo por corregir una sobreestimación general del Over.

**E6. Criterio 1 (decisión del operador, 2026-09-26: «Solo afectados»).** El margen se exige sobre el **subconjunto afectado** del test: partidos con viento pronosticado > 20 km/h o lluvia pronosticada > 0. Se define solo con el pronóstico, antes del resultado, así que no hay leakage. Motivo: el precedente de 0,002 venía de un parámetro que actuaba en todos los partidos evaluados. Aplicarlo a partidos donde Δp = 0 por construcción diluye el efecto y rechaza por diseño. Antes de unir con carreras se informan la fracción afectada f y la distribución de viento y lluvia.

**E7. Criterios, sustituyen a los de arriba (todos a la vez):**
1. Δ log loss tratamiento − base **≤ −0,002** en el subconjunto afectado del test combinado.
2. Δ log loss tratamiento − base **< 0** en el subconjunto afectado de cada partición.
3. ECE del tratamiento **≤** ECE de la base en todo el universo abierto del test combinado.
4. Coeficientes de la partición B **negativos**. Es una convención de la forma funcional (`weather.py`), no un argumento físico: la velocidad sin dirección no tiene signo a priori.
5. Log loss del tratamiento **<** log loss del control de intercepto, en todo el universo abierto del test combinado.
«Test combinado» = unión de los partidos de test de A y B, con media por partido y línea.

**E8. Incertidumbre.** Bootstrap por **bloques de fecha** (se remuestrean días completos), 10.000 réplicas, semilla 42, para el Δ del criterio 1. Se informa el IC95. No es puerta de aceptación: exigir que el extremo superior sea < 0 sería un umbral nuevo que el operador no ha fijado.

**E9. Estimación.** Nelder-Mead desde (0, 0) sobre el log loss medio de las tres líneas, con el recorte [0,01; 0,99] incluido, `xatol=1e-7`, `fatol=1e-10`, `maxiter=2000`, sin límites. Si un solo coeficiente sale negativo, **no** se reajusta con un solo coeficiente: el criterio 4 falla. ECE con la función `expected_calibration_error` del proyecto por defecto, uniendo las tres líneas.

**E10. Regla de re-ejecución.** Solo se repite la ejecución si aparece un defecto de **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal unidas o descarga incompleta. Se documenta el defecto y se commitean las dos salidas. Un resultado adverso no es motivo para repetir.

**E11. Informes secundarios añadidos (no deciden):**
- el mismo Δp evaluado contra la **línea de totales capturada** (`roi_engine.load_closing_odds`, línea principal del consenso) sobre la muestra con cuotas disponible;
- Δ log loss con el viento **centrado por estadio**, para medir cuánto del efecto es residuo del factor parque.

**E12. Activación, si llegara.** Filtrar **también** `Retractable`, además de `Dome`. Usar el mismo `models`. Recalibrar en staging, porque los calibradores MLB se entrenaron sin clima. Anotar el efecto sobre el test de `mlb|totals` del gate y sobre «el modelo manda».

**E13. Limpieza del calendario (detectada antes de medir, sin marcadores).** El calendario de MLB repite el `gamePk` de cada partido aplazado en su fecha original, con estado `Postponed` y `abstractGameState` Final: 94 `Postponed` y 35 `Cancelled` en la descarga. Esas filas se descartan y el clima es el de la fecha en que el partido **sí** se jugó. También trae pretemporada y exhibiciones, que no están en el histórico: el universo son los `game_id` del histórico. Tras la limpieza hay 7.244 partidos, justo los del histórico de 2024–2026.

## Informe previo (solo clima, SIN marcadores), 2026-09-26

`measure_weather_mlb.py --pre` sobre la descarga con las enmiendas (`gfs_seamless`, hora truncada):

| Concepto | Valor |
|---|---|
| Partidos 2024–2026 | 7.244 |
| Excluidos: techo no abierto | 1.852 |
| Excluidos: menos de 9 entradas | 10 |
| Excluidos: reanudados | 8 |
| **Universo abierto** | **5.374** (5.370 con pronóstico) |
| Primera fecha con pronóstico | 2024-03-20 (toda la temporada 2024 cubierta) |
| Fracción afectada f (viento > 20 km/h o lluvia > 0) | **0,181** |
| Afectados por temporada | 2024: 313 · 2025: 317 · 2026: 344 |
| Viento: mediana / p90 / p95 / p99 | 13,4 / 22,5 / 25,6 / 30,8 km/h |
| Partidos con viento sobre el umbral | 15,9 % |
| Partidos con lluvia pronosticada > 0 | 3,0 % (mediana 0,7 mm) |

**Potencia (derivación de la revisión de Fable):** para mejorar el log loss en 0,002 hace falta una corrección de ≈ 3,2 pp de media cuadrática, porque cerca de p = 0,5 la ganancia es ≈ 2δ². En el test hay 661 partidos afectados (317 de 2025 y 344 de 2026).
