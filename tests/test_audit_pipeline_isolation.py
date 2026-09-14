"""AUD-008: independent test roots cannot overwrite operator artifacts."""
import os
from pathlib import Path
import subprocess
import sys

from sqp import config
from sqp.pipeline import daily


def test_fixture_preserves_config_and_external_sentinels(tmp_path, isolated_pipeline_outputs):
    operator = tmp_path / "operator"
    sentinels = []
    for mode in ("demo", "live"):
        p = operator / mode / "predictions_nba.csv"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"operator data")
        sentinels.append(p)
    assert daily.ROOT == isolated_pipeline_outputs
    assert config.ROOT != isolated_pipeline_outputs
    daily._finalize("nba", [{"event_id": "fixture"}], [], mode="demo")
    assert (isolated_pipeline_outputs / "data/predictions/demo/predictions_nba.csv").exists()
    assert all(p.read_bytes() == b"operator data" for p in sentinels)


def test_concurrent_processes_publish_to_independent_roots(tmp_path):
    code = """
import sys
from pathlib import Path
from sqp.pipeline import daily
daily.ROOT = Path(sys.argv[1])
daily._finalize('nba', [{'event_id': sys.argv[2]}], [], mode='demo')
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    processes = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path / name), name],
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for name in ("first", "second")]
    for proc in processes:
        _, stderr = proc.communicate(timeout=30)
        assert proc.returncode == 0, stderr.decode(errors="replace")
    for name in ("first", "second"):
        text = (tmp_path / name / "data/predictions/demo/predictions_nba.csv").read_text()
        assert text.splitlines() == ["event_id", name]
