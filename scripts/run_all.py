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
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.clv import SHADOW_EXIT_MIN_N, daily_clv
from sqp.audit.html_report import html_dashboard, open_in_browser
from sqp.audit.patterns import build_pick_history
from sqp.audit.report import consolidated_report, settlement_audit_report
from sqp.calibration.data import stage_calibrators_from_settled
from sqp.config import CONFIG_DIR, ROOT, Settings, load_yaml
from sqp.logging_config import get_logger
from sqp.pipeline.budget import (DEFAULT_PRIORITY, days_left_in_month,
                                 leagues_within_budget, request_cost_per_league)
from sqp.pipeline.cleanup import (prune_stale_candidates,
                                  unsettled_completed_picks)
from sqp.pipeline.daily import apply_global_exposure_cap, run_league
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
            in_season = client.is_sport_active(sk)
        except Exception as exc:  # status check is best-effort
            # Mirror run_league (daily.py:396): a transient /sports failure must
            # NOT silently drop the league for the whole run. Assume active and
            # let run_league/_finalize decide; the budget guard still ranks it by
            # priority. (False/None from a SUCCESSFUL check still exclude: out of
            # season / unknown key.)
            log.warning("status check failed for %s; assuming active: %s", lg, exc)
            in_season = True
        if in_season:
            active.append(lg)
    active += _active_tennis(client)  # dynamic tennis tournaments, settled via ESPN
    cost = request_cost_per_league(MARKETS, settings.regions)
    days_left = days_left_in_month(date.today())
    # The Odds API exposes the live quota only via response headers. If it could
    # not be read (None), the budget cannot be rationed; rather than silently
    # selecting zero leagues (no picks for the whole day), fall back to a small
    # conservative count of the top-priority leagues and say so loudly.
    fallback_leagues = int(os.getenv("ODDS_API_FALLBACK_LEAGUES", "5"))
    if client.requests_remaining is None and max_leagues is None:
        log.warning("No se pudo leer la cuota de The Odds API; presupuesto no "
                    "racionable. Fallback conservador: %d ligas prioritarias "
                    "(ODDS_API_FALLBACK_LEAGUES).", fallback_leagues)
    selected = leagues_within_budget(
        active, DEFAULT_PRIORITY, remaining=client.requests_remaining,
        cost_per_league=cost, days_left=days_left,
        safety_margin=int(os.getenv("ODDS_API_SAFETY_MARGIN", "20")),
        max_leagues_per_day=max_leagues, fallback_leagues=fallback_leagues)
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
    failures = 0

    settings = Settings.load()
    # Size today's stakes on the real running balance (initial + realized PnL +
    # manual adjustments) when enabled. Live only; demo keeps the static initial.
    # Settlement runs before the daily run (SETTLE 09:00 -> RUN 10:00), so the
    # ledger already reflects yesterday's graded bets.
    if args.mode != "demo" and settings.bankroll_dynamic:
        from sqp.risk.bankroll import BankrollLedger
        bal = BankrollLedger(root=ROOT, initial=settings.bankroll).current_balance()
        log.info("Banca dinámica: inicial %.2f -> balance actual %.2f (PnL realizado + ajustes).",
                 settings.bankroll, bal)
        if bal <= 0:
            log.warning("Balance de banca <= 0 (%.2f): no se dimensionará ninguna apuesta.", bal)
        settings.bankroll = bal
    supported = _supported_leagues()
    if args.mode == "demo":
        selected = [lg for lg in DEFAULT_PRIORITY if lg in supported]
        active = set(selected)  # demo has no real season; never prune
        log.info("DEMO: %d ligas soportadas con datos sinteticos.", len(selected))
    else:
        selected, active = _select_live(settings, supported, args.max_leagues)

    # M2 guard: the daily run overwrites candidates_<league>.csv, and the
    # settlement dedup key includes generated_at, so a commenced-but-unsettled
    # pick becomes ungradeable once overwritten. Skip (do not overwrite) any
    # league that still holds such picks and say so loudly, so it stays settleable
    # by the next SETTLE_ALL. Canonical flow settles first (DIARIO_COMPLETO.bat),
    # so this is normally a no-op. SQP_ALLOW_UNSETTLED_OVERWRITE=1 forces through
    # (archive/ keeps overwritten files recoverable either way).
    if (args.mode != "demo"
            and os.getenv("SQP_ALLOW_UNSETTLED_OVERWRITE", "").lower()
            not in ("1", "true", "yes")):
        at_risk = unsettled_completed_picks(
            ROOT / "data" / "predictions", ROOT / "data" / "bets", selected)
        for lg, n in sorted(at_risk.items()):
            log.error("[%s] %d picks ya comenzados sin liquidar: se OMITE hoy para no "
                      "volverlos no graduables. Ejecuta SETTLE_ALL primero "
                      "(o SQP_ALLOW_UNSETTLED_OVERWRITE=1 para forzar).", lg, n)
        if at_risk:
            selected = [lg for lg in selected if lg not in at_risk]

    # Monitor de degradación por (liga, mercado) (2026-07-13): sobre la ventana
    # móvil de liquidadas, auto-pausa un mercado cuyo Brier estimado es peor que
    # el baseline del mercado o cuyo ROI a stake plano cae bajo el umbral, con
    # histéresis para reanudar (sqp.risk.degradation). Corre ANTES del loop de
    # ligas y fusiona por UNIÓN con paused_markets, así nunca des-pausa una
    # pausa estática del yaml. Best-effort: si el monitor falla, se aplican las
    # auto-pausas del último registro persistido (conservador) y el run sigue.
    if args.mode != "demo" and settings.degradation_enabled:
        from sqp.risk.degradation import (load_degradation_registry,
                                          paused_from_registry,
                                          run_degradation_monitor)
        try:
            reg_path, transitions, auto_paused = run_degradation_monitor(
                ROOT / "data" / "bets",
                window_days=settings.degradation_window_days,
                min_n=settings.degradation_min_n,
                brier_margin=settings.degradation_brier_margin,
                roi_pause=settings.degradation_roi_pause,
                roi_resume=settings.degradation_roi_resume)
            for t in transitions:
                log.warning("Degradación [%s|%s] -> %s (%s; n=%d, brier_model=%s, "
                            "brier_market=%s, roi_flat=%s)", t["league"], t["market"],
                            t["action"].upper(), t["reasons"] or "-", t["n"],
                            t["brier_model"], t["brier_market"], t["roi_flat"])
            log.info("Monitor de degradación -> %s | mercados auto-pausados: %s",
                     reg_path, auto_paused or "ninguno")
        except Exception as exc:
            log.warning("Monitor de degradación falló (%s); se aplican las "
                        "auto-pausas del último registro persistido.", exc)
            auto_paused = paused_from_registry(
                load_degradation_registry(ROOT / "data" / "bets"))
        for lg, mks in auto_paused.items():
            settings.paused_markets[lg] = sorted(
                set(settings.paused_markets.get(lg, [])) | set(mks))

    for lg in selected:
        try:
            run_league(lg, settings, mode=args.mode)
        except Exception as exc:
            failures += 1
            log.error("[%s] fallo en el pipeline: %s", lg, exc)
            # Preserve the prior file for settlement. Daily reports and the
            # global cap are scoped by generated_at, so yesterday's candidates
            # cannot masquerade as today's picks after this failure.

    pred_dir = (ROOT / "data" / "predictions" / ("demo" if args.mode == "demo" else ".")).resolve()
    if args.mode != "demo":
        # Drop pick files from leagues that have gone out of season (and whose
        # bets are already settled) so the report below -- markdown AND HTML --
        # never shows stale candidates.
        prune_stale_candidates(pred_dir, ROOT / "data" / "bets", active)

    # Cross-league exposure cap: the per-league cap inside run_league bounds each
    # league alone, so a multi-league day could compound to N x that fraction.
    # Enforce the whole day's total here, after every league is written and stale
    # files pruned. Applies in both modes (demo sizes on the static bankroll).
    run_day = datetime.now(timezone.utc).date().isoformat()
    factor = apply_global_exposure_cap(
        pred_dir, settings.bankroll, settings.risk.max_total_exposure_pct,
        generated_day=run_day)
    if factor < 1.0:
        log.warning("Exposición global del día excedió %.0f%% del bankroll; stakes de "
                    "todas las ligas escalados por %.3f para respetar el cap global.",
                    settings.risk.max_total_exposure_pct * 100, factor)

    if not args.no_report:
        path = consolidated_report(pred_dir)
        log.info("Reporte consolidado (md) -> %s", path)
        if args.mode == "demo":
            # Demo data is isolated under predictions/demo + calibration/demo.
            # Never let a synthetic run rewrite the real CLV gate, settled-bet
            # audit, pick history, staging models or live calibration registry.
            if not args.no_html:
                demo_bets = ROOT / "data" / "bets" / "demo"
                html_path = html_dashboard(
                    pred_dir, demo_bets,
                    patterns_path=pred_dir / "pick_history.csv")
                log.info("Dashboard HTML demo -> %s", html_path)
                if args.open_dashboard:
                    open_in_browser(html_path)
            return 1 if failures else 0
        # Refresh the realized-result artifacts the dashboard reads. Both are
        # best-effort: a failure here must never sink the daily run, which has
        # already produced the picks and the markdown report.
        try:
            audit_md = settlement_audit_report(ROOT / "data" / "bets")
            log.info("Auditoria de liquidacion (md) -> %s", audit_md)
        except Exception as exc:
            failures += 1
            log.warning("No se pudo generar la auditoria de liquidacion: %s", exc)
        # CLV diario: mide precio de entrada vs cierre capturado sobre lo ya
        # liquidado y deja en el log el avance de la regla de salida del shadow
        # mode (mediana > 0 con n suficiente). Best-effort, como la auditoria.
        try:
            clv = daily_clv(ROOT / "data" / "bets", ROOT,
                            gate_min_n=settings.clv_gate_min_n)
            if clv["n_matched"]:
                log.info("CLV diario -> %s | n=%d (sin cierre: %d) | "
                         "mediana=%+.2f%% | batio cierre=%.1f%% | salida shadow "
                         "(parte CLV): %s", clv["path"], clv["n_matched"],
                         clv["n_unmatched"], clv["median_clv_pct"] * 100,
                         clv["beat_close_rate"] * 100,
                         "CUMPLE" if clv["shadow_clv_ok"]
                         else f"pendiente (requiere n>={SHADOW_EXIT_MIN_N} "
                              f"y mediana>0)")
            else:
                log.info("CLV diario: aun no hay apuestas emparejables a un "
                         "cierre capturado (sin cierre: %d) -> %s",
                         clv["n_unmatched"], clv["path"])
            allowed = clv.get("gate_allowed") or []
            log.info("Gate de CLV por mercado -> %s | habilitados para stake "
                     "real: %s", clv["gate_path"],
                     ", ".join(allowed) if allowed
                     else "ninguno (default-deny)")
        except Exception as exc:
            failures += 1
            log.warning("No se pudo generar el analisis CLV: %s", exc)
        try:
            hist = build_pick_history(settings, write=True)
            log.info("Historial consolidado de picks: %d picks", len(hist))
            # Retrain per-(league, market) calibrators as CANDIDATES for NEXT runs.
            # Trains on settled live bets UNION the graded served stream
            # (opening-anchored), NOT the closing-anchored backtest above. Today's
            # picks were already generated with the prior LIVE
            # models, so this cannot leak the current day into its own calibrator.
            # With calibration.auto_promote (2026-07-08) the gated staging
            # recommendation is then adopted into the LIVE registry (OOS gates +
            # independent-event guard, see auto_promote_calibrators); improvements apply from
            # the NEXT run. Flag off = staging only, human promotion.
            cal = stage_calibrators_from_settled(settings)
            if cal:
                n_ok = sum(1 for r in cal if r.get("trained"))
                log.info("Calibradores reentrenados a STAGING desde settled: %d de "
                         "%d grupos", n_ok, len(cal))
                if settings.calibration_auto_promote:
                    from sqp.calibration.calibrator import auto_promote_calibrators
                    sync = auto_promote_calibrators(cal)
                    if sync["promoted"] or sync["demoted"]:
                        log.info("Autocorrección de calibración: promovidos=%s "
                                 "demovidos=%s omitidos_por_n_val=%s — aplican "
                                 "desde el próximo run (log: data/models/"
                                 "promotion_log.csv)", sync["promoted"],
                                 sync["demoted"], sync["skipped"])
                    else:
                        log.info("Autocorrección de calibración: ningún candidato "
                                 "elegible hoy (gates OOS / n_val); registro live "
                                 "sin cambios. Omitidos=%s", sync["skipped"])
                else:
                    log.info("Auto-promoción OFF: candidatos en staging; usa "
                             "scripts/promote_calibration.py para revisar y promover")
        except Exception as exc:
            failures += 1
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
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
