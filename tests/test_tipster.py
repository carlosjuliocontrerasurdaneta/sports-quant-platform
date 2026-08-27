"""Clasificacion del Tipster: A / B / C / NO BET.

Implementa `AGENTS Tipster.md` (encargo del operador, 2026-08-26) como codigo
determinista, porque un agente de Claude Code no puede dispararse desde el
Programador de tareas.

El punto delicado, y por eso hay tests dedicados: el documento asume que "edge
significativo" es senal de calidad (tier A). En ESTE sistema la evidencia dice
lo contrario -- la escalera de `min_edge` va al reves y lo que el cap de
plausibilidad corta rinde -22,6% -- asi que un EV por encima del cap se
clasifica NO BET, no A.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sqp.evaluation.tipster import (classify, expected_value, fair_odds,
                                    tipster_summary, tipster_table)

ROOT = Path(__file__).resolve().parents[1]
CAP = 0.075


class TestFormulasDelDocumento:
    def test_cuota_justa_es_uno_partido_prob(self):
        assert fair_odds(0.64) == pytest.approx(1.5625)

    def test_ev_es_prob_por_cuota_menos_uno(self):
        # ejemplo literal del documento: P=0.60, O=1.80 -> EV = +8%
        assert expected_value(0.60, 1.80) == pytest.approx(0.08)


class TestClasificacion:
    def test_ev_no_positivo_es_no_bet(self):
        tier, _ = classify(ev=-0.05, edge_pp=0.05, casas=50, prob=0.7,
                           max_plausible_ev=CAP)
        assert tier == "NO BET"

    def test_ev_implausible_es_no_bet_no_tier_a(self):
        """El nucleo de la desviacion respecto al documento. Un EV de +38% con
        consenso profundo parece tier A y es error de medida: medido, lo que el
        cap corta rinde -22,6% frente al -5,6% de lo que deja pasar."""
        tier, motivo = classify(ev=0.38, edge_pp=0.15, casas=60, prob=0.75,
                                max_plausible_ev=CAP)
        assert tier == "NO BET"
        assert "implausible" in motivo

    def test_consenso_fino_degrada_a_c(self):
        tier, motivo = classify(ev=0.05, edge_pp=0.05, casas=3, prob=0.7,
                                max_plausible_ev=CAP)
        assert tier == "C"
        assert "casas" in motivo

    def test_edge_marginal_degrada_a_c(self):
        tier, _ = classify(ev=0.01, edge_pp=0.005, casas=50, prob=0.7,
                           max_plausible_ev=CAP)
        assert tier == "C"

    def test_tier_a_exige_consenso_profundo_y_edge_solido(self):
        tier, _ = classify(ev=0.05, edge_pp=0.04, casas=40, prob=0.60,
                           max_plausible_ev=CAP)
        assert tier == "A"

    def test_tier_b_cuando_no_llega_a_a(self):
        tier, _ = classify(ev=0.03, edge_pp=0.025, casas=15, prob=0.55,
                           max_plausible_ev=CAP)
        assert tier == "B"

    def test_todo_tier_lleva_motivo(self):
        """Una etiqueta sin razon no es auditable; el documento exige poder
        explicar cada decision."""
        for args in ((-0.1, 0.05, 50, 0.7), (0.5, 0.2, 60, 0.8),
                     (0.05, 0.05, 2, 0.7), (0.05, 0.04, 40, 0.6)):
            _, motivo = classify(*args, max_plausible_ev=CAP)
            assert motivo


def _served(rows):
    """Base calibrada para caer en tier A: ev=0.045 (dentro del cap 0.075),
    edge_pp=0.04, casas=40. Una base con cuota 2.0 y prob 0.55 daria ev=0.10 y
    saldria NO BET por implausible -- correcto, pero inutil como fixture."""
    base = {"league": "mlb", "event_id": "e1", "market": "h2h",
            "selection": "A", "line": None, "price_decimal": 1.90,
            "estimated_probability": 0.55, "implied_probability_novig": 0.51,
            "books_count": 40, "game_date": "2026-08-26"}
    return pd.DataFrame([{**base, **r} for r in rows])


class TestTabla:
    def test_ordena_por_tier_y_luego_ev(self):
        t = tipster_table(_served([
            {"selection": "ES_B", "books_count": 15,
             "estimated_probability": 0.54, "implied_probability_novig": 0.515},
            {"selection": "ES_A"},   # la base cae en A
        ]), max_plausible_ev=CAP)
        assert list(t["tier"])[:2] == ["A", "B"]
        assert list(t["seleccion"])[:2] == ["ES_A", "ES_B"]

    def test_marca_selecciones_correlacionadas_del_mismo_evento(self):
        """Varias selecciones del MISMO partido no son riesgos independientes:
        el resultado determina a la vez h2h, spread y en parte el total."""
        t = tipster_table(_served([
            {"event_id": "X", "market": "h2h", "selection": "S1"},
            {"event_id": "X", "market": "spreads", "selection": "S2"},
            {"event_id": "Y", "market": "h2h", "selection": "S3"},
        ]), max_plausible_ev=CAP)
        corr = dict(zip(t["seleccion"], t["correlacionado"]))
        assert corr["S1"] and corr["S2"]
        assert not corr["S3"]

    def test_reporta_las_cuatro_cifras_del_documento(self):
        t = tipster_table(_served([{}]), max_plausible_ev=CAP)
        assert {"cuota_justa", "prob_implicita", "edge_pp", "ev"} <= set(t.columns)

    def test_no_asigna_stake(self):
        """El documento habla de stake, pero la REGLA FUNDAMENTAL del operador
        es generar picks, NO apostar. Esta tabla no puede asignar dinero."""
        t = tipster_table(_served([{}]), max_plausible_ev=CAP)
        assert not any("stake" in c.lower() for c in t.columns)

    def test_resumen_incluye_los_no_bet(self):
        """El documento: "la ausencia de apuesta es una decision valida". Debe
        verse en el resumen, no esconderse."""
        r = tipster_summary(tipster_table(_served([
            {"estimated_probability": 0.30}]), max_plausible_ev=CAP))
        assert set(r) == {"A", "B", "C", "NO BET"}

    def test_frame_vacio_no_revienta(self):
        assert tipster_table(pd.DataFrame()).empty


class TestSeGeneraCadaDia:
    def test_el_orquestador_corre_el_tipster(self):
        bat = (ROOT / "DIARIO_COMPLETO.bat").read_text(encoding="utf-8",
                                                       errors="replace")
        assert "tipster_report.py" in bat

    def test_el_agente_esta_registrado(self):
        p = ROOT / ".claude" / "agents" / "tipster.md"
        assert p.exists()
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        assert "name: tipster" in head
