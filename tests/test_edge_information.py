"""Contratos de sqp.evaluation.edge_information y del bootstrap compartido.

La escalera de `min_edge` es la prueba que decide si el edge declarado tiene
valor realizado. Estos tests fijan que (a) detecta una ventaja construida, (b)
detecta su inversion, (c) no fabrica significancia tratando las dos caras de un
mercado como observaciones independientes y (d) no deja pasar valores no finitos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sqp.evaluation.bootstrap import cluster_bootstrap_ci
from sqp.evaluation.edge_information import (
    MIN_ROWS,
    cap_ladder,
    edge_ladder,
    edge_signal,
    prepare,
)


def _stream(n_events: int, *, edge_wins: bool, price: float = 2.0,
            seed: int = 0) -> pd.DataFrame:
    """Dos caras por evento. La cara con edge>0 gana con probabilidad 0.65 si
    `edge_wins`, y con 0.35 si no: ventaja real e inversion exacta."""
    rng = np.random.default_rng(seed)
    p_win = 0.65 if edge_wins else 0.35
    rows = []
    for i in range(n_events):
        favored_wins = rng.random() < p_win
        for side, edge in (("A", 0.10), ("B", -0.10)):
            won = favored_wins if side == "A" else not favored_wins
            rows.append({
                "league": "test", "market": "h2h", "event_id": f"e{i}",
                "selection": side, "price_decimal": price,
                "estimated_edge": edge, "calibrated_probability": 0.5,
                "implied_probability_novig": 0.5,
                "result": "win" if won else "loss",
            })
    return pd.DataFrame(rows)


class TestUnaFilaPorApuesta:
    """El stream sirve el mismo pick una vez por dia de horizonte; una apuesta
    se hace UNA vez. Medido el 2026-08-27: 13.999 filas para 6.379 picks."""

    def _servings(self, dias: int) -> pd.DataFrame:
        base = _stream(1, edge_wins=True)
        out = pd.concat([base.assign(generated_at=f"2026-08-2{d}T12:00:00Z")
                         for d in range(1, dias + 1)], ignore_index=True)
        return out

    def test_repeated_servings_collapse_to_one_row(self):
        assert len(prepare(self._servings(7))) == 2  # dos caras, un evento

    def test_the_kept_serving_is_the_first_one(self):
        d = self._servings(5)
        d.loc[d["generated_at"] == "2026-08-21T12:00:00Z", "price_decimal"] = 3.0
        assert set(prepare(d)["price_decimal"]) == {3.0}

    def test_a_stream_without_generated_at_still_collapses(self):
        d = self._servings(4).drop(columns=["generated_at"])
        assert len(prepare(d)) == 2

    def test_without_selection_nothing_is_collapsed(self):
        """Colapsar por una clave incompleta fusionaria picks DISTINTOS del
        mismo partido: borrar informacion es peor que contarla dos veces."""
        d = self._servings(3).drop(columns=["selection"])
        assert len(prepare(d)) == 6


class TestPrepare:
    def test_excludes_push_and_void(self):
        df = _stream(30, edge_wins=True)
        df.loc[:5, "result"] = "push"
        df.loc[6:9, "result"] = "void"
        assert set(prepare(df)["result"]) == {"win", "loss"}

    def test_drops_non_finite_price_and_edge(self):
        df = _stream(30, edge_wins=True)
        df.loc[0, "price_decimal"] = np.nan
        df.loc[1, "estimated_edge"] = np.inf
        out = prepare(df)
        assert np.isfinite(out["_price"]).all()
        assert np.isfinite(out["_edge"]).all()
        assert len(out) == len(df) - 2

    def test_roi_is_flat_unit_pnl(self):
        out = prepare(_stream(10, edge_wins=True, price=2.5))
        assert set(np.round(out["_roi"], 6)) == {1.5, -1.0}

    def test_rebuilds_edge_when_column_absent(self):
        df = _stream(10, edge_wins=True, price=2.0).drop(columns=["estimated_edge"])
        # p=0.5, precio=2.0 -> edge exactamente 0.
        assert prepare(df)["_edge"].abs().max() == pytest.approx(0.0)

    def test_missing_mandatory_column_raises(self):
        df = _stream(10, edge_wins=True).drop(columns=["event_id"])
        with pytest.raises(ValueError, match="event_id"):
            prepare(df)


class TestEdgeLadder:
    def test_detects_real_advantage(self):
        lad = edge_ladder(_stream(400, edge_wins=True, seed=1),
                          thresholds=(0.0, 0.05), n_boot=400, seed=1)
        top = lad[lad.min_edge == 0.05].iloc[0]
        assert top.roi_flat > 0
        assert top.veredicto == "ROI positivo"

    def test_detects_inverted_selection(self):
        lad = edge_ladder(_stream(400, edge_wins=False, seed=2),
                          thresholds=(0.0, 0.05), n_boot=400, seed=1)
        top = lad[lad.min_edge == 0.05].iloc[0]
        assert top.roi_flat < 0
        assert top.veredicto == "ROI negativo"

    def test_thin_slice_reports_nan_interval_not_a_verdict(self):
        lad = edge_ladder(_stream(5, edge_wins=True), thresholds=(0.0, 0.05),
                          n_boot=100, seed=1)
        thin = lad[lad.min_edge == 0.05].iloc[0]
        assert thin.n_rows < MIN_ROWS
        assert np.isnan(thin.roi_lo) and np.isnan(thin.roi_hi)
        assert thin.veredicto == "indistinguible de 0"

    def test_price_floor_filters_by_implied_probability(self):
        df = _stream(200, edge_wins=True)
        df.loc[df.index[:100], "implied_probability_novig"] = 0.10
        wide = edge_ladder(df, thresholds=(0.0,), n_boot=100, seed=1).iloc[0]
        floored = edge_ladder(df, thresholds=(0.0,), price_floor=0.35,
                              n_boot=100, seed=1).iloc[0]
        assert floored.n_rows < wide.n_rows


class TestEdgeSignal:
    def test_delta_positive_when_selection_helps(self):
        sig = edge_signal(_stream(400, edge_wins=True, seed=3), n_boot=400, seed=1)
        assert sig["delta"] > 0
        assert sig["delta_lo"] > 0

    def test_delta_negative_when_selection_hurts(self):
        sig = edge_signal(_stream(400, edge_wins=False, seed=4), n_boot=400, seed=1)
        assert sig["delta"] < 0
        assert sig["delta_hi"] < 0

    def test_no_interval_without_enough_rows_on_both_sides(self):
        df = _stream(400, edge_wins=True)
        df = df[df.selection == "A"]  # solo un grupo
        sig = edge_signal(df, n_boot=100, seed=1)
        assert np.isnan(sig["delta_lo"]) and np.isnan(sig["delta_hi"])


class TestClusterBootstrap:
    def test_clustering_changes_the_answer_versus_treating_rows_as_independent(self):
        """El punto de todo el modulo: las dos caras de un mercado no son dos
        observaciones independientes, y tratarlas como tales da otro intervalo.

        Aqui el fixture las hace exactamente de suma cero (mismo precio, una gana
        y otra pierde), asi que el ROI de CADA evento es 0 y el intervalo
        correcto tiene ancho nulo. El bootstrap por filas, en cambio, fabrica
        dispersion que no existe.
        """
        df = prepare(_stream(200, edge_wins=True, seed=5))
        roi = df["_roi"].to_numpy()
        clustered = cluster_bootstrap_ci(roi, df["event_id"].to_numpy(),
                                         n_boot=800, seed=1)
        naive = cluster_bootstrap_ci(roi, np.arange(len(roi)), n_boot=800, seed=1)
        assert clustered == pytest.approx((0.0, 0.0), abs=1e-9)
        assert (naive[1] - naive[0]) > 0.05

    def test_single_cluster_gives_nan_not_a_zero_width_interval(self):
        lo, hi = cluster_bootstrap_ci(np.array([1.0, 2.0, 3.0]),
                                      np.array(["a", "a", "a"]), n_boot=50)
        assert np.isnan(lo) and np.isnan(hi)

    def test_is_deterministic_for_a_given_seed(self):
        v, c = np.arange(100.0), np.repeat(np.arange(20), 5)
        assert cluster_bootstrap_ci(v, c, n_boot=200, seed=9) == \
            cluster_bootstrap_ci(v, c, n_boot=200, seed=9)

    def test_custom_stat_is_honoured(self):
        v, c = np.arange(100.0), np.repeat(np.arange(20), 5)
        lo, hi = cluster_bootstrap_ci(v, c, n_boot=200, seed=9,
                                      stat=lambda x: float(np.median(x)))
        assert lo < 50 < hi


class TestCapLadder:
    """El cap de plausibilidad (`risk.max_plausible_edge`) es el control con mas
    trabajo efectivo del sistema -- el 63% de las filas descartadas de un run
    real llevan su flag, mas que el gate de prediccion -- y hasta 2026-08-26
    nadie habia medido si acierta."""

    def _mixed(self, n_events: int = 300) -> pd.DataFrame:
        """Edges pequenos que ganan al 60%, edges grandes que ganan al 25%.
        Es la forma medida: edge declarado alto => ROI realizado peor."""
        rng = np.random.default_rng(11)
        rows = []
        for i in range(n_events):
            for edge, p in ((0.03, 0.60), (0.30, 0.25)):
                rows.append({
                    "league": "t", "market": "h2h", "event_id": f"e{i}",
                    "price_decimal": 2.0, "estimated_edge": edge,
                    "result": "win" if rng.random() < p else "loss",
                })
        return pd.DataFrame(rows)

    def test_flags_a_cap_that_cuts_the_worst_picks(self):
        row = cap_ladder(self._mixed(), caps=(0.10,), n_boot=300, seed=1).iloc[0]
        assert row.roi_cortadas < row.roi_pasan
        assert row.veredicto == "el cap corta lo peor"

    def test_flags_a_cap_that_cuts_good_picks(self):
        """Contraprueba: con la relacion invertida el veredicto debe cambiar.
        Sin este test, uno que siempre dijera 'corta lo peor' pasaria igual."""
        df = self._mixed()
        df["estimated_edge"] = df["estimated_edge"].map({0.03: 0.30, 0.30: 0.03})
        lad = cap_ladder(df, caps=(0.10,), n_boot=300, seed=1)
        assert lad.iloc[0].veredicto == "el cap corta picks buenos"

    def test_infinite_cap_blocks_nothing(self):
        row = cap_ladder(self._mixed(), caps=(float("inf"),),
                         n_boot=200, seed=1).iloc[0]
        assert row.n_cortadas == 0
        assert row.veredicto == "sin cap"

    def test_only_positive_edge_rows_enter_the_ladder(self):
        """El cap actua sobre lo que el selector elegiria, no sobre todo el
        stream: incluir edges negativos falsearia el denominador."""
        df = self._mixed()
        extra = df.head(50).copy()
        extra["estimated_edge"] = -0.20
        extra["event_id"] = extra["event_id"] + "_neg"
        row = cap_ladder(pd.concat([df, extra]), caps=(float("inf"),),
                         n_boot=200, seed=1).iloc[0]
        assert row.n_pasan == len(df)
