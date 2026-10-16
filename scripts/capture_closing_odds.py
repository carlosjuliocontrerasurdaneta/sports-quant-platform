#!/usr/bin/env python
"""Capture a closing-line odds snapshot for leagues with imminent bet events.

Runs every 30 min (CAPTURE_CLOSE.bat, SQP_Capture_Close_Cdev PT30M; el docstring
decia "hourly" hasta el 2026-09-13, AUD-LOW-004). Spends API quota only on leagues that have open
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
from sqp.pipeline.closing_capture import all_leagues_failed, capture_closing

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
    failures: list[str] = []  # AUD-004: etapas fallidas -> rc=1 al final
    if all_leagues_failed(out):
        failures.append("closing capture: fallaron TODAS las ligas intentadas "
                        f"{out['failed_leagues']}")
    elif out.get("failed_leagues"):
        log.warning("closing capture: ligas fallidas (parcial): %s",
                    out["failed_leagues"])
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
            log.error("revalidation pass failed: %s", exc)
            failures.append(f"revalidation: {type(exc).__name__}: {exc}")
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
            log.error("pitcher guard failed: %s", exc)
            failures.append(f"pitcher guard: {type(exc).__name__}: {exc}")
    # Observatorio de edge intradia: re-evalua el edge h2h de lo SERVIDO a las
    # 11:00 contra el consenso recien capturado y lo loguea (medicion pura,
    # sin picks ni stakes; decide la fase ofensiva #4 con datos). Best-effort
    # DOCUMENTADO: no protege ninguna decision ni stake, asi que su fallo sigue
    # siendo warning y NO cambia el rc (AUD-004).
    if settings.intraday_scan_enabled:
        try:
            from sqp.pipeline.intraday_scan import log_intraday_edges
            sc = log_intraday_edges(
                ROOT / "data" / "predictions", ROOT,
                min_edge=settings.risk.min_edge,
                window_min=settings.revalidation_window_min,
                price_max_age_min=settings.revalidation_price_max_age_min)
            log.info("intraday scan: scanned=%d would_generate=%d leagues=%s",
                     sc["scanned"], sc["would_generate"], sc["leagues"])
            print(f"Intraday scan: {sc['scanned']} h2h sides evaluated, "
                  f"{sc['would_generate']} above min_edge")
        except Exception as exc:
            log.warning("intraday scan failed (non-fatal): %s", exc)
    if failures:
        # Todos los pasos ya se ejecutaron; rc!=0 hace que CAPTURE_CLOSE.bat
        # registre el fallo del centinela en vez de limpiarlo.
        for f in failures:
            log.error("FALLO: %s", f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
