"""Match NHL API game/team identities to the ESPN-sourced NHL results history
(`ResultsStore('nhl')`), for the goalie backfill
(`docs/research/2026-09-26-preregistro-portero-nhl.md`, section 3.2).

The pre-registro's stated approach is `sqp.sports.team_names.normalize_key`
plus `configs/leagues/team_aliases.yaml`, flagging four historical cases to
cover: Phoenix/Arizona/Utah, Atlanta Thrashers, Mighty Ducks of Anaheim,
Montreal with an accent. Empirically (live API calls, 2026-09-26) a STATIC
alias table cannot resolve the first case: the NHL API's team name for a game
is the era-correct short/common name ("Coyotes" for both a 2013 Phoenix game
and a 2021 Arizona game), while ESPN's own history spells the SAME franchise
differently across eras (`results_nhl.csv` has "Phoenix Coyotes" and "Arizona
Coyotes" as distinct literal strings). One static alias "Coyotes" -> X can
only be right for one era.

The generic rule used instead -- normalized exact match, or the NHL short
name is the trailing WHOLE WORD of the ESPN full name -- resolves every case
the pre-registro flags without inventing a per-team, per-era mapping:
  - "Coyotes" is the trailing word of both "Phoenix Coyotes" and
    "Arizona Coyotes"; the DATE disambiguates which one is in play.
  - "Ducks" is the trailing word of "Anaheim Ducks" AND "Anaheim Mighty
    Ducks" (verified: the NHL API already calls it "Ducks" even for a
    2005-10-08 game, while ESPN's history still says "Anaheim Mighty Ducks"
    for that season).
  - "Thrashers" / "Atlanta Thrashers": exact suffix.
  - "Utah Hockey Club" (2024-25) / "Mammoth" (2025-26 on) both match their
    respective ESPN rows ("Utah Hockey Club" is an exact match; "Mammoth" is
    the trailing word of "Utah Mammoth").
  - Accents are already folded by `normalize_key` (Montreal/Montréal).

`configs/leagues/team_aliases.yaml`'s (empty) nhl section is still consulted
first via `get_team_normalizer`, for a genuinely different ESPN spelling this
rule cannot cover. None is known as of 2026-09-26; this module does not
populate that file.
"""
from __future__ import annotations

from typing import Callable

from sqp.sports.team_names import get_team_normalizer


def _short_is_suffix(short_key: str, full_key: str) -> bool:
    """True if `short_key` equals `full_key`, or is its trailing WHOLE word."""
    if not short_key or not full_key:
        return False
    if short_key == full_key:
        return True
    return full_key.endswith(" " + short_key)


def build_results_index(results: list[dict]) -> dict[str, list[dict]]:
    """`date` (YYYY-MM-DD, ESPN's UTC day) -> the ESPN result rows on it.

    `results` is `ResultsStore(ROOT).load("nhl")` format: date/home/away/
    game_id/... dicts."""
    index: dict[str, list[dict]] = {}
    for r in results:
        index.setdefault(str(r.get("date", "")), []).append(r)
    return index


def match_espn_game(
    date_utc: str,
    home_name_nhl: str,
    away_name_nhl: str,
    index: dict[str, list[dict]],
    normalize: Callable[[str], str] | None = None,
) -> dict | None:
    """The single ESPN result row matching this NHL-API (date, home, away),
    or None if zero or more than one candidate matches (ambiguous -> left
    unmatched rather than guessed).

    `normalize` defaults to `get_team_normalizer("nhl")` (normalize_key +
    the nhl alias map); injectable for tests."""
    norm = normalize or get_team_normalizer("nhl")
    home_key = norm(home_name_nhl)
    away_key = norm(away_name_nhl)
    matches = []
    for r in index.get(date_utc, []):
        r_home = norm(str(r.get("home", "")))
        r_away = norm(str(r.get("away", "")))
        if _short_is_suffix(home_key, r_home) and _short_is_suffix(away_key, r_away):
            matches.append(r)
    if len(matches) == 1:
        row = matches[0]
        return {
            "espn_game_id": str(row.get("game_id") or ""),
            "home_espn": row.get("home"),
            "away_espn": row.get("away"),
        }
    return None
