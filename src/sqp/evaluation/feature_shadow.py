"""Isolated, frozen feature experiments and append-only pregame captures."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import sklearn
import scipy

from sqp.config import ROOT, Settings
from sqp.calibration.metrics import calibration_report
from sqp.evaluation.bootstrap import cluster_bootstrap_ci
from sqp.evaluation.feature_blocks import _learner
from sqp.features.research import build_research_dataset
from sqp.pipeline.daily import _league_meta
from sqp.storage.atomic import atomic_write_json


def utc_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_versions() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "sklearn": sklearn.__version__, "joblib": joblib.__version__,
            "scipy": scipy.__version__}


def fingerprint(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted((root / "src/sqp").rglob("*.py")) + sorted((root / "configs").rglob("*.yaml")):
        h.update(str(path.relative_to(root)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def design(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    out = frame.copy()
    if target == "h2h":
        for col in ("base_home", "base_away", "base_draw"):
            out[col] = np.log(np.clip(out[col], 1e-6, 1 - 1e-6))
    return out


def fit_pair(dataset, candidate: dict) -> dict:
    target = candidate["target"]
    d = dataset.frame
    if target == "h2h":
        d = d.loc[~d.is_draw]
    d = design(d, target)
    y = d["target_h2h" if target == "h2h" else "target_total"].to_numpy()
    if target == "h2h" and not np.array_equal(np.unique(y), [0, 1]):
        raise ValueError("shadow candidates require both binary outcome classes")
    base = ["base_home", "base_away", "base_draw"] if target == "h2h" else ["base_total", "base_margin"]
    extra = [c for c in dataset.blocks[candidate["block"]] if d[c].nunique(dropna=False) > 1]
    if not extra:
        raise ValueError("candidate block has no variable training columns")
    pair = {}
    for name, cols in (("baseline", base), ("candidate", base + extra)):
        model = _learner(target == "h2h")
        model.fit(d[cols], y)
        pair[name] = {"model": model, "columns": cols}
    return {"pair": pair, "n_train": len(d), "train_through": d.date.max()}


def train(root: Path, manifest_path: Path, report_path: Path, out: Path,
          start: str, end: str) -> dict:
    """Reserve a new directory; publish READY only after every artifact exists."""
    begin, finish = pd.Timestamp(start), pd.Timestamp(end)
    if begin.tzinfo is None or finish.tzinfo is None or begin <= utc_now() or finish <= begin:
        raise ValueError("require timezone-aware future start and end > start")
    if begin != begin.normalize() or finish != finish.normalize():
        raise ValueError("protocol boundaries must be UTC midnight")
    if begin.utcoffset().total_seconds() or finish.utcoffset().total_seconds():
        raise ValueError("protocol boundaries must use UTC")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if digest(report_path) != manifest["discovery_report_sha256"]:
        raise ValueError("discovery report hash mismatch")
    candidates = manifest["candidates"]
    if not candidates or len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("empty or duplicate candidate selection")
    for c in candidates:
        if c["status"] != "AWAITING_FORWARD_PROTOCOL" or c["target"] not in {"h2h", "total_score"}:
            raise ValueError("unsupported candidate")
        if c["block"] not in {"schedule", "opponent_form"}:
            raise ValueError("only approved local blocks supported")
        if pd.Timestamp(c["discovery_through"], tz="UTC") >= begin:
            raise ValueError("forward start overlaps discovery")
    code_hash = fingerprint(root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "captures").mkdir()
    (out / "training").mkdir()
    (out / "candidate_selection.json").write_bytes(manifest_path.read_bytes())
    for path in (list((root / "src/sqp").rglob("*.py")) + list((root / "configs").rglob("*.yaml"))
                 + [root / "scripts/feature_shadow.py"]):
        frozen = out / "frozen" / path.relative_to(root)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_bytes(path.read_bytes())
    records = []
    for league in sorted({c["league"] for c in candidates}):
        meta = _league_meta(league)
        selected = [c for c in candidates if c["league"] == league]
        path = root / "data/historical" / f"results_{league}.csv"
        raw_bytes = path.read_bytes()
        source_hash = hashlib.sha256(raw_bytes).hexdigest()
        if any(c["source_sha256"] != source_hash for c in selected):
            raise ValueError(f"{league}: historical source changed since discovery")
        archived = out / "training" / path.name
        archived.write_bytes(raw_bytes)
        raw = pd.read_csv(archived, dtype={"game_id": str})
        if pd.to_datetime(raw.date, utc=True).max() >= utc_now().normalize():
            raise ValueError("training history must end before today UTC")
        windows = {c["window"] for c in selected}
        if len(windows) != 1:
            raise ValueError("mixed windows in a league")
        dataset = build_research_dataset(raw, league, meta["family"], meta.get("league_params"),
                                         window=selected[0]["window"])
        for c in selected:
            fitted = fit_pair(dataset, c)
            filename = f"{league}_{c['target']}_{c['block']}.joblib"
            joblib.dump(fitted, out / filename)
            records.append({**c, "artifact": filename, "artifact_sha256": digest(out / filename),
                            "family": meta["family"], "n_train": fitted["n_train"],
                            "train_through": fitted["train_through"]})
            print(f"trained {c['id']}: {fitted['n_train']} rows", flush=True)
    if utc_now() >= begin or fingerprint(root) != code_hash:
        raise ValueError("training crossed start boundary or code changed")
    protocol = {
        "schema_version": 1, "status": "FROZEN_SHADOW_ONLY", "created_at": utc_now().isoformat(),
        "start": begin.isoformat(), "end_exclusive": finish.isoformat(),
        "code_config_sha256": code_hash, "selection_sha256": digest(manifest_path),
        "runtime_versions": runtime_versions(),
        "event_horizon_days": Settings().event_horizon_days,
        "discovery_report_sha256": digest(report_path), "candidates": records,
        "sampling": "All eligible first captures in fixed calendar window; no outcome-dependent stopping",
        "sample_size": "Determined by eligible fixtures and capture coverage; no power guarantee",
        "primary": "Paired loss vs learned baseline; Brier h2h or MAE total_score",
        "secondary": "Paired loss vs operational adapter; descriptive logloss and calibration for h2h",
        "alpha": 0.05, "comparisons": 2 * len(records), "bootstrap": 20000,
        "cluster": "UTC event date", "seed": 42,
        "inference": "Only at end; Bonferroni across all candidates and both comparators",
        "model_policy": "Frozen weights; prior-day sporting state updated from captured history",
        "capture_policy": "First successful capture before kickoff; UTC prior-day results only",
        "ties": "Exclude draws from binary h2h; keep scores for totals",
        "market_comparison": "NOT_VERIFIABLE without separately aligned timestamped odds",
        "promotion": False,
    }
    atomic_write_json(protocol, out / "protocol.json")
    (out / "protocol.sha256").write_text(digest(out / "protocol.json"), encoding="ascii")
    return protocol


def load_protocol(root: Path, experiment: Path) -> dict:
    if digest(experiment / "protocol.json") != (experiment / "protocol.sha256").read_text().strip():
        raise ValueError("protocol integrity mismatch")
    p = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    if p["status"] != "FROZEN_SHADOW_ONLY" or fingerprint(ROOT) != p["code_config_sha256"]:
        raise ValueError("experiment code/configuration changed; use frozen checkout")
    if p["runtime_versions"] != runtime_versions():
        raise ValueError("experiment dependency versions changed")
    return p


def capture(root: Path, experiment: Path, fixtures_path: Path) -> dict:
    """CSV fixtures: league,game_id,home,away,start_time,source. No result fields.

    IDs are source-scoped. Archives retain inputs and oriented participants.
    No remote requests, stakes, live model registry writes, or retrospective rows.
    """
    p = load_protocol(root, experiment)
    now = utc_now()
    raw = fixtures_path.read_bytes()
    from io import BytesIO
    fixtures = pd.read_csv(BytesIO(raw), dtype={"game_id": str})
    required = {"league", "game_id", "home", "away", "start_time", "source"}
    if set(fixtures) != required or fixtures.isna().any().any():
        raise ValueError("fixtures require exactly league,game_id,home,away,start_time,source")
    for col in required:
        if fixtures[col].astype(str).str.strip().eq("").any():
            raise ValueError("empty fixture field")
    if not fixtures.start_time.str.contains(r"(?:Z|[+-]\d\d:\d\d)$").all():
        raise ValueError("kickoff requires explicit timezone")
    starts = pd.to_datetime(fixtures.start_time, utc=True, errors="raise")
    if fixtures.duplicated(["league", "source", "game_id"]).any():
        raise ValueError("duplicate fixture identity")
    leagues = {c["league"] for c in p["candidates"]}
    eligible = (starts > now) & (starts >= pd.Timestamp(p["start"])) & (starts < pd.Timestamp(p["end_exclusive"]))
    if p["event_horizon_days"] > 0:
        eligible &= starts <= now + pd.Timedelta(days=p["event_horizon_days"])
    eligible &= fixtures.league.isin(leagues)
    fixtures = fixtures.loc[eligible].copy()
    fixtures["date"] = starts.loc[eligible].dt.strftime("%Y-%m-%d")
    batch = experiment / "captures" / f"batch_{now.strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:10]}"
    batch.mkdir()
    (batch / "fixtures.csv").write_bytes(raw)
    predictions = []
    for (league, source), group in fixtures.groupby(["league", "source"]):
        selected = [c for c in p["candidates"] if c["league"] == league]
        meta = _league_meta(league)
        history_path = root / "data/historical" / f"results_{league}.csv"
        history_bytes = history_path.read_bytes()
        history_hash = hashlib.sha256(history_bytes).hexdigest()
        (batch / f"results_{league}_{history_hash}.csv").write_bytes(history_bytes)
        history = pd.read_csv(BytesIO(history_bytes), dtype={"game_id": str})
        dates = pd.to_datetime(history.date, utc=True)
        history = history.loc[dates < now.normalize()]
        future = group[["date", "game_id", "home", "away"]]
        dataset = build_research_dataset(history, league, meta["family"], meta.get("league_params"),
                                         window=selected[0]["window"], fixtures=future)
        frame = dataset.frame.loc[dataset.frame.target_h2h.isna()].copy()
        indexed = group.set_index("game_id")
        for c in selected:
            path = experiment / c["artifact"]
            if digest(path) != c["artifact_sha256"]:
                raise ValueError("model integrity mismatch")
            fitted = joblib.load(path)
            x = design(frame, c["target"])
            values = {}
            for name, entry in fitted["pair"].items():
                model = entry["model"]
                values[name] = (model.predict_proba(x[entry["columns"]])[:, 1] if c["target"] == "h2h"
                                else model.predict(x[entry["columns"]]))
            for pos, (_, row) in enumerate(frame.iterrows()):
                game = indexed.loc[str(row.game_id)]
                cols = fitted["pair"]["candidate"]["columns"]
                predictions.append({
                    "candidate_id": c["id"], "league": league, "source": source,
                    "game_id": str(row.game_id), "date": row.date, "start_time": game.start_time,
                    "home": row.home, "away": row.away, "target": c["target"],
                    "baseline": float(values["baseline"][pos]), "candidate": float(values["candidate"][pos]),
                    "operational": float(row.base_home if c["target"] == "h2h" else row.base_total),
                    "inputs": {col: None if pd.isna(x.iloc[pos][col]) else float(x.iloc[pos][col]) for col in cols},
                    "history_sha256": history_hash, "artifact_sha256": c["artifact_sha256"],
                })
    captured = utc_now()
    # A long replay may cross kickoff. Such rows are never persisted as pregame.
    predictions = [r for r in predictions if pd.Timestamp(r["start_time"]) > captured]
    for row in predictions:
        row["captured_at"] = captured.isoformat()
    payload = {"captured_at": captured.isoformat(), "protocol_sha256": digest(experiment / "protocol.json"),
               "fixtures_sha256": hashlib.sha256(raw).hexdigest(), "predictions": predictions,
               "n_input": len(starts), "n_eligible_at_start": len(fixtures),
               "n_predictions": len(predictions)}
    # Strict JSON rejects accidental non-finite outputs before the atomic commit.
    json.dumps(payload, allow_nan=False)
    atomic_write_json(payload, batch / "predictions.json")
    return {"batch": str(batch), "n_predictions": len(predictions), "n_input": len(starts)}


def captured_rows(experiment: Path) -> list[dict]:
    rows = []
    protocol_hash = digest(experiment / "protocol.json")
    for path in sorted((experiment / "captures").glob("batch_*/predictions.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["protocol_sha256"] != protocol_hash:
            raise ValueError("capture belongs to a different protocol")
        rows.extend(payload["predictions"])
    # First successful pregame capture, independent of outcomes or later accuracy.
    first: dict[tuple[str, str, str], dict] = {}
    for row in sorted(rows, key=lambda r: r["captured_at"]):
        if pd.Timestamp(row["captured_at"]) >= pd.Timestamp(row["start_time"]):
            raise ValueError("post-start row in capture archive")
        key = (row["candidate_id"], row["source"], row["game_id"])
        first.setdefault(key, row)
    return list(first.values())


def capture_store(root: Path, experiment: Path) -> dict:
    """Read fixtures already fetched by the normal pipeline; no API quota use."""
    p = load_protocol(root, experiment)
    now = utc_now()
    frames = []
    seen = {(r["league"], r["source"], r["game_id"]) for r in captured_rows(experiment)}
    for league in sorted({c["league"] for c in p["candidates"]}):
        pattern = f"odds_tennis_{league}_*.csv" if league in {"atp", "wta"} else f"odds_{league}_*.csv"
        for path in sorted((root / "data/odds").glob(pattern)):
            d = pd.read_csv(path, dtype={"event_id": str})
            if d.empty:
                continue
            times = pd.to_datetime(d.commence_time, utc=True, errors="raise")
            obtained = pd.to_datetime(d.captured_at, utc=True, errors="raise")
            d = d.loc[(times > now) & (obtained <= now)].copy()
            if d.empty:
                continue
            d["_observed"] = obtained.loc[d.index]
            d = d.rename(columns={"event_id": "game_id", "commence_time": "start_time"})
            d["league"], d["source"] = league, "odds_api"
            frames.append(d[["league", "game_id", "home", "away", "start_time", "source", "_observed"]])
    cols = ["league", "game_id", "home", "away", "start_time", "source"]
    if frames:
        fixtures = pd.concat(frames).sort_values("_observed").drop_duplicates(["league", "source", "game_id"], keep="last")
        fixtures = fixtures.loc[[tuple(r) not in seen for r in fixtures[["league", "source", "game_id"]].to_numpy()], cols]
        start = pd.to_datetime(fixtures.start_time, utc=True)
        fixtures = fixtures.loc[(start >= pd.Timestamp(p["start"])) & (start < pd.Timestamp(p["end_exclusive"]))]
        if p["event_horizon_days"] > 0:
            fixtures = fixtures.loc[start.loc[fixtures.index] <= now + pd.Timedelta(days=p["event_horizon_days"])]
    else:
        fixtures = pd.DataFrame(columns=cols)
    if fixtures.empty:
        return {"n_predictions": 0, "n_input": 0, "reason": "no new eligible fixtures in local odds store"}
    inputs = experiment / "fixture_inputs"
    inputs.mkdir(exist_ok=True)
    path = inputs / f"fixtures_{uuid4().hex}.csv"
    fixtures.to_csv(path, index=False)
    return capture(root, experiment, path)


def evaluate(root: Path, experiment: Path, outcomes_path: Path) -> dict:
    """Fixed-end evaluation requires explicit source-scoped outcomes, never fuzzy joins."""
    p = load_protocol(root, experiment)
    if utc_now() < pd.Timestamp(p["end_exclusive"]):
        raise ValueError("fixed evaluation window has not ended")
    outcomes = pd.read_csv(outcomes_path, dtype={"game_id": str})
    required = {"league", "source", "game_id", "home", "away", "home_score", "away_score", "start_time"}
    if set(outcomes) != required or outcomes.isna().any().any():
        raise ValueError("outcomes require exact schema with final scores and actual start_time")
    if outcomes.duplicated(["league", "source", "game_id"]).any():
        raise ValueError("ambiguous outcomes")
    if not np.isfinite(outcomes[["home_score", "away_score"]].to_numpy(float)).all():
        raise ValueError("nonfinite outcomes")
    index = outcomes.set_index(["league", "source", "game_id"])
    rows = captured_rows(experiment)
    reports = []
    for c in p["candidates"]:
        matched, excluded = [], 0
        captured = [r for r in rows if r["candidate_id"] == c["id"]]
        for row in captured:
            key = (row["league"], row["source"], row["game_id"])
            if key not in index.index:
                excluded += 1
                continue
            result = index.loc[key]
            if {row["home"], row["away"]} != {result.home, result.away} or pd.Timestamp(result.start_time) != pd.Timestamp(row["start_time"]):
                excluded += 1
                continue
            hs, aws = (float(result.home_score), float(result.away_score))
            if row["home"] != result.home:
                hs, aws = aws, hs
            if c["target"] == "h2h" and hs == aws:
                excluded += 1
                continue
            matched.append({**row, "y": float(hs > aws) if c["target"] == "h2h" else hs + aws})
        d = pd.DataFrame(matched)
        report = {"candidate_id": c["id"], "n_captured": len(captured), "n_matched": len(d), "n_excluded": excluded}
        if d.empty or d.date.nunique() < 2:
            reports.append({**report, "status": "NOT_VERIFIABLE: insufficient matched dates"})
            continue
        losses = {name: (d[name] - d.y).to_numpy() ** 2 if c["target"] == "h2h"
                  else np.abs((d[name] - d.y).to_numpy()) for name in ("candidate", "baseline", "operational")}
        contrasts = {}
        for name in ("baseline", "operational"):
            delta = losses["candidate"] - losses[name]
            lo, hi = cluster_bootstrap_ci(delta, d.date.to_numpy(), n_boot=p["bootstrap"],
                                          seed=p["seed"], alpha=p["alpha"] / p["comparisons"])
            contrasts[name] = {"mean_delta": float(delta.mean()), "lo": lo, "hi": hi}
        reports.append({**report, "status": "MEASURED_NO_AUTOMATIC_PROMOTION", "contrasts": contrasts,
                        "mean_loss": {k: float(v.mean()) for k, v in losses.items()},
                        "calibration": {name: calibration_report(d[name], d.y) for name in losses}
                        if c["target"] == "h2h" else None})
    return {"protocol_sha256": digest(experiment / "protocol.json"), "outcomes_sha256": digest(outcomes_path),
            "reports": reports, "promotion": False,
            "limitations": ["No market comparison", "Missing captures/results can bias coverage",
                            "Date bootstrap does not model serial dependence across dates"]}
