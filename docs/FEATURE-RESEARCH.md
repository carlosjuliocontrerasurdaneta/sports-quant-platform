# Investigación de features pregame

## Alcance y estado

El evaluador es offline y exploratorio. No registra modelos, no altera los
coeficientes de producción y no envía apuestas. El resultado de una exploración
no autoriza su promoción: la selección de bloques debe confirmarse en una
ventana futura, separada del descubrimiento.

```powershell
python -B scripts/evaluate_feature_blocks.py --leagues all --out audit/feature_blocks.json
python -B scripts/evaluate_feature_blocks.py --leagues mlb wnba ncaaf atp --snapshots-dir data/sporting_snapshots --out audit/feature_blocks_enriched.json
```

`all` evalúa las ligas con CSV de resultados local. Las claves ATP/WTA corresponden
al circuito completo, no a un modelo independiente por torneo. `--window` (20
partidos por defecto), `--folds` (5), `--n-boot` (2000) y `--seed` (42) quedan
registrados. Cambiarlos después de ver resultados constituye otro experimento.

## Cuatro correcciones de datos/evaluación

- El medidor de correlaciones almacena features y desenlaces emparejados; las
  ausencias intermedias ya no desplazan las etiquetas.
- Pearson usa SciPy. Sus valores p son nominales: ni independencia temporal
  ni multiplicidad quedan resueltas por una correlación individual. Se retiró
  la sugerencia de convertir `r * 0.05` en un coeficiente de probabilidad.
- Los pitchers nulos no se convierten en una identidad compartida `nan`.
- Los constructores MLB/NBA/NFL/NHL actualizan resultados después de calcular
  el día completo. Entrenamiento, holdout y comparación ML mantienen días
  completos a ambos lados de cada frontera.

La huella de caché incluye los módulos temporal y común. Los datasets anteriores
deben reconstruirse con `scripts/build_features.py`; sus modelos entrenados
siguen siendo artefactos históricos y no se reinterpretan como corregidos.

## Bloques nuevos calculados con información local

| Bloque | Variables | Disponibilidad |
|---|---|---|
| `schedule` | Días de descanso y partidos en 7/14 días | Resultados de días anteriores |
| `opponent_form` | Residuos de victoria y margen respecto al adaptador, anotación/concesión y diferencias | Ventana de partidos anteriores |
| `venue_form` | Residuo de victoria en el rol local/visitante y tamaño de muestra | Ventana anterior; es rol del proveedor, no estadio verificado |
| `pitching` | FIP medio reciente de los abridores de cada equipo y cobertura | MLB: `starter_fip_mlb.csv`, retrasado por día |
| `sporting` | Proyecciones específicas por deporte e interacciones | Solo snapshots con disponibilidad acreditada |

El FIP por rotación no identifica al próximo abridor y no separa el bullpen.
No se etiqueta como calidad del abridor confirmado. En tenis se eliminan
features de anotación/margen que no tienen sentido en un store ganador=1,
perdedor=0. La orientación se aleatoriza determinísticamente por identidad,
independiente del marcador, incluyendo las columnas externas de cada lado.

## Contrato de snapshots externos

CSV `<league>.csv` con columnas obligatorias:

- `game_id`: ID inequívoco del mismo store de resultados, leído como texto.
- `available_at`: timestamp ISO con zona horaria, momento en que la proyección
  podía conocerse (no la fecha del partido ni del dato observado).
- `source`: procedencia de la proyección.

Las restantes columnas permitidas son `home_`/`away_` seguidas de:

| Familia | Campos y unidades |
|---|---|
| MLB | `starter_fip`, `bullpen_fip` (escala FIP); `starter_expected_innings` [0,9]; `bullpen_pitches_3d` (conteo); `lineup_xwoba` [0,1]; `park_run_factor` (multiplicador) |
| Baloncesto | `pace` (posesiones por partido); `off_rating`, `def_rating` (puntos por 100 posesiones); `available_rotation_minutes` (minutos proyectados) |
| Football | `qb_epa_per_play`, `off_epa_per_play`, `def_epa_per_play` (EPA por jugada); `plays_per_game`; `returning_snap_share` [0,1] |
| NHL | `goalie_gsax_per60`; `xgf_per60_5v5`, `xga_per60_5v5`; `power_play_rate`, `penalty_kill_rate` [0,1] |
| Fútbol | `xgf_per90`, `xga_per90`; `available_starter_minutes` (minutos proyectados) |
| Tenis | `surface_elo`; `serve_points_won_rate`, `return_points_won_rate` [0,1]; `minutes_played_7d` |

Ejemplo MLB (datos ilustrativos, no señal validada):

```csv
game_id,available_at,source,home_starter_fip,away_starter_fip
example-game,2026-09-14T20:00:00Z,example-projection,3.7,4.2
```

Solo entra la última versión disponible a las **00:00 UTC del día del partido**.
El corte conservador coincide con las features de resultados. Una versión
posterior se excluye; nunca se rellena hacia atrás. Cada versión es completa:
un campo ausente permanece ausente, no hereda automáticamente una versión vieja.
IDs ambiguos, versiones duplicadas, columnas desconocidas y valores infinitos
se rechazan. No se aceptan marcadores/resultados como campos de proyección.

Las interacciones incluyen diferencias entre lados, ritmo por eficiencia en
baloncesto, FIP ponderado por entradas de abridor/bullpen y xG del enfrentamiento.
Son entradas de un modelo aprendido, no ajustes manuales de probabilidad.

Sin proveedores de estas proyecciones y su archivo histórico, el bloque figura
como ausente. No se construyen lesiones, xG, superficie o quarterbacks a partir
de marcadores. Los resultados locales sí permiten investigación retrospectiva,
pero no prueban cuándo ingresó cada dato o corrección a la plataforma.

## Comparación y límites de interpretación

1. Folds expansivos sobre fechas completas; imputación y escalado solo en train.
2. Baseline aprendido a partir de las salidas del adaptador real configurado.
3. Cada bloque individual, todos juntos y ablación retirando un bloque.
4. Referencias adicionales: adaptador puro y tasa base/mediana de train.
5. Brier y log loss para ganador; tres clases para fútbol. Empates se excluyen
   en deportes con contrato de ganador binario. Totals mide MAE del marcador,
   no probabilidad de Over/Under ni ROI. Tenis no evalúa totales ficticios.
6. Intervalos por bootstrap agrupado por fecha, con Bonferroni por liga sobre
   los contrastes publicados. La dependencia entre fechas y la selección entre
   ligas siguen siendo limitaciones. `improvement_detected` no es promoción.
7. Huellas de código/configuración y fuentes en el reporte. Si el código cambia
   mientras se ejecuta, el CLI marca el reporte y termina con error.

Comparar contra cuotas requiere IDs, líneas, selección y horizonte exactamente
alineados. Este CLI no adivina equivalencias entre IDs ESPN y Odds API: declara
esa comparación `NOT_VERIFIABLE`. El evaluador existente `model_vs_market`
continúa siendo la referencia para las probabilidades realmente servidas.

## Confirmación antes de producción

El entrenamiento aislado y la captura prospectiva están implementados en
[`FEATURE-SHADOW.md`](FEATURE-SHADOW.md), con protocolo de ventana fija,
versiones congeladas y evaluación al cierre.

La selección reproducible del informe exploratorio está en
[`feature_candidates_20260915.json`](../audit/feature_candidates_20260915.json):
12 candidatos y dos bloques de rol en tenis diferidos hasta revisar la
orientación del proveedor. El manifiesto conserva las huellas del informe y
código de descubrimiento, la última fecha evaluada y el intervalo de cada
candidato. El manifiesto de selección es un borrador; el protocolo prospectivo
se congeló por separado en `data/models/feature_shadow_20260915_v2/protocol.json`,
con ventana 2026-09-16 a 2027-09-16 y sin garantía de potencia. No reutilizar el
período de descubrimiento como confirmación independiente. Las herramientas
quedaron integradas en el árbol principal el 2026-09-16; el experimento existente
continúa con su código congelado, según [FEATURE-SHADOW.md](FEATURE-SHADOW.md).

```powershell
python -B scripts/prepare_feature_candidates.py --report audit/feature_blocks_20260915.json --out audit/feature_candidates_new.json
```

El comando exige que el código haya permanecido estable durante la evaluación
y crea un archivo nuevo sin sobrescribir selecciones anteriores. Selecciona
bloques individuales cuyo intervalo corregido queda por debajo de cero;
no combina automáticamente varios ganadores ni modifica modelos guardados.

Congelar versión, bloque y mercado elegidos; registrar la hipótesis y la ventana
futura antes de medirla. Repetir Brier/log loss/calibración en esa ventana,
comparar a igual instante con el mercado y aplicar los gates canónicos vigentes.
Un bloque que ayuda al ganador no se aprueba automáticamente para spreads o
totals. La producción sigue usando sus parámetros actuales hasta esa evidencia.

## Pruebas

```powershell
python -B -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-features tests/test_feature_research.py tests/test_feature_shadow.py tests/test_feature_integration.py tests/test_measure_features_harness.py tests/test_feature_store.py tests/test_feature_manifest.py tests/test_mlb_features.py tests/test_ml_models.py tests/test_compare.py
python -B -m ruff check --no-cache src scripts tests
python -B -m mypy --cache-dir .codex-tmp/mypy-features src
```
