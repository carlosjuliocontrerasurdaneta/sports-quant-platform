"""Regression: _persist_settled must reconcile columns across schema versions.

A settled_*.csv written by an older BetCandidate schema (before
calibrated_probability existed) must not misalign when newer rows -- which carry
the extra column -- are persisted. The old failure was a blind mode='a' append
that wrote the new column order under the old header (audit 2026-06, I-1)."""

from pathlib import Path

import pandas as pd
import pytest

import sqp.settlement.runner as runner


def _persist(tmp_path, df):
    return runner._persist_settled("nfl", df)


def test_persist_reconciles_added_column_without_misalignment(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    out = tmp_path / "data" / "bets" / "settled_nfl.csv"
    out.parent.mkdir(parents=True)
    # Prior file from the OLD schema: no calibrated_probability column.
    out.write_text(
        "event_id,market,selection,line,price_decimal,stake,model_probability,"
        "flags,generated_at,result,pnl,settled_at\n"
        "e1,h2h,A,,1.9,10.0,0.55,,2026-06-01T00:00:00+00:00,win,9.0,"
        "2026-06-01T03:00:00+00:00\n",
        encoding="utf-8")

    # New row from the CURRENT schema: calibrated_probability sits between
    # model_probability and flags.
    new = pd.DataFrame([{
        "event_id": "e2", "market": "h2h", "selection": "B", "line": float("nan"),
        "price_decimal": 2.1, "stake": 12.0, "model_probability": 0.48,
        "calibrated_probability": 0.50, "flags": "",
        "generated_at": "2026-06-02T00:00:00+00:00", "result": "loss",
        "pnl": -12.0, "settled_at": "2026-06-02T03:00:00+00:00"}])

    _persist(tmp_path, new)
    back = pd.read_csv(out)

    # Both rows present, union of columns, no shift.
    assert "calibrated_probability" in back.columns
    r1 = back[back.event_id == "e1"].iloc[0]
    r2 = back[back.event_id == "e2"].iloc[0]
    # Old row's values stay under their own columns (not shifted by the new field).
    assert r1["result"] == "win" and float(r1["pnl"]) == 9.0
    assert float(r1["price_decimal"]) == 1.9
    assert pd.isna(r1["calibrated_probability"])      # absent in the old schema
    # New row keeps its calibrated probability and grade.
    assert r2["result"] == "loss" and float(r2["calibrated_probability"]) == 0.50


def test_persist_write_failure_leaves_prior_file_intact(tmp_path, monkeypatch):
    """Crash-safety: settled_*.csv es fuente unica de la auditoria de ROI, el
    ledger de banca y el entrenamiento de calibradores. Un fallo a mitad de
    escritura no debe truncar el archivo previo: se escribe a un temporal y se
    reemplaza atomicamente (os.replace)."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    row = {"event_id": "e1", "market": "h2h", "selection": "A",
           "price_decimal": 1.9, "stake": 10.0,
           "generated_at": "2026-06-01T00:00:00+00:00", "result": "win",
           "pnl": 9.0, "settled_at": "2026-06-01T03:00:00+00:00"}
    _persist(tmp_path, pd.DataFrame([row]))          # seed the prior file
    out = tmp_path / "data" / "bets" / "settled_nfl.csv"
    original = out.read_text(encoding="utf-8")

    def exploding_to_csv(self, path_or_buf, *args, **kwargs):
        Path(path_or_buf).write_text("PARTIAL", encoding="utf-8")
        raise OSError("disk full mid-write")

    monkeypatch.setattr(pd.DataFrame, "to_csv", exploding_to_csv)
    with pytest.raises(OSError):
        runner._persist_settled("nfl", pd.DataFrame([{**row, "event_id": "e2"}]))

    assert out.read_text(encoding="utf-8") == original   # prior file untouched
    assert not list(out.parent.glob("*.tmp"))            # no stray temp files


def test_persist_is_idempotent_on_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    row = {"event_id": "e9", "market": "totals", "selection": "Over", "line": 7.5,
           "price_decimal": 1.95, "stake": 5.0,
           "generated_at": "2026-06-03T00:00:00+00:00", "result": "win",
           "pnl": 4.75, "settled_at": "2026-06-03T03:00:00+00:00"}
    df = pd.DataFrame([row])
    first = _persist(tmp_path, df.copy())
    second = _persist(tmp_path, df.copy())
    assert len(first) == 1 and second.empty          # already settled -> deduped
    back = pd.read_csv(tmp_path / "data" / "bets" / "settled_nfl.csv")
    assert len(back) == 1                             # not double-written


class TestLaTransaccionCorreBajoLock:
    """AUD-20260906-02 (Codex, HIGH, REPRODUCED).

    `_persist_settled` hacia lectura, dedup, combinacion y reemplazo SIN lock. El
    temporal unico y `os.replace` protegen contra un fichero a medio escribir,
    pero no contra que un escritor sustituya el resultado COMPLETO de otro: es un
    read-modify-write.

    Reproducido antes de arreglarlo con un intercalado determinista -- A lee y
    prepara, B liquida entero, A escribe --: de dos liquidaciones de -400
    sobrevivio SOLO una y el saldo daba 600 en vez de 200. Movimientos del ledger
    perdidos, con la banca, el ROI y las etiquetas de calibracion detras.
    """

    @staticmethod
    def _fila(eid, pnl=-400.0):
        return {"event_id": eid, "market": "h2h", "selection": "A", "line": "nan",
                "generated_at": "2026-09-06T00:00:00Z", "pnl": pnl, "result": "loss",
                "stake": 400, "data_label": "real",
                "settled_at": "2026-09-06T00:00:00+00:00"}

    def _lock(self, tmp_path):
        return tmp_path / "data" / "bets" / "settled_nfl.csv.lock"

    def test_la_escritura_ocurre_dentro_de_la_seccion_critica(self, tmp_path, monkeypatch):
        """La propiedad que cierra el hallazgo. Un test que solo comprobara el
        resultado final pasaria igual SIN lock cuando no hay concurrencia: hay
        que comprobar que el lock esta TOMADO en el momento de escribir."""
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        visto = {}
        real = runner._atomic_write_csv

        def espia(df, path):
            visto["tomado"] = self._lock(tmp_path).exists()
            real(df, path)

        monkeypatch.setattr(runner, "_atomic_write_csv", espia)
        _persist(tmp_path, pd.DataFrame([self._fila("e1")]))
        assert visto["tomado"] is True, "se escribio FUERA del lock"

    def test_el_lock_se_libera_al_salir(self, tmp_path, monkeypatch):
        """Sin esto, la primera liquidacion del dia dejaria el fichero bloqueado
        para todas las demas hasta que venciera `LOCK_STALE_S`."""
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        _persist(tmp_path, pd.DataFrame([self._fila("e1")]))
        assert not self._lock(tmp_path).exists()

    def test_tambien_con_el_fichero_inicialmente_ausente(self, tmp_path, monkeypatch):
        """Codex pidio cubrir las dos ramas: `prior is None` y `prior` existente.
        La rama sin fichero previo escribe por otra linea."""
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        assert not (tmp_path / "data" / "bets" / "settled_nfl.csv").exists()
        visto = {}
        real = runner._atomic_write_csv
        monkeypatch.setattr(runner, "_atomic_write_csv",
                            lambda df, path: (visto.__setitem__("tomado", self._lock(tmp_path).exists()),
                                              real(df, path))[1])
        _persist(tmp_path, pd.DataFrame([self._fila("e1")]))
        assert visto["tomado"] is True

    def test_dos_liquidaciones_secuenciales_se_unen(self, tmp_path, monkeypatch):
        """Lo que el defecto destruia: filas distintas deben sobrevivir las dos."""
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        _persist(tmp_path, pd.DataFrame([self._fila("evA")]))
        _persist(tmp_path, pd.DataFrame([self._fila("evB")]))
        df = pd.read_csv(tmp_path / "data" / "bets" / "settled_nfl.csv")
        assert sorted(df["event_id"]) == ["evA", "evB"]
        assert df["pnl"].sum() == -800.0

    def test_una_fila_repetida_sigue_apareciendo_una_sola_vez(self, tmp_path, monkeypatch):
        """El lock no puede haber roto la idempotencia, que es el contrato que ya
        tenia el modulo."""
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        _persist(tmp_path, pd.DataFrame([self._fila("evA")]))
        nuevas = _persist(tmp_path, pd.DataFrame([self._fila("evA")]))
        df = pd.read_csv(tmp_path / "data" / "bets" / "settled_nfl.csv")
        assert len(nuevas) == 0 and len(df) == 1

    def test_un_lock_retenido_aborta_en_vez_de_entrar(self, tmp_path, monkeypatch):
        """La otra mitad del contrato de `locked`: agotar la espera NO entra sin
        exclusion (AUD-002, 2026-09-05). Se inyecta un timeout corto para no
        esperar los 120 s reales."""
        from sqp.exceptions import LockNoAdquiridoError
        from sqp.storage import lock as lock_mod
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        bets = tmp_path / "data" / "bets"
        bets.mkdir(parents=True, exist_ok=True)
        self._lock(tmp_path).touch()          # otro proceso VIVO lo retiene
        monkeypatch.setattr(runner, "locked",
                            lambda p: lock_mod.locked(p, timeout_s=0.5, stale_s=300.0))
        with pytest.raises(LockNoAdquiridoError):
            _persist(tmp_path, pd.DataFrame([self._fila("e1")]))
