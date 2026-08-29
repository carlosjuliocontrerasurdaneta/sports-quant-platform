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

import inspect

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


def test_el_run_diario_aplica_el_techo():
    fuente = inspect.getsource(__import__("sqp.pipeline.daily", fromlist=["daily"]))
    assert "_cache_ttl_acotado(getattr(client, \"cache_ttl\", None)" in fuente
    assert "client.cache_ttl = acotado" in fuente


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


def test_la_captura_de_cierre_sigue_forzando_refresco():
    """El cierre no puede salir de cache bajo ningun TTL: mediria el CLV contra
    un precio viejo."""
    from sqp.pipeline import closing_capture
    assert "force_refresh=True" in inspect.getsource(closing_capture)
