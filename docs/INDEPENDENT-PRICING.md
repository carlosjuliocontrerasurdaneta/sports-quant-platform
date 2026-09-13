# Pricing independiente: contrato v1

Módulos: `sqp.models.independent`, `sqp.markets.settlement_math` y
`sqp.markets.independent`. Entrada CLI: `scripts/price_independent.py`.
Modo opcional de análisis local, sin conexión con selección, riesgo o ledger.

## Secuencia y trazabilidad

1. Leer exclusivamente el JSON deportivo; rechazar campos ajenos al esquema.
2. Exigir `fuente.as_of <= sporting_as_of <= ahora < event.starts_at`.
3. Construir distribución y comprobar masa/probabilidades.
4. Congelar una copia inmutable y guardar `model_freeze.json`.
5. Leer el JSON de cuotas; evaluar líneas sobre esa misma distribución.
6. Guardar el informe. Las filas de mercado inválidas se identifican individualmente.

La huella incluye versión del algoritmo, timestamp, JSON deportivo canónico y
rejilla calculada cuando existe. No es una firma criptográfica ni acredita la
calidad de las fuentes. Cambiar entradas requiere un nuevo modelo y carpeta de
auditoría; `model_version` permite distinguir actualizaciones deportivas.

## JSON deportivo

Campos obligatorios: `schema_version: 1`, `event`, `sporting_as_of`, `model_version`
(entero positivo), `data_label` (`demo_synthetic` o `user_supplied`), `sources`
y `distribution`. Cada fuente requiere `source` y `as_of`.

`event` requiere `event_id`, `league`, `home`, `away`, `starts_at` y `period`
(`regulation` o `full_game`). Los timestamps usan ISO 8601 con zona horaria.
Las entradas son estimaciones externas; el módulo no atribuye calibración propia.

| Distribución | Parámetros | Alcance |
|---|---|---|
| `count` | `expected_home`, `expected_away`; opcionales `max_score=60`, `dispersion_k`, `dc_rho=0`, `max_tail_mass=1e-6` | Poisson; binomial negativa si k>0; ajuste Dixon-Coles opcional. Solo `regulation`. |
| `normal` | `expected_home`, `expected_away`, `margin_sigma`, `total_sigma` | Aproximaciones marginales de margen y total; moneyline de dos vías sin empate. |

Las tasas deben ser no negativas; los sigmas y k, positivos. Se rechazan NaN e
infinitos. `max_score` tiene límite de recursos 512. `max_tail_mass` es una
tolerancia numérica explícita: si la cola omitida la excede, se pide aumentar la
rejilla; no se normaliza silenciosamente una truncación grande. La masa registrada
es anterior al ajuste Dixon-Coles. No se estima la dependencia entre equipos en
este modo. La normal no es una distribución conjunta de marcadores y sus pushes
enteros son aproximaciones mediante corrección de continuidad.

## Mercados y líneas

| `market` | `side` | `line` |
|---|---|---|
| `moneyline_3way` | `home`, `draw`, `away` | `null`; solo modelo count |
| `moneyline_2way` | `home`, `away` | `null`; solo normal, convención sin empate |
| `spread` | `home`, `away` | Handicap de la selección: home −1 equivale a away +1 como contraparte |
| `total` | `over`, `under` | Misma línea para las dos selecciones |

Se aceptan líneas enteras, medias y cuartos, nunca redondeos silenciosos de otras
líneas. En −0.25 se reparte media unidad en −0.5 y media en 0. Los cinco estados
son mutuamente excluyentes: `full_win`, `half_win`, `push`, `half_loss`, `full_loss`.

Sea `W = P(full_win) + 0.5 P(half_win)` y
`L = P(full_loss) + 0.5 P(half_loss)`:

- `EV_por_unidad = W × (Decimal − 1) − L`.
- `fair_decimal = 1 + L/W`, cuando W>0.
- `decision_probability = W/(W+L)`, cuando hay alguna parte de stake resuelta.
- `ROI_esperado_porcentaje = 100 × EV_por_unidad`.

Sin medias liquidaciones, la probabilidad de decisión es `P_win/(P_win+P_loss)`.
En cuartos es su equivalente ponderado por stake, identificado en `edge_basis`.
No equivale a la probabilidad bruta de ganar completamente. Si todo es push, la
probabilidad condicionada y el precio justo son `null`, y EV es cero.
Si no hay masa ganadora, no existe un precio justo finito y se usa `null`.

## Cuotas posteriores al freeze

El JSON requiere `schema_version: 1` y `quotes`. Cada fila requiere `event_id`,
`period`, `market`, `side`, `line`, `price_decimal`, `bookmaker`, `timestamp` y
`source`. El evento y período deben coincidir con el modelo.

`--max-quote-age-min` debe declararse explícitamente. La política del pipeline
original está en `configs/default.yaml: revalidation.price_max_age_min` (90 en el
commit base); se admite reproducirla pasando 90. Se rechazan fechas futuras,
precios caducados, cuotas no finitas o <=1 y mercados incompatibles.

No-vig proporcional utiliza exclusivamente contrapartes de la misma casa,
mercado, línea normalizada, instante exacto y fuente. Exige dos lados o los tres
del 1X2. No mezcla proveedores para completar un mercado. Una sola cuota permite
calcular EV, pero deja `market_no_vig_probability` y `probability_edge_pp` en null.
Duplicados de una selección vuelven ambiguo el grupo y no se elige un precio
silenciosamente. `MarketDataQuality` no cambia las probabilidades deportivas.

`probability_edge_pp = 100 × (decision_probability − no_vig_probability)`.
`positive_ev_scenarios` lista índices de escenarios con EV>0, ordenados por EV,
excluyendo duplicados ambiguos. Los precios son suministrados, sin verificación
externa: el informe no los presenta como apuestas ejecutables verificadas.

## Límites frente a PROMPT 191

Se implementan aquí independencia de lectura, freeze auditable, fórmulas de
liquidación, precio justo, separación edge/EV y validación temporal de entradas.
No se implementan todas las reglas del PROMPT 191: faltan adquisición deportiva
avanzada, reconstrucción automática de datos históricos as-of, modelos de OT,
entrenamiento/calibración por deporte y acceso garantizado a fuentes de mercado.
No se proclaman Monte Carlo, CLV realizado ni ventajas predictivas no calculadas.
