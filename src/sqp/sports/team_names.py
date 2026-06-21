"""Cross-vendor team-name normalization.

The Odds API, ESPN and the MLB Stats API spell the same team differently
("Man City" vs "Manchester City", accents, punctuation, casing). Elo ratings
are keyed by team identity, so without a single canonical key the ratings
built from results never bind to the live event names and no candidates are
produced. Two layers, neither of which INVENTS a team identity:

1. Deterministic key (`normalize_key`): strip accents, casefold, drop
   punctuation, collapse whitespace. Resolves the common spelling-only
   differences automatically.
2. Explicit alias map (configs/leagues/team_aliases.yaml): user-maintained,
   for genuinely different names. Ships EMPTY; scripts/audit_team_names.py
   surfaces unmatched names so you know exactly what to add.
"""
from __future__ import annotations
import unicodedata
from functools import lru_cache
from typing import Callable

from sqp.config import CONFIG_DIR, load_yaml

ALIASES_PATH = CONFIG_DIR / "leagues" / "team_aliases.yaml"


def normalize_key(name: str | None) -> str:
    """Deterministic identity key: accent-stripped, casefolded, punctuation
    removed, whitespace collapsed. Spelling-only differences collapse; distinct
    teams are NOT merged."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name))
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    kept = "".join(c.lower() if c.isalnum() else " " for c in ascii_only)
    return " ".join(kept.split())


@lru_cache(maxsize=None)
def _league_aliases(league: str) -> dict[str, str]:
    """variant_key -> canonical_key for one league (empty if none configured).
    Both sides are reduced to deterministic keys so the map is itself spelling
    insensitive.

    Cached for the lifetime of the process: the daily run is a fresh process so
    it always reads the current team_aliases.yaml, but a long-lived process will
    NOT see edits to the file. Call ``_league_aliases.cache_clear()`` after
    editing the aliases in-process (tests inject ``aliases=`` directly and so
    bypass this cache entirely)."""
    if not ALIASES_PATH.exists():
        return {}
    leagues = load_yaml(ALIASES_PATH).get("leagues") or {}
    raw = leagues.get(league) or {}
    return {normalize_key(variant): normalize_key(canonical)
            for variant, canonical in raw.items()}


class TeamNormalizer:
    """Callable mapping any vendor spelling of a team to one canonical key.

    `aliases` (variant_key -> canonical_key) is injectable for testing; when
    omitted it is loaded from configs/leagues/team_aliases.yaml for the league.
    """

    def __init__(self, league: str, aliases: dict[str, str] | None = None):
        self.league = league
        self._aliases = aliases if aliases is not None else _league_aliases(league)

    def __call__(self, name: str | None) -> str:
        key = normalize_key(name)
        return self._aliases.get(key, key)


def get_team_normalizer(league: str) -> Callable[[str | None], str]:
    return TeamNormalizer(league)
