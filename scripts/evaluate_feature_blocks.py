"""Offline exploratory feature ablations. Never promotes models."""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from sqp.config import ROOT
from sqp.evaluation.feature_blocks import evaluate_blocks
from sqp.evaluation.feature_shadow import fingerprint
from sqp.features.research import build_research_dataset
from sqp.pipeline.daily import _league_meta
from sqp.storage.atomic import atomic_write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leagues", nargs="+", required=True)
    parser.add_argument("--snapshots-dir", type=Path)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.folds < 2 or args.n_boot < 1 or args.window < 1:
        parser.error("require folds >= 2, n-boot >= 1, window >= 1")
    code_hash = fingerprint(ROOT)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    leagues = ([p.stem.removeprefix("results_") for p in sorted((ROOT / "data/historical").glob("results_*.csv"))]
               if args.leagues == ["all"] else args.leagues)
    if not leagues:
        parser.error("no local historical results found")
    reports, failed = [], False
    for league in leagues:
        try:
            meta = _league_meta(league)
            path = ROOT / "data/historical" / f"results_{league}.csv"
            raw = pd.read_csv(path, dtype={"game_id": str})
            fip_hash = snapshot_hash = None
            fip_path = path.with_name(f"starter_fip_{league}.csv")
            if meta["family"] == "baseball" and fip_path.exists():
                fips = pd.read_csv(fip_path, dtype={"game_id": str})
                cols = ["game_id", "date", "home_starter_fip", "away_starter_fip"]
                if fips.duplicated(["game_id", "date"]).any():
                    raise ValueError("duplicate FIP game/date")
                raw = raw.merge(fips[cols], on=["game_id", "date"], how="left", validate="one_to_one")
                fip_hash = hashlib.sha256(fip_path.read_bytes()).hexdigest()
            snapshots = None
            if args.snapshots_dir:
                sp = args.snapshots_dir / f"{league}.csv"
                if sp.exists():
                    snapshots = pd.read_csv(sp, dtype={"game_id": str})
                    snapshot_hash = hashlib.sha256(sp.read_bytes()).hexdigest()
            dataset = build_research_dataset(raw, league, meta["family"], meta.get("league_params"),
                                             snapshots=snapshots, window=args.window)
            report = evaluate_blocks(dataset, n_splits=args.folds, n_boot=args.n_boot, seed=args.seed)
            report.update(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          snapshot_sha256=snapshot_hash, fip_sha256=fip_hash, window=args.window)
            failed |= any(t["status"] != "MEASURED" for t in report["tasks"].values())
        except (ValueError, KeyError, FileNotFoundError) as exc:
            failed = True
            report = {"league": league, "status": "NOT_VERIFIABLE", "reason": str(exc)}
        reports.append(report)
        print(f"{league}: {report['status']}", flush=True)
    changed = code_hash != fingerprint(ROOT) or script_hash != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json({"schema_version": 1, "git_head": head.stdout.strip(),
                       "code_config_sha256": code_hash, "script_sha256": script_hash,
                       "code_changed_during_run": changed, "reports": reports,
                       "limitations": ["Exploratory only; no automatic promotion or market comparison",
                                       "Historical dates do not establish historical ingestion availability",
                                       "Selection across leagues requires independent forward validation"]}, args.out)
    return int(failed or changed)


if __name__ == "__main__":
    raise SystemExit(main())
