# Sports Quant Platform (SQP)

Plataforma cuantitativa profesional, modular, auditable y calibrada estadísticamente
que produce **probabilidades estimadas** para tres mercados — moneyline (1X2 en fútbol),
spread/handicap y totals (over/under) — sobre un núcleo único compartido y adaptadores
por familia de deporte.

> **Este sistema produce probabilidades estimadas únicamente. No produce certezas y no
> garantiza ganancias. Los mercados de apuestas son riesgosos, el error de modelo es
> esperado, y los resultados deben auditarse antes de usarse.**




## Alcance

| Familia | Ligas | Modelo de anotación |
|---|---|---|
| Basketball | NBA, WNBA, NCAAB, WNCAAB | Margen ~ Normal(μ, σ) |
| American Football | NFL, NCAAF | Margen ~ Normal(μ, σ) |
| Baseball | MLB | Poisson por equipo (carreras) |
| Hockey | NHL | Poisson por equipo (goles), empates→OT 50/50 |
| Soccer | 12 ligas preconfiguradas (EPL, La Liga, Bundesliga, Serie A, Ligue 1, UCL, Liga MX, MLS, Brasileirão, Chile, Frauen-Bundesliga, UWCL) + extensible por YAML | Poisson por equipo, 3 vías (1X2), ajuste Dixon-Coles |
| Tennis | ATP/WTA cuadros principales | Elo jugador-vs-jugador; solo ganador del partido por ahora |

- **Agregar una liga de fútbol** = una entrada en `configs/leagues/soccer.yaml`.
- **Agregar un deporte** = implementar un `SportAdapter` (el núcleo no cambia).
- **Cuotas**: The Odds API (plan de pago) como proveedor principal. Claves solo por `.env`.







## Arquitectura

```
src/sqp/
├── config.py            # entorno + YAML, sin secretos hardcodeados
├── domain/              # Event, MarketLine, EstimatedProbabilities, BetCandidate
├── providers/           # odds_api (The Odds API), mlb_statsapi (API pública MLB),
│                        #   espn_results / espn_tennis (resultados, no oficial),
│                        #   base (interfaces; vendors no configurados fallan explícito),
│                        #   synthetic (modo demo, etiquetado demo_synthetic)
├── markets/             # conversión de cuotas, remoción de vig (proporcional y power), edge
├── models/              # Elo genérico + distribuciones (Normal, Poisson) + park/rest/FIP
├── simulation/          # Monte Carlo (cross-check de las fórmulas analíticas)
├── calibration/         # Brier, log-loss, ECE, reliability tables (POR LIGA y MERCADO)
├── risk/                # Kelly fraccional, caps, edge mínimo, ledger de banca
├── backtesting/         # walk-forward temporal (nunca splits aleatorios) + ROI engine
├── settlement/          # liquidación vía /scores, ROI realizado, trail append-only
├── audit/               # reportes calibración/ROI timestamped + dashboard HTML
├── sports/              # adaptadores por familia + registro de ligas/parámetros
├── features/, models/ml_*  # ruta ML experimental (ver "Subsistema ML")
└── pipeline/daily.py    # cuotas → modelo → de-vig → edge → Kelly → reporte
```

Distinción estricta en todas las salidas: probabilidad estimada ≠ probabilidad
implícita del mercado (sin vig) ≠ edge estimado ≠ ROI esperado ≠ ROI realizado.

**Precedencia de configuración** (qué fuente gana entre env / `default.yaml` /
YAML por liga / defaults de código): ver [`docs/CONFIG-PRECEDENCE.md`](docs/CONFIG-PRECEDENCE.md).






## Instalación

```bash
pip install -e ".[dev]"
cp .env.example .env       # poner ODDS_API_KEY para modo live
pytest -q
```




## Ejecución







### Operación diaria (producción) — Windows / Programador de tareas

El orquestador recomendado es **`DIARIO_COMPLETO.bat`**, que garantiza el orden correcto:

```
DIARIO_COMPLETO.bat
  ├─ SETTLE_ALL.bat        # 1) liquida los picks del día anterior + auditoría de ROI
  └─ RUN_DIARIO_ALL.bat    # 2) genera los picks del día (sobrescribe candidates_*)
```

> **Orden crítico:** el run diario SOBRESCRIBE `data/predictions/candidates_*.csv`; por eso
> la liquidación debe correr ANTES (si falla, `DIARIO_COMPLETO.bat` aborta el run). Como
> respaldo, el pipeline archiva en `data/predictions/archive/` antes de sobrescribir.

`RUN_DIARIO_ALL.bat` ejecuta `scripts/run_all.py --mode live`, que:
- **auto-detecta** las ligas en temporada (`/sports`) y corre tantas como permita el
  **guard de presupuesto de cuota** (raciona la cuota real del mes, orden por prioridad);
- aplica **calibración por (liga, mercado)** si está activa (`configs/default.yaml`),
  **penalización de EV** por desacuerdo modelo-mercado y **banca dinámica** (Kelly sobre
  el balance corriente del ledger);
- escribe el **reporte consolidado** (`data/predictions/report_<día>.md` + dashboard HTML).

Otros BAT: `BACKFILL_ALL.bat` (resultados históricos, semanal), `REFRESH_ML.bat`
(mantenimiento ML, semanal), `VALIDATE_OOS.bat` (validación OOS mensual de parámetros).








### Uso manual / demo (CLI)

`scripts/run_daily.py` es una herramienta **manual ligera** (lista explícita de ligas,
imprime una tabla; NO aplica guard de presupuesto, reporte consolidado, recalibración ni
banca dinámica — para producción usa `run_all.py` / los BAT):

```bash
# Demo sin credenciales (datos sintéticos etiquetados demo_synthetic):
python scripts/run_daily.py --sports mlb nba nfl nhl epl --mode demo

# Live (requiere ODDS_API_KEY):
python scripts/run_daily.py --sports nba wnba ligamx --mode live
python scripts/run_backtest.py --league nba --mode demo     # backtest de calibración
python scripts/settle_all.py --days-from 2                  # liquidación multi-liga
python scripts/list_sports.py                               # cobertura activa (incl. tenis)
```

Salidas: `data/predictions/predictions_<liga>.csv` y `candidates_<liga>.csv`.
El criterio de selección depende de `pick_mode` (ver la sección siguiente): en
`edge` (el modo activo en producción desde 2026-07-31), candidatos con edge ≥
mínimo y stake por Kelly fraccional con tope; en `accuracy`, moneyline con
probabilidad de decisión ≥ umbral y stake plano.







## Modo precisión (`pick_mode: accuracy`) — disponible, NO activo (revertido 2026-07-31)

Estuvo activo en producción del 2026-07-28 al 2026-07-31. Se revirtió a `edge`
por decisión explícita del operador (commit `f6c2130`): seleccionar por
probabilidad ≥ 0.70 elegía favoritos extremos con cuotas 1.07–1.16, cuyo punto
de equilibrio (1/1.07 = 93.5% de aciertos) supera el hit rate alcanzable — el
modo subía el acierto y perdía dinero **por construcción**, además de recortar
el sistema a 1 de sus 3 mercados. Ese mismo commit añadió al reporte por
segmento las columnas `breakeven_hit_rate` y `hit_rate_margin` para juzgar
cualquier hit rate contra lo que la cuota exige.

Cómo funciona si se reactiva (`picks.mode: accuracy` o env `PICK_MODE`), en
`configs/default.yaml`:

- `pick_mode: accuracy` selecciona por **probabilidad de decisión** (blend modelo +
  no-vig del consenso) `>= accuracy_threshold` (0.70), **solo moneyline (h2h)**.
- El stake es **plano** (`max_stake_pct`), no Kelly: sin objetivo de valor esperado
  no hay fracción óptima que dimensionar.
- No aplica `min_edge` ni la revocación por edge de la revalidación.
- `shadow_mode: true` sigue activo: **todos los picks se registran con stake 0**.

Advertencias verificadas en la auditoría 2026-07-29 (vigentes si se reactiva),
necesarias para leer las métricas sin engañarse:

1. **El umbral no se aplica hoy a una probabilidad calibrada.** No existe
   calibrador promovido para `(liga, h2h)`, así que `calibrate_probability` es un
   no-op y el umbral recae sobre el blend crudo modelo + mercado. El pipeline
   ahora emite un WARNING cuando esto ocurre. La columna conserva el nombre
   `calibrated_probability` por compatibilidad de esquema.
2. **Un hit rate alto no implica rentabilidad.** La selección favorece favoritos
   claros; con cuota 1.07 el punto de equilibrio está en 93.5%. Hit rate y ROI se
   leen por separado, nunca uno como proxy del otro.
3. **La política vigente no tiene backtest propio.** `VALIDATE_OOS.bat` y
   `scripts/backtest_roi.py` evalúan la regla por edge/Kelly, no esta. El −5.32%
   de ROI out-of-sample conocido **no** describe el modo precisión.

El KPI a vigilar es el `gap` = hit rate observado − prometido, por banda de
probabilidad, en `data/bets/segment_diagnostics_latest.csv`.





## Subsistema ML (experimental, NO en producción)

`src/sqp/features/`, `src/sqp/models/ml_train.py`, `ml_predict.py`, `blend.py` y los
scripts `build_features.py` / `train_models.py` / `compare_models.py` (orquestados por
`REFRESH_ML.bat`) entrenan un modelo ML y comparan sim-vs-ML como **evidencia para decidir
un blend futuro**. Hoy **la generación de picks usa la ruta de simulación/Elo**; el ML no
alimenta la salida. Mantener o integrar es una decisión abierta.







## Skills especializadas

`.claude/skills/` contiene una skill por familia (quant-baseball-mlb, quant-basketball,
quant-american-football, quant-hockey-nhl, quant-soccer, quant-tennis) con las métricas,
ajustes y riesgos específicos que guían la evolución de cada adaptador.







## Limitaciones (honestas)

1. **Sin odds históricas suficientes no hay ROI realizado fiable.** La captura forward
   propia + el backfill de pago generan el dataset out-of-sample; hoy el sistema está
   ≈ break-even sobre un proxy de cierre de un snapshot, cobertura limitada y sin IC.
2. El modelo base es Elo + distribución por familia. Las features avanzadas por deporte
   (pitchers, goalies, EPA/play, xG, pace, lesiones) se integran como ajustes a μ/λ pero
   requieren vendors de stats que no se asumen. El factor de **parque MLB** (totals) es la
   primera señal por deporte validada OOS; el abridor MLB fue rechazado por evidencia.
3. σ y parámetros por liga (`configs/leagues/ratings.yaml`) son tuneados walk-forward;
   re-validar OOS antes de operar (algunos en frontera de grilla).
4. Tenis: The Odds API no entrega scores → settlement vía ESPN (no oficial); solo
   auditabilidad, no habilita operar.
5. El backtest demo usa datos sintéticos y solo valida la mecánica, jamás rentabilidad.
6. NFL: las distribuciones normales ignoran key numbers (3, 7); tratar spreads cerca de
   key numbers con cautela.

































