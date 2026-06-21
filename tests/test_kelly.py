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
