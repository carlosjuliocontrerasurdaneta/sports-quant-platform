"""El arnes walk-forward de `scripts/measure_features.py` debe AVANZAR.

`team_hist` solo recibia `append` en el cebado del warmup y en la rama de
marcador ilegible; el cuerpo normal del bucle terminaba sin reinsertar el
partido evaluado. Resultado: cada partido de test se puntuaba contra el mismo
historial congelado en el borde del warmup, asi que cada feature era una
CONSTANTE por equipo y la correlacion medida era un efecto fijo de equipo, no
una senal walk-forward. Sobre marcadores aleatorios puros el arnes llegaba a
emitir significacion (auditoria 2026-08-31, F-02).

Importa porque es el UNICO arnes del repositorio que mide las features de
`rest_form`, y `streak_coef=0.01` -- hoy el unico coeficiente activo -- se
activo el mismo dia que se escribio, apoyandose en sus cifras.
"""
from __future__ import annotations

import importlib.util

import pytest

from sqp.config import ROOT

SCRIPT = ROOT / "scripts" / "measure_features.py"
WARMUP = 20


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_features", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _fixture_results(n: int = 60) -> list[dict]:
    """Liga sintetica de 4 equipos, un partido por dia, marcadores deterministas."""
    teams = ["T0", "T1", "T2", "T3"]
    out = []
    for i in range(n):
        out.append({
            "date": f"2026-{1 + i // 28:02d}-{(i % 28) + 1:02d}",
            "home": teams[i % 4], "away": teams[(i + 1) % 4],
            "home_score": 3 + (i % 3), "away_score": 1 + ((i + 1) % 3),
        })
    return out


@pytest.fixture
def harness(monkeypatch):
    """Modulo cargado con un `ResultsStore` falso que sirve el fixture."""
    mod = _load_module()
    results = _fixture_results(60)

    class FakeStore:
        def __init__(self, root):
            pass

        def load(self, league):
            return list(results)

    monkeypatch.setattr(mod, "ResultsStore", FakeStore)
    return mod, results


def _spy_on_streak(mod, monkeypatch, record):
    real = mod.team_streak

    def spy(team, prior, normalize=None):
        record(prior)
        return real(team, prior, normalize)

    monkeypatch.setattr(mod, "team_streak", spy)


def test_history_grows_across_the_test_set(harness, monkeypatch):
    """Antes del arreglo, la longitud del historial previo era una sola
    constante por equipo durante todo el tramo de test."""
    mod, _ = harness
    seen: list[int] = []
    _spy_on_streak(mod, monkeypatch, lambda prior: seen.append(len(prior)))

    mod._measure_league("mlb", warmup=WARMUP, totals_ref=None)

    assert seen, "el arnes no evaluo ningun partido"
    assert len(set(seen)) > 1, (
        "el historial previo es constante: el arnes sigue congelado en el warmup")
    assert max(seen) > min(seen)


def test_history_never_includes_the_game_being_evaluated(harness, monkeypatch):
    """El arreglo no puede introducir lookahead: la reinsercion va DESPUES de
    calcular todas las senales del partido en curso."""
    mod, results = harness
    violations: list[str] = []
    calls = [0]

    def _same(a: dict, b: dict) -> bool:
        return (a.get("date") == b.get("date") and a.get("home") == b.get("home")
                and a.get("away") == b.get("away"))

    def check(prior):
        # Dos llamadas por partido de test (local y visitante), en orden: la
        # llamada k corresponde a results[WARMUP + k // 2].
        idx = WARMUP + calls[0] // 2
        calls[0] += 1
        if idx < len(results) and any(_same(r, results[idx]) for r in prior):
            violations.append(str(results[idx]))

    _spy_on_streak(mod, monkeypatch, check)
    mod._measure_league("mlb", warmup=WARMUP, totals_ref=None)

    assert calls[0] == 2 * (len(results) - WARMUP), "el espia no cubrio el tramo de test"
    assert not violations, (
        f"lookahead: el partido evaluado estaba en su propio historial ({violations[:2]})")


def test_the_most_recent_prior_game_advances_with_the_test_set(harness, monkeypatch):
    """La comprobacion decisiva: la fecha del ultimo partido del historial debe
    avanzar. Congelado, se quedaba clavada en el borde del warmup."""
    mod, results = harness
    last_dates: list[str] = []

    def record(prior):
        if prior:
            last_dates.append(str(prior[-1].get("date")))

    _spy_on_streak(mod, monkeypatch, record)
    mod._measure_league("mlb", warmup=WARMUP, totals_ref=None)

    assert len(set(last_dates)) > 1, "la fecha mas reciente del historial no avanza"
    assert max(last_dates) > min(last_dates)


@pytest.mark.parametrize("warmup", [10, 25])
def test_every_test_game_is_still_evaluated(harness, monkeypatch, warmup):
    """El arreglo no debe hacer perder partidos del tramo de test."""
    mod, results = harness
    calls = [0]
    _spy_on_streak(mod, monkeypatch, lambda prior: calls.__setitem__(0, calls[0] + 1))

    mod._measure_league("mlb", warmup=warmup, totals_ref=None)

    assert calls[0] == 2 * (len(results) - warmup)
