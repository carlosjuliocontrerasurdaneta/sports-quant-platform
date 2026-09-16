# Validación futura de features

## Código versionado en esta rama

Esta rama recupera la implementación en `src/sqp/` y `scripts/feature_shadow.py`,
con sus pruebas. No modifica el checkout principal ni el capturador ya iniciado.
Las rutas `outputs/` y `data/models/` mencionadas abajo describen la ejecución
local del 15 de septiembre: esos datos y modelos no se suben a Git.
Para una ejecución nueva, usar `python -B scripts/feature_shadow.py train` con
datos locales y fechas futuras explícitas. Los comandos con fechas fijas de
abajo documentan el experimento original, no deben reutilizarse después de su inicio.

## Qué ejecuta

El script aislado `outputs/feature-shadow-runtime-20260915/scripts/feature_shadow.py`
entrena cada uno de los 12 candidatos seleccionados
y su referencia con el historial de descubrimiento verificado por SHA-256.
Cada pareja conserva las mismas familias y parámetros del experimento original:
regresión logística para ganador y Ridge para total de puntos/goles.
No escribe en el registro de modelos de producción ni modifica apuestas.

La carpeta del experimento contiene modelos, datos de entrenamiento, selección,
protocolo, versiones de Python/dependencias y copia de `src/sqp` y configuración.
El protocolo solo se publica después de completar todos los entrenamientos.
Las huellas de archivos detectan cambios accidentales; no constituyen una firma
externa ni un registro independiente de la hora de creación.

Durante el trabajo se detectó la retirada concurrente de los módulos/scripts
nuevos del árbol principal y la reversión de sus modificaciones. No se restauró
ese árbol: la implementación se conserva en la copia aislada y en el `frozen/`
del experimento. La primera versión `feature_shadow_20260915` queda como referencia
sin capturas publicadas. La ejecución vigente es `feature_shadow_20260915_v2`.

## Protocolo fijado

- Ventana: **2026-09-16 00:00 UTC a 2027-09-16 00:00 UTC**, extremo final excluido.
  El año calendario cubre temporadas de las ocho ligas/circuitos seleccionados.
- Tamaño: todos los eventos elegibles capturados en esa ventana. No hay parada
  por resultados ni garantía de potencia; se publicarán muestra y faltantes.
- Cada candidato se compara con su referencia aprendida y el adaptador operativo.
  Error Brier para ganador; MAE del marcador total. Log loss y calibración son
  descriptivos para ganador. El total no es una probabilidad de Over/Under.
- Pesos congelados. El estado deportivo usa resultados locales de días UTC
  anteriores a la captura y al evento, archivados con cada lote.
- Se conserva la primera captura anterior al inicio por candidato, proveedor e ID.
  Se aplica `event_horizon_days` registrado en el protocolo, tomado del ajuste
  canónico de la plataforma (por defecto siete días), y se calcula el historial
  una sola vez por liga/fuente para todos sus fixtures elegibles.
  Los cambios de horario no sustituyen esa predicción; si el inicio final difiere,
  se excluye al liquidar y se cuenta entre los faltantes.
- Una evaluación al cierre: bootstrap por fecha, 20.000 remuestreos, semilla 42,
  alfa familiar 0,05 dividido entre los 24 contrastes. No se evalúa antes del fin.
  La dependencia entre fechas sigue siendo una limitación.
- Empates excluidos en ganador binario; incluidos para total del marcador.
- No hay promoción automática ni conclusión contra cuotas.

## Entrenar y capturar

```powershell
python -B outputs/feature-shadow-runtime-20260915/scripts/feature_shadow.py --data-root outputs/feature-shadow-runtime-20260915 train --manifest audit/feature_candidates_20260915.json --report audit/feature_blocks_20260915.json --out data/models/feature_shadow_20260915_v2 --start 2026-09-16T00:00:00Z --end 2027-09-16T00:00:00Z
```

Después de entrenar, usar siempre el script congelado, pasando la raíz real de
los datos. Las versiones de dependencias deben coincidir con las registradas.

```powershell
python -B data/models/feature_shadow_20260915_v2/frozen/scripts/feature_shadow.py --data-root C:/dev/3/sports-quant-platform capture --experiment data/models/feature_shadow_20260915_v2
python -B data/models/feature_shadow_20260915_v2/frozen/scripts/feature_shadow.py --data-root C:/dev/3/sports-quant-platform watch --experiment data/models/feature_shadow_20260915_v2
```

`capture` lee eventos futuros de los CSV de cuotas existentes. No consulta APIs,
consume créditos ni interpreta las cuotas como features. `watch` comprueba cambios
en esos archivos cada 60 segundos. Depende de que el flujo normal siga guardando
cuotas/resultados: no realiza su descarga. No es un servicio instalado ni reinicia
automáticamente al encender Windows. `heartbeat.json` muestra estado y errores;
crear un archivo `STOP` en el experimento lo detiene. Un cierre abrupto puede dejar
`worker.lock`: comprobar que su PID ya no vive antes de retirarlo para reiniciar.

Fixtures de otra fuente pueden ingresarse con `capture --fixtures ruta.csv`:

```csv
league,game_id,home,away,start_time,source
nba,example-game,Team A,Team B,2026-10-20T23:00:00Z,example-provider
```

Se rechazan columnas de resultados, identidades vacías/duplicadas y horas sin
zona. Se filtran eventos ya iniciados, fuera de ventana o ligas no seleccionadas.
El ejemplo es ilustrativo y no forma parte de las capturas reales.

Los lotes archivan fixtures, históricos usados, features efectivamente pasadas
al modelo, orientación de participantes, predicciones y hora de captura.
Un lote incompleto no tiene `predictions.json` y no entra en evaluación.

## Evaluación al cierre

Se requiere CSV con resultados finales y columnas exactas:
`league,source,game_id,home,away,home_score,away_score,start_time`.
`start_time` es el inicio real con zona horaria. Los IDs deben pertenecer al mismo
proveedor de la captura; no se adivinan equivalencias entre ESPN y Odds API.
Los nombres deben coincidir exactamente, admitiendo lados invertidos. No incluir
resultados parciales ni eventos anulados. Los no emparejados se contabilizan.

```powershell
python -B data/models/feature_shadow_20260915_v2/frozen/scripts/feature_shadow.py --data-root C:/dev/3/sports-quant-platform evaluate --experiment data/models/feature_shadow_20260915_v2 --outcomes final_results.csv --out audit/feature_shadow_final.json
```

La ventana futura todavía no ha sucedido. No hay métricas prospectivas actuales,
ni se puede garantizar captura continua durante apagados o fallos del proveedor.
