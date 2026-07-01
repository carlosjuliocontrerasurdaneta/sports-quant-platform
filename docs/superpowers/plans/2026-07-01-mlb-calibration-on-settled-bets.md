# MLB Calibration on Settled Bets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train per-(league, market) probability calibrators on the settled *live* bets (opening-anchored) instead of the closing-anchored backtest, so MLB's real overconfidence becomes learnable — reusing the existing ECE+Brier+monotone gate, staging, and explicit promotion.

**Architecture:** Add one data-source module that projects `data/bets/settled_*.csv` onto the schema `train_market_calibrators` already consumes, plus a thin staging helper. Redirect the daily staging retrain and the manual CLI to that source. The calibration engine, gates, staging, and promotion are untouched; only the *training data source* changes.

**Tech Stack:** Python 3, pandas, scikit-learn (isotonic), scipy (beta), pytest. Tests run with `PYTHONPATH=src`.

## Global Constraints

- Betting-output language: "probabilidad estimada", never certainties or profit guarantees; separate estimated probability, implied probability, edge, expected ROI estimate, realized ROI.
- Do NOT lower `min_n` (default 40); a market with n<40 stays no-op (honest).
- Do NOT touch the calibration engine, the ECE+Brier+monotone gate, WNBA, tennis, or the promotion step. Promotion stays a deliberate, separate, MLB-only act.
- Temporal validation only: the calibrator's split must order by real game date, never row order (leakage guard).
- Type hints, explicit exceptions, small functions, tests for core logic.
- `train_market_calibrators` consumes columns exactly: `league, market, date, estimated_probability, result`.

---

### Task 1: Settled-bets training-data source

**Files:**
- Create: `src/sqp/calibration/data.py`
- Test: `tests/test_calibration_data.py`

**Interfaces:**
- Consumes: `sqp.audit.report.load_all_settled(bets_dir: Path) -> pd.DataFrame` (returns concatenated `settled_*.csv` with a `league` column added; carries `market, estimated_probability, result, game_date, generated_at`).
- Produces:
  - `TRAINING_COLS: list[str] = ["league", "market", "date", "estimated_probability", "result"]`
  - `load_settled_training_history(bets_dir: Path | None = None) -> pd.DataFrame` with columns `TRAINING_COLS`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calibration_data.py`:

```python
import pandas as pd
import pytest

from sqp.calibration.data import TRAINING_COLS, load_settled_training_history


def _write_settled(bets_dir, name, rows):
    bets_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(bets_dir / f"settled_{name}.csv", index=False)


def test_projects_to_training_schema(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.58, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
        {"market": "spreads", "estimated_probability": 0.61, "result": "loss",
         "game_date": "2026-06-21", "generated_at": "2026-06-21T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert list(out.columns) == TRAINING_COLS
    assert out.loc[0, "league"] == "mlb"
    assert out.loc[0, "market"] == "h2h"
    assert out.loc[0, "date"] == "2026-06-20"
    assert out.loc[0, "estimated_probability"] == pytest.approx(0.58)
    assert set(out["result"]) == {"win", "loss"}


def test_date_falls_back_to_generated_at(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.55, "result": "win",
         "game_date": "", "generated_at": "2026-06-22T09:30:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-22"


def test_drops_rows_without_estimated_probability(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.55, "result": "win",
         "game_date": "2026-06-20", "generated_at": ""},
        {"market": "h2h", "estimated_probability": "", "result": "loss",
         "game_date": "2026-06-21", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1
    assert out.loc[0, "result"] == "win"


def test_date_tracks_game_date_not_row_order(tmp_path):
    # Row inserted later has an EARLIER game_date. `date` must reflect the game
    # date (so the downstream temporal sort is correct), not the row position.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.60, "result": "loss",
         "game_date": "2026-06-25", "generated_at": ""},
        {"market": "h2h", "estimated_probability": 0.40, "result": "win",
         "game_date": "2026-06-10", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-25"
    assert out.loc[1, "date"] == "2026-06-10"


def test_empty_or_missing_dir_is_empty_frame(tmp_path):
    out = load_settled_training_history(tmp_path / "nope")
    assert out.empty
    assert list(out.columns) == TRAINING_COLS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sqp.calibration.data'`.

- [ ] **Step 3: Write the implementation**

Create `src/sqp/calibration/data.py`:

```python
"""Training-data source for probability calibration.

The calibrator must learn from the probabilities the pipeline ACTUALLY served
(opening-anchored, from data/bets/settled_*.csv), not from the closing-anchored
backtest replay (build_pick_history). Training on the backtest makes the live
overconfidence unlearnable, because live probabilities are anchored to the
opening line while the backtest is anchored to the close. This projects the
settled bets onto the schema train_market_calibrators expects.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.report import load_all_settled
from sqp.config import ROOT

TRAINING_COLS = ["league", "market", "date", "estimated_probability", "result"]


def load_settled_training_history(bets_dir: Path | None = None) -> pd.DataFrame:
    """Project settled live bets onto the calibration-training schema
    (league, market, date, estimated_probability, result).

    ``date`` is the real game date (``game_date``, falling back to
    ``generated_at``) truncated to YYYY-MM-DD, so the temporal split in
    ``train_calibration`` orders by when the game happened -- never by row order,
    which could otherwise place a validation game before its training games and
    leak. Rows without an ``estimated_probability`` are dropped (nothing to
    calibrate); push/void rows are kept and filtered downstream by
    ``train_market_calibrators``. Returns an empty frame with ``TRAINING_COLS``
    when there are no settled bets.
    """
    bets_dir = bets_dir or (ROOT / "data" / "bets")
    settled = load_all_settled(bets_dir)
    if settled.empty:
        return pd.DataFrame(columns=TRAINING_COLS)

    out = pd.DataFrame(index=settled.index)
    out["league"] = settled["league"].astype(str) if "league" in settled else ""
    out["market"] = settled["market"].astype(str) if "market" in settled else ""
    gd = (settled["game_date"].astype(str) if "game_date" in settled
          else pd.Series("", index=settled.index))
    gen = (settled["generated_at"].astype(str) if "generated_at" in settled
           else pd.Series("", index=settled.index))
    out["date"] = gd.where(gd.str.len() >= 10, gen).str[:10]
    if "estimated_probability" in settled:
        out["estimated_probability"] = pd.to_numeric(
            settled["estimated_probability"], errors="coerce")
    else:
        out["estimated_probability"] = pd.Series(float("nan"), index=settled.index)
    out["result"] = settled["result"].astype(str) if "result" in settled else ""
    out = out.dropna(subset=["estimated_probability"]).reset_index(drop=True)
    return out[TRAINING_COLS]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Add the end-to-end "gate still governs" test**

Append to `tests/test_calibration_data.py`:

```python
def test_overconfident_settled_feeds_trainable_history(tmp_path, monkeypatch):
    # An overconfident MLB h2h market (est ~0.70, wins ~40%) projected from
    # settled must feed train_market_calibrators and produce a STAGED candidate,
    # proving the new source integrates with the existing gate/staging machinery.
    import numpy as np
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(0)
    n = 200
    wins = rng.random(n) < 0.40  # true ~40% vs claimed ~70% -> overconfident
    rows = [{"market": "h2h", "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path, "mlb", rows)

    hist = load_settled_training_history(tmp_path)
    results = cal.train_market_calibrators(hist, min_n=40)  # staging=True default
    mlb = next(r for r in results if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert mlb["persisted"] is True  # a calibrator that lowers OOS Brier was kept
    # Staged, NOT live: nothing was promoted into the live registry.
    assert (tmp_path / "models" / "staging").exists()
    assert cal._load_method_registry(staging=False) == {}
```

- [ ] **Step 6: Run the full new test file**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py -q`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add src/sqp/calibration/data.py tests/test_calibration_data.py
git commit -m "feat(calibration): entrenar sobre settled reales (fuente de datos)

Nueva fuente load_settled_training_history: proyecta data/bets/settled_*.csv
al esquema de train_market_calibrators. date = game_date (fallback generated_at)
para que el split temporal ordene por fecha real y no filtre futuro.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Manual CLI trains from settled by default

**Files:**
- Modify: `scripts/train_calibration.py:24` (imports) and `scripts/train_calibration.py:31-43` (arg + source selection)

**Interfaces:**
- Consumes: `load_settled_training_history` (Task 1); existing `build_pick_history`, `load_pick_history`, `train_market_calibrators`, `MODELS_DIR`.
- Produces: CLI flag `--source {settled,backtest}` (default `settled`).

- [ ] **Step 1: Add the import**

In `scripts/train_calibration.py`, change line 24 from:

```python
from sqp.audit.patterns import build_pick_history, load_pick_history
```

to:

```python
from sqp.audit.patterns import build_pick_history, load_pick_history
from sqp.calibration.data import load_settled_training_history
```

- [ ] **Step 2: Add the `--source` argument**

In `main()`, after the `--rebuild` argument block (line 35-36), add:

```python
    ap.add_argument("--source", choices=["settled", "backtest"], default="settled",
                    help="Datos de entrenamiento: 'settled' (apuestas liquidadas "
                         "en vivo, ancladas a la apertura -- corrige el desajuste "
                         "train/serve) o 'backtest' (historial anclado al cierre).")
```

- [ ] **Step 3: Select the source**

Replace the current source block (lines 39-43):

```python
    hist = build_pick_history(write=True) if args.rebuild else load_pick_history()
    if hist.empty:
        log.warning("pick_history vacio: corre scripts/build_pick_history.py "
                    "(o usa --rebuild) antes de calibrar.")
        return 1
```

with:

```python
    if args.source == "settled":
        hist = load_settled_training_history()
        empty_msg = ("no hay apuestas liquidadas (data/bets/settled_*.csv): corre "
                     "SETTLE_ALL.bat antes de calibrar sobre settled.")
    else:
        hist = build_pick_history(write=True) if args.rebuild else load_pick_history()
        empty_msg = ("pick_history vacio: corre scripts/build_pick_history.py "
                     "(o usa --rebuild) antes de calibrar.")
    if hist.empty:
        log.warning(empty_msg)
        return 1
```

- [ ] **Step 4: Verify nothing else imports break**

Run: `PYTHONPATH=src python -c "import ast,sys; ast.parse(open('scripts/train_calibration.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Smoke run against real data (staging-only, safe)**

Run: `PYTHONPATH=src python scripts/train_calibration.py --source settled --min-n 40`
Expected: a table `liga mercado n_val ECE_antes ECE_mejor delta metodo` including `mlb` rows; the live registry is NOT modified (staging-only). If MLB markets appear with a positive `delta` and a method other than `NINGUNO`, a candidate was staged. This is diagnostic; nothing is live until promotion.

- [ ] **Step 6: Confirm the live registry is still empty**

Run: `PYTHONPATH=src python -c "from sqp.calibration.calibrator import _load_method_registry; print('LIVE:', _load_method_registry())"`
Expected: `LIVE: {}` (nothing promoted; staging only).

- [ ] **Step 7: Commit**

```bash
git add scripts/train_calibration.py
git commit -m "feat(calibration): CLI --source settled|backtest (default settled)

train_calibration.py entrena por defecto sobre las apuestas liquidadas en vivo
(ancladas a la apertura). --source backtest conserva el camino anterior para
diagnostico. Staging-only; no promueve nada.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Daily staging retrain uses the settled source

**Files:**
- Modify: `src/sqp/calibration/data.py` (add staging helper)
- Modify: `scripts/run_all.py:22` (import) and `scripts/run_all.py:198-215` (wire the helper)
- Test: `tests/test_calibration_data.py` (append helper tests)

**Interfaces:**
- Consumes: `load_settled_training_history` (Task 1); `train_market_calibrators`; a `settings` object exposing `.calibration_enabled: bool`.
- Produces: `stage_calibrators_from_settled(settings) -> list[dict]` (one summary dict per (league, market); `[]` when disabled or no settled data).

- [ ] **Step 1: Write the failing helper tests**

Append to `tests/test_calibration_data.py`:

```python
def test_stage_helper_disabled_returns_empty():
    from types import SimpleNamespace
    from sqp.calibration.data import stage_calibrators_from_settled
    assert stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=False)) == []


def test_stage_helper_empty_settled_returns_empty(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    monkeypatch.setattr(cdata, "ROOT", tmp_path)  # empty data/bets
    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    assert out == []


def test_stage_helper_trains_from_settled(tmp_path, monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cdata, "ROOT", tmp_path)
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(1)
    wins = rng.random(200) < 0.40
    rows = [{"market": "h2h", "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path / "data" / "bets", "mlb", rows)

    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    mlb = next(r for r in out if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert cal._load_method_registry(staging=False) == {}  # staged, not live
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py -q`
Expected: FAIL — `ImportError: cannot import name 'stage_calibrators_from_settled'`.

- [ ] **Step 3: Implement the staging helper**

Append to `src/sqp/calibration/data.py`:

```python
def stage_calibrators_from_settled(settings) -> list[dict]:
    """Stage per-(league, market) calibrator CANDIDATES from the settled live bets.

    Trains on the opening-anchored settled outcomes (see
    ``load_settled_training_history``) into STAGING only -- promotion into the
    live registry stays a deliberate, separate step (scripts/promote_calibration).
    Returns ``train_market_calibrators``' per-group summaries, or ``[]`` when
    calibration is disabled or there are no settled bets yet.
    """
    from sqp.calibration.calibrator import train_market_calibrators

    if not getattr(settings, "calibration_enabled", False):
        return []
    hist = load_settled_training_history()
    if hist.empty:
        return []
    return train_market_calibrators(hist)  # staging=True by default
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py -q`
Expected: PASS (9 tests total).

- [ ] **Step 5: Wire the helper into the daily run**

In `scripts/run_all.py`, add the import near line 22 (next to the existing calibrator import):

```python
from sqp.calibration.data import stage_calibrators_from_settled
```

Then replace the retrain block (lines 199-213), currently:

```python
            hist = build_pick_history(settings, write=True)
            log.info("Historial consolidado de picks: %d picks", len(hist))
            # Retrain per-(league, market) calibrators as CANDIDATES for NEXT runs.
            # Today's picks were already generated above with the prior LIVE models,
            # so this can never leak the current day into its own calibrator. The
            # retrain writes to STAGING only -- it never promotes a model into
            # production in the same cycle (that is a deliberate, separate step:
            # scripts/promote_calibration.py), so a degenerate daily fit cannot
            # auto-install itself. Only when enabled.
            if settings.calibration_enabled and not hist.empty:
                cal = train_market_calibrators(hist)  # staging=True by default
                n_ok = sum(1 for r in cal if r.get("trained"))
                log.info("Calibradores reentrenados a STAGING: %d de %d grupos "
                         "(sin promover; usa scripts/promote_calibration.py para "
                         "revisar y promover)", n_ok, len(cal))
```

with:

```python
            hist = build_pick_history(settings, write=True)
            log.info("Historial consolidado de picks: %d picks", len(hist))
            # Retrain per-(league, market) calibrators as CANDIDATES for NEXT runs.
            # Trains on the SETTLED live bets (opening-anchored), NOT the
            # closing-anchored backtest above: the pipeline serves opening-anchored
            # probabilities, so only settled outcomes make live overconfidence
            # learnable. Today's picks were already generated with the prior LIVE
            # models, so this cannot leak the current day into its own calibrator.
            # STAGING only -- promotion is a deliberate, separate step
            # (scripts/promote_calibration.py), so a degenerate daily fit cannot
            # auto-install itself. Only when enabled.
            cal = stage_calibrators_from_settled(settings)
            if cal:
                n_ok = sum(1 for r in cal if r.get("trained"))
                log.info("Calibradores reentrenados a STAGING desde settled: %d de "
                         "%d grupos (sin promover; usa scripts/promote_calibration.py "
                         "para revisar y promover)", n_ok, len(cal))
```

Note: `build_pick_history(settings, write=True)` stays — it still refreshes `data/processed/pick_history.csv` for the dashboard/patterns. Only the calibrator's input changed.

- [ ] **Step 6: Verify run_all.py parses and imports**

Run: `PYTHONPATH=src python -c "import ast; ast.parse(open('scripts/run_all.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 7: Run the full calibration test suite (regression check)**

Run: `PYTHONPATH=src pytest tests/test_calibration_data.py tests/test_calibration_live.py -q`
Expected: PASS (all green — the existing gate/staging tests must still pass with the new source wired in).

- [ ] **Step 8: Commit**

```bash
git add src/sqp/calibration/data.py scripts/run_all.py tests/test_calibration_data.py
git commit -m "feat(calibration): staging diario entrena sobre settled reales

run_all.py stagea calibradores desde stage_calibrators_from_settled (apuestas
liquidadas en vivo) en vez del backtest anclado al cierre. build_pick_history
sigue refrescando el dashboard. Staging-only; promocion sigue siendo explicita.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run: `PYTHONPATH=src pytest tests/ -q`
Expected: PASS (no regressions). Record the count.

- [ ] **Step 2: Confirm live behavior is unchanged (registry still empty)**

Run: `PYTHONPATH=src python -c "from sqp.calibration.calibrator import _load_method_registry; print('LIVE:', _load_method_registry())"`
Expected: `LIVE: {}` — no calibrator is live until an explicit, reviewed promotion. The daily run only stages.

---

## Post-plan operational note (NOT a code task)

After this ships and a daily run (or the manual CLI) has staged MLB candidates,
promotion is the human-reviewed step:

1. Review staged candidates: `PYTHONPATH=src python scripts/promote_calibration.py` (dry-run).
2. Promote only MLB markets whose OOS Brier improved:
   `promote_calibrators(["mlb_h2h", "mlb_spreads", "mlb_totals"])` (or the subset that passed).
3. Leave WNBA (calibrated) and tennis (small n) unpromoted → they stay no-op.

Improvement is verifiable only **forward** (on future settled bets); this reduces
expected overconfidence bleed, it does not guarantee positive ROI.

---

## Self-Review

- **Spec coverage:** (1) new data source → Task 1. (2) redirect CLI → Task 2. (3) redirect daily staging → Task 3. (4) gate/staging/promotion unchanged → asserted in Task 1 Step 5 and Task 3 Step 7. (5) temporal-order guard → Task 1 `test_date_tracks_game_date_not_row_order`. (6) empty/NaN edge cases → Task 1 Steps 1/5. (7) min_n unchanged, MLB-only promotion → Global Constraints + Post-plan note. (8) full verification → Task 4. No gaps.
- **Placeholder scan:** none — every code step shows full code and exact commands.
- **Type consistency:** `load_settled_training_history(bets_dir=None) -> DataFrame[TRAINING_COLS]` and `stage_calibrators_from_settled(settings) -> list[dict]` are used consistently across tasks; `train_market_calibrators(hist, min_n=40)` matches its real signature; `_load_method_registry(staging=...)` matches `calibrator.py`.
