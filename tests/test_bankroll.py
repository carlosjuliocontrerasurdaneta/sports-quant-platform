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


class TestLaCorrupcionParcial:
    """KI-032 / AUD-20260906-01 (Codex, HIGH, REPRODUCED).

    La guarda de AUD-001 solo rechaza el fichero cuando NO queda NINGUN `pnl`
    numerico. Si queda uno valido, los demas valores ilegibles pasan por
    `to_numeric(errors="coerce").fillna(0.0)` y una PERDIDA se convierte en un
    movimiento de CERO. La proteccion contra el fichero totalmente ilegible no
    cubria la corrupcion parcial, que es la mas probable de las dos.

    Direccion del error: la banca siempre SUBE, porque las filas que se dejan de
    leer son casi siempre perdidas. Y de esa cifra cuelgan el Kelly y el cap de
    exposicion diaria.
    """

    def test_una_perdida_ilegible_entre_perdidas_validas_no_desaparece(self, tmp_path):
        """El caso exacto de Codex: banca 1.000, dos perdidas de -400.

        Con el ledger integro son 200. Sustituyendo UN importe por texto, la
        guarda anterior lo dejaba pasar (queda otro `pnl` numerico) y el saldo
        salia 600: +400 sin deposito ni ganancia.
        """
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-400.0, result="loss"),
                                     _row("ERROR", result="loss")])
        with pytest.raises(LedgerIntegridadError, match="loss"):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_una_ganancia_ilegible_tambien_para_el_calculo(self, tmp_path):
        """No se trata de proteger solo a la baja: un importe que no se puede
        determinar hace el saldo NO VERIFICABLE, suba o baje."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(50.0, result="win"),
                                     _row("n/d", result="win")])
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_un_pnl_infinito_no_es_un_importe(self, tmp_path):
        """`to_numeric` convierte 'inf' en un float valido y `notna()` lo acepta,
        asi que una comprobacion de "es numerico" a secas lo deja pasar y la
        banca sale infinita."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss"),
                                     _row("inf", result="win")])
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_una_retirada_ilegible_entre_ajustes_validos(self, tmp_path):
        """Segundo caso de Codex: banca 1.000 con una retirada de -400 da 600;
        con el importe ilegible daba 1.000. Un ajuste no tiene estado que admita
        importe vacio -- un movimiento sin cantidad no es un movimiento."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss")])
        (bets / "bankroll_adjustments.csv").write_text(
            NL.join(["date,amount", "2026-09-01,-400", "2026-09-02,ERROR", ""]),
            encoding="utf-8")
        with pytest.raises(LedgerIntegridadError, match="amount"):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_el_error_nombra_la_fila_y_el_fichero(self, tmp_path):
        """Un ledger de 1.305 filas necesita saber CUAL revisar. El fichero no
        se toca ni se repara: se nombra para poder diagnosticarlo."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-400.0, result="loss"),
                                     _row(-400.0, result="loss"),
                                     _row("ERROR", result="loss")])
        with pytest.raises(LedgerIntegridadError) as exc:
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()
        assert "settled_mlb.csv" in str(exc.value)
        assert "fila" in str(exc.value).lower()

    def test_el_staking_cae_a_CERO_ante_corrupcion_parcial(self, tmp_path):
        """Lo que de verdad protege el capital: `apply_dynamic_bankroll` NO debe
        aceptar la cifra inflada. Codex verifico que aceptaba los 600."""
        from types import SimpleNamespace
        from sqp.risk.bankroll import apply_dynamic_bankroll
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-400.0, result="loss"),
                                     _row("ERROR", result="loss")])
        s = SimpleNamespace(bankroll=1000.0, bankroll_dynamic=True)
        assert apply_dynamic_bankroll(s, tmp_path, "live") == 0.0
        assert s.bankroll == 0.0

    # --- Discriminacion: lo que NO debe cambiar -------------------------------

    def test_un_push_con_pnl_vacio_sigue_siendo_cero_legitimo(self, tmp_path):
        """DECISION REGISTRADA que este arreglo NO contradice
        (`test_un_push_con_pnl_vacio_no_dispara_la_guarda`).

        La discriminacion correcta no es "todo pnl debe ser numerico" sino POR
        TIPO DE MOVIMIENTO: `settle.py` grada push y void con pnl 0.0 explicito,
        asi que un importe vacio en esos estados es un cero legitimo. En una
        `loss` no lo es: ahi el importe es el corazon del movimiento.
        """
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss"),
                                     _row(None, result="push"),
                                     _row(None, result="void")])
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 900.0

    def test_un_ledger_integro_no_se_toca(self, tmp_path):
        """Contraprueba obligatoria: sin ella, una guarda que lanzara SIEMPRE
        pasaria todos los tests de arriba."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-400.0, result="loss"),
                                     _row(-400.0, result="loss")])
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 200.0

    def test_las_1305_filas_reales_seguirian_pasando(self, tmp_path):
        """Fija la premisa medida antes de endurecer la guarda: de las 1.305
        filas liquidadas en produccion y los 2 ajustes, CERO tienen importe no
        numerico. Se reproduce aqui la forma de esas filas."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(18.5, result="win"),
                                     _row(-20.0, result="loss"),
                                     _row(0.0, result="push"),
                                     _row(0.0, result="void")])
        assert BankrollLedger(root=tmp_path, initial=1000.0).current_balance() == 998.5


class TestElDiagnosticoNoPuedeRomperse:
    """Defecto introducido POR el arreglo de KI-032 y encontrado por la revision
    cruzada de Codex sobre ese mismo cambio.

    Las guardas numeraban las filas con `int(i) + 2` sobre la ETIQUETA del
    indice, asumiendo el RangeIndex por defecto. No lo es justo en el caso que
    existen para detectar: con un campo de mas en todas las filas, pandas toma
    la primera columna como indice y las etiquetas pasan a ser fechas, asi que
    `int("2026-09-01")` lanza `ValueError`.

    Y un `ValueError` NO es `LedgerIntegridadError`, que es lo unico que captura
    `apply_dynamic_bankroll`: en vez de caer a banca 0 se propagaba y
    `settings.bankroll` se quedaba en la cifra ESTATICA. El codigo de
    diagnostico reintroducia el fallo que su propia guarda arregla.
    """

    def test_ajustes_desplazados_lanzan_integridad_y_no_ValueError(self, tmp_path):
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss")])
        (bets / "bankroll_adjustments.csv").write_text(
            NL.join(["date,amount,kind,note",
                     "2026-09-01,-400,withdrawal,note,SOBRA", ""]),
            encoding="utf-8")
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_el_staking_cae_a_CERO_con_ajustes_desplazados(self, tmp_path):
        """Lo que de verdad importaba: sin esto, `settings.bankroll` se quedaba
        en 1000 -- la cifra que el ledger ya no respalda."""
        from types import SimpleNamespace
        from sqp.risk.bankroll import apply_dynamic_bankroll
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-100.0, result="loss")])
        (bets / "bankroll_adjustments.csv").write_text(
            NL.join(["date,amount,kind,note",
                     "2026-09-01,-400,withdrawal,note,SOBRA", ""]),
            encoding="utf-8")
        s = SimpleNamespace(bankroll=1000.0, bankroll_dynamic=True)
        assert apply_dynamic_bankroll(s, tmp_path, "live") == 0.0
        assert s.bankroll == 0.0

    def test_liquidados_con_indice_no_entero_tampoco_rompen(self, tmp_path):
        """La misma suposicion vivia en `_exigir_importes_legibles`. Se llega ahi
        con un desplazamiento que deja `pnl` numerico, asi que `_exigir_pnl_legible`
        no lo intercepta antes."""
        bets = tmp_path / "data" / "bets"
        bets.mkdir(parents=True, exist_ok=True)
        (bets / "settled_mlb.csv").write_text(
            NL.join(["pnl,result,stake,data_label,settled_at",
                     "-100.0,loss,100,real,2026-06-01T00:00:00+00:00,SOBRA",
                     "ERROR,loss,100,real,2026-06-02T00:00:00+00:00,SOBRA", ""]),
            encoding="utf-8")
        with pytest.raises(LedgerIntegridadError):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()

    def test_los_numeros_de_fila_son_los_del_csv(self, tmp_path):
        """Contraprueba: el diagnostico tiene que seguir siendo UTIL. La tercera
        fila de datos es la linea 4 del fichero (cabecera + base 1)."""
        bets = tmp_path / "data" / "bets"
        _write_settled(bets, "mlb", [_row(-1.0, result="loss"),
                                     _row(-1.0, result="loss"),
                                     _row("ERROR", result="loss")])
        with pytest.raises(LedgerIntegridadError, match=r"\[4\]"):
            BankrollLedger(root=tmp_path, initial=1000.0).current_balance()


# --- Esquema de los ajustes manuales (AUD-HIGH-003, auditoria 2026-09-08) -----
#
# `adjustments_total` validaba el VALOR del importe pero no la PRESENCIA de su
# columna: con la cabecera derivada devolvia 0.0 en silencio y la retirada
# desaparecia. Es el hueco que `_exigir_pnl_legible` ya cierra en settled_*.csv,
# dejado abierto en el otro sumando del saldo. El error va SIEMPRE hacia arriba.

def _ajustes(tmp_path, texto: str):
    bets = tmp_path / "data" / "bets"
    bets.mkdir(parents=True, exist_ok=True)
    (bets / "settled_mlb.csv").write_text(
        "pnl,data_label,result,stake\n-100,real,loss,100\n", encoding="utf-8")
    (bets / "bankroll_adjustments.csv").write_text(texto, encoding="utf-8")
    return BankrollLedger(root=tmp_path, initial=1000.0)


def test_una_retirada_con_la_columna_renombrada_no_se_evapora(tmp_path):
    """Reproducido antes de corregir: daba 900,0 con la retirada desaparecida."""
    led = _ajustes(tmp_path, "date,importe,kind,note\n2026-01-01,-400,withdrawal,x\n")
    with pytest.raises(LedgerIntegridadError, match="amount"):
        led.current_balance()


def test_el_esquema_correcto_sigue_sumando(tmp_path):
    led = _ajustes(tmp_path, "date,amount,kind,note\n2026-01-01,-400,withdrawal,x\n")
    assert led.adjustments_total() == -400.0
    assert led.current_balance() == 500.0


def test_un_fichero_de_ajustes_sin_filas_es_un_cero_legitimo(tmp_path):
    """Lo normal es no haber hecho ningun ajuste: eso no puede ser un error."""
    led = _ajustes(tmp_path, "date,amount,kind,note\n")
    assert led.adjustments_total() == 0.0
    assert led.current_balance() == 900.0


def test_una_cabecera_desplazada_por_un_campo_de_mas_tampoco_pasa(tmp_path):
    """Mismo modo de fallo que KI-011, en el fichero de ajustes: pandas toma la
    primera columna como indice y `amount` deja de existir con ese nombre."""
    led = _ajustes(tmp_path, "date,amount,kind\n2026-01-01,-400,withdrawal,SOBRA\n")
    with pytest.raises(LedgerIntegridadError):
        led.current_balance()


def test_el_error_nombra_las_columnas_que_si_encontro(tmp_path):
    """Un diagnostico que no dice que se leyo manda a adivinar."""
    led = _ajustes(tmp_path, "date,importe,kind\n2026-01-01,-400,withdrawal\n")
    with pytest.raises(LedgerIntegridadError, match="importe"):
        led.current_balance()
