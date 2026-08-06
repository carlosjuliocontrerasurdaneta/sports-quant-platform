"""Gate de CLV por (liga, mercado): allow-list para stake real.

Un (liga, mercado) solo puede llevar stake real si su CLV mediano sobre la
muestra liquidada emparejada a cierre es positivo con n suficiente. Politica
default-deny: sin registro, sin entrada o con evidencia insuficiente, el
mercado queda en stake 0 (flag "clv_gate") mientras la evidencia (settlement,
CLV, calibracion) sigue acumulando a costo cero. El registro lo escribe la
auditoria CLV diaria (sqp.audit.clv.daily_clv); este modulo solo define el
formato y el acceso, sin imports del pipeline (evita el ciclo daily -> clv ->
roi_engine -> daily).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CLV_GATE_FILENAME = "clv_gate.json"
# Minimo de apuestas liquidadas emparejadas a un cierre capturado por (liga,
# mercado). Con menos muestra, el signo de la mediana es ruido: deny.
CLV_GATE_MIN_N = 30


def gate_decisions(segments: pd.DataFrame,
                   min_n: int = CLV_GATE_MIN_N) -> pd.DataFrame:
    """Anota la tabla de segmentos por (league, market) — columnas n y
    median_clv_pct, como la produce sqp.audit.clv.clv_segments — con la
    columna `allowed`: n >= min_n y CLV mediano estrictamente positivo."""
    if segments.empty:
        return segments.copy()
    out = segments.copy()
    med = pd.to_numeric(out["median_clv_pct"], errors="coerce")
    # La mediana debe ser FINITA ademas de positiva: pandas no ignora inf en
    # median (a diferencia de NaN), asi que una sola fila corrupta la llevaba a
    # inf, e inf > 0 es True -- un precio malo podia APROBAR un mercado para
    # stake real (auditoria 2026-08-05, F-02). Doble guard con clv_segments: si
    # una de las dos capas se relaja, la otra sigue negando.
    finite = med.notna() & (med != math.inf) & (med != -math.inf)
    out["allowed"] = (out["n"] >= min_n) & finite & (med > 0)
    return out


def write_clv_gate(segments: pd.DataFrame, bets_dir: Path,
                   min_n: int = CLV_GATE_MIN_N) -> Path:
    """Persiste el registro del gate en bets_dir/clv_gate.json (reemplazo
    atomico via archivo temporal). Escribe SIEMPRE, incluso sin segmentos: un
    registro con markets vacio hace explicito el default-deny."""
    decided = gate_decisions(segments, min_n)
    markets: dict[str, dict] = {}
    if not decided.empty:
        for r in decided.itertuples():
            markets[f"{r.league}|{r.market}"] = {
                "n": int(r.n),
                "median_clv_pct": float(r.median_clv_pct),
                "allowed": bool(r.allowed),
            }
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "min_n": int(min_n), "markets": markets}
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / CLV_GATE_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def load_clv_gate(bets_dir: Path) -> dict[str, dict]:
    """Mapa "liga|mercado" -> {n, median_clv_pct, allowed}. Devuelve {} si el
    registro no existe o es ilegible; el consumidor debe tratar {} como
    default-deny, nunca como "todo permitido"."""
    path = Path(bets_dir) / CLV_GATE_FILENAME
    if not path.exists():
        return {}
    try:
        markets = json.loads(path.read_text(encoding="utf-8")).get("markets")
    except (OSError, json.JSONDecodeError):
        return {}
    return markets if isinstance(markets, dict) else {}


def market_allowed(gate: dict[str, dict], league: str, market: str) -> bool:
    """True solo si el registro tiene la entrada y esta aprobada (default-deny)."""
    entry = gate.get(f"{league}|{market}")
    return bool(entry and entry.get("allowed"))
