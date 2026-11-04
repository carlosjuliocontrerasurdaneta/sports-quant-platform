"""AUD-017: lectores JSON con raiz no valida fallan de forma controlada."""
from __future__ import annotations

import json

import pytest

from sqp.evaluation import feature_shadow as shadow
from sqp.models import ml_train
from sqp.storage import feature_store as fs

RAICES = ["[]", "{}", "null", "1", '"x"']


@pytest.mark.parametrize("raw", ["{}", "null", "1", '"x"'])
def test_ml_train_register_raiz_no_lista_se_respalda(tmp_path, raw):
    reg = tmp_path / "data" / "models" / "registry.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(raw, encoding="utf-8")
    ml_train._register(tmp_path, {"sport": "nba"})
    assert json.loads(reg.read_text(encoding="utf-8")) == [{"sport": "nba"}]
    assert len(list(reg.parent.glob("registry.json.corrupt-*"))) == 1


@pytest.mark.parametrize("raw", ["[]", "null", "1", '"x"'])
def test_feature_store_manifest_raiz_no_objeto_es_caducado(tmp_path, raw):
    feat, man = fs._feature_path(tmp_path, "nba"), fs._manifest_path(tmp_path, "nba")
    feat.parent.mkdir(parents=True, exist_ok=True)
    man.parent.mkdir(parents=True, exist_ok=True)
    feat.write_text("a\n1\n", encoding="utf-8")
    man.write_text(raw, encoding="utf-8")
    assert fs.dataset_is_current(tmp_path, "nba") is False


@pytest.mark.parametrize("raw", ["[]", "{}", "null", '{"protocol_sha256": "x"}'])
def test_feature_shadow_captured_rows_payload_invalido(tmp_path, raw):
    (tmp_path / "protocol.json").write_text("{}")
    folder = tmp_path / "captures" / "batch_a"
    folder.mkdir(parents=True)
    (folder / "predictions.json").write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="malformed capture archive"):
        shadow.captured_rows(tmp_path)
