"""AUD-003 (ronda audit-2026-09-18): una clave SANDBOX (`<liga>_h2h_pergame`)
no puede llegar al registro live por promocion, y si esta ahi no cuenta como
calibrador vivo.

`pergame.py` fija el contrato: la clave sandbox vive SOLO en staging;
produccion resuelve `<liga>_h2h` (`calibration_key`), asi que un mapa bajo la
sandbox en el registro live no lo aplica nadie. `promote_calibrators(keys=None)`
promovia TODO staging y el 2026-08-23 instalo `mlb_h2h_pergame` en live:
`mlb_h2h` se servia en crudo mientras `health_check` (`calibration=True`,
mercado "h2h_pergame") y el dashboard ("En produccion: 4") decian lo contrario.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from sklearn.isotonic import IsotonicRegression

import sqp.calibration.calibrator as cal
from sqp.calibration.pergame import PERGAME_SUFFIX, pergame_key
from sqp.monitoring.health import (_live_calibration_markets,
                                   _orphan_calibration_entries)

LEAGUE = "mlb"


def _iso_compresivo() -> IsotonicRegression:
    iso = IsotonicRegression(out_of_bounds="clip")
    grid = np.linspace(0.05, 0.95, 50)
    iso.fit(grid, 0.5 + (grid - 0.5) * 0.7)
    return iso


def _stage(key: str, *, n_val_events: int = 200) -> None:
    path = cal._model_path(key, "iso", staging=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    cal._persist_or_remove(_iso_compresivo(), path, True)
    cal._set_best_method(key, "isotonic", staging=True)
    cal._write_staging_meta(key, n_val=n_val_events, n_val_events=n_val_events)


def _install_live(key: str) -> None:
    path = cal._model_path(key, "iso")
    path.parent.mkdir(parents=True, exist_ok=True)
    cal._persist_or_remove(_iso_compresivo(), path, True)
    if cal.is_sandbox_key(key):
        # Estado HISTORICO (registro escrito antes del invariante de
        # `_set_best_method`): se reproduce escribiendo el JSON directamente.
        reg = cal._load_method_registry()
        reg[key] = "isotonic"
        cal._method_registry_path().write_text(json.dumps(reg), encoding="utf-8")
    else:
        cal._set_best_method(key, "isotonic")


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    yield tmp_path / "models"
    cal._load_calibrator.cache_clear()


def test_is_sandbox_key():
    assert cal.is_sandbox_key(pergame_key(LEAGUE))
    assert pergame_key(LEAGUE).endswith(PERGAME_SUFFIX)
    assert not cal.is_sandbox_key("mlb_h2h")
    assert not cal.is_sandbox_key("mlb_totals")


def test_full_promotion_never_adopts_the_sandbox_key(models_dir):
    _stage(pergame_key(LEAGUE))
    _stage("mlb_spreads")
    promoted = cal.promote_calibrators(keys=None)
    assert promoted == ["mlb_spreads"]
    live = cal._load_method_registry()
    assert pergame_key(LEAGUE) not in live
    assert "mlb_h2h" not in live               # adoptar es una decision aparte
    assert not cal._model_path(pergame_key(LEAGUE), "iso").exists()


def test_explicit_keys_promotion_rejects_the_sandbox_key(models_dir):
    _stage(pergame_key(LEAGUE))
    assert cal.promote_calibrators(keys=[pergame_key(LEAGUE)]) == []
    assert cal._load_method_registry() == {}


def test_full_promotion_demotes_a_sandbox_key_already_live(models_dir):
    """El estado real de produccion el 2026-09-18: la sandbox YA estaba en live."""
    _install_live(pergame_key(LEAGUE))
    _stage(pergame_key(LEAGUE))          # y sigue en staging
    _stage("mlb_spreads")
    cal.promote_calibrators(keys=None)
    assert pergame_key(LEAGUE) not in cal._load_method_registry()
    assert not cal._model_path(pergame_key(LEAGUE), "iso").exists()


def test_demote_calibrators_removes_key_artifacts_and_logs(models_dir):
    _install_live(pergame_key(LEAGUE))
    _install_live("mlb_spreads")
    demoted = cal.demote_calibrators([pergame_key(LEAGUE)], reason="clave sandbox sin consumidor")
    assert demoted == [pergame_key(LEAGUE)]
    assert cal._load_method_registry() == {"mlb_spreads": "isotonic"}
    assert not cal._model_path(pergame_key(LEAGUE), "iso").exists()
    log_text = (models_dir / "promotion_log.csv").read_text(encoding="utf-8")
    assert pergame_key(LEAGUE) in log_text and "demoted" in log_text
    # idempotente: demover lo que no esta no falla ni escribe
    assert cal.demote_calibrators([pergame_key(LEAGUE)], reason="x") == []


def test_serving_ignores_sandbox_key_and_health_does_not_count_it(models_dir):
    _install_live(pergame_key(LEAGUE))
    # produccion resuelve <liga>_h2h: sin entrada -> no-op
    assert cal.calibrate_probability(0.62, LEAGUE, "h2h", "auto") == pytest.approx(0.62)
    # y la sandbox NO cuenta como calibrador vivo de la liga
    assert _live_calibration_markets(models_dir, LEAGUE) == []
    huerfanas = _orphan_calibration_entries(models_dir)
    assert any(pergame_key(LEAGUE) in h and "sandbox" in h for h in huerfanas)


def test_health_counts_real_keys_unchanged(models_dir):
    _install_live("mlb_spreads")
    assert _live_calibration_markets(models_dir, LEAGUE) == ["spreads"]
    assert _orphan_calibration_entries(models_dir) == []


def test_auto_promote_demotes_live_sandbox_key(models_dir):
    _install_live(pergame_key(LEAGUE))
    _stage(pergame_key(LEAGUE))
    out = cal.auto_promote_calibrators([])
    assert pergame_key(LEAGUE) in out["demoted"]
    assert pergame_key(LEAGUE) not in cal._load_method_registry()


def test_live_registry_on_disk_has_no_sandbox_key():
    """Candado sobre el DATO de produccion (data/models no esta bajo git):
    tras la democion del 2026-09-18 el registro live no debe volver a tener
    una clave que `calibration_key` nunca produce."""
    path = cal._method_registry_path()
    if not path.exists():
        pytest.skip("registro live ausente en este entorno")
    reg = json.loads(path.read_text(encoding="utf-8"))
    assert [k for k in reg if cal.is_sandbox_key(k)] == []


def test_set_best_method_refuses_sandbox_key_in_live(models_dir):
    """Invariante en el origen (revision `fable` de AUD-003): ni
    `train_calibration(staging=False)` ni un uso directo pueden registrar una
    clave sandbox en live; en staging sigue permitido; borrar de live tambien."""
    with pytest.raises(ValueError):
        cal._set_best_method(pergame_key(LEAGUE), "beta")
    cal._set_best_method(pergame_key(LEAGUE), "beta", staging=True)
    assert cal._load_method_registry(staging=True) == {pergame_key(LEAGUE): "beta"}
    cal._set_best_method(pergame_key(LEAGUE), None)  # no lanza
    assert cal._load_method_registry() == {}


def test_full_sync_demotion_leaves_a_trail_in_promotion_log(models_dir):
    _install_live("mlb_totals")           # ausente en staging -> se demueve
    _stage("mlb_spreads")
    cal.promote_calibrators(keys=None)
    log_text = (models_dir / "promotion_log.csv").read_text(encoding="utf-8")
    assert "mlb_totals" in log_text and "demoted: sync completa" in log_text


def test_cli_demote_is_dry_run_without_yes(models_dir, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    _install_live("mlb_spreads")
    spec = importlib.util.spec_from_file_location(
        "promote_cli", Path(__file__).resolve().parents[1] / "scripts" / "promote_calibration.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr("sys.argv", ["promote_calibration.py", "--demote", "mlb_spreads"])
    assert mod.main() == 0
    assert "DRY RUN" in capsys.readouterr().out
    assert cal._load_method_registry() == {"mlb_spreads": "isotonic"}   # intacto
    monkeypatch.setattr("sys.argv", ["promote_calibration.py", "--demote", "mlb_spreads",
                                     "--yes", "--reason", "prueba"])
    assert mod.main() == 0
    assert cal._load_method_registry() == {}
