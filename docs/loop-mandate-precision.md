# Loop autónomo — mejora de precisión del modelo

Mandato durable para el loop autopaceado. **Lee este archivo completo al inicio de cada
iteración** y respétalo al pie de la letra. El objetivo es mejorar incrementalmente la
precisión del modelo en un repo de **producción**, de forma segura y verificable.

## Barreras duras (NUNCA las cruces)

1. **Solo ramas.** Trabaja siempre en una rama `loop/<tema>` creada con `git checkout -b`.
   NUNCA commitees en `main`. Verifica `git branch --show-current` antes de commitear.
2. **Nunca `push`.** Está denegado por permisos. No publiques nada.
3. **Nunca mergees a `main` por tu cuenta.** Cuando una rama esté completa y verde, **detente**
   y deja el resumen para revisión humana. El merge es decisión de Carlos.
4. **Nunca promuevas calibradores a live.** `promote_calibrators` / `promote_calibration.py`
   con `--yes` o `--keys` es un paso HUMANO. Solo puedes correr el script SIN flags
   (su default es dry-run: muestra diff + preview y no promueve nada) para diagnóstico.
   El registro live debe seguir `{}` salvo que un humano promueva.
5. **Nunca toques `data/`, `logs/`, `exports/`, `historical/`** (denegado). No abras CSV/Parquet
   completos; usa encabezados, `nrows`, esquemas, o las funciones del pipeline por stdout.
6. **No re-persigas hipótesis refutadas** (ver memoria): MLB pitcher RA+FIP (refutado OOS),
   subir shrink global con n chico. **No toques `shrink`/`adjusted_edge`** — es damage-control
   load-bearing, no un defecto ([[oos-generalization-findings]], [[shrink-analysis-adverse-selection]]).
7. **Lenguaje de estimación** en todo output: probabilidad estimada, nunca certezas ni ROI
   garantizado. Separa prob estimada / implícita / edge / ROI esperado / ROI realizado.
8. **TDD obligatorio.** Test que falla primero, luego implementación. Corre la suite completa
   (`PYTHONPATH=src pytest tests/ -q`) antes de cada commit; no commitees en rojo.

## Ciclo de una iteración

1. Lee este mandato y revisa el ledger de progreso: `docs/loop-progress.md` (créalo si no existe).
2. Elige **UNA** tarea pequeña del backlog (abajo) que NO esté bloqueada por acumulación de datos.
   Una tarea = una unidad con su propio ciclo de test, del tamaño de un commit.
3. Si no estás en una rama `loop/*`, crea una con `git checkout -b loop/<tema>`.
4. TDD: test rojo → implementación mínima → verde → suite completa verde → commit.
5. Registra una línea en `docs/loop-progress.md`: `<fecha> <tema>: <qué se hizo> (commit <sha7>)`.
6. Si la rama del tema quedó **completa**: escribe un resumen para revisión y **detente**
   (no mergees). Si quedan pasos, continúa en la siguiente iteración.
7. Si te bloqueas, no adivines: registra el bloqueo en el ledger y detente.

## Backlog inicial (ordenado por seguridad/valor; ninguno toca producción en vivo)

- **[investigación] Calibrar p_model puro vs p_used blended.** `estimated_probability` ya es 50%
  mercado (`market_shrink=0.5`); calibrar la mezcla confunde miscalibración del modelo con blending.
  Investiga y documenta (con datos, sin cambiar serving) si conviene calibrar `p_model` puro,
  consistente en train y serve. Solo análisis + doc; cambios de serving requieren aprobación humana.
- **[test/robustez] Cobertura de `sqp/calibration/data.py`** para casos límite no cubiertos:
  ambas fechas presentes pero `game_date` inválida (no ISO), mercado con exactamente `min_n`,
  proyección con columnas extra. TDD, sin cambiar comportamiento salvo bugs reales.
- **[deuda menor, ver ledger SDD]** `train_calibration.py`: avisar cuando `--rebuild` se ignora
  bajo `--source settled`. Pequeño, TDD.
- **[auditoría, solo lectura]** Recalcular calibración/Brier por liga×mercado desde settled a
  medida que crecen los datos; documentar qué mercados se acercan a pasar el gate (sin promover).
- **[feature engineering, con leakage-check]** SOLO si hay una mejora concreta y testeable con
  corrección temporal estricta; empezar por auditar features existentes antes de añadir.

## Cuándo NO hacer nada y detenerte

- Si todo el backlog accionable está agotado o bloqueado por datos: registra "sin trabajo
  accionable" en el ledger y detente hasta la próxima ventana (probablemente tras el run diario).
- Si una tarea requiere decisión de arquitectura con varias opciones válidas: para y deja la
  pregunta para el humano.

> Recordatorio honesto: corregir calibración/precisión reduce el sangrado esperado por
> sobreconfianza; **no** garantiza ROI positivo. La mejora solo es verificable hacia adelante.
