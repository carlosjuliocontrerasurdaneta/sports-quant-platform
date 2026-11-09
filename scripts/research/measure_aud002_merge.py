"""Medicion de solo lectura de AUD-002: regla de descarte de `_merge_results`.

Compara la regla ANTIGUA (copia congelada abajo: descartar el reciente si el
historico tiene la misma pareja en cualquier fecha local posible) con la NUEVA
(`sqp.pipeline.daily._merge_results`, identidad (pareja, dia)), reconstruyendo
para cada dia de ejecucion R de los ultimos N dias lo que cada una habria visto:

  history_R = filas de data/historical/results_<liga>.csv con ingested_at < R 12:00
              (hora local), con la misma migracion/deduplicacion por game_id
              que `ResultsStore.load`.
  recent_R  = TODOS los eventos de data/odds/odds_<liga>_YYYYMM.csv, unicos por
              event_id (el ultimo), con commence_time en [R-3 d, R 12:00 local),
              con marcador ficticio (la fusion no usa marcadores). La VERDAD solo
              existe para los emparejados con el historico COMPLETO mediante
              `roi_engine.match_results` (identidad canonica de la liquidacion):
              su fila de resultado esta o no en history_R.

Las columnas cuentan pares (R, evento): un mismo evento aparece en ~3 dias R.
(a) y (b) se dan tambien deduplicados por event_id (columnas "ev").
Salida (SOLO agregados por liga; no escribe en data/):
  a) la antigua descarta un partido que NO estaba en history_R (par / ev)
  b) de (a), recuperados (conservados) por la nueva (par / ev)
  c) dobles conteos: conservados cuyo partido YA estaba en history_R, de la
     nueva y de la antigua (linea base). Codigo de salida 1 si la nueva tiene
     mas que la antigua en alguna liga.
  d) ambiguedades registradas (WARNING de la nueva)
  e) perdida residual: la nueva descarta un partido que no estaba en history_R
  f) cambio_sin_verdad: eventos NO emparejados que la nueva conserva y la
     antigua descartaba (se listan hasta 50 por liga para revision manual)

Ejecutar con PYTHONPATH=src desde la raiz que se quiere medir: sin el, Python
puede importar otra copia instalada de `sqp` (p. ej. el arbol de produccion).

Uso:  PYTHONPATH=src python scripts/research/measure_aud002_merge.py [--days 120] [--leagues mlb,nba] [--root RUTA]
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

from sqp.backtesting.roi_engine import match_results
from sqp.config import ROOT
from sqp.domain.models import Event, EventOdds
from sqp.pipeline.daily import _merge_results, _possible_local_days
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.odds_store import OddsStore
from sqp.storage.results_store import ResultsStore


def _merge_results_old(history: list[dict], recent: list[dict],
                       normalize: Callable[[str | None], str] | None = None) -> list[dict]:
    """Copia CONGELADA de `_merge_results` antes de AUD-002 (no editar)."""
    nk = normalize or (lambda s: s or "")
    seen: dict[tuple, dict] = {}
    for r in history:
        day = str(r.get("date", ""))[:10]
        seen.setdefault((day, nk(r["home"]), nk(r["away"]), str(r.get("game_id") or "")), r)
    history_days = {k[:3] for k in seen}
    for r in recent:
        day = str(r.get("date", ""))[:10]
        if any((d, nk(r["home"]), nk(r["away"])) in history_days
               for d in _possible_local_days(str(r.get("date", "")))):
            continue
        seen.setdefault((day, nk(r["home"]), nk(r["away"]), str(r.get("game_id") or "")), r)
    return [seen[k] for k in sorted(seen, key=lambda k: k[0])]


class _Count(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.n = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "merge_results" in record.getMessage():
            self.n += 1


_ODDS_FILE = re.compile(r"odds_(?P<league>.+)_(?P<month>\d{6})\.csv")
_KEY = ["date", "home", "away", "game_id"]
_ROWCOLS = _KEY + ["home_score", "away_score"]


def _load_events(odds: OddsStore, league: str) -> pd.DataFrame:
    files = [p for p in sorted(odds.dir.glob(f"odds_{league}_*.csv"))
             if (m := _ODDS_FILE.fullmatch(p.name)) and m.group("league") == league]
    cols = ["event_id", "commence_time", "home", "away"]
    parts = [pd.read_csv(p, usecols=cols, dtype=str) for p in files]
    if not parts:
        return pd.DataFrame(columns=cols)
    ev = pd.concat(parts, ignore_index=True).drop_duplicates("event_id", keep="last")
    ev["t"] = pd.to_datetime(ev["commence_time"], errors="coerce", utc=True)
    return ev.dropna(subset=["t"]).reset_index(drop=True)


def _clean(df: pd.DataFrame, league: str) -> pd.DataFrame:
    """Misma migracion/deduplicacion que `ResultsStore.load`."""
    df = ResultsStore._migrate(df.copy()).sort_values("date", kind="stable")
    return ResultsStore._drop_repeated_game_ids(df, league)


def measure_league(root: Path, league: str, days: int, now: datetime) -> dict | None:
    rpath = ResultsStore(root).path(league)
    if not rpath.exists():
        return None
    raw = pd.read_csv(rpath, dtype={"date": str, "game_id": str}, keep_default_na=False)
    if "ingested_at" not in raw.columns:
        return None
    events = _load_events(OddsStore(root), league)
    if events.empty:
        return None
    norm = get_team_normalizer(league)
    # ingested_at vacio/ilegible: se trata como "ya estaba" (siempre en history_R).
    raw["_ing"] = pd.to_datetime(raw["ingested_at"].replace("", None), errors="coerce", utc=True)
    full = _clean(raw, league)
    rows = full[_ROWCOLS].to_dict("records")
    ev_ids = events["event_id"].tolist()
    ev_ts = events["commence_time"].tolist()
    ev_home = events["home"].tolist()
    ev_away = events["away"].tolist()
    odds_by_id = {
        eid: EventOdds(Event(event_id=eid, sport_key="", league=league,
                             home=h, away=a, start_time=t))
        for eid, t, h, a in zip(ev_ids, ev_ts, ev_home, ev_away)}
    matched = match_results(rows, odds_by_id, league, normalize=norm)
    ev_key = {eo.event.event_id: tuple(rows[i][k] for k in _KEY) for i, eo in matched.items()}
    info = {eid: (t, h, a) for eid, t, h, a in zip(ev_ids, ev_ts, ev_home, ev_away)}

    c: dict[str, int] = defaultdict(int)
    ev_a: set[str] = set()
    ev_b: set[str] = set()
    sin_verdad: dict[str, tuple[str, str, str]] = {}
    counter_log = _Count()
    logging.getLogger("sqp.pipeline").addHandler(counter_log)
    try:
        for back in range(days):
            run_day = (now - timedelta(days=back)).date()
            cutoff = datetime(run_day.year, run_day.month, run_day.day, 12, 0).astimezone()
            cut_utc = pd.Timestamp(cutoff).tz_convert("UTC")
            sub = raw[(raw["_ing"] < cut_utc) | raw["_ing"].isna()]
            hist_df = _clean(sub, league)
            history = hist_df[_ROWCOLS].to_dict("records")
            hist_keys = set(hist_df[_KEY].itertuples(index=False, name=None))
            window = events[(events["t"] >= cut_utc - pd.Timedelta(days=3))
                            & (events["t"] < cut_utc)]
            recent = [{"date": t, "home": h, "away": a, "home_score": 0, "away_score": 0,
                       "game_id": f"odds-{eid}"}
                      for eid, t, h, a in zip(window["event_id"], window["commence_time"],
                                              window["home"], window["away"])]
            if not recent:
                continue
            kept_old = {r["game_id"] for r in _merge_results_old(history, recent, norm)
                        if str(r.get("game_id", "")).startswith("odds-")}
            before = counter_log.n
            kept_new = {r["game_id"] for r in _merge_results(history, recent, norm, league)
                        if str(r.get("game_id", "")).startswith("odds-")}
            c["ambiguedades"] += counter_log.n - before
            for r in recent:
                gid = r["game_id"]
                eid = gid[len("odds-"):]
                c["recientes"] += 1
                key = ev_key.get(eid)
                if key is None:
                    c["sin_verdad"] += 1
                    if gid in kept_new and gid not in kept_old:
                        c["cambio_sin_verdad"] += 1
                        sin_verdad.setdefault(eid, info[eid])
                    continue
                if key in hist_keys:
                    c["c_doble_conteo_nueva"] += gid in kept_new
                    c["c_doble_conteo_antigua"] += gid in kept_old
                    continue
                if gid not in kept_old:
                    c["a_par"] += 1
                    ev_a.add(eid)
                    if gid in kept_new:
                        c["b_par"] += 1
                        ev_b.add(eid)
                if gid not in kept_new:
                    c["e_residual"] += 1
    finally:
        logging.getLogger("sqp.pipeline").removeHandler(counter_log)
    out: dict = dict(c)
    out["a_ev"], out["b_ev"] = len(ev_a), len(ev_b)
    out["lista_sin_verdad"] = [(e, *v) for e, v in list(sin_verdad.items())[:50]]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Mide el efecto de AUD-002 en _merge_results (solo lectura; "
                    "imprime agregados por liga). Ejecutar con PYTHONPATH=src.")
    ap.add_argument("--days", type=int, default=120, help="dias de ejecucion R a simular (120)")
    ap.add_argument("--leagues", default="", help="ligas separadas por coma (por defecto: todas)")
    ap.add_argument("--root", type=Path, default=ROOT, help="raiz del proyecto con data/")
    args = ap.parse_args(argv)
    store = ResultsStore(args.root)
    leagues = ([x for x in args.leagues.split(",") if x] or
               sorted(p.stem[len("results_"):] for p in store.dir.glob("results_*.csv")))
    now = datetime.now().astimezone()
    print("Columnas = pares (R, evento) salvo las 'ev' (eventos unicos).")
    print("liga | pares | sin_verdad | (a) par | (a) ev | (b) par | (b) ev | "
          "(c) doble nueva | (c) doble antigua | (d) ambig. | (e) residual | "
          "cambio_sin_verdad")
    bad = 0
    detail: list[str] = []
    for lg in leagues:
        c = measure_league(args.root, lg, args.days, now)
        if c is None:
            print(f"{lg} | sin datos suficientes")
            continue
        g = c.get
        if g("c_doble_conteo_nueva", 0) > g("c_doble_conteo_antigua", 0):
            bad += 1
        print(f"{lg} | {g('recientes', 0)} | {g('sin_verdad', 0)} | {g('a_par', 0)} | "
              f"{g('a_ev', 0)} | {g('b_par', 0)} | {g('b_ev', 0)} | "
              f"{g('c_doble_conteo_nueva', 0)} | {g('c_doble_conteo_antigua', 0)} | "
              f"{g('ambiguedades', 0)} | {g('e_residual', 0)} | {g('cambio_sin_verdad', 0)}")
        detail += [f"  {lg} {e} {t} {h} vs {a}" for e, t, h, a in c.get("lista_sin_verdad", [])]
    if detail:
        print("cambio_sin_verdad (revision manual, max 50 por liga):")
        print("\n".join(detail))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
