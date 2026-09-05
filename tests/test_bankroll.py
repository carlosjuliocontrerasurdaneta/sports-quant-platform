"""Bankroll ledger: balance = initial + realized PnL (real bets) + adjustments."""
import pandas as pd
import pytest

from sqp.exceptions import LedgerIntegridadError
from sqp.risk.bankroll import BankrollLedger


# `chr(10)` en vez de la secuencia de escape: este fichero se ha escrito
# mas de una vez desde herramientas que se comen las contrabarras.
NL = chr(10)


def _write_settled(bets_dir, league, rows):
    bets_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(bets_dir / f"settled_{league}.csv", index=False)


def _row(pnl, result="win", stake=10.0, data_label="real", settled_at="2026-06-01T00:00:00+00:00"):
    return {"pnl": pnl, "result": result, "stake": stake,
            "data_label": data_label, "settled_at": settled_at}


def test_empty_state_equals_initial(tmp_path):
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 1000.0
    assert led.realized_pnl() == 0.0


def test_balance_sums_realized_pnl_across_leagues(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(9.0), _row(-10.0, result="loss")])
    _write_settled(bets, "nhl", [_row(5.0)])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.realized_pnl() == 4.0                 # 9 - 10 + 5
    assert led.current_balance() == 1004.0


def test_demo_bets_are_excluded(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(9.0, data_label="real"),
                                 _row(500.0, data_label="demo_synthetic")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 1009.0           # demo PnL ignored


def test_manual_adjustments_apply(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(0.0, result="push")])
    bets.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": "2026-06-01", "amount": 250.0, "kind": "deposit", "note": ""},
                  {"date": "2026-06-05", "amount": -100.0, "kind": "withdrawal", "note": ""}]
                 ).to_csv(bets / "bankroll_adjustments.csv", index=False)
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.adjustments_total() == 150.0
    assert led.current_balance() == 1150.0


def test_summary_and_drawdown(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [
        _row(20.0, settled_at="2026-06-01"),
        _row(-50.0, result="loss", settled_at="2026-06-02"),
        _row(10.0, settled_at="2026-06-03")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    s = led.summary()
    assert s["current_balance"] == 980.0             # 1000 + 20 - 50 + 10
    assert s["n_graded"] == 3
    assert s["total_staked"] == 30.0
    # peak 1020 after day1, trough 970 after day2 -> drawdown -50.
    assert s["max_drawdown"] == -50.0


def _corromper(path):
    """Longitudes de fila INCONSISTENTES -> ParserError.

    Anadir un campo a la ULTIMA fila solo corrompe si hay otra fila con la
    longitud buena: con una sola fila, pandas 3.0 no protesta -- toma la primera
    columna como indice y sigue (ver `TestElDesplazamientoSilencioso`)."""
    lineas = path.read_text(encoding="utf-8").rstrip(NL).split(NL)
    assert len(lineas) >= 3, "el fixture necesita cabecera + 2 filas"
    lineas[-1] = lineas[-1] + ",SOBRA"
    path.write_text(NL.join(lineas) + NL, encoding="utf-8")


class TestUnLedgerIlegibleNoEsUnLedgerVacio:
    """AUD-001 (Codex, 2026-09-05). CONTRATO INVERTIDO.

    Sustituye a `test_corrupt_or_empty_file_is_skipped`, que fijaba lo
    contrario: omitir el fichero ilegible y seguir sumando. No se anade al lado
    -- el hallazgo lo advierte: "debe revisarse su contrato y no solamente
    agregarse otro test que lo repita".

    Por que el contrato viejo era peligroso: omitir equipara "no se sabe" con
    "no aporta nada", y en contabilidad eso NO es neutral. Las filas ilegibles
    son casi siempre PERDIDAS, asi que el saldo SUBE -- y de el cuelgan el Kelly
    y el cap de exposicion diaria.
    """

    def test_un_fichero_corrupto_de_perdidas_ya_no_infla_la_banca(self, tmp_path):
        """La reproduccion exacta del hallazgo, como regresion."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-200.0, result="loss"),
                                    _row(-200.0, result="loss")])
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 600.0
        _corromper(bets / "settled_mlb.csv")
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_el_error_nombra_el_fichero(self, tmp_path):
        """Sin el nombre, un ledger de 27 ficheros deja al operador a ciegas."""
        bets = tmp_path / "data" / "bets"
        bets.mkdir(parents=True, exist_ok=True)
        (bets / "settled_wnba.csv").write_text(NL.join(["a,b", "1,2", "3,4,5", ""]),
                                               encoding="utf-8")
        with pytest.raises(LedgerIntegridadError, match="settled_wnba.csv"):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_un_settled_vacio_tambien_es_indeterminado(self, tmp_path):
        """`_persist_settled` SIEMPRE escribe cabecera, asi que un frame vacio da
        un fichero CON cabecera que pandas lee sin error. Cero bytes significa
        truncado, no "liga sin apuestas"."""
        bets = tmp_path / "data" / "bets"
        bets.mkdir(parents=True, exist_ok=True)
        (bets / "settled_mlb.csv").write_text("", encoding="utf-8")
        _write_settled(bets, "nhl", [_row(7.0)])
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_ajustes_corruptos_tambien_paran_el_calculo(self, tmp_path):
        """Una retirada ilegible infla la banca igual que una perdida ilegible."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss")])
        (bets / "bankroll_adjustments.csv").write_text(
            NL.join(["date,amount", "2026-09-01,-500", "2026-09-02,-1,SOBRA", ""]),
            encoding="utf-8")
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_ajustes_vacios_SI_son_cero_legitimo(self, tmp_path):
        """Discriminacion: lo normal es no haber hecho ningun ajuste. Si esto
        tambien lanzara, el arreglo seria inservible en operacion."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss")])
        (bets / "bankroll_adjustments.csv").write_text("", encoding="utf-8")
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 900.0

    def test_el_staking_cae_a_CERO_y_no_a_la_cifra_estatica(self, tmp_path):
        """Lo que de verdad protege el capital.

        Caer al nominal seria el mismo fallo por otra puerta: dimensionar sobre
        un numero que el ledger ya no respalda, y ademas el MAS ALTO de los dos
        -- el inicial no descuenta las perdidas ilegibles. Con 0 no se dimensiona
        ninguna apuesta; la lista de picks se sigue generando entera, que es lo
        que exige la REGLA FUNDAMENTAL."""
        import types

        from sqp.risk.bankroll import apply_dynamic_bankroll
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-200.0, result="loss"),
                                     _row(-200.0, result="loss")])
        _corromper(bets / "settled_mlb.csv")
        s = types.SimpleNamespace(bankroll=1000.0, bankroll_dynamic=True)
        assert apply_dynamic_bankroll(s, tmp_path, "live") == 0.0
        assert s.bankroll == 0.0

    def test_demo_no_queda_bloqueado_por_un_ledger_real_corrupto(self, tmp_path):
        """Demo conserva la banca estatica a proposito: no toca dinero real."""
        import types

        from sqp.risk.bankroll import apply_dynamic_bankroll
        bets = tmp_path / "data" / "bets"
        bets.mkdir(parents=True, exist_ok=True)
        (bets / "settled_mlb.csv").write_text(NL.join(["a,b", "1,2", "3,4,5", ""]),
                                              encoding="utf-8")
        s = types.SimpleNamespace(bankroll=1000.0, bankroll_dynamic=True)
        assert apply_dynamic_bankroll(s, tmp_path, "demo") == 1000.0


def test_max_drawdown_counts_the_loss_from_the_opening_balance(tmp_path):
    """`peak` used to start at -inf, so the curve's first point -- already AFTER
    the first bet -- became the peak and that first loss never counted: three
    -100 bets on a 1000 bankroll reported -200 instead of -300 (R-B-1).
    Understating drawdown is the unsafe direction for a risk metric."""
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [
        _row(-100.0, result="loss", settled_at="2026-06-01T00:00:00+00:00"),
        _row(-100.0, result="loss", settled_at="2026-06-02T00:00:00+00:00"),
        _row(-100.0, result="loss", settled_at="2026-06-03T00:00:00+00:00")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led.current_balance() == 700.0
    assert led._max_drawdown() == -300.0


def test_max_drawdown_measures_from_the_running_peak_not_the_opening(tmp_path):
    """Seeding with the opening balance must not turn the metric into
    'distance below the start': after a run-up the peak still moves."""
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [
        _row(200.0, settled_at="2026-06-01T00:00:00+00:00"),    # 1200, new peak
        _row(-50.0, result="loss", settled_at="2026-06-02T00:00:00+00:00")])
    led = BankrollLedger(root=tmp_path, initial=1000.0)
    assert led._max_drawdown() == -50.0


def test_max_drawdown_is_zero_on_a_monotonically_rising_curve(tmp_path):
    bets = tmp_path / "data" / "bets"
    _write_settled(bets, "mlb", [_row(10.0, settled_at="2026-06-01T00:00:00+00:00"),
                                 _row(10.0, settled_at="2026-06-02T00:00:00+00:00")])
    assert BankrollLedger(root=tmp_path, initial=1000.0)._max_drawdown() == 0.0


class TestElDesplazamientoSilencioso:
    """Variante de AUD-001 encontrada al escribir sus tests, y PEOR que el
    hallazgo original: aqui no hay ninguna excepcion que capturar.

    pandas 3.0 NO lanza `ParserError` cuando TODAS las filas traen un campo de
    mas: toma la primera columna como indice y desplaza el resto, asi que `pnl`
    acaba conteniendo lo que habia en `data_label`. `to_numeric` lo vuelve NaN,
    el `fillna(0.0)` lo suma como cero y las perdidas desaparecen.
    """

    def _desplazado(self, bets):
        cab = "league,market,pnl,data_label,result,stake,settled_at"
        filas = [f"mlb,h2h,-200.0,real,loss,200,2026-09-0{i}T00:00:00Z,SOBRA"
                 for i in (1, 2)]
        bets.mkdir(parents=True, exist_ok=True)
        (bets / "settled_mlb.csv").write_text(NL.join([cab] + filas + [""]),
                                              encoding="utf-8")

    def test_pandas_no_senala_el_desplazamiento(self, tmp_path):
        """Premisa del hallazgo, fijada para que se vea si algun dia cambia."""
        bets = tmp_path / "data" / "bets"
        self._desplazado(bets)
        df = pd.read_csv(bets / "settled_mlb.csv")   # NO lanza
        assert df["pnl"].tolist() == ["real", "real"], "pnl trae otra columna"

    def test_las_perdidas_desplazadas_ya_no_desaparecen(self, tmp_path):
        """Sin la guarda, la banca salia 1000 en vez de 600: -400 evaporados."""
        bets = tmp_path / "data" / "bets"
        self._desplazado(bets)
        with pytest.raises(LedgerIntegridadError, match="desplazadas"):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_un_push_con_pnl_vacio_no_dispara_la_guarda(self, tmp_path):
        """Discriminacion: la guarda exige que al menos UNA fila tenga `pnl`
        numerico, no todas. Un push o un void legitimo puede traerlo vacio."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss"),
                                     _row(None, result="push")])
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 900.0
