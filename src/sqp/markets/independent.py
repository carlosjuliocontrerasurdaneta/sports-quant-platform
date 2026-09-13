"""Post-freeze comparison against caller-supplied, timestamped quotes."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqp.markets.odds import is_usable_price
from sqp.markets.settlement_math import proportional_no_vig
from sqp.models.independent import FrozenScoreModel, finite_number, strict_fields, timestamp


def compare_quotes(
    model: FrozenScoreModel, payload: dict, *, max_age_minutes: float,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    event = model.spec["event"]
    if now.tzinfo is None or not timestamp(model.frozen_at) <= now < timestamp(event["starts_at"]):
        raise ValueError("market evaluation must be after freeze and before the event")
    finite_number(max_age_minutes, "max_age_minutes", positive=True)
    strict_fields(payload, {"schema_version", "quotes"})
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("unsupported quote schema_version")
    if not isinstance(payload["quotes"], list):
        raise ValueError("quotes must be a list")
    rows: list[dict] = []
    rejected: list[dict] = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for index, quote in enumerate(payload["quotes"]):
        try:
            strict_fields(quote, {"event_id", "period", "market", "side", "line", "price_decimal",
                                  "bookmaker", "timestamp", "source"})
            for key in ("event_id", "period", "market", "side", "bookmaker", "timestamp", "source"):
                if not isinstance(quote[key], str) or not quote[key].strip():
                    raise ValueError(f"{key} must be a non-empty string")
            if quote["event_id"] != event["event_id"] or quote["period"] != event["period"]:
                raise ValueError("event or settlement period does not match the frozen model")
            age = (now - timestamp(quote["timestamp"])).total_seconds() / 60
            if not 0 <= age <= max_age_minutes:
                raise ValueError("quote is future-dated or stale under the supplied age policy")
            price = finite_number(quote["price_decimal"], "price_decimal")
            if not is_usable_price(price):
                raise ValueError("decimal price must exceed one")
            line = quote["line"]
            if line is not None: line = finite_number(line, "line")
            p = model.price(quote["market"], quote["side"], line)
            row = {
                "quote_index": index, **quote, "model_id": model.model_id,
                "settlement": p.report(price), "raw_implied_probability": 1 / price,
                "market_no_vig_probability": None, "overround": None,
                "probability_edge_pp": None, "market_data_quality": "LOW",
                "no_vig_status": "INCOMPLETE", "stake": 0.0,
                "edge_basis": "stake_weighted_decision" if p.half_win or p.half_loss else "conditional_on_decision",
            }
            # Away handicap has the opposite sign to the home handicap. Totals
            # use the same line on both sides. Never mix books, times or sources.
            group_line = -line if quote["market"] == "spread" and quote["side"] == "away" and line is not None else line
            group_key = (quote["bookmaker"], quote["market"], group_line,
                         timestamp(quote["timestamp"]).isoformat(), quote["source"])
            groups[group_key].append(row)
            rows.append(row)
        except (ValueError, TypeError, KeyError) as exc:
            rejected.append({"quote_index": index, "reason": str(exc)})
    for group in groups.values():
        market = group[0]["market"]
        expected = {"home", "draw", "away"} if market == "moneyline_3way" else (
            {"over", "under"} if market == "total" else {"home", "away"})
        sides = [row["side"] for row in group]
        if len(sides) != len(set(sides)):
            for row in group: row["no_vig_status"] = "AMBIGUOUS_DUPLICATE"
            continue
        if set(sides) != expected:
            continue
        fair, hold = proportional_no_vig({r["side"]: r["price_decimal"] for r in group})
        for row in group:
            market_p = fair[row["side"]]
            model_p = row["settlement"]["decision_probability"]
            row.update({
                "market_no_vig_probability": market_p, "overround": hold,
                "probability_edge_pp": None if model_p is None else 100 * (model_p - market_p),
                "market_data_quality": "MEDIUM", "no_vig_status": "COMPLETE_MATCHED",
            })
    ranked = sorted(
        (r for r in rows if r["settlement"]["ev_per_unit"] > 0 and r["no_vig_status"] != "AMBIGUOUS_DUPLICATE"),
        key=lambda r: (-r["settlement"]["ev_per_unit"], r["quote_index"]),
    )
    return {
        "model_id": model.model_id, "evaluated_at": now.astimezone(timezone.utc).isoformat(),
        "quote_max_age_minutes": max_age_minutes, "quotes": rows, "rejected_quotes": rejected,
        "positive_ev_scenarios": [r["quote_index"] for r in ranked],
        "realized_clv": None, "stake": 0.0,
        "warning": "Offline scenarios using supplied prices, not independently verified executable betting opportunities.",
    }
