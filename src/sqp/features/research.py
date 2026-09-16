"""Pregame feature blocks for offline experiments across every adapter family.

No model registration or live probability changes. Result-derived features use
the preceding day's state. External sporting projections require an explicit
availability timestamp at or before that same cutoff; missing data stays NaN.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd

from sqp.domain.models import Event
from sqp.features.temporal import ordered_games
from sqp.sports.registry import get_adapter


# Units belong to the contract, not to a coefficient guessed by the engine.
SPORTING_INPUTS = {
    "baseball": ("starter_fip", "starter_expected_innings", "bullpen_fip",
                 "bullpen_pitches_3d", "lineup_xwoba", "park_run_factor"),
    "basketball": ("pace", "off_rating", "def_rating", "available_rotation_minutes"),
    "football": ("qb_epa_per_play", "off_epa_per_play", "def_epa_per_play",
                 "plays_per_game", "returning_snap_share"),
    "hockey": ("goalie_gsax_per60", "xgf_per60_5v5", "xga_per60_5v5",
               "power_play_rate", "penalty_kill_rate"),
    "soccer": ("xgf_per90", "xga_per90", "available_starter_minutes"),
    "tennis": ("surface_elo", "serve_points_won_rate", "return_points_won_rate",
               "minutes_played_7d"),
}


@dataclass
class FeatureDataset:
    frame: pd.DataFrame
    blocks: dict[str, list[str]]
    family: str
    league: str
    coverage: dict[str, float]


def snapshot_features(games: pd.DataFrame, snapshots: pd.DataFrame | None,
                      family: str) -> pd.DataFrame:
    """Join latest pre-cutoff projection per game. Never backfill from future.

    Schema: game_id, available_at (timezone required), source, and any subset
    of home_/away_ SPORTING_INPUTS. One row represents a complete snapshot;
    partial rows do not inherit fields from earlier snapshots. Conflicting
    versions at the same game/time are rejected rather than chosen by order.
    """
    cols = [f"{side}_{name}" for name in SPORTING_INPUTS[family]
            for side in ("home", "away")]
    out = pd.DataFrame(np.nan, index=games.index, columns=cols)
    if snapshots is None or snapshots.empty:
        return out
    required = {"game_id", "available_at", "source"}
    if not required.issubset(snapshots):
        raise ValueError(f"snapshot requires {sorted(required)}")
    unexpected = set(snapshots) - required - set(cols)
    if unexpected:
        raise ValueError(f"unknown snapshot fields: {sorted(unexpected)}")
    s = snapshots.copy()
    if s[list(required)].isna().any().any():
        raise ValueError("snapshot identity, availability and source cannot be null")
    if s["game_id"].astype(str).str.strip().eq("").any() or s["source"].astype(str).str.strip().eq("").any():
        raise ValueError("snapshot game_id and source cannot be empty")
    if not s["available_at"].astype(str).str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
        raise ValueError("snapshot available_at requires a timezone")
    s["available_at"] = pd.to_datetime(s["available_at"], utc=True, errors="raise")
    s["game_id"] = s["game_id"].astype(str)
    ambiguous = set(games.loc[games.game_id.astype(str).duplicated(keep=False), "game_id"].astype(str))
    if ambiguous & set(s.game_id):
        raise ValueError("snapshot game_id is ambiguous in results")
    if s.duplicated(["game_id", "available_at"]).any():
        raise ValueError("duplicate game/time snapshot")
    for col in set(cols) & set(s):
        s[col] = pd.to_numeric(s[col], errors="raise")
        if np.isinf(s[col].to_numpy(float)).any():
            raise ValueError(f"nonfinite snapshot: {col}")
        if col.endswith(("_rate", "_share", "_xwoba")) and not s[col].dropna().between(0, 1).all():
            raise ValueError(f"snapshot fraction outside [0,1]: {col}")
        if col.endswith("starter_expected_innings") and not s[col].dropna().between(0, 9).all():
            raise ValueError(f"starter innings outside [0,9]: {col}")
    grouped = {key: group.sort_values("available_at") for key, group in s.groupby("game_id")}
    for i, row in games.iterrows():
        group = grouped.get(str(row.get("game_id", "")))
        if group is None:
            continue
        cutoff = pd.Timestamp(row["date"], tz="UTC")
        eligible = group[group.available_at <= cutoff]
        if not eligible.empty:
            values = eligible.iloc[-1].reindex(cols)
            out.loc[i, cols] = values.to_numpy()
    return out


def sporting_interactions(values: dict, family: str) -> dict[str, float]:
    """Pregame matchup interactions, preserving missingness rather than guessing."""
    out = {}
    for name in SPORTING_INPUTS[family]:
        h, a = values[f"home_{name}"], values[f"away_{name}"]
        out[f"sporting_diff_{name}"] = h - a
    if family == "basketball":
        pace = (values["home_pace"] + values["away_pace"]) / 2
        efficiency = sum(values[f"{side}_{kind}_rating"] for side in ("home", "away")
                         for kind in ("off", "def")) / 2
        out["sporting_pace_efficiency_total"] = pace * efficiency / 100
    elif family == "baseball":
        for side in ("home", "away"):
            innings = values[f"{side}_starter_expected_innings"]
            out[f"sporting_{side}_staff_fip"] = (values[f"{side}_starter_fip"] * innings
                                                + values[f"{side}_bullpen_fip"] * (9 - innings)) / 9
    elif family in {"soccer", "hockey"}:
        unit = "per90" if family == "soccer" else "per60_5v5"
        for side, opponent in (("home", "away"), ("away", "home")):
            out[f"sporting_{side}_matchup_xg"] = (values[f"{side}_xgf_{unit}"]
                                                 + values[f"{opponent}_xga_{unit}"]) / 2
    return out


def build_research_dataset(results: pd.DataFrame, league: str, family: str,
                           league_params: dict | None = None, *,
                           snapshots: pd.DataFrame | None = None,
                           window: int = 20,
                           fixtures: pd.DataFrame | None = None) -> FeatureDataset:
    if window < 1:
        raise ValueError("window must be positive")
    needed = {"date", "home", "away", "home_score", "away_score", "game_id"}
    if not needed.issubset(results):
        raise ValueError(f"results require {sorted(needed)}")
    d = ordered_games(results)
    if d[["home", "away", "home_score", "away_score"]].isna().any().any():
        raise ValueError("results cannot contain missing teams or scores")
    if not np.isfinite(d[["home_score", "away_score"]].to_numpy(float)).all():
        raise ValueError("results require finite scores")
    d["_fixture"] = False
    if fixtures is not None:
        required = {"date", "game_id", "home", "away"}
        if not required.issubset(fixtures) or fixtures[list(required)].isna().any().any():
            raise ValueError("fixtures require date, game_id, home and away")
        if {"home_score", "away_score"} & set(fixtures):
            raise ValueError("fixtures must not contain results")
        future = ordered_games(fixtures)
        if len(future) and len(d) and future.date.min() <= d.date.max():
            raise ValueError("fixture dates must follow every history date")
        future["_fixture"] = True
        future["home_score"] = np.nan
        future["away_score"] = np.nan
        d = ordered_games(pd.concat([d, future], ignore_index=True))
    # Composite identity supports legacy blank IDs without merging games.
    d["event_id"] = [f"{league}|{day}|{gid}|{h}|{a}" for day, gid, h, a in
                     zip(d.date, d.game_id.fillna(""), d.home, d.away)]
    if d.event_id.duplicated().any():
        raise ValueError("duplicate event in research results")
    external = snapshot_features(d, snapshots, family)
    if family == "tennis":
        # Some sources always store winner as home. A fixed identity-based
        # orientation (not score-based) restores a meaningful classification task.
        for i, r in d.iterrows():
            identity = f"{league}|{r.date}|{r.game_id}|{'|'.join(sorted((r.home, r.away)))}"
            if hashlib.sha256(identity.encode()).digest()[0] % 2:
                for left, right in (("home", "away"), ("home_score", "away_score")):
                    left_value, right_value = d.at[i, left], d.at[i, right]
                    d.at[i, left], d.at[i, right] = right_value, left_value
                for name in SPORTING_INPUTS[family]:
                    cols = [f"home_{name}", f"away_{name}"]
                    external.loc[i, cols] = external.loc[i, cols[::-1]].to_numpy().copy()
    adapter = get_adapter(league, family, league_params)
    hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
    # Schedule history is independent of the form window (doubleheaders count).
    dates: dict[str, list[pd.Timestamp]] = defaultdict(list)
    rows = []
    for day, group in d.groupby("date", sort=False):
        now = pd.Timestamp(day)
        pending = []
        for i, r in group.iterrows():
            h, a = adapter.normalize(r["home"]), adapter.normalize(r["away"])
            ev = Event(str(r.event_id), "research", league, r.home, r.away, day)
            est = adapter.estimate(ev, None, None)
            ph, pa = est.home_win_estimated_probability, est.away_win_estimated_probability
            draw = est.draw_estimated_probability or 0.0
            hs, aws = float(r.home_score), float(r.away_score)
            label: float = (2 if hs > aws else 1 if hs == aws else 0) if family == "soccer" else int(hs > aws)
            if r["_fixture"]:
                label = np.nan
            baseline_total = (adapter.scoring.expected_total(r.home, r.away, adapter.params["avg_total"])
                              if hasattr(adapter, "scoring") else np.nan)
            if hasattr(adapter, "_rates"):
                rates = adapter._rates(ev)
                baseline_total = sum(rates)
                margin = rates[0] - rates[1]
            elif family != "tennis":
                margin = adapter.elo.rating_diff(r.home, r.away) * adapter.params["points_per_elo"]
                margin += adapter.rest.margin_adjustment(r.home, r.away, day)
            else:
                margin = 0.0
            row = {"date": day, "event_id": r.event_id, "game_id": r.game_id,
                   "home": r.home, "away": r.away, "target_h2h": label,
                   "target_total": hs + aws,
                   "is_draw": hs == aws, "base_home": ph, "base_away": pa,
                   "base_draw": draw, "base_total": baseline_total,
                   "base_margin": margin}
            for side, team, role in (("home", h, "home"), ("away", a, "away")):
                prior = list(hist[team])
                row[f"schedule_{side}_rest_days"] = ((now - dates[team][-1]).days if dates[team] else np.nan)
                for span in (7, 14):
                    row[f"schedule_{side}_games_{span}d"] = sum((now - t).days <= span for t in dates[team])
                for field in ("win_residual", "margin_residual", "scored", "conceded"):
                    row[f"form_{side}_{field}"] = float(np.mean([x[field] for x in prior])) if prior else np.nan
                row[f"form_{side}_n"] = len(prior)
                same_role = [x for x in prior if x["role"] == role]
                row[f"venue_{side}_win_residual"] = (float(np.mean([x["win_residual"] for x in same_role])) if same_role else np.nan)
                row[f"venue_{side}_n"] = len(same_role)
                if family == "baseball":
                    fips = [x["starter_fip"] for x in prior if np.isfinite(x["starter_fip"])]
                    row[f"pitching_{side}_rotation_fip"] = float(np.mean(fips)) if fips else np.nan
                    row[f"pitching_{side}_n"] = len(fips)
            for field in ("win_residual", "margin_residual", "scored", "conceded"):
                row[f"form_diff_{field}"] = row[f"form_home_{field}"] - row[f"form_away_{field}"]
            for col, value in external.loc[i].items():
                row[f"sporting_{col}"] = value
            row.update(sporting_interactions(external.loc[i].to_dict(), family))
            # Never use a false 'total' from winner-coded tennis result stores.
            if family == "tennis":
                for key in list(row):
                    if key.startswith("form_") and any(x in key for x in ("margin", "scored", "conceded")):
                        del row[key]
            rows.append(row)
            if not r["_fixture"]:
                pending.append((r.to_dict(), h, a, ph, pa, margin, hs, aws))
        # All estimates for the day precede all result updates.
        for result, h, a, ph, pa, margin, hs, aws in pending:
            for team, role, scored, conceded, p, expected in (
                    (h, "home", hs, aws, ph, margin), (a, "away", aws, hs, pa, -margin)):
                hist[team].append({"role": role, "win_residual": float(scored > conceded) - p,
                                   "margin_residual": scored - conceded - expected,
                                   "scored": scored, "conceded": conceded,
                                   "starter_fip": float(result.get(f"{role}_starter_fip", np.nan)
                                                        if pd.notna(result.get(f"{role}_starter_fip")) else np.nan)})
                dates[team].append(now)
                dates[team] = [t for t in dates[team] if (now - t).days <= 14]
            adapter.observe(result)
    out = pd.DataFrame(rows)
    blocks = {name: [c for c in out if c.startswith(prefix)] for name, prefix in
              (("schedule", "schedule_"), ("opponent_form", "form_"),
               ("venue_form", "venue_"), ("sporting", "sporting_"))}
    if family == "baseball":
        # Counts alone must not make an entirely absent data source 'available'.
        cols = [c for c in out if c.startswith("pitching_")]
        if not any(out[c].notna().any() for c in cols if c.endswith("fip")):
            out[cols] = np.nan
        blocks["pitching"] = cols
    coverage = {c: float(out[c].notna().mean()) for cols in blocks.values() for c in cols}
    return FeatureDataset(out, blocks, family, league, coverage)
