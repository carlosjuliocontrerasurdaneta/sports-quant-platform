"""Medicion del pre-registro del clima MLB (2026-09-26, con enmiendas E1-E12).

Ver `docs/research/2026-09-26-preregistro-clima-mlb.md`. Entrada: el CSV de
`fetch_weather_mlb.py`. Dos modos:

  --pre   informe SOLO de clima (cobertura, fraccion afectada f, distribuciones,
          primera fecha con datos). No lee marcadores: es lo que E6 exige
          registrar ANTES de unir con carreras.
  (sin)   la medicion, UNA sola ejecucion (E10). Reproduce el walk-forward
          canonico partido a partido y aborta si la paridad con el motor se
          rompe (E4).

  python scripts/research/measure_weather_mlb.py --weather <csv> --out <json> [--pre]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import _match_index, _match_result, load_closing_odds
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import ROOT, Settings
from sqp.domain.models import Event
from sqp.pipeline.daily import _league_meta
from sqp.pipeline.probabilities import _pick_main_lines
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore
from sqp.storage.starter_fip import StarterFIPStore
from sqp.storage.starters import StartersStore

LINES = (7.5, 8.5, 9.5)
WARMUP = 60  # default de walk_forward_backtest
PERIODO = ("2024-01-01", "2026-09-24")
FOLDS = {"A": (("2024",), ("2025",)), "B": (("2024", "2025"), ("2026",))}
NM_OPTS = {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}  # E9
N_BOOT, SEED = 10_000, 42  # E8


# ---------------------------------------------------------------- universo --
def universo_clima(w: pd.DataFrame) -> pd.DataFrame:
    """E3: estadio abierto con techo conocido, 9+ entradas, no reanudado."""
    w = w.copy()
    w["date"] = w["official_date"].astype(str).str[:10]
    en_periodo = (w["date"] >= PERIODO[0]) & (w["date"] <= PERIODO[1])
    completo = pd.to_numeric(w["current_inning"], errors="coerce") >= 9
    reanudado = w["resumed"].astype(str).str.lower() == "true"
    w["excl"] = np.select(
        [~en_periodo, w["roof_type"].fillna("") == "", w["roof_type"] != "Open",
         ~completo, reanudado],
        ["fuera_de_periodo", "techo_desconocido", "techo_no_abierto",
         "menos_de_9_entradas", "reanudado"], default="")
    return w


def afectado(w: pd.DataFrame, threshold: float) -> pd.Series:
    """E6: definido SOLO por el pronostico, antes del resultado."""
    return (w["wind_kmh"] > threshold) | (w["precip_mm"] > 0)


def informe_pre(w: pd.DataFrame, threshold: float) -> dict:
    u = universo_clima(w)
    ab = u[u["excl"] == ""]
    con = ab[ab["wind_kmh"].notna()]
    q = [0.5, 0.9, 0.95, 0.99]
    return {
        "partidos_descargados": int(len(u)),
        "exclusiones": u["excl"].replace("", "incluido").value_counts().to_dict(),
        "primera_fecha_con_pronostico": str(u.loc[u["wind_kmh"].notna(), "date"].min()),
        "abiertos_incluidos": int(len(ab)),
        "abiertos_con_pronostico": int(len(con)),
        "fraccion_afectada_f": float(afectado(con, threshold).mean()),
        "afectados_por_temporada": {s: int(afectado(g, threshold).sum())
                                    for s, g in con.groupby(con["date"].str[:4])},
        "viento_kmh_cuantiles": {str(k): float(v) for k, v in con["wind_kmh"].quantile(q).items()},
        "frac_viento_sobre_umbral": float((con["wind_kmh"] > threshold).mean()),
        "frac_lluvia_positiva": float((con["precip_mm"] > 0).mean()),
        "lluvia_mm_cuantiles_si_llueve": {
            str(k): float(v) for k, v in con.loc[con["precip_mm"] > 0, "precip_mm"].quantile(q).items()},
    }


# ------------------------------------------------------------- walk-forward --
def walk_forward_over(results: list[dict], params: dict,
                      market_lines: dict[str, float]) -> pd.DataFrame:
    """P(Over) por partido: lineas fijas + linea capturada (E11), MISMA secuencia
    que `engine.walk_forward_backtest`."""
    adapter = get_adapter("mlb", "baseball", params)
    rows, pending = [], []
    for i, r in enumerate(sorted(results, key=lambda x: str(x.get("date", "")))):
        if pending and str(r.get("date", ""))[:10] != str(pending[0].get("date", ""))[:10]:
            for done in pending:
                adapter.observe(done)
            pending.clear()
        if i >= WARMUP:
            ev = Event(event_id=str(i), sport_key="bt", league="mlb",
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            total = r["home_score"] + r["away_score"]
            gid = str(r.get("game_id"))
            row = {"game_id": gid, "total": total}
            for t in LINES:
                row[f"p{t}"] = adapter.estimate(ev, None, t).over_estimated_probability
                row[f"y{t}"] = 1.0 if total > t else 0.0
            ml = market_lines.get(gid)
            if ml is not None:
                row["mkt_line"] = ml
                row["p_mkt"] = adapter.estimate(ev, None, ml).over_estimated_probability
            rows.append(row)
        pending.append(r)
    return pd.DataFrame(rows)


def captured_lines(results: list[dict]) -> dict[str, float]:
    """game_id -> linea principal de totales del ultimo snapshot pregame."""
    odds = load_closing_odds(ROOT, "mlb")
    idx, used, out = _match_index(odds), set(), {}
    for r in sorted(results, key=lambda x: str(x.get("date", ""))):
        if str(r.get("date", "")) < "2026-01-01":
            continue
        eo = _match_result(r, idx, used)
        if eo is None:
            continue
        used.add(eo.event.event_id)
        total_line = _pick_main_lines(eo)[1]
        if total_line is not None:
            out[str(r.get("game_id"))] = float(total_line)
    return out


# ----------------------------------------------------------------- metricas --
def delta_weather(df: pd.DataFrame, wc: float, pc: float, threshold: float,
                  wind_col: str = "wind_kmh") -> np.ndarray:
    """Formula de `weather.weather_p_adjustment`; 0 sin pronostico."""
    wind = df[wind_col].to_numpy(dtype=float)
    prec = df["precip_mm"].to_numpy(dtype=float)
    d = np.maximum(0.0, wind - threshold) * wc + prec * pc
    return np.where(np.isfinite(d), d, 0.0)


def ll_por_partido(df: pd.DataFrame, delta: np.ndarray) -> np.ndarray:
    """Log loss medio de las tres lineas, por partido (con el recorte)."""
    terms = []
    for t in LINES:
        p = np.clip(df[f"p{t}"].to_numpy() + delta, 0.01, 0.99)
        y = df[f"y{t}"].to_numpy()
        terms.append(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return np.mean(np.vstack(terms), axis=0)


def mean_ll(df: pd.DataFrame, delta: np.ndarray) -> float:
    return float(ll_por_partido(df, delta).mean()) if len(df) else float("nan")


def ece(df: pd.DataFrame, delta: np.ndarray) -> float:
    p = np.concatenate([np.clip(df[f"p{t}"].to_numpy() + delta, 0.01, 0.99) for t in LINES])
    y = np.concatenate([df[f"y{t}"].to_numpy() for t in LINES])
    return float(expected_calibration_error(list(p), list(y)))


def bias(df: pd.DataFrame) -> float:
    p = np.concatenate([df[f"p{t}"].to_numpy() for t in LINES])
    y = np.concatenate([df[f"y{t}"].to_numpy() for t in LINES])
    return float(p.mean() - y.mean())


def bootstrap_por_fecha(dates: np.ndarray, diff: np.ndarray) -> dict:
    """E8: remuestrea DIAS completos; IC95 del Δ medio por partido."""
    u, inv = np.unique(dates, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    cnts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    reps = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    return {"n_dias": int(len(u)), "ic95": [float(np.quantile(reps, 0.025)),
                                             float(np.quantile(reps, 0.975))]}


def fit(objetivo, x0) -> np.ndarray:
    return minimize(objetivo, x0=np.asarray(x0, dtype=float), method="Nelder-Mead",
                    options=NM_OPTS).x


# --------------------------------------------------------------------- main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weather", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pre", action="store_true")
    args = ap.parse_args()

    threshold = float(Settings.load().weather.wind_threshold_kmh)
    w = pd.read_csv(args.weather, dtype={"game_id": str})
    if args.pre:
        out = {"modo": "pre (sin marcadores)", "threshold_kmh": threshold,
               **informe_pre(w, threshold)}
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    params = dict(_league_meta("mlb").get("league_params") or {})
    results = ResultsStore(ROOT).load("mlb")
    n_st = StartersStore(ROOT).attach("mlb", results)  # E2
    n_fip = StarterFIPStore(ROOT).attach("mlb", results)
    mkt = captured_lines(results)

    base = walk_forward_over(results, params, mkt)
    ref = walk_forward_backtest(results, "mlb", "baseball", params, total_lines=LINES)
    for t in LINES:  # E4: paridad con el motor canonico
        mine = base[f"p{t}"].to_numpy()
        theirs = np.asarray(ref["markets"][f"totals@{t}"]["probs"])
        if len(mine) != len(theirs) or not np.allclose(mine, theirs, rtol=0, atol=1e-12):
            raise SystemExit(f"PARIDAD ROTA en la linea {t}: no se mide nada.")
        if not np.array_equal(base[f"y{t}"].to_numpy(),
                              np.asarray(ref["markets"][f"totals@{t}"]["outcomes"])):
            raise SystemExit(f"RESULTADOS DESALINEADOS en la linea {t}.")

    u = universo_clima(w)
    df = base.merge(u[["game_id", "date", "venue_id", "excl", "wind_kmh", "precip_mm"]],
                    on="game_id", how="inner")
    ab = df[df["excl"] == ""].copy()
    ab["season"] = ab["date"].str[:4]
    ab["afectado"] = afectado(ab, threshold)

    out: dict = {"threshold_kmh": threshold, "params": params,
                 "cobertura": {"resultados": len(results), "con_abridor": n_st,
                               "con_fip": n_fip, "unidos_al_calendario": int(len(df)),
                               "abiertos_incluidos": int(len(ab)),
                               "exclusiones": df["excl"].replace("", "incluido")
                               .value_counts().to_dict(),
                               "con_linea_capturada": int(ab["mkt_line"].notna().sum())
                               if "mkt_line" in ab else 0},
                 "folds": {}}
    piezas = []
    for name, (train_s, test_s) in FOLDS.items():
        tr = ab[ab["season"].isin(train_s)]
        te = ab[ab["season"].isin(test_s)].copy()
        wc, pc = fit(lambda c: mean_ll(tr, delta_weather(tr, c[0], c[1], threshold)), (0, 0))
        (c0,) = fit(lambda c: mean_ll(tr, np.full(len(tr), c[0])), (0,))  # E5
        te["d_trat"] = delta_weather(te, wc, pc, threshold)
        te["d_ctrl"] = c0
        te["ll_base"] = ll_por_partido(te, np.zeros(len(te)))
        te["ll_trat"] = ll_por_partido(te, te["d_trat"].to_numpy())
        te["ll_ctrl"] = ll_por_partido(te, te["d_ctrl"].to_numpy())
        a = te[te["afectado"]]
        out["folds"][name] = {
            "train": list(train_s), "test": list(test_s),
            "n_train": int(len(tr)), "n_test": int(len(te)), "n_test_afectados": int(len(a)),
            "wind_coef": float(wc), "precip_coef": float(pc), "control_c": float(c0),
            "bias_base_test": bias(te),
            "delta_ll_afectados": float((a["ll_trat"] - a["ll_base"]).mean()),
            "delta_ll_universo": float((te["ll_trat"] - te["ll_base"]).mean()),
            "ll_trat_menos_ctrl_universo": float((te["ll_trat"] - te["ll_ctrl"]).mean())}
        if name == "B":
            coefs_b = (wc, pc)
            # E11: viento centrado por estadio (medias del ENTRENAMIENTO)
            media_v = tr.groupby("venue_id")["wind_kmh"].mean()
            glob = tr["wind_kmh"].mean()
            for d in (tr, te):
                d.loc[:, "wind_cent"] = (d["wind_kmh"] - d["venue_id"].map(media_v).fillna(glob)
                                         + glob)
            wcc, pcc = fit(lambda c: mean_ll(tr, delta_weather(tr, c[0], c[1], threshold,
                                                               "wind_cent")), (0, 0))
            dc = delta_weather(te, wcc, pcc, threshold, "wind_cent")
            out["secundario_viento_centrado_B"] = {
                "wind_coef": float(wcc), "precip_coef": float(pcc),
                "delta_ll_afectados": float(
                    (ll_por_partido(a, dc[te["afectado"].to_numpy()])
                     - a["ll_base"].to_numpy()).mean())}
            # E11: contra la linea capturada (sin empujes)
            m = te[te["mkt_line"].notna() & (te["total"] != te["mkt_line"])] \
                if "mkt_line" in te else te.iloc[0:0]
            if len(m):
                y = (m["total"] > m["mkt_line"]).to_numpy(dtype=float)
                dm = delta_weather(m, wc, pc, threshold)

                def _ll(p):
                    p = np.clip(p, 0.01, 0.99)
                    return -(y * np.log(p) + (1 - y) * np.log(1 - p))
                d_row = _ll(m["p_mkt"].to_numpy() + dm) - _ll(m["p_mkt"].to_numpy())
                af = m["afectado"].to_numpy()
                out["secundario_linea_capturada_B"] = {
                    "n": int(len(m)), "n_afectados": int(af.sum()),
                    "delta_ll_todos": float(d_row.mean()),
                    "delta_ll_afectados": float(d_row[af].mean()) if af.any() else None}
        piezas.append(te)

    te_all = pd.concat(piezas)
    a_all = te_all[te_all["afectado"]]
    diff_a = (a_all["ll_trat"] - a_all["ll_base"]).to_numpy()
    out["combinado"] = {
        "n_test": int(len(te_all)), "n_afectados": int(len(a_all)),
        "delta_ll_afectados": float(diff_a.mean()),
        "bootstrap_afectados": bootstrap_por_fecha(a_all["date"].to_numpy(), diff_a),
        "delta_ll_universo": float((te_all["ll_trat"] - te_all["ll_base"]).mean()),
        "ece_base": ece(te_all, np.zeros(len(te_all))),
        "ece_trat": ece(te_all, te_all["d_trat"].to_numpy()),
        "ll_trat": float(te_all["ll_trat"].mean()),
        "ll_ctrl": float(te_all["ll_ctrl"].mean())}
    c = out["combinado"]
    out["criterios"] = {  # E7
        "1_delta_afectados_combinado_le_-0.002": c["delta_ll_afectados"] <= -0.002,
        "2_delta_afectados_negativo_en_cada_particion":
            all(f["delta_ll_afectados"] < 0 for f in out["folds"].values()),
        "3_ece_universo_no_empeora": c["ece_trat"] <= c["ece_base"],
        "4_coefs_B_negativos": coefs_b[0] < 0 and coefs_b[1] < 0,
        "5_trat_bate_control_intercepto": c["ll_trat"] < c["ll_ctrl"]}
    out["veredicto"] = "ACEPTA" if all(out["criterios"].values()) else "RECHAZA"
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
