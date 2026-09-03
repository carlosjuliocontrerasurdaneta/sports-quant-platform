"""Tests for the ported probability calibrator. SYNTHETIC data only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.isotonic import IsotonicRegression

from sqp.calibration import calibrator as cal
from sqp.calibration.metrics import expected_calibration_error


def _miscalibrated(n: int = 3000, seed: int = 0):
    """Estimated probs with a monotone systematic bias vs true outcome rate."""
    rng = np.random.default_rng(seed)
    model_prob = rng.uniform(0.1, 0.9, n)
    true_prob = np.clip(model_prob ** 1.8, 0.02, 0.98)  # systematic overconfidence
    outcomes = (rng.uniform(size=n) < true_prob).astype(float)
    return pd.DataFrame({"probability": model_prob, "home_win": outcomes})


def test_beta_calibrator_bounds():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.95, 500)
    y = (rng.uniform(size=500) < p).astype(float)
    out = cal.BetaCalibrator().fit(p, y).predict(p)
    assert out.shape == p.shape
    assert np.all(out >= 0.01) and np.all(out <= 0.99)


def test_is_monotone_increasing_detects_non_monotone():
    # An increasing calibrator passes the guard.
    assert cal._is_monotone_increasing(lambda x: np.asarray(x, dtype=float)) is True
    # A U-shaped map (decreasing then increasing) inverts rank order and is rejected,
    # even though it is a perfectly valid probability in [0, 1].
    assert cal._is_monotone_increasing(lambda x: (np.asarray(x, dtype=float) - 0.5) ** 2) is False


def test_apply_without_model_is_noop():
    probs = np.array([0.2, 0.5, 0.8])
    out = cal.apply_calibration(probs, sport="no_such_sport_xyz")
    assert np.allclose(out, probs)  # unchanged when no model exists


def test_train_improves_oos_calibration(tmp_path, monkeypatch):
    # Redirect model persistence to a temp dir (don't touch the project's data/).
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")

    df = _miscalibrated()
    split = int(len(df) * 0.8)
    raw_val_ece = expected_calibration_error(
        df.iloc[split:]["probability"], df.iloc[split:]["home_win"])

    res = cal.train_calibration(df, sport="unit_test")

    assert res["n_train"] + res["n_val"] == len(df)
    assert (tmp_path / "models" / "unit_test_calibration_iso.joblib").exists()
    # Calibration must not worsen out-of-sample; here it clearly improves.
    assert res["val_metrics"]["ece"] <= raw_val_ece

    # Round-trip: a trained model now transforms inputs within bounds.
    out = cal.apply_calibration(np.array([0.3, 0.6, 0.9]), sport="unit_test")
    assert np.all(out >= 0.01) and np.all(out <= 0.99)


def test_train_rejects_tiny_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    df = pd.DataFrame({"probability": [0.5] * 10, "home_win": [0, 1] * 5})
    with pytest.raises(ValueError):
        cal.train_calibration(df, sport="too_small")


def test_temporal_holdout_keeps_event_sides_together(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    # Two complementary rows per event. A row-level 80/20 split would count
    # eight validation rows as eight independent observations and can split an
    # event at the boundary; the grouped split must report four events.
    rows = []
    for i in range(20):
        day = f"2026-05-{i + 1:02d}"
        rows += [
            {"probability": 0.70, "won": float(i % 2 == 0),
             "date": day, "event_id": f"e{i}"},
            {"probability": 0.30, "won": float(i % 2 != 0),
             "date": day, "event_id": f"e{i}"},
        ]
    res = cal.train_calibration(
        pd.DataFrame(rows), prob_col="probability", outcome_col="won",
        sport="grouped", time_col="date", group_col="event_id")
    assert res["n_train_events"] == 16
    assert res["n_val_events"] == 4
    assert res["n_train"] == 32 and res["n_val"] == 8


def test_persist_or_remove_writes_and_cleans_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    (tmp_path / "models").mkdir()
    cal._load_calibrator.cache_clear()
    p = cal._model_path("x_h2h", "iso")
    # keep=True persists the model
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=True) is True
    assert p.exists()
    # keep=False removes the stale model -> live application falls back to no-op
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=False) is False
    assert not p.exists()
    # removing an already-absent model is safe
    assert cal._persist_or_remove(IsotonicRegression(), p, keep=False) is False


def test_train_keeps_improving_model_and_reports_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_keep")
    # clearly miscalibrated input -> calibration helps -> persisted
    assert res["iso_persisted"] is True and res["persisted"] is True
    assert "beta_val_ece" in res
    assert (tmp_path / "models" / "unit_keep_calibration_iso.joblib").exists()


class _UShapedBeta:
    """A calibrator whose predict() is U-shaped (decreasing then increasing) -- it
    inverts rank order at the low end, exactly the mlb_spreads degeneracy."""

    def fit(self, probs, outcomes):
        return self

    def predict(self, probs):
        probs = np.asarray(probs, dtype=float)
        return np.clip((probs - 0.5) ** 2 + 0.4, 0.01, 0.99)


def test_train_drops_non_monotone_calibrator_despite_good_ece(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    # Make the isotonic OOS ECE worse than raw so iso is dropped; only beta is a
    # candidate to persist.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    # Raw ECE high, beta ECE low -> beta BEATS raw on ECE, so without the
    # monotonicity guard it WOULD persist. Stub statefully: 1st call raw, 2nd beta.
    calls = {"n": 0}

    def fake_ece(*a, **k):
        calls["n"] += 1
        return 0.5 if calls["n"] == 1 else 0.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    # Force the beta calibrator to be non-monotone (U-shaped).
    monkeypatch.setattr(cal, "BetaCalibrator", _UShapedBeta)

    res = cal.train_calibration(_miscalibrated(), sport="unit_ushape")

    # Beats raw on ECE but is rejected purely for non-monotonicity.
    assert res["beta_persisted"] is False
    assert res["best_method"] is None
    assert not (tmp_path / "models" / "unit_ushape_calibration_beta.joblib").exists()
    # live application for this market is therefore a safe no-op
    assert cal.apply_calibration(np.array([0.3]), sport="unit_ushape", method="auto")[0] == 0.3


def test_no_extreme_expansion_guard():
    # Identity and compression toward the middle are fine.
    assert cal._no_extreme_expansion(lambda x: np.asarray(x, dtype=float)) is True
    assert cal._no_extreme_expansion(
        lambda x: 0.35 + 0.3 * np.asarray(x, dtype=float)) is True
    # A step that sends non-extreme favorites to 0.99 (wnba_h2h 2026-07-13,
    # mlb_spreads 2026-06-30) must be rejected.
    assert cal._no_extreme_expansion(
        lambda x: np.where(np.asarray(x, dtype=float) >= 0.75, 0.99, 0.50)) is False
    # A downward correction of overconfident underdog probs suppresses picks
    # rather than creating phantom edges, so it stays allowed.
    assert cal._no_extreme_expansion(
        lambda x: np.where(np.asarray(x, dtype=float) <= 0.25, 0.01, 0.50)) is True
    # Mapping a genuinely extreme input to an extreme output stays allowed.
    assert cal._no_extreme_expansion(
        lambda x: np.clip(np.asarray(x, dtype=float), 0.04, 0.96)) is True


def test_keeps_resolution_guard():
    """La quinta condicion. Las otras cuatro vigilan el exceso de confianza; el
    fallo simetrico -- colapsar a una constante -- las pasaba todas."""
    # La identidad conserva toda la resolucion.
    assert cal._keeps_resolution(lambda x: np.asarray(x, dtype=float)) is True
    # `ligamx_spreads` del 2026-08-28: TODO a 0,500, aceptado en staging.
    assert cal._keeps_resolution(lambda x: np.full(np.shape(x), 0.50)) is False
    # `ligue1_spreads`: 0,455-0,545. Cabe entero en un bin de ECE.
    assert cal._keeps_resolution(
        lambda x: 0.455 + 0.09 * (np.asarray(x, dtype=float) >= 0.5)) is False
    # Un encogimiento fuerte pero con recorrido real sigue siendo legitimo: dice
    # que el modelo discrimina poco, no que no discrimina nada.
    assert cal._keeps_resolution(
        lambda x: 0.35 + 0.3 * np.asarray(x, dtype=float)) is True


def test_keeps_resolution_rejects_a_map_flat_where_the_picks_live():
    """El candidato de `wnba_totals` del 2026-08-28: recorrido 0,2121 sobre
    [0,05, 0,95] -- por encima del umbral -- pero constante en 0,499 de 0,25 a
    0,75. Todo el recorrido lo compraban las colas, donde casi no hay picks."""
    def colas(x):
        x = np.asarray(x, dtype=float)
        return np.where(x < 0.20, 0.333, np.where(x > 0.80, 0.545, 0.499))

    assert cal._keeps_resolution(colas, min_range=0.10) is False
    # Contraprueba: el mismo recorrido total repartido POR la banda si vale.
    assert cal._keeps_resolution(
        lambda x: 0.39 + 0.21 * np.asarray(x, dtype=float)) is True


def test_a_constant_map_passes_the_other_four_gates():
    """El motivo de existir de la quinta, escrito como prueba: si alguna de las
    otras cuatro cazara la constante, esta condicion sobraria."""
    constante = lambda x: np.full(np.shape(x), 0.50)  # noqa: E731
    assert cal._is_monotone_increasing(constante) is True
    assert cal._no_extreme_expansion(constante) is True
    # ECE y Brier son las otras dos, y con tasa base 0,5 una constante 0,5 da
    # ECE 0 y Brier 0,25 -- que en estos mercados bate al modelo crudo.
    from sqp.calibration.metrics import expected_calibration_error
    y = np.array([1.0, 0.0] * 50)
    p = np.full(100, 0.50)
    assert expected_calibration_error(p, y) == pytest.approx(0.0, abs=1e-9)
    assert float(np.mean((p - y) ** 2)) == pytest.approx(0.25)


class _ConstantCalibrator:
    """Mapa colapsado: la forma que pasaba las cuatro condiciones anteriores."""

    def fit(self, probs, outcomes):
        return self

    def predict(self, probs):
        return np.full(np.shape(probs), 0.50)


class _ShrinkingCalibrator:
    """Encoge fuerte pero conserva recorrido: legitimo, debe seguir aplicandose.
    A nivel de modulo porque joblib no serializa clases locales de un test."""

    def fit(self, probs, outcomes):
        return self

    def predict(self, probs):
        return 0.25 + 0.5 * np.asarray(probs, dtype=float)


class _ExtremePushingBeta:
    """Monotone calibrator that pushes favorites >= 0.75 to 0.99 -- the phantom
    -edge shape that passed ECE, Brier AND monotonicity on a small split."""

    def fit(self, probs, outcomes):
        return self

    def predict(self, probs):
        probs = np.asarray(probs, dtype=float)
        return np.where(probs >= 0.75, 0.99, np.minimum(probs, 0.74))


def test_train_drops_extreme_pushing_calibrator_despite_good_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    # Drop iso via a bad reported ECE so beta is the only candidate.
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    # Stub metrics so beta BEATS raw on both ECE and Brier: without the
    # extremity guard it would persist.
    ece_calls = {"n": 0}

    def fake_ece(*a, **k):
        ece_calls["n"] += 1
        return 0.5 if ece_calls["n"] == 1 else 0.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    monkeypatch.setattr(cal, "brier_score", lambda *a, **k: 0.1)
    monkeypatch.setattr(cal, "BetaCalibrator", _ExtremePushingBeta)

    res = cal.train_calibration(_miscalibrated(), sport="unit_extreme")

    assert res["beta_gate"]["monotone_ok"] is True
    assert res["beta_gate"]["ece_ok"] is True
    assert res["beta_gate"]["extreme_ok"] is False
    assert res["beta_persisted"] is False
    assert not (tmp_path / "models" / "unit_extreme_calibration_beta.joblib").exists()
    # live application for this market is therefore a safe no-op
    assert cal.apply_calibration(np.array([0.8]), sport="unit_extreme", method="auto")[0] == 0.8


def test_train_drops_a_collapsed_calibrator_despite_good_metrics(tmp_path, monkeypatch):
    """El caso real: un mapa constante con ECE y Brier mejores que el crudo. Es
    lo que estaba ACEPTADO en staging para `ligamx_spreads` el 2026-08-28."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    ece_calls = {"n": 0}

    def fake_ece(*a, **k):
        ece_calls["n"] += 1
        return 0.5 if ece_calls["n"] == 1 else 0.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    monkeypatch.setattr(cal, "brier_score", lambda *a, **k: 0.1)
    monkeypatch.setattr(cal, "BetaCalibrator", _ConstantCalibrator)

    res = cal.train_calibration(_miscalibrated(), sport="unit_colapso")

    assert res["beta_gate"]["ece_ok"] is True
    assert res["beta_gate"]["brier_ok"] is True
    assert res["beta_gate"]["monotone_ok"] is True
    assert res["beta_gate"]["extreme_ok"] is True
    assert res["beta_gate"]["resolution_ok"] is False, "solo la quinta lo caza"
    assert res["beta_persisted"] is False
    # Sin calibrador, el mercado se sirve en crudo: honesto, y no convierte el
    # edge en una funcion del precio.
    assert cal.apply_calibration(np.array([0.8]), sport="unit_colapso",
                                 method="auto")[0] == 0.8


def test_a_collapsed_live_calibrator_is_ignored_at_apply_time(tmp_path, monkeypatch):
    """El registro LIVE no se reevalua nunca: lo escribe la promocion y ahi se
    queda. El 2026-08-28 `wnba_totals` llevaba dias en produccion mandando toda
    probabilidad a 0,490, con el `estimated_edge` de ese mercado correlacionando
    0,97 con la CUOTA. El gate de entrenamiento no lo habria salvado: es
    anterior. Por eso se comprueba tambien al aplicar."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ConstantCalibrator(), str(cal._model_path("liga_totals", "iso")))
    cal._set_best_method("liga_totals", "isotonic")

    probs = np.array([0.30, 0.50, 0.70])
    out = cal.apply_calibration(probs, sport="liga_totals", method="auto")
    assert np.allclose(out, probs), "se sirve en crudo, no aplanado"


@pytest.mark.parametrize("modelo, defecto", [
    (_UShapedBeta, "no monotono"),
    (_ExtremePushingBeta, "expande a extremos"),
])
def test_any_structural_defect_is_ignored_at_apply_time(tmp_path, monkeypatch,
                                                        modelo, defecto):
    """Al aplicar se comprueba `structural_defect` ENTERO, no solo el colapso.

    La promocion evalua las tres condiciones; el servicio evaluaba UNA -- la del
    incidente de `wnba_totals` que lo motivo (auditoria 2026-09-03, AUD-MED-002).
    Un artefacto promovido ANTES de que existieran las puertas podia seguir vivo
    siendo no monotono o expansivo sin que nadie lo viera, y esos dos son peores
    para el dinero que el colapso: "expande a extremos" sube `p_decision`, con
    ella el `edge` y con el el STAKE de Kelly, y "no monotono" invierte el orden
    de una lista que se sirve ordenada por probabilidad. El colapso, en
    comparacion, solo aplana.

    Ambos mapas son legibles y devuelven probabilidades validas en [0,1]: lo que
    los descalifica es la forma, no un error de carga.
    """
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    key = "liga_h2h"
    joblib.dump(modelo(), str(cal._model_path(key, "iso")))
    cal._set_best_method(key, "isotonic")
    # El mapa esta vivo y es el defecto que decimos: si esto cambia, el test
    # dejaria de probar lo que cree probar.
    assert cal.structural_defect(modelo().predict) == defecto

    probs = np.array([0.30, 0.60, 0.80])
    out = cal.apply_calibration(probs, sport=key, method="auto")
    assert np.allclose(out, probs), (
        f"un calibrador live '{defecto}' se aplico en vez de degradar a crudo")


def test_a_healthy_live_calibrator_still_applies(tmp_path, monkeypatch):
    """Contraprueba: sin ella, un guard que ignorase SIEMPRE pasaria igual."""
    import joblib

    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ShrinkingCalibrator(), str(cal._model_path("liga_h2h", "iso")))
    cal._set_best_method("liga_h2h", "isotonic")

    out = cal.apply_calibration(np.array([0.80]), sport="liga_h2h", method="auto")
    assert out[0] == pytest.approx(0.65)


def test_train_reports_per_gate_verdicts(tmp_path, monkeypatch):
    """Observabilidad del gate: el resultado debe decir CUAL condicion paso/fallo
    (ECE / Brier / monotonia) por modelo. El 2026-07-02 un mlb_spreads que
    MEJORABA el ECE OOS fue descartado y el log solo decia '(dropped)': hubo que
    reproducir el fit a mano para descubrir que fue el Brier. La persistencia
    debe ser exactamente la conjuncion de los tres veredictos."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_gates")
    for key in ("iso_gate", "beta_gate"):
        assert set(res[key]) == {"ece_ok", "brier_ok", "monotone_ok",
                                 "extreme_ok", "resolution_ok"}
        for v in res[key].values():
            assert isinstance(v, bool)
    assert res["iso_persisted"] == all(res["iso_gate"].values())
    assert res["beta_persisted"] == all(res["beta_gate"].values())


def test_train_gate_verdicts_flag_brier_failure(tmp_path, monkeypatch):
    """Cuando el drop es por Brier (pasa ECE, es monotono), el veredicto debe
    senalar brier_ok=False y los otros dos True."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 0.0, "brier_score": 1.0})
    monkeypatch.setattr(cal, "expected_calibration_error", lambda *a, **k: 0.5)
    brier_calls = {"n": 0}

    def fake_brier(*a, **k):
        brier_calls["n"] += 1
        return 0.1 if brier_calls["n"] == 1 else 1.0

    monkeypatch.setattr(cal, "brier_score", fake_brier)

    res = cal.train_calibration(_miscalibrated(), sport="unit_gate_brier")

    assert res["iso_gate"]["ece_ok"] is True
    assert res["iso_gate"]["brier_ok"] is False
    assert res["iso_gate"]["monotone_ok"] is True
    assert res["iso_persisted"] is False


def test_train_drops_calibrator_that_passes_ece_but_worsens_brier(tmp_path, monkeypatch):
    """A monotone calibrator can pass the binned-ECE gate yet be overconfident in
    a way a proper scoring rule exposes: pushing favorites toward 0.9 inflates the
    out-of-sample Brier score even when each ECE bin's average looks fine. That is
    exactly the mlb_spreads regression -- a monotone-but-overfit isotonic step that
    manufactured phantom edges. The gate must reject it on OOS Brier."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    # iso PASSES the ECE gate (cal ECE 0.0 <= raw ECE 0.5) but its Brier is worse.
    monkeypatch.setattr(cal, "calibration_report",
                        lambda probs, outcomes: {"ece": 0.0, "brier_score": 1.0})
    monkeypatch.setattr(cal, "expected_calibration_error", lambda *a, **k: 0.5)
    # brier_score: 1st call = raw (low 0.1), 2nd = beta (high 1.0) -> raw beats both.
    brier_calls = {"n": 0}

    def fake_brier(*a, **k):
        brier_calls["n"] += 1
        return 0.1 if brier_calls["n"] == 1 else 1.0

    # raising=False: the production code does not reference brier_score yet (RED).
    monkeypatch.setattr(cal, "brier_score", fake_brier, raising=False)

    res = cal.train_calibration(_miscalibrated(), sport="unit_brier")

    # Passes ECE + is monotone, but worsens OOS Brier -> dropped.
    assert res["iso_persisted"] is False
    assert res["best_method"] is None
    assert not (tmp_path / "models" / "unit_brier_calibration_iso.joblib").exists()
    # live application for this market is therefore a safe no-op
    assert cal.apply_calibration(np.array([0.7]), sport="unit_brier", method="auto")[0] == 0.7


def test_train_to_staging_does_not_promote_to_live(tmp_path, monkeypatch):
    """A retrain must never make a calibrator live in the same cycle. Training
    with staging=True writes the candidate model + a STAGING registry, but leaves
    the LIVE registry untouched, so the pipeline (apply method='auto') stays a
    no-op until an explicit promotion. This is the architectural guard against a
    degenerate daily-retrained calibrator auto-installing itself into production."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()

    res = cal.train_calibration(_miscalibrated(), sport="unit_stage", staging=True)
    assert res["persisted"] is True  # a good candidate was produced

    # LIVE registry untouched -> pipeline still a no-op for this market.
    assert "unit_stage" not in cal._load_method_registry()
    assert cal.apply_calibration(np.array([0.85]), "unit_stage", method="auto")[0] == 0.85
    # ...but the candidate is staged, ready to promote.
    assert "unit_stage" in cal._load_method_registry(staging=True)


def test_promote_calibrators_moves_staging_to_live(tmp_path, monkeypatch):
    """The explicit, separate promotion step copies a staged candidate into the
    live registry (and its model file), after which the pipeline applies it."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    cal.train_calibration(_miscalibrated(), sport="unit_promote", staging=True)

    promoted = cal.promote_calibrators()

    assert "unit_promote" in promoted
    assert "unit_promote" in cal._load_method_registry()          # now live
    # the live model file exists and the pipeline now transforms inputs
    assert cal._model_path("unit_promote", "iso").exists()
    out = cal.apply_calibration(np.array([0.85]), "unit_promote", method="auto")[0]
    assert out != 0.85 and 0.01 <= out <= 0.99


def test_method_registry_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    assert cal._load_method_registry() == {}          # absent -> empty
    cal._set_best_method("mlb_spreads", "beta")
    cal._set_best_method("nhl_h2h", "isotonic")
    assert cal._load_method_registry() == {"mlb_spreads": "beta",
                                           "nhl_h2h": "isotonic"}
    cal._set_best_method("mlb_spreads", None)          # clear -> group drops out
    assert cal._load_method_registry() == {"nhl_h2h": "isotonic"}


def test_train_records_best_method_and_auto_matches_it(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    res = cal.train_calibration(_miscalibrated(), sport="unit_auto")

    best = res["best_method"]
    assert best in ("isotonic", "beta")               # a winner was chosen
    assert cal._load_method_registry()["unit_auto"] == best
    # method="auto" must resolve to exactly the recorded method's model.
    probs = np.array([0.3, 0.6, 0.9])
    assert np.allclose(cal.apply_calibration(probs, "unit_auto", "auto"),
                       cal.apply_calibration(probs, "unit_auto", best))


def test_apply_auto_noop_when_unregistered(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    probs = np.array([0.2, 0.5, 0.8])
    out = cal.apply_calibration(probs, sport="never_trained", method="auto")
    assert np.allclose(out, probs)                     # no registry entry -> no-op


def test_train_drops_worsening_model_clears_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    cal._set_best_method("unit_noauto", "beta")        # stale entry from a prior fit
    # Force raw to look better than both calibrators so neither persists. raw and
    # beta both call expected_calibration_error, so stub it statefully: 1st call
    # (raw) low, 2nd call (beta) high; iso's ECE comes from calibration_report.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    calls = {"n": 0}

    def fake_ece(*a, **k):
        calls["n"] += 1
        return 0.0 if calls["n"] == 1 else 1.0

    monkeypatch.setattr(cal, "expected_calibration_error", fake_ece)
    res = cal.train_calibration(_miscalibrated(), sport="unit_noauto")
    assert res["iso_persisted"] is False and res["beta_persisted"] is False
    assert res["best_method"] is None                  # nothing helped
    assert "unit_noauto" not in cal._load_method_registry()   # stale entry cleared
    # "auto" therefore falls back to a no-op for this group.
    assert cal.apply_calibration(np.array([0.5]), "unit_noauto", "auto")[0] == 0.5


def test_train_drops_worsening_model_and_removes_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    cal._load_calibrator.cache_clear()
    iso_path = cal._model_path("unit_drop", "iso")
    iso_path.parent.mkdir(parents=True, exist_ok=True)
    iso_path.write_bytes(b"stale")  # a previously-persisted model now on disk

    # Force the isotonic OOS ECE to look worse than raw so the gate must drop it.
    monkeypatch.setattr(cal, "calibration_report", lambda probs, outcomes: {"ece": 1.0, "brier_score": 1.0})
    res = cal.train_calibration(_miscalibrated(), sport="unit_drop")

    assert res["iso_persisted"] is False        # worsening model not kept
    assert not iso_path.exists()                # and the stale file is cleaned
    # live application for this market is now a safe no-op
    assert cal.apply_calibration(np.array([0.5]), sport="unit_drop")[0] == 0.5


# --- Revalidacion del registro LIVE (auditoria 2026-08-28, AUD-MED-002) -------
#
# El registro live no se reevaluaba NUNCA: lo escribe la promocion y ahi se
# queda. La democion existia solo en la sincronizacion completa
# (`promote_calibrators` sin `keys`), asi que promoviendo por `--keys` -- o
# sencillamente no promoviendo -- un mapa degradado seguia sirviendo. Paso:
# `wnba_totals` mando toda probabilidad a 0,490 durante 33 dias.


def test_revalidate_demotes_a_collapsed_live_calibrator(tmp_path, monkeypatch):
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ConstantCalibrator(), str(cal._model_path("liga_totals", "iso")))
    cal._set_best_method("liga_totals", "isotonic")

    assert cal.revalidate_live_registry() == ["liga_totals"]
    assert cal._load_method_registry() == {}
    # y el mercado pasa a servirse en crudo
    assert cal.apply_calibration(np.array([0.3]), sport="liga_totals",
                                 method="auto")[0] == 0.3


def test_revalidate_keeps_a_healthy_live_calibrator(tmp_path, monkeypatch):
    """Contraprueba: sin ella, uno que degradara SIEMPRE pasaria igual."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ShrinkingCalibrator(), str(cal._model_path("liga_h2h", "iso")))
    cal._set_best_method("liga_h2h", "isotonic")

    assert cal.revalidate_live_registry() == []
    assert cal._load_method_registry() == {"liga_h2h": "isotonic"}


def test_revalidate_demotes_a_registry_entry_without_model(tmp_path, monkeypatch):
    """Una entrada que apunta a un fichero que ya no esta es un no-op silencioso;
    mejor decirlo y limpiar el registro."""
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    cal._load_calibrator.cache_clear()
    cal._set_best_method("liga_spreads", "isotonic")

    assert cal.revalidate_live_registry() == ["liga_spreads"]
    assert cal._load_method_registry() == {}


def test_revalidate_never_promotes(tmp_path, monkeypatch):
    """Es estrictamente conservador: solo degrada. Un candidato en staging no
    puede llegar a produccion por esta via."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ShrinkingCalibrator(),
                str(cal._model_path("liga_h2h", "iso", staging=True)))
    cal._set_best_method("liga_h2h", "isotonic", staging=True)

    cal.revalidate_live_registry()
    assert cal._load_method_registry(staging=False) == {}


def test_promotion_refuses_a_structurally_defective_candidate(tmp_path, monkeypatch):
    """El agujero real: el tablero invita a `promote_calibration.py`, y `--yes`
    habria instalado en produccion un mapa que el propio gate de entrenamiento
    rechaza. Paso con el candidato de `wnba_totals` el 2026-08-29."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ConstantCalibrator(),
                str(cal._model_path("liga_totals", "iso", staging=True)))
    cal._set_best_method("liga_totals", "isotonic", staging=True)
    cal._write_staging_meta("liga_totals", n_val=500, n_val_events=200)

    assert cal.promote_calibrators(keys=["liga_totals"]) == []
    assert cal._load_method_registry(staging=False) == {}


def test_force_does_not_override_a_structural_defect(tmp_path, monkeypatch):
    """`force` existe para asumir una muestra fina -- un juicio sobre la
    evidencia --, no para instalar un artefacto invalido."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ConstantCalibrator(),
                str(cal._model_path("liga_totals", "iso", staging=True)))
    cal._set_best_method("liga_totals", "isotonic", staging=True)

    assert cal.promote_calibrators(keys=["liga_totals"], force=True) == []
    assert cal._load_method_registry(staging=False) == {}


def test_promotion_still_accepts_a_healthy_candidate(tmp_path, monkeypatch):
    """Contraprueba: sin ella, un guard que rechazara SIEMPRE pasaria igual."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ShrinkingCalibrator(),
                str(cal._model_path("liga_h2h", "iso", staging=True)))
    cal._set_best_method("liga_h2h", "isotonic", staging=True)
    cal._write_staging_meta("liga_h2h", n_val=500, n_val_events=200)

    assert cal.promote_calibrators(keys=["liga_h2h"]) == ["liga_h2h"]
    assert cal._load_method_registry(staging=False) == {"liga_h2h": "isotonic"}


def test_structural_defect_names_each_failure():
    """Un motivo por condicion: 'invalido' a secas no es auditable."""
    assert cal.structural_defect(lambda x: np.asarray(x, dtype=float)) is None
    assert cal.structural_defect(
        lambda x: (np.asarray(x, dtype=float) - 0.5) ** 2) == "no monotono"
    assert cal.structural_defect(
        lambda x: np.where(np.asarray(x, dtype=float) >= 0.75, 0.99, 0.50)
    ) == "expande a extremos"
    assert cal.structural_defect(
        lambda x: np.full(np.shape(x), 0.50)) == "colapsado (sin resolucion)"


def test_auto_promote_log_records_a_rejection_not_a_promotion(tmp_path, monkeypatch):
    """El rastro de auditoria no puede afirmar una promocion que no ocurrio.
    Antes elegible implicaba promovido; desde que la promocion rechaza defectos
    estructurales (2026-08-29) ya no, y el log habria mentido en el fichero que
    existe justo para poder confiar en el."""
    import joblib
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path)
    (tmp_path / "staging").mkdir(exist_ok=True)
    cal._load_calibrator.cache_clear()
    joblib.dump(_ConstantCalibrator(),
                str(cal._model_path("liga_totals", "iso", staging=True)))
    cal._set_best_method("liga_totals", "isotonic", staging=True)

    out = cal.auto_promote_calibrators([{
        "league": "liga", "market": "totals", "persisted": True,
        "n_val": 500, "n_val_events": 200}])

    assert out["promoted"] == []
    registro = pd.read_csv(tmp_path / "promotion_log.csv")
    acciones = registro["action"].tolist()
    assert not any(a == "promoted" for a in acciones)
    assert any(str(a).startswith("rejected:") for a in acciones)
    assert any("colapsado" in str(a) for a in acciones)
