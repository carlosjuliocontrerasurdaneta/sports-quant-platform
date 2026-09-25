"""Tests del monitor de degradacion por (liga, mercado). SYNTHETIC only."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sqp.config import Settings
from sqp.exceptions import RegistroEstadoIlegibleError
from sqp.risk.degradation import (DEGRADATION_FILENAME, DEGRADATION_LOG_FILENAME,
                                  degradation_metrics, evaluate_pauses,
                                  load_degradation_registry, paused_from_registry,
                                  run_degradation_monitor,
                                  write_degradation_registry)

TODAY = date(2026, 7, 13)


def _metrics_row(league="mlb", market="totals", n=40, brier_model=0.25,
                 brier_market=0.25, roi_flat=0.0) -> pd.DataFrame:
    return pd.DataFrame([{"league": league, "market": market, "n": n,
                          "brier_model": brier_model, "brier_market": brier_market,
                          "roi_flat": roi_flat}])


def _settled(n: int, *, result="loss", est=0.7, implied=0.5, price=2.0,
             game_date="2026-07-10") -> pd.DataFrame:
    return pd.DataFrame([{"league": "mlb", "market": "totals", "result": result,
                          "estimated_probability": est,
                          "implied_probability_novig": implied,
                          "price_decimal": price, "game_date": game_date,
                          "stake": 0.0, "pnl": 0.0}] * n)


# --- metricas de ventana --------------------------------------------------------

def test_metrics_grading_window_and_values():
    df = pd.concat([
        _settled(3, result="win", game_date="2026-07-10"),
        _settled(1, result="loss", game_date="2026-07-10"),
        _settled(5, result="void", game_date="2026-07-10"),   # no graduada: fuera
        _settled(7, result="loss", game_date="2026-01-01"),   # fuera de ventana
    ], ignore_index=True)
    m = degradation_metrics(df, window_days=60, today=TODAY)
    assert len(m) == 1
    r = m.iloc[0]
    assert r["n"] == 4
    # win: (0.7-1)^2=0.09 x3; loss: (0.7-0)^2=0.49 -> media 0.19
    assert r["brier_model"] == pytest.approx(0.19)
    # implied 0.5: (0.25*3 + 0.25)/4 = 0.25
    assert r["brier_market"] == pytest.approx(0.25)
    # stake plano: 3 wins x (2.0-1) + 1 loss x (-1) = +2 sobre 4 picks
    assert r["roi_flat"] == pytest.approx(0.5)


def test_metrics_empty_and_missing_columns():
    assert degradation_metrics(pd.DataFrame(), today=TODAY).empty
    no_implied = _settled(4).drop(columns=["implied_probability_novig"])
    m = degradation_metrics(no_implied, today=TODAY)
    assert pd.isna(m.iloc[0]["brier_market"])  # sin baseline: no dispara Brier


# --- gate de pausa / reanudacion -------------------------------------------------

def test_pause_on_brier_worse_than_market():
    markets, trans = evaluate_pauses(
        _metrics_row(brier_model=0.30, brier_market=0.25), {}, min_n=30)
    entry = markets["mlb|totals"]
    assert entry["paused"] and entry["reasons"] == ["brier_worse_than_market"]
    assert len(trans) == 1 and trans[0]["action"] == "pause"


def test_pause_on_roi_below_threshold():
    markets, _ = evaluate_pauses(_metrics_row(roi_flat=-0.30), {}, min_n=30)
    assert markets["mlb|totals"]["reasons"] == ["roi_flat_below_threshold"]


def test_no_pause_below_min_n_or_within_thresholds():
    markets, trans = evaluate_pauses(
        _metrics_row(n=10, brier_model=0.40, brier_market=0.25), {}, min_n=30)
    assert not markets["mlb|totals"]["paused"] and not trans
    markets, trans = evaluate_pauses(_metrics_row(roi_flat=-0.10), {}, min_n=30)
    assert not markets["mlb|totals"]["paused"] and not trans


def test_hysteresis_holds_then_resumes():
    paused_prev = {"mlb|totals": {"paused": True, "since": "2026-07-01T00:00:00",
                                  "reasons": ["roi_flat_below_threshold"]}}
    # roi recupero sobre roi_pause pero no llega a roi_resume: sigue pausado
    markets, trans = evaluate_pauses(
        _metrics_row(roi_flat=-0.10), paused_prev, min_n=30,
        roi_pause=-0.15, roi_resume=-0.05)
    entry = markets["mlb|totals"]
    assert entry["paused"] and entry["reasons"] == ["hysteresis_hold"]
    assert entry["since"] == "2026-07-01T00:00:00" and not trans
    # ambas metricas recuperadas: reanuda y deja transicion
    markets, trans = evaluate_pauses(
        _metrics_row(roi_flat=0.02), paused_prev, min_n=30)
    assert not markets["mlb|totals"]["paused"]
    assert len(trans) == 1 and trans[0]["action"] == "resume"


def test_insufficient_sample_never_lifts_a_pause():
    paused_prev = {"mlb|totals": {"paused": True, "since": "2026-07-01T00:00:00",
                                  "reasons": ["brier_worse_than_market"]}}
    for metrics in (pd.DataFrame(), _metrics_row(n=5, roi_flat=0.10)):
        markets, trans = evaluate_pauses(metrics, paused_prev, min_n=30)
        assert markets["mlb|totals"]["paused"] and not trans


# --- registro y fusion ------------------------------------------------------------

def test_registry_roundtrip_and_paused_map(tmp_path):
    markets = {"mlb|totals": {"paused": True, "since": "x", "reasons": ["r"],
                              "n": 40, "brier_model": 0.3, "brier_market": None,
                              "roi_flat": -0.2, "updated_at": "x"},
               "nba|h2h": {"paused": False, "since": None, "reasons": [], "n": 50,
                           "brier_model": 0.2, "brier_market": 0.21,
                           "roi_flat": 0.01, "updated_at": "x"}}
    path = write_degradation_registry(markets, tmp_path, params={"min_n": 30})
    assert path.name == DEGRADATION_FILENAME
    assert load_degradation_registry(tmp_path) == markets
    assert paused_from_registry(markets) == {"mlb": ["totals"]}
    assert load_degradation_registry(tmp_path / "nope") == {}


def test_run_monitor_e2e_pause_and_idempotent_log(tmp_path):
    # 40 picks degradados: siempre pierde con estimada 0.7 (Brier 0.49 vs 0.25
    # del mercado) y ROI plano -1: ambas condiciones de pausa
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    path, trans, paused = run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert paused == {"mlb": ["totals"]}
    assert len(trans) == 1 and trans[0]["reasons"].count(";") == 1
    assert (tmp_path / DEGRADATION_LOG_FILENAME).exists()
    n_log = len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME))
    # segunda corrida: mismo estado, sin transiciones nuevas ni filas de log
    _, trans2, paused2 = run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert paused2 == paused and not trans2
    assert len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)) == n_log


# --- settings ---------------------------------------------------------------------

def test_settings_degradation_defaults_and_validation():
    s = Settings()
    assert s.degradation_enabled is False  # Settings() directo: monitor apagado
    s.degradation_roi_pause = -0.05
    s.degradation_roi_resume = -0.15  # histeresis invertida: invalida
    with pytest.raises(ValueError, match="DEGRADATION_ROI_RESUME"):
        s.validate()


def test_el_registro_no_pisa_el_temporal_de_otro_proceso(tmp_path):
    """AUD-2026-09-08b: temporal de nombre fijo `degradation.json.tmp`. Misma
    causa raiz que en el gate de CLV y en el de prediccion."""
    ajeno = tmp_path / f"{DEGRADATION_FILENAME}.tmp"
    ajeno.write_text("AJENO A MEDIO ESCRIBIR", encoding="utf-8")
    write_degradation_registry({"mlb|h2h": {"paused": True}}, tmp_path)
    assert ajeno.read_text(encoding="utf-8") == "AJENO A MEDIO ESCRIBIR"
    assert load_degradation_registry(tmp_path)["mlb|h2h"]["paused"] is True


# --- registro ilegible (AUD-002, ronda audit-2026-09-22-r2) -------------------
# El monitor tomaba "no se lee" por "nada estaba pausado", perdia la histeresis
# y lo persistia encima. Ahora lanza sin escribir, y el fallback de `run_all.py`
# reconstruye las pausas vigentes desde el log append-only.

_ILEGIBLES = [b'{"markets": {', b"[1]", b'{"markets": 3}',
              # Bytes no UTF-8: UnicodeDecodeError no es JSONDecodeError y se
              # escapaba al `except` generico del fallback (revision Fable).
              b'{"markets": {"mlb|totals": {"paused": true}}}\xff']


@pytest.mark.parametrize("contenido", _ILEGIBLES)
def test_monitor_con_registro_ilegible_lanza_y_no_lo_reescribe(tmp_path, contenido):
    from sqp.exceptions import RegistroEstadoIlegibleError
    ruta = tmp_path / DEGRADATION_FILENAME
    ruta.write_bytes(contenido)
    with pytest.raises(RegistroEstadoIlegibleError):
        run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert ruta.read_bytes() == contenido
    # El lector del consumidor no lanza: {} (sin auto-pausas propias).
    assert load_degradation_registry(tmp_path) == {}


@pytest.mark.parametrize("contenido", _ILEGIBLES)
def test_fallback_reconstruye_las_pausas_desde_el_log(tmp_path, contenido):
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_bytes(contenido)
    pd.DataFrame([
        {"timestamp": "t1", "league": "mlb", "market": "totals", "action": "pause"},
        {"timestamp": "t2", "league": "nba", "market": "h2h", "action": "pause"},
        {"timestamp": "t3", "league": "mlb", "market": "totals", "action": "resume"},
        {"timestamp": "t4", "league": "wnba", "market": "spreads", "action": "pause"},
    ]).to_csv(tmp_path / DEGRADATION_LOG_FILENAME, index=False)
    assert auto_pauses_from_persisted_registry(tmp_path) == {
        "nba": ["h2h"], "wnba": ["spreads"]}


def test_fallback_sin_log_y_registro_ilegible_no_cae(tmp_path):
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    assert auto_pauses_from_persisted_registry(tmp_path) == {}


def test_fallback_con_registro_legible_no_mira_el_log(tmp_path):
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    write_degradation_registry({"mlb|totals": {"paused": True}}, tmp_path)
    pd.DataFrame([{"timestamp": "t", "league": "nba", "market": "h2h",
                   "action": "pause"}]).to_csv(tmp_path / DEGRADATION_LOG_FILENAME,
                                                index=False)
    assert auto_pauses_from_persisted_registry(tmp_path) == {"mlb": ["totals"]}


# --- KI-061 (REG-001 de la verificacion de r2) -------------------------------------
#
# Con el registro ilegible, el fallback devolvia SOLO las pausas del log: un
# mercado que se degradaba por primera vez no se pausaba mientras durase la
# corrupcion (indefinidamente: el registro ya no se reescribe).


def test_fallback_con_registro_ilegible_pausa_un_mercado_que_se_degrada_ahora(tmp_path):
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    ilegible = b'{"markets": {"nba|h2h": '
    (tmp_path / DEGRADATION_FILENAME).write_bytes(ilegible)
    # nba|h2h ya estaba pausado segun el log; mlb|totals se degrada HOY
    # (40 perdidas con estimada 0.7: Brier 0.49 frente a 0.25 y ROI -1).
    pd.DataFrame([{"timestamp": "t1", "league": "nba", "market": "h2h",
                   "action": "pause"}]).to_csv(tmp_path / DEGRADATION_LOG_FILENAME,
                                               index=False)
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    pausas = auto_pauses_from_persisted_registry(tmp_path, min_n=30, today=TODAY)
    assert pausas == {"mlb": ["totals"], "nba": ["h2h"]}
    # El registro ilegible queda intacto; la pausa nueva se anota en el log
    # (KI-063) marcada como decision del fallback.
    assert (tmp_path / DEGRADATION_FILENAME).read_bytes() == ilegible
    filas = pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)
    assert filas[["league", "market", "action"]].values.tolist() == [
        ["nba", "h2h", "pause"], ["mlb", "totals", "pause"]]
    assert filas["reasons"].iloc[1].startswith("fallback_registro_ilegible;")


@pytest.mark.parametrize("log_ilegible", [b"", b"foo,bar\n1,2\n"],
                         ids=["vacio", "sin_columnas"])
def test_fallback_con_log_ilegible_evalua_hoy_desde_cero(tmp_path, log_ilegible):
    """KI-064: con registro Y log ilegibles se devolvia {} sin evaluar el dia;
    un mercado que se degrada hoy debe pausarse igualmente, sin escribir nada."""
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    (tmp_path / DEGRADATION_LOG_FILENAME).write_bytes(log_ilegible)
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    assert auto_pauses_from_persisted_registry(
        tmp_path, min_n=30, today=TODAY) == {"mlb": ["totals"]}
    assert (tmp_path / DEGRADATION_FILENAME).read_text(encoding="utf-8") == "[1]"
    assert (tmp_path / DEGRADATION_LOG_FILENAME).read_bytes() == log_ilegible


def test_un_apendice_fallido_al_log_se_reconcilia_en_la_siguiente_corrida(
        tmp_path, monkeypatch):
    """KI-064 (b): el registro se escribe antes que el log. Si el apendice
    falla, la pausa vive solo en el registro; la corrida siguiente ya no ve
    transicion. Sin reconciliar, un registro corrupto despues la hacia
    invisible para el fallback, que solo conoce el log."""
    from sqp.risk import degradation as deg
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    real_append = deg.append_degradation_log

    def falla(transitions, bets_dir):
        raise OSError("disco lleno")

    monkeypatch.setattr(deg, "append_degradation_log", falla)
    with pytest.raises(OSError):
        run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert load_degradation_registry(tmp_path)["mlb|totals"]["paused"]
    assert not (tmp_path / DEGRADATION_LOG_FILENAME).exists()

    monkeypatch.setattr(deg, "append_degradation_log", real_append)
    _, trans, paused = run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert not trans and paused == {"mlb": ["totals"]}
    filas = pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)
    assert filas[["league", "market", "action", "reasons"]].values.tolist() == [
        ["mlb", "totals", "pause", "reconciliacion_registro"]]
    # Idempotente: una tercera corrida no anade nada.
    run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    assert len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)) == 1

    # Con el registro corrupto, el fallback ve la pausa aunque hoy no haya
    # liquidadas en la ventana (sin metricas: manda el estado del log).
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    (tmp_path / "settled_mlb.csv").unlink()
    assert deg.auto_pauses_from_persisted_registry(
        tmp_path, min_n=30, today=TODAY) == {"mlb": ["totals"]}


def test_la_reconciliacion_no_duplica_la_transicion_de_hoy(tmp_path):
    """Un corte con transicion propia hoy no recibe ademas una fila de
    reconciliacion, aunque el log estuviera desfasado."""
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    run_degradation_monitor(tmp_path, min_n=30, today=TODAY)
    filas = pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)
    assert filas["action"].tolist() == ["pause"]
    assert "reconciliacion_registro" not in filas["reasons"].tolist()


def test_la_pausa_del_fallback_sobrevive_a_un_segundo_dia_de_corrupcion(tmp_path):
    """KI-063: la pausa que decide el fallback se anota en el log; al dia
    siguiente, con el registro aun ilegible y el corte en zona de histeresis,
    sigue pausado como lo mantendria el monitor normal (hysteresis_hold)."""
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    settled = tmp_path / "settled_mlb.csv"
    _settled(40).to_csv(settled, index=False)
    kw = dict(min_n=30, roi_pause=-0.15, roi_resume=-0.05, today=TODAY)
    assert auto_pauses_from_persisted_registry(tmp_path, **kw) == {"mlb": ["totals"]}
    # Mismo dia otra vez: idempotente, el log no crece.
    auto_pauses_from_persisted_registry(tmp_path, **kw)
    assert len(pd.read_csv(tmp_path / DEGRADATION_LOG_FILENAME)) == 1
    # Dia 2: 20 ganadas y 20 perdidas a 1.8 con estimada 0.5 -> ROI -0.10,
    # Brier igual al mercado: ni pausa nueva ni reanudacion (zona intermedia).
    pd.concat([_settled(20, result="win", est=0.5, price=1.8),
               _settled(20, result="loss", est=0.5, price=1.8)]).to_csv(
        settled, index=False)
    assert auto_pauses_from_persisted_registry(tmp_path, **kw) == {"mlb": ["totals"]}
    assert (tmp_path / DEGRADATION_FILENAME).read_text(encoding="utf-8") == "[1]"


def test_si_el_log_no_se_puede_escribir_el_fallback_aplica_igual(tmp_path, monkeypatch):
    from sqp.risk import degradation as deg

    def falla(transitions, bets_dir):
        raise OSError("disco lleno")

    monkeypatch.setattr(deg, "append_degradation_log", falla)
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    assert deg.auto_pauses_from_persisted_registry(
        tmp_path, min_n=30, today=TODAY) == {"mlb": ["totals"]}


_LOG_PARCIALMENTE_ROTO = [
    # Una fila con un campo de mas: ParserError en la lectura completa, pero
    # `_previous_from_log` (usecols) si lo lee (revision Codex de KI-063).
    "timestamp,league,market,action\nt1,nba,h2h,pause\nt2,wnba,spreads,pause,x\n",
    # TODAS las filas con un campo de mas: pandas 3 desplaza al indice.
    "timestamp,league,market,action\nt1,nba,h2h,pause,x\nt2,wnba,spreads,pause,x\n",
]


@pytest.mark.parametrize("contenido", _LOG_PARCIALMENTE_ROTO,
                         ids=["una_fila", "todas_las_filas"])
def test_el_apendice_no_reescribe_un_log_no_parseable(tmp_path, contenido):
    from sqp.risk.degradation import append_degradation_log
    ruta = tmp_path / DEGRADATION_LOG_FILENAME
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(RegistroEstadoIlegibleError):
        append_degradation_log([{"timestamp": "t3", "league": "mlb",
                                 "market": "totals", "action": "pause"}], tmp_path)
    assert ruta.read_text(encoding="utf-8") == contenido


def test_fallback_con_log_parcialmente_roto_no_borra_el_historial(tmp_path):
    """El fallback aplica la pausa nueva y las del log, pero no puede anotarla
    sin reescribir el log: lo deja intacto y, al dia siguiente, las pausas
    antiguas siguen ahi."""
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    ruta = tmp_path / DEGRADATION_LOG_FILENAME
    ruta.write_text(_LOG_PARCIALMENTE_ROTO[0], encoding="utf-8")
    _settled(40).to_csv(tmp_path / "settled_mlb.csv", index=False)
    esperado = {"mlb": ["totals"], "nba": ["h2h"], "wnba": ["spreads"]}
    for _ in range(2):
        assert auto_pauses_from_persisted_registry(
            tmp_path, min_n=30, today=TODAY) == esperado
        assert ruta.read_text(encoding="utf-8") == _LOG_PARCIALMENTE_ROTO[0]


def test_fallback_conserva_la_histeresis_del_log(tmp_path):
    """Un corte pausado segun el log que HOY esta en zona intermedia (ni peor
    que el mercado ni recuperado) sigue pausado: la histeresis sale del log."""
    from sqp.risk.degradation import auto_pauses_from_persisted_registry
    (tmp_path / DEGRADATION_FILENAME).write_text("[1]", encoding="utf-8")
    pd.DataFrame([{"timestamp": "t1", "league": "mlb", "market": "totals",
                   "action": "pause"}]).to_csv(tmp_path / DEGRADATION_LOG_FILENAME,
                                               index=False)
    # 20 ganadas y 20 perdidas a 2.0 con estimada 0.5: Brier igual al mercado,
    # ROI 0 -> no reanuda con roi_resume=0.05 (zona de histeresis).
    pd.concat([_settled(20, result="win", est=0.5),
               _settled(20, result="loss", est=0.5)]).to_csv(
        tmp_path / "settled_mlb.csv", index=False)
    assert auto_pauses_from_persisted_registry(
        tmp_path, min_n=30, roi_resume=0.05, today=TODAY) == {"mlb": ["totals"]}
