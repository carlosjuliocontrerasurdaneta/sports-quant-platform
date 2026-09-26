"""Descarga los datos del pre-registro del clima MLB (2026-09-26).

Solo DATOS DE ENTRADA: calendario MLB (hora UTC, estadio, techo) y el pronostico
emitido 24 h antes (Open-Meteo Previous Runs API). No lee marcadores ni mide
nada; la medicion vive en `measure_weather_mlb.py`. Ver
`docs/research/2026-09-26-preregistro-clima-mlb.md`.

  python scripts/research/fetch_weather_mlb.py --out <dir>

Salida: `<dir>/games_weather_mlb.csv`, una fila por partido, con el instante de
la descarga en `fetched_at`.
"""
from __future__ import annotations

import argparse
import csv
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
VARS = ("wind_speed_10m_previous_day1", "precipitation_previous_day1")
TIMEOUT_S = 60
PAUSE_S = 1.0


def _get(url: str, params: dict) -> dict:
    for intento in range(4):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT_S)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if intento == 3:
                raise
            espera = 5.0 * (intento + 1)
            print(f"  reintento {intento + 1} en {espera:.0f}s: {exc}")
            time.sleep(espera)
    raise RuntimeError("inalcanzable")


def fetch_schedule(start: str, end: str) -> list[dict]:
    """Partidos FINALIZADOS entre start y end, mes a mes."""
    games: list[dict] = []
    y, m = int(start[:4]), int(start[5:7])
    while f"{y:04d}-{m:02d}" <= end[:7]:
        d0 = max(start, f"{y:04d}-{m:02d}-01")
        nm = date(y + (m == 12), m % 12 + 1, 1)
        d1 = min(end, (nm.fromordinal(nm.toordinal() - 1)).isoformat())
        data = _get(SCHEDULE_URL, {"sportId": 1, "startDate": d0, "endDate": d1,
                                   "hydrate": "venue(location,fieldInfo)"})
        for day in data.get("dates", []):
            for g in day.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                v = g.get("venue", {})
                coords = (v.get("location") or {}).get("defaultCoordinates") or {}
                games.append({
                    "game_id": str(g["gamePk"]),
                    "game_date_utc": g.get("gameDate", ""),
                    "official_date": g.get("officialDate", ""),
                    "venue_id": v.get("id"), "venue": v.get("name", ""),
                    "roof_type": (v.get("fieldInfo") or {}).get("roofType", ""),
                    "lat": coords.get("latitude"), "lon": coords.get("longitude")})
        print(f"calendario {y:04d}-{m:02d}: {len(games)} acumulados")
        time.sleep(PAUSE_S)
        y, m = y + (m == 12), m % 12 + 1
    return games


def attach_forecasts(games: list[dict]) -> None:
    """Pronostico a 24 h a la hora mas proxima al inicio, por estadio y temporada."""
    grupos: dict[tuple, list[dict]] = {}
    for g in games:
        if g["lat"] is None or not g["game_date_utc"]:
            continue
        clave = (round(float(g["lat"]), 4), round(float(g["lon"]), 4),
                 g["game_date_utc"][:4])
        grupos.setdefault(clave, []).append(g)
    for i, ((lat, lon, _), gs) in enumerate(sorted(grupos.items()), 1):
        fechas = sorted(g["game_date_utc"][:10] for g in gs)
        data = _get(PREVIOUS_RUNS_URL, {
            "latitude": lat, "longitude": lon, "hourly": ",".join(VARS),
            "start_date": fechas[0], "end_date": fechas[-1], "timezone": "UTC"})
        hourly = data.get("hourly") or {}
        idx = {t: k for k, t in enumerate(hourly.get("time", []))}
        for g in gs:
            t = datetime.fromisoformat(g["game_date_utc"].replace("Z", "+00:00"))
            # hora mas proxima al inicio (19:07 -> 19:00, 19:35 -> 20:00)
            h = (t + timedelta(minutes=30)).replace(minute=0, second=0)
            k = idx.get(h.strftime("%Y-%m-%dT%H:00"))
            for var, col in zip(VARS, ("wind_kmh", "precip_mm")):
                vals = hourly.get(var) or []
                g[col] = vals[k] if k is not None and k < len(vals) else None
        print(f"clima {i}/{len(grupos)}: {gs[0]['venue']} {fechas[0]}..{fechas[-1]}")
        time.sleep(PAUSE_S)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2026-09-24")
    args = ap.parse_args()
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    games = fetch_schedule(args.start, args.end)
    attach_forecasts(games)
    args.out.mkdir(parents=True, exist_ok=True)
    cols = ["game_id", "game_date_utc", "official_date", "venue_id", "venue",
            "roof_type", "lat", "lon", "wind_kmh", "precip_mm", "fetched_at"]
    path = args.out / "games_weather_mlb.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for g in games:
            w.writerow({**g, "fetched_at": fetched_at})
    con = sum(1 for g in games if g.get("wind_kmh") is not None)
    print(f"escrito {path}: {len(games)} partidos, {con} con pronostico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
