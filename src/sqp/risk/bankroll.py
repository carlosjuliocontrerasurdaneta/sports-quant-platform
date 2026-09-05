"""Bankroll ledger: the current balance is the configured initial capital plus
all REALIZED bet PnL plus manual adjustments (deposits/withdrawals/corrections).

The single source of truth for bet PnL is ``data/bets/settled_*.csv`` (append-only,
deduped by the settlement runner); we never keep a parallel PnL store that could
drift. Manual, non-bet movements live in ``data/bets/bankroll_adjustments.csv``
(columns: date, amount, kind, note; ``amount`` positive = deposit, negative =
withdrawal/correction).

Demo bets never touch the real bankroll: only settled rows with
``data_label == "real"`` are summed. Used by the live daily run to size Kelly
stakes and the daily-exposure cap on the actual running balance instead of a
fixed nominal figure.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sqp.exceptions import LedgerIntegridadError
from sqp.logging_config import get_logger

log = get_logger("sqp.bankroll")

ADJUSTMENTS_FILE = "bankroll_adjustments.csv"


def _exigir_pnl_legible(f: Path, df: pd.DataFrame) -> None:
    """Un fichero con filas pero sin `pnl` numerico es INDETERMINADO, no cero.

    Cubre la variante SILENCIOSA de AUD-001, encontrada al escribir sus tests y
    peor que el hallazgo original: **pandas 3.0 no lanza `ParserError` cuando
    todas las filas traen un campo de mas**. Reinterpreta la primera columna
    como indice y DESPLAZA el resto, asi que `pnl` pasa a contener lo que habia
    en `data_label`. Reproducido: dos perdidas de -400 sobre banca 1.000 daban
    200; con el desplazamiento, `pnl` valia `['real', 'real']`, `to_numeric`
    los volvia NaN, el `fillna(0.0)` de `realized_pnl` los sumaba como CERO y la
    banca salia **1.000**. Sin excepcion, sin aviso y sin nada roto a la vista.

    Es el mismo modo de fallo que KI-011 (deriva de esquema que desalinea
    columnas), pero aguas arriba: alli desalineaba al ESCRIBIR, aqui al LEER.

    No se exige que TODAS las filas tengan `pnl` numerico -- un push o un void
    legitimo puede traerlo vacio --, solo que al menos una lo tenga. Un fichero
    con filas y ni un solo `pnl` legible no es un fichero sin movimientos: es un
    fichero que no sabemos leer.
    """
    if "pnl" not in df.columns:
        raise LedgerIntegridadError(
            f"{f.name} tiene {len(df)} filas pero ninguna columna 'pnl': el "
            f"esquema no es el esperado y el saldo no es verificable.")
    if pd.to_numeric(df["pnl"], errors="coerce").notna().sum() == 0:
        raise LedgerIntegridadError(
            f"{f.name} tiene {len(df)} filas y ningun 'pnl' numerico "
            f"(leido: {df['pnl'].head(3).tolist()}). Sintoma tipico de columnas "
            f"desplazadas por un campo de mas, que pandas NO senala. El saldo "
            f"no es verificable.")


@dataclass
class BankrollLedger:
    root: Path
    initial: float

    @property
    def _bets_dir(self) -> Path:
        return self.root / "data" / "bets"

    def _settled(self) -> pd.DataFrame:
        """All settled REAL-money rows across leagues (demo excluded).

        Un fichero ILEGIBLE aborta el calculo con `LedgerIntegridadError`. NO se
        omite: omitirlo equipara "no se sabe" con "no aporta nada", y en un
        ledger contable eso no es neutral -- las filas que se dejan de leer son
        casi siempre PERDIDAS, asi que el saldo SUBE.

        Reproducido (auditoria independiente de Codex, 2026-09-05, AUD-001, y
        re-reproducido antes de tocar nada): con un `settled_mlb.csv` de PnL
        -400 sobre banca inicial 1.000, el saldo era 600. Anadiendo una fila con
        un campo de mas -- lo que produce un `ParserError` -- el saldo pasaba a
        **1.000: +400 sin deposito ni ganancia**, un 66,7% de capital
        sobreestimado, sin excepcion ni aviso. Y de ese numero cuelgan el Kelly
        y el cap de exposicion diaria.

        El fichero NO se toca ni se mueve: se nombra en el error para poder
        diagnosticarlo. Vaciar o reparar a ciegas destruiria la evidencia.
        """
        frames: list[pd.DataFrame] = []
        for f in sorted(self._bets_dir.glob("settled_*.csv")):
            try:
                df = pd.read_csv(f)
            except pd.errors.EmptyDataError as exc:
                # Un settled_*.csv sin cabecera siquiera es anomalo: `_persist_settled`
                # siempre escribe cabecera, asi que un frame vacio produce un
                # fichero CON cabecera y 0 filas, que pandas lee sin error. Cero
                # bytes significa truncado, no "liga sin apuestas".
                raise LedgerIntegridadError(
                    f"{f.name} esta vacio o sin cabecera: el saldo no es "
                    f"verificable. No se omite porque las filas ilegibles "
                    f"suelen ser perdidas y omitirlas SUBE la banca.") from exc
            except pd.errors.ParserError as exc:
                raise LedgerIntegridadError(
                    f"{f.name} no es parseable ({exc}): el saldo no es "
                    f"verificable.") from exc
            if not df.empty:
                _exigir_pnl_legible(f, df)
                frames.append(df)
        if not frames:
            return pd.DataFrame(columns=["pnl", "data_label", "result", "stake", "settled_at"])
        out = pd.concat(frames, ignore_index=True)
        if "data_label" in out.columns:
            out = out[out["data_label"].astype(str) == "real"]
        else:
            # Esquema legacy sin data_label: se asume real (los settled demo
            # viven en data/bets/demo/, fuera de este glob). Visible en logs
            # por si algun dia se mezclaran (auditoria 2026-07-24, M-18).
            log.warning("settled_*.csv sin columna data_label: filas asumidas reales")
        return out

    def realized_pnl(self) -> float:
        df = self._settled()
        if df.empty or "pnl" not in df.columns:
            return 0.0
        return float(pd.to_numeric(df["pnl"], errors="coerce").fillna(0.0).sum())

    def adjustments_total(self) -> float:
        """Ajustes manuales (depositos/retiradas). Mismo criterio que `_settled`.

        Ausente SI es cero legitimo -- lo normal es no haber hecho ninguno --,
        pero ilegible NO: una retirada que no se puede leer infla la banca
        exactamente igual que una perdida que no se puede leer.
        """
        path = self._bets_dir / ADJUSTMENTS_FILE
        if not path.exists():
            return 0.0
        try:
            adj = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return 0.0  # existe pero vacio: sin ajustes, que es un cero legitimo
        except pd.errors.ParserError as exc:
            raise LedgerIntegridadError(
                f"{ADJUSTMENTS_FILE} no es parseable ({exc}): el saldo no es "
                f"verificable.") from exc
        if "amount" not in adj.columns:
            return 0.0
        return float(pd.to_numeric(adj["amount"], errors="coerce").fillna(0.0).sum())

    def current_balance(self) -> float:
        return round(self.initial + self.realized_pnl() + self.adjustments_total(), 2)

    def equity_curve(self) -> pd.DataFrame:
        """Running balance by settlement time. Manual adjustments are applied as a
        flat offset (their timing is not modelled in v1; drawdown is unaffected)."""
        df = self._settled()
        if df.empty or "settled_at" not in df.columns or "pnl" not in df.columns:
            return pd.DataFrame(columns=["settled_at", "pnl", "balance"])
        d = df.copy()
        d["pnl"] = pd.to_numeric(d["pnl"], errors="coerce").fillna(0.0)
        # Orden temporal real: settled_at es string y puede mezclar formatos
        # ISO ('+00:00' vs 'Z'); el orden lexicografico no es cronologico
        # (auditoria 2026-07-24, M-18).
        d = (d.assign(_ts=pd.to_datetime(d["settled_at"], errors="coerce", utc=True))
             .sort_values("_ts", kind="stable").drop(columns="_ts"))
        base = self.initial + self.adjustments_total()
        d["balance"] = base + d["pnl"].cumsum()
        return d[["settled_at", "pnl", "balance"]].reset_index(drop=True)

    def _max_drawdown(self) -> float:
        eq = self.equity_curve()
        if eq.empty:
            return 0.0
        # Seed the peak with the OPENING balance, not -inf. The curve's first
        # point is already *after* the first bet, so with -inf that point became
        # the peak and the first loss never counted: 1000 opening with three -100
        # bets reported -200 instead of -300 (audit 2026-08-31, R-B-1).
        # Understating drawdown is the unsafe direction for a risk metric.
        peak = self.initial + self.adjustments_total()
        mdd = 0.0
        for b in eq["balance"]:
            peak = max(peak, b)
            mdd = min(mdd, b - peak)
        return round(mdd, 2)

    def summary(self) -> dict:
        df = self._settled()
        graded = (df[df["result"].isin(["win", "loss"])]
                  if not df.empty and "result" in df.columns else df.iloc[0:0])
        staked = (float(pd.to_numeric(graded["stake"], errors="coerce").fillna(0.0).sum())
                  if not graded.empty and "stake" in graded.columns else 0.0)
        pnl = self.realized_pnl()
        return {
            "initial": round(self.initial, 2),
            "realized_pnl": round(pnl, 2),
            "adjustments": round(self.adjustments_total(), 2),
            "current_balance": self.current_balance(),
            "n_settled": int(len(df)),
            "n_graded": int(len(graded)),
            "total_staked": round(staked, 2),
            "realized_roi": round(pnl / staked, 4) if staked else 0.0,
            "max_drawdown": self._max_drawdown(),
        }


def apply_dynamic_bankroll(settings, root: Path, mode: str | None) -> float:
    """Fija `settings.bankroll` al balance real corriente y lo devuelve.

    Vivia inline en `scripts/run_all.py`. Se extrae aqui porque `run_daily.py
    --mode live` NO lo aplicaba y dimensionaba sobre la cifra nominal estatica:
    con inicial 1000 y balance real 915,75 eso infla TODOS los stakes un 9,2%.
    Con shadow_mode activo era inocuo; desde el 2026-08-16 ya no (KI-016).
    Duplicar las diez lineas en el segundo entrypoint habria repetido la causa
    raiz que la auditoria 2026-08-05 registro (implementaciones divergentes,
    F-10/F-15): un unico helper es la unica forma de que no puedan separarse.

    Demo conserva la banca estatica a proposito: no toca dinero real. Si
    `bankroll_dynamic` esta desactivado, no hace nada.
    """
    if mode == "demo" or not getattr(settings, "bankroll_dynamic", False):
        return settings.bankroll
    try:
        bal = BankrollLedger(root=root, initial=settings.bankroll).current_balance()
    except LedgerIntegridadError as exc:
        # Banca a CERO, no a la cifra estatica. Caer al nominal seria justo el
        # fallo de AUD-001 por otra puerta: dimensionar sobre un numero que el
        # ledger ya no respalda, y ademas el MAS ALTO de los dos (el inicial no
        # descuenta las perdidas ilegibles). Con 0 no se dimensiona ninguna
        # apuesta -- la lista de picks se sigue generando entera, que es lo que
        # exige la REGLA FUNDAMENTAL: el gate quita el stake, nunca la lista.
        log.error("BANCA NO VERIFICABLE: %s. Se dimensiona sobre 0: ninguna "
                  "apuesta llevara stake hasta que el ledger se repare. El "
                  "fichero NO se ha tocado, para poder diagnosticarlo.", exc)
        settings.bankroll = 0.0
        return 0.0
    log.info("Banca dinamica: inicial %.2f -> balance actual %.2f "
             "(PnL realizado + ajustes).", settings.bankroll, bal)
    if bal <= 0:
        log.warning("Balance de banca <= 0 (%.2f): no se dimensionara ninguna "
                    "apuesta.", bal)
    # Piso en 0: una banca negativa propagaba stakes NEGATIVOS al stake plano del
    # modo precision, y settle.py grada una perdida como pnl = -stake, es decir
    # POSITIVO, realimentando el ledger (auditoria 2026-07-29, B-06).
    settings.bankroll = max(0.0, bal)
    return settings.bankroll
