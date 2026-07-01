"""Broker de Polymarket — ejecución real vía el SDK oficial `polymarket` (CLOB V2).

Migrado de py-clob-client (v1, USDC.e) al SDK oficial `polymarket-client`
(SecureClient), que es nativo de **CLOB V2 + pUSD**: trae los contratos V2 baked-in,
deriva el proxy wallet desde la private key y maneja neg-risk internamente.

SEGURIDAD POR DEFECTO: dry-run. Sólo envía órdenes reales si TODO esto se cumple:
  - `live=True` al construirlo, Y
  - env `POLYMARKET_LIVE=1`, Y
  - hay `POLYMARKET_PRIVATE_KEY`, Y
  - no está activo el kill-switch (`POLYMARKET_KILL_SWITCH=1`).
En cualquier otro caso devuelve un OrderResult `status="dry_run"` mostrando EXACTO
lo que se enviaría, sin tocar la red ni la wallet.

Guardas: redondeo de precio al tick, tamaño mínimo (orderMinSize). El SDK es
opcional (extra `[live]`); sin él, el broker queda en dry-run.
"""
from __future__ import annotations

import hashlib
import os
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from core.utils import to_decimal, utcnow
from execution.schemas.order_result import OrderResult
from execution.schemas.trade_order import TradeOrder


def _kill_switch_on() -> bool:
    return os.getenv("POLYMARKET_KILL_SWITCH", "") in ("1", "true", "yes", "on")


def round_to_tick(price: Decimal, tick: Decimal | None) -> Decimal:
    """Redondea el precio al múltiplo de tick más cercano (default 0.001)."""
    t = tick or Decimal("0.001")
    return (price / t).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * t


class PolymarketBroker:
    """Envía órdenes al CLOB V2 de Polymarket (o simula en dry-run)."""

    def __init__(
        self,
        *,
        live: bool = False,
        private_key: str | None = None,
        funder: str | None = None,
    ) -> None:
        # `funder` (wallet) es opcional: el SDK lo deriva de la private key.
        self.private_key = private_key or os.getenv("POLYMARKET_PRIVATE_KEY")
        self.funder = funder or os.getenv("POLYMARKET_FUNDER") or None
        self._client = None

        env_live = os.getenv("POLYMARKET_LIVE", "") in ("1", "true", "yes", "on")
        self.live = bool(live and env_live and self.private_key and not _kill_switch_on())
        self._blocked_reason = None
        if live and not self.live:
            if _kill_switch_on():
                self._blocked_reason = "kill_switch"
            elif not env_live:
                self._blocked_reason = "POLYMARKET_LIVE!=1"
            elif not self.private_key:
                self._blocked_reason = "sin POLYMARKET_PRIVATE_KEY"

    # ── cliente V2 (lazy) ────────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            from polymarket import SecureClient

            kwargs = {"private_key": self.private_key}
            if self.funder:
                kwargs["wallet"] = self.funder
            self._client = SecureClient.create(**kwargs)
        return self._client

    # ── colocación ───────────────────────────────────────────────────────────

    def _prepare(self, order: TradeOrder) -> tuple[Decimal, Decimal, list[str]]:
        notes: list[str] = []
        price = round_to_tick(order.price, order.tick_size)
        if price != order.price:
            notes.append(f"precio redondeado a tick {order.tick_size}: {order.price}->{price}")
        shares = (to_decimal(order.size_usdc) / price) if price > 0 else Decimal("0")
        shares = shares.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return price, shares, notes

    def place(self, order: TradeOrder) -> OrderResult:
        price, shares, notes = self._prepare(order)
        raw = {
            "token_id": order.token_id, "condition_id": order.condition_id,
            "side": order.side.value, "price": str(price), "shares": str(shares),
            "size_usdc": str(order.size_usdc), "neg_risk": order.neg_risk,
            "tick_size": str(order.tick_size), "collateral": "pUSD", "notes": notes,
        }
        oid = "ord-" + hashlib.sha256(
            f"{order.token_id}|{order.side.value}|{order.size_usdc}|{price}".encode()
        ).hexdigest()[:16]

        if order.min_order_size is not None and shares < order.min_order_size:
            return OrderResult(
                order_id=oid, status="rejected", filled_size_usdc=Decimal("0"),
                avg_price=price, submitted_at=utcnow(),
                raw={**raw, "reject": f"shares {shares} < min {order.min_order_size}"},
            )

        if not self.live:
            return OrderResult(
                order_id=oid, status="dry_run", filled_size_usdc=Decimal("0"),
                avg_price=price, submitted_at=utcnow(),
                raw={**raw, "dry_run": True, "blocked_reason": self._blocked_reason,
                     "note": "dry-run: no se envió nada. Activá live con POLYMARKET_LIVE=1 + key"},
            )

        # ── ejecución real (CLOB V2, colateral pUSD) ─────────────────────────
        try:
            client = self._get_client()
            result = client.place_limit_order(
                token_id=order.token_id,
                price=float(price),
                size=float(shares),
                side="BUY" if order.side.value == "BUY" else "SELL",
            )
            accepted = type(result).__name__ == "AcceptedOrder"
            order_id = (getattr(result, "order_id", None) or getattr(result, "id", None) or oid)
            return OrderResult(
                order_id=str(order_id),
                status="live" if accepted else "rejected",
                filled_size_usdc=order.size_usdc if accepted else Decimal("0"),
                avg_price=price, submitted_at=utcnow(),
                raw={**raw, "response": str(result)[:500]},
            )
        except Exception as exc:  # noqa: BLE001 — nunca tirar dentro del pipeline de trading
            return OrderResult(
                order_id=oid, status="error", filled_size_usdc=Decimal("0"),
                avg_price=price, submitted_at=utcnow(),
                raw={**raw, "error": f"{type(exc).__name__}: {exc}"},
            )
