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
