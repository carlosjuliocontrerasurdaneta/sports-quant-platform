from sqp.risk.kelly import kelly_fraction_stake, edge

def test_no_bet_below_min_edge():
    stake, pct = kelly_fraction_stake(0.50, 1.91, 1000)  # negative edge
    assert stake == 0 and pct == 0

def test_fractional_kelly_capped():
    stake, pct = kelly_fraction_stake(0.60, 2.00, 1000, fraction=0.25, max_stake_pct=0.02)
    assert 0 < pct <= 0.02
    assert stake == round(1000 * pct, 2)

def test_edge_sign():
    assert edge(0.55, 2.0) > 0
    assert edge(0.45, 2.0) < 0

def test_out_of_bounds_probability_no_bet():
    assert kelly_fraction_stake(0.0, 2.0, 1000) == (0.0, 0.0)
    assert kelly_fraction_stake(1.0, 2.0, 1000) == (0.0, 0.0)

def test_invalid_price_no_bet():
    assert kelly_fraction_stake(0.60, 1.0, 1000) == (0.0, 0.0)

def test_nonpositive_bankroll_no_bet():
    # banca dinamica agotada (M-17): jamas un stake negativo
    assert kelly_fraction_stake(0.60, 2.0, 0.0) == (0.0, 0.0)
    assert kelly_fraction_stake(0.60, 2.0, -50.0) == (0.0, 0.0)


class TestValoresNoFinitos:
    """AUD-005 (Codex, 2026-09-05). Las guardas de RANGO no ven la finitud.

    `inf <= 0` es False y TODA comparacion con `nan` es False, asi que ambos
    atravesaban las comprobaciones existentes y producian un stake no finito.
    """

    def test_una_banca_infinita_no_produce_stake(self):
        assert kelly_fraction_stake(0.6, 2.0, float("inf")) == (0.0, 0.0)

    def test_una_banca_nan_no_produce_stake(self):
        assert kelly_fraction_stake(0.6, 2.0, float("nan")) == (0.0, 0.0)

    def test_probabilidad_o_precio_no_finitos_tampoco(self):
        assert kelly_fraction_stake(float("nan"), 2.0, 1000.0) == (0.0, 0.0)
        assert kelly_fraction_stake(0.6, float("inf"), 1000.0) == (0.0, 0.0)

    def test_el_caso_sano_sigue_dimensionando(self):
        """Discriminacion: la guarda no puede apagar el staking normal."""
        stake, pct = kelly_fraction_stake(0.6, 2.0, 1000.0)
        assert stake > 0 and pct > 0


def test_settings_rechaza_una_banca_no_finita(monkeypatch, tmp_path):
    """La primera linea de defensa: rechazar antes de evaluar candidatos."""
    import math

    import pytest

    from sqp.config import Settings
    for valor in ("inf", "-inf", "nan"):
        monkeypatch.setenv("BANKROLL", valor)
        with pytest.raises(ValueError, match="finite"):
            Settings.load().validate()
    monkeypatch.setenv("BANKROLL", "1000")
    assert math.isfinite(Settings.load().validate().bankroll)
