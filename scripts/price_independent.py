"""Freeze an offline sporting model before opening the optional market file.

No network, credentials, bankroll, production CSV or scheduler access.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.markets.independent import compare_quotes
from sqp.models.independent import freeze_model, timestamp


def _load(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError(f"non-finite JSON value: {value}")

    with path.open(encoding="utf-8") as handle:
        result = json.load(handle, object_pairs_hook=pairs, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("input must be a JSON object")
    return result


def _save_new(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(encoded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--quotes", type=Path)
    parser.add_argument("--output-dir", type=Path,
                        help="new audit directory; defaults to a unique directory under outputs/")
    parser.add_argument("--max-quote-age-min", type=float,
                        help="required with quotes; e.g. 90 to match the current production age policy")
    parser.add_argument("--as-of", help="fixed clock for demo_synthetic only, never user_supplied")
    args = parser.parse_args(argv)
    try:
        if args.quotes and args.max_quote_age_min is None:
            raise ValueError("--max-quote-age-min is required with --quotes")
        spec = _load(args.model)
        if args.as_of and spec.get("data_label") != "demo_synthetic":
            raise ValueError("--as-of is allowed only for explicitly synthetic demonstrations")
        now = timestamp(args.as_of) if args.as_of else datetime.now(timezone.utc)
        model = freeze_model(spec, now=now)
        output_dir = args.output_dir or Path("outputs") / datetime.now(timezone.utc).strftime("independent-%Y%m%dT%H%M%S%fZ")
        # Exclusive create prevents accidentally replacing a prior audit run.
        output_dir.mkdir(parents=True, exist_ok=False)
        frozen = model.report()
        _save_new(output_dir / "model_freeze.json", frozen)
        # The first access to market content is physically AFTER persisted freeze.
        market = None
        if args.quotes:
            market = compare_quotes(model, _load(args.quotes), max_age_minutes=args.max_quote_age_min,
                                    now=now if args.as_of else datetime.now(timezone.utc))
        _save_new(output_dir / "report.json", {"model": frozen, "market": market})
        print(f"MODEL_FREEZE {model.model_id}\nReport: {output_dir / 'report.json'}")
        return 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"NOT PRICED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
