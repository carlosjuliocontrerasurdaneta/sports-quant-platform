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
| Soccer | 12 ligas preconfiguradas (EPL, La Liga, Bundesliga, Serie A, Ligue 1, UCL, Liga MX, MLS, Brasileirão, Chile, Frauen-Bundesliga, UWCL) + extensible por YAML | Poisson por equipo, 3 vías (1X2) |
| Tennis | ATP/WTA cuadros principales (fase 3) | Elo jugador-vs-jugador; solo ganador del partido por ahora |

- **Agregar una liga de fútbol** = una entrada en `configs/leagues/soccer.yaml`.
- **Agregar un deporte** = implementar un `SportAdapter` (el núcleo no cambia).
- **Cuotas**: The Odds API (plan de pago) como proveedor principal. Claves solo por `.env`.

## Arquitectura

```
src/sqp/
├── config.py            # entorno + YAML, sin secretos hardcodeados
├── domain/              # Event, MarketLine, EstimatedProbabilities, BetCandidate
├── providers/           # odds_api (The Odds API), mlb_statsapi (API pública MLB),
│                        #   base (interfaces; vendors no configurados fallan explícito),
│                        #   synthetic (modo demo, etiquetado demo_synthetic)
├── markets/             # conversión de cuotas, remoción de vig (proporcional y power)
├── models/              # Elo genérico + distribuciones (Normal, Poisson, Skellam)
├── simulation/          # Monte Carlo (cross-check de las fórmulas analíticas)
├── calibration/         # Brier, log-loss, ECE, reliability tables (POR LIGA)
├── risk/                # Kelly fraccional (25% por defecto), caps, edge mínimo
├── backtesting/         # walk-forward temporal (nunca splits aleatorios)
├── settlement/          # liquidación vía /scores, ROI realizado, trail append-only
├── audit/               # reportes de calibración timestamped reproducibles
├── sports/              # adaptadores por familia + registro de ligas/parámetros
└── pipeline/daily.py    # cuotas → modelo → de-vig → edge → Kelly → reporte
```

Distinción estricta en todas las salidas: probabilidad estimada ≠ probabilidad
implícita del mercado (sin vig) ≠ edge estimado ≠ ROI esperado ≠ ROI realizado.

## Instalación

```bash
pip install -e ".[dev]"
cp .env.example .env       # poner ODDS_API_KEY para modo live
pytest -q                  # 15 tests
```

## Ejecución

```bash
# Demo completo sin credenciales (datos sintéticos etiquetados):
python scripts/run_daily.py --sports mlb nba nfl nhl epl --mode demo

# Live (requiere ODDS_API_KEY):
python scripts/run_daily.py --sports nba wnba ligamx --mode live
python scripts/run_backtest.py --league nba --results-csv data/raw/nba_results.csv --mode live
python scripts/settle_bets.py --league nba
python scripts/list_sports.py   # verifica cobertura activa (incl. torneos de tenis)
```

Salidas: `data/predictions/predictions_<liga>.csv` y `candidates_<liga>.csv`
(solo candidatos con edge ≥ mínimo y stake por Kelly fraccional con tope).

## Skills especializadas

`skills/` contiene una skill por familia (quant-baseball-mlb, quant-basketball,
quant-american-football, quant-hockey-nhl, quant-soccer, quant-tennis) con las
métricas, ajustes y riesgos específicos que guían la evolución de cada adaptador.

## Limitaciones (honestas)

1. **Los ratings live se construyen desde `/scores` de The Odds API (ventana de ~3 días).**
   Para estimaciones confiables se debe backfillear una temporada completa de resultados
   por liga (`--results-csv` o un ResultsProvider configurado). Sin historial suficiente,
   el sistema emite warnings y suprime candidatos.
2. El modelo base es Elo + distribución por familia. Las features avanzadas por deporte
   (pitchers, goalies, EPA/play, xG, pace, lesiones) están especificadas en las skills y
   se integran como ajustes a μ/λ, pero requieren vendors de stats que no se asumen.
3. σ y parámetros por liga son valores publicados estándar: **deben re-estimarse con tus
   datos en la calibración por liga** antes de operar.
4. Tenis: The Odds API no entrega scores de tenis → settlement requiere fuente secundaria.
5. El backtest demo usa datos sintéticos y solo valida la mecánica, jamás rentabilidad.
6. NFL: las distribuciones normales ignoran key numbers (3, 7); tratar spreads cerca de
   key numbers con cautela hasta implementar el modelo discreto de márgenes.
