# MLB calibration trained on settled live bets — design

Fecha: 2026-07-01
Estado: aprobado (diseño) — pendiente plan de implementación

## Problema

El calibrador de probabilidades se entrena hoy sobre `build_pick_history`, que
**reproduce el backtest de ROI realizado sobre `load_closing_odds`** — es decir,
sobre probabilidades **ancladas al cierre**. Pero el pipeline en vivo sirve
probabilidades **ancladas a la apertura**. Ese desajuste train/serve hace que la
miscalibración en vivo sea *inaprendible*: el calibrador ve datos donde MLB está
bien calibrado (cierre) y se aplica donde está sobreconfiado (apertura). Por eso
el gate de Brier no promueve nada útil y el registro live está vacío.

### Evidencia (sesión 2026-06-30 / 07-01)

Sobre los settled reales (apertura), n=194 MLB graded:

- Calibración global MLB: prob. estimada media 0.518 vs observada 0.423
  (gap −0.095), con la prob. estimada **fuera** del IC95% de Wilson
  ([0.355, 0.493]) → sobreconfianza estadísticamente significativa.
- Tabla de fiabilidad MLB: las 5 franjas caen por debajo de lo estimado y el
  hueco **crece con la confianza** (est 0.685 → obs 0.500 en la franja alta).
- Contraste: WNBA está calibrada (gap −0.060, est dentro del IC) — no se toca.
  Tenis con n=32–41 — sin base para recalibrar.
- CLV medible aún insuficiente (69% del histórico sin cierre real distinto al de
  entrada) → no se gatea por precio todavía.

## Objetivo

Hacer aprendible la sobreconfianza de MLB entrenando el calibrador sobre los
**settled reales (apertura)** en vez del backtest (cierre), reutilizando toda la
maquinaria de seguridad existente (gate ECE+Brier+monotonía, staging por defecto,
promoción explícita), y **promoviendo solo mercados MLB**.

Fuera de alcance: recalibrar otras ligas, gatear por CLV, tocar features o
modelos, bajar `min_n`, cambiar el motor de calibración.

## Enfoque elegido (A)

Cambiar la **fuente de datos** que alimenta el entrenamiento del calibrador, sin
tocar el motor ni los gates. Es el cambio mínimo que ataca la causa raíz.

Descartados: (B) reescribir el pipeline diario más allá de la fuente — innecesario;
(C) mezclar backtest + settled — sobre-ingeniería (YAGNI).

## Arquitectura y componentes

### 1. Nueva fuente de datos de entrenamiento — `src/sqp/calibration/data.py`

```
load_settled_training_history(bets_dir: Path | None = None) -> pd.DataFrame
```

Columnas de salida: `league, market, date, estimated_probability, result`
(exactamente el esquema que `train_market_calibrators` ya consume).

- Origen: `sqp.audit.report.load_all_settled(bets_dir)`.
- `date` = `game_date` cuando tiene largo >= 10; si no, `generated_at`. Misma
  lógica que `load_history` en `report.py`. **Crítico**: el split temporal de
  `train_calibration` ordena por esta fecha; debe ser la fecha real del partido,
  no el orden de fila, para no filtrar futuro.
- No filtra por resultado aquí (lo hace `train_market_calibrators`), pero
  descarta filas sin `estimated_probability`.
- `bets_dir` ausente/vacío → frame vacío con las columnas correctas (nunca error).

### 2. Redirigir el entrenamiento a la nueva fuente

- `scripts/train_calibration.py`: añadir `--source {settled,backtest}`, default
  `settled`. `backtest` conserva el comportamiento anterior (`build_pick_history`
  / `load_pick_history`) para diagnóstico.
- `scripts/run_all.py` (staging diario, ~línea 199–209): reemplazar el input de
  `train_market_calibrators` de `build_pick_history(...)` (cierre) por
  `load_settled_training_history()` (apertura). `staging=True` se mantiene.

### 3. Sin cambios

- Gate ECE+Brier+monotonía en `train_calibration` / `_persist_or_remove`.
- Staging por defecto y promoción explícita
  (`scripts/promote_calibration.py` → `promote_calibrators(keys)`).
- `build_pick_history` / `load_pick_history` siguen vivos para el dashboard y
  el análisis de patrones (`html_report`, `patterns`). Solo dejan de ser el input
  de calibración.
- `min_n=40` se mantiene (bajarlo ya se probó inútil): un mercado MLB con n<40
  queda no-op, honestamente sin calibrar.

## Flujo de datos

```
SETTLE_ALL.bat -> data/bets/settled_*.csv
  -> load_settled_training_history()
  -> train_market_calibrators(staging=True)         # gate por (liga, mercado)
  -> revisión: scripts/promote_calibration.py (dry-run)
  -> promote_calibrators(['mlb_h2h','mlb_spreads','mlb_totals'])  # solo MLB
  -> live: apply_calibration(method='auto')          # no-op para lo no promovido
```

## Manejo de errores y casos límite

- Settled vacío → frame vacío → `train_market_calibrators` devuelve `[]` (ya seguro).
- Mercado con n<40 → skip (`trained=False`), queda no-op. No se baja `min_n`.
- `estimated_probability` NaN → descartada.
- `game_date` ausente → cae a `generated_at`; si ambos faltan, `date` vacío y la
  fila queda al inicio del orden (se documenta; no debería ocurrir en settled
  válidos).
- Registro live vacío hoy: cambiar la fuente de staging **no altera nada en vivo**
  hasta una promoción explícita y revisada — de ahí el bajo riesgo.

## Testing (TDD)

Unit — `load_settled_training_history`:
- Proyección de columnas correcta.
- Fallback `game_date` -> `generated_at`.
- Descarta `estimated_probability` NaN; conserva push/void (los filtra el trainer).
- Dir vacío/ausente → frame vacío, sin error.
- Orden temporal por fecha real (guard anti-leakage del split).

Unit — el gate sigue mandando (con la fuente nueva):
- Frame sintético sobreconfiado → calibrador baja Brier OOS → persiste (kept).
- Frame bien calibrado → no mejora → se descarta (no-op).
- Escenario degenerado (step isotónico extremo) → rechazado por el gate de Brier
  (test existente sigue verde).

Smoke — CLI:
- `train_calibration.py --source settled` stagea candidatos y NO toca el registro
  live (verifica que los archivos aterrizan en `data/models/staging/`).

## Verificación y métricas

Tras stagear, imprimir por mercado MLB: `n, Brier OOS crudo vs calibrado, ECE,
best_method, persisted?`. El revisor promueve solo mercados donde el Brier OOS
mejora.

**Honestidad**: la mejora en vivo solo es verificable **hacia adelante** (sobre
settled futuros), no retroactivamente. Corregir la calibración reduce el sangrado
esperado por sobreconfianza; **no** garantiza ROI positivo (persisten varianza y
posibles efectos de selección/precio, aún no medibles por CLV). Lenguaje de
probabilidad estimada en todo output.

## Riesgos

- n=194 MLB total; por mercado algunos pueden quedar bajo 40 y no calibrarse —
  aceptado (no-op honesto).
- El split temporal deja ~20% val (~39 filas si un mercado tuviera todo el n);
  muestras chicas → el gate puede (correctamente) rechazar. Es el resultado
  deseado, no un fallo.
- Cambiar la fuente del staging diario podría, en el futuro, interactuar con otras
  ligas; mitigado porque solo promovemos MLB y el gate filtra por grupo.
