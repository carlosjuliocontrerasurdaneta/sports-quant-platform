"""Segundo pase pre-partido (sqp.pipeline.revalidation): re-valida el edge de
los picks del dia contra el consenso vigente cerca del comienzo y revoca los
que ya no se generarian (edge < min_edge al precio actual). Bajo shadow es
medicion pura: revocado vs mantenido se compara luego en CLV/ROI."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

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
