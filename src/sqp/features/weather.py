"""Pregame weather feature via Open-Meteo (no API key required).

Fetches hourly temperature, precipitation and wind speed for a venue at event
start time. Responses are cached per (lat_1dp, lon_1dp, date) so all events
at the same venue on the same day share one HTTP call.

Effect on totals: adverse conditions (wind above threshold, precipitation)
reduce expected scoring, shifting probability toward Under and away from Over.
Coefficients default to 0 (no-op) until validated on OOS data.

Usage:
    weather = get_event_weather(lat, lon, start_time_utc, settings.weather)
    adj = weather_p_adjustment("totals", "Over", weather, settings.weather)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqp.config import WeatherConfig

log = logging.getLogger("sqp.features.weather")

# Module-level cache: (lat_1dp, lon_1dp, date_str) -> hourly payload | None
_CACHE: dict[tuple[float, float, str], dict | None] = {}

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_HOURLY_VARS = "temperature_2m,precipitation,wind_speed_10m"


def _fetch_hourly(lat: float, lon: float, date_str: str,
                  timeout: int) -> dict | None:
    """One HTTP call to Open-Meteo returning the hourly block for a date."""
    try:
        import requests
    except ImportError:
        log.warning("weather: requests not installed; skipping weather fetch.")
        return None

    today = datetime.now(timezone.utc).date()
    try:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    # Archive endpoint for past dates; forecast for future/today
    url = _ARCHIVE_URL if event_date < today else _FORECAST_URL
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": _HOURLY_VARS,
        "timezone": "UTC",
        "start_date": date_str,
        "end_date": date_str,
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("hourly")
    except Exception as exc:
        log.warning("weather: Open-Meteo request failed (%s); skipping.", exc)
        return None


def _hourly_at(hourly: dict, target_hour: int) -> dict | None:
    """Extract temperature, precipitation and wind for the closest hour."""
    times = hourly.get("time", [])
    if not times:
        return None
    # Find index whose hour is closest to target_hour
    idx = min(range(len(times)),
              key=lambda i: abs(int(times[i][11:13]) - target_hour))
    try:
        return {
            "temperature_c": float(hourly["temperature_2m"][idx]),
            "precipitation_mm": float(hourly["precipitation"][idx]),
            "wind_speed_kmh": float(hourly["wind_speed_10m"][idx]),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def get_event_weather(lat: float, lon: float, start_time_utc: str,
                      cfg: "WeatherConfig") -> dict | None:
    """Return {temperature_c, precipitation_mm, wind_speed_kmh} or None.

    Results are cached per venue-day; safe to call once per event.
    """
    if not cfg.enabled:
        return None
    try:
        dt = datetime.fromisoformat(start_time_utc.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    date_str = dt.strftime("%Y-%m-%d")
    cache_key = (round(lat, 1), round(lon, 1), date_str)
    if cache_key not in _CACHE:
        _CACHE[cache_key] = _fetch_hourly(lat, lon, date_str, cfg.timeout_s)
    hourly = _CACHE[cache_key]
    if hourly is None:
        return None
    return _hourly_at(hourly, dt.hour)


def weather_p_adjustment(
    market: str,
    selection: str,
    weather: dict | None,
    cfg: "WeatherConfig",
) -> float:
    """Additive probability adjustment for adverse weather on totals markets.

    High wind (above threshold) and precipitation both reduce expected scoring,
    so p(Over) decreases and p(Under) increases proportionally.
    Returns 0 for non-totals markets, or when weather is None, or coefs are 0.

    Sign convention: wind_coef_totals and precip_coef_totals should be
    NEGATIVE to model adverse conditions (e.g. wind_coef_totals=-0.001
    means -0.1 pp per km/h of wind above threshold for Over). Default 0 = no-op.
    """
    if weather is None or market != "totals":
        return 0.0
    if cfg.wind_coef_totals == 0.0 and cfg.precip_coef_totals == 0.0:
        return 0.0

    excess_wind = max(0.0, weather["wind_speed_kmh"] - cfg.wind_threshold_kmh)
    precip = weather["precipitation_mm"]
    # Combined adverse effect on Over (negative = reduces Over probability)
    over_delta = excess_wind * cfg.wind_coef_totals + precip * cfg.precip_coef_totals

    if selection == "Over":
        return over_delta
    if selection == "Under":
        return -over_delta
    return 0.0
