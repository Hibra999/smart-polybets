from decimal import Decimal

from risk.functions.kelly import fractional_kelly


def test_kelly_positive_edge():
    # p=0.6, price=0.5 → b=1, raw=0.6-0.4=0.2; quarter-Kelly → 0.05
    out = fractional_kelly(0.6, 0.5, 0.25, 1000)
    assert out.raw_kelly == Decimal("0.2")
    assert out.kelly_fraction == Decimal("0.05")
    assert out.recommended_size_usdc == Decimal("50.00")


def test_kelly_negative_edge_is_zero():
    out = fractional_kelly(0.4, 0.5, 0.25, 1000)
    assert out.raw_kelly == Decimal("0")
    assert out.recommended_size_usdc == Decimal("0.00")


def test_kelly_capped_by_max_bet():
    out = fractional_kelly(0.9, 0.5, 1.0, 1000, max_bet_usdc=50)
    assert out.capped is True
    assert out.recommended_size_usdc == Decimal("50.00")


def test_kelly_capped_by_max_fraction():
    out = fractional_kelly(0.9, 0.5, 1.0, 1000, max_kelly_fraction=Decimal("0.05"))
    assert out.kelly_fraction == Decimal("0.05")
    assert out.capped is True


def test_kelly_invalid_price():
    out = fractional_kelly(0.6, 0, 0.25, 1000)
    assert out.recommended_size_usdc == Decimal("0")
