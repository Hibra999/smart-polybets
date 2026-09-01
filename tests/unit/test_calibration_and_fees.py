from decimal import Decimal

import pytest

from execution.functions.fees import taker_fee_usdc
from research.functions.calibration import (
    expected_calibration_error,
    multiclass_brier,
    multiclass_log_loss,
    power_devig,
)
from venue.books import fee_rate_bps, order_books


def test_probability_calibration_metrics():
    fair = power_devig([0.55, 0.30, 0.25])
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] > fair[1] > fair[2]
    perfect = [[1.0, 0.0], [0.0, 1.0]]
    assert multiclass_brier(perfect, [0, 1]) == 0
    assert multiclass_log_loss(perfect, [0, 1]) == 0
    assert expected_calibration_error(perfect, [0, 1]) == 0


def test_polymarket_fee_formula_and_rate_lookup():
    assert taker_fee_usdc(100, Decimal("0.50"), 500) == Decimal("1.25000")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"base_fee": 500}

    class Session:
        def get(self, url, **kwargs):
            assert url == "https://clob.polymarket.com/fee-rate"
            assert kwargs["params"] == {"token_id": "token"}
            return Response()

    assert fee_rate_bps("token", session=Session()) == 500


def test_order_books_follows_requested_token_order(monkeypatch):
    class Book:
        def __init__(self, token_id):
            self.token_id = token_id

    class Client:
        def get_order_books(self, *, token_ids):
            assert token_ids == ["a", "b"]
            return [Book("b"), Book("a")]

    monkeypatch.setattr("venue.books.build_public_client", lambda: Client())

    assert [book.token_id for book in order_books(["a", "b"])] == ["a", "b"]
