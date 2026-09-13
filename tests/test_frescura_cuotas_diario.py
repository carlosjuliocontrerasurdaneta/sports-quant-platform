"""Techo de frescura de las cuotas que fundamentan un pick (auditoria
2026-08-28, AUD-MED-003).

`fetch_odds` cachea en disco. Hoy `.env` fija el TTL en 1200 s, que esta bien
-- pero `.env` NO esta versionado: si esa linea desaparece, el default del
cliente salta a 6 h en silencio y un segundo run el mismo dia (lo que se hace
tras un fallo, como el del 2026-08-27) generaria picks sobre cuotas de hasta
seis horas antes, selladas con `generated_at` de ahora.

El limite no se inventa: el proyecto ya declara que un precio mas viejo que
`revalidation_price_max_age_min` no es accionable en la re-validacion
pre-partido. Si no vale para MANTENER un pick, no puede valer para CREARLO.
"""
from __future__ import annotations


from sqp.config import Settings
from sqp.pipeline.daily import _cache_ttl_acotado
from sqp.providers.odds_api import OddsAPIClient

POLITICA_MIN = 90.0  # revalidation_price_max_age_min por defecto


def test_un_ttl_mas_laxo_que_la_politica_se_acota():
    """El caso que motiva el arreglo: sin `.env`, el default de 6 h."""
    assert _cache_ttl_acotado(21600.0, POLITICA_MIN) == 5400.0


def test_un_ttl_mas_estricto_se_respeta():
    """Es un TECHO, no un valor asignado. Fijarlo sin comparar habria relajado a
    90 min los 1200 s que hay hoy en produccion -- el error que este test
    previene."""
    assert _cache_ttl_acotado(1200.0, POLITICA_MIN) is None


def test_el_limite_exacto_no_se_toca():
    assert _cache_ttl_acotado(5400.0, POLITICA_MIN) is None


def test_un_cliente_sin_concepto_de_cache_no_revienta():
    """Un cliente inyectado en tests puede no tener `cache_ttl`; entonces no hay
    nada que acotar."""
    assert _cache_ttl_acotado(None, POLITICA_MIN) is None


class _ClienteConCache:
    """Doble con la superficie que usa run_league, y `cache_ttl` mutable."""

    last_response_cached = True
    last_response_age_s = 0.0

    def __init__(self, events, cache_ttl):
        self._events = events
        self.cache_ttl = cache_ttl

    def is_sport_active(self, sport_key):      # noqa: ARG002
        return True

    def fetch_odds(self, *a, **k):             # noqa: ARG002
        return self._events

    def fetch_scores(self, *a, **k):           # noqa: ARG002
        return []


def test_el_run_diario_aplica_el_techo(tmp_path, monkeypatch):
    """AUD-HIGH-004: se comprueba el COMPORTAMIENTO, no el texto del fuente.

    Hasta el 2026-09-10 esto era
    `assert "client.cache_ttl = acotado" in inspect.getsource(daily)`, es decir
    una busqueda de subcadena sobre el modulo entero: habria pasado igual con la
    linea dentro de un comentario, en una rama muerta o detras de una condicion
    que nunca se cumple. La frescura de cuotas es invariante declarada del
    proyecto, asi que su candado no puede ser tipografico.

    Este test falla si se comenta la linea del techo: el cliente conservaria sus
    21600 s."""
    from sqp.config import Settings
    from sqp.pipeline import daily
    from sqp.providers.synthetic import SyntheticProvider

    sp = SyntheticProvider("basketball")
    eventos = sp.fetch_odds("nba", three_way=False)
    cliente = _ClienteConCache(eventos, cache_ttl=21600.0)

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: cliente)
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    ajustes = Settings.load()
    daily.run_league("nba", ajustes, mode="live")

    tope = ajustes.revalidation_price_max_age_min * 60.0
    assert cliente.cache_ttl == tope, (
        f"el run diario no acoto el TTL de cache: sigue en {cliente.cache_ttl} s "
        f"frente a la politica de frescura de {tope} s")


def test_un_ttl_ya_estricto_no_lo_relaja_el_run_diario(tmp_path, monkeypatch):
    """Contraprueba del anterior: es un TECHO, no una asignacion.

    Sin esta mitad, un arreglo que hiciera `client.cache_ttl = tope` a secas
    pasaria el test de arriba y RELAJARIA a 90 min los 1200 s de produccion."""
    from sqp.config import Settings
    from sqp.pipeline import daily
    from sqp.providers.synthetic import SyntheticProvider

    sp = SyntheticProvider("basketball")
    cliente = _ClienteConCache(sp.fetch_odds("nba", three_way=False), cache_ttl=1200.0)

    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "OddsAPIClient", lambda *a, **k: cliente)
    monkeypatch.setattr(daily, "_fetch_recent_scores", lambda *a, **k: [])

    daily.run_league("nba", Settings.load(), mode="live")

    assert cliente.cache_ttl == 1200.0, "el techo relajo un TTL que ya era mas estricto"


def test_la_politica_real_del_proyecto_es_mas_estricta_que_el_default():
    """Premisa: si algun dia el default bajara de la politica, este techo dejaria
    de proteger nada y habria que revisarlo."""
    politica_s = Settings.load().revalidation_price_max_age_min * 60.0
    assert politica_s < 21600.0


def test_el_cliente_sin_entorno_usa_el_default_documentado():
    """Ancla el literal 21600 de los tests anteriores al codigo real."""
    import os
    previo = {k: os.environ.pop(k, None)
              for k in ("ODDS_CACHE_TTL_SECONDS", "CACHE_TTL_SECONDS")}
    try:
        assert OddsAPIClient("dummy").cache_ttl == 21600.0
    finally:
        for k, v in previo.items():
            if v is not None:
                os.environ[k] = v


def test_la_captura_de_cierre_sigue_forzando_refresco(tmp_path, monkeypatch):
    """El cierre no puede salir de cache: mediria el CLV contra un precio viejo.

    ALCANCE EXACTO, corregido el 2026-09-10 (AUD-HIGH-004): la garantia cubre la
    ruta de PRODUCCION, que es la unica que construye el cliente
    (`closing_capture.py:119-120`, `if client is None`). Un llamador que INYECTE
    su cliente decide por su cuenta, y hoy solo lo hacen los tests. El docstring
    anterior afirmaba "bajo ningun TTL" y era falso para ese caso; ademas se
    comprobaba con `"force_refresh=True" in inspect.getsource(...)`, que habria
    pasado con la cadena dentro de un comentario.

    Ahora se espia la construccion real del cliente."""
    from sqp.pipeline import closing_capture

    visto = {}

    def _espia(*a, **k):
        visto.update(k)
        raise RuntimeError("corte deliberado: solo interesa como se construyo")

    # El import de OddsAPIClient es DIFERIDO (closing_capture.py:100), asi que
    # se parchea en su modulo de origen y no en el consumidor.
    from sqp.providers import odds_api
    monkeypatch.setattr(odds_api, "OddsAPIClient", _espia)
    monkeypatch.setattr(closing_capture, "ROOT", tmp_path)
    monkeypatch.setattr(closing_capture, "leagues_with_imminent_bets",
                        lambda *a, **k: {"nba": ["ev1"]})
    monkeypatch.setattr(closing_capture, "spent_today", lambda *a, **k: 0)

    try:
        closing_capture.capture_closing(tmp_path, settings=_AjustesMinimos())
    except RuntimeError:
        pass

    assert visto.get("force_refresh") is True, (
        "la captura de cierre construyo el cliente SIN force_refresh: el CLV se "
        f"mediria contra cache (kwargs vistos: {visto})")


class _AjustesMinimos:
    odds_api_key = "dummy"
    regions = "us"
