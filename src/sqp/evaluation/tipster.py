"""Tipster: clasifica cada pick del dia en A / B / C / NO BET.

Implementa la logica de seleccion de `AGENTS Tipster.md` (encargo del operador,
2026-08-26) como codigo DETERMINISTA. Se eligio codigo y no un agente LLM por
una razon dura: un agente de Claude Code no puede dispararse desde el Task
Scheduler -- vive dentro de una sesion. Esto corre solo cada dia, es
reproducible, testeable y no cuesta nada. Lo que el documento pide y NO es
computable (lesiones, alineaciones, noticias) queda fuera y se declara como
fuera, en vez de fingirse.

Formulas, tal como las define el documento:

    prob_implicita = 1 / cuota
    cuota_justa    = 1 / prob_estimada
    EV             = prob * cuota - 1
    edge_pp        = prob - prob_mercado_sin_vig      (Paso 8)

## Por que el edge GRANDE degrada la clasificacion en este sistema

El documento asume que "edge significativo" es senal de calidad (tier A). En
ESTE sistema la evidencia dice lo contrario, y esta medida:

- La escalera de `min_edge` va al reves: subir el umbral empeora monotonamente
  hit rate (0,430 -> 0,301) y ROI (-11,0% -> -23,9%), con IC95 que excluye el
  cero en tres de cinco escalones (2026-08-25).
- Lo que el cap de plausibilidad corta rinde **-22,6%** frente al -5,6% de lo
  que deja pasar, y el barrido de techos es monotono.

Asi que un EV por encima de `max_plausible_edge` se clasifica **NO BET**, no A.
No es una desviacion del documento: es aplicar su propia jerarquia de evidencia
("datos verificables" por encima de supuestos) y su prohibicion de "ocultar
incertidumbre". Un EV de +38% sobre este feed es casi siempre error de medida.

## Orden

Por TIER y despues por EV, sin formula compuesta. El documento pide "calidad
ajustada por riesgo, no exclusivamente por EV ni unicamente por probabilidad";
una puntuacion con pesos inventados seria menos defendible que un orden por
niveles explicitos, y ademas irreproducible para quien lea la tabla.

Nada aqui asigna stake ni promete ganancia.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sqp.evaluation.labels import decision_prob, game_date_local, match_label

# Minimos por nivel. Son PROXIES de lo que el documento pide y estan calibrados
# con lo medido en este proyecto, no elegidos a ojo:
#   - casas: calidad del dato / liquidez. Con <10 el "consenso" son unas pocas
#     opiniones; los mayores margenes del 2026-08-26 vivian en lineas de 1 a 5
#     casas.
#   - edge_pp: ventaja sobre el mercado SIN vig, que es el patron de medida.
TIER_A = {"casas": 20, "edge_pp": 0.03, "prob": 0.50}
TIER_B = {"casas": 10, "edge_pp": 0.02, "prob": 0.0}


def fair_odds(prob: pd.Series | float) -> pd.Series | float:
    """Cuota justa = 1/prob (documento, seccion 3)."""
    p = pd.to_numeric(prob, errors="coerce") if isinstance(prob, pd.Series) else prob
    return 1.0 / p


def expected_value(prob, price):
    """EV = prob * cuota - 1 (documento, seccion 2). Es el retorno esperado por
    unidad apostada; coincide con `estimated_edge` del pipeline."""
    return prob * price - 1.0


def classify(ev: float, edge_pp: float, casas: float, prob: float,
             max_plausible_ev: float) -> tuple[str, str]:
    """Devuelve (tier, motivo). El motivo va SIEMPRE: una etiqueta sin razon no
    es auditable, y el documento exige poder explicar cada decision."""
    if not np.isfinite(ev) or ev <= 0:
        return "NO BET", "EV no positivo"
    if ev > max_plausible_ev:
        # Medido: lo que el cap corta rinde -22,6% frente al -5,6% de lo que
        # pasa. Un EV asi es error de estimacion, no oportunidad.
        return "NO BET", f"EV implausible (>{max_plausible_ev:.3f})"
    if not np.isfinite(casas) or casas < TIER_B["casas"]:
        return "C", f"consenso fino ({int(casas) if np.isfinite(casas) else 0} casas)"
    if not np.isfinite(edge_pp) or edge_pp < TIER_B["edge_pp"]:
        return "C", "edge sobre el mercado marginal"
    if (casas >= TIER_A["casas"] and edge_pp >= TIER_A["edge_pp"]
            and prob >= TIER_A["prob"]):
        return "A", "edge solido con consenso profundo"
    return "B", "ventaja positiva, incertidumbre moderada"


def tipster_table(df: pd.DataFrame, *, max_plausible_ev: float = 0.075,
                  prob_col: str | None = None) -> pd.DataFrame:
    """Tabla del tipster: una fila por seleccion, con tier, motivo y correlacion.

    `df` es el stream servido. `max_plausible_ev` debe venir de
    `Settings.risk.max_plausible_edge` para que la frontera del NO BET sea la
    misma que usa el motor de riesgo y no una segunda opinion divergente.

    `prob_col=None` (por defecto) usa `labels.decision_prob`: la calibrada con
    fallback por fila a la estimada, que es con la que el pipeline decidio. El
    default era `estimated_probability`, la mezcla CRUDA sin calibrar, asi que
    los tiers, el EV y la cuota justa se calculaban sobre una probabilidad
    descartada por el sistema (auditoria 2026-08-31, A-01). Se admite un nombre
    de columna explicito para diagnostico.
    """
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    p = (decision_prob(d) if prob_col is None
         else pd.to_numeric(d.get(prob_col), errors="coerce"))
    price = pd.to_numeric(d.get("price_decimal"), errors="coerce")
    novig = pd.to_numeric(d.get("implied_probability_novig"), errors="coerce")
    casas = pd.to_numeric(d.get("books_count"), errors="coerce")

    out = pd.DataFrame({
        # Hora LOCAL, calculada aqui. Antes se leia `game_date` en crudo (UTC) y
        # solo salia bien porque `tipster_report.py` la sobrescribia antes de
        # llamar: cualquier otro llamador se llevaba fechas corridas un dia en
        # silencio. La conversion ya no depende de quien llame.
        "fecha": game_date_local(d), "liga": d.get("league"),
        # En `totals` la seleccion es "Over"/"Under": sin el partido, la fila no
        # dice de que encuentro habla (operador, 2026-08-26).
        "partido": match_label(d),
        "mercado": d.get("market"), "seleccion": d.get("selection"),
        "linea": d.get("line"), "cuota": price,
        "prob_est": p, "prob_implicita": 1.0 / price.where(price > 1.0),
        "prob_mercado": novig, "cuota_justa": fair_odds(p),
        "edge_pp": p - novig, "ev": expected_value(p, price),
        "casas": casas, "event_id": d.get("event_id"),
    })
    out = out[out["prob_est"].notna() & out["cuota"].notna()
              & (out["cuota"] > 1.0)]
    if out.empty:
        return out

    tiers = [classify(r.ev, r.edge_pp, r.casas, r.prob_est, max_plausible_ev)
             for r in out.itertuples()]
    out["tier"] = [t for t, _ in tiers]
    out["motivo"] = [m for _, m in tiers]

    # Correlacion (documento, seccion "Correlacion"): varias selecciones del
    # MISMO evento no son riesgos independientes -- el resultado de un partido
    # determina a la vez h2h, spread y parcialmente el total. Se marca; la
    # decision de exposicion es del operador.
    apostables = out[out["tier"] != "NO BET"]
    por_evento = apostables.groupby("event_id").size()
    out["correlacionado"] = out["event_id"].map(por_evento).fillna(0).gt(1)

    # Orden: TIER y luego EV. Sin formula compuesta -- ver docstring del modulo.
    # El INDICE de `df` se conserva a proposito (no hay `reset_index`): es la
    # unica clave que identifica una fila sin perdida. El dashboard reasociaba
    # los tiers por (liga, mercado, seleccion, cuota) y esa tupla NO es unica --
    # "wnba | totals | Over | 1.87" describe varios partidos--, asi que unas
    # filas heredaban el tier de otras. Alinear por indice lo hace imposible.
    orden = {"A": 0, "B": 1, "C": 2, "NO BET": 3}
    out["_o"] = out["tier"].map(orden)
    return (out.sort_values(["_o", "ev"], ascending=[True, False])
            .drop(columns=["_o"]))


def tipster_summary(table: pd.DataFrame) -> dict[str, int]:
    """Conteo por tier. `NO BET` incluido a proposito: el documento dice que la
    ausencia de apuesta es una decision valida y debe verse, no esconderse."""
    if table.empty:
        return {"A": 0, "B": 0, "C": 0, "NO BET": 0}
    c = table["tier"].value_counts().to_dict()
    return {k: int(c.get(k, 0)) for k in ("A", "B", "C", "NO BET")}
