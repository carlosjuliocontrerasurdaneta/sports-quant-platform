import pandas as pd
import pytest

from sqp.calibration.data import TRAINING_COLS, load_settled_training_history


def _write_settled(bets_dir, name, rows):
    bets_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(bets_dir / f"settled_{name}.csv", index=False)


def test_adjusted_probability_is_the_training_target_when_present(tmp_path):
    # The calibrator is applied to _p_adj at serve; training must mirror it, so
    # adjusted_probability (the served pre-blend belief) is the training target
    # when present -- not the raw model_probability nor the blended estimate.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.62, "adjusted_probability": 0.70,
         "estimated_probability": 0.58, "result": "win",
         "event_id": "e1", "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert "adjusted_probability" in TRAINING_COLS
    assert out.loc[0, "adjusted_probability"] == pytest.approx(0.70)
    assert out.loc[0, "model_probability"] == pytest.approx(0.62)  # raw kept for the gate


def test_adjusted_probability_falls_back_to_model_probability(tmp_path):
    # Old-schema rows (before adjusted_probability existed) train on the raw
    # model_probability, where _p_adj == model anyway (Σadj was tiny).
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.62, "estimated_probability": 0.58,
         "result": "win", "event_id": "e1", "game_date": "2026-06-20",
         "generated_at": "2026-06-20T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "adjusted_probability"] == pytest.approx(0.62)


def test_projects_to_training_schema(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.62, "estimated_probability": 0.58, "result": "win",
         "event_id": "e1", "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
        {"market": "spreads", "model_probability": 0.66, "estimated_probability": 0.61, "result": "loss",
         "game_date": "2026-06-21", "generated_at": "2026-06-21T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert list(out.columns) == TRAINING_COLS
    assert out.loc[0, "league"] == "mlb"
    assert out.loc[0, "market"] == "h2h"
    assert out.loc[0, "date"] == "2026-06-20"
    assert out.loc[0, "event_id"] == "e1"
    assert out.loc[0, "model_probability"] == pytest.approx(0.62)
    assert set(out["result"]) == {"win", "loss"}


def test_date_falls_back_to_generated_at(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.55, "estimated_probability": 0.55, "result": "win",
         "game_date": "", "generated_at": "2026-06-22T09:30:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-22"


def test_drops_rows_without_any_date(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.55, "estimated_probability": 0.55, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
        {"market": "h2h", "model_probability": 0.61, "estimated_probability": 0.61, "result": "loss",
         "game_date": "", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1
    assert out.loc[0, "date"] == "2026-06-20"


def test_drops_rows_without_model_probability(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.55, "estimated_probability": 0.55, "result": "win",
         "game_date": "2026-06-20", "generated_at": ""},
        {"market": "h2h", "estimated_probability": "", "result": "loss",
         "game_date": "2026-06-21", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1
    assert out.loc[0, "result"] == "win"


def test_date_tracks_game_date_not_row_order(tmp_path):
    # Row inserted later has an EARLIER game_date. `date` must reflect the game
    # date (so the downstream temporal sort is correct), not the row position.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.60, "estimated_probability": 0.60, "result": "loss",
         "game_date": "2026-06-25", "generated_at": ""},
        {"market": "h2h", "model_probability": 0.40, "estimated_probability": 0.40, "result": "win",
         "game_date": "2026-06-10", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-25"
    assert out.loc[1, "date"] == "2026-06-10"
    # Guard against a future accidental sort: order must be preserved as written,
    # not sorted by date (the temporal sort belongs downstream, not here).
    assert out.loc[0, "date"] > out.loc[1, "date"]


def test_training_probability_is_pure_model_probability(tmp_path):
    """Research 2026-07-02: el objetivo de calibracion es p_model PURO (pre-blend),
    no la mezcla p_used. La columna de entrenamiento debe salir de
    model_probability, y una fila sin ella se descarta (mezclar objetivos en un
    mismo calibrador seria incoherente)."""
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.72, "estimated_probability": 0.58,
         "result": "win", "game_date": "2026-06-20", "generated_at": ""},
        {"market": "h2h", "model_probability": "", "estimated_probability": 0.61,
         "result": "loss", "game_date": "2026-06-21", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1                       # la fila sin model_probability cae
    assert out.loc[0, "model_probability"] == pytest.approx(0.72)  # NO 0.58
    assert "model_probability" in TRAINING_COLS


def test_empty_or_missing_dir_is_empty_frame(tmp_path):
    out = load_settled_training_history(tmp_path / "nope")
    assert out.empty
    assert list(out.columns) == TRAINING_COLS


def test_non_iso_game_date_falls_back_to_generated_at(tmp_path):
    # game_date presente pero NO-ISO (dd/mm/yyyy mide 10 chars igual que ISO):
    # una fecha asi ordenaria lexicograficamente distinto que las ISO y rompe la
    # guarda anti-leakage del split temporal -> debe caer a generated_at.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.55, "estimated_probability": 0.55, "result": "win",
         "game_date": "20/06/2026", "generated_at": "2026-06-22T09:30:00Z"},
        {"market": "h2h", "model_probability": 0.60, "estimated_probability": 0.60, "result": "loss",
         "game_date": "2026-13-45", "generated_at": "2026-06-23T09:30:00Z"},  # ISO-shaped, fecha imposible
    ])
    out = load_settled_training_history(tmp_path)
    assert list(out["date"]) == ["2026-06-22", "2026-06-23"]


def test_row_with_no_iso_date_anywhere_is_dropped(tmp_path):
    # Ambas fechas presentes y >=10 chars pero ninguna ISO: la fila cae (una
    # fecha basura ordenaria antes/despues que las reales arbitrariamente).
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.55, "estimated_probability": 0.55, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
        {"market": "h2h", "model_probability": 0.61, "estimated_probability": 0.61, "result": "loss",
         "game_date": "junio 21, 2026", "generated_at": "ayer por la tarde"},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1
    assert out.loc[0, "date"] == "2026-06-20"


def test_market_with_exactly_min_n_trains_and_push_rows_do_not_count(tmp_path, monkeypatch):
    # Frontera exacta del gate de muestra: n graded == min_n entrena; las filas
    # push/void NO cuentan para min_n (39 graded + 3 push = 42 filas no entrena).
    import numpy as np
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(2)

    def rows(market, n_graded, n_push=0):
        graded = [{"market": market, "model_probability": round(0.35 + 0.3 * rng.random(), 3),
                   "estimated_probability": 0.55, "result": "win" if rng.random() < 0.5 else "loss",
                   "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
                  for i in range(n_graded)]
        push = [{"market": market, "model_probability": 0.55, "estimated_probability": 0.55,
                 "result": "push", "game_date": "2026-05-15", "generated_at": ""}
                for _ in range(n_push)]
        return graded + push

    _write_settled(tmp_path, "mlb", rows("h2h", 40) + rows("spreads", 39, n_push=3))
    hist = load_settled_training_history(tmp_path)
    results = cal.train_market_calibrators(hist, min_n=40, prob_col="model_probability")
    by_market = {r["market"]: r for r in results}
    assert by_market["h2h"]["trained"] is True and by_market["h2h"]["n"] == 40
    assert by_market["spreads"]["trained"] is False and by_market["spreads"]["n"] == 39


def _hist_eventos(n_eventos: int, filas_por_evento: int) -> "pd.DataFrame":
    """Historial con `n_eventos` eventos, cada uno repetido `filas_por_evento`
    veces: es la forma REAL del stream servido, que acumula una fila por dia de
    horizonte y otra por cada cara del mercado."""
    import numpy as np
    rng = np.random.default_rng(7)
    filas = []
    for e in range(n_eventos):
        for _ in range(filas_por_evento):
            filas.append({"league": "mlb", "market": "h2h",
                          "event_id": f"e{e}",
                          "date": f"2026-05-{1 + e % 28:02d}",
                          "model_probability": round(0.35 + 0.3 * rng.random(), 3),
                          "result": "win" if rng.random() < 0.5 else "loss"})
    return pd.DataFrame(filas)


def test_el_umbral_de_muestra_cuenta_EVENTOS_y_no_filas(tmp_path, monkeypatch):
    """El gate contaba `len(df)`, y la fuente dejo de ser una fila por apuesta:
    `load_calibration_training_history` une el stream servido, cuya clave de
    dedup conserva el dia de generacion y la seleccion. Medido el 2026-09-01:
    18.667 filas para 3.724 eventos (5,01x), 47 de 52 grupos pasaban por filas y
    solo 18 por eventos, con bundesliga|spreads entrenando sobre 42 filas de
    TRES eventos.

    `n_events` ya se calculaba dos lineas arriba del gate: se registraba y no se
    usaba, mientras el corte temporal y la promocion si contaban eventos."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")

    # 200 filas, 10 eventos: sobra por filas, no llega por eventos.
    r = cal.train_market_calibrators(_hist_eventos(10, 20), min_n=40,
                                     prob_col="model_probability")[0]
    assert r["n"] == 200 and r["n_events"] == 10
    assert r["trained"] is False, "200 filas de 10 eventos no son 200 ensayos"


def test_cuarenta_eventos_independientes_si_entrenan(tmp_path, monkeypatch):
    """Contraparte: el umbral no se vuelve inalcanzable. 40 eventos distintos
    entrenan aunque cada uno traiga una sola fila."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    r = cal.train_market_calibrators(_hist_eventos(40, 1), min_n=40,
                                     prob_col="model_probability")[0]
    assert r["n_events"] == 40
    assert r["trained"] is True


def test_esquema_antiguo_sin_event_id_conserva_una_fila_un_evento(tmp_path, monkeypatch):
    """Las filas sin `event_id` legible reciben uno sintetico por fila, asi que
    el historial liquidado antiguo (una fila = una apuesta = un evento) sigue
    contando como antes. Sin esto, cambiar el gate lo habria dejado sin entrenar
    entero."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    h = _hist_eventos(40, 1).drop(columns=["event_id"])
    r = cal.train_market_calibrators(h, min_n=40, prob_col="model_probability")[0]
    assert r["n"] == 40 and r["n_events"] == 40
    assert r["trained"] is True


def _hist_lados(n_eventos: int) -> "pd.DataFrame":
    """Historial con `selection`/`line`: cada evento aporta sus DOS caras del
    mercado (probabilidades complementarias, resultados opuestos), una fila por
    cara. Es la unidad real de observacion del stream servido."""
    import numpy as np
    rng = np.random.default_rng(11)
    filas = []
    for e in range(n_eventos):
        p = round(0.30 + 0.4 * rng.random(), 3)
        gana_home = bool(rng.random() < p)
        fecha = f"2026-05-{1 + e % 28:02d}"
        filas.append({"league": "mlb", "market": "h2h", "event_id": f"e{e:03d}",
                      "selection": "home", "line": float("nan"), "date": fecha,
                      "model_probability": p,
                      "result": "win" if gana_home else "loss"})
        filas.append({"league": "mlb", "market": "h2h", "event_id": f"e{e:03d}",
                      "selection": "away", "line": float("nan"), "date": fecha,
                      "model_probability": round(1.0 - p, 3),
                      "result": "loss" if gana_home else "win"})
    return pd.DataFrame(filas)


def test_evento_repetido_N_veces_pesa_igual_que_una_sola_vez(tmp_path, monkeypatch):
    """AUD-HIGH-001: el stream servido acumula una fila POR DIA DE HORIZONTE del
    mismo lado del mismo evento (mediana 21 filas/evento en mls|h2h). El ajuste
    (`iso.fit`, `BetaCalibrator.fit`) y las metricas de validacion del gate se
    calculaban sobre las filas CRUDAS, asi que un evento servido 21 dias pesaba
    21x y el tamaño efectivo del gate era ~1/10 del creido. Un lado repetido N
    veces debe producir EXACTAMENTE el mismo ajuste y las mismas metricas que
    ese lado una sola vez."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")

    base = _hist_lados(60)
    # Un evento temprano (cae en train) y uno tardio (cae en val), ambos lados,
    # repetidos 20 veces mas -- como los sirve el horizonte multi-dia.
    extra = base[base["event_id"].isin(["e005", "e055"])]
    dup = pd.concat([base] + [extra] * 20, ignore_index=True)

    r_base = cal.train_market_calibrators(base, min_n=40,
                                          prob_col="model_probability")[0]
    r_dup = cal.train_market_calibrators(dup, min_n=40,
                                         prob_col="model_probability")[0]
    assert r_base["trained"] and r_dup["trained"]
    assert r_dup["n"] == r_base["n"], "las filas repetidas no son observaciones"
    assert r_dup["n_val"] == r_base["n_val"]
    assert r_dup["n_events"] == r_base["n_events"]
    assert r_dup["n_val_events"] == r_base["n_val_events"]
    for k in ("raw_val_ece", "cal_val_ece", "beta_val_ece", "raw_val_brier"):
        assert r_dup[k] == pytest.approx(r_base[k], abs=1e-12), k
    assert r_dup["iso_gate"] == r_base["iso_gate"]
    assert r_dup["beta_gate"] == r_base["beta_gate"]
    assert r_dup["best_method"] == r_base["best_method"]


def test_las_dos_caras_de_un_mercado_no_se_colapsan(tmp_path, monkeypatch):
    """La unidad independiente es (event_id, selection, line): el mismo lado
    servido 21 dias es UNA observacion, pero las dos caras del evento son DOS
    (resultados opuestos, probabilidades complementarias). El colapso no debe
    fundirlas."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    r = cal.train_market_calibrators(_hist_lados(60), min_n=40,
                                     prob_col="model_probability")[0]
    assert r["n_events"] == 60
    assert r["n"] == 120, "dos caras por evento = dos observaciones"


def test_sin_selection_ni_line_no_se_colapsa_nada(tmp_path, monkeypatch):
    """Historial de esquema antiguo sin `selection`/`line`: no se puede
    distinguir la cara, asi que colapsar por evento fundiria observaciones
    legitimas. Se conserva el comportamiento previo (una fila = una
    observacion), igual que las filas sin `event_id` siguen contando un evento
    cada una."""
    from sqp.calibration import calibrator as cal
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    h = _hist_lados(60).drop(columns=["selection", "line"])
    r = cal.train_market_calibrators(h, min_n=40, prob_col="model_probability")[0]
    assert r["n"] == 120 and r["n_events"] == 60


def test_projection_carries_selection_and_line(tmp_path):
    # La proyeccion debe conservar selection/line: sin ellas el colapso por
    # unidad independiente (event_id, selection, line) es imposible aguas abajo.
    _write_settled(tmp_path, "mlb", [
        {"market": "totals", "selection": "over", "line": 8.5,
         "model_probability": 0.62, "estimated_probability": 0.58, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert "selection" in TRAINING_COLS and "line" in TRAINING_COLS
    assert out.loc[0, "selection"] == "over"
    assert out.loc[0, "line"] == pytest.approx(8.5)


def test_projection_ignores_extra_columns(tmp_path):
    # Un settled con columnas extra (stake, odds, lo que sea) proyecta limpio:
    # solo TRAINING_COLS en el orden canonico, valores intactos.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "model_probability": 0.62, "estimated_probability": 0.58, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z",
         "stake": 12.5, "odds": 1.91, "clv": 0.02, "columna_inesperada": "x"},
    ])
    out = load_settled_training_history(tmp_path)
    assert list(out.columns) == TRAINING_COLS
    assert len(out) == 1
    assert out.loc[0, "model_probability"] == pytest.approx(0.62)


def test_overconfident_settled_feeds_trainable_history(tmp_path, monkeypatch):
    # An overconfident MLB h2h market (est ~0.70, wins ~40%) projected from
    # settled must feed train_market_calibrators and produce a STAGED candidate,
    # proving the new source integrates with the existing gate/staging machinery.
    import numpy as np
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(0)
    n = 200
    wins = rng.random(n) < 0.40  # true ~40% vs claimed ~70% -> overconfident
    rows = [{"market": "h2h", "model_probability": 0.70, "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path, "mlb", rows)

    hist = load_settled_training_history(tmp_path)
    results = cal.train_market_calibrators(hist, min_n=40,
                                           prob_col="model_probability")  # staging default
    mlb = next(r for r in results if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert mlb["persisted"] is True  # a calibrator that lowers OOS Brier was kept
    # Staged, NOT live: nothing was promoted into the live registry.
    assert (tmp_path / "models" / "staging").exists()
    assert cal._load_method_registry(staging=False) == {}


def test_stage_helper_disabled_returns_empty():
    from types import SimpleNamespace
    from sqp.calibration.data import stage_calibrators_from_settled
    assert stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=False)) == []


def test_stage_helper_empty_settled_returns_empty(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    monkeypatch.setattr(cdata, "ROOT", tmp_path)  # empty data/bets
    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    assert out == []


def test_stage_helper_trains_from_settled(tmp_path, monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cdata, "ROOT", tmp_path)
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(1)
    wins = rng.random(200) < 0.40
    rows = [{"market": "h2h", "model_probability": 0.70, "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path / "data" / "bets", "mlb", rows)

    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    mlb = next(r for r in out if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert (tmp_path / "models" / "staging").exists()  # candidate was staged
    assert cal._load_method_registry(staging=False) == {}  # staged, not live
