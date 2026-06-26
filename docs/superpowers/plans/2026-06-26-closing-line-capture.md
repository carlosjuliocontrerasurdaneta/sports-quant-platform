# Captura de línea de cierre — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar un segundo snapshot de cuotas cerca del inicio de cada partido apostado, para que el CLV sea medible, mediante una tarea horaria que solo gasta cuota en ligas con picks abiertos y partidos inminentes.

**Architecture:** Lógica pura en `closing_capture.py` (qué ligas tienen un evento apostado en <120 min, y un contador diario de créditos persistido), orquestada por `capture_closing` que hace un fetch fresco (force_refresh) por liga y persiste el snapshot vía `OddsStore.append_snapshot`. Una tarea programada horaria lo invoca. Nada más en la cadena (`load_closing_odds`, `clv_analysis`, backtest) cambia: ya consumen el último snapshot pre-commence.

**Tech Stack:** Python 3, pandas, The Odds API client (existente), batch (cmd) + Programador de tareas Windows (PowerShell).

## Global Constraints

- Tests: `PYTHONPATH=src pytest tests/ -q` (Windows + Git Bash).
- Ventana = **120 min**; regiones/mercados = los del run diario (`us,eu,uk,au` × `h2h,spreads,totals`); tope diario = **300 créditos** (`MAX_CLOSING_CREDITS_DAY`, parametrizable).
- La captura **cede ante cuota mensual baja** (`requests_remaining` por debajo del margen) → nunca compite con el run de la mañana.
- Solo AÑADE snapshots; no toca `OddsStore`, `load_closing_odds`, `clv_analysis.py`, el modelo ni el staking.
- Best-effort: un fallo por liga se loguea y no aborta el resto.
- Type hints, excepciones explícitas, funciones pequeñas; lenguaje de apuestas (CLV es diagnóstico, no promesa).

---

### Task 1: Selección de ligas con apuesta inminente

**Files:**
- Create: `src/sqp/pipeline/closing_capture.py`
- Test: `tests/pipeline/test_closing_capture.py`

**Interfaces:**
- Produces:
  - `_parse_utc(s) -> datetime | None` — parsea ISO (acepta sufijo `Z`), siempre tz-aware UTC.
  - `leagues_with_imminent_bets(predictions_dir: Path, now: datetime, window_min: int = 120) -> dict[str, list[str]]` — `{league: [event_ids apostados que arrancan en (now, now+window_min]]}`. Sin API.

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_closing_capture.py
from datetime import datetime, timezone
import pandas as pd
from sqp.pipeline.closing_capture import leagues_with_imminent_bets, _parse_utc


def _seed(pred_dir, league, cand_ids, pred_rows):
    pd.DataFrame([{"event_id": e} for e in cand_ids]).to_csv(
        pred_dir / f"candidates_{league}.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(pred_dir / f"predictions_{league}.csv", index=False)


def test_parse_utc_handles_z_suffix_and_naive():
    assert _parse_utc("2026-06-26T23:05:00Z").tzinfo is not None
    assert _parse_utc("2026-06-26T23:05:00").tzinfo is not None  # naive -> assumed UTC
    assert _parse_utc("garbage") is None


def test_only_bet_events_inside_window(tmp_path):
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    _seed(tmp_path, "mlb", ["e1", "e2"], [
        {"event_id": "e1", "start_time": "2026-06-26T23:00:00Z"},  # in 60 min -> include
        {"event_id": "e2", "start_time": "2026-06-27T05:00:00Z"},  # in 7h -> exclude
        {"event_id": "e3", "start_time": "2026-06-26T23:10:00Z"},  # soon but NOT bet -> exclude
    ])
    out = leagues_with_imminent_bets(tmp_path, now, window_min=120)
    assert out == {"mlb": ["e1"]}


def test_league_without_imminent_bet_is_omitted(tmp_path):
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    _seed(tmp_path, "wnba", ["w1"],
          [{"event_id": "w1", "start_time": "2026-06-27T02:00:00Z"}])  # 4h out
    assert leagues_with_imminent_bets(tmp_path, now, window_min=120) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'sqp.pipeline.closing_capture'`.
(If `tests/pipeline/` lacks an `__init__.py` and the sibling test dirs have one — check `tests/audit/__init__.py` — create an empty `tests/pipeline/__init__.py`.)

- [ ] **Step 3: Implement the module skeleton + selection**

```python
# src/sqp/pipeline/closing_capture.py
"""Closing-line capture: snapshot fresh odds shortly before bet events start, so
CLV (entry vs close) becomes measurable. Only spends API quota on leagues that
have open candidates with a game commencing within the window. Adds snapshots
only; load_closing_odds / clv_analysis already use the latest pre-commence one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger("sqp.closing_capture")


def _parse_utc(s: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def leagues_with_imminent_bets(predictions_dir: Path, now: datetime,
                               window_min: int = 120) -> dict[str, list[str]]:
    """{league: [bet event_ids commencing in (now, now+window_min]]}. No API."""
    out: dict[str, list[str]] = {}
    horizon = now + timedelta(minutes=window_min)
    for cf in sorted(predictions_dir.glob("candidates_*.csv")):
        league = cf.stem.replace("candidates_", "")
        try:
            cands = pd.read_csv(cf, usecols=lambda c: c == "event_id")
        except (pd.errors.EmptyDataError, ValueError):
            continue
        if cands.empty:
            continue
        bet_ids = set(cands["event_id"].astype(str))
        pf = predictions_dir / f"predictions_{league}.csv"
        if not pf.exists() or pf.stat().st_size <= 1:
            continue
        preds = pd.read_csv(pf, usecols=lambda c: c in ("event_id", "start_time"))
        if "start_time" not in preds.columns:
            continue
        imminent = [str(r.event_id) for r in preds.itertuples()
                    if str(r.event_id) in bet_ids
                    and (st := _parse_utc(getattr(r, "start_time", ""))) is not None
                    and now <= st <= horizon]
        if imminent:
            out[league] = imminent
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/sqp/pipeline/closing_capture.py tests/pipeline/
git commit -m "feat(closing): select leagues with bet events commencing within the window"
```

---

### Task 2: Contador diario de créditos persistido

**Files:**
- Modify: `src/sqp/pipeline/closing_capture.py`
- Test: `tests/pipeline/test_closing_capture.py` (añadir casos)

**Interfaces:**
- Produces:
  - `spent_today(odds_dir: Path, day: str) -> int` — créditos ya gastados hoy (0 si no hay archivo).
  - `add_spent(odds_dir: Path, day: str, credits: int) -> int` — suma y persiste; devuelve el total. Archivo: `odds_dir / f".closing_credits_{day}"`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/pipeline/test_closing_capture.py
from sqp.pipeline.closing_capture import spent_today, add_spent


def test_credit_counter_accumulates_and_isolates_by_day(tmp_path):
    assert spent_today(tmp_path, "20260626") == 0
    assert add_spent(tmp_path, "20260626", 12) == 12
    assert add_spent(tmp_path, "20260626", 24) == 36     # accumulates same day
    assert spent_today(tmp_path, "20260626") == 36
    assert spent_today(tmp_path, "20260627") == 0        # new day resets
    assert add_spent(tmp_path, "20260626", -5) == 36     # negative ignored


def test_credit_counter_survives_corrupt_file(tmp_path):
    (tmp_path / ".closing_credits_20260626").write_text("not-a-number")
    assert spent_today(tmp_path, "20260626") == 0        # tolerant
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -k credit -q`
Expected: FAIL with `ImportError: cannot import name 'spent_today'`.

- [ ] **Step 3: Add the counter helpers**

Append to `src/sqp/pipeline/closing_capture.py`:

```python
def _credits_file(odds_dir: Path, day: str) -> Path:
    return odds_dir / f".closing_credits_{day}"


def spent_today(odds_dir: Path, day: str) -> int:
    """Credits already spent on closing capture today (0 if absent/corrupt)."""
    p = _credits_file(odds_dir, day)
    if not p.exists():
        return 0
    try:
        return int(p.read_text().strip() or "0")
    except (ValueError, OSError):
        return 0


def add_spent(odds_dir: Path, day: str, credits: int) -> int:
    """Add credits (negative ignored) to today's total and persist. Returns total."""
    total = spent_today(odds_dir, day) + max(0, int(credits))
    p = _credits_file(odds_dir, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(total))
    return total
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -k credit -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/sqp/pipeline/closing_capture.py tests/pipeline/test_closing_capture.py
git commit -m "feat(closing): persisted per-day credit counter"
```

---

### Task 3: Orquestador `capture_closing`

**Files:**
- Modify: `src/sqp/pipeline/closing_capture.py`
- Test: `tests/pipeline/test_closing_capture.py` (añadir casos)

**Interfaces:**
- Consumes: `leagues_with_imminent_bets`, `spent_today`, `add_spent` (Tasks 1-2); `OddsAPIClient.fetch_odds(league_id, sport_key)` con atributos `requests_last`/`requests_remaining`; `OddsStore.append_snapshot(league, events)`; `_league_meta(league)["sport_key"]`.
- Produces:
  - `capture_closing(predictions_dir: Path, settings, *, window_min=120, max_credits=300, min_remaining=100, now=None, client=None, odds_store=None) -> dict`
    Devuelve `{"captured": {league: n_lines}, "skipped_budget": [league...], "credits_spent": int, "leagues_considered": [league...]}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/pipeline/test_closing_capture.py
from datetime import datetime, timezone
import pandas as pd
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.closing_capture import capture_closing


class _FakeClient:
    def __init__(self, events, cost=12, remaining=5000):
        self._events = events
        self.requests_last = cost
        self.requests_remaining = remaining
        self.calls = []

    def fetch_odds(self, league_id, sport_key, markets="h2h,spreads,totals"):
        self.calls.append(league_id)
        return self._events


class _FakeStore:
    def __init__(self):
        self.snapshots = []

    def append_snapshot(self, league, events):
        self.snapshots.append((league, [e.event.event_id for e in events]))
        return len(events)


def _eo(eid):
    ev = Event(event_id=eid, sport_key="baseball_mlb", league="mlb",
               home="NYY", away="BOS", start_time="2026-06-26T23:00:00Z", data_label="real")
    return EventOdds(event=ev, lines=[MarketLine(market="h2h", bookmaker="x",
                                                 outcome="NYY", price_decimal=1.9, point=None)])


def _seed_mlb(pred_dir):
    pd.DataFrame([{"event_id": "e1"}]).to_csv(pred_dir / "candidates_mlb.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "start_time": "2026-06-26T23:00:00Z"}]).to_csv(
        pred_dir / "predictions_mlb.csv", index=False)


def test_capture_persists_only_bet_events(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    client = _FakeClient([_eo("e1"), _eo("e_other")])  # only e1 is a bet
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, now=now, client=client, odds_store=store)
    assert store.snapshots == [("mlb", ["e1"])]      # e_other filtered out
    assert out["captured"] == {"mlb": 1}
    assert out["credits_spent"] == 12


def test_capture_respects_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    (tmp_path / ".closing_credits_20260626").write_text("300")  # cap already reached
    client = _FakeClient([_eo("e1")])
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, max_credits=300, now=now,
                          client=client, odds_store=store)
    assert client.calls == []                         # no fetch when capped
    assert out["skipped_budget"] == ["mlb"]


def test_capture_skips_when_quota_low(tmp_path, monkeypatch):
    monkeypatch.setattr("sqp.pipeline.closing_capture.ROOT", tmp_path)
    _seed_mlb(tmp_path)
    client = _FakeClient([_eo("e1")], remaining=50)   # below min_remaining=100
    store = _FakeStore()
    now = datetime(2026, 6, 26, 22, 0, tzinfo=timezone.utc)
    out = capture_closing(tmp_path, settings=None, min_remaining=100, now=now,
                          client=client, odds_store=store)
    assert client.calls == [] and out["skipped_budget"] == ["mlb"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -k capture -q`
Expected: FAIL with `ImportError: cannot import name 'capture_closing'`.

- [ ] **Step 3: Implement the orchestrator**

Append to `src/sqp/pipeline/closing_capture.py`:

```python
def capture_closing(predictions_dir: Path, settings, *, window_min: int = 120,
                    max_credits: int = 300, min_remaining: int = 100,
                    now: datetime | None = None, client=None, odds_store=None) -> dict:
    """Snapshot fresh closing odds for leagues with imminent bet events.

    Budget-bounded: stops at `max_credits`/day (persisted across hourly runs) and
    skips a league when the API's known `requests_remaining` is below
    `min_remaining` (never starves the morning run). Best-effort per league.
    """
    from sqp.pipeline.daily import _league_meta
    from sqp.providers.odds_api import OddsAPIClient
    from sqp.storage.odds_store import OddsStore

    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y%m%d")
    odds_dir = ROOT / "data" / "odds"
    targets = leagues_with_imminent_bets(predictions_dir, now, window_min)
    summary = {"captured": {}, "skipped_budget": [], "credits_spent": 0,
               "leagues_considered": list(targets)}
    if not targets:
        return summary
    already = spent_today(odds_dir, day)
    if already >= max_credits:
        summary["skipped_budget"] = list(targets)
        log.info("closing: daily cap %d reached (%d spent); skipping %s",
                 max_credits, already, ", ".join(targets))
        return summary

    if client is None:
        client = OddsAPIClient(settings.odds_api_key, settings.regions, force_refresh=True)
    if odds_store is None:
        odds_store = OddsStore(ROOT)

    spent = 0
    for league, bet_ids in targets.items():
        if already + spent >= max_credits:
            summary["skipped_budget"].append(league)
            continue
        if client.requests_remaining is not None and client.requests_remaining < min_remaining:
            summary["skipped_budget"].append(league)
            log.warning("closing: requests_remaining %s < %d; skipping %s",
                        client.requests_remaining, min_remaining, league)
            continue
        try:
            sport_key = _league_meta(league)["sport_key"]
            events = client.fetch_odds(league, sport_key)
            spent += client.requests_last or 0
            want = set(bet_ids)
            keep = [eo for eo in events if str(eo.event.event_id) in want]
            if keep:
                n = odds_store.append_snapshot(league, keep)
                summary["captured"][league] = n
                log.info("closing: [%s] %d lines snapshotted for %d bet events",
                         league, n, len(keep))
        except Exception as exc:
            log.warning("[%s] closing capture failed: %s", league, exc)
    if spent:
        add_spent(odds_dir, day, spent)
    summary["credits_spent"] = spent
    return summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/pipeline/test_closing_capture.py -q`
Expected: PASS (all closing_capture tests).

- [ ] **Step 5: Run the full suite for regressions**

Run: `PYTHONPATH=src pytest tests/ -q`
Expected: PASS (new module only adds code).

- [ ] **Step 6: Commit**

```bash
git add src/sqp/pipeline/closing_capture.py tests/pipeline/test_closing_capture.py
git commit -m "feat(closing): capture_closing orchestrator with daily cap + quota guard"
```

---

### Task 4: CLI `capture_closing_odds.py`

**Files:**
- Create: `scripts/capture_closing_odds.py`

**Interfaces:**
- Consumes: `capture_closing` (Task 3), `Settings.load()`.

- [ ] **Step 1: Implement the CLI wrapper**

```python
# scripts/capture_closing_odds.py
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
```

- [ ] **Step 2: Smoke-run (no bets imminent → no-op, no quota)**

Run: `PYTHONPATH=src python scripts/capture_closing_odds.py`
Expected: prints a "Closing capture: ..." line and exits 0. If no leagues have an imminent bet right now, captured is empty and credits 0 (it must NOT raise).

- [ ] **Step 3: Commit**

```bash
git add scripts/capture_closing_odds.py
git commit -m "feat(closing): CLI wrapper for closing-line capture"
```

---

### Task 5: Batch `CAPTURE_CLOSE.bat`

**Files:**
- Create: `CAPTURE_CLOSE.bat`

- [ ] **Step 1: Create the batch file**

```bat
@echo off
REM SQP - Captura de linea de cierre. Horaria. Solo gasta cuota en ligas con
REM picks abiertos cuyo partido arranca en <120 min (guard interno + tope diario
REM de creditos). Anade un segundo snapshot de cuotas para que el CLV sea medible.
setlocal
cd /d %~dp0
set PYTHONPATH=src
set ODDS_API_REGIONS=us,eu,uk,au

if not exist logs mkdir logs

echo === SQP - CAPTURA CIERRE (%DATE% %TIME%) === >> logs\capture_close.log
python scripts\capture_closing_odds.py >> logs\capture_close.log 2>&1
if errorlevel 1 goto :error

endlocal
goto :eof

:error
echo.
echo *** ERROR EN LA CAPTURA DE CIERRE. Revisa logs\capture_close.log. ***
endlocal
exit /b 1
```

- [ ] **Step 2: Verify the batch parses and runs**

Run (Git Bash): `cmd //c CAPTURE_CLOSE.bat`
Expected: exits 0; `logs/capture_close.log` gets a "CAPTURA CIERRE" line. (No bets imminent → no-op.)

- [ ] **Step 3: Commit**

```bash
git add CAPTURE_CLOSE.bat
git commit -m "feat(closing): hourly closing-capture batch wrapper"
```

---

### Task 6: Tarea programada `SQP_Capture_Close_Cdev`

**Files:**
- (ninguno versionado — crea una tarea de Windows)

- [ ] **Step 1: Create the hourly scheduled task (PowerShell)**

Run in PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c "C:\dev\sports-quant-platform\CAPTURE_CLOSE.bat"'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(8) `
  -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId 'Richard' -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 72)
Register-ScheduledTask -TaskName 'SQP_Capture_Close_Cdev' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'SQP - Captura horaria de linea de cierre (solo ligas con picks, partidos en <120 min). Creada 2026-06-26.'
```

- [ ] **Step 2: Verify the task registered and repeats hourly**

Run in PowerShell:

```powershell
$t = Get-ScheduledTask -TaskName 'SQP_Capture_Close_Cdev'
[PSCustomObject]@{ State=$t.State; Exec=$t.Actions.Execute; Args=$t.Actions.Arguments;
  Rep=$t.Triggers[0].Repetition.Interval } | Format-List
```
Expected: `State=Ready`, `Args` points at `CAPTURE_CLOSE.bat`, `Rep=PT1H` (hourly).

- [ ] **Step 3: Record in the SDD ledger (no commit needed)**

The task is a Windows object, not a repo file. Note in the progress ledger that `SQP_Capture_Close_Cdev` now exists (6 `SQP_*_Cdev` tasks total).

---

## Self-Review

**Spec coverage:**
- Horaria, solo ligas con picks → Task 1 (selección) + Task 6 (trigger horario). ✅
- Ventana 120 min → Task 1 (`window_min=120`). ✅
- Fetch fresco (force_refresh) + regiones del run diario → Task 3 (`OddsAPIClient(..., force_refresh=True)`) + Task 5 (`ODDS_API_REGIONS=us,eu,uk,au`). ✅
- Persistir solo event_ids apostados → Task 3 (`keep = [...] in want`). ✅
- Tope diario 300 persistido across ejecuciones → Task 2 (contador) + Task 3 (gating). ✅
- Cesión ante cuota mensual baja → Task 3 (`min_remaining`). ✅
- Best-effort → Task 3 (try/except por liga). ✅
- No tocar OddsStore/load_closing_odds/clv_analysis → confirmado: solo se llama `append_snapshot`. ✅
- Tarea con la config de las otras `_Cdev` → Task 6. ✅
- Tests (selección, contador, cap, quota baja, filtrado, best-effort) → Tasks 1-3. ✅

**Placeholder scan:** sin TBD/TODO; cada paso de código tiene código completo. ✅

**Type consistency:** `leagues_with_imminent_bets -> dict[str, list[str]]`, `spent_today/add_spent(odds_dir, day[, credits]) -> int`, `capture_closing(...) -> dict` con claves `captured/skipped_budget/credits_spent/leagues_considered`; usadas consistentemente en Tasks 3-4. El `_FakeClient`/`_FakeStore` de los tests reflejan `fetch_odds(league_id, sport_key, markets=...)`, `requests_last`, `requests_remaining`, `append_snapshot(league, events)`. ✅

**Riesgo conocido:** el tope "diario" persiste en `data/odds/.closing_credits_<YYYYMMDD>` (gitignored). Si el archivo se borra a mitad de día, el conteo reinicia (a lo sumo se gasta un poco más ese día; acotado igual por `requests_remaining`). Aceptable.
