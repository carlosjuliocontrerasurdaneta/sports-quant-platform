"""REG-001 y NEW-001 (verificacion independiente de audit-2026-11-03).

REG-002 (wait_for_clean_tree.ps1) se fija en tests/test_diario_espera_arbol.py.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from sqp.calibration import calibrator
from sqp.evaluation.tipster import tipster_table
from sqp.risk.prediction_gate import (PREDICTION_GATE_LATCH_LOG,
                                      _append_latch_log)
from sqp.storage.atomic import append_csv_log


# ---- REG-001 --------------------------------------------------------------
def _stream(**kw):
    base = {"league": "nba", "event_id": "e1", "home": "A", "away": "B",
            "start_time": "2026-11-04T01:00:00Z", "game_date": "2026-11-04",
            "market": "h2h", "selection": "A", "line": None,
            "price_decimal": 1.95, "calibrated_probability": 0.52,
            "estimated_probability": 0.52, "implied_probability_novig": 0.49,
            "books_count": 12, "adjusted_edge": 0.0035}
    base.update(kw)
    return pd.DataFrame([base])


def test_fila_accuracy_mode_no_se_declara_descartada_por_el_motor():
    t = tipster_table(_stream(flags="accuracy_mode"), min_edge=0.02)
    assert t.iloc[0]["tier"] != "NO BET"
    assert "motor de riesgo" not in t.iloc[0]["motivo"]
    assert "_accuracy_mode" not in t.columns


def test_marca_accuracy_entre_otras_marcas():
    t = tipster_table(_stream(flags="shadow;accuracy_mode"), min_edge=0.02)
    assert "motor de riesgo" not in t.iloc[0]["motivo"]


def test_fila_modo_edge_sigue_descartada_por_el_motor():
    for flags in (None, float("nan"), "", "shadow", "accuracy_modex"):
        t = tipster_table(_stream(flags=flags), min_edge=0.02)
        assert t.iloc[0]["tier"] == "NO BET", flags
        assert "motor de riesgo" in t.iloc[0]["motivo"], flags


def test_stream_mixto_con_indice_duplicado():
    df = pd.concat([_stream(flags="accuracy_mode"), _stream(flags="")])
    assert list(df.index) == [0, 0]
    t = tipster_table(df, min_edge=0.02)
    assert list(t["tier"] == "NO BET") == [False, True]


def test_ev_no_positivo_sigue_siendo_no_bet_en_accuracy():
    t = tipster_table(_stream(flags="accuracy_mode", calibrated_probability=0.45,
                              estimated_probability=0.45), min_edge=0.02)
    assert t.iloc[0]["tier"] == "NO BET"
    assert t.iloc[0]["motivo"] == "EV no positivo"


# ---- NEW-001 --------------------------------------------------------------
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _log_con_fila_rota(path: Path, n: int = 50) -> str:
    filas = "".join(f"2026-11-0{1 + i % 3},k{i},latch\n" for i in range(n))
    path.write_text("ts,key,action\n" + filas + 'x,"sin cerrar,1\n',
                    encoding="utf-8")
    return _sha(path)


def _apartados(path: Path) -> list[Path]:
    return sorted(path.parent.glob(f"{path.name}.corrupt.*"))


def test_append_csv_log_aparta_un_log_malformado_intacto(tmp_path):
    path = tmp_path / "log.csv"
    sha = _log_con_fila_rota(path)
    append_csv_log(pd.DataFrame([{"ts": "n", "key": "k", "action": "a"}]), path)
    [apartado] = _apartados(path)
    assert _sha(apartado) == sha  # historial preservado byte a byte
    assert len(pd.read_csv(path)) == 1


def test_append_csv_log_aparta_columnas_desplazadas(tmp_path):
    # pandas 3: si TODAS las filas traen un campo de mas no hay ParserError,
    # la primera columna pasa al indice.
    path = tmp_path / "log.csv"
    path.write_text("a,b\n1,2,3\n4,5,6\n", encoding="utf-8")
    sha = _sha(path)
    append_csv_log(pd.DataFrame([{"a": 9, "b": 9}]), path)
    [apartado] = _apartados(path)
    assert _sha(apartado) == sha
    assert pd.read_csv(path).to_dict("records") == [{"a": 9, "b": 9}]


def test_append_csv_log_une_columnas_y_conserva_filas(tmp_path):
    path = tmp_path / "log.csv"
    pd.DataFrame([{"a": 1}]).to_csv(path, index=False)
    append_csv_log(pd.DataFrame([{"a": 2, "b": "x"}]), path)
    out = pd.read_csv(path)
    assert list(out.columns) == ["a", "b"]
    assert out["a"].tolist() == [1, 2]
    assert not _apartados(path)


def test_append_csv_log_fichero_vacio_no_aparta(tmp_path):
    path = tmp_path / "log.csv"
    path.write_bytes(b"")
    append_csv_log(pd.DataFrame([{"a": 1}]), path)
    assert len(pd.read_csv(path)) == 1
    assert not _apartados(path)


def test_append_csv_log_sin_poder_apartar_no_reescribe(tmp_path, monkeypatch):
    path = tmp_path / "log.csv"
    sha = _log_con_fila_rota(path)

    def _falla(self, target):
        raise OSError("bloqueado")
    monkeypatch.setattr(Path, "rename", _falla)
    with pytest.raises(OSError):
        append_csv_log(pd.DataFrame([{"ts": "n"}]), path)
    assert _sha(path) == sha


def test_latch_log_del_gate_no_pierde_el_historial(tmp_path):
    path = tmp_path / PREDICTION_GATE_LATCH_LOG
    sha = _log_con_fila_rota(path)
    _append_latch_log([{"ts": "n", "key": "nba|h2h", "action": "latch"}],
                      tmp_path)
    [apartado] = _apartados(path)
    assert _sha(apartado) == sha
    assert len(pd.read_csv(path)) == 1


def test_promotion_log_del_calibrador_no_pierde_el_historial(tmp_path,
                                                            monkeypatch):
    monkeypatch.setattr(calibrator, "MODELS_DIR", tmp_path)
    path = tmp_path / "promotion_log.csv"
    sha = _log_con_fila_rota(path)
    calibrator._append_promotion_log([{"timestamp": "n", "key": "mlb_h2h",
                                       "action": "demoted"}])
    [apartado] = _apartados(path)
    assert _sha(apartado) == sha
    assert len(pd.read_csv(path)) == 1
