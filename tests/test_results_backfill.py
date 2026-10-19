"""Historical results backfill: store dedup/ordering, ESPN parsing, pipeline merge."""
from sqp.pipeline.daily import _merge_results
from sqp.providers.espn_results import parse_scoreboard
from sqp.storage.results_store import ResultsStore


def _row(date: str, home: str = "A", away: str = "B", hs: int = 3, as_: int = 1) -> dict:
    return {"date": date, "home": home, "away": away, "home_score": hs, "away_score": as_}


def test_store_upsert_dedup_and_order(tmp_path):
    store = ResultsStore(tmp_path)
    added = store.upsert("nba", [_row("2026-02-01"), _row("2026-01-01"), _row("2026-02-01")])
    assert added == 2  # in-batch duplicate dropped
    assert store.upsert("nba", [_row("2026-01-01"), _row("2026-03-01")]) == 1
    loaded = store.load("nba")
    assert [r["date"] for r in loaded] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert all(r["neutral"] is False or r["neutral"] == False for r in loaded)  # noqa: E712


def test_store_existing_rows_win(tmp_path):
    store = ResultsStore(tmp_path)
    store.upsert("nhl", [_row("2026-01-01", hs=5, as_=0)])
    store.upsert("nhl", [_row("2026-01-01", hs=9, as_=9)])  # re-ingest must not mutate
    assert store.load("nhl")[0]["home_score"] == 5


def test_store_load_missing_league(tmp_path):
    assert ResultsStore(tmp_path).load("ligamx") == []


def test_parse_scoreboard_completed_only():
    payload = {"events": [
        {"date": "2026-05-10T01:00Z",
         "competitions": [{"status": {"type": {"completed": True}}, "neutralSite": True,
                           "competitors": [
                               {"homeAway": "home", "score": "2", "team": {"displayName": "Club America"}},
                               {"homeAway": "away", "score": "1", "team": {"displayName": "Toluca"}}]}]},
        {"date": "2026-05-11T01:00Z",
         "competitions": [{"status": {"type": {"completed": False}},
                           "competitors": [
                               {"homeAway": "home", "score": "0", "team": {"displayName": "X"}},
                               {"homeAway": "away", "score": "0", "team": {"displayName": "Y"}}]}]},
    ]}
    parsed = parse_scoreboard(payload)
    assert parsed == [{"date": "2026-05-10", "home": "Club America", "away": "Toluca",
                       "home_score": 2, "away_score": 1, "neutral": True, "game_id": ""}]


def test_espn_offseason_404_chunk_is_empty_not_fatal():
    from sqp.providers.espn_results import ESPNResultsProvider

    class _NotFound:
        status_code = 404

        def raise_for_status(self):
            raise AssertionError("must not be called on 404")

        def json(self):
            return {}

    class _Session:
        def get(self, url, params=None, timeout=None):
            return _NotFound()

    provider = ESPNResultsProvider(session=_Session())
    assert provider.fetch_results("ncaab", days_back=40) == []


def test_store_keeps_doubleheaders_distinct(tmp_path):
    store = ResultsStore(tmp_path)
    game1 = dict(_row("2026-06-19", hs=1, as_=0), game_id="745001")
    game2 = dict(_row("2026-06-19", hs=2, as_=7), game_id="745002")
    assert store.upsert("mlb", [game1, game2]) == 2
    assert store.upsert("mlb", [game1]) == 0  # same game re-ingested: no-op
    assert len(store.load("mlb")) == 2


def test_store_legacy_csv_without_game_id_migrates(tmp_path):
    store = ResultsStore(tmp_path)
    p = store.path("nhl")
    p.parent.mkdir(parents=True)
    p.write_text("date,home,away,home_score,away_score,neutral,ingested_at\n"
                 "2026-01-01,A,B,3,1,False,x\n", encoding="utf-8")
    assert store.upsert("nhl", [dict(_row("2026-02-01"), game_id="9")]) == 1
    loaded = store.load("nhl")
    assert len(loaded) == 2
    assert loaded[0]["game_id"] == ""  # legacy row preserved with empty id


def test_upsert_legacy_row_blocks_same_game_with_real_id(tmp_path):
    # M-22 (auditoria 2026-07-24): una fila legacy (game_id "") ya cubre ese
    # (date, home, away); re-ingerir el mismo juego con game_id real no debe
    # duplicarlo dentro del store.
    store = ResultsStore(tmp_path)
    legacy = dict(_row("2026-02-01"))
    legacy.pop("game_id", None)
    assert store.upsert("nhl", [legacy]) == 1          # migra a game_id ""
    assert store.upsert("nhl", [dict(_row("2026-02-01"), game_id="401999")]) == 0
    assert len(store.load("nhl")) == 1


def test_merge_results_tolerates_utc_date_drift():
    # Auditoria 2026-07-24 (I-3): la fila reciente data por commence_time (fecha
    # UTC); un juego nocturno de costa oeste cae en el dia UTC siguiente y sin
    # tolerancia +-1 el mismo juego entraria dos veces al fit de ratings.
    history = [dict(_row("2026-06-19", hs=1), game_id="745001")]
    recent = [dict(_row("2026-06-20T02:05:00Z", hs=1), game_id="odds-abc")]
    assert len(_merge_results(history, recent)) == 1


def test_merge_results_keeps_doubleheaders_history_wins_per_day():
    history = [dict(_row("2026-06-19", hs=1), game_id="745001"),
               dict(_row("2026-06-19", hs=2), game_id="745002")]
    recent = [dict(_row("2026-06-19T23:00:00Z", hs=9), game_id="odds-abc"),  # same day+pair
              dict(_row("2026-06-20", "C", "D"), game_id="odds-xyz")]
    merged = _merge_results(history, recent)
    assert len(merged) == 3  # both doubleheader games kept; recent duplicate dropped
    assert sorted(m["home_score"] for m in merged if m["date"].startswith("2026-06-19")) == [1, 2]


def test_mlb_postponed_finals_are_excluded():
    from sqp.providers.mlb_statsapi import MLBStatsProvider

    payload = {"dates": [{"date": "2026-06-06", "games": [
        {"status": {"abstractGameState": "Final", "detailedState": "Final"},
         "teams": {"home": {"team": {"name": "A"}, "score": 5},
                   "away": {"team": {"name": "B"}, "score": 3}}},
        {"status": {"abstractGameState": "Final", "detailedState": "Postponed"},
         "teams": {"home": {"team": {"name": "C"}},
                   "away": {"team": {"name": "D"}}}},
    ]}]}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class _Session:
        def get(self, url, params=None, timeout=None):
            return _Resp()

    results = MLBStatsProvider(session=_Session()).fetch_results("mlb")
    assert len(results) == 1
    assert results[0]["home"] == "A" and results[0]["home_score"] == 5


def test_merge_results_history_wins_and_sorted():
    history = [_row("2026-06-10", hs=100, as_=90)]
    recent = [_row("2026-06-10T02:30:00Z", hs=0, as_=0),  # same game, full timestamp
              _row("2026-06-09", "C", "D")]
    merged = _merge_results(history, recent)
    assert [m["home_score"] for m in merged] == [3, 100]  # sorted by day; history kept
    assert len(merged) == 2

# AUD-009 (ronda audit-2026-10-15): con el historico retrasado, el ±1 dia ciego
# descartaba un partido REAL del dia siguiente de una serie. Con hora, la fila
# reciente solo se descarta si el historico cubre una fecha local POSIBLE de
# ese instante (husos UTC-12..UTC+14).
def test_merge_results_keeps_next_day_series_game_when_history_lags():
    history = [dict(_row("2026-06-10", hs=1), game_id="745001")]
    recent = [dict(_row("2026-06-11T23:05:00Z", hs=7), game_id="odds-jun11")]
    merged = _merge_results(history, recent)
    assert [m["game_id"] for m in merged] == ["745001", "odds-jun11"]


def test_merge_results_still_drops_the_shifted_west_coast_game():
    history = [dict(_row("2026-06-10", hs=1), game_id="745001")]
    recent = [dict(_row("2026-06-11T02:10:00Z", hs=1), game_id="odds-jun10")]
    assert [m["game_id"] for m in _merge_results(history, recent)] == ["745001"]


def test_merge_results_without_time_keeps_the_conservative_window():
    """Sin hora no hay forma de distinguir los dos casos: se conserva el ±1."""
    history = [dict(_row("2026-06-10", hs=1), game_id="745001")]
    recent = [dict(_row("2026-06-11", hs=7), game_id="odds-jun11")]
    assert len(_merge_results(history, recent)) == 1


# --- AUD-003 (ronda audit-2026-10-18): un game_id, un partido ------------------

def _gid(date: str, home: str, away: str, gid: str, hs: int = 3, as_: int = 1) -> dict:
    return {**_row(date, home, away, hs, as_), "game_id": gid}


def test_aud003_resumed_game_is_read_once_on_its_final_date(tmp_path):
    """MLB suspendido y reanudado: mismo gamePk Final en dos fechas. La fila de
    la reanudacion se guarda (el CSV es append-only) y se LEE una sola vez, en
    la fecha del final: con la de la suspension el marcador entraba en el ajuste
    antes de existir (revision Fable 2026-10-18)."""
    store = ResultsStore(tmp_path)
    assert store.upsert("mlb", [_gid("2023-09-28", "NYM", "MIA", "716404", 1, 0)]) == 1
    assert store.upsert("mlb", [_gid("2023-10-02", "NYM", "MIA", "716404", 1, 0)]) == 1
    assert [r["date"] for r in store.load("mlb")] == ["2023-10-02"]
    # re-ingerir la fecha antigua no vuelve a crecer
    assert store.upsert("mlb", [_gid("2023-09-28", "NYM", "MIA2", "716404", 1, 0)]) == 0


def test_aud003_renamed_team_with_same_game_id_does_not_grow_the_store(tmp_path):
    """ESPN renombra un equipo y el backfill vuelve a bajar el mismo partido."""
    store = ResultsStore(tmp_path)
    store.upsert("ncaab", [_gid("2025-11-10", "TCU", "Saint Francis Red Flash", "401812250")])
    assert store.upsert("ncaab", [_gid("2025-11-10", "TCU", "Red Wolves", "401812250")]) == 0
    loaded = store.load("ncaab")
    assert len(loaded) == 1 and loaded[0]["away"] == "Saint Francis Red Flash"


def test_aud003_in_batch_repeated_game_id_keeps_one_row(tmp_path):
    store = ResultsStore(tmp_path)
    assert store.upsert("wncaab", [_gid("2025-11-10", "A", "B", "9"),
                                   _gid("2025-11-10", "A", "B2", "9")]) == 1


def test_aud003_load_drops_repeated_game_ids_already_in_the_csv(tmp_path):
    """Las filas ya guardadas no se reparan en disco (datos crudos), pero el
    ajuste de ratings las lee una sola vez: gana la ULTIMA por (date,
    ingested_at)."""
    import pandas as pd

    store = ResultsStore(tmp_path)
    store.dir.mkdir(parents=True)
    pd.DataFrame([
        {"date": "2023-10-02", "home": "NYM", "away": "MIA", "game_id": "716404",
         "home_score": 1, "away_score": 0, "neutral": False, "ingested_at": "x"},
        {"date": "2023-09-28", "home": "NYM", "away": "MIA", "game_id": "716404",
         "home_score": 1, "away_score": 0, "neutral": False, "ingested_at": "x"},
        {"date": "2023-09-29", "home": "A", "away": "B", "game_id": "",
         "home_score": 2, "away_score": 1, "neutral": False, "ingested_at": "x"},
        {"date": "2023-09-29", "home": "C", "away": "D", "game_id": "",
         "home_score": 2, "away_score": 1, "neutral": False, "ingested_at": "x"},
    ]).to_csv(store.path("mlb"), index=False)
    loaded = store.load("mlb")
    assert [(r["date"], r["game_id"]) for r in loaded] == [
        ("2023-09-29", ""), ("2023-09-29", ""), ("2023-10-02", "716404")]


def test_aud003_same_day_rename_keeps_the_latest_ingestion_on_read(tmp_path):
    import pandas as pd

    store = ResultsStore(tmp_path)
    store.dir.mkdir(parents=True)
    pd.DataFrame([
        {"date": "2025-11-10", "home": "TCU", "away": "Red Wolves", "game_id": "401812250",
         "home_score": 70, "away_score": 60, "neutral": False,
         "ingested_at": "2026-06-21T00:00:00+00:00"},
        {"date": "2025-11-10", "home": "TCU", "away": "Saint Francis Red Flash",
         "game_id": "401812250", "home_score": 70, "away_score": 60, "neutral": False,
         "ingested_at": "2026-06-13T00:00:00+00:00"},
    ]).to_csv(store.path("ncaab"), index=False)
    loaded = store.load("ncaab")
    assert len(loaded) == 1 and loaded[0]["away"] == "Red Wolves"


def test_aud003_doubleheaders_with_distinct_game_ids_still_both_kept(tmp_path):
    store = ResultsStore(tmp_path)
    assert store.upsert("mlb", [_gid("2026-06-06", "A", "B", "1"),
                                _gid("2026-06-06", "A", "B", "2")]) == 2
    assert len(store.load("mlb")) == 2


def test_aud003_mlb_resumed_game_is_returned_once_on_its_last_date():
    from sqp.providers.mlb_statsapi import MLBStatsProvider

    def _g(pk):
        return {"gamePk": pk, "status": {"abstractGameState": "Final", "detailedState": "Final"},
                "teams": {"home": {"team": {"name": "NYM"}, "score": 1},
                          "away": {"team": {"name": "MIA"}, "score": 0}}}

    payload = {"dates": [{"date": "2023-09-28", "games": [_g(716404)]},
                         {"date": "2023-10-02", "games": [_g(716404), _g(716500)]}]}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class _Session:
        def get(self, url, params=None, timeout=None):
            return _Resp()

    results = MLBStatsProvider(session=_Session()).fetch_results("mlb")
    assert sorted((r["game_id"], r["date"]) for r in results) == [
        ("716404", "2023-10-02"), ("716500", "2023-10-02")]
