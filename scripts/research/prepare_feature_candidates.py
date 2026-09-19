"""Draft candidate selection from exploratory evidence; never promotes models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def prepare(report: dict, report_hash: str) -> dict:
    if report.get("code_changed_during_run") is not False:
        raise ValueError("report must have an unchanged code fingerprint")
    candidates, deferred = [], []
    for league in report["reports"]:
        for target, task in league.get("tasks", {}).items():
            if task["status"] != "MEASURED":
                continue
            for score in task["scores"]:
                block = score["variant"]
                if block not in {"schedule", "opponent_form", "venue_form", "pitching", "sporting"} or not score["delta_hi"] < 0:
                    continue
                entry = {"id": f"{league['league']}/{target}/{block}", "league": league["league"],
                         "target": target, "block": block, "metric": task["metric"], "discovery_score": score,
                         "discovery_through": max(f["test_end"] for f in task["folds"]),
                         "source_sha256": league["source_sha256"], "window": league["window"],
                         "status": "AWAITING_FORWARD_PROTOCOL"}
                if league["family"] == "tennis" and block == "venue_form":
                    entry["status"] = "DEFERRED_PROVIDER_ORIENTATION_AUDIT"
                    deferred.append(entry)
                else:
                    candidates.append(entry)
    return {"schema_version": 1, "status": "DRAFT_NOT_PREREGISTERED",
            "discovery_report_sha256": report_hash, "discovery_code_config_sha256": report["code_config_sha256"],
            "candidates": candidates, "deferred": deferred,
            "forward_protocol": {"start": None, "end": None, "sample_size_or_power": None,
                                 "promotion": False, "selection": "Requires independent forward confirmation"}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    result = prepare(json.loads(raw), hashlib.sha256(raw).hexdigest())
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(f"{len(result['candidates'])} candidates; {len(result['deferred'])} deferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
