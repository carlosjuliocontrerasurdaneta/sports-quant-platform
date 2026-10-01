"""Pregame team-level features: rest days and recent form.

Both features are computed from the chronologically-sorted results list that
the adapter already uses for Elo fitting, so there is no extra data source.

Rest days: days since a team's last game strictly before the event date.
A larger differential (home more rested than away) is a weak positive signal.

Recent form: win rate (win=1, draw=0.5, loss=0) over the last n completed
games. Draws count as 0.5 regardless of sport; for two-outcome sports all
results are 0 or 1, so the metric is equivalent to plain win rate.

Both return None when there is insufficient data (< 1 prior game for rest,
< 2 for form) — callers treat None as "no adjustment".

Scaling guide for the coefficients in RiskConfig:
  rest_days_coef: probability points added per extra rest day of advantage.
    e.g. 0.002 → 3-day advantage gives home +0.6 pp.
  recent_form_coef: probability points added per unit of form differential
    (range −1 to +1).  e.g. 0.05 → perfect vs winless gives +5 pp.
  Both default to 0.0 (no-op) until validated on OOS data.
"""
from __future__ import annotations

import bisect
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Callable


def _hasta(results: list[dict], reference_date: str | None) -> list[dict]:
    """`results` recortado a lo ESTRICTAMENTE anterior a `reference_date`.

    Con `None` devuelve la lista tal cual, que es el comportamiento historico.

    Existe porque `team_rest_days` era la UNICA feature de este modulo que
    recibia fecha de corte y la aplicaba (`d >= ref: continue`); las otras diez
    tomaban "las ultimas n" de la lista que les dieran, asi que la proteccion
    contra look-ahead vivia entera en el llamador (AUD-LOW-005, 2026-09-06).

    No habia fuga: los dos consumidores recortan antes -- el backtest con
    `roi_engine._prior_games` (`d < rd`) y el run diario con partidos ya
    terminados --, y ademas la capa esta inerte (todos los coeficientes a 0
    desde el 2026-09-01). El problema era que un tercer consumidor que pasara el
    historial completo introducia look-ahead en diez features a la vez, sin
    error ni aviso. Filtrar aqui hace la garantia estructural en vez de
    disciplinada, y con las listas ya recortadas es un no-op exacto.

    Mismo criterio de corte que `team_rest_days`: se compara `date` truncado a
    10 caracteres y el MISMO dia queda FUERA. Un partido del propio dia del
    evento puede no haberse jugado todavia cuando se estima.
    """
    if reference_date is None:
        return results
    ref = str(reference_date)[:10]
    return [r for r in results if str(r.get("date", ""))[:10] < ref]


# --------------------------------------------------------------------------
# Indice por equipo (optimizacion de coste, 2026-09-30, autorizado por el
# operador; ver docs/research -- pre-registro de la bateria de ajustes).
#
# PROBLEMA: `build_adjustment_context` llama a ~15 funciones de este modulo
# por partido, y cada una filtra DESDE CERO el historial que le pasan --
# `_hasta` + pertenencia de equipo + `[-n:]` -- para encontrar practicamente
# el MISMO subconjunto ("los partidos de este equipo", "los de este equipo en
# casa", "los de esta pareja de equipos"...). En un recorrido walk-forward (el
# backtest, o la bateria de `scripts/research/measure_adjustment_battery.py`)
# el historial pasado a cada partido crece con cada jornada, asi que ese
# refiltrado repetido hace el coste por partido O(m) (m = tamano del
# historial de los dos equipos) y el recorrido completo de una liga O(n^2).
# Medido en NFL (la liga que decide con menos filas): ~24 ms/partido en las
# primeras 250 filas, ~116 ms/partido hacia la fila 1.750.
#
# SOLUCION: agrupar `results` por equipo (y por pareja, para el cara a cara)
# en UNA sola pasada, y resolver el corte temporal con `bisect` en vez de un
# filtro lineal cuando el grupo esta ordenado por fecha -- precondicion que
# las propias funciones de "ultimos n" ya documentaban. Con eso, una consulta
# de ventana pasa de O(m) a O(log m + n): el coste dominante por partido deja
# de crecer con el historial acumulado.
#
# GARANTIA DE EQUIVALENCIA: para un grupo NO ordenado por fecha (entrada que
# rompe la precondicion documentada, p.ej. un historial mal ordenado por un
# proveedor) cada consulta cae a un filtro lineal que reconstruye LITERALMENTE
# el mismo criterio que el codigo original (`_hasta` + pertenencia + `[-n:]`
# con la semantica nativa de Python, incluida la de n<=0), nunca peor que el
# coste original. El camino rapido y el de respaldo se contrastan
# exhaustivamente contra una copia de referencia del codigo anterior en
# `tests/test_rest_form_index_equivalence.py`.
# --------------------------------------------------------------------------
class _DateGroup:
    """Subconjunto de `results` (mismo orden relativo que la lista de
    entrada) mas sus claves de fecha (`date` truncada a 10 caracteres) ya
    extraidas, para poder cortar por `< ref` con `bisect` en vez de un filtro
    lineal cuando esas fechas son no decrecientes."""

    __slots__ = ("games", "_dates", "_sorted")

    def __init__(self, games: list[dict]) -> None:
        self.games = games
        self._dates = [str(g.get("date", ""))[:10] for g in games]
        self._sorted = all(self._dates[i] <= self._dates[i + 1]
                           for i in range(len(self._dates) - 1))

    def cutoff_count(self, ref: str | None) -> int:
        """Cuantos elementos cumplen `date < ref` (todos si `ref is None`)."""
        if ref is None:
            return len(self.games)
        if self._sorted:
            return bisect.bisect_left(self._dates, ref)
        return sum(1 for d in self._dates if d < ref)

    def window(self, ref: str | None, n: int) -> list[dict]:
        """Equivalente exacto a `_hasta(games, ref)` + `[-n:]`, preservando el
        orden original. Camino rapido O(log m + n) cuando el grupo esta
        ordenado por fecha y `n > 0` (el caso real: las ventanas de
        `RiskConfig` son enteros positivos); en cualquier otro caso
        (desorden, o `n <= 0` -- infrecuente, nunca usado por la
        configuracion de produccion) reconstruye la lista completa antes de
        rebanarla con la semantica NATIVA de Python (`lst[-n:]`, valida
        tambien para n=0 y n negativo), identica a la del codigo original."""
        if self._sorted and n > 0:
            cnt = self.cutoff_count(ref)
            return self.games[max(0, cnt - n):cnt]
        filtered = (self.games if ref is None
                   else [g for g, d in zip(self.games, self._dates) if d < ref])
        return filtered[-n:]

    def last_date_before(self, ref: str) -> str | None:
        """Fecha (str) maxima estrictamente anterior a `ref`, o `None`."""
        if self._sorted:
            cnt = self.cutoff_count(ref)
            return self._dates[cnt - 1] if cnt > 0 else None
        qualifying = [d for d in self._dates if d < ref]
        return max(qualifying) if qualifying else None

    def reversed_before(self, ref: str):
        """Itera las filas con `date < ref` en orden CRONOLOGICO INVERSO (la
        mas reciente primero), sin materializar ninguna lista intermedia
        cuando el grupo esta ordenado -- lo que necesita `team_streak`, que
        se detiene en la primera rotura de racha."""
        if self._sorted:
            cnt = self.cutoff_count(ref)
            for i in range(cnt - 1, -1, -1):
                yield self.games[i]
        else:
            for i in range(len(self.games) - 1, -1, -1):
                if self._dates[i] < ref:
                    yield self.games[i]


class StaleTeamIndexError(ValueError):
    """`team_index` no fue construido sobre el mismo `results` (y el mismo
    `normalize`) que se le esta pasando ahora.

    Contrato duro (2026-09-30, revision de Fable): un `TeamHistoryIndex`
    cachea agrupaciones por equipo de una lista `results` CONCRETA bajo un
    `normalize` CONCRETO. Si el llamador reutiliza un indice construido sobre
    un `results` distinto (otra liga, otro recorte temporal, otra lista) las
    consultas devuelven resultados de OTRO historial sin ningun aviso -- el
    tipo de fallo silencioso que el resto de este modulo evita
    deliberadamente. La comprobacion (`TeamHistoryIndex.matches_source`) es
    barata a proposito -- longitud + identidad de objeto, nunca un hash de
    contenido -- por lo que detecta la reutilizacion accidental entre
    backtest/daily sin pagar el coste de comparar el contenido, a costa de no
    detectar una mutacion in-place que conserve la longitud; ese caso queda
    como contrato documentado, no verificado."""


@dataclass(frozen=True)
class TeamHistoryIndex:
    """Agrupacion de `results` por equipo y por pareja de equipos, calculada
    en UNA sola pasada. `build_adjustment_context` la construye (o reutiliza
    una que le pasen) en vez de dejar que cada una de sus ~15 llamadas a este
    modulo vuelva a recorrer el historial completo por su cuenta.

    Contrato: para cualquier entrada, una consulta contra el indice devuelve
    EXACTAMENTE lo mismo (mismos elementos, mismo orden) que filtrar
    `results` desde cero con el mismo criterio -- verificado en
    `tests/test_rest_form_index_equivalence.py` contra una copia de
    referencia de las funciones originales, con semillas fijas y varias
    ligas sinteticas.

    Contrato duro sobre la procedencia: un indice solo es valido para
    consultar el MISMO `results` (misma lista, no una copia con el mismo
    contenido) y el MISMO `normalize` con los que se construyo -- ver
    `matches_source` y `StaleTeamIndexError`. `source_len`/`source_id`/
    `normalize_id` son metadatos de control, no datos del dominio: quedan
    fuera de la igualdad y del repr del indice."""

    all: dict[str, _DateGroup]
    home: dict[str, _DateGroup]
    away: dict[str, _DateGroup]
    pairs: dict[frozenset, _DateGroup]
    source_len: int = field(default=0, compare=False, repr=False)
    source_id: int = field(default=0, compare=False, repr=False)
    normalize_id: int | None = field(default=None, compare=False, repr=False)

    @classmethod
    def build(cls, results: list[dict],
             normalize: Callable[[str], str] | None = None) -> "TeamHistoryIndex":
        norm = normalize or (lambda x: x)
        all_g: dict[str, list[dict]] = defaultdict(list)
        home_g: dict[str, list[dict]] = defaultdict(list)
        away_g: dict[str, list[dict]] = defaultdict(list)
        pair_g: dict[frozenset, list[dict]] = defaultdict(list)
        for r in results:
            h = norm(str(r.get("home", "")))
            a = norm(str(r.get("away", "")))
            home_g[h].append(r)
            away_g[a].append(r)
            all_g[h].append(r)
            if a != h:
                all_g[a].append(r)
            pair_g[frozenset((h, a))].append(r)
        return cls(all={k: _DateGroup(v) for k, v in all_g.items()},
                  home={k: _DateGroup(v) for k, v in home_g.items()},
                  away={k: _DateGroup(v) for k, v in away_g.items()},
                  pairs={k: _DateGroup(v) for k, v in pair_g.items()},
                  source_len=len(results), source_id=id(results),
                  normalize_id=(id(normalize) if normalize is not None else None))

    def matches_source(self, results: list[dict],
                       normalize: Callable[[str], str] | None = None) -> bool:
        """Comprobacion barata (longitud + identidad de objeto, NUNCA un hash
        de contenido) de que este indice se construyo sobre este MISMO
        `results` bajo este MISMO `normalize`. Ver `StaleTeamIndexError` para
        el contrato completo y sus limites."""
        return (self.source_len == len(results)
               and self.source_id == id(results)
               and self.normalize_id == (id(normalize) if normalize is not None else None))


def _rest_days_from_group(grp: _DateGroup | None, ref: str) -> int | None:
    """Nucleo de `team_rest_days` a partir de un grupo ya construido."""
    if grp is None:
        return None
    last = grp.last_date_before(ref)
    if last is None:
        return None
    return (date.fromisoformat(ref) - date.fromisoformat(last)).days


def _win_rate_from_window(recent: list[dict],
                          home_matches: Callable[[dict], bool]) -> float | None:
    """Tasa de victorias (1/0.5/0) sobre `recent`, generalizando el bucle que
    comparten `team_recent_form` y `team_h2h_form`. `home_matches(r)` decide,
    fila a fila, si el "home" de esa fila es la perspectiva que se mide
    (equivalente a `is_home`/`home_is_a` en las funciones originales).

    NO usar para `team_recent_form_home`/`team_recent_form_away`: esas dos
    usan una expresion DISTINTA (`1.0 if hs > aws else (0.5 if hs == aws else
    0.0)`) que, con un marcador NaN, da 0.0 en vez del 0.5 que da el
    if/elif/else de aqui -- ver `_home_win_rate_from_window` y
    `_away_win_rate_from_window` (bug detectado en revision de Fable,
    2026-09-30: la primera version de este indice reutilizaba esta funcion
    tambien para esas dos, y silenciosamente cambiaba el tratamiento de NaN)."""
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        is_persp_home = home_matches(r)
        if hs > aws:
            total += 1.0 if is_persp_home else 0.0
        elif aws > hs:
            total += 0.0 if is_persp_home else 1.0
        else:
            total += 0.5
    return total / graded if graded >= 2 else None


def _home_win_rate_from_window(recent: list[dict]) -> float | None:
    """Nucleo de `team_recent_form_home` (perspectiva SIEMPRE home de la
    fila, porque `recent` ya viene filtrado a partidos en casa de un equipo):
    replica LITERALMENTE `1.0 if hs > aws else (0.5 if hs == aws else 0.0)`,
    fila a fila. Deliberadamente NO es un caso particular de
    `_win_rate_from_window`: con un marcador NaN esa da 0.5 (cae al `else`
    del if/elif/else) y esta da 0.0 (ni `hs > aws` ni `hs == aws` son ciertos
    con NaN) -- son las dos ramas que team_recent_form_home/_away distinguian
    ya en el codigo original y que hay que preservar exactas."""
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def _away_win_rate_from_window(recent: list[dict]) -> float | None:
    """Nucleo de `team_recent_form_away` (perspectiva SIEMPRE away de la
    fila): replica LITERALMENTE `1.0 if aws > hs else (0.5 if hs == aws else
    0.0)`. Ver `_home_win_rate_from_window` para por que esto NO se
    generaliza con `_win_rate_from_window`."""
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if aws > hs else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def _avg_margin_from_window(recent: list[dict], team_n: str,
                            norm: Callable[[str], str]) -> float | None:
    if len(recent) < 2:
        return None
    margins = []
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        is_home = norm(str(r.get("home", ""))) == team_n
        margins.append(hs - aws if is_home else aws - hs)
    return sum(margins) / len(margins) if margins else None


def _avg_scored_from_window(recent: list[dict], team_n: str,
                            norm: Callable[[str], str]) -> float | None:
    if len(recent) < 2:
        return None
    scored = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            scored.append(float(r["home_score"]) if is_home else float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(scored) / len(scored) if scored else None


def _avg_conceded_from_window(recent: list[dict], team_n: str,
                              norm: Callable[[str], str]) -> float | None:
    if len(recent) < 2:
        return None
    conceded = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            conceded.append(float(r["away_score"]) if is_home else float(r["home_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(conceded) / len(conceded) if conceded else None


def _avg_total_from_window(recent: list[dict]) -> float | None:
    if len(recent) < 2:
        return None
    totals_list = []
    for r in recent:
        try:
            totals_list.append(float(r["home_score"]) + float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(totals_list) / len(totals_list) if totals_list else None


def _over_rate_from_window(recent: list[dict],
                           reference_line: float | None) -> float | None:
    if reference_line is None:
        return None
    if len(recent) < 2:
        return None
    overs = []
    for r in recent:
        try:
            overs.append(1.0 if float(r["home_score"]) + float(r["away_score"]) > reference_line
                        else 0.0)
        except (KeyError, TypeError, ValueError):
            continue
    return sum(overs) / len(overs) if overs else None


def _streak_from_group(grp: _DateGroup | None, team_n: str,
                       norm: Callable[[str], str], ref: str) -> int:
    if grp is None:
        return 0
    streak = 0
    for r in grp.reversed_before(ref):
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            break
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            outcome = 1 if is_home else -1
        elif aws > hs:
            outcome = -1 if is_home else 1
        else:
            break  # draw breaks streak
        if streak == 0:
            streak = outcome
        elif (outcome > 0) == (streak > 0):
            streak += outcome
        else:
            break
    return streak


def over_rate_from_index(team_index: TeamHistoryIndex, team: str,
                         reference_line: float | None, n: int,
                         normalize: Callable[[str], str] | None = None,
                         reference_date: str | None = None) -> float | None:
    """Equivalente indexado de `team_over_rate`, para que
    `adjust_model_probability` (llamada una vez por cada seleccion de un
    mismo evento) no vuelva a filtrar `ctx.results` desde cero por cada una."""
    norm = normalize or (lambda x: x)
    grp = team_index.all.get(norm(team))
    if grp is None:
        return None
    ref = reference_date[:10] if reference_date is not None else None
    return _over_rate_from_window(grp.window(ref, n), reference_line)


def compute_pregame_features(
    home: str, away: str, ref_date: str, results: list[dict],
    recent_form_n: int, h2h_n: int, totals_tendency_n: int, off_def_n: int,
    home_away_form_n: int, margin_n: int,
    normalize: Callable[[str], str] | None = None,
    team_index: TeamHistoryIndex | None = None,
) -> dict:
    """Las 16 features pregame de `AdjustmentContext` (todo salvo `weather`,
    `results`, `normalize` y `ref_date`, que el llamador ya tiene), calculadas
    con el indice por equipo en vez de con ~15 llamadas independientes a las
    funciones de este modulo -- cada una de las cuales volvia a filtrar
    `results` desde cero. Equivalencia exacta con esas funciones (misma
    seleccion de filas, mismo orden de suma, mismos redondeos) verificada en
    `tests/test_rest_form_index_equivalence.py`.

    `team_index`: si se pasa uno ya construido (p.ej. porque el llamador lo
    reutiliza entre varios partidos con el mismo `results`), se usa tal cual;
    si no, se construye aqui con una sola pasada sobre `results`.

    Contrato duro sobre `team_index` (2026-09-30): si se pasa, DEBE haberse
    construido con este MISMO `results` (misma lista) y este MISMO
    `normalize` -- ver `TeamHistoryIndex.matches_source` y
    `StaleTeamIndexError`. Esta funcion, de bajo nivel y en la ruta caliente
    del backtest, no repite esa comprobacion en cada llamada (se pagaria por
    partido); el punto de entrada de mas alto nivel, `build_adjustment_context`
    en `pipeline/probabilities.py`, es quien la hace una vez por evento antes
    de llamar aqui."""
    idx = team_index if team_index is not None else TeamHistoryIndex.build(results, normalize)
    norm = normalize or (lambda x: x)
    home_n, away_n = norm(home), norm(away)
    ref = ref_date[:10]

    all_home = idx.all.get(home_n)
    all_away = idx.all.get(away_n)

    rest_home = _rest_days_from_group(all_home, ref)
    rest_away = _rest_days_from_group(all_away, ref)

    form_home = (_win_rate_from_window(
        all_home.window(ref, recent_form_n), lambda r: norm(str(r.get("home", ""))) == home_n)
        if all_home is not None else None)
    form_away = (_win_rate_from_window(
        all_away.window(ref, recent_form_n), lambda r: norm(str(r.get("home", ""))) == away_n)
        if all_away is not None else None)

    pair = idx.pairs.get(frozenset((home_n, away_n)))
    h2h_home = (_win_rate_from_window(
        pair.window(ref, h2h_n), lambda r: norm(str(r.get("home", ""))) == home_n)
        if pair is not None else None)

    avg_total_home = (_avg_total_from_window(all_home.window(ref, totals_tendency_n))
                      if all_home is not None else None)
    avg_total_away = (_avg_total_from_window(all_away.window(ref, totals_tendency_n))
                      if all_away is not None else None)

    streak_home = _streak_from_group(all_home, home_n, norm, ref)
    streak_away = _streak_from_group(all_away, away_n, norm, ref)

    avg_scored_home = (_avg_scored_from_window(all_home.window(ref, off_def_n), home_n, norm)
                       if all_home is not None else None)
    avg_conceded_home = (_avg_conceded_from_window(all_home.window(ref, off_def_n), home_n, norm)
                         if all_home is not None else None)
    avg_scored_away = (_avg_scored_from_window(all_away.window(ref, off_def_n), away_n, norm)
                       if all_away is not None else None)
    avg_conceded_away = (_avg_conceded_from_window(all_away.window(ref, off_def_n), away_n, norm)
                         if all_away is not None else None)

    # `_home_win_rate_from_window`/`_away_win_rate_from_window`, NO
    # `_win_rate_from_window`: team_recent_form_home/_away usan una expresion
    # de empate/NaN distinta de team_recent_form/team_h2h_form (ver el
    # docstring de `_win_rate_from_window`). Usar la generica aqui daba 0.5
    # para un marcador NaN en vez del 0.0 original (bug de la revision de
    # Fable, 2026-09-30).
    home_only = idx.home.get(home_n)
    away_only = idx.away.get(away_n)
    form_home_at_home = (_home_win_rate_from_window(home_only.window(ref, home_away_form_n))
                        if home_only is not None else None)
    form_away_at_away = (_away_win_rate_from_window(away_only.window(ref, home_away_form_n))
                        if away_only is not None else None)

    margin_home = (_avg_margin_from_window(all_home.window(ref, margin_n), home_n, norm)
                  if all_home is not None else None)
    margin_away = (_avg_margin_from_window(all_away.window(ref, margin_n), away_n, norm)
                  if all_away is not None else None)

    return {
        "rest_home": rest_home, "rest_away": rest_away,
        "form_home": form_home, "form_away": form_away,
        "h2h_home": h2h_home,
        "avg_total_home": avg_total_home, "avg_total_away": avg_total_away,
        "streak_home": streak_home, "streak_away": streak_away,
        "avg_scored_home": avg_scored_home, "avg_conceded_home": avg_conceded_home,
        "avg_scored_away": avg_scored_away, "avg_conceded_away": avg_conceded_away,
        "form_home_at_home": form_home_at_home, "form_away_at_away": form_away_at_away,
        "margin_home": margin_home, "margin_away": margin_away,
    }


def team_rest_days(
    team: str,
    results: list[dict],
    reference_date: str,
    normalize: Callable[[str], str] | None = None,
) -> int | None:
    """Days since the team's last game strictly before reference_date (YYYY-MM-DD).

    Returns None when no prior game is found.
    """
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    ref = reference_date[:10]
    last: str | None = None
    for r in results:
        d = str(r.get("date", ""))[:10]
        if d >= ref:
            continue
        if norm(str(r.get("home", ""))) == team_n or norm(str(r.get("away", ""))) == team_n:
            if last is None or d > last:
                last = d
    if last is None:
        return None
    return (date.fromisoformat(ref) - date.fromisoformat(last)).days


def team_recent_form(
    team: str,
    results: list[dict],
    n: int = 5,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Win rate (win=1, draw=0.5, loss=0) over the last n completed games.

    Results must be in chronological order (ascending date).
    Returns None when fewer than 2 games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    # `graded`, no `len(recent)`: una fila con marcador ilegible se saltaba con
    # `continue` pero seguia en el divisor, asi que contaba como DERROTA en vez
    # de excluirse -- con 5 partidos y uno ilegible, un equipo con pleno de
    # victorias salia 0,80 (AUD-LOW-005, 2026-09-06). Las medias de este mismo
    # modulo (`team_avg_margin`, `team_avg_scored`...) ya acumulan en lista y
    # dividen por lo realmente leido; las cuatro tasas de victoria no.
    total, graded = 0.0, 0
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            total += 1.0 if is_home else 0.0
        elif aws > hs:
            total += 0.0 if is_home else 1.0
        else:
            total += 0.5
    # Mismo umbral que arriba: un partido que no se puede graduar no es un
    # partido disponible.
    return total / graded if graded >= 2 else None


def rest_form_p_adjustment(
    p_model: float,
    market: str,
    selection: str,
    home: str,
    away: str,
    rest_home: int | None,
    rest_away: int | None,
    form_home: float | None,
    form_away: float | None,
    rest_days_coef: float,
    recent_form_coef: float,
) -> float:
    """Return an additive adjustment to p_model for (market, selection).

    Only adjusts h2h and spreads where the selection is a team name.
    Totals ("Over"/"Under") and three-way draws return 0.
    The result is NOT clamped here; callers clip to [0.01, 0.99].
    """
    if rest_days_coef == 0.0 and recent_form_coef == 0.0:
        return 0.0
    if market == "totals":
        return 0.0
    if selection == home:
        sign = 1.0
    elif selection == away:
        sign = -1.0
    else:
        return 0.0  # Draw or unknown
    adj = 0.0
    if rest_days_coef != 0.0 and rest_home is not None and rest_away is not None:
        adj += sign * (rest_home - rest_away) * rest_days_coef
    if recent_form_coef != 0.0 and form_home is not None and form_away is not None:
        adj += sign * (form_home - form_away) * recent_form_coef
    return adj


def team_h2h_form(
    team_a: str,
    team_b: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Win rate of team_a vs team_b in their last n direct matchups.

    win=1, draw=0.5, loss=0. Returns None when fewer than 2 matchups found.
    Results must be in chronological order (ascending date).
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    a = norm(team_a)
    b = norm(team_b)
    matchups = [
        r for r in results
        if (norm(str(r.get("home", ""))) == a and norm(str(r.get("away", ""))) == b)
        or (norm(str(r.get("home", ""))) == b and norm(str(r.get("away", ""))) == a)
    ]
    recent = matchups[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0     # divisor = filas realmente leidas (AUD-LOW-005)
    for r in recent:
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        home_is_a = norm(str(r.get("home", ""))) == a
        if hs > aws:
            total += 1.0 if home_is_a else 0.0
        elif aws > hs:
            total += 0.0 if home_is_a else 1.0
        else:
            total += 0.5
    return total / graded if graded >= 2 else None


def team_recent_form_home(
    team: str,
    results: list[dict],
    n: int = 5,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Win rate (win=1, draw=0.5, loss=0) in the team's last n HOME games only.

    Returns None when fewer than 2 home games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    home_games = [r for r in results if norm(str(r.get("home", ""))) == team_n]
    recent = home_games[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0     # divisor = filas realmente leidas (AUD-LOW-005)
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def team_recent_form_away(
    team: str,
    results: list[dict],
    n: int = 5,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Win rate (win=1, draw=0.5, loss=0) in the team's last n AWAY games only.

    Returns None when fewer than 2 away games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    away_games = [r for r in results if norm(str(r.get("away", ""))) == team_n]
    recent = away_games[-n:]
    if len(recent) < 2:
        return None
    total, graded = 0.0, 0     # divisor = filas realmente leidas (AUD-LOW-005)
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        graded += 1
        total += 1.0 if aws > hs else (0.5 if hs == aws else 0.0)
    return total / graded if graded >= 2 else None


def home_away_form_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    form_home_at_home: float | None,
    form_away_at_away: float | None,
    home_away_form_coef: float,
) -> float:
    """Additive adjustment based on role-specific recent form.

    adj = sign * (form_home_at_home - form_away_at_away) * coef.
    Home selection gets sign=+1, away gets -1. Totals and draws return 0.
    Returns 0 when either form value is None or coef is 0.
    """
    if home_away_form_coef == 0.0 or market == "totals":
        return 0.0
    if form_home_at_home is None or form_away_at_away is None:
        return 0.0
    diff = form_home_at_home - form_away_at_away
    if selection == home:
        return diff * home_away_form_coef
    if selection == away:
        return -diff * home_away_form_coef
    return 0.0


def team_avg_margin(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Average scoring margin (scored - conceded) in the team's last n games.

    Positive = team wins on average; negative = loses on average.
    Captures dominance that win rate misses (winning by 1 vs winning by 10).
    Returns None when fewer than 2 games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    margins = []
    for r in recent:
        try:
            hs, aws = float(r["home_score"]), float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        is_home = norm(str(r.get("home", ""))) == team_n
        margins.append(hs - aws if is_home else aws - hs)
    return sum(margins) / len(margins) if margins else None


def margin_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    margin_home: float | None,
    margin_away: float | None,
    margin_coef: float,
) -> float:
    """Additive adjustment based on average scoring margin differential.

    adj = sign * (margin_home - margin_away) * margin_coef.
    Home selection gets sign=+1, away gets -1.
    Only h2h and spreads; totals and draws return 0.
    margin_coef defaults to 0 (no-op); activate only after OOS validation.
    """
    if margin_coef == 0.0 or market == "totals":
        return 0.0
    if margin_home is None or margin_away is None:
        return 0.0
    diff = margin_home - margin_away
    if selection == home:
        return diff * margin_coef
    if selection == away:
        return -diff * margin_coef
    return 0.0


def team_avg_scored(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Average goals/runs scored per game in the team's last n games.

    Returns None when fewer than 2 games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    scored = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            scored.append(float(r["home_score"]) if is_home else float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(scored) / len(scored) if scored else None


def team_avg_conceded(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Average goals/runs conceded per game in the team's last n games.

    Returns None when fewer than 2 games are available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    conceded = []
    for r in recent:
        try:
            is_home = norm(str(r.get("home", ""))) == team_n
            conceded.append(float(r["away_score"]) if is_home else float(r["home_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(conceded) / len(conceded) if conceded else None


def off_def_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    avg_scored_home: float | None,
    avg_conceded_home: float | None,
    avg_scored_away: float | None,
    avg_conceded_away: float | None,
    point: float | None,
    off_def_h2h_coef: float,
    off_def_totals_coef: float,
) -> float:
    """Additive adjustment based on offensive and defensive strength.

    Totals: expected_total = (scored_home + conceded_away + scored_away + conceded_home) / 2
            adj = (expected_total - point) * off_def_totals_coef
            Over gets +adj, Under gets -adj.

    H2H/spreads: expected_margin = (scored_home + conceded_away - scored_away - conceded_home) / 2
                 adj = sign * expected_margin * off_def_h2h_coef
                 Home selection gets sign=+1, away gets -1.

    Returns 0 when any required input is None or both coefs are 0.
    """
    have_all = all(x is not None for x in
                   [avg_scored_home, avg_conceded_home, avg_scored_away, avg_conceded_away])
    if market == "totals" and off_def_totals_coef != 0.0 and have_all and point is not None:
        expected_total = (avg_scored_home + avg_conceded_away  # type: ignore[operator]
                          + avg_scored_away + avg_conceded_home) / 2.0  # type: ignore[operator]
        adj = (expected_total - point) * off_def_totals_coef
        if selection == "Over":
            return adj
        if selection == "Under":
            return -adj
        return 0.0
    if market in ("h2h", "spreads") and off_def_h2h_coef != 0.0 and have_all:
        expected_margin = (avg_scored_home + avg_conceded_away  # type: ignore[operator]
                           - avg_scored_away - avg_conceded_home) / 2.0  # type: ignore[operator]
        if selection == home:
            return expected_margin * off_def_h2h_coef
        if selection == away:
            return -expected_margin * off_def_h2h_coef
    return 0.0


def team_over_rate(
    team: str,
    results: list[dict],
    reference_line: float | None,
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Fraction of the team's last n games where (home_score + away_score) > reference_line.

    Uses the current game's totals line as the reference so the signal is
    calibrated to the actual bet being evaluated. Returns None when
    reference_line is None or fewer than 2 games are available.
    """
    results = _hasta(results, reference_date)
    if reference_line is None:
        return None
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    overs = []
    for r in recent:
        try:
            overs.append(1.0 if float(r["home_score"]) + float(r["away_score"]) > reference_line
                         else 0.0)
        except (KeyError, TypeError, ValueError):
            continue
    return sum(overs) / len(overs) if overs else None


def over_under_rate_p_adjustment(
    market: str,
    selection: str,
    over_rate_home: float | None,
    over_rate_away: float | None,
    over_under_rate_coef: float,
) -> float:
    """Additive adjustment for totals based on historical Over rate vs the line.

    combined = (over_rate_home + over_rate_away) / 2; centered at 0.5.
    adj = (combined - 0.5) * coef.
    Over gets +adj, Under gets -adj. Returns 0 for h2h/spreads or missing data.
    coef defaults to 0 (no-op); activate only after OOS validation.
    """
    if over_under_rate_coef == 0.0 or market != "totals":
        return 0.0
    if over_rate_home is None or over_rate_away is None:
        return 0.0
    combined = (over_rate_home + over_rate_away) / 2.0
    adj = (combined - 0.5) * over_under_rate_coef
    if selection == "Over":
        return adj
    if selection == "Under":
        return -adj
    return 0.0


def team_streak(
    team: str,
    results: list[dict],
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> int:
    """Current consecutive win (+) or loss (-) streak for the team.

    Iterates from the most recent game backward. A draw or a missing score
    resets to 0 and stops. Returns 0 when no games are available.
    e.g. W W W → +3; L L → -2; W L W → +1 (only the last win counts).
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    streak = 0
    for r in reversed(team_games):
        try:
            hs = float(r["home_score"])
            aws = float(r["away_score"])
        except (KeyError, TypeError, ValueError):
            break
        is_home = norm(str(r.get("home", ""))) == team_n
        if hs > aws:
            outcome = 1 if is_home else -1
        elif aws > hs:
            outcome = -1 if is_home else 1
        else:
            break  # draw breaks streak
        if streak == 0:
            streak = outcome
        elif (outcome > 0) == (streak > 0):
            streak += outcome
        else:
            break
    return streak


def streak_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    streak_home: int,
    streak_away: int,
    streak_coef: float,
) -> float:
    """Additive adjustment for h2h and spreads based on win/loss streak differential.

    adj = sign * (streak_home - streak_away) * streak_coef.
    Home selection gets sign=+1, away gets -1. Totals and draws return 0.
    streak_coef defaults to 0 (no-op); activate only after OOS validation.
    """
    if streak_coef == 0.0 or market == "totals":
        return 0.0
    if selection == home:
        sign = 1.0
    elif selection == away:
        sign = -1.0
    else:
        return 0.0
    return sign * (streak_home - streak_away) * streak_coef


def team_avg_total(
    team: str,
    results: list[dict],
    n: int = 10,
    normalize: Callable[[str], str] | None = None,
    reference_date: str | None = None,
) -> float | None:
    """Average total score (home_score + away_score) per game in the team's last n games.

    Captures scoring environment tendency: high-scoring teams inflate totals,
    low-scoring ones deflate them. Returns None when fewer than 2 games available.
    """
    results = _hasta(results, reference_date)
    norm = normalize or (lambda x: x)
    team_n = norm(team)
    team_games = [
        r for r in results
        if norm(str(r.get("home", ""))) == team_n
        or norm(str(r.get("away", ""))) == team_n
    ]
    recent = team_games[-n:]
    if len(recent) < 2:
        return None
    totals_list = []
    for r in recent:
        try:
            totals_list.append(float(r["home_score"]) + float(r["away_score"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sum(totals_list) / len(totals_list) if totals_list else None


def totals_tendency_p_adjustment(
    market: str,
    selection: str,
    avg_total_home: float | None,
    avg_total_away: float | None,
    point: float | None,
    totals_tendency_coef: float,
) -> float:
    """Additive adjustment to p_model for totals markets based on team scoring tendency.

    combined_avg = mean of both teams' avg total per game.
    adj = (combined_avg - point) * coef.
    Over gets +adj (teams tend to score more than the line → favor Over).
    Under gets -adj. Returns 0 for h2h/spreads, or when any input is missing.
    coef defaults to 0 (no-op); activate only with OOS evidence.
    """
    if totals_tendency_coef == 0.0 or market != "totals":
        return 0.0
    if avg_total_home is None or avg_total_away is None or point is None:
        return 0.0
    combined_avg = (avg_total_home + avg_total_away) / 2.0
    adj = (combined_avg - point) * totals_tendency_coef
    if selection == "Over":
        return adj
    if selection == "Under":
        return -adj
    return 0.0


def h2h_p_adjustment(
    market: str,
    selection: str,
    home: str,
    away: str,
    h2h_home: float | None,
    h2h_coef: float,
) -> float:
    """Additive h2h adjustment to p_model for h2h markets only.

    h2h_home is the home team's win rate in past direct matchups vs the away
    team (from team_h2h_form). Centered at 0.5 (equal record):
      adj = sign * (h2h_home - 0.5) * h2h_coef
    Returns 0 for spreads, totals, draws, or when h2h_home is None / coef is 0.
    """
    if h2h_home is None or h2h_coef == 0.0 or market != "h2h":
        return 0.0
    if selection == home:
        return (h2h_home - 0.5) * h2h_coef
    if selection == away:
        return -(h2h_home - 0.5) * h2h_coef
    return 0.0
