"""Backfill NHL goalie appearances (starter + backup, per game) from the
public NHL API into `data/historical/goalies_nhl.csv`, matched to the
ESPN-sourced results history (`ResultsStore('nhl')`).

Implements the backfill described in
`docs/research/2026-09-26-preregistro-portero-nhl.md`, section 3.3: one
request per second, `timeout=20` (`sqp.providers.nhl_api`), up to 3 retries
respecting `Retry-After`, single-threaded, resumable via a checkpoint file
(`data/historical/.goalies_nhl_backfill_checkpoint.json`).

Full authorized scope (operator decision, 2026-09-26): 2005-06 season through
2025-26 plus the current preseason (~34,000 requests, ~9.5h). This module
does not choose that range on its own; the caller (the CLI script) requires
explicit `--start`/`--end`.

Failure handling (revision independiente de Fable, B1 original vs. su
alternativa, 2026-09-27): la primera version de este backfill congelaba
`last_date_done` en el PRIMER dia incompleto de toda la ejecucion, para no
perder nunca un hueco en silencio. En el backfill real (2005-09-01 ..
2026-09-25) eso demostro un problema: `/v1/score/2009-09-15` y `/2009-09-20`
devuelven HTTP 500 de forma ESTABLE (dias vecinos como 2009-09-14 y
2009-10-01 responden 200), asi que el backfill nunca pasaria de 2009 --
reanudar solo reintentaria esas dos fechas para siempre.

La alternativa (la que ofrecio esa misma revision de Fable) es la que
implementa este modulo: en vez de congelar el puntero de reanudacion, cada
fecha incompleta se REGISTRA en una lista `failed` dentro del propio
checkpoint (fecha, tipo de fallo, codigo HTTP si lo hay, numero de intentos,
primera/ultima vez), y el checkpoint SI puede avanzar `last_date_done` mas
alla de esa fecha -- pero SOLO si queda registrada. Al reanudar, las fechas
de `failed` se reintentan PRIMERO; si una se completa, sale de la lista.

Esto exige distinguir dos clases de fallo, porque no todas merecen la misma
respuesta:

- Fallo DE UNA FECHA CONCRETA (HTTP 500/502/503/504 de un endpoint para un
  dia dado, una respuesta no-JSON, o un partido aun no finalizado): es un
  problema de ESE dato, no de la conexion ni de la API en general -- se
  registra en `failed` y el backfill SIGUE con el dia siguiente. El caso real
  de 2009-09-15/20 es exactamente esto. Un caso particular (revision
  independiente de Fable, escenario S1, 2026-09-27): `/v1/score/<dia>` solo
  lista los partidos por fecha LOCAL, asi que un partido nocturno de la costa
  oeste con `startTimeUTC` en el dia D aparece unicamente en
  `/v1/score/<D-1>` (desbordamiento horario). Si esa peticion de D-1 falla
  mientras se procesa D, no basta con registrar D-1 (que ya se procesa, o
  reintenta, por su cuenta) -- D TAMBIEN se registra, con el tipo propio
  `score_prev_*`, porque D es quien pierde ese partido si nadie vuelve a
  pedir D-1 en su nombre.
- Fallo GENERAL (timeout, error de conexion, o 429 persistente tras agotar
  los reintentos de `sqp.providers.nhl_api`): indica un problema de la
  conexion, del host, o de limite de tasa que probablemente afecta a
  CUALQUIER fecha, no a una en particular. Seguir adelante "registrando y
  saltando" aqui esconderia una caida real detras de un backfill que parece
  avanzar. Por eso estos SI cuentan para un contador de fallos consecutivos
  (`--max-consecutive-failures`, por defecto 3) que, al alcanzarse, detiene
  TODO el backfill sin avanzar el checkpoint mas alla del ultimo dia
  verdaderamente completo -- el mismo criterio "parar" que B1 usaba para
  cualquier fallo, ahora reservado a los que de verdad lo ameritan.

Solo la parada por fallo GENERAL deja un codigo de salida distinto de cero en
el CLI (`scripts/backfill_goalies_nhl.py`): un dia con fallos de fecha
concreta, todos registrados en `failed`, es una ejecucion COMPLETA (aunque
incompleta en cobertura), no un fallo del proceso.

Only FINAL games are ingested (B2): a boxscore whose `gameState` is not
`OFF`/`FINAL` (`sqp.providers.nhl_api.is_final_game_state`) is treated as
pending -- no raw JSON, no appearance rows -- because
`GoalieAppearanceStore.save` keeps the FIRST row it ever sees per key, and a
LIVE/CRIT snapshot saved once would freeze partial stats forever. A pending
game is recorded in `failed` (kind `not_final`) for retry; with `--end` no
posterior a ayer (UTC) esto no deberia ocurrir en la practica.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers import nhl_api
from sqp.sports.nhl_goalie_matching import build_results_index, match_espn_game
from sqp.storage.atomic import atomic_write_json, read_json_retrying
from sqp.storage.goalies import GoalieAppearanceStore, save_raw_boxscore
from sqp.storage.results_store import ResultsStore

log = get_logger("sqp.pipeline.goalie_backfill")

CHECKPOINT_NAME = ".goalies_nhl_backfill_checkpoint.json"
FAILED_REPORT_NAME = ".goalies_nhl_backfill_failed_dates.json"
MAX_CONSECUTIVE_FAILURES = 3


def checkpoint_path(root: Path) -> Path:
    return root / "data" / "historical" / CHECKPOINT_NAME


def failed_report_path(root: Path) -> Path:
    return root / "data" / "historical" / FAILED_REPORT_NAME


class _RateLimiter:
    """Enforces a minimum interval between requests (courtesy pacing against
    an undocumented public API); NOT a burst limiter, just spacing."""

    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            elapsed = time.monotonic() - self._last
            remaining = self.min_interval_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last = time.monotonic()


@dataclass
class Counts:
    days: int = 0
    games_total: int = 0
    games_matched: int = 0
    appearance_rows_seen: int = 0
    appearance_rows_added: int = 0
    starters_seen: int = 0
    unmatched: list[str] = field(default_factory=list)
    pending_games: list[str] = field(default_factory=list)
    stopped_by_failures: bool = False
    # Fechas que quedaron (o siguen) en `failed` al terminar esta ejecucion,
    # ya en el formato serializable del checkpoint -- para que el CLI pueda
    # informar y escribir el reporte sin releer el fichero.
    failed_dates: list[dict] = field(default_factory=list)


def _classify_exception(exc: Exception) -> tuple[str, int | None, bool]:
    """Clasifica un fallo de red en `(categoria, http_status, es_problema_general)`.

    Solo se consideran "problema general" -- el unico tipo que cuenta para el
    contador de fallos consecutivos que detiene TODO el backfill -- los que no
    se pueden atribuir a una fecha concreta: timeouts, errores de conexion, y
    HTTP 429 (limite de tasa) persistente tras agotar los reintentos de
    `sqp.providers.nhl_api`. Un HTTP 500/502/503/504 persistente de una fecha
    concreta (caso real: `/v1/score/2009-09-15` y `/2009-09-20` devuelven 500
    de forma estable mientras dias vecinos responden 200) es un problema DE
    ESA FECHA -- se registra en `failed` y el backfill sigue.

    Un `ValueError` (JSON invalido/inesperado) tambien se trata como
    especifico de la fecha: no hay motivo para asumir que TODAS las fechas
    futuras devolveran basura solo porque una lo hizo. Cualquier otra
    `RequestException` no reconocida se trata como problema general por
    precaucion (mejor parar de mas que perder cobertura sin darse cuenta)."""
    if isinstance(exc, requests.Timeout):
        return "timeout", None, True
    if isinstance(exc, requests.ConnectionError):
        return "connection", None, True
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status == 429:
            return "http_429", 429, True
        return "http", status, False
    if isinstance(exc, ValueError):
        return "invalid_response", None, False
    return "unknown", None, True


def _record_failed(failed_map: dict[str, dict], day: date, kind: str,
                    http_status: int | None) -> None:
    """Registra (o actualiza) una fecha incompleta en el mapa `failed` del
    checkpoint. Un fallo GENERAL nunca llega aqui (ver `_classify_exception`):
    solo los de una fecha concreta, que es lo que hace seguro dejar que
    `last_date_done` avance por delante de esta fecha."""
    key = day.isoformat()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = failed_map.get(key)
    if entry is None:
        failed_map[key] = {
            "date": key, "kind": kind, "http_status": http_status,
            "attempts": 1, "first_seen_at": now, "last_seen_at": now,
        }
    else:
        entry["kind"] = kind
        entry["http_status"] = http_status
        entry["attempts"] = int(entry.get("attempts", 0) or 0) + 1
        entry["last_seen_at"] = now


def _load_checkpoint(root: Path, start: date, end: date) -> tuple[date | None, dict[str, dict]]:
    """Ultima fecha completada y mapa de fechas fallidas para ESTE rango
    (start, end), o `(None, {})` si no aplica ningun checkpoint (primera
    ejecucion, rango distinto, o fichero ausente/corrupto).

    Migra en el momento de leer el formato anterior al 2026-09-27 (sin clave
    `failed`): a falta de esa clave se asume una lista vacia, sin necesidad de
    reescribir el fichero por adelantado ni de una version de esquema
    explicita -- el propio `.get("failed", [])` es la migracion."""
    p = checkpoint_path(root)
    if not p.exists():
        return None, {}
    try:
        data = read_json_retrying(p)
    except (OSError, ValueError):
        return None, {}
    if not isinstance(data, dict):
        return None, {}
    if data.get("start") != start.isoformat() or data.get("end") != end.isoformat():
        return None, {}

    last_date_done: date | None = None
    last = data.get("last_date_done")
    if last:
        try:
            last_date_done = date.fromisoformat(str(last))
        except ValueError:
            last_date_done = None

    failed_map: dict[str, dict] = {}
    for item in data.get("failed", []) or []:
        if not isinstance(item, dict):
            continue
        raw_date = item.get("date")
        if not raw_date:
            continue
        try:
            date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        key = str(raw_date)
        failed_map[key] = {
            "date": key,
            "kind": item.get("kind", "unknown"),
            "http_status": item.get("http_status"),
            "attempts": int(item.get("attempts", 1) or 1),
            "first_seen_at": item.get("first_seen_at") or item.get("last_seen_at") or "",
            "last_seen_at": item.get("last_seen_at") or item.get("first_seen_at") or "",
        }
    return last_date_done, failed_map


def _save_checkpoint(root: Path, start: date, end: date, last_date_done: date,
                      failed_map: dict[str, dict]) -> None:
    p = checkpoint_path(root)
    # Un rango sin ningun partido (por ejemplo, dias de descanso al principio
    # de temporada) nunca pasa por `GoalieAppearanceStore.save`, que es lo
    # unico que hasta ahora creaba `data/historical/` -- sin este mkdir, el
    # primer dia sin partidos de un `root` recien creado hacia fallar el
    # propio checkpoint (detectado al probar en un directorio temporal, sin
    # sembrar resultados de antemano).
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        {"start": start.isoformat(), "end": end.isoformat(),
         "last_date_done": last_date_done.isoformat(),
         "failed": [failed_map[k] for k in sorted(failed_map)],
         "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        p,
    )


def _guess_season_phase(d: date) -> str:
    """Aproximacion del tipo de temporada de una fecha SIN peticiones
    adicionales -- solo por el mes calendario, tal como autoriza el pedido
    ("si se puede saber sin leer marcadores... o simplemente el mes").

    La NHL juega pretemporada en septiembre, temporada regular de octubre a
    marzo, y playoffs de mayo a junio; abril es una transicion genuina (el
    cierre de la regular y el arranque de playoffs varian cada temporada) y se
    marca explicitamente como incierto en vez de adivinar; julio/agosto no
    tienen partidos de la NHL."""
    m = d.month
    if m == 9:
        return "preseason"
    if m in (10, 11, 12, 1, 2, 3):
        return "regular_season"
    if m in (5, 6):
        return "playoffs"
    if m == 4:
        return "unknown_regular_or_playoffs"
    return "offseason"


def write_failed_report(root: Path, start: date, end: date, failed_map: dict[str, dict]) -> Path:
    """Escribe, junto al checkpoint, un JSON con las fechas que siguen en
    `failed` al terminar esta ejecucion -- cada una con un marcador de
    temporada (`_guess_season_phase`) para priorizar la revision manual.
    Se escribe siempre (incluso lista vacia) para que el fichero refleje
    siempre el estado actual, nunca uno de una ejecucion anterior."""
    p = failed_report_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for key in sorted(failed_map):
        entry = dict(failed_map[key])
        entry["season_phase"] = _guess_season_phase(date.fromisoformat(key))
        entries.append(entry)
    atomic_write_json(
        {"start": start.isoformat(), "end": end.isoformat(),
         "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "failed": entries},
        p,
    )
    return p


def run(start: date, end: date, sleep_s: float = 1.0, root: Path = ROOT,
        max_consecutive_failures: int = MAX_CONSECUTIVE_FAILURES) -> Counts:
    counts = Counts()
    session = requests.Session()
    limiter = _RateLimiter(sleep_s)
    store = GoalieAppearanceStore(root)
    results_index = build_results_index(ResultsStore(root).load("nhl"))

    resume_after, failed_map = _load_checkpoint(root, start, end)
    cursor = start if resume_after is None else resume_after + timedelta(days=1)
    if resume_after is not None:
        log.info("Reanudando backfill de porteros NHL tras %s (checkpoint).", resume_after)

    score_cache: dict[str, list[dict]] = {}
    consecutive_failures = 0
    # A diferencia de `failed_map` (fechas concretas, seguras de saltar), este
    # contador y `first_incomplete` solo los tocan los fallos GENERALES
    # (timeout/conexion/429 persistente): son los unicos que detienen todo el
    # backfill, y por eso son tambien los unicos que congelan el avance del
    # checkpoint mientras la ejecucion sigue viva sin llegar al umbral.
    first_incomplete: date | None = None
    stop_requested = False

    def _fetch_score(local_date: date) -> list[dict]:
        key = local_date.isoformat()
        if key not in score_cache:
            limiter.wait()
            payload = nhl_api.fetch_score(key, session)
            score_cache[key] = nhl_api.parse_score_games(payload)
            # Solo se conservan los dias en juego: evita crecer sin limite en
            # un backfill de anios (cache "cada dia se pide una sola vez").
            if len(score_cache) > 3:
                for old_key in sorted(score_cache)[:-3]:
                    del score_cache[old_key]
        return score_cache[key]

    def _process_day(day: date) -> bool:
        """Procesa un dia completo: `/v1/score` del dia y del anterior (para
        el desbordamiento horario), boxscore de cada partido encontrado.
        Devuelve `True` si el dia tuvo AL MENOS un problema (de cualquier
        tipo) en esta llamada, `False` si quedo limpio. Muta `counts`,
        `failed_map` y, solo para fallos generales, `consecutive_failures` /
        `first_incomplete` / `stop_requested` (todas `nonlocal`)."""
        nonlocal consecutive_failures, first_incomplete, stop_requested
        had_issue = False

        def _handle_score_failure(exc: Exception, attributed_day: date, prefix: str) -> bool:
            """Clasifica un fallo de `/v1/score`, lo registra donde
            corresponde (fecha atribuida, no necesariamente `day` -- el
            desbordamiento del dia anterior atribuye a `attributed_day`, esa
            fecha, no a `day`), y devuelve si es GENERAL (el llamador decide
            si eso obliga a abortar el resto del dia)."""
            nonlocal consecutive_failures, first_incomplete, stop_requested
            category, http_status, is_general = _classify_exception(exc)
            if is_general:
                consecutive_failures += 1
                if first_incomplete is None:
                    first_incomplete = day
                log.warning("Fallo consultando /v1/score para %s (%s): %s",
                            attributed_day.isoformat(), exc.__class__.__name__, exc)
                if consecutive_failures >= max_consecutive_failures:
                    log.error("%d fallos GENERALES consecutivos (%s); se detiene "
                              "el backfill en %s sin avanzar el checkpoint.",
                              consecutive_failures, category, day.isoformat())
                    counts.stopped_by_failures = True
                    stop_requested = True
            else:
                kind = f"{prefix}_http" if category == "http" else f"{prefix}_{category}"
                _record_failed(failed_map, attributed_day, kind, http_status)
                log.warning("Fallo especifico de %s en /v1/score (%s, http=%s); "
                            "se registra en 'failed' y se sigue.",
                            attributed_day.isoformat(), kind, http_status)
            return is_general

        # Peticion del dia PROPIO: si falla, no hay lista de partidos de HOY
        # en absoluto -- se aborta el resto del dia (no hay nada que procesar).
        try:
            games_today = [g for g in _fetch_score(day) if g["date_utc"] == day.isoformat()]
        except (requests.RequestException, ValueError) as exc:
            had_issue = True
            _handle_score_failure(exc, day, "score")
            return had_issue

        # Peticion del dia ANTERIOR (desbordamiento horario): si falla, se
        # atribuye a ESA fecha (que ya se proceso, o se procesara, como `day`
        # en su propia iteracion) -- no a `day` -- y solo se pierde el posible
        # desbordamiento, no las peticiones ya confirmadas de `day`.
        try:
            games_yesterday = [g for g in _fetch_score(day - timedelta(days=1))
                               if g["date_utc"] == day.isoformat()]
        except (requests.RequestException, ValueError) as exc:
            had_issue = True
            is_general = _handle_score_failure(exc, day - timedelta(days=1), "score")
            games_yesterday = []
            if not is_general:
                # Revision independiente de Fable (2026-09-27, escenario S1):
                # un partido nocturno de la costa oeste con `startTimeUTC` en
                # `day` solo aparece en `/v1/score/<day-1>` (desbordamiento
                # horario). El registro de `day - 1` de arriba no basta: si
                # `day - 1` se recupera y sale de `failed` por su cuenta,
                # nadie vuelve a pedir su desbordamiento para `day`, y ese
                # partido se pierde en silencio (nunca llega al store ni
                # queda en `failed`). Se registra TAMBIEN `day`, con un tipo
                # propio (`score_prev_*`, nunca confundible con un fallo del
                # propio `/v1/score/day`) para que reintentar `day` vuelva a
                # pedir `day - 1` y, si ya esta sano, recoja el desbordamiento.
                category, http_status, _ = _classify_exception(exc)
                kind = "score_prev_http" if category == "http" else f"score_prev_{category}"
                _record_failed(failed_map, day, kind, http_status)
                log.warning("Fallo especifico en /v1/score de %s (desbordamiento "
                            "horario de %s); se registra tambien %s en 'failed'.",
                            (day - timedelta(days=1)).isoformat(), day.isoformat(),
                            day.isoformat())
            if stop_requested:
                return had_issue

        games = games_today + games_yesterday
        appearance_rows: list[dict] = []
        for g in games:
            counts.games_total += 1
            match = match_espn_game(g["date_utc"], g["home_name"], g["away_name"], results_index)
            if match is not None:
                counts.games_matched += 1
            else:
                counts.unmatched.append(f"{g['date_utc']} {g['away_name']} @ {g['home_name']}")

            try:
                limiter.wait()
                box = nhl_api.fetch_boxscore(g["nhl_game_id"], session)
            except (requests.RequestException, ValueError) as exc:
                category, http_status, is_general = _classify_exception(exc)
                had_issue = True
                if is_general:
                    consecutive_failures += 1
                    if first_incomplete is None:
                        first_incomplete = day
                    log.warning("Fallo consultando boxscore %s (%s): %s",
                                g["nhl_game_id"], exc.__class__.__name__, exc)
                    if consecutive_failures >= max_consecutive_failures:
                        log.error("%d fallos GENERALES consecutivos (%s); se "
                                  "detiene el backfill sin avanzar el checkpoint.",
                                  consecutive_failures, category)
                        counts.stopped_by_failures = True
                        stop_requested = True
                        if appearance_rows:
                            counts.appearance_rows_added += store.save(appearance_rows)
                        return had_issue
                    continue
                kind = "boxscore_http" if category == "http" else f"boxscore_{category}"
                _record_failed(failed_map, day, kind, http_status)
                log.warning("Fallo especifico de %s en boxscore %s (%s, http=%s); "
                            "se registra en 'failed' y se sigue.",
                            day.isoformat(), g["nhl_game_id"], kind, http_status)
                continue
            consecutive_failures = 0

            if not nhl_api.is_final_game_state(box):
                # Partido en juego / aun no arrancado (LIVE, CRIT, FUT, PRE...):
                # se trata como pendiente. No se guarda el JSON crudo (dejaria
                # de ser un snapshot inmutable) ni las filas de aparicion (el
                # store se queda con la PRIMERA fila que ve por clave, y una
                # parcial congelada nunca se corregiria). Se registra en
                # `failed` (kind `not_final`) para que la proxima ejecucion lo
                # reintente primero.
                had_issue = True
                counts.pending_games.append(
                    f"{g['date_utc']} {g['away_name']} @ {g['home_name']} "
                    f"(gameState={box.get('gameState')!r})")
                _record_failed(failed_map, day, "not_final", None)
                continue

            save_raw_boxscore(root, g["nhl_game_id"], box)

            for row in nhl_api.parse_boxscore_goalies(box, g["nhl_game_id"]):
                counts.appearance_rows_seen += 1
                if row["starter"]:
                    counts.starters_seen += 1
                row["date"] = g["date_utc"]
                row["team_nhl"] = g["home_name"] if row["team_side"] == "home" else g["away_name"]
                if match is not None:
                    row["espn_game_id"] = match["espn_game_id"]
                    row["team_espn"] = (match["home_espn"] if row["team_side"] == "home"
                                        else match["away_espn"])
                    row["matched"] = True
                else:
                    row["espn_game_id"] = ""
                    row["team_espn"] = ""
                    row["matched"] = False
                appearance_rows.append(row)

        if appearance_rows:
            counts.appearance_rows_added += store.save(appearance_rows)
        counts.days += 1
        return had_issue

    # 1) Reintento primero de las fechas que quedaron en `failed`: si una se
    #    completa limpia (sin fallos de ningun tipo), sale de la lista.
    if failed_map:
        pending_retries = sorted(failed_map)
        log.info("Reintentando %d fecha(s) marcada(s) como fallidas en el checkpoint.",
                  len(pending_retries))
        for day_key in pending_retries:
            if stop_requested:
                break
            retry_day = date.fromisoformat(day_key)
            had_issue = _process_day(retry_day)
            if not had_issue and not stop_requested:
                del failed_map[day_key]
                log.info("Fecha %s completada al reintentar; sale de 'failed'.", day_key)
        if resume_after is not None:
            _save_checkpoint(root, start, end, resume_after, failed_map)

    # 2) Marcha hacia delante desde el checkpoint, si el reintento no paro.
    day = cursor
    while not stop_requested and day <= end:
        _process_day(day)
        if not stop_requested and first_incomplete is None:
            _save_checkpoint(root, start, end, day, failed_map)
        day += timedelta(days=1)

    counts.failed_dates = [failed_map[k] for k in sorted(failed_map)]
    write_failed_report(root, start, end, failed_map)
    return counts
