# Precedencia de configuración (SQP)

Mapa autoritativo de **qué fuente gana** cuando un parámetro está definido en
varios sitios. Hay **dos cadenas independientes** que no se mezclan:

- **Cadena A — `Settings` globales** (riesgo, calibración, bankroll, odds, modo).
- **Cadena B — parámetros por liga del adaptador** (ratings/λ: Elo, scoring,
  `pitcher_*`, `park_bound`, `tilt_scale`, Dixon-Coles, etc.).

> Regla práctica: **las variables de entorno y `default.yaml` SOLO afectan la
> Cadena A.** Los parámetros de modelado por liga (Cadena B) **nunca** se leen
> de entorno ni de `default.yaml`: salen de `ratings.yaml` / `soccer.yaml` y de
> los defaults de código. No existe ninguna env var que active/desactive un
> feature de modelado por liga.

---

## Cadena A — `Settings` globales

Ensamblada en `src/sqp/config.py` (`Settings.load()`). Precedencia **por
parámetro**, de mayor a menor prioridad:

1. **Variable de entorno** (p.ej. `MARKET_SHRINK`, `MIN_EDGE`, `KELLY_FRACTION`,
   `CALIBRATION_ENABLED`, `MAX_TOTAL_EXPOSURE_PCT`, `BANKROLL`, `SQP_MODE`, ...).
2. **`configs/default.yaml`** (bloques `risk:`, `calibration:`, `bankroll:`).
3. **Default hardcodeado** en el dataclass (`os.getenv("X", yaml.get("x", default))`).

Patrón en código (`config.py`):

```python
min_edge = float(os.getenv("MIN_EDGE", r.get("min_edge", 0.02)))
# env  ──────────────^       yaml ─────^              default ─^
```

`.env` solo aporta credenciales/overrides de entorno (cargado por `Settings`);
**nunca** secretos hardcodeados.

---

## Cadena B — parámetros por liga del adaptador

Ensamblada en `src/sqp/sports/registry.py` (`get_adapter`). Cada capa **pisa** a
la anterior (la última gana); más una capa final de defaults dentro del
`__init__` del adaptador para claves ausentes en TODAS las capas:

| Prioridad | Fuente | Dónde |
|---|---|---|
| 1 (gana) | **`ratings.yaml` / `soccer.yaml`** (`league_params`) | `configs/leagues/` — tuneado walk-forward, aceptado solo si gana OOS |
| 2 | **`LEAGUE_OVERRIDES[league]`** | `registry.py` (hardcodeado; hoy solo variantes de basket/football) |
| 3 | **`FAMILY_PARAMS[family]`** | `registry.py` (defaults de familia: Elo/scoring) |
| 4 (último recurso) | **default de código** | `params.get("clave", default)` en `__init__` del adaptador |

```python
# registry.py
params = dict(FAMILY_PARAMS[family])        # capa 3
params.update(LEAGUE_OVERRIDES.get(league, {}))  # capa 2
params.update(league_params or {})          # capa 1 (ratings.yaml) -> gana
```

`league_params` llega vía `_league_meta(league)` (lee `ratings.yaml`; para
fútbol, `soccer.yaml`).

---

## Ejemplo trabajado: MLB `pitcher_bound` y `pitcher_signal`

| Parámetro | Capa que lo fija | Valor efectivo |
|---|---|---|
| `pitcher_bound` | `ratings.yaml` (`mlb:`) | **0.0** → ajuste por abridor **desactivado** (`factor()` ≡ 1.0) |
| `park_bound` | `ratings.yaml` (`mlb:`) | **0.10** → único ajuste de λ activo (OOS-validado) |
| `tilt_scale` | `ratings.yaml` pisa familia (0.8 → **0.4**) | 0.4 |
| `pitcher_prior_starts` | `ratings.yaml` | 5.0 |
| `pitcher_signal` | ninguna capa lo fija → **default de código** | `"ra"` (inerte mientras `pitcher_bound=0.0`) |
| `pitcher_min_starts` | ninguna capa → default de código | 3 |

**Implicación:** `pitcher_bound` se mantiene en 0.0 a propósito (la señal de
pitcher RA/FIP fue refutada OOS). **Nada lo reactiva sin editar el bloque `mlb:`
de `configs/leagues/ratings.yaml`** — ni `default.yaml`, ni `FAMILY_PARAMS`, ni
`LEAGUE_OVERRIDES`, ni una variable de entorno. Para cambiar el comportamiento
del pitcher hay un único punto de entrada: ese bloque YAML.
