"""Experimento de timing: ¿captura el sistema abridores MLB antes de que el
mercado mueva la línea de moneyline?

Pre-registro: docs/research/2026-08-22-preregistro-timing-starters.md

Uso:
    python scripts/timing_experiment.py [--threshold 0.03] [--min-n 30]
                                        [--bookmaker pinnacle] [--out PATH]

Salida: tabla de resultados por consola + CSV opcional.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Parsing de timestamps
# ---------------------------------------------------------------------------

def _utc(s: object) -> datetime | None:
    if not s or pd.isna(s):
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Carga de starters
# ---------------------------------------------------------------------------

def load_starters(root: Path) -> pd.DataFrame:
    p = root / "data" / "historical" / "starters_mlb.csv"
    if not p.exists():
        raise FileNotFoundError(f"starters_mlb.csv no encontrado en {p}")
    df = pd.read_csv(p, dtype={"game_id": str})
    df["ingested_at_dt"] = df["ingested_at"].apply(_utc)
    # Solo filas con ambos abridores confirmados
    mask = (
        df["home_starter"].notna() & (df["home_starter"].astype(str) != "") &
        df["away_starter"].notna() & (df["away_starter"].astype(str) != "")
    )
    return df[mask].copy()


# ---------------------------------------------------------------------------
# Carga de odds MLB (todas las snapshots)
# ---------------------------------------------------------------------------

def load_odds_mlb(root: Path) -> pd.DataFrame:
    odds_dir = root / "data" / "odds"
    files = sorted(odds_dir.glob("odds_mlb_*.csv"))
    if not files:
        raise FileNotFoundError(f"No hay archivos odds_mlb_*.csv en {odds_dir}")
    parts = []
    for f in files:
        try:
            chunk = pd.read_csv(f, dtype={"event_id": str, "bookmaker": str})
            parts.append(chunk)
        except Exception as exc:
            print(f"[WARN] No se pudo leer {f.name}: {exc}", file=sys.stderr)
    if not parts:
        raise ValueError("No se pudieron leer snapshots de odds MLB.")
    df = pd.concat(parts, ignore_index=True)
    df["captured_at_dt"] = df["captured_at"].apply(_utc)
    df["commence_dt"] = df["commence_time"].apply(_utc)
    return df


# ---------------------------------------------------------------------------
# Construcción de serie de precios sin vig por evento × snapshot
# ---------------------------------------------------------------------------

def build_novig_series(
    odds_df: pd.DataFrame,
    bookmaker: str | None,
) -> pd.DataFrame:
    """Devuelve un DataFrame con columnas:
       event_id, home, away, commence_dt, captured_at_dt, p_home_novig
    """
    h2h = odds_df[odds_df["market"] == "h2h"].copy()
    if bookmaker:
        bk = h2h[h2h["bookmaker"].str.lower() == bookmaker.lower()]
        if not bk.empty:
            h2h = bk

    # Necesitamos ambos lados por snapshot
    h2h = h2h[h2h["price_decimal"] > 1.0]
    home_side = h2h[
        h2h.apply(lambda r: r["outcome"] == r["home"], axis=1)
    ][["event_id", "home", "away", "commence_dt", "captured_at_dt", "price_decimal"]].rename(
        columns={"price_decimal": "p_home_raw"}
    )
    away_side = h2h[
        h2h.apply(lambda r: r["outcome"] == r["away"], axis=1)
    ][["event_id", "captured_at_dt", "price_decimal"]].rename(
        columns={"price_decimal": "p_away_raw"}
    )
    merged = home_side.merge(away_side, on=["event_id", "captured_at_dt"], how="inner")
    # Eliminar vig: suma inversa
    merged["inv_sum"] = 1.0 / merged["p_home_raw"] + 1.0 / merged["p_away_raw"]
    merged["p_home_novig"] = (1.0 / merged["p_home_raw"]) / merged["inv_sum"]
    return merged.sort_values(["event_id", "captured_at_dt"])


# ---------------------------------------------------------------------------
# Detectar primera movida significativa por evento
# ---------------------------------------------------------------------------

def first_significant_move(series: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Para cada event_id devuelve el timestamp de la primera movida >= threshold.

    Una movida es 'significativa' cuando |p_t - p_open| >= threshold en dos
    snapshots consecutivas (la primera de las dos se registra).
    """
    rows = []
    for event_id, grp in series.groupby("event_id"):
        grp = grp.sort_values("captured_at_dt").reset_index(drop=True)
        if len(grp) < 3:
            continue
        p_open = grp.loc[0, "p_home_novig"]
        commence_dt = grp.loc[0, "commence_dt"]
        move_ts = None
        for i in range(1, len(grp) - 1):
            delta = abs(grp.loc[i, "p_home_novig"] - p_open)
            delta_next = abs(grp.loc[i + 1, "p_home_novig"] - p_open)
            if delta >= threshold and delta_next >= threshold:
                move_ts = grp.loc[i, "captured_at_dt"]
                break
        rows.append({
            "event_id": event_id,
            "home": grp.loc[0, "home"],
            "away": grp.loc[0, "away"],
            "commence_dt": commence_dt,
            "p_open": p_open,
            "move_ts": move_ts,
            "n_snapshots": len(grp),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Join con starters por (home, away, date)
# ---------------------------------------------------------------------------

def join_starters(events_df: pd.DataFrame, starters_df: pd.DataFrame) -> pd.DataFrame:
    """Une por fecha del partido + nombres de equipos (normalización parcial)."""
    events_df = events_df.copy()
    events_df["game_date"] = events_df["commence_dt"].apply(
        lambda dt: dt.date().isoformat() if dt else None
    )

    def norm(s: str) -> str:
        return s.strip().lower()

    starters_df = starters_df.copy()
    starters_df["date_str"] = starters_df["date"].astype(str)

    # Índice por (date, home_norm)
    starters_df["home_norm"] = starters_df["home_starter"].apply(
        lambda s: norm(str(s)) if pd.notna(s) else ""
    )

    results = []
    for _, ev_row in events_df.iterrows():
        gdate = ev_row.get("game_date")

        # Buscar en starters por date + equipos que contengan substring del home/away
        cands = starters_df[starters_df["date_str"] == gdate] if gdate else pd.DataFrame()
        if cands.empty:
            continue
        # Matching: el nombre del equipo en odds a veces es ciudad + apodo
        # Gap: starters no tienen campo de equipo; se necesita tabla gamePk -> event_id
        for _, st_row in cands.iterrows():
            # los starters no tienen equipo, solo starter name + date
            # usamos game_id como clave — no podemos hacer match exacto aquí
            # necesitamos un campo de equipo en starters
            pass

        # Alternativa: unir por event_id si existe en starters (no existe)
        # El join real requiere un archivo de mapeo gamePk → (home, away)
        # que no existe actualmente. Reportar este gap.
        results.append({
            **ev_row.to_dict(),
            "home_starter": None,
            "away_starter": None,
            "ingested_at_dt": None,
            "join_status": "NO_TEAM_KEY",
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Join alternativo: vía odds_mlb que tiene home/away + event_id,
# y starters que tiene game_id pero no event_id
# El gap: no hay tabla de mapeo game_id (MLB gamePk) → event_id (Odds API)
# ---------------------------------------------------------------------------

def detect_join_gap(root: Path) -> dict:
    """Verifica si existe un mapeo gamePk → event_id."""
    candidates = [
        root / "data" / "historical" / "event_map_mlb.csv",
        root / "data" / "historical" / "game_event_map.csv",
        root / "data" / "predictions" / "predictions_mlb.csv",
    ]
    found = {}
    for p in candidates:
        if p.exists():
            try:
                df = pd.read_csv(p, nrows=2)
                cols = df.columns.tolist()
                has_game_id = any("game_id" in c.lower() for c in cols)
                has_event_id = any("event_id" in c.lower() for c in cols)
                found[str(p.name)] = {
                    "cols": cols,
                    "has_game_id": has_game_id,
                    "has_event_id": has_event_id,
                }
            except Exception as exc:
                found[str(p.name)] = {"error": str(exc)}
    return found


# ---------------------------------------------------------------------------
# Análisis de timing sobre datos disponibles (sin join de starters)
# ---------------------------------------------------------------------------

def analyze_line_movement_patterns(series: pd.DataFrame, threshold: float) -> dict:
    """Análisis exploratorio de cuándo se producen movidas en MLB.

    Sin el join de starters, analiza la distribución de movidas en el tiempo
    relativo al `commence_time` para entender la estructura del mercado MLB.
    """
    events = first_significant_move(series, threshold)
    events = events[events["move_ts"].notna() & events["commence_dt"].notna()].copy()
    if events.empty:
        return {"n_con_movida": 0}
    events["mins_before_commence"] = events.apply(
        lambda r: (r["commence_dt"] - r["move_ts"]).total_seconds() / 60, axis=1
    )
    m = events["mins_before_commence"]
    return {
        "n_eventos_total": len(events) + (len(series["event_id"].unique()) - len(events)),
        "n_con_movida": len(events),
        "fraccion_con_movida": round(len(events) / max(series["event_id"].nunique(), 1), 3),
        "mediana_mins_antes_commence": round(float(m.median()), 1),
        "p25_mins": round(float(m.quantile(0.25)), 1),
        "p75_mins": round(float(m.quantile(0.75)), 1),
        "p10_mins": round(float(m.quantile(0.10)), 1),
        "p90_mins": round(float(m.quantile(0.90)), 1),
    }


# ---------------------------------------------------------------------------
# CLI principal
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Experimento de timing starters MLB")
    parser.add_argument("--threshold", type=float, default=0.03,
                        help="Movida mínima vig-free para considerarse significativa (default: 0.03)")
    parser.add_argument("--bookmaker", default="pinnacle",
                        help="Bookmaker para la serie de precios (default: pinnacle)")
    parser.add_argument("--min-n", type=int, default=30,
                        help="Mínimo de partidos para emitir veredicto (default: 30)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Ruta CSV para guardar resultados por evento")
    args = parser.parse_args()

    print("=" * 60)
    print("EXPERIMENTO DE TIMING: STARTERS MLB vs MOVIMIENTO DE LÍNEA")
    print("Pre-registro: docs/research/2026-08-22-preregistro-timing-starters.md")
    print("=" * 60)

    # 1. Verificar gap de join
    print("\n[1/4] Verificando infraestructura de join...")
    gap_info = detect_join_gap(ROOT)
    join_possible = False
    for fname, info in gap_info.items():
        cols = info.get("cols", [])
        if info.get("has_game_id") and info.get("has_event_id"):
            print(f"  ✓ {fname}: tiene game_id Y event_id → join posible")
            join_possible = True
        else:
            print(f"  - {fname}: cols={cols[:6]}...")

    if not join_possible:
        print("\n  GAP DETECTADO: No existe tabla de mapeo gamePk (MLB) → event_id (Odds API).")
        print("  Sin este mapeo no es posible comparar ingested_at (starters)")
        print("  con captured_at (odds) a nivel de partido.")
        print("\n  → El experimento puede ejecutarse PARCIALMENTE:")
        print("    Fase A (disponible): medir CUÁNDO el mercado mueve líneas MLB")
        print("    Fase B (requiere mapeo): comparar con ingested_at de starters")

    # 2. Cargar starters
    print("\n[2/4] Cargando starters MLB...")
    try:
        starters = load_starters(ROOT)
        print(f"  Starters totales con ambos nombres: {len(starters)}")
        # Filtrar solo captura en tiempo real (no backfill masivo)
        real_time = starters[starters["ingested_at_dt"].notna()].copy()
        # Comparar fecha de ingesta con fecha del partido
        real_time["game_date_dt"] = pd.to_datetime(real_time["date"], utc=True, errors="coerce")
        real_time["hours_before"] = (
            real_time["game_date_dt"] - real_time["ingested_at_dt"]
        ).dt.total_seconds() / 3600
        valid = real_time[
            (real_time["hours_before"] > 0) &
            (real_time["hours_before"] <= 120)
        ]
        print(f"  Starters en tiempo real (0-120h antes): {len(valid)}")
        if len(valid) < args.min_n:
            print(f"  ADVERTENCIA: muestra de tiempo real ({len(valid)}) < min_n ({args.min_n})")
            print("  La mayoría de los starters fueron ingresados via backfill histórico.")
            print("  Interpretación: el sistema NO capturaba starters en tiempo real hasta ahora.")
        else:
            dist = valid["hours_before"].describe()
            print(f"  Horas antes del partido — mediana: {dist['50%']:.1f}h, "
                  f"p25: {dist['25%']:.1f}h, p75: {dist['75%']:.1f}h")
    except FileNotFoundError as exc:
        print(f"  ERROR: {exc}")
        starters = pd.DataFrame()
        valid = pd.DataFrame()

    # 3. Analizar movidas de línea
    print("\n[3/4] Analizando movidas de línea MLB...")
    try:
        odds = load_odds_mlb(ROOT)
        print(f"  Snapshots totales: {len(odds)}")
        print(f"  Eventos únicos: {odds['event_id'].nunique()}")
        print(f"  Rango: {odds['captured_at'].min()[:10]} → {odds['captured_at'].max()[:10]}")

        series = build_novig_series(odds, args.bookmaker)
        if series.empty:
            print(f"  ADVERTENCIA: sin datos de {args.bookmaker}; usando todos los bookmakers")
            series = build_novig_series(odds, None)

        print(f"  Pares home/away con serie de precios: {series['event_id'].nunique()}")
        patterns = analyze_line_movement_patterns(series, args.threshold)

        print(f"\n  Threshold de movida: {args.threshold:.0%} vig-free")
        print(f"  Eventos con movida significativa: {patterns.get('n_con_movida', 0)}")
        print(f"  Fracción con movida: {patterns.get('fraccion_con_movida', 0):.1%}")
        print("  Cuándo ocurre la movida (minutos antes del partido):")
        print(f"    p10={patterns.get('p10_mins', 'n/a')}  "
              f"p25={patterns.get('p25_mins', 'n/a')}  "
              f"mediana={patterns.get('mediana_mins_antes_commence', 'n/a')}  "
              f"p75={patterns.get('p75_mins', 'n/a')}  "
              f"p90={patterns.get('p90_mins', 'n/a')}")

    except (FileNotFoundError, ValueError) as exc:
        print(f"  ERROR: {exc}")
        patterns = {}

    # 4. Veredicto
    print("\n[4/4] Veredicto del experimento")
    print("-" * 60)
    n_real = len(valid) if not valid.empty else 0

    if not join_possible:
        verdict = "BLOQUEADO"
        reason = (
            "No existe el mapeo gamePk → event_id necesario para comparar\n"
            "  ingested_at (starters) con captured_at (odds) a nivel de partido.\n"
            "  La Fase A (estructura del mercado) sí ejecutó — ver resultados arriba.\n"
            "  Para la Fase B se necesita construir la tabla de mapeo."
        )
    elif n_real < args.min_n:
        verdict = "MUESTRA_INSUFICIENTE"
        reason = (
            f"Solo {n_real} starters en tiempo real (necesario >= {args.min_n}).\n"
            "  El sistema no capturaba starters de forma continua antes del experimento."
        )
    else:
        verdict = "EJECUTABLE_CON_JOIN"
        reason = "Muestra y datos disponibles. Ejecutar join cuando exista la tabla de mapeo."

    print(f"  VEREDICTO: {verdict}")
    print(f"  Razón: {reason}")
    print()

    # Siguiente acción
    print("SIGUIENTE ACCIÓN:")
    if verdict == "BLOQUEADO":
        print("  Construir la tabla de mapeo gamePk → event_id.")
        print("  Opciones:")
        print("  a) Enriquecer fetch_probable_pitchers() para guardar el event_id de Odds API")
        print("     junto al gamePk de MLB Stats API, emparejando por (home, away, date).")
        print("  b) Añadir un campo 'game_id' al odds snapshot en OddsStore.")
        print("  Costo: ~50 líneas de código + 1-2 semanas de acumulación de datos.")
    elif verdict == "MUESTRA_INSUFICIENTE":
        print("  Activar captura continua de starters con timestamp de tiempo real.")
        print("  El backfill histórico no sirve para este experimento.")
        print(f"  Acumular >= {args.min_n} partidos y re-ejecutar.")
    else:
        print("  Construir la tabla de mapeo y re-ejecutar la fase B.")


if __name__ == "__main__":
    main()
