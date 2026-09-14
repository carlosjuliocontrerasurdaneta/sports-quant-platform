"""Value-scoped secret detection for check-secrets.sh; never echo values."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ASSIGNMENT = re.compile(
    r"(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*"
    r"\s*[=:]\s*(?:\"([^\"\r\n]{8,})\"|'([^'\r\n]{8,})'|([^\s\"';#]{8,}))",
    re.IGNORECASE,
)
PREFIXED = re.compile(r"sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE)
PLACEHOLDER = re.compile(
    r"os\.environ|getenv|dotenv|environ\.get|\$\{|\$env:|%[A-Za-z_]+%|"
    r"\bexample\b|placeholder|changeme|dummy|your_|xxx|<[A-Za-z_]+>|TU_[A-Za-z_]+",
    re.IGNORECASE,
)


def suspicious_lines(text: str) -> list[int]:
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        values = [next(v for v in match.groups() if v is not None)
                  for match in ASSIGNMENT.finditer(line)]
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
