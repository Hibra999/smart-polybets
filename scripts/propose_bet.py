#!/usr/bin/env python
"""Proponer una apuesta manual (CIO override) COMO DECISIÓN DEL PIPELINE.

Reemplaza a los scripts manuales ad-hoc (place_totals_qf/place_winner_sf): la
apuesta pasa por el motor de riesgo (edge/volumen/drawdown/horas/exposure), queda
en el ledger con idempotency key, y se coloca con la ruta confiable de aprobación:

    # 1. proponer (NO coloca nada; guarda una Decision REVIEW)
    python scripts/propose_bet.py --market "Will Spain win on 2026-07-14?" \
        --stake 12 --model-prob 0.379 --reason "Poisson corregido vs ask 0.30"

    # 2. colocar (gates live + confirmación tipeada del monto)
    python scripts/orders.py --approve <key> --live --confirm <monto>

`--market` matchea por texto exacto o substring ÚNICO contra las questions de los
mercados abiertos del torneo (venue.discovery). `--outcome no` compra el lado NO.

Diseño: docs/superpowers/specs/2026-07-14-cio-override-lane-design.md
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()
load_env(Path(__file__).resolve().parent.parent / ".env")

from agent.tools.override_tools import (
    OVERRIDE_STRATEGY_ID,
    OVERRIDE_STRATEGY_VERSION,
    propose_override,
)
from core.local_state import LocalStateClient
from core.utils import to_decimal, utcnow
from execution.functions.broker import PolymarketBroker
from research.schemas.market_opportunity import MarketOpportunity
from tournaments.registry import load_active_strategy
from venue.discovery import match_events

TID = "fifa_world_cup_2026"


def find_market(query: str) -> tuple[dict, object] | None:
    """Mercado abierto cuya question matchea exacto o por substring único."""
    hits: list[tuple[dict, object]] = []
    for me in match_events(closed=False):
        for m in me.event.markets:
            d = m.model_dump()
            q = d.get("question") or ""
            if q == query:
                return d, me
            if query.lower() in q.lower():
                hits.append((d, me))
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"  '{query}' es ambiguo ({len(hits)} mercados):")
        for d, _ in hits[:10]:
            print(f"    - {d.get('question')}")
    return None


def build_opportunity(d: dict, me, *, outcome_key: str, model_prob: Decimal,
                      market_type: str, broker: PolymarketBroker) -> MarketOpportunity:
    o = (d.get("outcomes") or {}).get(outcome_key, {})
    token = str(o.get("token_id", ""))
    ask = broker.best_ask(token)
    price = to_decimal(ask) if ask is not None else to_decimal(o.get("price"))
    trading = d.get("trading") or {}
    metrics = d.get("metrics") or {}
    kickoff = me.kickoff
    now = utcnow()
    hours = (kickoff - now).total_seconds() / 3600.0 if kickoff else 0.0
    return MarketOpportunity(
        polymarket_condition_id=d.get("condition_id") or "",
        polymarket_token_id=token,
        outcome=outcome_key.upper(),
        tournament_id=TID,
        sport="football",
        event_id=str(getattr(me.event, "id", "") or d.get("id", "")),
        market_type=market_type,
        strategy_id=OVERRIDE_STRATEGY_ID,
        model_probability=model_prob,
        market_probability=price,
        edge=model_prob - price,
        participant_home=me.home_disp,
        participant_away=me.away_disp,
        event_start_utc=kickoff,
        hours_to_event=hours,
        event_phase="playoff",
        market_volume_usdc=to_decimal(metrics.get("volume") or 0),
        market_liquidity_usdc=to_decimal(metrics.get("liquidity") or 0),
        model_version="cio-judgment",
        model_confidence="MEDIUM",
        sample_size=0,
        best_ask=price,
        neg_risk=bool((getattr(me.event, "trading", None) or {}) and me.event.trading.neg_risk),
        tick_size=to_decimal(trading.get("minimum_tick_size") or "0.001"),
        min_order_size=to_decimal(trading.get("minimum_order_size") or 0) or None,
        generated_at=now,
        strategy_version=OVERRIDE_STRATEGY_VERSION,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Proponer apuesta manual (CIO override) → Decision REVIEW.")
    ap.add_argument("--market", required=True, help="question del mercado (exacta o substring único)")
    ap.add_argument("--stake", required=True, type=float, help="monto USDC decidido por el CIO")
    ap.add_argument("--model-prob", required=True, type=float,
                    help="prob. del modelo/juicio que justifica la apuesta (0-1)")
    ap.add_argument("--reason", required=True, help="justificación (queda en el ledger)")
    ap.add_argument("--outcome", default="yes", choices=["yes", "no"])
    ap.add_argument("--market-type", default="manual")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="evalúa riesgo y muestra la decisión SIN persistir en el ledger")
    a = ap.parse_args()

    strategy = load_active_strategy(TID)
    if strategy is None:
        print("No hay estrategia activa (se necesitan sus límites de riesgo).")
        return
    client = LocalStateClient(a.state, bankroll_usdc=a.bankroll)
    broker = PolymarketBroker(live=False)  # solo lectura de best_ask; NO coloca

    found = find_market(a.market)
    if not found:
        print(f"  mercado no encontrado (abierto): {a.market}")
        return
    d, me = found

    opp = build_opportunity(d, me, outcome_key=a.outcome,
                            model_prob=to_decimal(a.model_prob),
                            market_type=a.market_type, broker=broker)
    print(f"\n  {d.get('question')}  [{a.outcome.upper()}]")
    print(f"  ask={opp.best_ask}  model={opp.model_probability}  edge={opp.edge:+.4f}"
          f"  stake=${a.stake}  kickoff={opp.event_start_utc}")

    if a.dry_run:
        class _NoWrite:
            """Cliente de solo-lectura: idempotencia/estado reales, save descartado."""
            def __getattr__(self, name):
                if name == "save_decision":
                    return lambda payload: {**payload, "note": "dry-run: NO guardado"}
                return getattr(client, name)
        res = propose_override(opp, stake_usdc=to_decimal(a.stake), reason=a.reason,
                               client=_NoWrite(), strategy=strategy)
        print("  (dry-run: nada persistido)")
    else:
        res = propose_override(opp, stake_usdc=to_decimal(a.stake), reason=a.reason,
                               client=client, strategy=strategy)
    mode = res["mode"]
    key = res["idempotency_key"]
    if mode == "REVIEW":
        estado = "pasaría a REVIEW (dry-run, NO guardada)" if a.dry_run \
            else "decisión guardada en el ledger"
        print(f"\n  [REVIEW] {estado} — key: {key}")
        if not a.dry_run:
            print(f"  Siguiente paso (coloca con gates + confirmación):")
            print(f"    python scripts/orders.py --approve {key[:10]} --live --confirm {to_decimal(a.stake):.2f}")
    elif mode == "DISCARD":
        print(f"\n  [DISCARD] el motor de riesgo la bloqueó (nada guardado):")
        for r in res.get("reasons", []):
            print(f"    - {r}")
    else:
        print(f"\n  [SKIP] {res.get('reason')}")


if __name__ == "__main__":
    main()
