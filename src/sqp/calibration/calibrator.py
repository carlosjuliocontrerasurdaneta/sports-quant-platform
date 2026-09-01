"""Probability calibration (ported from the ML project, adapted to this base).

Two calibrators over estimated probabilities:
  * Isotonic regression (non-parametric, monotonic).
  * Beta calibration (parametric, 3-param logistic in log-odds space).

Trained out-of-sample with a TEMPORAL split (earlier games train, most recent
games validate) — never a random split — per the platform's modeling rules.
Fitted models persist under data/models/ and are applied by sport, since a model
can be well calibrated in one league and miscalibrated in another.

These produce calibrated ESTIMATED probabilities; they do not turn estimates
into certainties.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from sqp.calibration.metrics import (brier_score, calibration_report,
                                     expected_calibration_error)
from sqp.config import ROOT
from sqp.logging_config import get_logger

log = get_logger(__name__)

MODELS_DIR = ROOT / "data" / "models"


def _staging_dir():
    """Where a retrain writes CANDIDATE calibrators. Kept separate from the live
    ``MODELS_DIR`` so a daily retrain can never overwrite a production model or
    promote itself: candidates land here and a separate gated/manual promotion
    copies them up. Derived from ``MODELS_DIR`` so a monkeypatched dir still nests."""
    return MODELS_DIR / "staging"


def _model_path(sport: str, name: str, *, staging: bool = False):
    base = _staging_dir() if staging else MODELS_DIR
    return base / f"{sport}_calibration_{name}.joblib"


@lru_cache(maxsize=128)
def _load_calibrator(path_str: str):
    """Load a persisted calibrator once per process (the daily loop applies it
    per candidate). Keyed by absolute path, so a retrain to a new file -- or a
    test that redirects MODELS_DIR -- is picked up without stale caching."""
    path = Path(path_str)
    if not _verify_hash(path):
        log.warning("joblib integrity check FAILED for %s — file may have been "
                    "modified since training; loading anyway", path.name)
    return joblib.load(path_str)


def _is_monotone_increasing(predict, lo: float = 0.01, hi: float = 0.99,
                            n: int = 99, tol: float = 1e-6) -> bool:
    """True if ``predict`` (a calibrator's ``predict`` method) is non-decreasing
    over ``[lo, hi]``. A calibrator that inverts rank order -- e.g. a degenerate
    beta fit that maps LOW estimated probabilities UP -- must be rejected
    regardless of its aggregate ECE, because ECE is a binned average that does
    NOT penalize non-monotonicity. ``predict`` is called once on the whole grid."""
    grid = np.linspace(lo, hi, n)
    vals = np.asarray(predict(grid), dtype=float)
    return bool(np.all(np.diff(vals) >= -tol))


def _no_extreme_expansion(predict, lo: float = 0.05, hi: float = 0.95,
                          n: int = 19) -> bool:
    """True when ``predict`` never inflates a non-extreme input into
    near-certainty: no input <= 0.90 may map to >= 0.95. That inflation is the
    signature of the 2026-06-30 incident (and the 2026-07-13 wnba_h2h
    candidate): a monotone isotonic step fit on a small sample that sends
    favorites to 0.9+ and manufactures phantom edges, while still passing the
    ECE, Brier AND monotonicity gates on a small validation split. Only the
    high side is guarded: picks exist where estimated > implied, so inflating
    probabilities creates phantom edges, whereas a downward correction (e.g.
    0.10 -> 0.02 for a genuinely overconfident model) merely suppresses picks
    and must stay allowed. Compression toward the middle always passes
    -- de eso se ocupa `_keeps_resolution`."""
    grid = np.linspace(lo, hi, n)
    vals = np.asarray(predict(grid), dtype=float)
    return not bool(np.any((grid <= 0.90) & (vals >= 0.95)))


# Ancho de un bin de ECE: `expected_calibration_error` usa 10 bins sobre [0,1].
# Un mapa cuyo recorrido ENTERO cabe en un bin no pudo mostrarle ninguna
# resolucion al gate de ECE que lo acepto. El umbral sale de ahi, no de mirar
# los candidatos de hoy.
MIN_CALIBRATED_RANGE = 0.10

# La banda donde viven de verdad las probabilidades estimadas, y el recorrido
# minimo que hay que conservar DENTRO de ella. El umbral es el vig por lado de
# un mercado a dos caras (sobrerredondeo tipico del 4-5%): un calibrador que
# reparte menos de eso entre una estimacion de 0,25 y una de 0,75 no puede
# cambiar ninguna decision de apuesta, por mucho recorrido que tenga en las
# colas. Tampoco sale de mirar los candidatos de hoy.
OPERATING_BAND = (0.25, 0.75)
MIN_BAND_RANGE = 0.025


def _keeps_resolution(predict, lo: float = 0.05, hi: float = 0.95,
                      n: int = 19,
                      min_range: float = MIN_CALIBRATED_RANGE,
                      min_band_range: float = MIN_BAND_RANGE) -> bool:
    """True cuando el calibrador conserva algo de RESOLUCION: su recorrido sobre
    `[lo, hi]` es de al menos `min_range`.

    Las otras tres condiciones vigilan el exceso de confianza. Ninguna ve el
    fallo simetrico, que es el colapso: un mapa que manda TODO a 0,50 pasa las
    cuatro puertas de calle. ECE perfecto si la tasa base ronda 0,5 (una sola
    prediccion, un solo bin, observado 0,5); Brier exactamente 0,25, que en
    estos mercados suele batir al del modelo crudo; monotono, porque una
    constante no decrece; y jamas infla nada hacia la certeza.

    No es hipotetico. El 2026-08-28 el candidato de `ligamx_spreads` mapeaba
    0,10 y 0,90 -- y todo lo de en medio -- a **0,500** exactos, y estaba
    ACEPTADO en staging esperando promocion, junto con `ligamx_totals` (0,077 de
    recorrido) y `ligue1_spreads` (0,091).

    Por que importa mas que un Brier: con la probabilidad fijada en una
    constante, `edge = p * cuota - 1` pasa a ser funcion **solo del precio**, asi
    que el mercado entero ordena sus picks por cuota descendente. Es la peor
    politica conocida a la luz de la escalera de `min_edge` invertida. Y la lista
    del operador, que se ordena por probabilidad, se queda plana.

    Si el modelo de verdad no discrimina, lo honesto es quedarse en no-op y que
    hable el modelo crudo, no instalar una constante que convierte el edge en el
    precio.

    **El recorrido total no basta**, y lo enseño el candidato de `wnba_totals`
    del 2026-08-28: recorrido 0,2121 sobre [0,05, 0,95] -- por encima del umbral
    -- pero **exactamente constante en 0,499 de 0,25 a 0,75**. Todo su recorrido
    lo compraban las colas, donde casi no hay picks. Habria pasado el gate y
    aplanado el mercado igual que el que acababa de sustituir. De ahi la segunda
    condicion, sobre la banda operativa: los calibradores legitimos reparten ahi
    entre 0,09 y 0,42, y los colapsados exactamente 0,00.
    """
    grid = np.linspace(lo, hi, n)
    vals = np.asarray(predict(grid), dtype=float)
    if float(vals.max() - vals.min()) < min_range:
        return False
    banda = np.linspace(OPERATING_BAND[0], OPERATING_BAND[1], 51)
    en_banda = np.asarray(predict(banda), dtype=float)
    return bool(float(en_banda.max() - en_banda.min()) >= min_band_range)


def structural_defect(predict) -> str | None:
    """Motivo por el que un mapa es invalido, o `None` si esta sano.

    Son las condiciones de aceptacion que NO necesitan etiquetas: valen igual
    para un candidato recien ajustado, para uno que espera en staging y para uno
    que ya lleva meses en produccion. Una sola definicion porque llegaron a haber
    tres y divergieron: el 2026-08-29 el candidato de `wnba_totals` estaba
    RECHAZADO por el gate y sin embargo el tablero no lo marcaba, porque
    comparaba solo el recorrido ancho y no la banda operativa.

    Las de ECE/Brier no estan aqui a proposito: exigen datos nuevos y las evalua
    el reentreno contra su propio holdout.
    """
    if not _is_monotone_increasing(predict):
        return "no monotono"
    if not _no_extreme_expansion(predict):
        return "expande a extremos"
    if not _keeps_resolution(predict):
        return "colapsado (sin resolucion)"
    return None


def calibrator_defect(key: str, method: str, *,
                      staging: bool) -> str | None:
    """`structural_defect` sobre el artefacto persistido de `key`, o el motivo
    por el que no se puede siquiera evaluar. `None` si esta sano."""
    name = {"isotonic": "iso", "beta": "beta"}.get(str(method))
    if name is None:
        return f"metodo desconocido ({method!r})"
    path = _model_path(key, name, staging=staging)
    if not path.exists():
        return "sin modelo legible"
    try:
        modelo = _load_calibrator(str(path))
    except Exception as exc:  # artefacto corrupto o de otra version de joblib
        log.warning("[%s] calibrador ilegible (%s)", key, exc)
        return "sin modelo legible"
    if modelo is None:
        return "sin modelo legible"
    return structural_defect(modelo.predict)


def calibrator_resolution(key: str, method: str, *,
                          staging: bool = True) -> float | None:
    """Recorrido del calibrador de `key`, o None si no se puede leer.

    Lo usa el tablero para dos avisos distintos: los candidatos colapsados que
    ya estan escritos en staging -- la quinta condicion impide que se acepten
    NUEVOS, pero los aceptados antes siguen ahi hasta el proximo reentreno, y
    `promote_calibration.py --yes` los instalaria-- y los que estan en el
    registro LIVE, que no se reevalua nunca."""
    name = {"isotonic": "iso", "beta": "beta"}.get(method)
    if name is None:
        return None
    path = _model_path(key, name, staging=staging)
    try:
        model = _load_calibrator(str(path))
    except Exception:  # fichero ausente, corrupto o de otra version de joblib
        return None
    if model is None:
        return None
    grid = np.linspace(0.05, 0.95, 19)
    vals = np.asarray(model.predict(grid), dtype=float)
    return float(vals.max() - vals.min())


def _hash_sidecar(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".sha256")


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_hash(path: Path) -> None:
    _hash_sidecar(path).write_text(_compute_sha256(path), encoding="utf-8")


def _verify_hash(path: Path) -> bool:
    """True when the sidecar digest matches the file, or no sidecar exists
    (backward compat: models persisted before this change have no sidecar)."""
    sidecar = _hash_sidecar(path)
    if not sidecar.exists():
        return True
    return _compute_sha256(path) == sidecar.read_text(encoding="utf-8").strip()


def _persist_or_remove(model, path, keep: bool) -> bool:
    """Persist ``model`` to ``path`` when ``keep`` is True; otherwise remove any
    stale model already at ``path``. Returns whether a model is present at
    ``path`` afterwards. This is what makes calibration self-healing: a market
    whose calibrator stops helping is automatically dropped back to a no-op."""
    if keep:
        joblib.dump(model, str(path))
        _write_hash(path)
        return True
    path.unlink(missing_ok=True)
    _hash_sidecar(path).unlink(missing_ok=True)
    return False


def _gate_label(persisted: bool, gate: dict) -> str:
    """'kept', or 'dropped: <failed conditions>' -- e.g. 'dropped: brier'."""
    if persisted:
        return "kept"
    failed = [k.removesuffix("_ok") for k, v in gate.items() if not v]
    return "dropped: " + ",".join(failed) if failed else "dropped"


def _method_registry_path(*, staging: bool = False):
    base = _staging_dir() if staging else MODELS_DIR
    return base / "calibration_methods.json"


def _load_method_registry(*, staging: bool = False) -> dict:
    """Per-(league, market) winning calibrator method. The LIVE registry
    (``staging=False``) backs ``method='auto'`` -- what the pipeline applies --
    while the STAGING registry holds the last retrain's candidates awaiting
    promotion. Returns {} when absent or unreadable, so a missing / corrupt
    registry degrades to a no-op rather than an error."""
    path = _method_registry_path(staging=staging)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _staging_meta_path(key: str):
    return _staging_dir() / f"{key}_n_val.json"


def _write_staging_meta(key: str, *, n_val: int, n_val_events: int) -> None:
    path = _staging_meta_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n_val": n_val, "n_val_events": n_val_events}),
                    encoding="utf-8")


def _load_staging_meta(key: str) -> dict | None:
    path = _staging_meta_path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _set_best_method(key: str, method: str | None, *, staging: bool = False) -> None:
    """Record (or clear with ``None``) the best apply-time method for ``key`` in
    the live registry, or the staging registry when ``staging=True``. Self-healing
    like the model files: a retrain whose calibrators stop helping drops the group
    from the registry, so ``method='auto'`` falls back to a no-op for it.
    Read-modify-write a single JSON; training is sequential."""
    reg = _load_method_registry(staging=staging)
    if method is None:
        reg.pop(key, None)
    else:
        reg[key] = method
    path = _method_registry_path(staging=staging)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2, sort_keys=True), encoding="utf-8")


class BetaCalibrator:
    """Parametric beta calibration for estimated probabilities."""

    def __init__(self) -> None:
        self.a = 1.0
        self.b = 1.0
        self.c = 0.0

    def fit(self, probs: np.ndarray, outcomes: np.ndarray) -> "BetaCalibrator":
        from scipy.optimize import minimize

        def neg_log_loss(params: np.ndarray) -> float:
            a, b, c = params
            p = np.clip(probs, 1e-6, 1 - 1e-6)
            cal = 1 / (1 + np.exp(-(a * np.log(p) - b * np.log(1 - p) + c)))
            cal = np.clip(cal, 1e-6, 1 - 1e-6)
            return float(-np.mean(outcomes * np.log(cal) + (1 - outcomes) * np.log(1 - cal)))

        res = minimize(neg_log_loss, [1.0, 1.0, 0.0], method="Nelder-Mead")
        if not res.success:
            log.warning("BetaCalibrator Nelder-Mead did not converge: %s", res.message)
        self.a, self.b, self.c = res.x
        return self

    def predict(self, probs: np.ndarray) -> np.ndarray:
        p = np.clip(probs, 1e-6, 1 - 1e-6)
        cal = 1 / (1 + np.exp(-(self.a * np.log(p) - self.b * np.log(1 - p) + self.c)))
        return np.clip(cal, 0.01, 0.99)


def train_calibration(df: pd.DataFrame, prob_col: str = "probability",
                      outcome_col: str = "home_win", sport: str = "mlb",
                      val_fraction: float = 0.20, staging: bool = False,
                      time_col: str | None = None,
                      group_col: str | None = None) -> dict:
    """Fit isotonic + beta calibrators on the earlier games and validate on the
    most recent ``val_fraction``. Persists both models and returns OOS metrics.

    With ``staging=True`` the candidate model + method are written to the staging
    area instead of the live one, so a retrain produces candidates that the
    pipeline does NOT apply until a separate promotion call. In production that
    call may be automatic, but only after the OOS and independent-event gates."""
    required = [prob_col, outcome_col]
    if time_col:
        required.append(time_col)
    df2 = df.dropna(subset=required).copy()
    if len(df2) < 40:
        raise ValueError(f"Not enough data to calibrate: {len(df2)} rows (need >=40)")

    if time_col:
        df2 = df2.sort_values(time_col, kind="stable").reset_index(drop=True)
    else:
        df2 = df2.reset_index(drop=True)

    if group_col and group_col in df2.columns:
        # Every side of one event has a deterministically related target (A wins
        # implies B loses; 1X2 carries three correlated rows). Splitting rows can
        # therefore put one side in train and its complement in validation. Build
        # the temporal holdout from whole event groups so that leakage is
        # impossible and expose the independent-event count to the promotion gate.
        groups = df2[group_col].astype(str)
        missing = groups.isin(("", "nan", "None", "<NA>"))
        groups = groups.where(~missing,
                              [f"__row_{i}" for i in range(len(df2))])
        df2 = df2.assign(_split_group=groups)
        if time_col:
            ordered = (df2.groupby("_split_group", sort=False)[time_col]
                       .min().sort_values(kind="stable").index.tolist())
        else:
            ordered = list(dict.fromkeys(groups.tolist()))
        if len(ordered) < 2:
            raise ValueError("Not enough independent events to create a temporal holdout")
        split = max(1, min(len(ordered) - 1,
                           int(len(ordered) * (1.0 - val_fraction))))
        train_groups = set(ordered[:split])
        train_df = df2[df2["_split_group"].isin(train_groups)]
        val_df = df2[~df2["_split_group"].isin(train_groups)]
        n_train_groups, n_val_groups = split, len(ordered) - split
    else:
        split = int(len(df2) * (1.0 - val_fraction))
        train_df, val_df = df2.iloc[:split], df2.iloc[split:]
        n_train_groups, n_val_groups = len(train_df), len(val_df)

    train_probs = train_df[prob_col].to_numpy(dtype=float)
    train_outcomes = train_df[outcome_col].to_numpy(dtype=float)
    val_probs = val_df[prob_col].to_numpy(dtype=float)
    val_outcomes = val_df[outcome_col].to_numpy(dtype=float)

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(train_probs, train_outcomes)

    beta = BetaCalibrator().fit(train_probs, train_outcomes)

    raw_clipped = np.clip(val_probs, 0.01, 0.99)
    raw_val_ece = float(expected_calibration_error(raw_clipped, val_outcomes))
    raw_val_brier = float(brier_score(raw_clipped, val_outcomes))
    iso_val_probs = np.clip(iso.predict(val_probs), 0.01, 0.99)
    val_metrics = calibration_report(iso_val_probs, val_outcomes)
    beta_val_probs = np.clip(beta.predict(val_probs), 0.01, 0.99)
    beta_val_ece = float(expected_calibration_error(beta_val_probs, val_outcomes))
    beta_val_brier = float(brier_score(beta_val_probs, val_outcomes))

    iso_path = _model_path(sport, "iso", staging=staging)
    beta_path = _model_path(sport, "beta", staging=staging)
    iso_path.parent.mkdir(parents=True, exist_ok=True)
    # Self-healing gate: persist a calibrator only when it does NOT worsen the
    # out-of-sample ECE; otherwise drop it (and clean any stale prior model at
    # that path) so live application falls back to a safe no-op. Each model is
    # gated independently because the apply-time method (iso/beta) is
    # configurable. Without this, every retrain re-persisted worsening models
    # (e.g. low-sample markets), silently degrading the live picks.
    # Gate on FOUR conditions: the calibrator must not worsen (1) OOS ECE nor
    # (2) the OOS Brier score, (3) it must be monotone non-decreasing, and (4)
    # it must not inflate non-extreme inputs into near-certainty. ECE is a binned
    # average that tolerates a confident-but-wrong fit -- a monotone yet
    # overfit isotonic step that pushed favorites toward 0.9 passed the ECE gate
    # while manufacturing phantom edges on mlb spreads. The Brier score is a
    # proper scoring rule that penalizes that overconfidence per sample, so it is
    # an ECE-independent requirement, as is monotonicity (which catches a
    # degenerate beta that maps low probabilities UP, inverting rank order).
    # Even the three together are not sufficient on a small validation split:
    # on 2026-07-13 a wnba_h2h isotonic fit passed all three (24 val rows, 8
    # events) while mapping 0.80 -> 0.99, so extremity is its own condition.
    # Verdicts are recorded per condition (not just the conjunction) so the CLI
    # and the daily-run log can say WHY a candidate was dropped -- on 2026-07-02
    # an mlb_spreads fit that improved OOS ECE was dropped and the log gave no
    # reason (it was the Brier), forcing a manual re-fit to diagnose.
    # Y las CUATRO miran hacia el mismo lado: el exceso de confianza. El fallo
    # simetrico -- el colapso a una constante -- las pasa todas de calle, y el
    # 2026-08-28 habia tres candidatos asi ACEPTADOS en staging esperando
    # promocion (`ligamx_spreads` mandaba absolutamente todo a 0,500). De ahi la
    # quinta: ver `_keeps_resolution`.
    iso_gate = {"ece_ok": bool(val_metrics["ece"] <= raw_val_ece),
                "brier_ok": bool(val_metrics["brier_score"] <= raw_val_brier),
                "monotone_ok": _is_monotone_increasing(iso.predict),
                "extreme_ok": _no_extreme_expansion(iso.predict),
                "resolution_ok": _keeps_resolution(iso.predict)}
    beta_gate = {"ece_ok": bool(beta_val_ece <= raw_val_ece),
                 "brier_ok": bool(beta_val_brier <= raw_val_brier),
                 "monotone_ok": _is_monotone_increasing(beta.predict),
                 "extreme_ok": _no_extreme_expansion(beta.predict),
                 "resolution_ok": _keeps_resolution(beta.predict)}
    iso_persisted = _persist_or_remove(iso, iso_path, all(iso_gate.values()))
    beta_persisted = _persist_or_remove(beta, beta_path, all(beta_gate.values()))
    _load_calibrator.cache_clear()  # drop any stale cached model at these paths

    # Per-group best method for method="auto": among the calibrators that beat
    # the raw OOS ECE, record the lowest-ECE one so the live pipeline picks per
    # (league, market) instead of a single global method. None when neither
    # helps -> the group stays a no-op under "auto".
    ranked: list[tuple[str, float]] = []
    if iso_persisted:
        ranked.append(("isotonic", val_metrics["ece"]))
    if beta_persisted:
        ranked.append(("beta", beta_val_ece))
    best_method = min(ranked, key=lambda r: r[1])[0] if ranked else None
    _set_best_method(sport, best_method, staging=staging)
    if staging:
        _write_staging_meta(sport, n_val=len(val_df), n_val_events=n_val_groups)

    log.info("[%s] Calibration fit on %d rows, val %d | raw ECE %.4f -> iso %.4f "
             "(%s) / beta %.4f (%s)", sport, len(train_df), len(val_df), raw_val_ece,
             val_metrics["ece"], _gate_label(iso_persisted, iso_gate),
             beta_val_ece, _gate_label(beta_persisted, beta_gate))
    return {
        "iso_path": str(iso_path),
        "beta_path": str(beta_path),
        "n_train": len(train_df),
        "n_val": len(val_df),
        "n_train_events": n_train_groups,
        "n_val_events": n_val_groups,
        "raw_val_ece": raw_val_ece,
        "raw_val_brier": raw_val_brier,
        "beta_val_ece": beta_val_ece,
        "beta_val_brier": beta_val_brier,
        "val_metrics": val_metrics,
        "iso_persisted": iso_persisted,
        "beta_persisted": beta_persisted,
        "iso_gate": iso_gate,
        "beta_gate": beta_gate,
        "persisted": iso_persisted or beta_persisted,
        "best_method": best_method,
    }


def train_market_calibrators(hist: pd.DataFrame, *, min_n: int = 40,
                             staging: bool = True,
                             prob_col: str = "estimated_probability") -> list[dict]:
    """Train one calibrator per (league, market) from a consolidated pick history
    (columns: league, market, date, ``prob_col``, result).

    ``prob_col`` names the probability being calibrated: the settled source
    passes ``model_probability`` (pure pre-blend model prob -- the serving
    target since research 2026-07-02), while the legacy backtest source keeps
    ``estimated_probability`` (blended).

    Both isotonic and beta models are fitted and persisted per group (the
    apply-time method picks which one); the outcome is whether the selection won
    (graded bets only; push/void excluded), so this calibrates the estimated
    probability against realized frequency per market. Groups with fewer than
    ``min_n`` EVENTOS INDEPENDIENTES son saltados (recorded ``trained=False``)
    -- and since the live application is a no-op without a model, an untrained
    market simply stays uncalibrated. Returns one summary dict per group.

    ``min_n`` cuenta EVENTOS, no filas. Contaba filas, y la fuente dejo de ser
    un historico de una fila por apuesta: ``load_calibration_training_history``
    une el stream servido, cuya clave de dedup conserva a proposito el dia de
    generacion Y la seleccion, asi que un mismo evento aporta una fila por dia de
    horizonte y otra por cada cara del mercado. Medido el 2026-09-01: 18.667
    filas para 3.724 eventos (5,01x); 47 de 52 grupos pasaban el umbral por
    filas y solo 18 lo pasan por eventos, con casos como bundesliga|spreads
    entrenando con 42 filas de **3 eventos**.

    Es el mismo criterio que ya usan las otras dos piezas del modulo -- el corte
    temporal agrupa por ``event_id`` y la promocion exige ``n_val_events`` --, y
    ``n_events`` ya se calculaba aqui mismo dos lineas arriba: se registraba y no
    se usaba. Las filas sin ``event_id`` legible reciben uno sintetico por fila,
    de modo que el esquema antiguo (una fila = un evento) conserva su semantica.


    Candidates are written to STAGING by default. A separate caller chooses the
    manual promotion path or ``auto_promote_calibrators`` with its OOS/event gates.
    """
    out: list[dict] = []
    if hist is None or hist.empty:
        return out
    graded = hist[hist["result"].isin(["win", "loss"])].copy()
    graded["won"] = (graded["result"] == "win").astype(float)
    for (league, market), g in graded.groupby(["league", "market"]):
        if "date" in g.columns:
            g = g.sort_values("date")
        raw_event_ids = (g["event_id"].astype(str).tolist()
                         if "event_id" in g.columns else [""] * len(g))
        event_ids = [eid if eid not in ("", "nan", "None", "<NA>")
                     else f"__row_{i}"
                     for i, eid in enumerate(raw_event_ids)]
        df = pd.DataFrame({"probability": g[prob_col].to_numpy(dtype=float),
                           "won": g["won"].to_numpy(dtype=float),
                           "date": g["date"].astype(str).to_numpy(),
                           "event_id": event_ids}).dropna(
                               subset=["probability", "won", "date"])
        n_events = int(df["event_id"].nunique())
        rec = {"league": str(league), "market": str(market), "n": int(len(df)),
               "n_events": n_events,
               "trained": False}
        if n_events < min_n:
            out.append(rec)
            continue
        try:
            r = train_calibration(df, prob_col="probability", outcome_col="won",
                                  sport=calibration_key(str(league), str(market)),
                                  staging=staging, time_col="date",
                                  group_col="event_id")
            rec.update({"trained": True, "raw_val_ece": r["raw_val_ece"],
                        "cal_val_ece": r["val_metrics"]["ece"],
                        "beta_val_ece": r["beta_val_ece"], "n_val": r["n_val"],
                        "n_val_events": r["n_val_events"],
                        "raw_val_brier": r["raw_val_brier"],
                        "iso_persisted": r["iso_persisted"],
                        "iso_gate": r["iso_gate"], "beta_gate": r["beta_gate"],
                        "best_method": r["best_method"],
                        "persisted": r["persisted"]})
        except ValueError as exc:
            rec["error"] = str(exc)
        out.append(rec)
    revalidate_live_registry()
    return out


def revalidate_live_registry() -> list[str]:
    """Degrada a no-op los calibradores VIVOS que ya no pasan las condiciones
    estructurales. Devuelve las claves degradadas.

    El registro live no se reevaluaba NUNCA: lo escribe la promocion y ahi se
    queda. La democion existia solo en la sincronizacion completa
    (`promote_calibrators` sin `keys`), asi que promoviendo por `--keys` -- o
    sencillamente no promoviendo -- un mapa degradado seguia sirviendo
    indefinidamente. Paso: `wnba_totals` mando toda probabilidad a 0,490 durante
    33 dias (auditoria 2026-08-28, AUD-MED-002).

    Solo se comprueban las condiciones que NO necesitan etiquetas -- monotonia,
    no expansion a extremos y resolucion --, que son justo las que detectan un
    mapa degenerado. Las de ECE/Brier exigen datos nuevos y las evalua el
    reentreno sobre su propio holdout. Es estrictamente CONSERVADOR: solo puede
    degradar a no-op, nunca instalar ni ascender nada, asi que en el peor caso
    un mercado se sirve en crudo, que es el comportamiento por defecto.
    """
    degradados: list[str] = []
    for key, method in list(_load_method_registry(staging=False).items()):
        motivo = calibrator_defect(key, str(method), staging=False)
        if motivo is None:
            continue
        log.warning("[%s] calibrador live DEGRADADO a no-op: %s. El mercado "
                    "pasa a servirse en crudo hasta que se promueva uno "
                    "valido.", key, motivo)
        _set_best_method(key, None, staging=False)
        degradados.append(key)
    if degradados:
        _load_calibrator.cache_clear()
    return degradados


# 15 -> 30 (auditoria 2026-07-24, M-28): el gate elige best_method sobre el
# mismo split que reporta como OOS, asi que un n_val delgado sobreestima al
# candidato; exigir mas eventos independientes compensa ese optimismo de
# seleccion sin rediseñar el split. Compartido entre promote y auto_promote.
AUTO_PROMOTE_MIN_N_VAL = 30


def promote_calibrators(keys: list[str] | None = None,
                        min_n_val: int = AUTO_PROMOTE_MIN_N_VAL,
                        force: bool = False,
                        _log: bool = True) -> list[str]:
    """Promote staged candidate calibrators into the LIVE registry the pipeline
    applies. This is the deliberate step that ``train_market_calibrators`` does
    NOT perform: training only writes to staging, so a daily retrain can never
    push a (possibly degenerate) model into production on its own -- promotion is
    an explicit, reviewable act.

    For each promoted key the staged model file(s) are copied to their live path
    and the live registry is pointed at the staged method. A full promotion
    (``keys=None``) also DEMOTES any live market the latest retrain no longer
    recommends (absent from staging), so promotion faithfully adopts the current
    retrain and self-healing is preserved. Returns the keys promoted.

    ``min_n_val`` guards against promoting a calibrator fitted on a tiny
    out-of-sample split (the same guard ``auto_promote_calibrators`` applies).
    Pass ``force=True`` to override it — but document why.

    Un candidato con DEFECTO ESTRUCTURAL (`calibrator_defect`) no se promueve
    NUNCA, ni con ``force``: `force` existe para asumir una muestra fina, que es
    un juicio sobre la evidencia, no para instalar un mapa que el propio gate de
    entrenamiento rechaza. El agujero era real: el 2026-08-29 el candidato de
    `wnba_totals` -- constante en toda la banda operativa -- seguia en staging, y
    `promote_calibration.py --yes` lo habria instalado en produccion.
    """
    staged = _load_method_registry(staging=True)
    targets = staged if keys is None else {k: v for k, v in staged.items() if k in keys}
    promoted: list[str] = []
    for key, method in targets.items():
        # No lo salta `force`: ver el docstring. Un mapa degenerado no es una
        # muestra fina que uno pueda decidir asumir, es un artefacto invalido.
        defecto = calibrator_defect(key, str(method), staging=True)
        if defecto is not None:
            log.warning("[%s] promocion RECHAZADA: %s. Es el mismo criterio que "
                        "aplica el gate de entrenamiento; ni con force.",
                        key, defecto)
            continue
        if not force:
            meta = _load_staging_meta(key)
            if meta is not None:
                n_val_events = int(meta.get("n_val_events", meta.get("n_val", 0)))
                if n_val_events < min_n_val:
                    log.warning("[%s] skipping promotion: n_val_events=%d < min_n_val=%d "
                                "(pass force=True to override)", key, n_val_events, min_n_val)
                    continue
        for name in ("iso", "beta"):
            src = _model_path(key, name, staging=True)
            if src.exists():
                dst = _model_path(key, name)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(src), str(dst))
                sidecar = _hash_sidecar(src)
                if sidecar.exists():
                    shutil.copyfile(str(sidecar), str(_hash_sidecar(dst)))
        _set_best_method(key, method)
        promoted.append(key)
    if keys is None:  # full sync: demote live markets no longer recommended
        for key in list(_load_method_registry()):
            if key not in staged:
                _set_best_method(key, None)
                for name in ("iso", "beta"):
                    _model_path(key, name).unlink(missing_ok=True)
    _load_calibrator.cache_clear()
    # Log every manual promotion so the audit trail matches auto_promote_calibrators.
    # _log=False when called from auto_promote_calibrators, which handles its own
    # consolidated log (promoted + demoted + skipped in one write) to avoid double
    # entries: the same key would appear twice with different n_val values.
    if promoted and _log:
        now = pd.Timestamp.now(tz="UTC").isoformat()
        staged_reg = _load_method_registry(staging=True)
        entries = []
        for k in promoted:
            meta = _load_staging_meta(k)
            entries.append({"timestamp": now, "key": k, "action": "promoted",
                            "method": staged_reg.get(k, ""),
                            "n_val": meta.get("n_val") if meta else None,
                            "n_val_events": meta.get("n_val_events") if meta else None})
        log_path = MODELS_DIR / "promotion_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        new_df = pd.DataFrame(entries)
        if log_path.exists():
            try:
                prior = pd.read_csv(log_path)
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                prior = pd.DataFrame()
            cols = list(prior.columns) + [c for c in new_df.columns if c not in prior.columns]
            new_df = pd.concat([prior.reindex(columns=cols),
                                new_df.reindex(columns=cols)], ignore_index=True)
        tmp = log_path.with_suffix(".csv.tmp")
        new_df.to_csv(tmp, index=False)
        tmp.replace(log_path)
    return promoted


def auto_promote_calibrators(results: list[dict], *,
                             min_n_val: int = AUTO_PROMOTE_MIN_N_VAL) -> dict:
    """Adopt the latest gated retrain into the LIVE registry without a human
    step (auto-correction cycle, decision 2026-07-08).

    Promotes exactly the staged keys whose fit passed the OOS gates (ECE +
    Brier + monotonicity, enforced at staging time by ``train_calibration``)
    AND validated on at least ``min_n_val`` independent out-of-sample events -- the guard
    that would have kept the 2026-07-02 ``n_val=9`` step-function candidate
    out of production. Staged-but-small groups are left in staging (they keep
    accruing sample). Live keys the retrain no longer recommends are demoted
    to safe no-op, preserving the self-healing of a full manual promotion.
    Every action is appended to ``data/models/promotion_log.csv`` so the
    auto-corrections stay auditable after the fact.

    Returns ``{"promoted": [...], "demoted": [...], "skipped": [...]}``.
    """
    staged = _load_method_registry(staging=True)
    eligible: list[tuple[str, dict]] = []
    skipped: list[tuple[str, dict]] = []
    for r in results or []:
        key = calibration_key(str(r.get("league", "")), str(r.get("market", "")))
        if key not in staged or not r.get("persisted"):
            continue
        # New summaries report independent events. Fall back to row count for
        # compatibility with staged summaries produced by older versions.
        validation_n = int(r.get("n_val_events", r.get("n_val")) or 0)
        if validation_n >= min_n_val:
            eligible.append((key, r))
        else:
            skipped.append((key, r))
    promoted = promote_calibrators(keys=[k for k, _ in eligible], _log=False) if eligible else []
    demoted = [k for k in _load_method_registry() if k not in staged]
    for key in demoted:
        _set_best_method(key, None)
        for name in ("iso", "beta"):
            _model_path(key, name).unlink(missing_ok=True)
    _load_calibrator.cache_clear()
    now = pd.Timestamp.now(tz="UTC").isoformat()
    # El log se construye sobre lo REALMENTE promovido, no sobre lo elegible.
    # Antes coincidian siempre porque `auto_promote` prefiltraba por el mismo
    # `min_n_val` que `promote_calibrators`; desde que la promocion tambien
    # rechaza defectos estructurales (2026-08-29) un elegible puede acabar
    # rechazado, y registrar "promoted" seria falsear el rastro de auditoria en
    # el fichero que existe justo para poder confiar en el.
    hechas = set(promoted)
    entries = ([{"timestamp": now, "key": k, "action": "promoted",
                 "method": staged.get(k, ""), "n_val": r.get("n_val"),
                 "n_val_events": r.get("n_val_events", r.get("n_val"))}
                for k, r in eligible if k in hechas]
               + [{"timestamp": now, "key": k,
                   "action": f"rejected: {calibrator_defect(k, str(staged.get(k, '')), staging=True) or 'desconocido'}",
                   "method": staged.get(k, ""), "n_val": r.get("n_val"),
                   "n_val_events": r.get("n_val_events", r.get("n_val"))}
                  for k, r in eligible if k not in hechas]
               + [{"timestamp": now, "key": k, "action": "demoted",
                   "method": "", "n_val": None, "n_val_events": None}
                  for k in demoted]
               + [{"timestamp": now, "key": k, "action": "skipped_small_n_val",
                   "method": staged.get(k, ""), "n_val": r.get("n_val"),
                   "n_val_events": r.get("n_val_events", r.get("n_val"))}
                  for k, r in skipped])
    if entries:
        log_path = MODELS_DIR / "promotion_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        new = pd.DataFrame(entries)
        if log_path.exists():
            try:
                prior = pd.read_csv(log_path)
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                prior = pd.DataFrame()
            cols = list(prior.columns) + [c for c in new.columns if c not in prior.columns]
            new = pd.concat([prior.reindex(columns=cols),
                             new.reindex(columns=cols)], ignore_index=True)
        tmp = log_path.with_suffix(".csv.tmp")
        new.to_csv(tmp, index=False)
        tmp.replace(log_path)
    return {"promoted": promoted, "demoted": demoted,
            "skipped": [k for k, _ in skipped]}


def apply_calibration(probs: np.ndarray, sport: str = "mlb",
                      method: str = "isotonic") -> np.ndarray:
    """Apply a previously trained calibrator for ``sport``.

    ``method='auto'`` resolves the per-(league, market) winner recorded at
    training time (``calibration_methods.json``); an unregistered group, an
    unknown method, or a missing model all fall back to returning the input
    probabilities unchanged (safe no-op).

    Un mapa COLAPSADO se ignora aunque este en el registro live. El gate de
    entrenamiento solo protege lo que se acepta a partir de ahora, y el registro
    live no se reevalua nunca: lo escribe la promocion y ahi se queda. El
    2026-08-28 `wnba_totals` llevaba dias en produccion mandando TODA
    probabilidad a 0,490 -- el modelo estimaba entre 0,33 y 0,67 y salia plano --
    con el resultado de que el `estimated_edge` de ese mercado correlacionaba
    **0,97 con la cuota**: sus picks se ordenaban por precio. Comprobarlo aqui
    hace la proteccion independiente de quien escribio el registro, incluido un
    `promote_calibration.py --yes` sobre un candidato degenerado.
    """
    if method == "auto":
        resolved = _load_method_registry().get(sport)
        if resolved is None:
            return probs
        method = resolved
    name = {"isotonic": "iso", "beta": "beta"}.get(method)
    if name is None:
        return probs
    path = _model_path(sport, name)
    if not path.exists():
        return probs
    cal = _load_calibrator(str(path))
    if not _keeps_resolution(cal.predict):
        log.warning("[%s] calibrador live COLAPSADO (recorrido < %.2f, o < %.3f "
                    "dentro de [%.2f, %.2f]): se ignora y se sirve en crudo. "
                    "Revisar con scripts/promote_calibration.py.",
                    sport, MIN_CALIBRATED_RANGE, MIN_BAND_RANGE, *OPERATING_BAND)
        return probs
    return np.clip(cal.predict(probs), 0.01, 0.99)


def calibration_key(sport: str, market: str | None = None) -> str:
    """Composite model key. Markets are calibrated separately (a model can be
    well calibrated on moneyline yet biased on totals), so the live key is
    ``"<league>_<market>"`` -- e.g. ``"mlb_h2h"`` -- reusing the per-sport
    persistence/api unchanged."""
    return f"{sport}_{market}" if market else sport


def calibrate_probability(p: float, sport: str, market: str | None = None,
                          method: str = "isotonic") -> float:
    """Calibrate a single estimated probability for ``(sport, market)``. Returns
    ``p`` unchanged when no model exists (safe no-op), so callers can apply it
    unconditionally behind a feature flag."""
    key = calibration_key(sport, market)
    out = apply_calibration(np.asarray([p], dtype=float), sport=key, method=method)
    return float(out[0])
