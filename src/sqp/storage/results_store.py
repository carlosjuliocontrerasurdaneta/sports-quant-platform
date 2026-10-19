"""Local historical results store: one append-only CSV per league under
data/historical/. Existing rows always win over re-ingested duplicates
(raw data is never mutated), every row carries an ingestion timestamp,
and (date, home, away) is the dedup key.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_csv
from sqp.storage.lock import locked

log = get_logger("sqp.storage.results")


COLUMNS = ["date", "home", "away", "game_id", "home_score", "away_score", "neutral", "ingested_at"]
KEY = ["date", "home", "away", "game_id"]  # game_id keeps doubleheaders distinct


class ResultsStore:
    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self, league: str) -> Path:
        return self.dir / f"results_{league}.csv"

    _LOAD_COLS = ["date", "home", "away", "game_id", "home_score", "away_score", "neutral"]
    # `ingested_at` solo para elegir la fila de un `game_id` repetido (AUD-003).
    _READ_COLS = _LOAD_COLS + ["ingested_at"]

    def load(self, league: str, dedupe_game_id: bool = True) -> list[dict]:
        """Stored results in chronological order, in ResultsProvider dict format.

        ``dedupe_game_id=False`` returns the stored rows as they are, repeated
        ``game_id`` included: only for the frozen research scripts whose
        pre-registered population applies its OWN dedupe rule and checks its
        counts (battery Enmienda 3(c), totals recency)."""
        p = self.path(league)
        if not p.exists():
            return []
        df = pd.read_csv(p, usecols=lambda c: c in self._READ_COLS,
                         dtype={"date": str, "game_id": str})
        df = self._migrate(df).sort_values("date", kind="stable")
        if dedupe_game_id:
            df = self._drop_repeated_game_ids(df, league)
        return df[self._LOAD_COLS].to_dict("records")

    @staticmethod
    def _drop_repeated_game_ids(df: pd.DataFrame, league: str) -> pd.DataFrame:
        """Una fila por `game_id` NO vacio: la ULTIMA por (date, ingested_at).

        Auditoria audit-2026-10-18, AUD-003. La clave del store incluye fecha y
        nombres, asi que el MISMO partido del proveedor entraba dos veces cuando
        cambiaba uno de los dos: un partido MLB suspendido y reanudado (mismo
        `gamePk` Final en dos fechas; 15 filas) o un equipo que ESPN renombro
        y el backfill volvio a bajar (ncaab 31, wncaab 95). El ajuste de ratings
        contaba esos partidos dos veces. El CSV crudo NO se toca (los datos
        crudos no se mutan); se deduplica al leer. `game_id` vacio (esquema
        legacy) no identifica nada y se conserva siempre.

        La ULTIMA, no la primera (revision Fable 2026-10-18): en un partido MLB
        reanudado la primera fecha es la de la SUSPENSION, y quedarse con ella
        metia el marcador final en el ajuste dias antes de que existiera (fuga
        hacia delante); la ultima es la de su final, la misma que elige
        `MLBStatsProvider.fetch_results`. En un renombre de ESPN (misma fecha)
        gana la ingesta mas reciente, con el nombre vigente.
        """
        claves = ["date", "ingested_at"] if "ingested_at" in df.columns else ["date"]
        # Orden estable por (date, ingested_at): ante un empate exacto gana la
        # ultima fila del fichero, que es la ultima escrita.
        ordenado = df.sort_values(claves, kind="stable")
        con_id = ordenado["game_id"] != ""
        fuera = ordenado.index[con_id & ordenado.duplicated(subset=["game_id"], keep="last")]
        repetidos = df.index.isin(fuera)
        n = int(repetidos.sum())
        if n:
            log.warning("[%s] %d fila(s) con game_id repetido descartadas al leer "
                        "(AUD-003: partido reanudado o equipo renombrado)", league, n)
        return df.loc[~repetidos]

    @staticmethod
    def _migrate(df: pd.DataFrame) -> pd.DataFrame:
        if "game_id" not in df.columns:  # legacy schema (pre game_id)
            df["game_id"] = ""
        df["game_id"] = df["game_id"].fillna("").astype(str)
        return df

    def upsert(self, league: str, results: list[dict]) -> int:
        """Add new results; returns how many rows were actually added."""
        if not results:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(results)
        new["date"] = new["date"].astype(str).str[:10]
        if "neutral" not in new.columns:
            new["neutral"] = False
        new["neutral"] = new["neutral"].fillna(False).astype(bool)
        new = self._migrate(new)
        new["ingested_at"] = now
        new = new[COLUMNS].drop_duplicates(subset=KEY, keep="first")
        # Dentro del mismo lote, tambien una fila por `game_id` no vacio (AUD-003).
        new = new.loc[~((new["game_id"] != "") & new.duplicated(subset=["game_id"], keep="first"))]
        p = self.path(league)
        self.dir.mkdir(parents=True, exist_ok=True)
        # Leer, fusionar y escribir BAJO LOCK (AUD-009, ronda audit-2026-09-23):
        # el reemplazo atomico protege el fichero, no la transaccion, y dos
        # backfills solapados perdian en silencio las filas del primero en
        # escribir (reproducido por OpenAI, OPENAI-006). La red queda fuera:
        # quien llama ya trae los resultados descargados.
        with locked(p):
            if p.exists():
                cur = self._migrate(pd.read_csv(p, dtype={"date": str, "game_id": str}))
                # Una fila legacy (game_id == "") ya cubre ese (date, home, away):
                # re-ingerir el mismo juego con game_id real crearia un duplicado
                # dentro del store (auditoria 2026-07-24, M-22). Los doubleheaders
                # genuinos llegan del mismo vendor con ambos game_id no vacios.
                legacy = set(map(tuple, cur.loc[cur["game_id"] == "",
                                                ["date", "home", "away"]]
                                 .itertuples(index=False, name=None)))
                if legacy:
                    new = new[[(dy, h, a) not in legacy for dy, h, a in
                               new[["date", "home", "away"]].itertuples(index=False, name=None)]]
                # AUD-003 (ronda audit-2026-10-18): un `game_id` no vacio que ya
                # esta en el store es el MISMO partido aunque cambien la fecha
                # (MLB reanudado) o un nombre (renombre de ESPN). Con la MISMA
                # fecha o una anterior se descarta y se avisa: la fila existente
                # gana. Con una fecha POSTERIOR (la de reanudacion) se anade, sin
                # tocar la existente: `load` se queda con la ultima, que es la del
                # final real (revision Fable 2026-10-18: la primera fecha metia el
                # marcador en el ajuste antes de que existiera).
                con_id_cur = cur.loc[cur["game_id"] != ""]
                ultima_fecha = con_id_cur.groupby("game_id")["date"].max()
                previa = new["game_id"].map(ultima_fecha)
                repe = (new["game_id"] != "") & previa.notna()
                repe &= ~(new["date"].astype(str) > previa.astype(str))
                repe &= ~new.set_index(KEY).index.isin(cur.set_index(KEY).index)
                if repe.any():
                    log.warning("[%s] %d resultado(s) con un game_id ya guardado bajo otro "
                                "nombre o una fecha no posterior; se conserva la fila "
                                "existente (AUD-003)", league, int(repe.sum()))
                    new = new.loc[~repe]
                merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(subset=KEY, keep="first")
                added = len(merged) - len(cur)
            else:
                merged, added = new, len(new)
            atomic_write_csv(merged.sort_values("date", kind="stable"), p)
        return added
