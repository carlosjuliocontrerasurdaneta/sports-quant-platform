#!/usr/bin/env python
"""Train isolated candidates; capture local pregame fixtures; evaluate at fixed end."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from threadpoolctl import threadpool_limits

from sqp.config import ROOT
from sqp.evaluation.feature_shadow import (capture, capture_store, evaluate, load_protocol,
                                          train, utc_now)
from sqp.storage.atomic import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    tr = sub.add_parser("train")
    tr.add_argument("--manifest", type=Path, required=True)
    tr.add_argument("--report", type=Path, required=True)
    tr.add_argument("--out", type=Path, required=True)
    tr.add_argument("--start", required=True)
    tr.add_argument("--end", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("--experiment", type=Path, required=True)
    cap.add_argument("--fixtures", type=Path)
    watch = sub.add_parser("watch")
    watch.add_argument("--experiment", type=Path, required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--experiment", type=Path, required=True)
    ev.add_argument("--outcomes", type=Path, required=True)
    ev.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Avoid BLAS oversubscription; the experiment is low-priority shadow work.
    with threadpool_limits(limits=1):
        if args.command == "train":
            result = train(args.data_root, args.manifest, args.report, args.out, args.start, args.end)
            print(f"Frozen protocol: {args.out / 'protocol.json'}; {len(result['candidates'])} pairs")
        elif args.command == "capture":
            result = (capture(args.data_root, args.experiment, args.fixtures) if args.fixtures
                      else capture_store(args.data_root, args.experiment))
            print(json.dumps(result))
        elif args.command == "evaluate":
            result = evaluate(args.data_root, args.experiment, args.outcomes)
            with args.out.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, allow_nan=False)
                stream.write("\n")
        else:
            protocol = load_protocol(args.data_root, args.experiment)
            lock = args.experiment / "worker.lock"
            with lock.open("x", encoding="ascii") as stream:
                stream.write(str(os.getpid()))
            try:
                previous_signature = None
                while utc_now() < pd.Timestamp(protocol["end_exclusive"]):
                    if (args.experiment / "STOP").exists():
                        break
                    signature = [(str(f), f.stat().st_mtime_ns, f.stat().st_size)
                                 for f in sorted((args.data_root / "data/odds").glob("odds_*.csv"))]
                    if signature != previous_signature:
                        result = capture_store(args.data_root, args.experiment)
                        previous_signature = signature
                    else:
                        result = {"n_predictions": 0, "reason": "local odds files unchanged"}
                    atomic_write_json({"at": utc_now().isoformat(), "pid": os.getpid(),
                                       "status": "RUNNING", "last_capture": result}, args.experiment / "heartbeat.json")
                    time.sleep(60)
                atomic_write_json({"at": utc_now().isoformat(), "status": "STOPPED"}, args.experiment / "heartbeat.json")
            except Exception as exc:
                atomic_write_json({"at": utc_now().isoformat(), "status": "ERROR", "error": str(exc)},
                                  args.experiment / "heartbeat.json")
                raise
            finally:
                lock.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
