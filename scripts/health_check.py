#!/usr/bin/env python
"""Print the pipeline health report (data + feature + model artifacts).

Exits 0 on OK/WARN (warnings must not fail the daily pipeline) and 1 on ERROR
(missing artifacts), so BAT guards like REFRESH_ML.bat's `if errorlevel 1` are
operative (audit 2026-07-24, M-1). Use data/output/pipeline_health.json for
automation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.monitoring.health import generate_health_report


def main() -> int:
    r = generate_health_report()
    print(f"Pipeline health: {r['status']}")
    for lg, info in r["leagues"].items():
        print(f"  {lg:<4} results={info['results_rows']} features={info['features_rows']} "
              f"moneyline_model={info['moneyline_model']} calibration={info['calibration']}")
    for e in r.get("errors", []):
        print(f"  [ERROR] {e}")
    for w in r["warnings"]:
        print(f"  [WARN] {w}")
    return 1 if r["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
