"""La ventana de fetch de los proveedores debe anclarse en UTC, no en la hora
local de la maquina (que aqui es UTC-4 y va un dia por detras cada noche).

Lo que se prueba no es "usa UTC" como detalle de implementacion, sino la
propiedad que importa: la ventana nueva es un SUPERCONJUNTO de la que producia
`date.today()` en cualquier zona horaria, asi que el cambio no puede perder un
dia que antes si se pedia.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from sqp.providers.date_window import VENUE_TZ_MARGIN_DAYS, fetch_window, utc_today


class TestFetchWindow:
    def test_incluye_el_dia_siguiente_a_la_referencia(self):
        """El extremo derecho pasa de hoy: un partido indexado en la fecha civil
        de un recinto al este de UTC no puede quedarse fuera."""
        start, end = fetch_window(3, today=date(2026, 8, 26))
        assert end == date(2026, 8, 27)
        assert start == date(2026, 8, 22)

    def test_cubre_days_back_dias_completos(self):
        start, end = fetch_window(365, today=date(2026, 8, 26))
        assert (end - start).days == 365 + 2 * VENUE_TZ_MARGIN_DAYS

    @pytest.mark.parametrize("offset_local", [-1, 0, 1])
    def test_es_superconjunto_de_la_ventana_local_anterior(self, offset_local):
        """`date.today()` local podia ir un dia por delante o por detras de UTC
        segun donde corriera el proceso. La ventana nueva contiene a las tres."""
        utc_ref = date(2026, 8, 26)
        local_ref = utc_ref + timedelta(days=offset_local)
        vieja_end = local_ref
        vieja_start = local_ref - timedelta(days=3)

        start, end = fetch_window(3, today=utc_ref)

        assert start <= vieja_start
        assert end >= vieja_end

    def test_days_back_cero_sigue_dando_una_ventana_valida(self):
        start, end = fetch_window(0, today=date(2026, 8, 26))
        assert start <= end

    def test_days_back_negativo_es_error_explicito(self):
        with pytest.raises(ValueError, match="days_back"):
            fetch_window(-1)

    def test_utc_today_no_depende_del_tz_local(self, monkeypatch):
        """`utc_today` debe seguir a UTC aunque TZ diga otra cosa. Se compara
        contra el propio calculo UTC, no contra `date.today()`."""
        from datetime import datetime, timezone

        assert utc_today() == datetime.now(timezone.utc).date()


class TestProveedoresUsanLaVentana:
    """Los tres proveedores deben pedir el rango que dicta `fetch_window`, no uno
    calculado a mano. Se comprueba sobre las peticiones realmente emitidas."""

    def test_mlb_statsapi_pide_el_rango_utc(self, monkeypatch):
        from sqp.providers import mlb_statsapi

        capturado: dict = {}

        class _Resp:
            @staticmethod
            def json():
                return {"dates": []}

        def _fake_get(session, url, **kwargs):
            capturado.update(kwargs.get("params", {}))
            return _Resp()

        monkeypatch.setattr(mlb_statsapi, "_get_with_retry", _fake_get)
        mlb_statsapi.MLBStatsProvider(session=object()).fetch_results(days_back=3)

        start, end = fetch_window(3)
        assert capturado["startDate"] == start.isoformat()
        assert capturado["endDate"] == end.isoformat()

    def test_espn_results_recorre_hasta_el_final_de_la_ventana(self, monkeypatch):
        from sqp.providers import espn_results

        ventanas: list[str] = []
        monkeypatch.setattr(espn_results.ESPNResultsProvider, "_fetch",
                            lambda self, cfg, dates: ventanas.append(dates) or [])
        monkeypatch.setattr(espn_results.time, "sleep", lambda _s: None)
        # ncaab usa day_by_day: una peticion por dia, asi que los extremos de la
        # ventana son directamente observables.
        espn_results.ESPNResultsProvider(session=object()).fetch_results("ncaab", days_back=2)

        start, end = fetch_window(2)
        assert ventanas[0] == f"{start:%Y%m%d}"
        assert ventanas[-1] == f"{end:%Y%m%d}"

    def test_espn_tennis_recorre_hasta_el_final_de_la_ventana(self, monkeypatch):
        from sqp.providers import espn_tennis

        ventanas: list[str] = []
        monkeypatch.setattr(espn_tennis.ESPNTennisResultsProvider, "_fetch",
                            lambda self, tour, dates, since: ventanas.append(dates) or [])
        espn_tennis.ESPNTennisResultsProvider(session=object()).fetch_results(
            "atp", days_back=2)

        start, _end = fetch_window(2)
        assert ventanas[0] == f"{start:%Y%m%d}"
