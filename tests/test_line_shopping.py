"""Line shopping: el precio de EJECUCION es el mejor entre las casas accesibles.

Medicion que lo motiva (2026-09-07, sobre 8.670 picks graduados emparejados a su
propio snapshot, validacion: la mediana reconstruida reproduce el
`price_decimal` guardado con |err|<=0,01 en el 99,6%): ejecutar al mejor precio
del tier accesible vale **+2,3 a +2,8 pp de ROI** frente a la mediana del
consenso, sin tocar el modelo. NO cambia el signo -- el IC95 del mejor tier
realista sigue siendo [-0,1358; -0,0104] --, asi que esto es reduccion de
perdida y precondicion, no una ventaja.

INVARIANTE RECTOR de todo el archivo: el **benchmark no-vig no se toca**. La
probabilidad justa se sigue calculando sobre el consenso completo. De-vigear
precios best-of-N da suma < 1 y FABRICA edge que no existe: el mejor precio
cambia lo que se COBRA, nunca lo que se estima.
"""
from __future__ import annotations

import pytest

from sqp.config import CONFIG_DIR, Settings, load_yaml
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.probabilities import (_consensus_lines, _execution_prices,
                                        _novig_probs)

CONSENSUS = "consensus_median"


def _odds(*quotes: tuple[str, str, float]) -> EventOdds:
    """quotes = (casa, desenlace, precio) en h2h sin punto."""
    ev = Event(event_id="e1", sport_key="s", league="test", home="A", away="B",
               start_time="2026-09-20T23:00:00Z", data_label="real")
    return EventOdds(event=ev, lines=[
        MarketLine(market="h2h", bookmaker=bk, outcome=out, price_decimal=px,
                   point=None)
        for bk, out, px in quotes])


def _exec(eo, books, max_uplift=0.15):
    cons = _consensus_lines(eo)
    return cons, _execution_prices(eo, cons, books, max_uplift=max_uplift)


KEY_A = ("h2h", "A", None)


# --- 1. Desactivado por defecto: comportamiento identico al historico ---------

def test_sin_allowlist_ejecuta_a_la_mediana_del_consenso():
    """Default-deny: sin casas declaradas no hay line shopping."""
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.00), ("bk3", "A", 2.10),
               ("bk1", "B", 2.00))
    cons, ex = _exec(eo, books=())
    assert ex[KEY_A] == (pytest.approx(cons[KEY_A]), CONSENSUS)
    assert cons[KEY_A] == pytest.approx(2.00)


# --- 2. Con allowlist: el mejor precio accesible ------------------------------

def test_toma_el_mejor_precio_entre_las_casas_accesibles():
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.00), ("bk3", "A", 2.06),
               ("bk1", "B", 2.00))
    _, ex = _exec(eo, books=("bk1", "bk2", "bk3"))
    assert ex[KEY_A] == (pytest.approx(2.06), "bk3")


def test_ignora_una_casa_mejor_que_no_esta_en_la_allowlist():
    """Un precio inalcanzable no es un precio: produciria stake que no se puede
    tomar."""
    eo = _odds(("accesible", "A", 1.95), ("inalcanzable", "A", 2.40),
               ("otra", "A", 1.90), ("accesible", "B", 2.00))
    _, ex = _exec(eo, books=("accesible",))
    assert ex[KEY_A] == (pytest.approx(1.95), "accesible")


def test_sin_casa_accesible_en_esa_linea_cae_a_la_mediana():
    eo = _odds(("otra1", "A", 1.90), ("otra2", "A", 2.10), ("otra1", "B", 2.00))
    cons, ex = _exec(eo, books=("accesible",))
    assert ex[KEY_A] == (pytest.approx(cons[KEY_A]), CONSENSUS)


# --- 3. Guards: una cotizacion sospechosa no se convierte en edge -------------

def test_un_uplift_implausible_cae_a_la_mediana():
    """Una cuota muy por encima del consenso es cotizacion obsoleta o error del
    origen mucho antes que valor: mismo criterio conservador que
    `max_plausible_edge` y que el guard de KI-019."""
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.00), ("rara", "A", 4.00),
               ("bk1", "B", 2.00))
    cons, ex = _exec(eo, books=("bk1", "bk2", "rara"), max_uplift=0.15)
    assert ex[KEY_A] == (pytest.approx(cons[KEY_A]), CONSENSUS)


def test_un_uplift_dentro_del_limite_si_se_toma():
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.00), ("bk3", "A", 2.20),
               ("bk1", "B", 2.00))
    _, ex = _exec(eo, books=("bk1", "bk2", "bk3"), max_uplift=0.15)
    assert ex[KEY_A] == (pytest.approx(2.20), "bk3")   # +10% sobre 2.00


def test_precio_no_usable_de_una_casa_accesible_se_ignora():
    """Mismo predicado que `_consensus_lines`: un inf de una casa permitida
    no puede ganar el max."""
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.00),
               ("bk3", "A", float("inf")), ("bk1", "B", 2.00))
    _, ex = _exec(eo, books=("bk1", "bk2", "bk3"))
    assert ex[KEY_A] == (pytest.approx(2.00), "bk2")


# --- 4. EL INVARIANTE: el no-vig no se mueve ---------------------------------

def test_el_novig_se_calcula_sobre_el_consenso_no_sobre_el_mejor_precio():
    """De-vigear best-of-N da suma < 1 y fabrica edge. El benchmark no cambia."""
    eo = _odds(("bk1", "A", 1.90), ("bk2", "A", 2.10),
               ("bk1", "B", 1.90), ("bk2", "B", 2.10))
    cons, ex = _exec(eo, books=("bk1", "bk2"))
    fair_sin = _novig_probs(cons, "h2h")
    # El line shopping mejora AMBOS lados; si contaminara el benchmark, la
    # probabilidad justa se moveria.
    assert ex[KEY_A][0] > cons[KEY_A]
    assert ex[("h2h", "B", None)][0] > cons[("h2h", "B", None)]
    assert _novig_probs(cons, "h2h") == fair_sin
    assert sum(fair_sin.values()) == pytest.approx(1.0)


# --- 5. Configuracion ---------------------------------------------------------

def test_execution_desactivado_por_defecto():
    s = Settings()
    assert s.execution.books == ()
    assert s.execution.max_uplift == pytest.approx(0.15)


def test_produccion_declara_el_bloque_execution():
    """El yaml versionado tiene que DECLARARLO, no heredarlo del dataclass.

    La primera version de este test afirmaba `Settings.load().execution
    .max_uplift > 0` y pasaba con `configs/default.yaml` SIN bloque `execution`,
    porque caia al default del dataclass (0.15): comprobaba el default, no la
    declaracion (auditoria integral 2026-09-07, AUD-LOW-004). Se verifica contra
    el fichero, y ademas que un valor NO-default lo atraviesa -- sin esa segunda
    mitad, declarar la clave con cualquier valor bastaria para aprobarlo.
    """
    cfg = load_yaml(CONFIG_DIR / "default.yaml")
    assert "execution" in cfg, (
        "configs/default.yaml no declara el bloque `execution`: la ejecucion de "
        "los picks quedaria descrita solo por el default del dataclass")
    assert cfg["execution"].get("books") in ([], None), (
        "line shopping ACTIVADO en el yaml versionado: es una decision del "
        "operador sobre donde puede transaccionar, no un default")
    assert Settings.load().execution.max_uplift == pytest.approx(
        float(cfg["execution"]["max_uplift"]))


def test_el_yaml_manda_sobre_el_default_del_dataclass(tmp_path, monkeypatch):
    """La otra mitad: que el valor del fichero LLEGUE de verdad a `Settings`."""
    import sqp.config as cfgmod
    (tmp_path / "default.yaml").write_text(
        "execution:\n  books: [pinnacle]\n  max_uplift: 0.42\n", encoding="utf-8")
    monkeypatch.setattr(cfgmod, "CONFIG_DIR", tmp_path)
    monkeypatch.delenv("EXECUTION_BOOKS", raising=False)
    monkeypatch.delenv("EXECUTION_MAX_UPLIFT", raising=False)
    s = cfgmod.Settings.load()
    assert s.execution.books == ("pinnacle",)
    assert s.execution.max_uplift == pytest.approx(0.42)


def test_env_var_declara_las_casas_accesibles(monkeypatch):
    monkeypatch.setenv("EXECUTION_BOOKS", "Pinnacle, betfair_ex_eu ,")
    assert Settings.load().execution.books == ("pinnacle", "betfair_ex_eu")


def test_validate_rechaza_un_uplift_no_positivo_o_absurdo():
    s = Settings()
    s.execution.max_uplift = 0.0
    with pytest.raises(ValueError):
        s.validate()
    s.execution.max_uplift = 1.5     # +150%: no es un precio, es un error
    with pytest.raises(ValueError):
        s.validate()
    s.execution.max_uplift = 0.15
    s.validate()


def _run_live(tmp_path, monkeypatch, books, seed_book="better_book", uplift=1.06):
    """run_league en live con un doble de cliente: eventos sinteticos NBA mas
    una casa extra que cotiza h2h un `uplift` por encima de demo_book."""
    import copy
    from sqp.config import Settings
    from sqp.pipeline import daily
    from sqp.providers.synthetic import SyntheticProvider

    eventos = SyntheticProvider("basketball").fetch_odds("nba", three_way=False)
    for eo in eventos:
        for ln in list(eo.lines):
            if ln.market == "h2h":
                mejor = copy.copy(ln)
                mejor.bookmaker, mejor.price_decimal = seed_book, round(ln.price_decimal * uplift, 3)
                eo.lines.append(mejor)

    class _Cliente:
        last_response_cached = True   # no persiste snapshot de cuotas
        last_response_age_s = 0.0
        cache_ttl = 60.0

        def is_sport_active(self, sport_key):      # noqa: ARG002
            return True

        def fetch_odds(self, *a, **k):             # noqa: ARG002
            return eventos

    # Historial sintetico: sin >=10 partidos por equipo el adaptador marca el
    # evento como poco fiable y no se sirve ninguna linea.
    equipos = sorted({t for eo in eventos for t in (eo.event.home, eo.event.away)})
    historial = []
    for i in range(12):
        for j, h in enumerate(equipos):
            a = equipos[(j + 1 + i) % len(equipos)]
            if a != h:
                historial.append({"date": f"2026-0{1 + i % 8}-{10 + j:02d}", "home": h, "away": a,
                                  "home_score": 100 + (i + j) % 7, "away_score": 98 + (i * j) % 9})

    class _Resultados:
        def __init__(self, *a, **k):
            pass

        def load(self, league):               # noqa: ARG002
            return sorted(historial, key=lambda r: r["date"])

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: _Cliente())
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])
    monkeypatch.setattr(daily, "ResultsStore", _Resultados)
    if books:
        monkeypatch.setenv("EXECUTION_BOOKS", ",".join(books))
    else:
        monkeypatch.delenv("EXECUTION_BOOKS", raising=False)
    ajustes = Settings.load()
    assert ajustes.execution.books == tuple(books)
    daily.run_league("nba", ajustes, mode="live")
    import glob
    import pandas as pd
    servidas = sorted(glob.glob(str(tmp_path / "data" / "calibration" / "served_nba*.csv")))
    assert servidas, "el run live no escribio el stream servido"
    return pd.concat([pd.read_csv(f) for f in servidas], ignore_index=True)


# --- 4. Cableado en el pipeline (2026-09-19): capa ADITIVA de ejecucion ------

def test_con_books_vacio_la_ejecucion_repite_la_mediana(tmp_path, monkeypatch):
    """Default-deny: sin casas declaradas las dos columnas nuevas repiten la
    mediana del consenso y nada mas cambia."""
    df = _run_live(tmp_path, monkeypatch, books=())
    assert {"execution_price", "execution_book"} <= set(df.columns)
    assert (df["execution_book"] == CONSENSUS).all()
    assert df["execution_price"].to_numpy() == pytest.approx(df["price_decimal"].to_numpy())


def test_con_casa_accesible_la_ejecucion_toma_su_precio_sin_tocar_la_seleccion(tmp_path, monkeypatch):
    """INVARIANTE: `price_decimal`, no-vig y edge son los de la mediana en ambos
    runs (byte-identicos); solo cambian `execution_price` y `execution_book`."""
    base = _run_live(tmp_path / "a", monkeypatch, books=())
    con = _run_live(tmp_path / "b", monkeypatch, books=("better_book",))
    clave = ["event_id", "market", "selection", "line"]
    m = base.merge(con, on=clave, suffixes=("_base", "_con"))
    assert len(m) == len(base) == len(con)
    for col in ("price_decimal", "implied_probability_novig", "estimated_edge",
                "calibrated_probability", "stake"):
        assert m[f"{col}_base"].to_numpy() == pytest.approx(m[f"{col}_con"].to_numpy(),
                                                             nan_ok=True), col
    h2h = m["market"] == "h2h"
    assert (m.loc[h2h, "execution_book_con"] == "better_book").all()
    assert (m.loc[h2h, "execution_price_con"] > m.loc[h2h, "price_decimal_con"]).all()
    # Mercados que la casa accesible no cotiza: manda la mediana.
    assert (m.loc[~h2h, "execution_book_con"] == CONSENSUS).all()


def test_execution_prices_esta_cableado_en_daily():
    """Candado inverso al que hubo hasta el 2026-09-19 (AUD-005): si alguien
    retira la llamada, las dos columnas nuevas quedarian huerfanas."""
    from sqp.pipeline import daily
    import inspect
    assert "_execution_prices(" in inspect.getsource(daily.run_league)
