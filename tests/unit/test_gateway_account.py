# tests/unit/test_gateway_account.py
from decimal import Decimal
from venue.gateway import PolymarketGateway

class _Book:  # asks: lista de niveles con .price
    def __init__(self, asks): self.asks = asks
class _Lvl:
    def __init__(self, p): self.price = Decimal(str(p))
class _BA:
    balance = 448620000   # micro-USDC

class _FakeClient:
    def get_balance_allowance(self, *, asset_type, token_id=None): return _BA()
    def get_order_book(self, *, token_id): return _Book([_Lvl("0.47"), _Lvl("0.52")])

def _gw():
    gw = PolymarketGateway(live=False)
    gw._client = _FakeClient()          # inyecta el fake (evita red)
    gw.private_key = "0xabc"            # para que best_ask no corte por falta de key
    return gw

def test_balance_micro_to_usdc():
    assert _gw().balance().usdc_balance == Decimal("448.62")

def test_best_ask_min_of_asks():
    assert _gw().best_ask("t") == Decimal("0.47")
