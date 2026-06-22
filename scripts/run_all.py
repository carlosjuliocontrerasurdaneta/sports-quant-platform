#!/usr/bin/env python
"""Daily multi-league run: auto-detect in-season leagues, run only as many as the
quota budget allows (priority order), then write the consolidated picks report.

  python scripts/run_all.py                  # live, budget-guarded
  python scripts/run_all.py --max-leagues 6  # extra hard cap on leagues/day
  python scripts/run_all.py --mode demo      # all supported leagues, synthetic

The guard rations the REAL remaining quota (from the API headers) over the days
left in the month, so the daily run never exhausts the plan mid-month.
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.html_report import html_dashboard, open_in_browser
from sqp.audit.patterns import build_pick_history
from sqp.audit.report import consolidated_report, settlement_audit_report
from sqp.calibration.calibrator import train_market_calibrators
from sqp.config import CONFIG_DIR, ROOT, Settings, load_yaml
from sqp.logging_config import get_logger
from sqp.pipeline.budget import (DEFAULT_PRIORITY, days_left_in_month,
                                 leagues_within_budget, request_cost_per_league)
from sqp.pipeline.cleanup import prune_stale_candidates
from sqp.pipeline.daily import _finalize, run_league
from sqp.providers.odds_api import SPORT_KEYS, OddsAPIClient

log = get_logger("sqp.run_all")
MARKETS = "h2h,spreads,totals"


def _supported_leagues() -> dict[str, str]:
    leagues = {lg: meta["sport_key"] for lg, meta in SPORT_KEYS.items()}
    soccer = load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml").get("leagues", {})
    leagues.update({lg: c["sport_key"] for lg, c in soccer.items()})
    return leagues


def _active_tennis(client: OddsAPIClient) -> list[str]:
    """Active tennis tournament keys (league id == sport key). Tennis tournaments
    are dynamic, so they are discovered from /sports (free) rather than listed
    statically. has_scores is False; they settle via ESPN (settlement.runner)."""
    try:
        sports = client.list_sports(all_sports=True)
    except Exception as exc:
        log.warning("no se pudo listar torneos de tenis: %s", exc)
        return []
    return sorted(s["key"] for s in sports
                  if s.get("active") and (str(s.get("group", "")).lower() == "tennis"
                                          or str(s.get("key", "")).startswith("tennis_")))


def _select_live(settings: Settings, supported: dict[str, str],
                 max_leagues: int | None) -> tuple[list[str], list[str]]:
    client = OddsAPIClient(settings.odds_api_key, settings.regions, settings.odds_format)
    active = []
    for lg, sk in supported.items():
        try:
            if client.is_sport_active(sk):
                active.append(lg)
        except Exception as exc:  # status check is best-effort
            log.warning("status check failed for %s: %s", lg, exc)
    active += _active_tennis(client)  # dynamic tennis tournaments, settled via ESPN
    cost = request_cost_per_league(MARKETS, settings.regions)
    days_left = days_left_in_month(date.today())
    selected = leagues_within_budget(
        active, DEFAULT_PRIORITY, remaining=client.requests_remaining,
        cost_per_league=cost, days_left=days_left,
        safety_margin=int(os.getenv("ODDS_API_SAFETY_MARGIN", "20")),
        max_leagues_per_day=max_leagues)
    log.info("Cuota restante: %s | costo/liga: %d creditos | dias restantes del mes: %d",
             client.requests_remaining, cost, days_left)
    log.info("Ligas activas: %d [%s]", len(active), ", ".join(sorted(active)))
    log.info("Seleccionadas por presupuesto: %d [%s]", len(selected), ", ".join(selected))
    skipped = sorted(set(active) - set(selected))
    if skipped:
        log.warning("Aplazadas por presupuesto (correran cuando haya cuota): %s",
                    ", ".join(skipped))
    return selected, active


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["demo", "live"], default="live")
    ap.add_argument("--max-leagues", type=int, default=None,
                    help="Hard cap on leagues per day (on top of the budget guard)")
    ap.add_argument("--no-report", action="store_true")
    ap.add_argument("--no-html", action="store_true",
                    help="Skip the HTML dashboard (markdown report still written)")
    ap.add_argument("--open-dashboard", action="store_true",
                    help="Open the HTML dashboard in the default browser when the "
                         "run finishes (used by RUN_DIARIO_ALL.bat)")
    args = ap.parse_args()

    settings = Settings.load()
    supported = _supported_leagues()
    if args.mode == "demo":
        selected = [lg for lg in DEFAULT_PRIORITY if lg in supported]
        active = set(selected)  # demo has no real season; never prune
        log.info("DEMO: %d ligas soportadas con datos sinteticos.", len(selected))
    else:
        selected, active = _select_live(settings, supported, args.max_leagues)

    for lg in selected:
        try:
            run_league(lg, settings, mode=args.mode)
        except Exception as exc:
            log.error("[%s] fallo en el pipeline: %s", lg, exc)
            # Clear this league's picks so the report never shows a PRIOR day's
            # candidates as today's after a transient failure. _finalize archives
            # the old files first, so any un-settled pick stays recoverable.
            try:
                _finalize(lg, [], [], args.mode)
            except Exception as exc2:
                log.error("[%s] no se pudo limpiar picks tras el fallo: %s", lg, exc2)

    pred_dir = (ROOT / "data" / "predictions" / ("demo" if args.mode == "demo" else ".")).resolve()
    if args.mode != "demo":
        # Drop pick files from leagues that have gone out of season (and whose
        # bets are already settled) so the report below -- markdown AND HTML --
        # never shows stale candidates.
        prune_stale_candidates(pred_dir, ROOT / "data" / "bets", active)

    if not args.no_report:
        path = consolidated_report(pred_dir)
        log.info("Reporte consolidado (md) -> %s", path)
        # Refresh the realized-result artifacts the dashboard reads. Both are
        # best-effort: a failure here must never sink the daily run, which has
        # already produced the picks and the markdown report.
        try:
            audit_md = settlement_audit_report(ROOT / "data" / "bets")
            log.info("Auditoria de liquidacion (md) -> %s", audit_md)
        except Exception as exc:
            log.warning("No se pudo generar la auditoria de liquidacion: %s", exc)
        try:
            hist = build_pick_history(settings, write=True)
            log.info("Historial consolidado de picks: %d picks", len(hist))
            # Refresh per-(league, market) calibrators for NEXT runs. Today's picks
            # were already generated above with the prior models, so this can never
            # leak the current day into its own calibrator. Only when enabled.
            if settings.calibration_enabled and not hist.empty:
                cal = train_market_calibrators(hist)
                n_ok = sum(1 for r in cal if r.get("trained"))
                log.info("Calibradores reentrenados: %d (de %d grupos)", n_ok, len(cal))
        except Exception as exc:
            log.warning("No se pudo construir el historial / recalibrar: %s", exc)
        if not args.no_html:
            html_path = html_dashboard(pred_dir, ROOT / "data" / "bets")
            log.info("Dashboard HTML -> %s", html_path)
            log.info("Bookmark estable -> %s", pred_dir / "report_latest.html")
            if args.open_dashboard:
                if open_in_browser(html_path):
                    log.info("Dashboard abierto en el navegador.")
                else:
                    log.warning("No se pudo abrir el navegador (entorno headless?). "
                                "Abre manualmente: %s", html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
