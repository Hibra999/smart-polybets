from decimal import Decimal

from risk.functions.correlation import estimate_correlation
from risk.functions.drawdown import check_portfolio_stop_loss, position_stop_loss_triggered
from risk.functions.exposure import check_participant_exposure, projected_exposure_pct


def test_projected_exposure(portfolio_state):
    # 100 USDC sobre bankroll 1000 → 0.10
    assert projected_exposure_pct(portfolio_state, "Argentina", 100) == Decimal("0.1")


def test_check_exposure_within_limit(portfolio_state):
    assert check_participant_exposure(portfolio_state, "Argentina", 100, Decimal("0.15")) is True
    assert check_participant_exposure(portfolio_state, "Argentina", 200, Decimal("0.15")) is False


def test_drawdown_stop_loss(portfolio_state):
    assert check_portfolio_stop_loss(portfolio_state, Decimal("0.20")) is False


def test_position_stop_loss():
    assert position_stop_loss_triggered(100, 35) is True   # 65% pérdida > 60%
    assert position_stop_loss_triggered(100, 50) is False  # 50% < 60%


def test_correlation_same_market(opportunity_factory):
    from portfolio.schemas.position import Position
    from core.utils import utcnow

    opp = opportunity_factory()
    pos = Position(
        condition_id="cond_1", token_id="t", outcome="YES",
        tournament_id="fifa_world_cup_2026", participant="Brazil",
        size_usdc=Decimal("10"), entry_price=Decimal("0.5"),
        current_price=Decimal("0.5"), shares=Decimal("20"), opened_at=utcnow(),
    )
    assert estimate_correlation(opp, [pos]) == 1.0  # mismo condition_id


def test_correlation_empty(opportunity_factory):
    assert estimate_correlation(opportunity_factory(), []) == 0.0
