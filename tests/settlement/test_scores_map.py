"""_scores_map: una entrada malformada no debe abortar la liquidacion de la
liga entera (auditoria 2026-07-24, M-10)."""
from sqp.settlement.runner import _scores_map


def test_malformed_entries_are_skipped_not_fatal():
    raw = [
        {"id": "ok", "completed": True, "home_team": "A", "away_team": "B",
         "scores": [{"name": "A", "score": "3"}, {"name": "B", "score": "2"}]},
        # score no numerico: antes tumbaba todo el _scores_map con ValueError
        {"id": "bad_score", "completed": True, "home_team": "A", "away_team": "B",
         "scores": [{"name": "A", "score": "x"}, {"name": "B", "score": "2"}]},
        # entrada sin la clave "name": KeyError por-entrada, no fatal
        {"id": "bad_shape", "completed": True, "home_team": "A", "away_team": "B",
         "scores": [{"nombre": "A"}]},
    ]
    assert _scores_map(raw) == {"ok": (3, 2, "A")}
