"""Opt-in offline model freeze; never imports odds providers, risk or live state.

Inputs are externally estimated sporting parameters, NOT trained here. A freeze
proves which inputs this engine used; it cannot certify their upstream origin.
Count models price regulation three-way moneylines. No OT/tie redistribution is
invented. Normal moneylines explicitly assume a two-way, no-draw settlement.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from scipy.stats import norm

from sqp.markets.settlement_math import (
    SettlementProbabilities, combine_adjacent_lines, split_asian_line,
)
from sqp.models.distributions import _dixon_coles_tau, score_pmf


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("timestamp must be ISO 8601 with a timezone") from exc
    if result.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def strict_fields(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        raise ValueError(f"invalid fields: missing={sorted(missing)}, unexpected={sorted(extra)}")


def finite_number(value: Any, name: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class FrozenScoreModel:
    model_id: str
    frozen_at: str
    _spec_json: str = field(repr=False)
    _grid_bytes: bytes = field(repr=False)
    retained_mass: float

    @property
    def spec(self) -> dict:
        # Never expose a mutable reference into the frozen model.
        return json.loads(self._spec_json)

    def price(self, market: str, side: str, line: float | None = None) -> SettlementProbabilities:
        dist = self.spec["distribution"]
        kind = dist["kind"]
        if market in {"moneyline_2way", "moneyline_3way"}:
            if line is not None:
                raise ValueError("moneyline has no line")
            if market == "moneyline_2way" and kind == "normal":
                if side not in {"home", "away"}:
                    raise ValueError("two-way moneyline side must be home or away")
                p = float(norm.sf(0, dist["expected_home"] - dist["expected_away"], dist["margin_sigma"]))
                if side == "away": p = 1 - p
            elif market == "moneyline_3way" and kind == "count":
                grid = self._grid()
                home, away = np.indices(grid.shape)
                masks = {"home": home > away, "draw": home == away, "away": home < away}
                if side not in masks:
                    raise ValueError("three-way moneyline side must be home, draw or away")
                p = float(grid[masks[side]].sum())
            else:
                raise ValueError("unsupported moneyline convention; no OT/tie model is inferred")
            return SettlementProbabilities(full_win=p, full_loss=1 - p)
        if market not in {"spread", "total"} or line is None:
            raise ValueError("spread/total requires a line")
        if side not in ({"home", "away"} if market == "spread" else {"over", "under"}):
            raise ValueError("side is incompatible with market")
        first, second = split_asian_line(line)
        return combine_adjacent_lines(
            self._single_line(market, side, first), self._single_line(market, side, second),
        )

    def _grid(self) -> np.ndarray:
        size = self.spec["distribution"].get("max_score", 60) + 1
        return np.frombuffer(self._grid_bytes, dtype=np.float64).reshape(size, size)

    def _single_line(self, market: str, side: str, line: float) -> tuple[float, float, float]:
        d = self.spec["distribution"]
        if d["kind"] == "count":
            grid = self._grid()
            home, away = np.indices(grid.shape)
            score = home - away if market == "spread" else home + away
            if market == "spread":
                value = (score if side == "home" else -score) + line
            else:
                value = score - line if side == "over" else line - score
            return float(grid[value > 0].sum()), float(grid[value == 0].sum()), float(grid[value < 0].sum())
        if market == "spread":
            mean = d["expected_home"] - d["expected_away"]
            if side == "away": mean = -mean
            sigma, threshold = d["margin_sigma"], -line
        else:
            mean = d["expected_home"] + d["expected_away"]
            sigma, threshold = d["total_sigma"], line
        delta = 0.5 if float(threshold).is_integer() else 0.0
        win = float(norm.sf(threshold + delta, mean, sigma))
        loss = float(norm.cdf(threshold - delta, mean, sigma))
        push = max(0.0, 1.0 - win - loss) if delta else 0.0
        return (loss, push, win) if market == "total" and side == "under" else (win, push, loss)

    def report(self) -> dict:
        spec = self.spec
        count = spec["distribution"]["kind"] == "count"
        market = "moneyline_3way" if count else "moneyline_2way"
        sides = ["home", "draw", "away"] if count else ["home", "away"]
        return {
            "schema_version": 1, "model_id": self.model_id, "model_freeze": True,
            "frozen_at": self.frozen_at, "input": spec, "retained_grid_mass": self.retained_mass,
            "model_mode": "ANALYTIC_OFFLINE", "model_confidence": "UNVALIDATED",
            "market_used_by_this_engine_to_generate_model": False,
            "moneyline_convention": market,
            "moneyline": {side: self.price(market, side).report() for side in sides},
            "limitations": [
                "Sporting inputs supplied by caller; upstream provenance is not independently verified.",
                "No historical calibration or predictive advantage established by this run.",
                "Count model has independent marginals plus optional Dixon-Coles; no OT/empty-net model."
                if count else "Normal margin/total approximation; integer pushes use continuity correction; no joint-score simulation.",
                "No bet sizing, no production ledger writes, no realized CLV.",
            ],
        }


def freeze_model(spec: dict, *, now: datetime | None = None) -> FrozenScoreModel:
    """Validate and freeze before the caller opens any market file."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    strict_fields(spec, {"schema_version", "event", "sporting_as_of", "model_version",
                         "data_label", "sources", "distribution"})
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1:
        raise ValueError("unsupported schema_version")
    if type(spec["model_version"]) is not int or spec["model_version"] < 1:
        raise ValueError("model_version must be a positive integer")
    if spec["data_label"] not in {"demo_synthetic", "user_supplied"}:
        raise ValueError("data_label must be demo_synthetic or user_supplied")
    event = spec["event"]
    strict_fields(event, {"event_id", "league", "home", "away", "starts_at", "period"})
    if any(not isinstance(v, str) or not v.strip() for v in event.values()):
        raise ValueError("event values must be non-empty strings")
    if event["home"] == event["away"]:
        raise ValueError("home and away must differ")
    if event["period"] not in {"regulation", "full_game"}:
        raise ValueError("period must be regulation or full_game")
    starts = timestamp(event["starts_at"])
    cutoff = timestamp(spec["sporting_as_of"])
    if not cutoff <= now < starts:
        raise ValueError("pregame invariant requires sporting_as_of <= now < starts_at")
    if not isinstance(spec["sources"], list) or not spec["sources"]:
        raise ValueError("at least one sporting source is required")
    for source in spec["sources"]:
        strict_fields(source, {"source", "as_of"})
        if not isinstance(source["source"], str) or not source["source"].strip():
            raise ValueError("source must be a non-empty identifier")
        if timestamp(source["as_of"]) > cutoff:
            raise ValueError("source contains information after sporting_as_of")
    d = spec["distribution"]
    base = {"kind", "expected_home", "expected_away"}
    if not isinstance(d, dict) or d.get("kind") not in {"normal", "count"}:
        raise ValueError("distribution kind must be normal or count")
    for key in ("expected_home", "expected_away"):
        if finite_number(d.get(key), key) < 0:
            raise ValueError("expected scores cannot be negative")
    finite_number(d["expected_home"] + d["expected_away"], "expected_total")
    grid_bytes, retained = b"", 1.0
    if d["kind"] == "normal":
        strict_fields(d, base | {"margin_sigma", "total_sigma"})
        for key in ("margin_sigma", "total_sigma"):
            finite_number(d[key], key, positive=True)
    else:
        strict_fields(d, base, {"max_score", "dispersion_k", "dc_rho", "max_tail_mass"})
        if event["period"] != "regulation":
            raise ValueError("count model supports regulation only; no overtime model supplied")
        maximum = d.get("max_score", 60)
        if type(maximum) is not int or not 1 <= maximum <= 512:
            raise ValueError("max_score must be an integer in [1,512] (resource bound)")
        k = d.get("dispersion_k")
        if k is not None: finite_number(k, "dispersion_k", positive=True)
        rho = finite_number(d.get("dc_rho", 0), "dc_rho")
        tolerance = finite_number(d.get("max_tail_mass", 1e-6), "max_tail_mass", positive=True)
        if tolerance >= 1:
            raise ValueError("max_tail_mass must be below one")
        ph = score_pmf(d["expected_home"], maximum, k)
        pa = score_pmf(d["expected_away"], maximum, k)
        grid = np.outer(ph, pa)
        retained = float(grid.sum())
        if retained <= 0 or 1 - retained > tolerance:
            raise ValueError("truncated grid exceeds max_tail_mass; increase max_score")
        for i in (0, 1):
            for j in (0, 1):
                tau = _dixon_coles_tau(i, j, d["expected_home"], d["expected_away"], rho)
                if not math.isfinite(tau) or tau < 0:
                    raise ValueError("Dixon-Coles correction would produce negative/invalid mass")
                grid[i, j] *= tau
        mass = float(grid.sum())
        if not math.isfinite(mass) or mass <= 0:
            raise ValueError("score grid has no positive finite mass")
        grid_bytes = (grid / mass).astype(np.float64).tobytes()
    encoded = canonical_json(spec)
    frozen_at = now.astimezone(timezone.utc).isoformat()
    fingerprint = hashlib.sha256(("independent-v1\n" + frozen_at + "\n" + encoded).encode() + grid_bytes).hexdigest()
    return FrozenScoreModel(fingerprint, frozen_at, encoded, grid_bytes, retained)
