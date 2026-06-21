# Calibración de probabilidades — activación y seguimiento

**Fecha de activación:** 2026-06-21
**Revisión pendiente:** **2026-06-28** (≈1 semana) — foco: **MLB h2h**
**Flag:** `configs/default.yaml → calibration.enabled: true` (método `isotonic`)
**Alcance:** calibradores isotónico/beta por **(liga, mercado)** aplicados a la probabilidad
estimada (ya encogida hacia el mercado) **antes** de edge/stake en `pipeline/daily.py`.
La `estimated_probability` que se guarda y con la que se reentrena queda **sin calibrar**
(sin bucle de realimentación). Aplicación = no-op si no hay modelo para ese (liga, mercado).

## Por qué esta nota

Se activó la calibración tras verificar que mejora el ECE fuera de muestra en 5/6 grupos
entrenados (split temporal). El comparativo calibrado vs sin calibrar sobre las **mismas**
cuotas mostró un cambio de comportamiento que conviene vigilar:

| Mercado | Efecto de la calibración | Picks accionables |
|---|---|---|
| **mlb / h2h** | sube prob. media **+0.072** → crea edge | **0 → 9** (+44.92 stake) ⚠️ |
| mlb / spreads | leve subida (+0.017) | 2 → 3 |
| mlb / totals | baja edge (pausado, sin stake) | 0 → 0 |
| wnba / h2h | corrige sobreconfianza (−0.017) | 3 → 1 |
| wnba / spreads | corrige sobreconfianza (−0.021) | 5 → 1 |
| tenis (sin modelo) | **0.0000** (no-op confirmado) | — |

WNBA enfriándose es lo esperado (ECE h2h 0.264 → 0.094). El punto de atención es
**MLB h2h pasando de 0 a 9 apuestas**: la isotónica levantó probabilidades de rango medio
y generó edge donde antes no lo había. Puede ser legítimo (modelo infraconfiado ahí) o
puede estar fabricando bets marginales.

## Acción a revisar el 2026-06-28

Comprobar el **ROI realizado** y la **calibración** de MLB h2h con la muestra liquidada de
la semana:

```
SETTLE_ALL.bat                                  # liquidar primero
PYTHONPATH=src python scripts/train_calibration.py   # ECE antes/después por (liga, mercado)
```
- Abrir `data/predictions/report_latest.html` → pestaña **Auditoría** (ROI realizado por
  mercado) y comparar `mean_est_prob` vs `hit_rate` y `mean_est_edge` vs `realized_roi`
  para `mlb / h2h`.

**Criterio de decisión:**
- Si MLB h2h muestra ROI realizado que **contradice** el edge estimado, o el ECE OOS
  **empeora** → revertir solo ese mercado: borrar
  `data/models/mlb_h2h_calibration_iso.joblib` (y `_beta.joblib`). Queda sin calibrar
  (no-op), el resto sigue calibrado.
- Si todo mejora o se mantiene → dejar como está.
- Revertir **todo**: `calibration.enabled: false` en `configs/default.yaml`.

## Notas

- El run diario reentrena los calibradores best-effort al final (con los modelos previos;
  los picks del día ya se generaron antes → sin fuga del día sobre su propio calibrador).
- **Auto-sanable (gate por ECE):** `train_calibration` persiste un calibrador **solo si no
  empeora** el ECE OOS; si empeora, lo elimina y limpia cualquier modelo previo en esa ruta.
  Así un mercado que deja de ayudar vuelve solo a no-op en cada reentrenamiento. Ejemplo
  actual: `wnba/totals` (ECE 0.2046 → 0.2714) se **auto-descarta** — no requiere borrado manual.
- Por eso el borrado manual de un `.joblib` solo aplica a un mercado que el gate **sí mantiene**
  (mejora el ECE) pero cuyo **ROI realizado** contradice el edge estimado — son señales
  distintas: el gate mira ECE (calibración), la decisión de MLB h2h mira ROI realizado.
- Grupos con <40 graduados no se entrenaron (chile, nba, nhl, …): sin modelo, no-op.

---

> Esta plataforma produce únicamente probabilidades estimadas (ahora calibradas). No genera
> certezas ni garantiza ganancias. El edge estimado no es ROI realizado; los mercados son
> riesgosos y el error de modelo es esperable. Auditar antes de usar.
