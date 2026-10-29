"""`sqp.pipeline.pitcher_probables_capture.run`: captura prospectiva de abridores
probables MLB. Proveedor falso y tmp_path (sin red, sin `data/` real)."""
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from sqp.pipeline import pitcher_probables_capture as capture
from sqp.providers.date_window import utc_today

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _game(pk=1, *, hp=("10", "Home Sp"), ap=("20", "Away Sp"),
          commence=None, status="Scheduled"):
    if commence is None:
        commence = _iso(NOW + timedelta(hours=6))
    return {
        "date": "2026-10-29", "commence": commence,
        "home": "Home FC", "away": "Away FC",
        "home_pitcher": hp[1] if hp else None, "away_pitcher": ap[1] if ap else None,
        "game_pk": pk,
        "home_pitcher_id": hp[0] if hp else None,
        "away_pitcher_id": ap[0] if ap else None,
        "status": status,
    }


class FakeProvider:
    """Sustituye a MLBStatsProvider.fetch_probable_pitchers: hoy trae `games`,
    manana nada."""

    def __init__(self, games, fail_dates=()):
        self.games = games
        self.fail_dates = set(fail_dates)
        self.calls: list[str] = []

    def fetch_probable_pitchers(self, date_iso):
        self.calls.append(date_iso)
        if date_iso in self.fail_dates:
            raise requests.ConnectionError("sin red")
        return self.games if date_iso == utc_today().isoformat() else []


def _csv(tmp_path):
    return pd.read_csv(tmp_path / "data" / "historical" / "pitcher_probables_mlb.csv",
                       dtype=str, keep_default_na=False)


def _run(tmp_path, games, minutes=0, **kw):
    prov = FakeProvider(games, **kw)
    now = NOW + timedelta(minutes=minutes)
    return capture.run("capture", root=tmp_path, now=now, provider=prov)


def test_primera_captura_escribe_una_fila_por_lado(tmp_path):
    seen, appended = _run(tmp_path, [_game()])
    assert (seen, appended) == (2, 2)
    df = _csv(tmp_path)
    assert list(df.columns) == [
        "captured_at_utc", "game_pk", "game_date", "commence_time", "team_side",
        "team", "pitcher_id", "pitcher_name", "source_run"]
    assert set(df["team_side"]) == {"home", "away"}
    assert set(df["game_pk"]) == {"1"}
    assert set(df["source_run"]) == {"capture"}
    assert set(df["captured_at_utc"]) == {"2026-10-29T15:00:00+00:00"}


def test_sin_cambios_no_anade(tmp_path):
    _run(tmp_path, [_game()])
    seen, appended = _run(tmp_path, [_game()], minutes=30)
    assert (seen, appended) == (2, 0)
    assert len(_csv(tmp_path)) == 2


def test_cambio_de_abridor_anade_solo_ese_lado(tmp_path):
    _run(tmp_path, [_game()])
    _, appended = _run(tmp_path, [_game(hp=("11", "Nuevo Sp"))], minutes=30)
    assert appended == 1
    df = _csv(tmp_path)
    ult = df[(df["team_side"] == "home")].sort_values("captured_at_utc").iloc[-1]
    assert (ult["pitcher_id"], ult["pitcher_name"]) == ("11", "Nuevo Sp")
    assert len(df) == 3


def test_retirada_anade_fila_vacia_y_no_se_repite(tmp_path):
    _run(tmp_path, [_game()])
    _, appended = _run(tmp_path, [_game(ap=None)], minutes=30)
    assert appended == 1
    df = _csv(tmp_path)
    ult = df[df["team_side"] == "away"].sort_values("captured_at_utc").iloc[-1]
    assert (ult["pitcher_id"], ult["pitcher_name"]) == ("", "")
    # Sigue sin abridor: no se vuelve a registrar.
    _, again = _run(tmp_path, [_game(ap=None)], minutes=60)
    assert again == 0


def test_lado_sin_abridor_desde_el_inicio_no_se_registra(tmp_path):
    seen, appended = _run(tmp_path, [_game(ap=None)])
    assert (seen, appended) == (1, 1)
    assert set(_csv(tmp_path)["team_side"]) == {"home"}
    seen, appended = _run(tmp_path, [_game(hp=None, ap=None)], minutes=30)
    assert seen == 0  # solo la retirada del home
    assert appended == 1


def test_partido_comenzado_o_terminado_se_excluye(tmp_path):
    juegos = [
        _game(1),
        _game(2, commence=_iso(NOW - timedelta(hours=1))),            # ya paso la hora
        _game(3, status="In Progress"),
        _game(4, status="Final"),
        _game(5, status="Game Over"),
    ]
    seen, appended = _run(tmp_path, juegos)
    assert (seen, appended) == (2, 2)
    assert set(_csv(tmp_path)["game_pk"]) == {"1"}


def test_commence_no_parseable_se_excluye(tmp_path):
    juegos = [_game(1, commence="no-es-fecha"), _game(2, commence="")]
    assert _run(tmp_path, juegos) == (0, 0)
    assert not (tmp_path / "data").exists()


def test_fallo_de_red_de_una_fecha_no_impide_la_otra(tmp_path):
    hoy = utc_today()
    manana = hoy + timedelta(days=1)

    class P:
        def fetch_probable_pitchers(self, date_iso):
            if date_iso == hoy.isoformat():
                raise requests.ConnectionError("sin red")
            return [_game(7)] if date_iso == manana.isoformat() else []

    seen, appended = capture.run("capture", root=tmp_path, now=NOW, provider=P())
    assert (seen, appended) == (2, 2)
    assert set(_csv(tmp_path)["game_pk"]) == {"7"}


def test_partido_de_fecha_local_de_ayer_con_commence_futuro_se_captura(tmp_path):
    ayer = (utc_today() - timedelta(days=1)).isoformat()

    class P:
        def fetch_probable_pitchers(self, date_iso):
            return [_game(9)] if date_iso == ayer else []

    assert capture.run("capture", root=tmp_path, now=NOW, provider=P()) == (2, 2)
    assert set(_csv(tmp_path)["game_pk"]) == {"9"}


def test_mismo_game_pk_aplazado_hoy_y_programado_manana_no_duplica(tmp_path):
    hoy = utc_today().isoformat()
    manana = (utc_today() + timedelta(days=1)).isoformat()
    aplazado = _game(5, status="Postponed")
    nuevo = _game(5, hp=("11", "Otro Sp"), commence=_iso(NOW + timedelta(days=1)))

    class P:
        def fetch_probable_pitchers(self, date_iso):
            return {hoy: [aplazado], manana: [nuevo]}.get(date_iso, [])

    assert capture.run("capture", root=tmp_path, now=NOW, provider=P()) == (2, 2)
    assert capture.run("capture", root=tmp_path,
                       now=NOW + timedelta(minutes=30), provider=P()) == (2, 0)
    df = _csv(tmp_path)
    assert len(df) == 2
    assert set(df[df["team_side"] == "home"]["pitcher_id"]) == {"11"}


def test_aplazado_cancelado_suspendido_se_excluyen(tmp_path):
    juegos = [_game(1, status="Postponed"), _game(2, status="Cancelled"),
              _game(3, status="Suspended: Rain")]
    assert _run(tmp_path, juegos) == (0, 0)


def test_doubleheader_dos_game_pk_misma_fecha_y_equipos(tmp_path):
    juegos = [_game(1), _game(2, commence=_iso(NOW + timedelta(hours=9)))]
    assert _run(tmp_path, juegos) == (4, 4)
    assert set(_csv(tmp_path)["game_pk"]) == {"1", "2"}


def test_id_entero_frente_a_str_guardado_no_anade(tmp_path):
    _run(tmp_path, [_game(1, hp=("5", "Home Sp"))])
    assert _run(tmp_path, [_game(1, hp=(5, "Home Sp"))], minutes=30) == (2, 0)
