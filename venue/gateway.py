"""Gateway único de Polymarket — centraliza toda interacción con el SDK oficial.

Une la lógica de cuenta (PolymarketAccountSource) y ejecución (PolymarketBroker)
en un único punto de entrada. Los adapters existentes (Task 1.3) delegarán aquí.

SEGURIDAD POR DEFECTO: dry-run. Sólo envía órdenes reales si TODO esto se cumple:
  - `live=True` al construirlo, Y
  - env `POLYMARKET_LIVE=1`, Y
  - hay `POLYMARKET_PRIVATE_KEY`, Y
  - no está activo el kill-switch (`POLYMARKET_KILL_SWITCH=1`).
"""
from __future__ import annotations

import hashlib
import os
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from core.exceptions import AccountUnavailableError, PolymarketClientError
from core.polymarket_client import (
    build_public_client,
    build_secure_client,
    is_evm_private_key,
)
from core.utils import to_decimal, utcnow
from execution.schemas.order_result import OrderResult
from execution.schemas.trade_order import TradeOrder
from portfolio.schemas.account import (
    AccountBalance,
    ClosedPositionLive,
    LivePosition,
    LiveRedemption,
    LiveTrade,
    OpenOrder,
)
from research.functions.market_scanner import PolymarketMarket
from venue.matching import match_event

# Colateral USDC de Polymarket: entero en micro-unidades (6 decimales).
_USDC_DECIMALS = Decimal(10) ** 6


def _kill_switch_on() -> bool:
    return os.getenv("POLYMARKET_KILL_SWITCH", "") in ("1", "true", "yes", "on")


def round_to_tick(price: Decimal, tick: Decimal | None) -> Decimal:
    """Redondea el precio al múltiplo de tick más cercano (default 0.001)."""
    t = tick or Decimal("0.001")
    return (price / t).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * t


class PolymarketGateway:
    """Gateway único: cuenta + ejecución + order book vía el SDK oficial (CLOB V2).

    Portado de PolymarketAccountSource (portfolio/functions/account_source.py) y
    PolymarketBroker (execution/functions/broker.py). Los adapters delegan aquí.
    """

    def __init__(
        self,
        *,
        live: bool = False,
        private_key: str | None = None,
        funder: str | None = None,
    ) -> None:
        self.private_key = private_key or os.getenv("POLYMARKET_PRIVATE_KEY") or None
        self.funder = funder or os.getenv("POLYMARKET_FUNDER") or None
        self._client = None
        self._pub_client = None  # PublicClient del SDK (inyectable en tests)

        env_live = os.getenv("POLYMARKET_LIVE", "") in ("1", "true", "yes", "on")
        valid_signer = is_evm_private_key(self.private_key)
        self.live = bool(live and env_live and valid_signer and not _kill_switch_on())
        self._blocked_reason: str | None = None
        if live and not self.live:
            if _kill_switch_on():
                self._blocked_reason = "kill_switch"
            elif not env_live:
                self._blocked_reason = "POLYMARKET_LIVE!=1"
            elif not self.private_key:
                self._blocked_reason = "sin POLYMARKET_PRIVATE_KEY"
            elif not valid_signer:
                self._blocked_reason = "POLYMARKET_PRIVATE_KEY inválida"

    # ── conexión (lazy) ───────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            self._client = build_secure_client(
                private_key=self.private_key or None, funder=self.funder
            )
        except Exception as exc:  # PolymarketClientError, UserInputError, red, etc.
            raise AccountUnavailableError(
                f"No se pudo conectar la cuenta live: {type(exc).__name__}: {exc}"
            ) from exc
        return self._client

    # ── cuenta (read-only) ────────────────────────────────────────────────────

    def balance(self) -> AccountBalance:
        client = self._ensure_client()
        ba = client.get_balance_allowance(asset_type="COLLATERAL")
        return AccountBalance(
            usdc_balance=to_decimal(ba.balance) / _USDC_DECIMALS,
            as_of=utcnow(),
            address=getattr(client, "wallet", None),
        )

    def positions(self) -> list[LivePosition]:
        client = self._ensure_client()
        out: list[LivePosition] = []
        for p in client.list_positions(page_size=100).iter_items():
            out.append(LivePosition(
                condition_id=str(p.condition_id),
                token_id=str(p.token_id) if p.token_id is not None else "",
                outcome=p.outcome or "",
                size_shares=to_decimal(p.size or 0),
                avg_entry_price=to_decimal(p.avg_price or 0),
                current_price=to_decimal(p.cur_price) if p.cur_price is not None else None,
                title=p.title,
                event_id=str(p.event_id) if p.event_id is not None else None,
            ))
        return out

    def open_orders(self) -> list[OpenOrder]:
        client = self._ensure_client()
        out: list[OpenOrder] = []
        for o in client.list_open_orders().iter_items():
            out.append(OpenOrder(
                order_id=str(o.id),
                condition_id=str(o.market),
                token_id=str(o.token_id),
                side=o.side,
                price=to_decimal(o.price or 0),
                size_shares=to_decimal(o.original_size or 0),
                size_matched=to_decimal(o.size_matched or 0),
                status=o.status,
                created_at=o.created_at,
            ))
        return out

    def closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]:
        client = self._ensure_client()
        out: list[ClosedPositionLive] = []
        pag = client.list_closed_positions(
            sort_by="TIMESTAMP", sort_direction="DESC", page_size=max(1, limit),
        )
        for c in pag.iter_items():
            out.append(ClosedPositionLive(
                condition_id=str(c.condition_id) if c.condition_id is not None else "",
                token_id=str(c.token_id) if c.token_id is not None else "",
                outcome=c.outcome or "",
                avg_price=to_decimal(c.avg_price or 0),
                realized_pnl=to_decimal(c.realized_pnl or 0),
                current_price=to_decimal(c.cur_price) if c.cur_price is not None else None,
                closed_at=c.timestamp,
                title=c.title,
                event_id=getattr(c, "event_slug", None),
            ))
            if len(out) >= limit:
                break
        return out

    # ── flujos de caja (para PnL que cuadra con la UI) ───────────────────────

    def trades(self) -> list[LiveTrade]:
        """Fills on-chain de la wallet (compras y ventas). Insumo del PnL cash-flow."""
        client = self._ensure_client()
        out: list[LiveTrade] = []
        for t in client.list_trades(page_size=500).iter_items():
            out.append(LiveTrade(
                side=str(t.side),
                size_shares=to_decimal(t.size or 0),
                price=to_decimal(t.price or 0),
                condition_id=str(t.condition_id) if t.condition_id is not None else "",
                outcome=getattr(t, "outcome", None),
                title=getattr(t, "title", None),
                timestamp=getattr(t, "timestamp", None),
            ))
        return out

    def redemptions(self) -> list[LiveRedemption]:
        """Eventos REDEEM de la wallet (cobros de mercados resueltos)."""
        client = self._ensure_client()
        out: list[LiveRedemption] = []
        for a in client.list_activity(page_size=500).iter_items():
            if str(getattr(a, "type", "")).upper() != "REDEEM":
                continue
            out.append(LiveRedemption(
                condition_id=str(a.condition_id) if a.condition_id is not None else "",
                amount=to_decimal(getattr(a, "amount", 0) or 0),
                title=getattr(a, "title", None),
                timestamp=getattr(a, "timestamp", None),
            ))
        return out

    # ── order book ───────────────────────────────────────────────────────────

    def best_ask(self, token_id: str) -> Decimal | None:
        """Mejor ask (precio de compra) del order book live. None si no se puede."""
        if not self.private_key:
            return None
        try:
            book = self._ensure_client().get_order_book(token_id=token_id)
        except Exception:  # noqa: BLE001 — pricing best-effort, nunca rompe
            return None
        asks = getattr(book, "asks", None) or []
        prices = [to_decimal(level.price) for level in asks]
        return min(prices) if prices else None

    # ── ejecución ────────────────────────────────────────────────────────────

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
            client = self._ensure_client()
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

    def cancel(self, order_id: str) -> OrderResult:
        """Cancela una orden abierta (dry-run salvo live)."""
        base = {"action": "cancel", "order_id": order_id}
        if not self.live:
            return OrderResult(
                order_id=order_id, status="dry_run", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "dry_run": True, "blocked_reason": self._blocked_reason},
            )
        try:
            resp = self._ensure_client().cancel_order(order_id=order_id)
            return OrderResult(
                order_id=order_id, status="cancelled", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "response": str(resp)[:500]},
            )
        except Exception as exc:  # noqa: BLE001
            return OrderResult(
                order_id=order_id, status="error", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "error": f"{type(exc).__name__}: {exc}"},
            )

    # ── descubrimiento de mercados (PublicClient — read-only) ─────────────────

    def _ensure_pub_client(self):
        """Lazy-init del PublicClient del SDK (descubrimiento, read-only, sin auth).

        Delega en `build_public_client()` (caché por proceso) en lugar de construir
        una instancia nueva cada vez. `self._pub_client` se mantiene para inyección
        en tests.
        """
        if self._pub_client is not None:
            return self._pub_client
        try:
            self._pub_client = build_public_client()
        except PolymarketClientError as exc:
            raise AccountUnavailableError(str(exc)) from exc
        return self._pub_client

    def find_match_markets(
        self,
        home: str,
        away: str,
        *,
        tag_ids: int | list[int] | None = None,
        closed: bool = False,
        page_size: int = 100,
    ) -> list[PolymarketMarket]:
        """Descubrir mercados de Polymarket para un partido home vs. away.

        Usa PublicClient.list_events (SDK oficial, sin Gamma requests) y aplica
        match_event() para encontrar los mercados "Will X win?" correspondientes.

        Args:
            home:     Nombre del equipo local.
            away:     Nombre del equipo visitante.
            tag_ids:  Tag(s) para filtrar eventos (ej: 102232 = WC 2026). None = sin filtro.
            closed:   Incluir eventos cerrados (default False).
            page_size: Tamaño de página en la paginación del SDK.

        Returns:
            Lista de PolymarketMarket con model_outcome HOME_WIN o AWAY_WIN.
        """
        pub = self._ensure_pub_client()
        kwargs: dict = {"closed": closed, "page_size": page_size}
        if tag_ids is not None:
            kwargs["tag_ids"] = tag_ids

        results: list[PolymarketMarket] = []
        for event in pub.list_events(**kwargs).iter_items():
            matches = match_event(event, home, away)
            if not matches:
                continue
            for info in matches:
                results.append(PolymarketMarket(
                    condition_id=info["condition_id"],
                    token_id=info["token_id"],
                    outcome="YES",
                    model_outcome=info["model_outcome"],
                    market_probability=info["yes_price"],
                    volume_usdc=info["volume"],
                    liquidity_usdc=info["liquidity"],
                    best_ask=info["best_ask"],
                    best_bid=info["best_bid"],
                    neg_risk=info["neg_risk"],
                    tick_size=info["tick_size"],
                    min_order_size=info["min_order_size"],
                    accepting_orders=info["accepting_orders"],
                    no_token_id=info.get("no_token_id"),
                    no_best_ask=info.get("no_best_ask"),
                    no_probability=info.get("no_price"),
                ))
        return results
