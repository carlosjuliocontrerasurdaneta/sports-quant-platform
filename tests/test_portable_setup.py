import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _setup():
    spec = importlib.util.spec_from_file_location("setup_local_test", ROOT / "scripts/setup_local.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interpreter_is_portable_and_local(tmp_path):
    setup = _setup()
    assert setup.environment_python(tmp_path, windows=True) == tmp_path / ".venv/Scripts/python.exe"
    assert setup.environment_python(tmp_path, windows=False) == tmp_path / ".venv/bin/python"


def test_validation_is_offline_and_uses_isolated_temp_dir(tmp_path):
    setup = _setup()
    python = setup.environment_python(tmp_path)
    commands = setup.verification_commands(tmp_path, python)
    assert [cmd[2] for cmd in commands] == ["pip", "ruff", "mypy", "pytest"]
    assert all(cmd[0] == str(python) for cmd in commands)
    assert str(tmp_path / ".codex-tmp") in commands[-1][-1]
    assert "--mode" not in str(commands) and "install" not in commands[0]


def test_installer_check_only_does_not_install_or_change_credentials(tmp_path, monkeypatch):
    setup = _setup()
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    python = setup.environment_python(tmp_path)
    python.parent.mkdir(parents=True)
    python.touch()
    secret = tmp_path / ".env"
    secret.write_text("UNCHANGED=test-fixture")
    commands = []
    monkeypatch.setattr(setup.subprocess, "run", lambda command, **kwargs: commands.append(command))
    assert setup.main(["--check-only"]) == 0
    assert len(commands) == 4
    assert all("install" not in cmd for cmd in commands)
    assert secret.read_text() == "UNCHANGED=test-fixture"


def test_setup_refuses_to_replace_unrelated_directory(tmp_path, monkeypatch):
    setup = _setup()
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/user-file").write_text("keep")
    assert setup.main([]) == 1
    assert (tmp_path / ".venv/user-file").read_text() == "keep"


def test_windows_launchers_do_not_schedule_or_launch_live_jobs():
    install = (ROOT / "INSTALL_LOCAL.bat").read_text()
    demo = (ROOT / "DEMO_INDEPENDENT.bat").read_text()
    assert 'cd /d "%~dp0"' in install and 'cd /d "%~dp0"' in demo
    assert "setup_local.py --verify" in install
    assert '.venv\\Scripts\\python.exe' in demo
    for text in (install, demo):
        assert "Richard" not in text and "schtasks" not in text and "--mode live" not in text
