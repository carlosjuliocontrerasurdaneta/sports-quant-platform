"""On-disk TTL cache for The Odds API responses (credit-saving).

Keyed by endpoint + query params (api key excluded). A re-run within the TTL is
served from disk and costs no credits. Used only for the paid endpoints
(/odds, /scores, /historical); the free /sports list is never cached so the
live quota header stays fresh for the budget guard.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class FileCache:
    def __init__(self, cache_dir: Path):
        self.dir = cache_dir

    @staticmethod
    def key(path: str, params: dict) -> str:
        norm = "&".join(f"{k}={params[k]}" for k in sorted(params) if k != "apiKey")
        # Content-addressing only, never a signature or credential hash. Marking
        # that intent explicitly avoids treating this cache key as cryptography.
        return hashlib.sha1(
            f"{path}?{norm}".encode("utf-8"), usedforsecurity=False
        ).hexdigest()

    def _file(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str, ttl: float):
        """Return cached payload if present and younger than ttl (ttl=inf = any age)."""
        f = self._file(key)
        if not f.exists():
            return None
        # `>=`, no `>`: "younger than ttl" es age < ttl, asi que una entrada con
        # age == ttl ya caduco. Con `>` un ttl=0 servia la entrada si el archivo
        # se habia escrito en el mismo tick del reloj (age 0.0), lo que rompia la
        # pata Windows del CI de forma intermitente segun la granularidad de
        # mtime del runner (auditoria 2026-08-05).
        if ttl != float("inf") and (time.time() - f.stat().st_mtime) >= ttl:
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    def put(self, key: str, data) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            self._file(key).write_text(json.dumps(data), encoding="utf-8")
        except (TypeError, OSError):
            pass  # cache write is best-effort; never break a live fetch over it
