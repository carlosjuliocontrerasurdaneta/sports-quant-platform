"""Portable, isolated installation. Never creates .env or runs production jobs."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def environment_python(root: Path, *, windows: bool | None = None) -> Path:
    windows = os.name == "nt" if windows is None else windows
    return root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")


def verification_commands(root: Path, python: Path) -> list[list[str]]:
    temporary = root / ".codex-tmp" / f"install-{uuid.uuid4().hex}"
    return [
        [str(python), "-m", "pip", "check"],
        [str(python), "-m", "ruff", "check", "src", "scripts", "tests"],
        [str(python), "-m", "mypy", "src", "--cache-dir", str(root / ".codex-tmp" / "mypy")],
        [str(python), "-m", "pytest", "-q", "-ra", "-p", "no:cacheprovider", f"--basetemp={temporary}"],
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="run full offline tests after installation")
    parser.add_argument("--check-only", action="store_true", help="validate an existing .venv; no installation")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        print("Python 3.11+ is required (this bundle was tested on 3.12).", file=sys.stderr)
        return 2
    python = environment_python(ROOT)
    try:
        if args.check_only:
            if not python.is_file():
                raise ValueError("No .venv found. Run setup_local.py --verify first.")
        else:
            target = ROOT / ".venv"
            if target.exists() and not (target / "pyvenv.cfg").is_file():
                raise ValueError("Existing .venv is not a virtual environment; refusing to overwrite it.")
            if not target.exists():
                venv.EnvBuilder(with_pip=True).create(target)
            subprocess.run([str(python), "-m", "pip", "install", "-e", ".[dev]", "-c", "requirements.lock"],
                           cwd=ROOT, check=True)
        if args.verify or args.check_only:
            (ROOT / ".codex-tmp").mkdir(exist_ok=True)
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            for command in verification_commands(ROOT, python):
                print("VALIDATE:", " ".join(command), flush=True)
                subprocess.run(command, cwd=ROOT, env=env, check=True)
        print("READY: isolated environment prepared. No credentials, bankroll or live jobs changed.")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"SETUP FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
