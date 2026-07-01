from decimal import Decimal

from core.local_state import LocalStateClient


def test_set_bankroll_persists_and_is_preferred_on_reload(tmp_path):
    p = tmp_path / "state.json"
    c1 = LocalStateClient(p, bankroll_usdc=1000.0)
    c1.set_bankroll(Decimal("1234.56"))
    assert c1.initial_bankroll == Decimal("1234.56")
    # Nueva instancia con otro seed: debe preferir el bankroll persistido.
    c2 = LocalStateClient(p, bankroll_usdc=1000.0)
    assert c2.initial_bankroll == Decimal("1234.56")
    assert c2.get_portfolio_state()["bankroll_usdc"] == "1234.56"
