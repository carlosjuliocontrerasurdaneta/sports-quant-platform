# Historial mejorado del dashboard + auto-open interactivo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ampliar la pestaña Historial del dashboard (desglose por fecha/deporte/línea/home/away + tarjetas de totales picks/cerrados/wins/losses, ocultando picks pasados sin cerrar) y abrir el dashboard automáticamente solo en sesión interactiva.

**Architecture:** La liquidación persiste `home`/`away`/`game_date` en `settled_*.csv` (approach A); un script backfillea los liquidados pasados desde los snapshots de cuotas. El dashboard une candidatos accionables abiertos + liquidados en `load_history`, filtra los pasados sin cerrar en `visible_history`, y el `.bat` diario abre el `report_latest.html` solo si hay sesión interactiva.

**Tech Stack:** Python 3, pandas, HTML/JS embebido (sin assets externos), batch (cmd) en Windows.

## Global Constraints

- Tests se corren con: `PYTHONPATH=src pytest tests/ -q` (Windows + PowerShell).
- Lenguaje de apuestas: separar "probabilidad estimada", "edge estimado" y "ROI realizado"; nunca certezas ni profit garantizado (`betting-output-rules`).
- No borrar ni mutar datos crudos: a `settled_*.csv` solo se AÑADEN columnas; `pick_history.csv` no se toca (`data-integrity-rules`).
- No escanear `data/` completo: usar encabezados / `usecols` / muestras.
- Columnas nuevas en settled, en este orden al final: `home`, `away`, `game_date` (`YYYY-MM-DD`).
- Type hints, funciones pequeñas, excepciones explícitas (`coding-standards`).

---

### Task 1: Persistir home/away/game_date en la liquidación (ligas con scores)

**Files:**
- Modify: `src/sqp/settlement/runner.py` (añadir `_event_meta_map`, `_attach_event_meta`; usarlos en `fetch_and_settle`)
- Test: `tests/settlement/test_settle_enrichment.py`

**Interfaces:**
- Consumes: `settle_candidates(candidates, scores)` (existente) → DataFrame con columna `event_id`.
- Produces:
  - `_event_meta_map(raw: list[dict]) -> dict[str, dict]` — `event_id -> {"home","away","game_date"}` desde entradas crudas de `/scores`.
  - `_attach_event_meta(settled: pd.DataFrame, meta: dict[str, dict]) -> pd.DataFrame` — añade columnas `home`,`away`,`game_date` por `event_id` (vacío si falta).

- [ ] **Step 1: Write the failing test**

```python
# tests/settlement/test_settle_enrichment.py
import pandas as pd
from sqp.settlement.runner import _event_meta_map, _attach_event_meta


def test_event_meta_map_extracts_teams_and_date():
    raw = [{"id": "evt1", "home_team": "NYY", "away_team": "BOS",
            "commence_time": "2026-06-25T23:05:00Z", "completed": True,
            "scores": [{"name": "NYY", "score": "5"}, {"name": "BOS", "score": "3"}]}]
    meta = _event_meta_map(raw)
    assert meta["evt1"] == {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}


def test_attach_event_meta_adds_columns_by_event_id():
    settled = pd.DataFrame([{"event_id": "evt1", "market": "h2h", "result": "win"},
                            {"event_id": "missing", "market": "h2h", "result": "loss"}])
    meta = {"evt1": {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}}
    out = _attach_event_meta(settled, meta)
    assert out.loc[0, "home"] == "NYY" and out.loc[0, "away"] == "BOS"
    assert out.loc[0, "game_date"] == "2026-06-25"
    assert out.loc[1, "home"] == ""  # unmatched event_id -> empty, not error


def test_attach_event_meta_empty_df_is_noop():
    out = _attach_event_meta(pd.DataFrame(), {})
    assert out.empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/settlement/test_settle_enrichment.py -q`
Expected: FAIL with `ImportError: cannot import name '_event_meta_map'`.

- [ ] **Step 3: Add the helpers to `runner.py`**

Insert after `_scores_map` (around line 31):

```python
def _event_meta_map(raw: list[dict]) -> dict[str, dict]:
    """event_id -> {home, away, game_date} from raw /scores entries.

    game_date is the commence date (YYYY-MM-DD); empty when the API omits it.
    """
    out: dict[str, dict] = {}
    for s in raw:
        eid = s.get("id")
        if not eid:
            continue
        out[str(eid)] = {
            "home": s.get("home_team", "") or "",
            "away": s.get("away_team", "") or "",
            "game_date": str(s.get("commence_time", ""))[:10],
        }
    return out


def _attach_event_meta(settled: pd.DataFrame, meta: dict[str, dict]) -> pd.DataFrame:
    """Add home/away/game_date columns to settled rows, keyed by event_id.

    Unmatched event_ids get empty strings (cosmetic; backfill fills them later).
    """
    if settled.empty:
        return settled
    settled = settled.copy()
    for col in ("home", "away", "game_date"):
        settled[col] = settled["event_id"].map(
            lambda e: meta.get(str(e), {}).get(col, ""))
    return settled
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/settlement/test_settle_enrichment.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire into `fetch_and_settle`**

Replace the body of `fetch_and_settle` (lines 144-148) so the raw scores are kept and the meta attached:

```python
    cands = pd.read_csv(cand_path)
    client = client or OddsAPIClient(settings.odds_api_key, settings.regions)
    raw = client.fetch_scores(meta["sport_key"], days_from=days_from)
    scores = _scores_map(raw)
    settled = settle_candidates(cands, scores)
    settled = _attach_event_meta(settled, _event_meta_map(raw))
    return _persist_settled(league, settled)
```

- [ ] **Step 6: Run the full settlement test module**

Run: `PYTHONPATH=src pytest tests/settlement/ -q`
Expected: PASS (no regressions; `_persist_settled` reconciles the new columns via its union-of-columns logic).

- [ ] **Step 7: Commit**

```bash
git add src/sqp/settlement/runner.py tests/settlement/test_settle_enrichment.py
git commit -m "feat(settle): persist home/away/game_date on settled bets (scores leagues)"
```

---

### Task 2: Persistir home/away/game_date en la liquidación de tenis

**Files:**
- Modify: `src/sqp/settlement/runner.py` (`_settle_tennis`)
- Test: `tests/settlement/test_settle_enrichment.py` (añadir caso)

**Interfaces:**
- Consumes: `_attach_event_meta` (Task 1); `preds` DataFrame con columnas `event_id`, `home`, `away`, `start_time`.
- Produces: filas liquidadas de tenis con `home`/`away`/`game_date` pobladas.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/settlement/test_settle_enrichment.py
def test_tennis_meta_from_predictions(monkeypatch, tmp_path):
    import pandas as pd
    from sqp.settlement import runner
    preds = pd.DataFrame([{"event_id": "t1", "home": "Alcaraz", "away": "Sinner",
                           "start_time": "2026-06-25T12:00:00Z"}])
    meta = {str(r.event_id): {"home": str(r.home), "away": str(r.away),
                              "game_date": str(getattr(r, "start_time", ""))[:10]}
            for r in preds.itertuples()}
    settled = pd.DataFrame([{"event_id": "t1", "market": "h2h", "result": "win"}])
    out = runner._attach_event_meta(settled, meta)
    assert out.loc[0, "home"] == "Alcaraz" and out.loc[0, "away"] == "Sinner"
    assert out.loc[0, "game_date"] == "2026-06-25"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/settlement/test_settle_enrichment.py::test_tennis_meta_from_predictions -q`
Expected: FAIL only if the mapping/attach is wrong. (It exercises `_attach_event_meta` with a tennis-shaped meta; the real wiring is Step 3.)

- [ ] **Step 3: Wire meta into `_settle_tennis`**

Replace the tail of `_settle_tennis` (lines 126-128) with:

```python
    scores = tennis_scores_map(preds, results)
    settled = settle_candidates(cands, scores)
    meta = {str(r.event_id): {"home": str(r.home), "away": str(r.away),
                              "game_date": str(getattr(r, "start_time", ""))[:10]}
            for r in preds.itertuples()}
    settled = _attach_event_meta(settled, meta)
    return _persist_settled(league, settled)
```

- [ ] **Step 4: Run the settlement tests**

Run: `PYTHONPATH=src pytest tests/settlement/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sqp/settlement/runner.py tests/settlement/test_settle_enrichment.py
git commit -m "feat(settle): persist home/away/game_date on settled tennis bets"
```

---

### Task 3: Backfill de home/away/game_date en liquidados pasados

**Files:**
- Create: `src/sqp/settlement/backfill_teams.py`
- Create: `scripts/backfill_settled_teams.py`
- Test: `tests/settlement/test_backfill_teams.py`

**Interfaces:**
- Produces:
  - `teams_from_odds(odds_dir: Path, league: str) -> dict[str, dict]` — `event_id -> {"home","away","game_date"}` desde `odds_<league>_*.csv`.
  - `backfill_settled_file(settled_path: Path, meta: dict[str, dict]) -> tuple[int, int]` — rellena filas con `home` vacío; devuelve `(filled, unresolved)`. Idempotente.

- [ ] **Step 1: Write the failing test**

```python
# tests/settlement/test_backfill_teams.py
import pandas as pd
from sqp.settlement.backfill_teams import teams_from_odds, backfill_settled_file


def test_teams_from_odds_reads_event_meta(tmp_path):
    odds = tmp_path
    pd.DataFrame([
        {"captured_at": "2026-06-25T09:00:00Z", "event_id": "evt1",
         "commence_time": "2026-06-25T23:05:00Z", "home": "NYY", "away": "BOS",
         "market": "h2h", "outcome": "NYY", "point": "", "price_decimal": 1.9,
         "bookmaker": "x"},
    ]).to_csv(odds / "odds_mlb_202606.csv", index=False)
    meta = teams_from_odds(odds, "mlb")
    assert meta["evt1"] == {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}


def test_backfill_fills_only_empty_rows_and_is_idempotent(tmp_path):
    path = tmp_path / "settled_mlb.csv"
    pd.DataFrame([
        {"event_id": "evt1", "market": "h2h", "result": "win", "home": "", "away": "", "game_date": ""},
        {"event_id": "evt2", "market": "h2h", "result": "loss", "home": "LAD", "away": "SF", "game_date": "2026-06-24"},
    ]).to_csv(path, index=False)
    meta = {"evt1": {"home": "NYY", "away": "BOS", "game_date": "2026-06-25"}}
    filled, unresolved = backfill_settled_file(path, meta)
    assert (filled, unresolved) == (1, 0)
    df = pd.read_csv(path).fillna("")
    assert df.loc[0, "home"] == "NYY" and df.loc[1, "home"] == "LAD"  # existing untouched
    # second run is a no-op
    assert backfill_settled_file(path, meta) == (0, 0)


def test_backfill_reports_unresolved(tmp_path):
    path = tmp_path / "settled_mlb.csv"
    pd.DataFrame([{"event_id": "ghost", "market": "h2h", "result": "win",
                   "home": "", "away": "", "game_date": ""}]).to_csv(path, index=False)
    filled, unresolved = backfill_settled_file(path, {})
    assert (filled, unresolved) == (0, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/settlement/test_backfill_teams.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sqp.settlement.backfill_teams'`.

- [ ] **Step 3: Implement the backfill module**

```python
# src/sqp/settlement/backfill_teams.py
"""Backfill home/away/game_date on already-settled bets from captured odds.

The odds snapshots (data/odds/odds_<league>_*.csv) carry the same The Odds API
event_id as settled bets, so the join is exact. Idempotent: only empty cells are
filled; existing values are preserved. Reads no API (stored data only).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd


def teams_from_odds(odds_dir: Path, league: str) -> dict[str, dict]:
    """event_id -> {home, away, game_date} from odds_<league>_*.csv snapshots."""
    out: dict[str, dict] = {}
    for f in sorted(odds_dir.glob(f"odds_{league}_*.csv")):
        df = pd.read_csv(f, usecols=lambda c: c in ("event_id", "home", "away", "commence_time"))
        for r in df.itertuples():
            eid = str(r.event_id)
            if eid in out:
                continue
            out[eid] = {"home": str(r.home), "away": str(r.away),
                        "game_date": str(r.commence_time)[:10]}
    return out


def backfill_settled_file(settled_path: Path, meta: dict[str, dict]) -> tuple[int, int]:
    """Fill empty home/away/game_date rows in one settled file. Returns
    (filled, unresolved). Writes only if something changed (idempotent)."""
    df = pd.read_csv(settled_path).fillna("")
    if df.empty:
        return 0, 0
    for col in ("home", "away", "game_date"):
        if col not in df.columns:
            df[col] = ""
    filled = unresolved = 0
    for i in df.index:
        if str(df.at[i, "home"]).strip():
            continue
        m = meta.get(str(df.at[i, "event_id"]))
        if not m:
            unresolved += 1
            continue
        df.at[i, "home"], df.at[i, "away"], df.at[i, "game_date"] = (
            m["home"], m["away"], m["game_date"])
        filled += 1
    if filled:
        df.to_csv(settled_path, index=False)
    return filled, unresolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/settlement/test_backfill_teams.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Add the CLI wrapper**

```python
# scripts/backfill_settled_teams.py
#!/usr/bin/env python
"""One-time backfill of home/away/game_date on settled bets from odds snapshots.

  python scripts/backfill_settled_teams.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.settlement.backfill_teams import backfill_settled_file, teams_from_odds

log = get_logger("sqp.backfill_teams")


def main() -> int:
    bets_dir = ROOT / "data" / "bets"
    odds_dir = ROOT / "data" / "odds"
    total_filled = total_unresolved = 0
    for sf in sorted(bets_dir.glob("settled_*.csv")):
        league = sf.stem.replace("settled_", "")
        meta = teams_from_odds(odds_dir, league)
        filled, unresolved = backfill_settled_file(sf, meta)
        total_filled += filled
        total_unresolved += unresolved
        log.info("[%s] backfilled %d, unresolved %d", league, filled, unresolved)
    print(f"Backfill done: {total_filled} filled, {total_unresolved} unresolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Commit**

```bash
git add src/sqp/settlement/backfill_teams.py scripts/backfill_settled_teams.py tests/settlement/test_backfill_teams.py
git commit -m "feat(settle): backfill script for home/away/game_date on past settled bets"
```

---

### Task 4: Loader de unión del historial (`load_history` + `visible_history`)

**Files:**
- Modify: `src/sqp/audit/report.py` (extender `load_all_candidates` con `start_time`; añadir `load_history`, `visible_history`)
- Test: `tests/audit/test_history_loader.py`

**Interfaces:**
- Consumes: `load_all_settled(bets_dir)`, `load_all_candidates(predictions_dir)`, `rank_candidates(df)` (existentes).
- Produces:
  - `load_history(predictions_dir: Path, bets_dir: Path) -> pd.DataFrame` — columnas: `fecha, league, market, line, home, away, selection, price_decimal, stake, result, pnl, is_closed`. Unión de liquidados (cerrados) + candidatos accionables (abiertos).
  - `visible_history(df: pd.DataFrame, today: str) -> pd.DataFrame` — quita filas abiertas (`is_closed == False`) con `fecha < today`.

- [ ] **Step 1: Write the failing test**

```python
# tests/audit/test_history_loader.py
import pandas as pd
from sqp.audit.report import load_history, visible_history


def _write_settled(d, rows):
    pd.DataFrame(rows).to_csv(d / "settled_mlb.csv", index=False)


def _write_candidates(d, cand_rows, pred_rows):
    pd.DataFrame(cand_rows).to_csv(d / "candidates_mlb.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(d / "predictions_mlb.csv", index=False)


def test_load_history_unions_closed_and_open(tmp_path):
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    _write_settled(bets, [{"event_id": "e1", "market": "h2h", "selection": "NYY",
                           "line": 0.0, "price_decimal": 1.9, "stake": 10.0,
                           "result": "win", "pnl": 9.0, "generated_at": "2026-06-24T09:00:00Z",
                           "home": "NYY", "away": "BOS", "game_date": "2026-06-24"}])
    _write_candidates(preds,
        [{"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
          "price_decimal": 2.0, "stake": 5.0}],
        [{"event_id": "e2", "home": "LAD", "away": "SF", "start_time": "2026-06-26T20:00:00Z"}])
    h = load_history(preds, bets)
    assert set(h["is_closed"]) == {True, False}
    closed = h[h["is_closed"]].iloc[0]
    assert closed["home"] == "NYY" and closed["fecha"] == "2026-06-24" and closed["result"] == "win"
    open_row = h[~h["is_closed"]].iloc[0]
    assert open_row["home"] == "LAD" and open_row["fecha"] == "2026-06-26" and open_row["result"] == ""


def test_visible_history_hides_past_unclosed():
    df = pd.DataFrame([
        {"fecha": "2026-06-24", "is_closed": True, "result": "win"},   # closed past -> show
        {"fecha": "2026-06-20", "is_closed": False, "result": ""},     # open past -> HIDE
        {"fecha": "2026-06-26", "is_closed": False, "result": ""},     # open today -> show
    ])
    out = visible_history(df, today="2026-06-26")
    assert len(out) == 2
    assert "2026-06-20" not in set(out["fecha"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/audit/test_history_loader.py -q`
Expected: FAIL with `ImportError: cannot import name 'load_history'`.

- [ ] **Step 3: Extend `load_all_candidates` to also pull `start_time`**

In `report.py`, change the predictions merge (line 65) from:

```python
            p = pd.read_csv(pf, usecols=lambda x: x in ("event_id", "home", "away"))
```

to:

```python
            p = pd.read_csv(pf, usecols=lambda x: x in ("event_id", "home", "away", "start_time"))
```

- [ ] **Step 4: Add `load_history` and `visible_history`**

Append to `report.py`:

```python
_HISTORY_COLS = ["fecha", "league", "market", "line", "home", "away",
                 "selection", "price_decimal", "stake", "result", "pnl", "is_closed"]


def _normalize_history(df: pd.DataFrame, *, fecha: pd.Series, is_closed: bool) -> pd.DataFrame:
    """Project a settled/candidate frame onto the common history columns."""
    out = pd.DataFrame(index=df.index)
    out["fecha"] = fecha.astype(str).str[:10]
    for col in ("league", "market", "home", "away", "selection", "result"):
        out[col] = df[col].astype(str) if col in df.columns else ""
    for col in ("line", "price_decimal", "stake", "pnl"):
        out[col] = pd.to_numeric(df[col], errors="coerce") if col in df.columns else float("nan")
    out["is_closed"] = is_closed
    return out[_HISTORY_COLS]


def load_history(predictions_dir: Path, bets_dir: Path) -> pd.DataFrame:
    """Union of closed (settled) bets and open actionable candidates, projected
    onto a common column set. Closed rows carry result/pnl; open rows do not.
    `fecha` is the game date (settled: game_date, fallback generated_at; open:
    start_time)."""
    frames = []
    closed = load_all_settled(bets_dir)
    if not closed.empty:
        gd = closed["game_date"] if "game_date" in closed.columns else pd.Series("", index=closed.index)
        gen = closed["generated_at"] if "generated_at" in closed.columns else pd.Series("", index=closed.index)
        fecha = gd.where(gd.astype(str).str.len() >= 10, gen)
        frames.append(_normalize_history(closed, fecha=fecha, is_closed=True))
    open_df = rank_candidates(load_all_candidates(predictions_dir))
    if not open_df.empty:
        st = open_df["start_time"] if "start_time" in open_df.columns else pd.Series("", index=open_df.index)
        frames.append(_normalize_history(open_df, fecha=st, is_closed=False))
    if not frames:
        return pd.DataFrame(columns=_HISTORY_COLS)
    return pd.concat(frames, ignore_index=True)


def visible_history(df: pd.DataFrame, today: str) -> pd.DataFrame:
    """Drop open rows (not closed) whose game date is in the past. Closed rows
    always shown; open rows shown only when fecha >= today."""
    if df.empty:
        return df
    keep = df["is_closed"] | (df["fecha"] >= today)
    return df[keep].reset_index(drop=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/audit/test_history_loader.py -q`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the audit suite for regressions**

Run: `PYTHONPATH=src pytest tests/audit/ -q`
Expected: PASS (the `load_all_candidates` change only adds an optional column).

- [ ] **Step 7: Commit**

```bash
git add src/sqp/audit/report.py tests/audit/test_history_loader.py
git commit -m "feat(audit): load_history union + visible_history hide rule"
```

---

### Task 5: Reescribir la pestaña Historial (columnas, tarjetas, ocultar)

**Files:**
- Modify: `src/sqp/audit/html_report.py` (`_history_section`, `_HISTORY_COLUMNS`, JS `initHistory`/`filterHistory`)
- Test: `tests/audit/test_history_section.py`

**Interfaces:**
- Consumes: `load_history`, `visible_history` (Task 4).
- Produces: `_history_section(predictions_dir, bets_dir, today=None) -> str` (HTML con filtros Deporte/Línea/Home/Away/Fecha, tarjetas de totales, y filas con `data-*`).

- [ ] **Step 1: Write the failing test**

```python
# tests/audit/test_history_section.py
import pandas as pd
from sqp.audit.html_report import _history_section


def test_history_section_hides_past_open_and_emits_cards(tmp_path):
    bets = tmp_path / "bets"; bets.mkdir()
    preds = tmp_path / "pred"; preds.mkdir()
    pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "NYY", "line": 0.0,
                   "price_decimal": 1.9, "stake": 10.0, "result": "win", "pnl": 9.0,
                   "generated_at": "2026-06-24T09:00:00Z", "home": "NYY", "away": "BOS",
                   "game_date": "2026-06-24"}]).to_csv(bets / "settled_mlb.csv", index=False)
    # an open candidate whose game is in the PAST -> must be hidden
    pd.DataFrame([{"event_id": "e2", "market": "totals", "selection": "Over", "line": 8.5,
                   "price_decimal": 2.0, "stake": 5.0}]).to_csv(preds / "candidates_mlb.csv", index=False)
    pd.DataFrame([{"event_id": "e2", "home": "LAD", "away": "SF",
                   "start_time": "2026-06-20T20:00:00Z"}]).to_csv(preds / "predictions_mlb.csv", index=False)
    html = _history_section(preds, bets, today="2026-06-26")
    assert "NYY" in html and "BOS" in html         # closed row shown
    assert "LAD" not in html                         # past-open row hidden
    assert 'id="hWins"' in html or "Wins" in html    # totals cards present
    assert "Picks cerrados" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/audit/test_history_section.py -q`
Expected: FAIL (current `_history_section(bets_dir)` has a different signature and no team/cards output).

- [ ] **Step 3: Rewrite `_history_section`**

Replace the existing `_HISTORY_COLUMNS` (lines 184-191) and `_history_section` (lines 194-225) with:

```python
_HISTORY_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("fecha", "Fecha", True), ("league", "Deporte", True),
    ("market", "Mercado", True), ("line", "Linea", False),
    ("home", "Home", True), ("away", "Away", True),
    ("selection", "Seleccion", True), ("price_decimal", "Cuota", False),
    ("stake", "Stake", False), ("result", "Resultado", True),
    ("pnl", "PnL", False),
)


def _history_section(predictions_dir: Path, bets_dir: Path,
                     today: str | None = None) -> str:
    """Unified history: closed bets + open actionable picks, with filters
    (sport/line/home/away/date) and totals cards (picks, closed, wins, losses)
    recomputed client-side over the visible rows. Past picks that never settled
    are hidden (not deleted)."""
    from datetime import date
    from sqp.audit.report import load_history, visible_history
    today = today or date.today().isoformat()
    df = visible_history(load_history(predictions_dir, bets_dir), today)
    if df.empty:
        return '<p class="empty">Sin historial de picks.</p>'
    df = df.sort_values("fecha", ascending=False)
    cols = [(k, hdr, txt) for k, hdr, txt in _HISTORY_COLUMNS if k in df.columns]
    cards = (
        '<div class="cards" id="historyCards">'
        '<div class="card"><span class="label">Picks</span><span class="value" id="hPicks">0</span></div>'
        '<div class="card"><span class="label">Picks cerrados</span><span class="value" id="hClosed">0</span></div>'
        '<div class="card"><span class="label">Wins</span><span class="value pos" id="hWins">0</span></div>'
        '<div class="card"><span class="label">Losses</span><span class="value neg" id="hLosses">0</span></div>'
        '</div>')
    controls = (
        '<div class="filters" id="historyFilters">'
        '<label>Deporte<select id="hSport"><option value="">(todos)</option></select></label>'
        '<label>Linea<select id="hLine"><option value="">(todas)</option></select></label>'
        '<label>Home<select id="hHome"><option value="">(todos)</option></select></label>'
        '<label>Away<select id="hAway"><option value="">(todos)</option></select></label>'
        '<label>Desde<input type="date" id="hFrom"></label>'
        '<label>Hasta<input type="date" id="hTo"></label>'
        '<label>&nbsp;<span class="gen" id="hCount"></span></label>'
        '</div>')
    head = "".join(f'<th class="{"txt" if txt else ""}">{html.escape(hdr)}</th>'
                   for _, hdr, txt in cols)
    body = []
    for _, row in df.iterrows():
        cells = "".join(
            f'<td class="{"txt" if txt else ""}">{html.escape(_fmt_cell(row.get(k)))}</td>'
            for k, _, txt in cols)
        body.append(
            f'<tr data-fecha="{html.escape(str(row.get("fecha", "")))}" '
            f'data-league="{html.escape(str(row.get("league", "")))}" '
            f'data-line="{html.escape(_fmt_cell(row.get("line")))}" '
            f'data-home="{html.escape(str(row.get("home", "")))}" '
            f'data-away="{html.escape(str(row.get("away", "")))}" '
            f'data-result="{html.escape(str(row.get("result", "")))}">{cells}</tr>')
    table = (f'<table class="grid" id="historyTable"><thead><tr>{head}</tr></thead>'
             f'<tbody>{"".join(body)}</tbody></table>')
    return cards + controls + table
```

- [ ] **Step 4: Update the `html_dashboard` call site**

In `html_dashboard` (around line 271), change:

```python
        history=_history_section(bets_dir),
```

to:

```python
        history=_history_section(predictions_dir, bets_dir),
```

- [ ] **Step 5: Replace the JS `initHistory`/`filterHistory`**

Replace the two functions (lines 525-554) with versions that populate the new selects and recompute the cards:

```javascript
function initHistory() {{
  const table = document.getElementById("historyTable");
  if (!table) return;
  const rowsArr = [...table.querySelectorAll("tbody tr")];
  const uniqOf = a => [...new Set(rowsArr.map(r => r.dataset[a]).filter(Boolean))].sort();
  const fill = (id, vals, lbl) => {{
    const sel = document.getElementById(id);
    vals.forEach(v => sel.add(new Option(lbl ? lbl(v) : v, v)));
  }};
  fill("hSport", uniqOf("league"), labelFor);
  fill("hLine", uniqOf("line"));
  fill("hHome", uniqOf("home"));
  fill("hAway", uniqOf("away"));
  ["hSport", "hLine", "hHome", "hAway", "hFrom", "hTo"].forEach(id =>
    document.getElementById(id).addEventListener("input", filterHistory));
  filterHistory();
}}
function filterHistory() {{
  const table = document.getElementById("historyTable");
  const g = id => document.getElementById(id).value;
  const lg = g("hSport"), ln = g("hLine"), ho = g("hHome"), aw = g("hAway"),
        from = g("hFrom"), to = g("hTo");
  let picks = 0, closed = 0, wins = 0, losses = 0;
  table.querySelectorAll("tbody tr").forEach(r => {{
    const d = r.dataset;
    const ok = (!lg || d.league === lg) && (!ln || d.line === ln) &&
               (!ho || d.home === ho) && (!aw || d.away === aw) &&
               (!from || d.fecha >= from) && (!to || d.fecha <= to);
    r.style.display = ok ? "" : "none";
    if (!ok) return;
    picks++;
    if (d.result) closed++;
    if (d.result === "win") wins++;
    if (d.result === "loss") losses++;
  }});
  const set = (id, v) => {{ const e = document.getElementById(id); if (e) e.textContent = v; }};
  set("hPicks", picks); set("hClosed", closed); set("hWins", wins); set("hLosses", losses);
  set("hCount", picks + " filas");
}}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/audit/test_history_section.py -q`
Expected: PASS.

- [ ] **Step 7: Manual smoke test of the rendered dashboard**

Run: `PYTHONPATH=src python -c "from sqp.audit.html_report import html_dashboard; print(html_dashboard())"`
Then open the printed path in a browser; on the Historial tab verify: the four cards show numbers, the Deporte/Linea/Home/Away selects filter the rows, and the cards recompute on filter.

- [ ] **Step 8: Commit**

```bash
git add src/sqp/audit/html_report.py tests/audit/test_history_section.py
git commit -m "feat(dashboard): history tab with home/away breakdown + totals cards, hide past-open"
```

---

### Task 6: Auto-open del dashboard solo en sesión interactiva

**Files:**
- Modify: `DIARIO_COMPLETO.bat`

**Interfaces:**
- Consumes: `report_latest.html` escrito por `run_all.py` (vía `RUN_DIARIO_ALL.bat`).
- Produces: apertura del navegador solo cuando `SESSIONNAME` está definido (sesión interactiva).

- [ ] **Step 1: Add the guarded open after a successful run**

In `DIARIO_COMPLETO.bat`, between the successful `call "%~dp0RUN_DIARIO_ALL.bat"` block (line 25) and `echo === DIARIO COMPLETO: OK ===` (line 27), insert:

```bat
REM Abrir el dashboard solo en sesion interactiva (SESSIONNAME definido). Bajo el
REM Programador de tareas se omite: abrir el navegador puede terminar el proceso
REM (0xC000013A) y no hay escritorio. El report_latest.html se escribe siempre.
if defined SESSIONNAME start "" "%~dp0data\predictions\report_latest.html"
```

- [ ] **Step 2: Verify the batch syntax parses**

Run: `cmd /c "type DIARIO_COMPLETO.bat"` (visual check the inserted lines are present and well-formed; no execution needed).
Expected: the `if defined SESSIONNAME start ""` line appears before the OK echo.

- [ ] **Step 3: Manual interactive verification**

From an interactive PowerShell session: run `.\DIARIO_COMPLETO.bat` (or just the open line `if defined SESSIONNAME start "" "data\predictions\report_latest.html"`), confirm the dashboard opens. (Scheduler behavior is no-op by design; do not run under the scheduler to test.)

- [ ] **Step 4: Commit**

```bash
git add DIARIO_COMPLETO.bat
git commit -m "feat(daily): auto-open dashboard at end of daily flow in interactive sessions only"
```

---

## Self-Review

**Spec coverage:**
- Auto-open interactivo → Task 6. ✅
- Home/Away en liquidación (approach A) → Tasks 1 (scores) + 2 (tennis). ✅
- Backfill de pasados → Task 3. ✅
- Fecha = partido → `load_history` usa `game_date`/`start_time` (Task 4). ✅
- Columnas Fecha/Deporte/Mercado/Línea/Home/Away/Selección/Cuota/Stake/Resultado/PnL → Task 5 `_HISTORY_COLUMNS`. ✅
- Filtros Deporte/Línea/Home/Away/Fecha → Task 5 controls + JS. ✅
- Tarjetas Picks/Cerrados/Wins/Losses que recalculan → Task 5 JS `filterHistory`. ✅
- Ocultar (no borrar) pasados sin cerrar → `visible_history` (Task 4) usado en Task 5. ✅
- Solo accionables abiertos → `rank_candidates` en `load_history` (Task 4). ✅
- No mutar datos crudos → solo columnas añadidas; backfill solo rellena vacíos. ✅
- Lenguaje de apuestas → el historial no introduce certezas; muestra resultado realizado. ✅

**Placeholder scan:** sin TBD/TODO; todo paso con código tiene código completo. ✅

**Type consistency:** `_event_meta_map`/`_attach_event_meta` (Tasks 1-2), `teams_from_odds`/`backfill_settled_file` → `(filled, unresolved)` (Task 3), `load_history`/`visible_history` con columnas `_HISTORY_COLS` (Task 4), `_history_section(predictions_dir, bets_dir, today=None)` (Task 5) coinciden en firmas y nombres entre tareas. ✅

**Riesgo conocido:** `game_date` desde `/scores` depende de que la API incluya `commence_time`; si falta, queda vacío y el backfill (Task 3, fuente con `commence_time` garantizado) lo rellena. La columna `fecha` cae a `generated_at` cuando `game_date` está vacío (Task 4).
