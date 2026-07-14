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
    # Segundo pase pre-partido: re-valida los picks del dia contra el snapshot
    # recien capturado (sin cuota extra). Best-effort: nunca rompe la captura.
    if settings.revalidation_enabled:
        try:
            from sqp.pipeline.revalidation import revalidate_candidates
            rv = revalidate_candidates(
                ROOT / "data" / "predictions", ROOT,
                min_edge=settings.risk.min_edge,
                window_min=settings.revalidation_window_min,
                price_max_age_min=settings.revalidation_price_max_age_min)
            log.info("revalidation: evaluated=%d kept=%d revoked=%d "
                     "skipped_no_price=%d", rv["evaluated"], rv["kept"],
                     rv["revoked"], rv["skipped_no_price"])
            print(f"Revalidation: {rv['evaluated']} evaluated, "
                  f"{rv['kept']} kept, {rv['revoked']} revoked, "
                  f"{rv['skipped_no_price']} without fresh price")
        except Exception as exc:
            log.warning("revalidation pass failed (non-fatal): %s", exc)
        # Guard de abridores (informacion temprana, ligas de beisbol): revoca
        # picks cuyo abridor anunciado cambio o fue retirado. Statsapi es
        # gratis; solo eventos inminentes. Best-effort igual que el de precio.
        try:
            from sqp.pipeline.daily import _league_meta
            from sqp.pipeline.revalidation import revalidate_pitchers
            from sqp.providers.mlb_statsapi import MLBStatsProvider
            from sqp.sports.registry import get_adapter
            pred_dir = ROOT / "data" / "predictions"
            provider = None
            for cf in sorted(pred_dir.glob("candidates_*.csv")):
                lg = cf.stem.replace("candidates_", "")
                try:
                    meta = _league_meta(lg)
                except Exception:
                    continue
                if meta.get("family") != "baseball":
                    continue
                provider = provider or MLBStatsProvider()
                adapter = get_adapter(lg, "baseball", meta.get("league_params"))
                rp = revalidate_pitchers(
                    pred_dir, ROOT, lg,
                    fetch_probables=provider.fetch_probable_pitchers,
                    normalize=adapter.normalize,
                    window_min=settings.revalidation_window_min)
                if rp["checked"] or rp["revoked"] or rp["skipped_unmatched"]:
                    log.info("pitcher guard [%s]: checked=%d revoked=%d "
                             "unmatched=%d", lg, rp["checked"], rp["revoked"],
                             rp["skipped_unmatched"])
                    print(f"Pitcher guard [{lg}]: {rp['checked']} checked, "
                          f"{rp['revoked']} revoked, "
                          f"{rp['skipped_unmatched']} unmatched")
        except Exception as exc:
            log.warning("pitcher guard failed (non-fatal): %s", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
