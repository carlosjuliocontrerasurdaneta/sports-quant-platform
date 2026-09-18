"""Value-scoped secret detection for check-secrets.sh; never echo values."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ASSIGNMENT = re.compile(
    r"(?P<name>(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*)"
    r"[\"']?\s*[=:]\s*(?:\"([^\"\r\n]{8,})\"|'([^'\r\n]{8,})'|([^\s\"';#]{8,}))",
    re.IGNORECASE,
)
PREFIXED = re.compile(r"sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE)
PLACEHOLDER = re.compile(
    r"os\.environ|getenv|dotenv|environ\.get|\$\{|\$env:|%[A-Za-z_]+%|"
    r"\bexample\b|placeholder|changeme|dummy|your_|xxx|<[A-Za-z_]+>|TU_[A-Za-z_]+",
    re.IGNORECASE,
)
# Secuencias de escape LITERALES (`\r`, `\n`, `\t`) que aparecen cuando la linea
# es codigo fuente citado dentro de una cadena JSON/Python: cortan el valor.
_ESCAPE = re.compile(r"\\[rnt]")


def _symbolic(name: str, value: str, quoted: bool) -> bool:
    """True si el "valor" no es un literal sino una referencia simbolica.

    AUD-007 (ronda audit-2026-09-18): una asignacion reflexiva del cliente de
    cuotas (atributo = parametro homonimo) citada como codigo fuente dentro de
    un EVIDENCE.json, con CRLF escapado detras, se marcaba como secreto en cada
    comando de la sesion. Una asignacion reflexiva (`x = x`, `self.x = x`,
    `cfg.x = settings.x`) o una llamada (`x = leer(ruta)`) no puede ser un
    literal filtrado; un literal REAL sin comillas (estilo `set NOMBRE=valor`)
    sigue detectandose porque no termina en el nombre asignado ni contiene una
    llamada.
    """
    value = _ESCAPE.split(value, 1)[0]
    if not value:
        return True
    lowered, target = value.lower(), name.lower()
    if lowered == target or (not quoted and lowered.endswith(target)):
        return True
    return not quoted and "(" in value


def suspicious_lines(text: str) -> list[int]:
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        values = []
        for match in ASSIGNMENT.finditer(line):
            groups = match.groups()[1:]
            quoted = groups[0] is not None or groups[1] is not None
            value = next(v for v in groups if v is not None)
            if _symbolic(match.group("name"), value, quoted):
                continue
            values.append(value)
        values.extend(match.group() for match in PREFIXED.finditer(line))
        if any(not PLACEHOLDER.search(value) for value in values):
            found.append(number)
    return found


if __name__ == "__main__":
    try:
        content = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        sys.exit(0)
    for number in suspicious_lines(content):
        print(f"{number}: literal sospechoso [valor omitido]")
