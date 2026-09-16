# Integración de investigación de features — 2026-09-16

## Resultado

Las herramientas experimentales están integradas localmente en `src/` y
`scripts/`. Los dos archivos de pruebas que antes no podían importarse ahora
se ejecutan. La integración no promueve candidatos al pipeline diario.

Se recuperaron del runtime aislado cuatro módulos nuevos (`temporal`, `research`,
`feature_blocks`, `feature_shadow`) y su CLI. Los CLIs de evaluación exploratoria
y selección se recuperaron de `.codex-tmp/commit-feature-shadow`, inspeccionando
sus diferencias antes de incorporarlos. Las copias originales y el experimento
congelado se conservaron.

## Correcciones integradas

- Constructores MLB/NBA/NFL/NHL: calculan el día completo antes de incorporar
  resultados; los pitchers ausentes no acumulan un historial compartido.
- Validación ML y comparación: entrenamiento, holdout y selección de mezcla
  respetan días completos. La referencia usa el adaptador configurado.
- Caché: incorpora el código temporal y común en su huella de invalidación.
- Correlaciones: cada variable conserva su resultado asociado; Pearson usa
  SciPy y no se recomiendan coeficientes derivados de la correlación.
- Trazabilidad: el CLI exploratorio calcula hashes sobre los mismos bytes que
  evaluó, incluso si la fuente local se actualiza durante la ejecución.

Los modelos y datasets históricos de producción no se reconstruyeron ni se
reinterpretaron como entrenados con estas correcciones. Una futura construcción
de datasets detectará el cambio de huella.

## Validación ejecutada

1. 119 pruebas pertinentes aprobadas: investigación, shadow, integración,
   constructores, caché, medición, entrenamiento ML, comparación, corte temporal
   y pipeline demo.
2. Después se añadió un caso independiente de evaluación prospectiva sintética:
   las 11 pruebas de `test_feature_integration.py` pasaron (10 se solapan con el
   conjunto anterior). Total: **120 casos distintos comprobados**.
3. Ruff sin errores; mypy sin errores en 105 archivos de código fuente.
4. Recopilación de la suite completa sin errores de importación. No se repitió
   íntegramente la suite general de 22 minutos de la tarea anterior.
5. CLI de selección ejecutado sobre el informe original: conserva 12 candidatos
   y 2 diferidos. Los CLIs integrados muestran su ayuda correctamente.

Los tests verifican perturbaciones de resultados futuros, exclusión del mismo
día, cortes de entrenamiento, disponibilidad de snapshots, ausencia de etiquetas
en fixtures, integridad de modelos, prohibición de evaluar antes del cierre,
emparejamiento de participantes y exclusión de inicios reprogramados. El caso
sintético comprueba Brier 0,04 frente a referencia 0,25 y ECE 0,20; esas cifras
son pruebas de software, **no métricas del experimento real**.

## Experimento prospectivo preservado

Evidencia estructurada: [feature_integration_20260916.json](feature_integration_20260916.json).

- 12 parejas candidato/referencia; hashes de modelos, selección, entrenamiento,
  protocolo y código/configuración congelados comprobados.
- 1 lote completo, 101 primeras predicciones y 96 eventos.
- Capturas anteriores al inicio, en la ventana del protocolo; salidas finitas
  y probabilidades binarias dentro de [0,1]. Fixtures e históricos archivados
  coinciden con sus hashes registrados.
- Se detectó el proceso antiguo 2456 ausente y su bloqueo residual. Tras comprobar
  que no había otro capturador, se conservó el bloqueo en `.codex-tmp/` y se inició
  el watcher congelado como proceso oculto 8760. Estado `RUNNING` comprobado, sin
  errores de arranque y sin nuevos eventos elegibles. PID y estado son una
  observación de esta sesión, no garantía de continuidad.
- Sigue dependiendo de datos locales y del equipo encendido. No se instaló un
  servicio de Windows ni se alteró el protocolo para arrancar automáticamente.

El código integrado tiene otra huella. Para capturar y evaluar el experimento
existente se debe seguir usando su CLI en `frozen/scripts/feature_shadow.py`.
No se modificaron sus pesos, selección, fechas ni criterios estadísticos.

## Evaluación pendiente

**NOT_VERIFIABLE todavía:** la ventana independiente termina el
**2027-09-16 00:00 UTC**. No se calcularon métricas intermedias ni se reutilizó el
descubrimiento como confirmación. Al cierre serán necesarios resultados finales
con el mismo proveedor e IDs y un inicio coincidente con la captura.

Los hashes no son firmas externas. Las fechas históricas no prueban cuándo se
ingresó originalmente cada dato; pueden faltar capturas durante interrupciones.
No hay una conclusión de mayor precisión, rentabilidad ni ventaja frente al
mercado. Los gates de producción mantienen su comportamiento vigente.
