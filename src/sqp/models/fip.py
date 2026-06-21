"""FIP (Fielding Independent Pitching), per start.

FIP isolates what a pitcher controls (HR, BB, HBP, K) from defense and the
opponent's offense -- the exact confound that sank the v1 starter rating (which
used full-game runs allowed, mixing bullpen and opponent quality). Per-start FIP
feeds the same bounded StarterRatings, but as a fielding-independent signal.

    FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + C

C scales FIP onto the ERA scale; the bounded factor is a RATIO to the league
mean, so its exact value barely matters (it cancels to first order). Lower FIP =
better pitcher = suppresses the opponent's runs (factor < 1).
"""
from __future__ import annotations

FIP_CONSTANT = 3.10  # league-average scaling; ratings are relative, so insensitive


def innings_to_float(ip) -> float:
    """MLB innings-pitched notation to innings as a float: '5.2' -> 5 + 2/3,
    '6.0' -> 6.0. The decimal digit counts OUTS (0, 1 or 2), not tenths."""
    whole, _, frac = str(ip).partition(".")
    try:
        outs = {"0": 0, "1": 1, "2": 2}.get(frac, 0)
        return int(whole) + outs / 3.0
    except (ValueError, TypeError):
        return 0.0


def fip_from_line(hr: int, bb: int, hbp: int, k: int, ip,
                  constant: float = FIP_CONSTANT) -> float | None:
    """Per-start FIP from a boxscore pitching line. Returns None when the start
    has no recorded outs (IP=0), which cannot yield a rate."""
    ipf = innings_to_float(ip)
    if ipf <= 0:
        return None
    return (13 * hr + 3 * (bb + hbp) - 2 * k) / ipf + constant
