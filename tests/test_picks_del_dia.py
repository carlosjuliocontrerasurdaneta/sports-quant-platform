"""Pestana "Picks del Dia": TODOS los candidatos, con la razon de su stake.

Motivo de estos tests: la pestana mostraba solo los ACCIONABLES via
`rank_candidates` (stake>0 o flag `shadow_mode`). Al levantar shadow el
2026-08-16 ese flag dejo de emitirse y **la pestana que se abre por defecto
quedo en blanco**, sin que nada lo señalara. El operador paso 53 dias creyendo
que el sistema no generaba nada; generaba 63 candidatos al dia, ninguno con
dinero.

Una tabla vacia y una tabla que dice "0 con stake, 42 cortados por el cap, 20
por el gate" transmiten cosas MUY distintas. Estos tests fijan la segunda.
"""
from __future__ import annotations

import pandas as pd

from sqp.audit.html_report import _picks_records
from sqp.audit.report import rank_candidates


def _cands(tmp_path, rows):
    base = {"event_id": "e1", "league": "mlb", "market": "h2h",
            "selection": "A", "line": None, "price_decimal": 2.0,
            "estimated_probability": 0.55, "implied_probability_novig": 0.5,
            "estimated_edge": 0.10, "kelly_stake_pct": 0.0, "stake": 0.0,
            "home": "H", "away": "V", "flags": "", "data_label": "real",
            "start_time": "2026-08-26T18:00:00Z",
            "generated_at": "2026-08-26T11:00:00+00:00"}
    df = pd.DataFrame([{**base, **r} for r in rows])
    (tmp_path / "candidates_mlb.csv").write_text(df.to_csv(index=False),
                                                 encoding="utf-8")
    return tmp_path


class TestMuestraTodosLosCandidatos:
    def test_incluye_los_de_stake_cero(self, tmp_path):
        """El nucleo: sin esto la pestana estaba vacia y parecia una averia."""
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "BLOQUEADA", "stake": 0.0,
             "flags": "prediction_gate"},
        ]))
        assert [r["selection"] for r in recs] == ["BLOQUEADA"]

    def test_incluye_los_cortados_por_el_cap(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "CAP", "flags": "edge_exceeds_max_plausible"},
        ]))
        assert len(recs) == 1

    def test_incluye_los_pausados(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "PAUSADO", "flags": "market_paused"},
        ]))
        assert len(recs) == 1

    def test_ordena_por_edge_descendente(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"selection": "BAJO", "estimated_edge": 0.01},
            {"selection": "ALTO", "estimated_edge": 0.30},
        ]))
        assert [r["selection"] for r in recs] == ["ALTO", "BAJO"]


class TestColumnaEstado:
    """El 0 tiene que venir explicado. 64 filas a stake 0 sin razon visible
    parecen un fallo del pipeline."""

    def test_reporta_el_flag_como_estado(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [
            {"flags": "edge_exceeds_max_plausible"}]))
        assert recs[0]["estado"] == "edge_exceeds_max_plausible"

    def test_sin_flag_y_con_stake_dice_con_stake(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [{"stake": 5.0, "flags": ""}]))
        assert recs[0]["estado"] == "con stake"

    def test_sin_flag_y_sin_stake_dice_sin_stake(self, tmp_path):
        recs = _picks_records(_cands(tmp_path, [{"stake": 0.0, "flags": ""}]))
        assert recs[0]["estado"] == "sin stake"


class TestNoSeTocoElContadorDeAccionables:
    """`rank_candidates` define "accionable" y alimenta el contador
    `Total accionables` del reporte markdown. Ampliar la PESTANA no debe
    ampliar esa cifra: son preguntas distintas."""

    def test_rank_candidates_sigue_excluyendo_los_de_stake_cero(self):
        df = pd.DataFrame([
            {"stake": 0.0, "flags": "prediction_gate", "estimated_edge": 0.1},
            {"stake": 3.0, "flags": "", "estimated_edge": 0.2},
        ])
        assert len(rank_candidates(df)) == 1


class TestDiaEnHoraLocalNoUTC:
    """El dashboard resolvia "hoy" en UTC. A partir de las 22:00 en Espana
    (00:00Z) buscaba los candidatos del dia SIGUIENTE, no encontraba ninguno y
    mostraba "Sin candidatos accionables hoy" -- cada noche, hasta el run de la
    manana. Detectado por el operador el 2026-08-26 a las 22:15 locales
    (02:15Z del 27).

    Es el mismo fallo -- UTC donde tocaba hora local -- que ya se habia
    corregido en la pestana "Todos los Picks" y quedo sin corregir aqui.
    """

    def test_no_calcula_el_dia_a_partir_de_ahora(self, tmp_path, monkeypatch):
        """La solucion final NO es usar hora local sino no calcular el dia en
        absoluto: se toma el mas reciente presente en los datos. Local arreglaba
        el sintoma de hoy pero volveria a romperse si el run corriera cerca de
        medianoche. Leerlo del dato es inmune al huso."""
        import sqp.audit.html_report as hr

        capturado = {}
        real = hr._picks_records

        def espia(pred_dir, generated_day=None):
            capturado.setdefault("dias", []).append(generated_day)
            return real(pred_dir, generated_day=generated_day)

        monkeypatch.setattr(hr, "_picks_records", espia)
        hr.html_dashboard(predictions_dir=tmp_path / "p",
                          bets_dir=tmp_path / "b", make_latest=False)
        assert capturado["dias"] == [None]

    def test_cae_al_dia_mas_reciente_si_hoy_no_hay(self, tmp_path):
        """Mejor los candidatos de ayer que un tablero en blanco: el blanco es
        lo que hizo creer al operador durante 53 dias que no se generaba nada."""
        pred = tmp_path / "p"
        pred.mkdir()
        df = pd.DataFrame([{
            "event_id": "e1", "league": "mlb", "market": "h2h", "selection": "A",
            "line": None, "price_decimal": 2.0, "estimated_probability": 0.55,
            "implied_probability_novig": 0.5, "estimated_edge": 0.1,
            "kelly_stake_pct": 0.0, "stake": 0.0, "home": "H", "away": "V",
            "flags": "prediction_gate", "data_label": "real",
            "start_time": "2020-01-01T18:00:00Z",
            "generated_at": "2020-01-01T11:00:00+00:00"}])
        (pred / "candidates_mlb.csv").write_text(df.to_csv(index=False),
                                                 encoding="utf-8")
        from sqp.audit.html_report import html_dashboard
        import json
        import re
        path = html_dashboard(predictions_dir=pred, bets_dir=tmp_path / "b",
                              make_latest=False)
        txt = open(path, encoding="utf-8").read()
        data = json.loads(re.search(r"const DATA = (\{.*?\});\n", txt, re.S).group(1))
        assert len(data["picks"]) == 1
