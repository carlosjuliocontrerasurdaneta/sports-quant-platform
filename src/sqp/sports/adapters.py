"""Concrete family adapters.

Each family declares: how Elo difference maps to expected margin, the scoring
distribution, and baseline league parameters. League-specific values override
family defaults via params (this is how WNBA/NCAAB reuse the basketball
adapter, and every soccer league reuses the soccer adapter).

Feature roadmap per sport (pitchers, goalies, EPA/play, xG, pace, injuries)
plugs in as adjustments to mu/lambda BEFORE the distribution step - see each
sport skill in skills/ for the full feature spec.
"""
from __future__ import annotations
from sqp.domain.models import Event, EstimatedProbabilities
from sqp.models import distributions as dist
from sqp.models.park import ParkFactors
from sqp.models.rest import RestModel
from sqp.models.starters import StarterRatings
from sqp.models.team_scoring import TeamScoringRates
from sqp.logging_config import get_logger
from .base import SportAdapter

log = get_logger("sqp.adapters")


class NormalMarginAdapter(SportAdapter):
    """Basketball & american football: margin ~ Normal(mu, sigma).

    Margin (moneyline/spread) is Elo-driven; the total is built from per-team
    offense/defense scoring rates so it tracks the specific matchup instead of a
    league constant (which produced systematic Over/Under edges)."""

    def __init__(self, league: str, params: dict):
        super().__init__(league, params)
        self.scoring = TeamScoringRates(
            prior_games=params.get("scoring_prior_games", 6.0),
            half_life_days=params.get("scoring_half_life_days", 0.0),
            normalize=self.normalize)
        # Rest / back-to-back margin adjustment. points_per_day 0.0 (default) =
        # no-op; set rest_points_per_day > 0 to enable after an OOS check.
        self.rest = RestModel(points_per_day=params.get("rest_points_per_day", 0.0),
                              max_rest=params.get("rest_max_days", 4),
                              normalize=self.normalize)

    def observe(self, r: dict) -> None:
        super().observe(r)
        self.scoring.update(r["home"], r["away"], r["home_score"], r["away_score"],
                            r.get("date"))
        self.rest.observe(r["home"], r["away"], r.get("date"))

    def estimate(self, event, spread_line, total_line) -> EstimatedProbabilities:
        diff = self.elo.rating_diff(event.home, event.away)
        mu_margin = dist.elo_diff_to_margin(diff, self.params["points_per_elo"])
        # Rest differential nudges the home margin (back-to-backs underperform).
        mu_margin += self.rest.margin_adjustment(event.home, event.away,
                                                 str(event.start_time)[:10])
        sigma_m = self.params["margin_sigma"]
        mu_total = self.params["avg_total"]
        if self.params.get("scoring_totals", True):
            mu_total = self.scoring.expected_total(event.home, event.away, mu_total)
        sigma_t = self.params["total_sigma"]
        mp = dist.normal_margin_probs(mu_margin, sigma_m, spread_line)
        tp = dist.normal_total_probs(mu_total, sigma_t, total_line)
        return EstimatedProbabilities(
            home_win_estimated_probability=mp["home_win"],
            away_win_estimated_probability=mp["away_win"],
            home_cover_estimated_probability=mp.get("home_cover"),
            away_cover_estimated_probability=mp.get("away_cover"),
            over_estimated_probability=tp.get("over"),
            under_estimated_probability=tp.get("under"),
            spread_line=spread_line, total_line=total_line)


class PoissonAdapter(SportAdapter):
    """Hockey, soccer, baseball: per-team Poisson scoring.

    The home/away SPLIT comes from the Elo win expectation (tilt toward the
    favorite). The SCALE (expected total) comes from per-team offense/defense
    rates instead of a league constant, so a high-scoring matchup produces
    larger lambdas than a low-scoring one at the same Elo - which also flows
    through the baseball pitcher adjustment. Toggle with `scoring_totals`
    (default on); off reproduces the old league-constant scale.
    """

    def __init__(self, league: str, params: dict):
        super().__init__(league, params)
        self.scoring = TeamScoringRates(
            prior_games=params.get("scoring_prior_games", 6.0),
            half_life_days=params.get("scoring_half_life_days", 0.0),
            normalize=self.normalize)

    def observe(self, r: dict) -> None:
        super().observe(r)
        self.scoring.update(r["home"], r["away"], r["home_score"], r["away_score"],
                            r.get("date"))

    def _rates(self, event) -> tuple[float, float]:
        p_home = self.elo.expected_home_win(event.home, event.away)
        avg = self.params["avg_total"]
        if self.params.get("scoring_totals", True):
            avg = self.scoring.expected_total(event.home, event.away, avg)
        # tilt: shift scoring share toward the favorite, bounded.
        tilt = max(-0.30, min(0.30, (p_home - 0.5) * self.params.get("tilt_scale", 0.9)))
        lam_home = avg * (0.5 + tilt) + self.params.get("home_scoring_bonus", 0.0)
        lam_away = avg * (0.5 - tilt)
        return max(0.1, lam_home), max(0.1, lam_away)

    def estimate(self, event, spread_line, total_line) -> EstimatedProbabilities:
        lam_h, lam_a = self._rates(event)
        probs = dist.poisson_match_probs(lam_h, lam_a, spread_line, total_line,
                                         three_way=self.three_way,
                                         max_goals=self.params.get("max_score", 15),
                                         dc_rho=self.params.get("dc_rho", 0.0),
                                         dispersion_k=self.params.get("dispersion_k"))
        return EstimatedProbabilities(
            home_win_estimated_probability=probs["home_win"],
            away_win_estimated_probability=probs["away_win"],
            draw_estimated_probability=probs.get("draw"),
            home_cover_estimated_probability=probs.get("home_cover"),
            away_cover_estimated_probability=probs.get("away_cover"),
            over_estimated_probability=probs.get("over"),
            under_estimated_probability=probs.get("under"),
            spread_line=spread_line, total_line=total_line)


class BasketballAdapter(NormalMarginAdapter):
    family = "basketball"

class FootballAdapter(NormalMarginAdapter):
    family = "football"

class BaseballAdapter(PoissonAdapter):
    """Baseball: Poisson runs with starting-pitcher lambda adjustment.

    The starter is the largest single factor; its bounded factor scales the
    OPPONENT'S lambda before the distribution step. Games without a known
    probable starter are estimated but flagged (no bet candidates).
    """
    family = "baseball"

    def __init__(self, league: str, params: dict):
        super().__init__(league, params)
        self.starters = StarterRatings(
            prior_starts=params.get("pitcher_prior_starts", 5.0),
            min_starts=params.get("pitcher_min_starts", 3),
            bound=params.get("pitcher_bound", 0.35))
        # Starter signal: "fip" (v2, fielding-independent, per-start FIP) or "ra"
        # (v1, full-game runs allowed). Kept separate so the rating pool never
        # mixes the two scales; "fip" ignores RA and vice versa.
        self.pitcher_signal = params.get("pitcher_signal", "ra")
        # Ballpark run-environment factor on the TOTAL. Bound 0.0 (default) = no-op
        # (factor always 1.0); set park_bound > 0 (e.g. 0.20) to enable after an OOS
        # check. Estimated home-vs-away runs for the home team (isolates the venue).
        self.park = ParkFactors(prior_games=params.get("park_prior_games", 20.0),
                                bound=params.get("park_bound", 0.0),
                                normalize=self.normalize)

    def observe(self, r: dict) -> None:
        super().observe(r)
        self.park.update(r["home"], r["away"], r["home_score"] + r["away_score"])
        if self.pitcher_signal == "fip":
            # Each starter rated by his own per-start FIP (independent of defense
            # and opponent offense -- the v1 confound). Rows without FIP are skipped
            # rather than RA-substituted, to avoid mixing scales.
            if r.get("home_starter_fip") is not None:
                self.starters.update(r.get("home_starter"), r["home_starter_fip"])
            if r.get("away_starter_fip") is not None:
                self.starters.update(r.get("away_starter"), r["away_starter_fip"])
        else:
            # v1: runs allowed while this starter's team was pitching = opponent score.
            self.starters.update(r.get("home_starter"), r["away_score"])
            self.starters.update(r.get("away_starter"), r["home_score"])

    def _rates(self, event) -> tuple[float, float]:
        lam_h, lam_a = super()._rates(event)
        f_vs_away_starter = self.starters.factor(event.away_pitcher)
        f_vs_home_starter = self.starters.factor(event.home_pitcher)
        # Park factor scales BOTH lambdas (a total-environment adjustment), so it
        # moves Over/Under without distorting the moneyline split. No-op at bound 0.
        pf = self.park.factor(event.home)
        if f_vs_away_starter != 1.0 or f_vs_home_starter != 1.0 or pf != 1.0:
            log.debug("[%s] %s@%s lambda adj: home x%.3f (vs %s), away x%.3f (vs %s), park x%.3f",
                      self.league, event.away, event.home, f_vs_away_starter,
                      event.away_pitcher, f_vs_home_starter, event.home_pitcher, pf)
        return max(0.1, lam_h * f_vs_away_starter * pf), max(0.1, lam_a * f_vs_home_starter * pf)

    def f5_rates(self, event) -> tuple[float, float]:
        """Per-team run rates for the FIRST 5 INNINGS.

        F5 is starter-dominated (the starter throws ~all of innings 1-5, the
        bullpen governs 6-9). A pure proration `phi * lam_full` is a deterministic
        rescale of the full-game view and adds NO edge over it, so the starter
        factor is applied with a tunable emphasis: `amp = 1 + emphasis*(f-1)`.
        `f5_starter_emphasis = 1.0` recovers pure proration (edge-neutral); values
        > 1 encode the hypothesis that the starter matters more in F5 than the
        full-game model, where the bullpen dilutes him. Both params are read with
        defaults so the production config is untouched until an OOS check on
        backfilled inning-level data justifies tuning them.
        """
        base_h, base_a = super()._rates(event)  # offense baseline, no starter/park
        phi = self.params.get("f5_innings_fraction", 5.0 / 9.0)
        emph = self.params.get("f5_starter_emphasis", 1.0)
        pf = self.park.factor(event.home)
        amp_away = 1.0 + emph * (self.starters.factor(event.away_pitcher) - 1.0)
        amp_home = 1.0 + emph * (self.starters.factor(event.home_pitcher) - 1.0)
        lam_h5 = base_h * phi * amp_away * pf
        lam_a5 = base_a * phi * amp_home * pf
        return max(0.05, lam_h5), max(0.05, lam_a5)

    def estimate_f5(self, event, total_line: float | None = None,
                    spread_line: float | None = None) -> dict[str, float]:
        """F5 market probabilities from the starter-isolated run distribution.

        Three-way moneyline (a tie after 5 is a real outcome, unlike the full game
        which resolves in extras), plus F5 total O/U and F5 team spread. Reuses the
        same Poisson/NegBin grid as the full game; `dispersion_k` is inherited as a
        first cut and flagged for re-estimation on F5 counts once data exists.
        """
        lam_h5, lam_a5 = self.f5_rates(event)
        return dist.poisson_match_probs(
            lam_h5, lam_a5, spread_line, total_line, three_way=True,
            max_goals=self.params.get("max_score", 25),
            dispersion_k=self.params.get("f5_dispersion_k",
                                         self.params.get("dispersion_k")))

    def reliability_warning(self, event: Event, min_games: int = 10) -> str | None:
        base = super().reliability_warning(event, min_games)
        unknown = [n for n, p in ((event.home, event.home_pitcher),
                                  (event.away, event.away_pitcher))
                   if not self.starters.is_known(p)]
        if unknown:
            msg = (f"Starter unknown or <{self.starters.min_starts} starts for: "
                   f"{', '.join(unknown)}. Estimate flagged, no bet candidates.")
            return f"{base} {msg}" if base else msg
        return base

class HockeyAdapter(PoissonAdapter):
    family = "hockey"

class SoccerAdapter(PoissonAdapter):
    family = "soccer"
    three_way = True

class TennisAdapter(SportAdapter):
    """Tennis (ATP/WTA main tour). Elo por jugador, de tour completo.

    NO modela la superficie. Se afirmaba "surface-aware" en este docstring y no
    existe ninguna linea de codigo que la maneje (auditoria 2026-07-31); la
    superficie es probablemente el factor mas determinante del tenis, asi que
    esa ausencia acota lo que el modelo puede explicar: log loss 0.656 frente a
    0.693 de una moneda.

    Markets: match winner now; game handicap / total games require a
    game-level model (phase 3 extension). The Odds API tennis keys carry no
    scores: settlement needs a secondary results source.
    """
    family = "tennis"

    def estimate(self, event, spread_line, total_line) -> EstimatedProbabilities:
        p = self.elo.expected_home_win(event.home, event.away, neutral=True)
        return EstimatedProbabilities(
            home_win_estimated_probability=p,
            away_win_estimated_probability=1 - p,
            spread_line=spread_line, total_line=total_line)
