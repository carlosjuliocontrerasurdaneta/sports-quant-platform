"""Candados automaticos del principio de independencia del mercado.

Las probabilidades se construyen SOLO con datos deportivos; el mercado solo
sirve para compararlas despues. Fuentes de la especificacion:

- docs/prompts-audit/09-principios-fundamentales.md (P1, P2, P8, P9, con su
  «Candado propuesto»);
- docs/prompts-audit/06-arquitectura-recomendada.md §5.1 (fronteras de
  importacion, REGLA 1 y REGLA 2).

Si el codigo actual viola una regla, el hallazgo NO se esconde ni se arregla
aqui: se registra en ``KNOWN_VIOLATIONS`` / ``KNOWN_DYNAMIC_VIOLATIONS`` (con
motivo y fecha) y los tests exigen que la lista no crezca y que cada entrada
siga existiendo (una entrada obsoleta tambien falla).
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import re
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# --------------------------------------------------------------------------
# Clasificacion de capas (06-arquitectura-recomendada.md §5.1)
# --------------------------------------------------------------------------
SPORTING_DIRS = ("sports", "models", "features")

# Alcance: SOLO sqp.sports, sqp.models y sqp.features (09 P1), mas el fichero
# sqp/markets/settlement_math.py por la clausula 2 de la REGLA 2 (06 §5.1).
# Tratar sqp.pipeline ENTERO como mercado es mas estricto que 06 §5.1, donde se
# nombran modulos concretos (pipeline.price, closing_capture, intraday_scan,
# revalidation, daily) y donde ni ``estimate.py`` ni ``price.py`` existen hoy.
# Prefijos de modulo: coincide el modulo exacto o cualquier submodulo.
MARKET_PREFIXES = (
    "sqp.providers.odds_api",
    "sqp.providers.odds_cache",
    "sqp.storage.odds_store",
    "sqp.markets",              # salvo REGLA 2 (abajo)
    "sqp.risk",
    "sqp.audit.intraday_gate",
    "sqp.evaluation.model_vs_market",
    "sqp.evaluation.edge_information",
    "sqp.pipeline",
)
# Prefijos "por comodin" (sqp.audit.clv*): coincide cualquier modulo que EMPIECE asi.
MARKET_STARTSWITH = ("sqp.audit.clv",)
# REGLA 2: matematica de lineas sin datos de mercado.
ALLOWED_MARKET_MODULES = ("sqp.markets.settlement_math",)

# (modulo importador -> modulo importado, motivo). Fecha del hallazgo: 2026-11-10.
KNOWN_VIOLATIONS: dict[tuple[str, str], str] = {}
KNOWN_DYNAMIC_VIOLATIONS: dict[str, str] = {}
# Frontera dinamica, REGLA 2 (06 §5.1): el paquete ``sqp.markets`` SIEMPRE esta
# en sys.modules, porque Python carga el paquete padre de
# ``sqp.markets.settlement_math``. Es aceptable SOLO si es el paquete vacio y
# perezoso: ``sqp.markets.odds`` y ``sqp.markets.vig`` no deben estar cargados.
PARENT_PACKAGE = "sqp.markets"
FORBIDDEN_WITH_PARENT = ("sqp.markets.odds", "sqp.markets.vig")
# LIMITE conocido: ``import sqp.markets.settlement_math`` enlaza el nombre
# ``sqp`` y eso permite llegar a ``sqp.markets.*`` por atributo sin que ninguna
# importacion lo nombre; el analisis estatico no puede verlo.


def _is_market_module(name: str) -> bool:
    if name in ALLOWED_MARKET_MODULES:
        return False
    if any(name == p or name.startswith(p + ".") for p in MARKET_PREFIXES):
        return True
    return any(name.startswith(p) for p in MARKET_STARTSWITH)


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _is_module(name: str) -> bool:
    base = SRC.joinpath(*name.split("."))
    return base.with_suffix(".py").exists() or (base / "__init__.py").exists()


def _imported_modules(path: Path) -> set[str]:
    """Todos los modulos importados (estatica y dentro de funciones), con las
    importaciones relativas resueltas contra el paquete del fichero."""
    pkg = _module_name(path)
    if path.name != "__init__.py":
        pkg = pkg.rpartition(".")[0]
    return _imports_of_source(path.read_text(encoding="utf-8"), pkg)


def _imports_of_source(source: str, pkg: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = pkg.split(".")
                if node.level > 1:
                    anchor = anchor[: len(anchor) - (node.level - 1)]
                base = ".".join(anchor + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            unresolved = False
            for alias in node.names:  # ``from pkg import submodulo``
                cand = f"{base}.{alias.name}"
                if _is_module(cand):
                    found.add(cand)
                else:
                    unresolved = True
            # El paquete base solo cuenta si algun alias NO es un submodulo
            # (``from sqp.markets import implied_probability`` toca el paquete).
            if unresolved:
                found.add(base)
    return found


def _sporting_files() -> list[Path]:
    files: list[Path] = []
    for d in SPORTING_DIRS:
        files += sorted((SRC / "sqp" / d).rglob("*.py"))
    files.append(SRC / "sqp" / "markets" / "settlement_math.py")  # REGLA 2, clausula 2
    # sqp/markets/__init__.py NO se barre en estatico: su bloque TYPE_CHECKING
    # importa odds/vig solo para tipos. Una carga ansiosa en el la detecta el
    # test dinamico (odds/vig en sys.modules).
    return files


def test_sporting_layer_never_imports_market_layer_static():
    """P1a / §5.1 test 1 (09-principios-fundamentales.md P1; 06-arquitectura-
    recomendada.md §5.1 REGLA 1 y 2): ningun fichero de sqp.sports, sqp.models
    ni sqp.features importa (ni dentro de funciones) un modulo de la capa de
    mercado. Las violaciones conocidas viven en KNOWN_VIOLATIONS: no pueden
    crecer ni quedar obsoletas."""
    files = _sporting_files()
    assert len(files) > 10, "el recorrido no encontro la capa deportiva"
    for p in MARKET_PREFIXES + ALLOWED_MARKET_MODULES:  # guarda contra la vacuidad
        assert _is_module(p), f"el modulo {p} ya no existe: actualizar la clasificacion"
    found: set[tuple[str, str]] = set()
    for f in files:
        mod = _module_name(f)
        for imp in _imported_modules(f):
            if _is_market_module(imp):
                found.add((mod, imp))
    new = sorted(found - KNOWN_VIOLATIONS.keys())
    stale = sorted(KNOWN_VIOLATIONS.keys() - found)
    assert not new, f"importaciones de capa de mercado NUEVAS en la capa deportiva: {new}"
    assert not stale, f"entradas obsoletas en KNOWN_VIOLATIONS (eliminar): {stale}"


def test_import_resolver_positive_cases():
    """P1a (06 §5.1): casos positivos del resolvedor de importaciones, contra
    la vacuidad."""
    reg = _imported_modules(SRC / "sqp" / "sports" / "registry.py")
    assert {"sqp.sports.adapters", "sqp.sports.base"} <= reg
    dist = _imported_modules(SRC / "sqp" / "models" / "distributions.py")
    assert "sqp.markets.settlement_math" in dist
    assert "sqp.markets" not in dist       # from pkg import submodulo no toca el paquete


def test_import_resolver_package_cases():
    """P1a (06 §5.1): ``import sqp.markets``, ``from sqp import markets`` y
    ``from sqp.markets import implied_probability`` quedan prohibidos;
    ``from sqp.markets import settlement_math`` queda permitido."""
    def bad(code: str) -> bool:
        mods = _imports_of_source(code, "sqp.sports")
        return any(_is_market_module(m) for m in mods)
    assert bad("import sqp.markets")
    assert bad("from sqp import markets")
    assert bad("from sqp.markets import implied_probability")
    assert bad("from sqp.markets import settlement_math, implied_probability")
    assert not bad("from sqp.markets import settlement_math")
    assert bad("from ..markets import odds")          # relativa resuelta


def test_classifier_recognises_market_modules_and_rule_2():
    """P1a (06 §5.1): sanidad del clasificador, para que el test estatico no
    pase por vacuidad."""
    for m in ("sqp.providers.odds_api", "sqp.storage.odds_store", "sqp.markets.odds",
              "sqp.risk.kelly", "sqp.audit.clv", "sqp.audit.clv_movement",
              "sqp.audit.intraday_gate", "sqp.evaluation.model_vs_market",
              "sqp.evaluation.edge_information", "sqp.pipeline.daily"):
        assert _is_market_module(m), m
    for m in ("sqp.markets.settlement_math", "sqp.models.elo", "sqp.features.rest_form",
              "sqp.audit.report", "sqp.providers.espn_scoreboard"):
        assert not _is_market_module(m), m


_DYNAMIC_CODE = """
import json, sys
import sqp.sports.registry, sqp.sports.adapters, sqp.models.distributions
print(json.dumps(sorted(m for m in sys.modules if m == "sqp" or m.startswith("sqp."))))
"""


def test_sporting_imports_do_not_load_market_modules_dynamic():
    """P1a / §5.1 test 2 (09 P1; 06 §5.1): en un subproceso limpio, importar el
    registro de ligas, los adaptadores y las distribuciones no carga en
    sys.modules ningun modulo de capa de mercado (incluidos
    sqp.providers.odds_api y sqp.storage.odds_store). Misma tecnica que
    tests/test_audit_pipeline_isolation.py. Limite: ``import
    sqp.markets.settlement_math`` enlaza el nombre ``sqp`` y permite llegar a
    ``sqp.markets.*`` por atributo.

    REGLA 2 (06 §5.1) y paquete padre: ``sqp.markets`` queda en sys.modules
    porque Python siempre carga el paquete padre de
    ``sqp.markets.settlement_math``. Se permite SOLO si ``sqp.markets.odds`` y
    ``sqp.markets.vig`` NO estan cargados (el paquete vacio y perezoso es
    aceptable; sus submodulos de mercado no)."""
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run([sys.executable, "-c", _DYNAMIC_CODE], env=env,
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    every = set(json.loads(proc.stdout.strip().splitlines()[-1]))
    assert "sqp.sports.registry" in every
    assert "sqp.markets.settlement_math" in every     # el padre se cargo de verdad
    assert PARENT_PACKAGE in every
    assert not (set(FORBIDDEN_WITH_PARENT) & every), "el paquete padre dejo de ser perezoso"
    loaded = {m for m in every if _is_market_module(m)} - {PARENT_PACKAGE}
    new = sorted(loaded - KNOWN_DYNAMIC_VIOLATIONS.keys())
    stale = sorted(KNOWN_DYNAMIC_VIOLATIONS.keys() - loaded)
    assert not new, f"modulos de mercado cargados por la capa deportiva: {new}"
    assert not stale, f"entradas obsoletas en KNOWN_DYNAMIC_VIOLATIONS: {stale}"


def test_domain_prices_imports_nothing_from_sqp():
    """REGLA 2 (06 §5.1): sqp.domain.prices es hoja pura, sin imports de sqp."""
    path = SRC / "sqp" / "domain" / "prices.py"
    assert path.exists()
    mods = _imported_modules(path)
    assert not [m for m in mods if m == "sqp" or m.startswith("sqp.")], mods


def test_odds_reexports_the_single_is_usable_price():
    """La fuente unica vive en sqp.domain.prices; markets.odds solo la reexporta."""
    import sqp.domain.prices as prices
    import sqp.markets.odds as odds
    assert odds.is_usable_price is prices.is_usable_price


# --------------------------------------------------------------------------
# P1b: el adaptador no recibe ni devuelve precios
# --------------------------------------------------------------------------
FORBIDDEN_NAME_PARTS = ("price", "odds", "implied", "novig", "consensus",
                        "closing", "fair")


def _forbidden(name: str) -> bool:
    low = name.lower()
    return any(part in low for part in FORBIDDEN_NAME_PARTS)


def _adapter_classes():
    from sqp.sports.registry import _FAMILY_ADAPTER
    return dict(_FAMILY_ADAPTER)


def test_adapter_estimate_signature_has_no_price_parameters():
    """P1b (09 P1 «Candado propuesto» b): ningun adaptador registrado acepta
    precios en estimate/estimate_f5. spread_line y total_line son umbrales
    legitimos (06 §2: el umbral solo fija donde se evalua la CDF)."""
    adapters = _adapter_classes()
    assert {"basketball", "baseball", "hockey", "soccer", "tennis", "football"} <= set(adapters)
    checked = 0
    for family, cls in adapters.items():
        for meth in ("estimate", "estimate_f5"):
            fn = getattr(cls, meth, None)
            if fn is None:
                continue
            params = [p for p in inspect.signature(fn).parameters if p != "self"]
            assert "event" in params, (family, meth, params)
            bad = [p for p in params if _forbidden(p)]
            assert not bad, f"{cls.__name__}.{meth} recibe parametros de mercado: {bad}"
            checked += 1
    assert checked >= len(adapters)
    sig = inspect.signature(adapters["basketball"].estimate)
    assert {"spread_line", "total_line"} <= set(sig.parameters)  # umbrales permitidos


def test_estimated_probabilities_has_no_market_fields():
    """P1b (09 P1; 06 §5.1 test 3): EstimatedProbabilities no contiene campos
    de precio/implicita/consenso/cierre. Complementa, sin duplicar, el rechazo
    de campos de mercado en freeze_model (tests/test_independent_pricing.py)."""
    from sqp.domain.models import EstimatedProbabilities
    names = [f.name for f in fields(EstimatedProbabilities)]
    assert "home_win_estimated_probability" in names
    assert not [n for n in names if _forbidden(n) or "clv" in n.lower()]


# --------------------------------------------------------------------------
# P2: mezcla y probabilidad pura
# --------------------------------------------------------------------------
def _cal(p, league, market, method):
    """Calibrador sintetico NO identidad y monotono, para detectar en que
    cantidad se aplica."""
    return float(p) ** 1.5


@pytest.fixture
def decision(monkeypatch):
    from sqp.pipeline import probabilities as pr
    seen: list[float] = []

    def spy(p, league, market, method="isotonic"):
        seen.append(float(p))
        return _cal(p, league, market, method)

    monkeypatch.setattr(pr, "calibrate_probability", spy)
    settings = SimpleNamespace(calibration_enabled=True, calibration_method="isotonic")

    def call(p, fair, shrink):
        return pr._decision_probability(p, fair, shrink, "mlb", "h2h", settings)
    call.seen = seen  # type: ignore[attr-defined]
    return call


@pytest.mark.parametrize("p", [0.12, 0.37, 0.5, 0.81])
def test_decision_probability_is_pure_calibrated_without_fair_or_shrink(decision, p):
    """P2 (09 P2 «Candado propuesto» b): con fair=None o shrink=0,
    p_decision == cal(p_model) exactamente y p_used == p_model."""
    cal = _cal(p, "mlb", "h2h", "isotonic")
    for fair, shrink in ((None, 0.5), (None, 0.0), (0.6, 0.0), (0.9, 0.0)):
        p_used, p_dec = decision(p, fair, shrink)
        assert p_dec == cal
        assert p_used == p


@pytest.mark.parametrize("p", [0.2, 0.55, 0.78])
@pytest.mark.parametrize("fair", [0.1, 0.5, 0.93])
@pytest.mark.parametrize("s", [0.1, 0.5, 0.9, 1.0])
def test_decision_probability_blend_identity(decision, p, fair, s):
    """Documenta la mezcla vigente (09 P1: INCUMPLE en la decision; 09 P2:
    PARCIAL, vigencia pendiente de MM, preregistro-el-modelo-manda). No la
    bendice: si el operador fija market_shrink=0 tras MM, este test queda como
    caso degenerado y manda
    test_decision_probability_is_pure_calibrated_without_fair_or_shrink.
    Identidad p_decision = (1-s)*cal + s*fair y p_used = (1-s)*p + s*fair sobre
    filas sinteticas. La parte «muestra del stream» de P2(a) se omite a
    proposito porque exigiria data/."""
    p_used, p_dec = decision(p, fair, s)
    assert p_dec == pytest.approx((1 - s) * _cal(p, "", "", "") + s * fair, abs=1e-12)
    assert p_used == pytest.approx((1 - s) * p + s * fair, abs=1e-12)


def test_pure_part_does_not_depend_on_fair(decision):
    """P2 (09 P2, «model_probability independiente de fair»): al cambiar fair,
    la parte pura (p_decision - s*fair)/(1-s) no se mueve."""
    p, s = 0.63, 0.5
    pures = set()
    for fair in (0.05, 0.3, 0.5, 0.8, 0.99):
        _, p_dec = decision(p, fair, s)
        pures.add(round((p_dec - s * fair) / (1 - s), 12))
    assert len(pures) == 1


# --------------------------------------------------------------------------
# P9: calibracion contra resultados, nunca contra el mercado
# --------------------------------------------------------------------------
def test_decision_calibrates_pre_blend_probability_not_the_blend(decision):
    """P9 (09 P9 «Candado propuesto» b): el calibrador recibe la probabilidad
    PRE-BLEND (p_model) y nunca la mezcla; el resultado difiere de cal(mezcla)."""
    p, fair, s = 0.4, 0.8, 0.5
    decision.seen.clear()
    _, p_dec = decision(p, fair, s)
    assert decision.seen == [p]                      # solo se calibro p_model
    blend = (1 - s) * p + s * fair
    assert blend not in decision.seen
    assert p_dec != pytest.approx(_cal(blend, "", "", ""), abs=1e-6)


def _synthetic_served(seed: int = 7, n_events: int = 240) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_events):
        p = float(rng.uniform(0.2, 0.8))
        won = rng.uniform() < p ** 1.4
        rows.append({
            "league": "mlb", "market": "h2h", "event_id": f"E{i:04d}",
            "selection": "home", "line": np.nan,
            "game_date": f"2026-{1 + i // 28:02d}-{i % 28 + 1:02d}",
            "generated_at": f"2026-{1 + i // 28:02d}-{i % 28 + 1:02d}T12:00:00+00:00",
            "model_probability": p, "adjusted_probability": p,
            "implied_probability_novig": float(rng.uniform(0.2, 0.8)),
            "result": "win" if won else "loss"})
    return pd.DataFrame(rows)


def _train_isolated(frame: pd.DataFrame, models_dir: Path):
    """Entrena con las funciones reales del proyecto en un MODELS_DIR aislado."""
    import joblib

    from sqp.calibration import calibrator as cal
    from sqp.calibration.data import TRAINING_COLS, _project_training
    hist = _project_training(frame)
    assert list(hist.columns) == TRAINING_COLS
    old = cal.MODELS_DIR
    cal.MODELS_DIR = models_dir
    cal._load_calibrator.cache_clear()
    try:
        summary = cal.train_market_calibrators(hist, min_n=40, staging=True,
                                               prob_col="adjusted_probability")
        grid = np.linspace(0.05, 0.95, 37)
        preds = {}
        for name in ("iso", "beta"):  # joblib.load: ficheros propios, recien escritos en tmp_path
            path = cal._model_path("mlb_h2h", name, staging=True)
            if path.exists():
                preds[name] = np.asarray(joblib.load(path).predict(grid), dtype=float)
    finally:
        cal.MODELS_DIR = old
        cal._load_calibrator.cache_clear()
    return summary, preds


def test_calibrator_ignores_market_column(tmp_path):
    """P9 (09 P9 «Candado propuesto» a): un calibrador entrenado con
    implied_probability_novig perturbada es identico al entrenado con la
    columna original (la columna de mercado no entra al ajuste)."""
    base = _synthetic_served()
    perturbed = base.copy()
    perturbed["implied_probability_novig"] = (
        1.0 - perturbed["implied_probability_novig"].to_numpy()[::-1])
    s1, p1 = _train_isolated(base, tmp_path / "a")
    s2, p2 = _train_isolated(perturbed, tmp_path / "b")
    assert s1 and s1[0]["trained"] is True
    assert p1, "no se persistio ningun calibrador: el test seria vacuo"
    assert s1 == s2
    assert p1.keys() == p2.keys()
    for k in p1:
        np.testing.assert_array_equal(p1[k], p2[k])


def test_calibrator_does_depend_on_outcomes_sensitivity(tmp_path):
    """P9 (control de sensibilidad del test anterior): si se perturba el
    OBJETIVO (adjusted_probability), el resumen de entrenamiento cambia; asi
    se demuestra que la comparacion anterior puede detectar diferencias."""
    base = _synthetic_served()
    shifted = base.copy()
    shifted["adjusted_probability"] = (shifted["adjusted_probability"] * 0.5 + 0.25)
    s1, _ = _train_isolated(base, tmp_path / "a")
    s2, _ = _train_isolated(shifted, tmp_path / "b")
    assert s1 != s2


# --------------------------------------------------------------------------
# P8: tuning sin ROI
# --------------------------------------------------------------------------
def test_tuning_modules_do_not_import_roi_engine():
    """P8a (09 P8 «Candado propuesto» a): sqp.backtesting.tuning y
    scripts/tune_ratings.py no importan sqp.backtesting.roi_engine (solo
    importaciones; no se comprueba que no lean data/odds)."""
    assert (SRC / "sqp" / "backtesting" / "roi_engine.py").exists()
    for path in (SRC / "sqp" / "backtesting" / "tuning.py", ROOT / "scripts" / "tune_ratings.py"):
        assert path.exists(), path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                mods.add(base)
                mods.update(f"{base}.{a.name}" for a in node.names)
        assert not [m for m in mods if m.startswith("sqp.backtesting.roi_engine")], path


# Parametros cuya justificacion por ROI es HEREDADA (09 P8; 05-informe-de-riesgos
# R2): heredados de junio de 2026, pendientes de revalidacion por log loss
# (docs/prompts-audit/05-informe-de-riesgos.md R2).
LEGACY_ROI_JUSTIFIED = {
    "configs/leagues/ratings.yaml": {"park_bound"},
    "configs/default.yaml": {"max_plausible_edge", "uncertainty_penalty"},
}
# Menciones de ROI en bloques de politica operativa (interruptores de pausa /
# monitor de degradacion): describen CUANDO se suspende un mercado, no eligen
# un parametro del modelo ni de la decision. Se listan para que cualquier
# bloque nuevo tenga que declararse explicitamente (2026-11-10). Ver 09 P8:66
# y P14.
OPERATIONAL_ROI_MENTIONS = {
    "configs/default.yaml": {"paused_markets", "degradation_monitor"},
}
_ROI = re.compile(r"\bROI\b", re.IGNORECASE)
_KEY = re.compile(r"^\s*([A-Za-z_][\w]*)\s*:")


unattributed: list[str] = []   # bloques con ROI sin clave reconocida


def _roi_justified_keys(text: str) -> set[str]:
    """Criterio: un bloque de comentarios contiguos (`#` al inicio de linea,
    interrumpido por una linea en blanco) que menciona ROI se atribuye a la
    PRIMERA clave YAML que le sigue; un comentario `#` en la misma linea que
    una clave se le atribuye a esa clave. Solo se miran comentarios: claves
    como ``roi_pause`` no cuentan. Devuelve las claves (nombre hoja)."""
    keys: set[str] = set()
    unattributed.clear()
    pending = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            if pending:
                unattributed.append("bloque con ROI seguido de linea en blanco")
            pending = False
            continue
        if stripped.startswith("#"):
            if _ROI.search(stripped):
                pending = True
            continue
        m = _KEY.match(raw)
        if m:
            inline = raw.partition(" #")[2]
            if pending or _ROI.search(inline):
                keys.add(m.group(1))
        elif pending:
            unattributed.append(stripped[:60])
        pending = False
    if pending:
        unattributed.append("bloque con ROI al final del fichero")
    return keys


def test_roi_justified_values_are_only_the_declared_legacy_ones():
    """P8b (09 P8 «Candado propuesto» b; 05-informe-de-riesgos R2): los
    comentarios de ratings.yaml y default.yaml que justifican un valor por ROI
    estan en la lista LEGACY_ROI_JUSTIFIED (park_bound, max_plausible_edge,
    uncertainty_penalty: heredados de junio de 2026, pendientes de
    revalidacion por log loss). Una justificacion nueva por ROI falla; una
    entrada obsoleta de la lista tambien."""
    for rel in ("configs/leagues/ratings.yaml", "configs/default.yaml"):
        found = _roi_justified_keys((ROOT / rel).read_text(encoding="utf-8"))
        assert not unattributed, f"{rel}: bloques con ROI sin clave: {unattributed}"
        allowed = LEGACY_ROI_JUSTIFIED.get(rel, set()) | OPERATIONAL_ROI_MENTIONS.get(rel, set())
        assert not (found - allowed), (
            f"{rel}: justificacion nueva por ROI en {sorted(found - allowed)}; "
            "P8 prohibe elegir parametros por ROI (usar log loss/Brier/ECE)")
        assert not (allowed - found), f"{rel}: entradas obsoletas {sorted(allowed - found)}"


def test_roi_scanner_detects_new_justification():
    """P8b: el detector funciona (positivo y negativo) sobre YAML sintetico."""
    text = ("a:\n  # tuned by ROI +2%\n  new_param: 1\n\n"
            "  # chosen by log loss\n  ok_param: 2\n  inline: 3  # best ROI\n"
            "  roi_pause: -0.1\n")
    assert _roi_justified_keys(text) == {"new_param", "inline"}
