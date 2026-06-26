#!/usr/bin/env python
"""Capture a closing-line odds snapshot for leagues with imminent bet events.

Runs hourly (CAPTURE_CLOSE.bat). Spends API quota only on leagues that have open
candidates with a game commencing within the window. Bounded by a daily credit
cap and the monthly remaining-quota guard.

  python scripts/capture_closing_odds.py
  python scripts/capture_closing_odds.py --window-min 120 --max-credits 300
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.closing_capture import capture_closing

log = get_logger("sqp.capture_close")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-min", type=int, default=120)
    ap.add_argument("--max-credits", type=int,
                    default=int(os.getenv("MAX_CLOSING_CREDITS_DAY", "300")))
    args = ap.parse_args()
    settings = Settings.load()
    out = capture_closing(ROOT / "data" / "predictions", settings,
                          window_min=args.window_min, max_credits=args.max_credits)
    log.info("closing capture: captured=%s skipped_budget=%s credits_spent=%d",
             out["captured"], out["skipped_budget"], out["credits_spent"])
    print(f"Closing capture: {sum(out['captured'].values())} lines across "
          f"{len(out['captured'])} leagues; credits {out['credits_spent']}; "
          f"skipped(budget): {out['skipped_budget']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
