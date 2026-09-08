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

# Estados de liquidacion cuyo importe PUEDE venir vacio sin que eso signifique
# "no se sabe". `settle.py` los grada con `pnl` 0.0 explicito -- el mapa de
# `settle_candidates` cubre los cuatro estados y ninguno produce vacio --, asi
# que un hueco aqui solo aparece en ficheros de otra procedencia; y en un push o
# un void el importe no es el corazon del movimiento, el resultado si.
#
# En una `win` o una `loss` es al reves: el importe ES el movimiento, y un hueco
# ahi no es un cero, es un dato que falta.
_ESTADOS_SIN_IMPORTE = frozenset({"push", "void"})
_INF = float("inf")


def _filas_csv(mala: pd.Series, limite: int = 5) -> list[int]:
    """Numeros de fila del CSV (cabecera + base 1) de las posiciones marcadas.

    Por POSICION, nunca por etiqueta de indice. La primera version hacia
    `int(i) + 2` sobre `df.index[mala]`, y eso asume que el indice es el
    RangeIndex por defecto. No lo es justo en el caso que estas guardas existen
    para detectar: cuando todas las filas traen un campo de mas, pandas toma la
    primera columna como indice, asi que las etiquetas pasan a ser fechas y
    `int("2026-09-01")` lanza `ValueError`.

    Y ese ValueError NO es `LedgerIntegridadError`, asi que `apply_dynamic_bankroll`
    no lo captura: en vez de caer a banca 0 se propagaba y `settings.bankroll`
    se quedaba en la cifra estatica -- exactamente el fallo que KI-032 arregla,
    reintroducido por su propio codigo de diagnostico. Encontrado por la revision
    cruzada de Codex sobre este mismo cambio y reproducido antes de corregirlo.
    """
    return [pos + 2 for pos, bad in enumerate(mala.to_numpy()) if bad][:limite]


def _finitos(valores: pd.Series) -> pd.Series:
    """Mascara de importes numericos Y finitos.

    `to_numeric` convierte la cadena "inf" en un float perfectamente valido que
    `notna()` acepta, asi que comprobar solo "es numerico" deja pasar un importe
    infinito y la banca sale infinita.
    """
    num = pd.to_numeric(valores, errors="coerce")
    return num.notna() & (num.abs() != _INF)


def _exigir_importes_legibles(f: Path, df: pd.DataFrame) -> None:
    """Ninguna fila que DECIDA el saldo puede traer un importe indeterminado.

    KI-032 / AUD-20260906-01 (auditoria independiente de Codex, 2026-09-06,
    HIGH, REPRODUCED). `_exigir_pnl_legible` solo rechaza el fichero cuando NO
    queda NINGUN `pnl` numerico. Si queda uno valido -- que es el caso mucho mas
    probable --, los demas valores ilegibles pasaban por
    `to_numeric(errors="coerce").fillna(0.0)` y una PERDIDA se convertia en un
    movimiento de CERO. La proteccion contra el fichero totalmente ilegible no
    cubria la corrupcion PARCIAL.

    Reproducido antes de tocar nada: banca inicial 1.000 con dos perdidas de
    -400 da 200 con el ledger integro; sustituyendo UN importe por texto salia
    **600**, y `apply_dynamic_bankroll` aceptaba esa cifra sin excepcion. De ese
    numero cuelgan el Kelly y el cap de exposicion diaria.

    El error siempre va en la misma direccion -- la banca SUBE --, porque las
    filas que se dejan de leer son casi siempre perdidas.

    DISCRIMINACION POR TIPO DE MOVIMIENTO, no por severidad: un `push` o un
    `void` con importe VACIO sigue siendo un cero legitimo (decision registrada
    en `test_un_push_con_pnl_vacio_no_dispara_la_guarda`, que este cambio NO
    contradice). Lo que se rechaza es un importe indeterminado donde el importe
    es el movimiento, y tambien un valor PRESENTE pero ilegible en un estado
    exento: ahi ya no falta el dato, esta corrupto.

    Se comprueba el fichero entero, antes de filtrar por `data_label`, igual que
    la guarda que amplia: es la direccion conservadora, y los liquidados demo
    viven en `data/bets/demo/`, fuera de este glob.

    El fichero NO se toca ni se repara: se nombran fichero y filas para poder
    diagnosticarlo. Un ledger de 1.305 filas necesita saber cual mirar.
    """
    crudo = df["pnl"]
    finito = _finitos(crudo)
    vacio = crudo.isna() | (crudo.astype(str).str.strip() == "")
    if "result" in df.columns:
        exento = df["result"].astype(str).str.strip().str.lower().isin(_ESTADOS_SIN_IMPORTE)
    else:
        # Sin `result` no se puede acreditar la exencion, y no acreditarla es
        # exactamente "no se sabe": se exige importe legible en todas.
        exento = pd.Series(False, index=df.index)
    malas = ~(finito | (exento & vacio))
    if not malas.any():
        return
    idx = _filas_csv(malas)
    muestra = crudo[malas].head(3).tolist()
    estados = df.loc[malas, "result"].head(3).tolist() if "result" in df.columns else ["?"]
    raise LedgerIntegridadError(
        f"{f.name}: {int(malas.sum())} de {len(df)} filas con importe "
        f"indeterminado (fila/s {idx}, result={estados}, leido: {muestra}). "
        f"Un importe que no se puede determinar NO es cero: las filas ilegibles "
        f"suelen ser perdidas y tratarlas como cero SUBE la banca. Solo un push "
        f"o un void admiten importe vacio. El saldo no es verificable.")


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
                # Primero el desplazamiento de columnas, que tiene diagnostico
                # propio; despues la corrupcion PARCIAL fila a fila (KI-032).
                _exigir_pnl_legible(f, df)
                _exigir_importes_legibles(f, df)
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
        """Suma de los PnL realizados de las apuestas REALES liquidadas.

        El `fillna(0.0)` es seguro AQUI y solo aqui: `_exigir_importes_legibles`
        ya aborto si quedaba algun importe indeterminado, asi que los unicos NaN
        que sobreviven son los de un push o un void con importe vacio, donde
        cero es el valor correcto y no una suposicion (KI-032).
        """
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
            # Fichero VACIO de filas: no hay ningun movimiento que leer mal, y
            # "sin ajustes" es el estado normal. Cero legitimo.
            if adj.empty:
                return 0.0
            # Con filas y SIN columna `amount` el saldo no es verificable
            # (AUD-HIGH-003, auditoria integral 2026-09-08, HIGH, REPRODUCIDO).
            # La guarda de abajo valida el VALOR del importe, pero no validaba
            # la PRESENCIA de su columna, asi que una cabecera derivada --
            # `importe`, `Amount`, un espacio de mas, o las columnas desplazadas
            # por un campo extra -- hacia desaparecer los ajustes en silencio.
            #
            # Es exactamente el hueco que `_exigir_pnl_legible` cierra en
            # `settled_*.csv`, dejado abierto en el OTRO sumando del saldo.
            # Reproducido: banca 1.000 con una perdida de -100 y una retirada de
            # -400 da 500; renombrando `amount` a `importe` daba **900**, con la
            # retirada evaporada. El error va SIEMPRE hacia arriba, porque lo
            # que se registra aqui son correcciones y retiradas, y de esa cifra
            # cuelgan el Kelly y el cap de exposicion diaria.
            #
            # El fichero se mantiene A MANO, que es justo donde una deriva de
            # cabecera es plausible; hoy tiene dos filas reales.
            raise LedgerIntegridadError(
                f"{ADJUSTMENTS_FILE} tiene {len(adj)} filas pero ninguna columna "
                f"'amount' (columnas leidas: {list(adj.columns)}). Un ajuste cuyo "
                f"importe no se puede localizar NO es un ajuste de cero: una "
                f"retirada que se evapora SUBE la banca. El saldo no es "
                f"verificable.")
        # Aqui NO hay estado exento: un ajuste sin cantidad no es un ajuste de
        # cero, es un movimiento que no sabemos leer. Codex lo reprodujo con la
        # otra mitad de KI-032: banca 1.000 con una retirada de -400 da 600, y
        # con el importe ilegible daba 1.000 -- la retirada se evaporaba.
        malos = ~_finitos(adj["amount"])
        if malos.any():
            idx = _filas_csv(malos)
            raise LedgerIntegridadError(
                f"{ADJUSTMENTS_FILE}: {int(malos.sum())} de {len(adj)} filas con "
                f"'amount' indeterminado (fila/s {idx}, leido: "
                f"{adj['amount'][malos].head(3).tolist()}). Una retirada que no "
                f"se puede leer infla la banca igual que una perdida que no se "
                f"puede leer. El saldo no es verificable.")
        return float(pd.to_numeric(adj["amount"], errors="coerce").sum())

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
