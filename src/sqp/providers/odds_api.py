"""The Odds API client (primary odds provider). https://the-odds-api.com

- API key from env only (never hardcoded).
- Featured markets: h2h, spreads, totals.
- Soccer h2h is 3-way (1X2). Tennis sport keys are per-tournament and carry
  NO scores in this API: tennis settlement requires a secondary results source.
- /scores endpoint feeds ratings and settlement for leagues marked has_scores.
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import cast

import requests
from sqp.exceptions import ProviderNotConfiguredError
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.logging_config import get_logger
from sqp.markets.odds import is_usable_price
from sqp.providers.odds_cache import FileCache

log = get_logger("sqp.odds_api")

BASE = "https://api.the-odds-api.com/v4"

# Transient upstream errors: retried with linear backoff, like the ESPN
# providers (audit 2026-07-24, M-11). A failed call returns no data, so one
# 5xx no longer loses the whole day's fetch.
# 429 incluido: un rate limit propagaba HTTPError y perdia el fetch completo de
# la liga, cuando es exactamente el caso que el backoff resuelve (auditoria
# 2026-07-29, D-05).
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 2.0  # multiplied by attempt number (linear backoff)

_TRUTHY = ("1", "true", "yes", "on")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY

# Verified against the official sports list (the-odds-api.com), 2026-06.
SPORT_KEYS: dict[str, dict] = {
    # league_id: {sport_key, family, three_way, has_scores}
    "mlb":    {"sport_key": "baseball_mlb",          "family": "baseball",   "three_way": False, "has_scores": True},
    "nba":    {"sport_key": "basketball_nba",        "family": "basketball", "three_way": False, "has_scores": True},
    "wnba":   {"sport_key": "basketball_wnba",       "family": "basketball", "three_way": False, "has_scores": True},
    "ncaab":  {"sport_key": "basketball_ncaab",      "family": "basketball", "three_way": False, "has_scores": True},
    "wncaab": {"sport_key": "basketball_wncaab",     "family": "basketball", "three_way": False, "has_scores": True},
    "nfl":    {"sport_key": "americanfootball_nfl",  "family": "football",   "three_way": False, "has_scores": True},
    "ncaaf":  {"sport_key": "americanfootball_ncaaf","family": "football",   "three_way": False, "has_scores": True},
    "nhl":    {"sport_key": "icehockey_nhl",         "family": "hockey",     "three_way": False, "has_scores": True},
    # soccer leagues are loaded dynamically from configs/leagues/soccer.yaml (family=soccer, three_way=True)
    # tennis tournaments are discovered dynamically via /sports (family=tennis, has_scores=False)
}


class OddsAPIClient:
    def __init__(self, api_key: str | None, regions: str = "us,eu", odds_format: str = "decimal",
                 session: requests.Session | None = None, *,
                 cache_ttl: float | None = None, force_refresh: bool | None = None,
                 offline_mode: bool | None = None, cache_dir: Path | None = None):
        if odds_format != "decimal":
            # Prices are persisted as price_decimal; american prices would be
            # stored in a decimal field and silently corrupt every probability.
            raise ValueError(
                f"OddsAPIClient stores prices as decimal; odds_format must be "
                f"'decimal', got '{odds_format}'. Set ODDS_API_ODDS_FORMAT=decimal.")
        self.api_key = api_key
        self.regions = regions
        self.odds_format = odds_format
        self.session = session or requests.Session()
        self._sports_cache: dict[str, dict] | None = None
        # Live quota, refreshed from response headers on every call (None until
        # the first request). Used by the budget guard in the daily orchestrator.
        self.requests_remaining: int | None = None
        self.requests_used: int | None = None
        self.requests_last: int | None = None  # credit cost of the most recent call
        # True when the most recent _get was served from the on-disk cache (no
        # network call, no credit spent). Lets callers skip side effects that must
        # happen once per real fetch (e.g. persisting an odds snapshot).
        self.last_response_cached: bool = False
        # On-disk TTL cache for paid endpoints: re-running within the TTL costs no
        # credits. Wired to .env (ODDS_CACHE_TTL_SECONDS / FORCE_REFRESH /
        # OFFLINE_MODE); the free /sports list is never cached.
        self.cache_ttl = float(cache_ttl if cache_ttl is not None else os.getenv(
            "ODDS_CACHE_TTL_SECONDS", os.getenv("CACHE_TTL_SECONDS", "21600")))
        self.force_refresh = _env_flag("FORCE_REFRESH") if force_refresh is None else force_refresh
        self.offline_mode = _env_flag("OFFLINE_MODE") if offline_mode is None else offline_mode
        if cache_dir is None:
            from sqp.config import ROOT
            cache_dir = ROOT / "data" / "cache" / "odds"
        self._cache = FileCache(cache_dir)

    def _require_key(self):
        if not self.api_key:
            raise ProviderNotConfiguredError(
                "ODDS_API_KEY is missing. Set it in .env or run with SQP_MODE=demo.")

    def _get(self, path: str, *, cache: bool = False, **params) -> list | dict:
        self.last_response_cached = False
        # Reset por llamada: _capture_quota solo asigna cuando el header viene
        # presente, asi que una respuesta sin headers heredaba el costo de la
        # llamada ANTERIOR y lo volvia a sumar al contador diario de creditos en
        # closing_capture (auditoria 2026-07-29, D-06).
        self.requests_last = None
        ckey = self._cache.key(path, params) if cache else None
        if ckey is not None and not self.force_refresh:
            ttl = float("inf") if self.offline_mode else self.cache_ttl
            hit = self._cache.get(ckey, ttl)
            if hit is not None:
                self.last_response_cached = True
                return hit
        if cache and self.offline_mode:
            raise ProviderNotConfiguredError(
                f"OFFLINE_MODE active and no cached response for {path}.")
        self._require_key()
        params["apiKey"] = self.api_key
        r = None
        last_error = ""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                r = self.session.get(f"{BASE}{path}", params=params, timeout=30)
            except (requests.Timeout, requests.ConnectionError) as exc:
                # Class name only: requests exception messages carry the full
                # URL including apiKey= (audit 2026-07-24, I-1).
                r, last_error = None, exc.__class__.__name__
            # getattr: test fakes/sessions may omit status_code; treat as final.
            if r is not None and getattr(r, "status_code", None) not in _RETRY_STATUS:
                break
            if r is not None:
                last_error = f"{r.status_code} {getattr(r, 'reason', '')}"
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_BACKOFF_SECONDS * attempt)
        if r is None:
            raise requests.ConnectionError(
                f"could not reach {BASE}{path} after {_MAX_ATTEMPTS} attempts "
                f"({last_error}; query redacted)")
        try:
            r.raise_for_status()
        except requests.HTTPError as exc:
            # The HTTPError message carries the full URL including apiKey=...;
            # callers log the exception, which would persist the credential in
            # logs/. Re-raise with the query string redacted (audit 2026-07-24, I-1).
            status = exc.response.status_code if exc.response is not None else "?"
            raise requests.HTTPError(
                f"{status} error for {BASE}{path} (query redacted)",
                response=exc.response) from None
        self._capture_quota(getattr(r, "headers", {}) or {})
        data = r.json()
        if ckey is not None:
            self._cache.put(ckey, data)
        return data

    def _capture_quota(self, headers) -> None:
        for attr, key in (("requests_remaining", "x-requests-remaining"),
                          ("requests_used", "x-requests-used"),
                          ("requests_last", "x-requests-last")):
            val = headers.get(key)
            if val is not None:
                try:
                    setattr(self, attr, int(val))
                except (TypeError, ValueError):
                    pass

    def list_sports(self, all_sports: bool = True) -> list[dict]:
        return cast("list[dict]", self._get("/sports", all="true" if all_sports else "false"))

    def is_sport_active(self, sport_key: str) -> bool | None:
        """Whether the sport is currently in season per /sports (cached per client).

        Returns None when the key is unknown to the API. /sports does not
        consume request quota.
        """
        if self._sports_cache is None:
            self._sports_cache = {s["key"]: s for s in self.list_sports(all_sports=True)}
        sport = self._sports_cache.get(sport_key)
        return None if sport is None else bool(sport.get("active", False))

    def _parse_events(self, raw: list, sport_key: str, league_id: str) -> list[EventOdds]:
        """Shared parser for live and historical odds payloads (same event shape).

        Las cotizaciones degeneradas (``price_decimal <= 1.0``, "sin pago") se
        CUENTAN y se avisan, pero NO se descartan. La decision es deliberada y
        tiene dos patas:

        - Descartarlas no cambia ningun calculo: el lado de LECTURA ya las filtra
          con el predicado unico ``markets.odds.is_usable_price`` desde `c210a22`
          (auditoria 2026-08-05, F-01). Un filtro aqui seria redundante.
        - Descartarlas SI destruiria evidencia de que el proveedor las emite, y
          `data-integrity-rules.md` prohibe la mutacion oculta de datos crudos.
          Mismo criterio que el guard de CLV no finito, que tambien avisa sin
          descartar la fila: el defecto queda audible, no corregido.

        Lo que faltaba era justamente eso: audibilidad. Medido el 2026-08-25
        sobre el historico persistido, 1.611 de 3.866.927 lineas (0,042%) tienen
        precio <= 1.0 -- concentradas en mlb y tenis -- y ninguna habia dejado
        rastro en ningun contador (hallazgo del primer run OOS, 2026-07-24).
        """
        out: list[EventOdds] = []
        degenerate = 0
        for ev in raw:
            event = Event(event_id=ev["id"], sport_key=sport_key, league=league_id,
                          home=ev["home_team"], away=ev["away_team"],
                          start_time=ev["commence_time"], data_label="real")
            lines: list[MarketLine] = []
            for bm in ev.get("bookmakers", []):
                for mk in bm.get("markets", []):
                    for oc in mk.get("outcomes", []):
                        price = float(oc["price"])
                        if not is_usable_price(price):
                            degenerate += 1
                        lines.append(MarketLine(
                            market=mk["key"], bookmaker=bm["key"], outcome=oc["name"],
                            price_decimal=price, point=oc.get("point")))
            out.append(EventOdds(event=event, lines=lines))
        if degenerate:
            # Agregado por llamada, no por linea: con 1.611 casos en el historico
            # un aviso por fila seria ruido que nadie lee.
            log.warning("[%s] %d cotizacion(es) degeneradas (precio <= 1.0 o no "
                        "finito) recibidas del proveedor y persistidas. El "
                        "consenso las descarta al leer; se avisa aqui para que el "
                        "problema sea visible en su ORIGEN.", league_id, degenerate)
        return out

    def fetch_odds(self, league_id: str, sport_key: str, markets: str = "h2h,spreads,totals") -> list[EventOdds]:
        raw = self._get(f"/sports/{sport_key}/odds", cache=True, regions=self.regions,
                        markets=markets, oddsFormat=self.odds_format)
        return self._parse_events(cast(list, raw), sport_key, league_id)

    def fetch_historical_odds(self, sport_key: str, date_iso: str, league_id: str | None = None,
                              markets: str = "h2h,spreads,totals") -> dict:
        """Odds snapshot as it stood at an ISO-8601 UTC timestamp (paid plans only).

        The /historical endpoint costs ~10x a live call (markets x regions x 10);
        read ``requests_last`` after calling to see the real credit cost. Returns
        the snapshot's timestamp, the adjacent snapshot timestamps (for paging),
        and the parsed events.
        """
        raw = self._get(f"/historical/sports/{sport_key}/odds", cache=True, regions=self.regions,
                        markets=markets, oddsFormat=self.odds_format, date=date_iso)
        snap = raw if isinstance(raw, dict) else {}
        events = self._parse_events(snap.get("data", []) or [], sport_key, league_id or sport_key)
        return {"timestamp": snap.get("timestamp"),
                "previous_timestamp": snap.get("previous_timestamp"),
                "next_timestamp": snap.get("next_timestamp"),
                "events": events}

    # The Odds API solo admite daysFrom en [1, 3]; fuera de rango devuelve 422.
    MAX_SCORES_DAYS_FROM = 3

    def fetch_scores(self, sport_key: str, days_from: int = 3) -> list[dict]:
        """Completed games for settlement / rating updates (where supported).
        Not cached: settlement needs fresh final scores; a stale cache could grade
        not-yet-final games. Scores are cheap; correctness outweighs the saving.

        ``days_from`` fuera de [1, 3] falla RAPIDO y en local. Antes se enviaba
        tal cual y el proveedor devolvia 422 por liga: N errores que en el log
        son indistinguibles de una caida del proveedor, gastando ademas una
        llamada por liga para averiguar algo que se sabe de antemano
        (observado el 2026-08-06 con --days-from 10)."""
        if not 1 <= days_from <= self.MAX_SCORES_DAYS_FROM:
            raise ValueError(
                f"days_from={days_from} fuera del rango admitido por el "
                f"proveedor [1, {self.MAX_SCORES_DAYS_FROM}]. Para liquidar mas "
                f"atras, usa el backfill de resultados historicos.")
        return cast("list[dict]", self._get(f"/sports/{sport_key}/scores", daysFrom=days_from))
