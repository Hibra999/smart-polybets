from scripts.profit_challengers import simulate


def test_simulation_applies_costs_and_uses_one_side_per_event():
    result = simulate([
        {
            "event_id": "win", "season": "2022", "probabilities": (0.9, 0.1),
            "odds": (2.0, 2.0), "winner": 0,
        },
        {
            "event_id": "no-edge", "season": "2022", "probabilities": (0.5, 0.5),
            "odds": (2.0, 2.0), "winner": 1,
        },
    ])
    assert result["performance"]["bets"] == 1
    assert result["performance"]["profit"] < 25  # fee y slippage reducen el payout
    assert result["performance"]["profit"] > 0
    assert result["bets"][0]["event_id"] == "win"
