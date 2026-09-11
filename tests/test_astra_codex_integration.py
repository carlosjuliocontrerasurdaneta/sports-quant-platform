import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / "scripts" / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import codex_review  # noqa: E402


ATTESTED_PASS = """PASS

VERIFICATION: pytest -q -> passed; ruff check src scripts tests -> clean"""


def test_project_review_model_is_astra() -> None:
    config = tomllib.loads(
        (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    )

    assert config["review_model"] == "gpt-6-astra"


def test_cross_review_launcher_declares_astra() -> None:
    assert codex_review.ASTRA_MODEL == "gpt-6-astra"


def test_cross_review_launcher_passes_astra_to_codex_exec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        return subprocess.CompletedProcess(
            ["codex"], 0, ATTESTED_PASS, ""
        )

    monkeypatch.setattr(codex_review, "ROOT", tmp_path)
    monkeypatch.setattr(
        codex_review, "OUTPUT", tmp_path / "codex-review.md"
    )
    monkeypatch.setattr(
        codex_review, "codex_command", lambda: Path("codex")
    )
    monkeypatch.setattr(codex_review.subprocess, "run", fake_run)

    assert codex_review.main() == 0
    assert captured["args"] == [
        "codex",
        "exec",
        "--model",
        "gpt-6-astra",
        "-",
    ]


def test_hook_keeps_using_codex_review_so_review_model_applies() -> None:
    hook = (
        ROOT / ".claude" / "hooks" / "crossreview-on-stop.sh"
    ).read_text(encoding="utf-8")

    assert "codex review $alcance" in hook
    assert "--model" not in hook


def test_no_silent_fallback_model_is_encoded() -> None:
    source = (
        ROOT / "scripts" / "ai" / "codex_review.py"
    ).read_text(encoding="utf-8")
    config = (
        ROOT / ".codex" / "config.toml"
    ).read_text(encoding="utf-8")

    for weaker_or_legacy in (
        "gpt-5.6",
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.3",
        "gpt-5.2-codex",
        "codex-mini",
    ):
        assert weaker_or_legacy not in source
        assert weaker_or_legacy not in config
