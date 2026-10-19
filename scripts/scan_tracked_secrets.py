"""Escanea los ficheros rastreados por git en busca de literales de credencial.

Auditoria audit-2026-10-18, AUD-006: el repositorio es PUBLICO y no habia
ninguna barrera de secretos antes de publicar. El hook `check-secrets.sh` es
PostToolUse (avisa despues de escribir) y solo cubre lo que toca Claude Code.
Este script es la capa del CI: reutiliza el mismo detector
(`.claude/hooks/_secret_literals.py`) sobre `git ls-files`, nunca imprime el
valor y sale con 1 si encuentra algo.

Uso: `python scripts/scan_tracked_secrets.py` (desde cualquier directorio).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
DETECTOR = ROOT / ".claude" / "hooks" / "_secret_literals.py"

# Mismas carpetas de datos que excluye `check-secrets.sh` (no se versionan, y
# si alguna lo estuviera no es texto escrito a mano).
_PREFIJOS_EXCLUIDOS = ("data/", "historical/", "exports/", "logs/")
# Fixtures DELIBERADOS del propio detector: literales falsos que sus tests
# necesitan para comprobar que se detectan. Lista cerrada, por ruta exacta.
_FIXTURES_DEL_DETECTOR = frozenset({"tests/test_audit_hooks.py"})


def _detector() -> ModuleType:
    spec = importlib.util.spec_from_file_location("secret_literals", DETECTOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {DETECTOR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rastreados(root: Path) -> list[str]:
    salida = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "-z"],
        cwd=root, capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    return [r for r in salida.split("\0") if r]


def hallazgos(root: Path) -> list[tuple[str, list[int]]]:
    detector = _detector()
    encontrados: list[tuple[str, list[int]]] = []
    for rel in _rastreados(root):
        if rel.startswith(_PREFIJOS_EXCLUIDOS) or rel in _FIXTURES_DEL_DETECTOR:
            continue
        ruta = root / rel
        try:
            datos = ruta.read_bytes()
        except OSError:
            continue
        if b"\0" in datos[:8192]:
            continue  # binario
        lineas = detector.suspicious_lines(datos.decode("utf-8", errors="replace"))
        if lineas:
            encontrados.append((rel, lineas))
    return encontrados


def main() -> int:
    encontrados = hallazgos(ROOT)
    for rel, lineas in encontrados:
        for n in lineas:
            print(f"{rel}:{n}: literal sospechoso [valor omitido]")
    if encontrados:
        print("Posible secreto en ficheros rastreados: usar variables de entorno.",
              file=sys.stderr)
        return 1
    print("Sin literales de credencial en los ficheros rastreados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
