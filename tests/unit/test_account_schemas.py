from decimal import Decimal

from portfolio.schemas.account import LivePosition


def test_unrealized_pnl_none_without_price():
    p = LivePosition(condition_id="0xabc", token_id="1", outcome="YES",
                     size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"))
    assert p.current_price is None
    assert p.unrealized_pnl is None
    assert p.market_value is None


def test_unrealized_pnl_and_market_value_with_price():
    p = LivePosition(condition_id="0xabc", token_id="1", outcome="YES",
                     size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"),
                     current_price=Decimal("0.60"))
    assert p.unrealized_pnl == Decimal("10.0")   # (0.60-0.50)*100
    assert p.market_value == Decimal("60.0")      # 0.60*100
