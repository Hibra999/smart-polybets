"""Ledger de trades del agente. Función pura.

Clasifica las decisiones (del estado local o del Django App) en:
  - pendientes  : recomendadas, esperando aprobación humana (REVIEW / approved).
  - abiertas    : ejecutadas sobre un partido que aún no termina.
  - cerradas    : ejecutadas sobre un partido terminado → PnL asentado.

No lee la DB ni el estado: recibe las decisiones y un mapa de resultados de
fixtures (`results[event_id] -> {status, home_team_id, away_team_id, winner_team_id}`).
El PnL no realizado requiere precio live y no se calcula aquí (lo deja en None).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.utils import to_decimal

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"

WON = "WON"
LOST = "LOST"
OPEN = "OPEN"
UNGRADED = "UNGRADED"  # ejecutada pero no se puede asentar (falta el lado del pick)


def settle_pnl(size: Decimal, entry_price: Decimal | None, outcome: str) -> Decimal:
    """PnL asentado de una posición binaria comprada a `entry_price` (0-1).

    Ganada: shares = size/precio, payout = shares*1 → pnl = size*(1-precio)/precio.
    Perdida: se pierde todo el stake → pnl = -size.
    """
    if outcome == LOST:
        return -size
    if outcome == WON and entry_price and entry_price > 0:
        return size * (Decimal("1") - entry_price) / entry_price
    return Decimal("0")


def _entry_price(dec: dict) -> Decimal | None:
    """Precio de entrada: avg_price ejecutado > raw.price > best_ask de la señal."""
    res = dec.get("order_result") or {}
    if res.get("avg_price") is not None:
        return to_decimal(res["avg_price"])
    raw = res.get("raw") or {}
    if raw.get("price") is not None:
        return to_decimal(raw["price"])
    opp = dec.get("opportunity_json") or {}
    if opp.get("best_ask") is not None:
        return to_decimal(opp["best_ask"])
    return None


def _size(dec: dict) -> Decimal:
    res = dec.get("order_result") or {}
    if res.get("filled_size_usdc") is not None:
        return to_decimal(res["filled_size_usdc"])
    return to_decimal(dec.get("recommended_size", 0))


def _pick_side(dec: dict) -> str | None:
    return dec.get("pick_side") or (dec.get("opportunity_json") or {}).get("model_outcome")


def _base_row(dec: dict) -> dict[str, Any]:
    opp = dec.get("opportunity_json") or {}
    home = opp.get("participant_home", "?")
    away = opp.get("participant_away", "?")
    side = _pick_side(dec)
    pick = dec.get("pick_participant")
    if not pick:
        pick = home if side == HOME_WIN else away if side == AWAY_WIN else opp.get("outcome", "?")
    return {
        "key": (dec.get("idempotency_key") or "")[:10],
        "event_id": opp.get("event_id"),
        "match": f"{home} vs {away}",
        "pick": pick,
        "pick_side": side,
        "size": _size(dec),
        "entry_price": _entry_price(dec),
        "edge": to_decimal(dec.get("edge", 0)),
        "strategy": dec.get("strategy_id", ""),
        "event_start": opp.get("event_start_utc"),
        "verdict": dec.get("verdict"),
    }


def _grade_executed(dec: dict, results: dict[str, dict]) -> dict[str, Any]:
    row = _base_row(dec)
    # Resolución EXPLÍCITA (backfills / mercados no-winner como O/U, que no pueden
    # asentarse contra winner_team_id): {"outcome": "WON"|"LOST", "pnl": opcional}.
    explicit = dec.get("resolution") or {}
    if explicit.get("outcome") in (WON, LOST):
        row["outcome"] = explicit["outcome"]
        row["pnl"] = (to_decimal(explicit["pnl"]) if explicit.get("pnl") is not None
                      else settle_pnl(row["size"], row["entry_price"], row["outcome"]))
        return row
    fx = results.get(row["event_id"]) or {}
    row["status_db"] = fx.get("status")
    if fx.get("status") != "finished":
        row["outcome"] = OPEN
        row["pnl"] = Decimal("0")
        return row
    side = row["pick_side"]
    if side not in (HOME_WIN, AWAY_WIN):
        row["outcome"] = UNGRADED
        row["pnl"] = Decimal("0")
        return row
    picked_team_id = fx.get("home_team_id") if side == HOME_WIN else fx.get("away_team_id")
    winner = fx.get("winner_team_id")
    row["outcome"] = WON if (winner is not None and winner == picked_team_id) else LOST
    row["pnl"] = settle_pnl(row["size"], row["entry_price"], row["outcome"])
    return row


def build_ledger(
    decisions: list[dict],
    results: dict[str, dict],
    *,
    bankroll: Decimal | float = 0,
) -> dict[str, Any]:
    """Construye el ledger completo a partir de decisiones + resultados de fixtures."""
    bankroll = to_decimal(bankroll)
    open_pos: list[dict] = []
    closed: list[dict] = []
    pending: list[dict] = []

    for dec in decisions:
        if dec.get("status") == "executed":
            row = _grade_executed(dec, results)
            (open_pos if row["outcome"] in (OPEN, UNGRADED) else closed).append(row)
        else:
            pending.append(_base_row(dec))

    realized = sum((r["pnl"] for r in closed), Decimal("0"))
    wins = sum(1 for r in closed if r["outcome"] == WON)
    losses = sum(1 for r in closed if r["outcome"] == LOST)
    staked_open = sum((r["size"] for r in open_pos), Decimal("0"))
    pending_size = sum((r["size"] for r in pending), Decimal("0"))
    decided = wins + losses

    summary = {
        "bankroll": bankroll,
        "realized_pnl": realized,
        "staked_open": staked_open,
        "pending_size": pending_size,
        "n_open": len(open_pos),
        "n_closed": len(closed),
        "n_pending": len(pending),
        "wins": wins,
        "losses": losses,
        "win_rate": (wins / decided) if decided else 0.0,
        "roi": float(realized / bankroll) if bankroll else 0.0,
        "equity": bankroll + realized,
    }
    # Orden: más recientes/próximos primero por event_start.
    _key = lambda r: r.get("event_start") or ""
    return {
        "summary": summary,
        "open": sorted(open_pos, key=_key),
        "closed": sorted(closed, key=_key, reverse=True),
        "pending": sorted(pending, key=_key),
    }
