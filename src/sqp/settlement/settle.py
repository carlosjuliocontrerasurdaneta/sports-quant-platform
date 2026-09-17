"""Settlement: grade bet candidates against final scores, compute realized ROI.

Sources: The Odds API /scores for leagues with has_scores=True. Tennis has no
scores in this API -> requires a secondary results provider (explicit gap).
Audit trail: settled rows are appended, never overwritten.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone
import pandas as pd

from sqp.markets.settlement_math import is_quarter_line, split_asian_line
from sqp.sports.team_names import normalize_key

# Un partido cancelado/pospuesto nunca entrega score: sin expiracion, su pick
# quedaria abierto para siempre y (post-shadow, stake > 0) la regla de
# "picks comenzados sin liquidar" excluiria su liga del run diario
# INDEFINIDAMENTE (auditoria 2026-07-12). Pasados estos dias desde el
# comienzo sin resultado, el pick se liquida como void (pnl 0, flag).
STALE_VOID_DAYS = 3


def _grade(row: pd.Series, hs: int, as_: int, home: str,
           three_way: bool = False) -> str:
    m, sel, line = row["market"], row["selection"], row["line"]
    margin, total = hs - as_, hs + as_
    # Compare side identity (selection vs home) by normalized key, not raw string:
    # the winner match upstream already normalizes, so a selection spelled
    # differently than `home` (accents, casing) must not silently misgrade a
    # home-side bet (2026-06-28 WTA Wimbledon review).
    sel_is_home = normalize_key(sel) == normalize_key(home)
    # Si la seleccion no casa con NINGUNO de los dos equipos, `sel_is_home` es
    # False y el grading seguia como si fuera el visitante: una apuesta al local
    # escrita de otra forma salia "loss" con el local GANANDO (reproducido en la
    # auditoria del 2026-08-28, AUD-LOW-001). Un resultado fabricado es peor que
    # una fila sin graduar: entra en el ROI realizado y en las etiquetas de
    # calibracion como evidencia valida.
    #
    # Hoy no es alcanzable -- cuotas y marcadores vienen del MISMO proveedor y
    # las 783 filas liquidadas casan --, pero el modulo ya anticipa un proveedor
    # secundario de resultados para tenis, que es justo cuando los nombres
    # divergen. Solo aplica a los mercados que dependen del lado; en `totals` la
    # seleccion es Over/Under y en 1X2 el empate no es ningun equipo.
    if m in ("h2h", "spreads") and not sel_is_home and not (three_way and sel == "Draw"):
        away = row.get("away")
        if away is not None and str(away) != "" and normalize_key(sel) != normalize_key(away):
            return "void"
    if m == "h2h":
        if margin == 0:
            if sel == "Draw": return "win"
            # 2-way (el empate no se cotiza): los books gradan PUSH y devuelven
            # el stake; gradarlo "loss" sesgaba las etiquetas de calibracion y
            # el ROI realizado (auditoria 2026-07-24, M-9). En 1X2 (three_way)
            # el empate solo lo gana la seleccion Draw.
            return "loss" if three_way else "push"
        return "win" if sel_is_home == (margin > 0) and sel != "Draw" else "loss"
    if m in ("spreads", "totals"):
        # Una linea no finita (NaN/inf) volvia FALSAS todas las comparaciones de
        # abajo, asi que el resultado se FABRICABA sin mirar el marcador:
        # totals/Under ganaba SIEMPRE, totals/Over y spreads perdian SIEMPRE
        # (auditoria 2026-08-05, F-03, reproducido). Un "win" fabricado es peor
        # que una fila perdida: entra en el ROI realizado y en las etiquetas de
        # calibracion como evidencia valida.
        # "void" y no "push": push afirma que la apuesta existio y se devolvio
        # el stake; void afirma que no se pudo graduar, que es lo cierto.
        try:
            line = float(line)
        except (TypeError, ValueError):
            return "void"
        if not math.isfinite(line):
            return "void"
        # LINEA ASIATICA DE CUARTO (+-0.25 / +-0.75, o totales 2.25 / 2.75):
        # el stake se reparte a medias entre las dos lineas de medio punto
        # adyacentes. Graduarla como una linea entera FABRICABA un resultado:
        # `-0.75` con margen +1 salia "win" completo siendo medio-gana, y
        # `-0.25` con empate salia "loss" completo siendo medio-pierde.
        # Reproducido sobre el ledger el 2026-09-13 (chile, Universidad de
        # Chile -0.75, margen +1, graduado `win`); 536 filas del stream
        # graduado llevan linea de cuarto, 212 dentro de la ventana del gate
        # (auditoria integral 2026-09-13, AUD-MED-002). La descomposicion es
        # la de `markets.settlement_math.split_asian_line`, que ya existia
        # como API de investigacion sin llegar al ledger.
        if is_quarter_line(line):
            lo, hi = split_asian_line(line)
            return _combinar_medias(_grade_linea(m, sel, sel_is_home, margin, total, lo),
                                    _grade_linea(m, sel, sel_is_home, margin, total, hi))
        return _grade_linea(m, sel, sel_is_home, margin, total, line)
    return "void"


def _grade_linea(m: str, sel: str, sel_is_home: bool, margin: int, total: int,
                 line: float) -> str:
    """Resultado de una linea de medio punto o entera (win/push/loss)."""
    if m == "spreads":
        adj = margin + line if sel_is_home else -margin + line
        return "win" if adj > 0 else ("push" if adj == 0 else "loss")
    if total == line: return "push"
    return "win" if (total > line) == (sel == "Over") else "loss"


# Resultados de una linea de cuarto: mitad del stake en cada linea adyacente.
# `half_win`: una mitad gana y la otra se devuelve; `half_loss`: una mitad
# pierde y la otra se devuelve. Todo consumidor que filtre `isin(["win",
# "loss"])` los EXCLUYE, como a un push: es la direccion conservadora para el
# gate, la calibracion y el monitor de degradacion. El ledger de banca los
# incluye por su `pnl`, que es lo que define el saldo.
HALF_RESULTS = frozenset({"half_win", "half_loss"})
_COMBINACION_MEDIAS = {
    ("win", "win"): "win", ("loss", "loss"): "loss",
    ("win", "push"): "half_win", ("push", "win"): "half_win",
    ("loss", "push"): "half_loss", ("push", "loss"): "half_loss",
}


# Resultados que ARRIESGAN stake y por tanto entran en el ROI realizado: las
# victorias/derrotas enteras y las medias. Push y void devuelven el stake.
#
# DEFINICION CANONICA DEL ROI REALIZADO (auditoria integral 2026-09-17,
# AUD-002): numerador y denominador sobre el MISMO conjunto de filas, este.
# Tras AUD-MED-002 coexistian tres definiciones: `runner.realized_roi` (medias
# en ambos lados), `roi_engine._summarize` y el dashboard (pnl de TODAS las
# filas sobre el stake de win/loss: una `half_win` sola daba ROI 0,0 y mezclada
# con una `win` lo DUPLICABA, 1,50 frente a 0,75) y `audit/report.py` (medias
# fuera de ambos). Todos los consumidores pasan por `realized_roi_parts`.
STAKED_RESULTS = frozenset({"win", "loss"}) | HALF_RESULTS


def staked_mask(result: pd.Series) -> pd.Series:
    """Filas cuyo stake se arriesgo (win/loss/medias); push y void quedan fuera."""
    return result.isin(STAKED_RESULTS)


def realized_roi_parts(settled: pd.DataFrame) -> tuple[float, float]:
    """(pnl, stake) sobre las filas con stake arriesgado. ROI = pnl / stake."""
    if settled.empty or "result" not in settled.columns:
        return 0.0, 0.0
    graded = settled[staked_mask(settled["result"])]
    stake = float(pd.to_numeric(graded["stake"], errors="coerce").fillna(0.0).sum())
    pnl = float(pd.to_numeric(graded["pnl"], errors="coerce").fillna(0.0).sum())
    return pnl, stake


def _combinar_medias(r_lo: str, r_hi: str) -> str:
    # Dos lineas adyacentes de medio punto no pueden dar (win, loss) ni
    # (push, push) sobre el mismo marcador; si ocurriera, mejor no graduar.
    return _COMBINACION_MEDIAS.get((r_lo, r_hi), "void")


def settle_candidates(candidates: pd.DataFrame, scores: dict[str, tuple[int, int, str]],
                      three_way: bool = False) -> pd.DataFrame:
    """scores: event_id -> (home_score, away_score, home_team_name).
    ``three_way``: liga con mercado 1X2 (empate cotizado); gobierna el grading
    de empates en h2h (push en 2-way, loss para equipos en 1X2)."""
    rows = []
    for _, row in candidates.iterrows():
        sc = scores.get(row["event_id"])
        if sc is None:
            continue
        hs, as_, home = sc
        result = _grade(row, hs, as_, home, three_way)
        pnl = {"win": row["stake"] * (row["price_decimal"] - 1),
               "loss": -row["stake"], "push": 0.0, "void": 0.0,
               "half_win": 0.5 * row["stake"] * (row["price_decimal"] - 1),
               "half_loss": -0.5 * row["stake"]}[result]
        rows.append({**row.to_dict(), "result": result, "pnl": round(pnl, 2),
                     "settled_at": datetime.now(timezone.utc).isoformat()})
    out = pd.DataFrame(rows)
    return out


def _parse_start(s: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def void_stale_candidates(candidates: pd.DataFrame,
                          scores: dict[str, tuple[int, int, str]],
                          start_times: dict[str, str], *,
                          now: datetime | None = None,
                          stale_days: int = STALE_VOID_DAYS) -> pd.DataFrame:
    """Void por expiracion: candidatos comenzados hace mas de ``stale_days``
    dias que siguen sin score (partido cancelado/pospuesto sin reprogramar).

    Devuelve filas con result='void', pnl 0.0 y flag ``stale_void`` (mismo
    formato que ``settle_candidates``, listas para ``_persist_settled``). Sin
    ``start_time`` conocido el candidato se deja abierto (nunca adivinar)."""
    if candidates.empty:
        return pd.DataFrame()
    now = now or datetime.now(timezone.utc)
    scored = {str(k) for k in scores}
    rows = []
    for _, row in candidates.iterrows():
        eid = str(row["event_id"])
        if eid in scored:
            continue
        start = _parse_start(start_times.get(eid))
        if start is None or (now - start).total_seconds() < stale_days * 86400:
            continue
        raw_flags = row.get("flags", "")
        flags = "" if pd.isna(raw_flags) else str(raw_flags)
        rows.append({**row.to_dict(),
                     "flags": f"{flags};stale_void" if flags else "stale_void",
                     "result": "void", "pnl": 0.0,
                     "settled_at": now.isoformat()})
    return pd.DataFrame(rows)
