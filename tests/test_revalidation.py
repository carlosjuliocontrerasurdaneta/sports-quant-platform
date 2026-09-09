"""Segundo pase pre-partido (sqp.pipeline.revalidation): re-valida el edge de
los picks del dia contra el consenso vigente cerca del comienzo y revoca los
que ya no se generarian (edge < min_edge al precio actual). Bajo shadow es
medicion pura: revocado vs mantenido se compara luego en CLV/ROI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from sqp.config import Settings
from sqp.pipeline.revalidation import revalidate_candidates

NOW = datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc)
START_IN_WINDOW = "2026-07-01T21:00:00Z"       # 60 min despues de NOW
FRESH_CAPTURE = "2026-07-01T19:40:00Z"         # 20 min antes de NOW
GENERATED_TODAY = "2026-07-01T15:00:00Z"


def _cand_row(**kw) -> dict:
    base = {"event_id": "e1", "market": "h2h", "selection": "A", "line": "",
            "price_decimal": 2.0, "estimated_probability": 0.55,
            "estimated_edge": 0.10, "adjusted_edge": 0.08, "stake": 5.0,
            "kelly_stake_pct": 0.005, "flags": "",
            "generated_at": GENERATED_TODAY}
    return {**base, **kw}


def _odds_row(**kw) -> dict:
    base = {"event_id": "e1", "commence_time": START_IN_WINDOW, "home": "A",
            "away": "B", "market": "h2h", "point": "", "bookmaker": "dk",
            "captured_at": FRESH_CAPTURE, "outcome": "A", "price_decimal": 1.7}
    return {**base, **kw}


def _write(root, cands, odds, preds=None):
    pred_dir = root / "data" / "predictions"
    odds_dir = root / "data" / "odds"
    pred_dir.mkdir(parents=True, exist_ok=True)
    odds_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cands).to_csv(pred_dir / "candidates_test.csv", index=False)
    preds = preds or [{"event_id": "e1", "home": "A", "away": "B",
                       "start_time": START_IN_WINDOW}]
    pd.DataFrame(preds).to_csv(pred_dir / "predictions_test.csv", index=False)
    if odds:
        pd.DataFrame(odds).to_csv(odds_dir / "odds_test_202607.csv",
                                  index=False)
    return pred_dir


def _read_cands(root) -> pd.DataFrame:
    return pd.read_csv(root / "data" / "predictions" / "candidates_test.csv")


def test_revokes_when_edge_gone_at_current_price(tmp_path):
    # p_basis = (adjusted_edge+1)/entrada = 1.08/2.0 = 0.54; consenso 1.70 ->
    # edge actual 0.54*1.7-1 = -0.082 < min_edge -> revocar.
    pred_dir = _write(tmp_path, [_cand_row()], [_odds_row()])
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    assert s["revoked"] == 1 and s["kept"] == 0
    row = _read_cands(tmp_path).iloc[0]
    assert row["reval_action"] == "revoke"
    assert "stale_edge_revoked" in str(row["flags"])
    assert float(row["stake"]) == 0.0
    assert float(row["kelly_stake_pct"]) == 0.0
    assert abs(float(row["reval_price"]) - 1.7) < 1e-9
    assert float(row["reval_edge"]) < 0.02
    # rastro auditable
    log = pd.read_csv(tmp_path / "data" / "bets" / "revalidation_log.csv")
    assert len(log) == 1 and log.iloc[0]["event_id"] == "e1"


def test_keeps_when_edge_survives(tmp_path):
    # consenso 2.05 -> edge actual 0.54*2.05-1 = 0.107 >= min_edge -> mantener.
    pred_dir = _write(tmp_path, [_cand_row()],
                      [_odds_row(price_decimal=2.05)])
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    assert s["kept"] == 1 and s["revoked"] == 0
    row = _read_cands(tmp_path).iloc[0]
    assert row["reval_action"] == "keep"
    assert float(row["stake"]) == 5.0
    assert str(row.get("flags", "")) in ("", "nan")
    assert not (tmp_path / "data" / "bets" / "revalidation_log.csv").exists()


def test_skips_out_of_window_stale_price_and_old_rows(tmp_path):
    cands = [
        _cand_row(),                                        # sin snapshot fresco
        _cand_row(event_id="e2"),                           # fuera de ventana
        _cand_row(event_id="e1", generated_at="2026-06-30T15:00:00Z"),  # ayer
    ]
    odds = [_odds_row(captured_at="2026-07-01T16:00:00Z")]  # 4h antes: viejo
    preds = [{"event_id": "e1", "home": "A", "away": "B",
              "start_time": START_IN_WINDOW},
             {"event_id": "e2", "home": "C", "away": "D",
              "start_time": "2026-07-02T05:00:00Z"}]
    pred_dir = _write(tmp_path, cands, odds, preds)
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    assert s["revoked"] == 0 and s["kept"] == 0
    assert s["skipped_no_price"] == 1                       # solo la fila en ventana
    df = _read_cands(tmp_path)
    assert "reval_action" not in df.columns or df["reval_action"].isna().all()
    assert (df["stake"] == 5.0).all()


def test_revoke_is_final_even_if_price_recovers(tmp_path):
    pred_dir = _write(tmp_path, [_cand_row()], [_odds_row()])
    revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    # snapshot posterior con precio recuperado: el revoke no se deshace
    odds2 = [_odds_row(), _odds_row(captured_at="2026-07-01T20:30:00Z",
                                    price_decimal=2.5)]
    pd.DataFrame(odds2).to_csv(
        tmp_path / "data" / "odds" / "odds_test_202607.csv", index=False)
    later = datetime(2026, 7, 1, 20, 40, tzinfo=timezone.utc)
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=later)
    assert s["revoked"] == 0 and s["kept"] == 0             # ya final, no re-evalua
    row = _read_cands(tmp_path).iloc[0]
    assert row["reval_action"] == "revoke"
    log = pd.read_csv(tmp_path / "data" / "bets" / "revalidation_log.csv")
    assert len(log) == 1                                    # sin duplicados


def test_keep_is_reevaluated_on_later_pass(tmp_path):
    pred_dir = _write(tmp_path, [_cand_row()], [_odds_row(price_decimal=2.05)])
    revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    # a T-20 el consenso cayo a 1.7: el keep anterior debe volverse revoke
    odds2 = [_odds_row(price_decimal=2.05),
             _odds_row(captured_at="2026-07-01T20:30:00Z", price_decimal=1.7)]
    pd.DataFrame(odds2).to_csv(
        tmp_path / "data" / "odds" / "odds_test_202607.csv", index=False)
    later = datetime(2026, 7, 1, 20, 40, tzinfo=timezone.utc)
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=later)
    assert s["revoked"] == 1
    assert _read_cands(tmp_path).iloc[0]["reval_action"] == "revoke"


def test_accuracy_picks_are_not_revoked_by_edge(tmp_path):
    # Un pick del modo precision (flag accuracy_mode) se selecciona por
    # probabilidad, no por edge: los favoritos suelen tener edge negativo al
    # precio vigente, asi que la revocacion por edge lo eliminaria siempre.
    # El pase de edge lo salta por completo (el guard de cambio de abridor,
    # que si invalida la probabilidad, se mantiene aparte).
    pred_dir = _write(tmp_path,
                      [_cand_row(flags="shadow_mode;accuracy_mode")],
                      [_odds_row()])   # consenso 1.70: edge actual negativo
    s = revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
    assert s["revoked"] == 0 and s["kept"] == 0 and s["evaluated"] == 0
    row = _read_cands(tmp_path).iloc[0]
    assert "stale_edge_revoked" not in str(row["flags"])
    assert float(row["stake"]) == 5.0
    assert not (tmp_path / "data" / "bets" / "revalidation_log.csv").exists()


def _preds_with_pitchers(home_p="Gerrit Cole", away_p="José Berríos"):
    return [{"event_id": "e1", "home": "A", "away": "B",
             "start_time": START_IN_WINDOW,
             "home_pitcher": home_p, "away_pitcher": away_p}]


def _probables(home_p="Gerrit Cole", away_p="José Berríos", home="A", away="B"):
    """Respuesta estilo MLB Stats API para fetch_probables(day)."""
    return [{"date": START_IN_WINDOW[:10], "commence": START_IN_WINDOW,
             "home": home, "away": away,
             "home_pitcher": home_p, "away_pitcher": away_p}]


@pytest.mark.slow
def test_run_league_persists_pick_time_pitchers():
    from sqp.config import Settings as S
    from sqp.pipeline.daily import run_league
    df = run_league("mlb", S.load(), mode="demo")
    assert "home_pitcher" in df.columns and "away_pitcher" in df.columns


def test_pitcher_change_revokes_with_reason(tmp_path):
    from sqp.pipeline.revalidation import revalidate_pitchers
    pred_dir = _write(tmp_path, [_cand_row()], [], preds=_preds_with_pitchers())
    s = revalidate_pitchers(pred_dir, tmp_path, "test",
                            fetch_probables=lambda day: _probables(
                                home_p="Random Guy"), now=NOW)
    assert s["revoked"] == 1
    row = _read_cands(tmp_path).iloc[0]
    assert row["reval_action"] == "revoke"
    assert "pitcher_changed" in str(row["flags"])
    assert float(row["stake"]) == 0.0
    log = pd.read_csv(tmp_path / "data" / "bets" / "revalidation_log.csv")
    assert log.iloc[0]["reason"] == "pitcher_changed"


def test_pitcher_accent_variants_do_not_revoke(tmp_path):
    from sqp.pipeline.revalidation import revalidate_pitchers
    pred_dir = _write(tmp_path, [_cand_row()], [], preds=_preds_with_pitchers())
    s = revalidate_pitchers(pred_dir, tmp_path, "test",
                            fetch_probables=lambda day: _probables(
                                away_p="Jose Berrios"), now=NOW)
    assert s["revoked"] == 0 and s["checked"] == 1
    row = _read_cands(tmp_path).iloc[0]
    assert "pitcher_changed" not in str(row.get("flags", ""))
    assert float(row["stake"]) == 5.0


def test_starter_pulled_revokes(tmp_path):
    from sqp.pipeline.revalidation import revalidate_pitchers
    pred_dir = _write(tmp_path, [_cand_row()], [], preds=_preds_with_pitchers())
    s = revalidate_pitchers(pred_dir, tmp_path, "test",
                            fetch_probables=lambda day: _probables(home_p=None),
                            now=NOW)
    assert s["revoked"] == 1
    row = _read_cands(tmp_path).iloc[0]
    assert "starter_pulled" in str(row["flags"])


def test_unmatched_game_and_fetch_failure_skip(tmp_path):
    from sqp.pipeline.revalidation import revalidate_pitchers
    pred_dir = _write(tmp_path, [_cand_row()], [], preds=_preds_with_pitchers())
    s = revalidate_pitchers(pred_dir, tmp_path, "test",
                            fetch_probables=lambda day: _probables(
                                home="X", away="Y"), now=NOW)
    assert s["revoked"] == 0 and s["skipped_unmatched"] == 1
    assert (_read_cands(tmp_path)["stake"] == 5.0).all()

    def boom(day):
        raise RuntimeError("statsapi down")
    s2 = revalidate_pitchers(pred_dir, tmp_path, "test",
                             fetch_probables=boom, now=NOW)
    assert s2["revoked"] == 0                       # fallo de red: sin accion
    assert (_read_cands(tmp_path)["stake"] == 5.0).all()


def test_revalidation_log_reconciles_old_schema(tmp_path):
    from sqp.pipeline.revalidation import revalidate_pitchers
    pred_dir = _write(tmp_path, [_cand_row()], [], preds=_preds_with_pitchers())
    bets = tmp_path / "data" / "bets"
    bets.mkdir(parents=True, exist_ok=True)
    # log de esquema viejo (sin columna reason)
    pd.DataFrame([{"timestamp": "t0", "league": "test", "event_id": "e0",
                   "market": "h2h", "selection": "A"}]).to_csv(
        bets / "revalidation_log.csv", index=False)
    revalidate_pitchers(pred_dir, tmp_path, "test",
                        fetch_probables=lambda day: _probables(
                            home_p="Random Guy"), now=NOW)
    log = pd.read_csv(bets / "revalidation_log.csv")
    assert len(log) == 2 and "reason" in log.columns
    assert log.iloc[0]["event_id"] == "e0"          # fila vieja preservada


def test_price_revoke_logs_reason(tmp_path):
    revalidate_candidates(_write(tmp_path, [_cand_row()], [_odds_row()]),
                          tmp_path, min_edge=0.02, now=NOW)
    log = pd.read_csv(tmp_path / "data" / "bets" / "revalidation_log.csv")
    assert log.iloc[0]["reason"] == "edge_below_min"


def test_settings_revalidation_defaults_and_validation():
    s = Settings()                          # directo: apagado (tests/demo)
    assert s.revalidation_enabled is False
    assert s.revalidation_window_min == 120
    loaded = Settings.load()                # produccion: yaml lo enciende
    assert loaded.revalidation_enabled is True
    try:
        Settings(revalidation_window_min=0).validate()
        raise AssertionError("validate() debio fallar con window_min=0")
    except ValueError:
        pass


class TestLaRedYaNoOcurreBajoElLock:
    """AUD-002, correccion de fondo (2026-09-05).

    `revalidate_pitchers` retenia el lock de `candidates_<liga>.csv` durante
    `fetch_probables` -- MLB Stats API, llamadas de hasta 60 s. Mientras el lock
    degradaba en silencio eso "solo" causaba escrituras perdidas; desde que
    agotar la espera ABORTA, habria empezado a tumbar al otro escritor.
    """

    def test_el_fetch_ocurre_con_el_lock_LIBRE(self, tmp_path, monkeypatch):
        """La propiedad, comprobada por observacion y no leyendo el fuente: se
        mira si el fichero de lock existe en el instante del fetch."""
        import pandas as pd

        from sqp.pipeline.revalidation import revalidate_pitchers

        pred = tmp_path / "predictions_mlb.csv"
        cand = tmp_path / "candidates_mlb.csv"
        lock = tmp_path / "candidates.lock"
        inicio = "2099-01-01T12:00:00+00:00"
        pd.DataFrame([{"event_id": "e1", "start_time": inicio,
                       "home": "A", "away": "B",
                       "home_pitcher": "P1", "away_pitcher": "P2"}]
                     ).to_csv(pred, index=False)
        pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "A",
                       "line": None, "price_decimal": 2.0, "stake": 10.0,
                       "generated_at": "2099-01-01T00:00:00+00:00"}]
                     ).to_csv(cand, index=False)

        lock_visto = {}

        def fetch_espia(day):
            lock_visto["existia"] = lock.exists()
            return []

        import datetime as dt
        ahora = dt.datetime(2099, 1, 1, 11, 0, tzinfo=dt.timezone.utc)
        revalidate_pitchers(tmp_path, tmp_path, "mlb", now=ahora,
                            window_min=120, fetch_probables=fetch_espia)
        assert lock_visto.get("existia") is False, (
            "el fetch de red se hizo con el lock TOMADO: vuelve a retener la "
            "seccion critica durante una llamada de hasta 60 s")

    def test_sin_eventos_en_ventana_no_se_consulta_la_red(self, tmp_path):
        """Se conserva la frugalidad del `if not targets: return` original: si
        no hay nada que vigilar, no se gasta una llamada."""
        import datetime as dt

        import pandas as pd

        from sqp.pipeline.revalidation import revalidate_pitchers

        pd.DataFrame([{"event_id": "e1", "start_time": "2099-01-01T12:00:00+00:00",
                       "home": "A", "away": "B",
                       "home_pitcher": "P1", "away_pitcher": "P2"}]
                     ).to_csv(tmp_path / "predictions_mlb.csv", index=False)
        pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "A",
                       "line": None, "price_decimal": 2.0, "stake": 10.0,
                       "generated_at": "2099-01-01T00:00:00+00:00"}]
                     ).to_csv(tmp_path / "candidates_mlb.csv", index=False)
        llamadas = []
        # `now` muy anterior: el partido queda FUERA de la ventana de 120 min.
        revalidate_pitchers(tmp_path, tmp_path, "mlb",
                            now=dt.datetime(2099, 1, 1, 0, 0, tzinfo=dt.timezone.utc),
                            window_min=120,
                            fetch_probables=lambda d: llamadas.append(d) or [])
        assert llamadas == [], "no debe consultarse la red sin eventos en ventana"


# --- Coste del pase: no leer lo que no se va a mirar ---------------------------
#
# Auditoria integral 2026-09-08 (segunda pasada). El pase cargaba el HISTORICO
# COMPLETO de cuotas de cada liga -- `data/odds/` acumulaba 810 MB el 2026-09-08,
# y `odds_mlb_202608.csv` son 107 MB y 32,5 s de `read_csv` el solo -- antes de
# comprobar si alguna fila era siquiera evaluable, y aunque solo va a mirar el
# ultimo snapshot fresco (<= price_max_age_min). Corre cada 30 min: el pase se
# comia su propio intervalo y el Programador rechazaba los arranques siguientes,
# y con ellos la captura de cierre, que es la unica fuente de evidencia del CLV.

class TestCosteDelPase:

    def test_sin_filas_evaluables_no_se_leen_cuotas(self, tmp_path, monkeypatch):
        """Ninguna fila generada hoy -> ni un byte de data/odds/."""
        from sqp.pipeline import revalidation as mod

        pred_dir = _write(tmp_path, [_cand_row(generated_at="2026-06-30T15:00:00Z")],
                          [_odds_row()])
        monkeypatch.setattr(mod, "_league_odds", lambda *a, **kw: pytest.fail(
            "se leyeron cuotas sin ninguna fila evaluable"))
        s = mod.revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW)
        assert s["evaluated"] == 0 and s["leagues"] == []

    def test_fuera_de_ventana_tampoco_se_leen_cuotas(self, tmp_path, monkeypatch):
        from sqp.pipeline import revalidation as mod

        pred_dir = _write(tmp_path, [_cand_row()], [_odds_row()],
                          preds=[{"event_id": "e1", "home": "A", "away": "B",
                                  "start_time": "2026-07-02T21:00:00Z"}])
        monkeypatch.setattr(mod, "_league_odds", lambda *a, **kw: pytest.fail(
            "se leyeron cuotas con el evento fuera de la ventana"))
        assert mod.revalidate_candidates(pred_dir, tmp_path, min_edge=0.02,
                                         now=NOW)["evaluated"] == 0

    def test_solo_se_leen_los_meses_que_pueden_tener_capturas_frescas(self, tmp_path):
        """`_fresh_snapshot` descarta todo lo anterior a price_max_age_min, asi
        que un mes ANTERIOR al de la marca no puede aportar una sola fila."""
        from sqp.pipeline.revalidation import _league_odds, _odds_files

        odds_dir = tmp_path / "data" / "odds"
        odds_dir.mkdir(parents=True)
        pd.DataFrame([_odds_row(captured_at="2026-05-10T10:00:00Z",
                                price_decimal=9.99)]).to_csv(
            odds_dir / "odds_test_202605.csv", index=False)
        pd.DataFrame([_odds_row()]).to_csv(odds_dir / "odds_test_202607.csv",
                                           index=False)
        since = datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc)
        assert [f.name for f in _odds_files(tmp_path, "test", since)] == [
            "odds_test_202607.csv"]
        assert 9.99 not in set(_league_odds(tmp_path, "test",
                                            since=since)["price_decimal"])
        assert len(_league_odds(tmp_path, "test")) == 2   # sin `since`, todo

    def test_un_nombre_que_no_es_mensual_no_se_descarta(self, tmp_path):
        """Ante un fichero inesperado, la direccion segura es leerlo."""
        from sqp.pipeline.revalidation import _odds_files

        odds_dir = tmp_path / "data" / "odds"
        odds_dir.mkdir(parents=True)
        for nombre in ("odds_test_raro.csv", "odds_test_202605.csv"):
            pd.DataFrame([_odds_row()]).to_csv(odds_dir / nombre, index=False)
        nombres = [f.name for f in _odds_files(
            tmp_path, "test", datetime(2026, 7, 1, tzinfo=timezone.utc))]
        assert nombres == ["odds_test_raro.csv"]

    def test_la_lectura_se_acota_con_la_frescura_configurada(self, tmp_path,
                                                             monkeypatch):
        """El corte que se pasa a `_league_odds` es now - price_max_age_min."""
        from sqp.pipeline import revalidation as mod

        pred_dir = _write(tmp_path, [_cand_row()], [_odds_row()])
        vistos: list = []
        real = mod._league_odds
        monkeypatch.setattr(mod, "_league_odds",
                            lambda root, lg, **kw: (vistos.append(kw.get("since")),
                                                    real(root, lg, **kw))[1])
        mod.revalidate_candidates(pred_dir, tmp_path, min_edge=0.02, now=NOW,
                                  price_max_age_min=45.0)
        assert vistos == [NOW - timedelta(minutes=45)]

    def test_sin_cuotas_frescas_las_filas_cuentan_como_sin_precio(self, tmp_path):
        """Los dos caminos hacia "no hay precio" informan igual.

        Antes, una liga SIN ningun fichero de cuotas salia por `odds.empty` y no
        sumaba nada, mientras que una liga CON ficheros viejos llegaba a
        `_fresh_snapshot` fila a fila y si sumaba. Misma situacion, dos cifras."""
        from sqp.pipeline.revalidation import revalidate_candidates as rc

        pred_dir = _write(tmp_path, [_cand_row()], [])      # sin cuotas
        s = rc(pred_dir, tmp_path, min_edge=0.02, now=NOW)
        assert s["skipped_no_price"] == 1
        assert s["evaluated"] == 0 and s["leagues"] == []
