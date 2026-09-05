"""Gate de PREDICCION por (liga, mercado): la regla de salida vigente.

Sustituye al gate de CLV como criterio rector (decision 2026-08-16). El CLV mide
rendimiento contra un mercado, no la veracidad de la prediccion, y su gate
llevaba vacio desde julio: una puerta que nadie puede cruzar equivale a no tener
puerta.

Un (liga, mercado) lleva stake real solo si cumple LAS DOS condiciones:

1. Su modelo PURO bate al mercado evento a evento -- test de signo pareado sobre
   ``d = (p_mercado - y)^2 - (p_modelo - y)^2``, unilateral, empates excluidos,
   n >= min_n y p < alpha. Se usa ``model_probability`` y no la mezcla ni la
   calibrada porque ambas contienen el precio dentro: compararlas con el mercado
   no diria si el modelo aporta algo propio.
   ``n`` cuenta OBSERVACIONES INDEPENDIENTES, una por (evento, mercado, linea),
   no filas del stream: ver ``_independent_units``.
2. Su EV a stake plano es positivo. Acertar mas que el precio no basta si el
   margen no cubre el vig (leccion de pick_mode accuracy, favoritos a 1.07).

FUERA DE MUESTRA: solo cuentan las filas posteriores a ``VALIDATION_START``, la
fecha del pre-registro. Lo anterior ya fue observado por el analisis que
descubrio los candidatos, y usarlo seria validar sobre la muestra del hallazgo
(KI-019). El dia de entrada en vigor el gate niega todos los mercados; es el
comportamiento correcto.

HISTERESIS DEL PRE-REGISTRO (pestillo de una sola direccion): "un corte que
pase el gate y luego lo pierda NO VUELVE A ENTRAR sin revision humana". No es
la histeresis de dos umbrales de ``degradation.py``: es un pestillo. Cuando un
corte con ``allowed: true`` en el registro previo deja de cumplir los criterios
(o desaparece de la evaluacion), ``latched`` pasa a true y el corte queda con
``allowed: false`` aunque los criterios estadisticos vuelvan a cumplirse. Solo
``release_prediction_gate_latch`` -- un acto humano explicito, con identidad y
rastro en ``prediction_gate_latch_log.csv`` -- desarma el pestillo; la
reentrada la decide despues el criterio pre-registrado, nunca la liberacion en
si. El estado vive en el propio ``prediction_gate.json``: ``write_prediction_gate``
lee el registro previo del mismo directorio antes de reescribirlo. Un registro
de la version anterior (sin ``latched``) se trata como "sin pestillo", lo cual
no abre nada: ``allowed`` sigue exigiendo los criterios.

MULTIPLICIDAD Y MIRADAS REPETIDAS (corregido el 2026-09-04; pre-registro
docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md, aprobado por el
operador). El pre-registro del 2026-08-16 asumia ~25 cortes y un solo analisis.
Ninguna de las dos cosas era cierta: se evaluan 41 cortes y la evaluacion se
repite a DIARIO. Con K=41 a alpha 0,05, si los 41 fueran nulos, la probabilidad
de al menos un falso positivo en UNA evaluacion es del 87,8%; y a alpha fijo con
miradas repetidas el error de tipo I crece sin cota. Ademas el pestillo no
protegia del falso positivo -- `allowed` se concede el dia que cruza y el
pestillo se arma al dia SIGUIENTE --, asi que el corte podia llevar stake real
un dia entero.

Dos reglas, ambas fijadas por test:

1. **Bonferroni**: `alpha_corte = 0,05 / 41 = 0,00122`. Precio, dicho sin
   adornos: a n=300 el liston sube del 55,0% al 59,0% de aciertos pareados.
2. **Un solo test de ENTRADA por corte**, en la primera evaluacion con
   `n >= min_n`. Elimina la parada opcional. La SALIDA sigue siendo diaria: una
   oportunidad de entrar, vigilancia continua para salir. Un corte que gasta su
   test sin pasar queda fuera hasta liberacion humana, que devuelve el test y
   deja decidir otra vez al criterio pre-registrado.

Se fijo mientras los 41 cortes estaban en `muestra_insuficiente`: nadie era
elegible, asi que el criterio se eligio sin saber quien cruzaria primero. Los
registros anteriores no traen `entry_test_at`; se leen como "test no consumido",
que es lo correcto -- ninguno lo habia gastado.

Politica default-deny: sin registro, sin entrada o con evidencia insuficiente,
stake 0 (flag "prediction_gate"). Criterio completo y criterios de descarte en
docs/research/2026-08-16-preregistro-regla-de-salida.md.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

from sqp.logging_config import get_logger
from sqp.sports.team_names import normalize_key

log = get_logger(__name__)

PREDICTION_GATE_FILENAME = "prediction_gate.json"
# Rastro append-only de cada pestillo armado y de cada liberacion humana,
# al estilo de data/models/promotion_log.csv y degradation_log.csv.
PREDICTION_GATE_LATCH_LOG = "prediction_gate_latch_log.csv"
# Fecha del pre-registro. Solo cuenta lo ESTRICTAMENTE posterior.
VALIDATION_START = "2026-08-16"
# Minimo de filas no empatadas por (liga, mercado). Por debajo, el signo es
# ruido: deny.
PREDICTION_GATE_MIN_N = 300

# Alpha de FAMILIA y reparto Bonferroni (pre-registro 2026-09-04, aprobado por el
# operador). El pre-registro del 2026-08-16 asumio ~25 cortes y acepto el riesgo
# de multiplicidad; son 41, y con K=41 a alpha 0,05 la probabilidad de al menos
# un falso positivo en UNA evaluacion -- si los 41 fueran nulos -- es del 87,8%.
# Una puerta que el ruido abre con esa probabilidad no es una puerta.
PREDICTION_GATE_FAMILY_ALPHA = 0.05
# K se FIJO el 2026-09-04, con los 41 cortes en `muestra_insuficiente`: contar
# cuantos cortes existen es un hecho de diseno del pipeline, no un resultado --
# no dice quien gana ni con que p-valor --, asi que fijarlo entonces no favorecio
# a ninguno. No se re-divide sobre la marcha: eso volveria el umbral dependiente
# del calendario de temporadas.
PREDICTION_GATE_K = 41
PREDICTION_GATE_ALPHA = PREDICTION_GATE_FAMILY_ALPHA / PREDICTION_GATE_K
# Si el universo crece por encima de esto (+22% sobre K), el criterio se
# RE-PRE-REGISTRA antes de que ningun corte nuevo sea elegible. No se corrige
# solo: se avisa, que es lo que este repositorio sabe hacer con los candados.
PREDICTION_GATE_K_REPREGISTRO = 50

_REQUIRED = ("model_probability", "implied_probability_novig", "price_decimal")
_TABLE_COLS = ["league", "market", "n", "wins", "p_value", "ev_flat",
               "allowed", "reason"]


def _usable(graded: pd.DataFrame, validation_start: str) -> pd.DataFrame:
    """Filas resueltas win/loss, posteriores al pre-registro y con las tres
    columnas numericas presentes."""
    if graded.empty or "result" not in graded.columns:
        return pd.DataFrame(columns=list(graded.columns) + ["y"])
    df = graded[graded["result"].isin(["win", "loss"])].copy()
    if df.empty:
        return df.assign(y=pd.Series(dtype=int))
    for col in ("game_date", "event_id"):
        if col not in df.columns:
            # `event_id` es tan obligatorio como `game_date`: sin identidad de
            # evento no se puede colapsar a observaciones independientes
            # (`_independent_units`) y el test de signo dejaria de ser valido.
            # Default-deny antes que un p-valor que no significa nada.
            log.warning("prediction_gate: columna '%s' ausente — todas las "
                        "filas filtradas (default-deny).", col)
            return df.iloc[0:0].assign(y=pd.Series(dtype=int))
    fecha = df["game_date"].astype(str)
    df = df[fecha > validation_start]
    for col in _REQUIRED:
        if col not in df.columns:
            return df.iloc[0:0].assign(y=pd.Series(dtype=int))
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=list(_REQUIRED))
    df["y"] = (df["result"] == "win").astype(int)
    return df


def _home_oriented_line(g: pd.DataFrame) -> pd.Series:
    """Linea de `spreads` reorientada al LOCAL, para que las dos caras del mismo
    handicap caigan en el mismo grupo.

    `pipeline/probabilities.py` emite `(spreads, home, +L)` y
    `(spreads, away, -L)`: la linea es RELATIVA AL LADO, no un identificador de
    mercado. Agrupar por la cruda separaba dos filas que son el mismo ensayo.

    NO se usa `abs(line)`: `home -1.5` y `home +1.5` son mercados DISTINTOS
    (la linea cruza el pick'em entre dias) y hay 20 pares evento/seleccion asi en
    los datos del 2026-09-01; `abs` los habria fusionado. Se niega el signo solo
    en la cara visitante, que es exactamente la inversa del productor.

    `h2h` (linea nula en ambas caras) y `totals` (Over/Under comparten el mismo
    total) ya colapsaban solos y no se tocan. Si faltan las columnas de identidad
    no se puede reorientar: se devuelve la linea cruda, que es el comportamiento
    previo.
    """
    line = pd.to_numeric(g["line"], errors="coerce")
    if not {"market", "selection", "away"}.issubset(g.columns):
        return line
    sel = g["selection"].astype(str).map(normalize_key)
    is_away = sel == g["away"].astype(str).map(normalize_key)
    is_spread = g["market"].astype(str) == "spreads"
    return line.where(~(is_spread & is_away), -line)


def _independent_units(g: pd.DataFrame) -> pd.DataFrame:
    """Una observacion por (evento, mercado, linea): `d` y `ev` promediados.

    El test de signo asume ENSAYOS INDEPENDIENTES, y las filas del stream servido
    no lo son, por dos vias que se multiplican:

    - **Repeticion diaria.** `append_served` deduplica solo dentro del mismo dia
      de run, asi que un pick dentro del horizonte de 7 dias se sirve una vez por
      dia. Medido el 2026-08-27: 13.999 filas graduadas para 6.379 picks (2,19x),
      y en la ventana del gate `mls|h2h` tenia **348 filas de 21 eventos** (16,6
      por evento) con el umbral en 300.
    - **Las dos caras del mismo mercado.** Si las probabilidades del lado
      contrario son complementarias (`p' = 1-p`, `y' = 1-y`), entonces
      `(p'-y')^2 = (p-y)^2` y `d` es EXACTAMENTE el mismo: el lado B duplica n
      sin aportar ni un bit. En `spreads` esto exige reorientar la linea al local
      antes de agrupar (`_home_oriented_line`), porque ahi la linea es relativa
      al lado: agrupando por la cruda, las dos caras caian en grupos distintos y
      `spreads` seguia contando el doble. Medido el 2026-09-01: `n` declarado 743
      frente a 392 unidades reales, con `mlb|spreads` en 266 sobre 136 eventos.

    Contar esas filas como ensayos independientes infla `n` y hunde el p-valor
    del binomial. El 2026-08-27 `mls|h2h` estaba en `p = 0,0600` con alpha 0,05 y
    `brasileirao|h2h` en `p = 0,000039` sobre **8 eventos**: el gate estaba a un
    paso de autorizar dinero real sobre un test invalido.

    Colapsar nunca abre una puerta cerrada -- que es la propiedad que importa --,
    pero NO es cierto que solo pueda subir el p-valor: en muestras desfavorables
    lo baja (medido el 2026-09-01, `mlb|spreads` 0,7500 -> 0,7257 y
    `wnba|spreads` 0,9767 -> 0,9290). Lo que garantiza es reducir `n`, y con el
    umbral `min_n` de por medio eso solo puede endurecer la decision.
    """
    d = ((g["implied_probability_novig"] - g["y"]) ** 2
         - (g["model_probability"] - g["y"]) ** 2)
    ev = (g["model_probability"] * (g["price_decimal"] - 1.0)
          - (1.0 - g["model_probability"]))
    units = pd.DataFrame({"d": d, "ev": ev})
    keys = [c for c in ("event_id", "market", "line") if c in g.columns]
    oriented = _home_oriented_line(g) if "line" in g.columns else None
    for k in keys:
        units[k] = oriented if k == "line" else g[k]
    return units.groupby(keys, dropna=False, sort=False)[["d", "ev"]].mean().reset_index()


def _decide(g: pd.DataFrame, min_n: int, alpha: float) -> dict:
    """Evalua un (liga, mercado) ya filtrado. Orden de las razones: la muestra
    manda sobre el signo, y el signo sobre el EV."""
    units = _independent_units(g)
    d = units["d"]
    n = int((d != 0).sum())
    wins = int((d > 0).sum())
    ev = float(units["ev"].mean())
    p = (float(binomtest(wins, n, 0.5, alternative="greater").pvalue)
         if n > 0 else float("nan"))
    if n < min_n:
        reason = "muestra_insuficiente"
    elif not (p < alpha):
        reason = "no_bate_al_mercado"
    elif not (ev > 0):
        reason = "ev_no_positivo"
    else:
        reason = ""
    return {"n": n, "wins": wins, "p_value": p, "ev_flat": ev,
            "allowed": reason == "", "reason": reason}


def evaluate_markets(graded: pd.DataFrame, *,
                     min_n: int = PREDICTION_GATE_MIN_N,
                     alpha: float = PREDICTION_GATE_ALPHA,
                     validation_start: str = VALIDATION_START) -> pd.DataFrame:
    """Una fila por (league, market) con la decision y su evidencia."""
    df = _usable(graded, validation_start)
    if df.empty:
        return pd.DataFrame(columns=_TABLE_COLS)
    rows = []
    for (lg, mk), g in df.groupby(["league", "market"]):
        rows.append({"league": str(lg), "market": str(mk),
                     **_decide(g, min_n, alpha)})
    return pd.DataFrame(rows, columns=_TABLE_COLS)


def _apply_latch(decided: pd.DataFrame, previous: dict[str, dict],
                 now: str, *,
                 min_n: int = PREDICTION_GATE_MIN_N) -> tuple[dict[str, dict],
                                                              list[dict]]:
    """Fusiona la decision estadistica del dia con el estado previo del pestillo.

    Reglas (pre-registro 2026-08-16, criterios de descarte):

    - Pestillo armado permanece armado: solo lo desarma la liberacion humana.
    - Un corte con ``allowed: true`` previo que deja de cumplir los criterios
      arma el pestillo.
    - Un corte con ``allowed: true`` o pestillo previo que DESAPARECE de la
      evaluacion se conserva con el pestillo armado (``sin_evaluacion``): no
      poder verificar que sigue cumpliendo no es permiso.
    - Con pestillo armado, ``allowed`` es false aunque los criterios se cumplan
      (razon ``bloqueado_pendiente_revision``): el ``allowed`` persistido es la
      decision FINAL, asi que los consumidores viejos tambien la respetan.
    - Un registro previo sin campos de pestillo (version anterior) equivale a
      "sin pestillo", que no abre nada: ``allowed`` sigue exigiendo criterios.

    Devuelve el mapa de mercados y las transiciones de pestillo del dia.
    """
    markets: dict[str, dict] = {}
    transitions: list[dict] = []

    def _latch_entry(key: str, entry: dict, was_latched: bool,
                     reason: str) -> None:
        markets[key] = entry
        if entry["latched"] and not was_latched:
            lg, mk = key.split("|", 1)
            transitions.append({
                "timestamp": now, "league": lg, "market": mk,
                "action": "latch", "reason": reason, "released_by": "",
                "note": "", "n": entry["n"], "p_value": entry["p_value"],
                "ev_flat": entry["ev_flat"],
            })

    seen: set[str] = set()
    for r in decided.itertuples():
        key = f"{r.league}|{r.market}"
        seen.add(key)
        prev = previous.get(key) or {}
        was_latched = bool(prev.get("latched"))
        was_allowed = bool(prev.get("allowed"))
        stat_allowed = bool(r.allowed)
        stat_reason = str(r.reason)

        # TEST UNICO DE ENTRADA (pre-registro 2026-09-04). La entrada se decide
        # UNA vez, en la primera evaluacion en que el corte alcanza `min_n`. Ese
        # punto de analisis lo determinan los datos pero esta declarado de
        # antemano, y es lo que elimina la parada opcional: sin esto el gate
        # reevalua a diario y un corte puede tirar el dado cada dia hasta que le
        # salga. La SALIDA sigue siendo diaria: una oportunidad de entrar,
        # vigilancia continua para salir.
        entry_at = prev.get("entry_test_at")
        if int(r.n) < min_n:
            # Aun no elegible: el test NO se consume. Un corte sin muestra no ha
            # gastado su unica bala.
            nuevo_entry_at, permitido, razon = entry_at, False, stat_reason
        elif entry_at is None:
            # ESTE es el test de entrada. Se consume ahora, pase o no pase.
            nuevo_entry_at, permitido = now, stat_allowed
            razon = "" if stat_allowed else stat_reason
        elif was_allowed:
            # Ya dentro: se sigue vigilando a diario para poder echarlo.
            nuevo_entry_at, permitido = entry_at, stat_allowed
            razon = "" if stat_allowed else stat_reason
        else:
            # Gasto su test y no paso. No reentra sin liberacion humana, aunque
            # los criterios vuelvan a cumplirse: eso es justo lo que seria tirar
            # el dado otra vez.
            nuevo_entry_at, permitido, razon = entry_at, False, "agotado_test_unico"

        latched = was_latched or (was_allowed and not permitido)
        if not permitido:
            reason = razon
        elif latched:
            reason = "bloqueado_pendiente_revision"
        else:
            reason = ""
        entry = {
            "n": int(r.n), "wins": int(r.wins), "p_value": float(r.p_value),
            "ev_flat": float(r.ev_flat),
            "allowed": permitido and not latched, "reason": reason,
            "latched": latched,
            "latched_at": (prev.get("latched_at") if was_latched
                           else (now if latched else None)),
            "entry_test_at": nuevo_entry_at,
        }
        _latch_entry(key, entry, was_latched, reason or stat_reason)
    for key in sorted(set(previous) - seen):
        prev = previous.get(key) or {}
        was_latched = bool(prev.get("latched"))
        was_allowed = bool(prev.get("allowed"))
        # El test GASTADO es estado que preservar, igual que el pestillo. Sin
        # esta tercera condicion el corte se caia del registro entero y al
        # reaparecer estrenaba test: bastaba con quedarse sin partidos unos dias
        # para volver a tirar el dado, que es exactamente la puerta trasera que
        # el pre-registro del 2026-09-04 cierra.
        gasto_test = bool(prev.get("entry_test_at"))
        if not (was_latched or was_allowed or gasto_test):
            continue  # sin estado que preservar: ausente = deny, como siempre
        # Pestillo solo para quien ESTABA DENTRO (o ya lo tenia): no poder
        # verificar que sigue cumpliendo no es permiso. Quien solo gasto su test
        # y estaba fuera no necesita pestillo -- ya esta fuera --, y armarselo
        # ensuciaria el rastro con una transicion que no ocurrio.
        latched = was_latched or was_allowed
        entry = {
            "n": 0, "wins": 0, "p_value": None, "ev_flat": None,
            "allowed": False, "reason": "sin_evaluacion", "latched": latched,
            "latched_at": (prev.get("latched_at") or now) if latched else None,
            "entry_test_at": prev.get("entry_test_at"),
        }
        _latch_entry(key, entry, was_latched, "sin_evaluacion")
    return markets, transitions


def _append_latch_log(rows: list[dict], bets_dir: Path) -> Path | None:
    """Rastro auditable append-only (escritura atomica), como degradation_log."""
    if not rows:
        return None
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / PREDICTION_GATE_LATCH_LOG
    new = pd.DataFrame(rows)
    if path.exists():
        try:
            prior = pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            prior = pd.DataFrame()
        if not prior.empty:
            cols = list(prior.columns) + [c for c in new.columns
                                          if c not in prior.columns]
            new = pd.concat([prior.reindex(columns=cols),
                             new.reindex(columns=cols)], ignore_index=True)
    tmp = path.with_suffix(".csv.tmp")
    new.to_csv(tmp, index=False)
    tmp.replace(path)
    return path


def _write_payload(payload: dict, bets_dir: Path) -> Path:
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / PREDICTION_GATE_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True),
                   encoding="utf-8")
    tmp.replace(path)
    return path


def write_prediction_gate(graded: pd.DataFrame, bets_dir: Path, *,
                          min_n: int = PREDICTION_GATE_MIN_N,
                          alpha: float = PREDICTION_GATE_ALPHA,
                          validation_start: str = VALIDATION_START) -> Path:
    """Persiste el registro (reemplazo atomico). Escribe SIEMPRE, incluso sin
    mercados: un ``markets`` vacio hace explicito el default-deny.

    Lee el registro previo del MISMO ``bets_dir`` para aplicar el pestillo del
    pre-registro (ver ``_apply_latch``): la evaluacion estadistica se rehace de
    cero, pero el estado dentro/fuera NO se olvida entre dias."""
    decided = evaluate_markets(graded, min_n=min_n, alpha=alpha,
                               validation_start=validation_start)
    bets_dir = Path(bets_dir)
    previous = load_prediction_gate(bets_dir)
    now = datetime.now(timezone.utc).isoformat()
    markets, transitions = _apply_latch(decided, previous, now, min_n=min_n)
    for t in transitions:
        log.warning("prediction_gate: pestillo ARMADO para %s|%s (%s); no "
                    "reentra sin liberacion humana (release_prediction_gate_latch).",
                    t["league"], t["market"], t["reason"])
    # Candado del pre-registro 2026-09-04: K se fijo en 41 y el reparto de alpha
    # depende de el. Si el universo crece, el criterio hay que re-pre-registrarlo
    # ANTES de que un corte nuevo sea elegible. No se corrige solo -- se delata,
    # que es lo que hacen el resto de candados de este repositorio.
    if len(markets) > PREDICTION_GATE_K_REPREGISTRO:
        log.warning("prediction_gate: %d cortes evaluados, por encima del limite "
                    "%d del pre-registro (K=%d). El reparto Bonferroni de alpha "
                    "se queda corto: RE-PRE-REGISTRAR el criterio antes de que "
                    "un corte nuevo alcance n>=%d.",
                    len(markets), PREDICTION_GATE_K_REPREGISTRO,
                    PREDICTION_GATE_K, min_n)
    payload = {"generated_at": now,
               "min_n": int(min_n), "alpha": float(alpha),
               # Trazabilidad del reparto: sin esto, leyendo el registro no se
               # puede reconstruir de donde sale un alpha de 0,00122.
               "family_alpha": float(PREDICTION_GATE_FAMILY_ALPHA),
               "k_bonferroni": int(PREDICTION_GATE_K),
               "n_cortes_evaluados": len(markets),
               "validation_start": str(validation_start), "markets": markets}
    path = _write_payload(payload, bets_dir)
    _append_latch_log(transitions, bets_dir)
    return path


def release_prediction_gate_latch(bets_dir: Path, league: str, market: str, *,
                                  released_by: str, note: str = "") -> bool:
    """Desarma el pestillo de un (liga, mercado) por revision humana explicita.

    NO pone ``allowed: true``: la liberacion autoriza la RE-EVALUACION, y es la
    siguiente ejecucion del gate la que decide con el criterio pre-registrado.
    Exige identidad no vacia y deja rastro en ``prediction_gate_latch_log.csv``.
    Devuelve True si habia pestillo que liberar, False si no habia nada que
    hacer (entrada ausente o sin pestillo)."""
    if not released_by or not released_by.strip():
        raise ValueError("release_prediction_gate_latch exige una identidad "
                         "humana no vacia en released_by (rastro auditable).")
    bets_dir = Path(bets_dir)
    path = bets_dir / PREDICTION_GATE_FILENAME
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    markets = payload.get("markets")
    if not isinstance(markets, dict):
        return False
    key = f"{league}|{market}"
    entry = markets.get(key)
    # Hay DOS formas de quedar fuera sin reentrada automatica, y la liberacion
    # tiene que cubrir las dos:
    #   - pestillo armado (entro y se cayo);
    #   - test unico de entrada gastado sin pasar (pre-registro 2026-09-04).
    # La segunda NO arma pestillo -- `was_allowed` era False --, asi que exigir
    # `latched` aqui habria dejado a esos cortes fuera PARA SIEMPRE, sin ningun
    # mecanismo de revision. Es el agujero que abre la regla del test unico si se
    # implementa sin mirar a su pareja.
    if not isinstance(entry, dict):
        return False
    bloqueado_por_pestillo = bool(entry.get("latched"))
    # `and not allowed` no es un detalle: sin el, liberar un corte que esta
    # DENTRO y sano lo expulsaria y le exigiria volver a pasar su test unico.
    # Lo caza `test_release_of_an_unlatched_market_is_a_noop`, que ya existia.
    bloqueado_por_test = (bool(entry.get("entry_test_at"))
                          and not entry.get("allowed"))
    if not (bloqueado_por_pestillo or bloqueado_por_test):
        return False
    now = datetime.now(timezone.utc).isoformat()
    entry["latched"] = False
    entry["latched_at"] = None
    # Devuelve el test de entrada: la siguiente evaluacion con n >= min_n vuelve
    # a ser SU test unico. La liberacion autoriza la RE-EVALUACION, no la
    # entrada -- quien decide sigue siendo el criterio pre-registrado.
    entry["entry_test_at"] = None
    entry["allowed"] = False  # direccion segura: reabre la evaluacion, no la puerta
    entry["reason"] = "liberado_pendiente_reevaluacion"
    _write_payload(payload, bets_dir)
    _append_latch_log([{
        "timestamp": now, "league": str(league), "market": str(market),
        "action": "release", "reason": "revision_humana",
        "released_by": released_by.strip(), "note": str(note),
        "n": entry.get("n"), "p_value": entry.get("p_value"),
        "ev_flat": entry.get("ev_flat"),
    }], bets_dir)
    log.info("prediction_gate: pestillo LIBERADO para %s por %s; la reentrada "
             "la decide la proxima evaluacion.", key, released_by.strip())
    return True


def load_prediction_gate(bets_dir: Path) -> dict[str, dict]:
    """Mapa "liga|mercado" -> decision. Devuelve {} si el registro no existe o
    es ilegible; el consumidor debe tratar {} como default-deny."""
    path = Path(bets_dir) / PREDICTION_GATE_FILENAME
    if not path.exists():
        return {}
    try:
        markets = json.loads(path.read_text(encoding="utf-8")).get("markets")
    except (OSError, json.JSONDecodeError):
        return {}
    return markets if isinstance(markets, dict) else {}


def market_allowed(gate: dict[str, dict], league: str, market: str) -> bool:
    """True solo si el registro tiene la entrada, esta aprobada y NO tiene el
    pestillo armado (default-deny). El escritor ya persiste ``allowed`` final
    con el pestillo aplicado; comprobar ``latched`` aqui es cinturon y tirantes
    contra un registro editado a mano. Un registro de la version anterior no
    trae ``latched``: se trata como sin pestillo, sin abrir nada nuevo."""
    entry = gate.get(f"{league}|{market}")
    return bool(entry and entry.get("allowed") and not entry.get("latched"))
