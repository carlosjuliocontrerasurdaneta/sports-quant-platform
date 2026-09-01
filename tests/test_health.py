"""Tests for the pipeline health report. SYNTHETIC only."""
from __future__ import annotations

import pandas as pd

from sqp.monitoring.health import ML_LEAGUES, generate_health_report


def test_empty_root_errors(tmp_path):
    # Missing artifacts are ERRORS since the 2026-07-24 audit (M-1): they make
    # the pipeline inoperative and must trip the BAT errorlevel guards.
    r = generate_health_report(root=tmp_path)
    assert r["status"] == "ERROR"
    assert set(r["leagues"]) == set(ML_LEAGUES)
    assert any("no stored results" in e for e in r["errors"])
    assert (tmp_path / "data" / "output" / "pipeline_health.json").exists()


def test_present_artifacts_reduce_warnings(tmp_path):
    data = tmp_path / "data"
    (data / "historical").mkdir(parents=True)
    (data / "features").mkdir(parents=True)
    (data / "models").mkdir(parents=True)
    pd.DataFrame({"date": ["2024-01-01"], "home": ["A"], "away": ["B"],
                  "game_id": ["1"], "home_score": [1], "away_score": [0]}
                 ).to_csv(data / "historical" / "results_nba.csv", index=False)
    pd.DataFrame({"home_win": [1, 0]}).to_csv(
        data / "features" / "nba_training_dataset.csv", index=False)
    (data / "models" / "nba_moneyline_model.joblib").write_bytes(b"x")

    r = generate_health_report(root=tmp_path)
    assert r["leagues"]["nba"]["results_rows"] == 1
    assert r["leagues"]["nba"]["moneyline_model"] is True
    # nba no longer errors about missing results/model; other leagues still do
    assert not any(e.startswith("nba: no stored results") for e in r["errors"])
    assert any(e.startswith("mlb:") for e in r["errors"])
    assert r["status"] == "ERROR"  # still ERROR because mlb/nfl/nhl incomplete


def test_health_detects_per_market_calibration_registry(tmp_path):
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "mlb_spreads_calibration_iso.joblib").write_bytes(b"x")
    (models / "calibration_methods.json").write_text(
        '{"mlb_spreads": "isotonic"}', encoding="utf-8")
    r = generate_health_report(root=tmp_path)
    assert r["leagues"]["mlb"]["calibration"] is True
    assert r["leagues"]["mlb"]["calibration_markets"] == ["spreads"]


# --- El informe vigilaba un universo casi disjunto del que se sirve -----------
#
# `ML_LEAGUES` es FIJO (mlb/nba/nfl/nhl) y lo servido es DINAMICO. El 2026-09-01
# los dos conjuntos se cruzaban en UNA liga: se vigilaban nba/nfl/nhl, que no se
# sirven (fuera de temporada, luego su falta de calibrador NO es un fallo), y
# quedaban fuera del informe las 22 servidas, incluida `wnba` con calibrador vivo.

def test_el_inventario_incluye_ligas_servidas_fuera_de_ML_LEAGUES(tmp_path):
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "wnba_spreads_calibration_iso.joblib").write_bytes(b"x")
    (models / "calibration_methods.json").write_text(
        '{"wnba_spreads": "isotonic"}', encoding="utf-8")
    _served(tmp_path, "wnba", [1])
    _served(tmp_path, "epl", [1])
    r = generate_health_report(root=tmp_path)
    assert "wnba" not in ML_LEAGUES, "premisa del test: wnba no es liga ML"
    assert r["served_calibration"]["wnba"] == ["spreads"], (
        "el calibrador vivo de una liga servida no-ML era invisible")
    assert "epl" in r["served_calibration"]


def test_una_liga_servida_sin_calibrador_no_genera_aviso(tmp_path):
    """21 de 23 ligas servidas no tienen calibrador y la ausencia es un no-op
    soportado. Convertirlo en warning seria la alarma permanente que este modulo
    ya rechaza para las filas irrecuperables: una alarma que no se puede apagar
    deja de leerse."""
    _served(tmp_path, "epl", [1])
    r = generate_health_report(root=tmp_path)
    assert r["served_without_calibration"] == ["epl"]
    assert not any("calibrad" in w for w in r["warnings"]), (
        "la ausencia de calibrador no debe alarmar; solo registrarse")


def test_un_calibrador_registrado_sin_artefacto_si_avisa(tmp_path):
    """Incoherencia OBJETIVA y sin umbral nuevo: el registro afirma un
    calibrador que no esta en disco. `_live_calibration_markets` lo descarta en
    silencio, que es correcto para resolver que esta vivo, pero dejaba el
    desajuste invisible."""
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "calibration_methods.json").write_text(
        '{"mlb_spreads": "isotonic"}', encoding="utf-8")  # sin el .joblib
    r = generate_health_report(root=tmp_path)
    assert r["orphan_calibration_entries"] == ["mlb_spreads (isotonic)"]
    assert any("sin artefacto en disco" in w for w in r["warnings"])
    assert r["status"] != "OK"


def test_un_registro_de_calibracion_ilegible_no_pasa_en_silencio(tmp_path):
    models = tmp_path / "data" / "models"
    models.mkdir(parents=True)
    (models / "calibration_methods.json").write_text("{no es json", encoding="utf-8")
    r = generate_health_report(root=tmp_path)
    assert r["orphan_calibration_entries"], "un registro ilegible deja el pipeline sin calibradores"


def test_corrupt_results_file_is_logged_not_silently_counted_as_absent(tmp_path, caplog):
    # An unreadable CSV already reaches the same None/0 branch as a missing one,
    # so the status was never wrong -- but the operator could not tell "never
    # ingested" from "ingested and now corrupt", which need different repairs.
    hist = tmp_path / "data" / "historical"
    hist.mkdir(parents=True)
    corrupt = hist / f"results_{ML_LEAGUES[0]}.csv"
    corrupt.write_bytes(b'a,b\n"unterminated,1\n\x00\x00')

    with caplog.at_level("WARNING", logger="sqp.monitoring.health"):
        generate_health_report(root=tmp_path)

    assert any("no se pudo leer" in rec.getMessage() for rec in caplog.records), \
        "un CSV ilegible debe registrarse, no confundirse con uno ausente"


# --- Punto ciego de las filas servidas irrecuperables -------------------------
#
# `_served_pending_expired` se apoyaba en `ServedStore.pending`, que descarta lo
# anterior a 7 dias porque su proposito es acotar el trabajo de la liquidacion.
# Heredando ese corte, el aviso solo veia la ventana de 3 a 7 dias: el 2026-08-29
# reportaba 4 filas mientras habia 154 irrecuperables, 150 invisibles por
# antiguas. Justo el punto ciego que su docstring decia cerrar.

def _served(tmp_path, liga: str, dias_atras: list[int]):
    """Escribe filas servidas SIN graduar cuyo evento empezo hace `dias_atras`."""
    from datetime import datetime, timedelta, timezone
    ahora = datetime.now(timezone.utc)
    filas = [{
        "league": liga, "event_id": f"e{d}", "market": "h2h",
        "selection": "A", "line": 0.0,
        "start_time": (ahora - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "price_decimal": 2.0, "model_probability": 0.5,
    } for d in dias_atras]
    cal = tmp_path / "data" / "calibration"
    cal.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(cal / f"served_{liga}.csv", index=False)


def test_expired_rows_older_than_the_scan_window_are_counted(tmp_path):
    """Lo viejo ya no puede desaparecer del informe."""
    _served(tmp_path, "mlb", [5, 30, 60])          # 1 reciente, 2 antiguas
    r = generate_health_report(root=tmp_path)
    assert r["served_pending_expired_total"]["mlb"] == 3
    # y solo la reciente es accionable
    assert r["served_pending_expired"]["mlb"] == 1


def test_only_the_recent_expiry_raises_the_warning(tmp_path):
    """La perdida acumulada no genera warning: no se puede arreglar, y una
    alarma que no se apaga deja de leerse."""
    _served(tmp_path, "mlb", [30, 60])             # ninguna reciente
    r = generate_health_report(root=tmp_path)
    assert r["served_pending_expired_total"]["mlb"] == 2
    assert "mlb" not in r["served_pending_expired"]
    assert not any("beyond the scores window" in w for w in r["warnings"])


def test_a_game_not_yet_played_is_not_counted_as_lost(tmp_path):
    """Premisa: un partido futuro esta pendiente, no perdido."""
    _served(tmp_path, "mlb", [-2])
    r = generate_health_report(root=tmp_path)
    assert r["served_pending_expired_total"] == {}
    assert r["served_pending_expired"] == {}
