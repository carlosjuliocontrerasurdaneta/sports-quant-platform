"""AUD-004 (ronda audit-2026-09-18): el informe de salud expone el estado de
las tareas programadas (ultimo lanzamiento, codigo, historial del Programador)
como rastro independiente del BAT. `pipeline_liveness` dice que no hubo run;
esto dice si la tarea se LANZO y con que codigo, y avisa si el historial del
Programador esta apagado (el motivo por el que los dias 11/15/16-09 quedaron
sin causa diagnosticable).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqp.monitoring.health import (DAILY_TASK, SCHEDULED_TASKS,
                                   scheduled_tasks_status)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


def _raw(*, history=True, daily_last=None, daily_rc=0, extra=None):
    daily_last = daily_last or (NOW - timedelta(hours=3))
    tasks = [{"Task": DAILY_TASK, "State": "Ready",
              "LastRun": daily_last.isoformat(), "LastResult": daily_rc, "Missed": 0}]
    for name in SCHEDULED_TASKS:
        if name != DAILY_TASK:
            tasks.append({"Task": name, "State": "Ready",
                          "LastRun": (NOW - timedelta(hours=1)).isoformat(),
                          "LastResult": 0, "Missed": 0})
    tasks.extend(extra or [])
    return json.dumps({"history_enabled": history, "tasks": tasks})


def test_todo_sano_sin_avisos():
    out = scheduled_tasks_status(_raw(), now=NOW)
    assert out["available"] is True and out["history_enabled"] is True
    assert out["warnings"] == []
    assert set(out["tasks"]) == set(SCHEDULED_TASKS)
    assert out["tasks"][DAILY_TASK]["last_result"] == 0


def test_historial_deshabilitado_avisa_con_el_comando():
    out = scheduled_tasks_status(_raw(history=False), now=NOW)
    assert out["history_enabled"] is False
    assert any("DESHABILITADO" in w and "wevtutil" in w for w in out["warnings"])


def test_tarea_diaria_sin_lanzarse_avisa_distinto_de_un_fallo():
    out = scheduled_tasks_status(_raw(daily_last=NOW - timedelta(days=3)), now=NOW)
    avisos = [w for w in out["warnings"] if w.startswith(DAILY_TASK)]
    assert len(avisos) == 1 and "no se LANZA" in avisos[0] and "3.0 dias" in avisos[0]


def test_codigo_de_salida_distinto_de_cero_avisa_y_running_no():
    out = scheduled_tasks_status(_raw(daily_rc=1), now=NOW)
    assert any(w == f"{DAILY_TASK}: ultimo resultado 0x1" for w in out["warnings"])
    out = scheduled_tasks_status(_raw(daily_rc=0x41301), now=NOW)  # en ejecucion
    assert out["warnings"] == []


def test_tarea_ausente_avisa():
    raw = json.loads(_raw())
    raw["tasks"] = [t for t in raw["tasks"] if t["Task"] != "SQP_Backfill_Cdev"]
    out = scheduled_tasks_status(json.dumps(raw), now=NOW)
    assert any("SQP_Backfill_Cdev" in w and "no encontrada" in w for w in out["warnings"])


def test_sin_acceso_o_ilegible_no_es_ok():
    for raw in (None, "", "no json", "[]", "1"):
        out = scheduled_tasks_status(raw, now=NOW)
        assert out["available"] is False
        assert out["warnings"], raw


def test_un_solo_objeto_en_tasks_se_acepta():
    """ConvertTo-Json devuelve un objeto (no lista) cuando hay una sola tarea."""
    raw = json.dumps({"history_enabled": True,
                      "tasks": {"Task": DAILY_TASK, "State": "Ready",
                                "LastRun": (NOW - timedelta(hours=2)).isoformat(),
                                "LastResult": 0, "Missed": 0}})
    out = scheduled_tasks_status(raw, now=NOW)
    assert DAILY_TASK in out["tasks"]
