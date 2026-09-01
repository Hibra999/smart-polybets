"""E2E del workflow full_analysis con la estrategia draft de Liga MX.

Sin red: DATA_ROOT seeded (con partidos jugados → warmup OK) + DjangoClient falso +
market_source inyectado. Los casos de análisis habilitan draft sólo en dry-run.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from agent.workflows import full_analysis, post_event_review, quick_scan
from core.exceptions import NoActiveStrategyError
from execution.functions import PolymarketBroker
from research.functions.market_scanner import PolymarketMarket


def _market_source(market_prob="0.40", outcome="HOME_WIN"):
    def source(prediction):
        return [
            PolymarketMarket(
                condition_id="cond_1", token_id="tok_1", outcome="YES",
                model_outcome=outcome, market_probability=Decimal(market_prob),
                volume_usdc=Decimal("6000"), liquidity_usdc=Decimal("8000"),
            )
        ]
    return source


def test_full_analysis_auto(seeded_data_root, fake_client):
    # AME favorito (ganó 2 partidos) vs mercado 0.40 → edge alto → AUTO.
    # Broker default = dry-run → la decisión queda `simulated`, NUNCA `executed`
    # (el bug de 2026-07-09 marcaba executed en dry-run y bloqueaba el run real).
    decisions = full_analysis.run(
        "m1", "liga_mx_2026",
        client=fake_client, market_source=_market_source("0.40"),
        allow_draft=True,
    )
    assert len(decisions) == 1
    assert decisions[0]["mode"] == "AUTO"
    assert fake_client.saved
    assert not fake_client.executed
    assert fake_client.simulated
    assert fake_client.simulated[0][1]["status"] == "dry_run"


def test_full_analysis_review_with_flag(seeded_data_root, fake_client):
    decisions = full_analysis.run(
        "m1", "liga_mx_2026",
        client=fake_client, market_source=_market_source("0.40"),
        qualitative_flags=["QR-002: lesión reportada"],
        allow_draft=True,
    )
    assert decisions[0]["mode"] == "REVIEW"
    assert "TRADE REVIEW REQUEST" in decisions[0]["report"]
    assert not fake_client.executed


def test_full_analysis_discard_negative_edge(seeded_data_root, fake_client):
    # mercado 0.95 > prob del modelo → edge negativo → DISCARD.
    decisions = full_analysis.run(
        "m1", "liga_mx_2026",
        client=fake_client, market_source=_market_source("0.95"),
        allow_draft=True,
    )
    assert decisions[0]["mode"] == "DISCARD"


def test_full_analysis_picks_home_side(seeded_data_root, fake_client):
    # Si sólo hay mercado del lado AWAY (CAZ), la estrategia (que elige HOME=AME)
    # no encuentra mercado para su lado → no genera oportunidad.
    decisions = full_analysis.run(
        "m1", "liga_mx_2026",
        client=fake_client, market_source=_market_source("0.40", outcome="AWAY_WIN"),
        allow_draft=True,
    )
    assert decisions == []


def test_quick_scan_sorts_by_edge(seeded_data_root, fake_client):
    opps = quick_scan.run(
        client=fake_client,
        active_tournaments=[{"tournament_id": "liga_mx_2026"}],
        event_ids_by_tournament={"liga_mx_2026": ["m1"]},
        market_source=_market_source("0.40"),
        allow_draft=True,
    )
    assert len(opps) == 1
    assert opps[0].outcome == "YES"
    assert opps[0].edge > Decimal("0")


def test_post_event_review_builds_digest(seeded_data_root):
    out = post_event_review.run("m1", "liga_mx_2026", decisions=[], save=False)
    assert "Post-Event Review" in out["report"]
    assert out["digest"].total_bets == 0


def test_full_analysis_with_real_odds_source(seeded_data_root, fake_client):
    # Usa las cuotas reales migradas (SqliteOddsSource) en vez de un market_source
    # sintético: AME@0.30 en el mercado vs modelo ~0.64 → edge alto → AUTO.
    from research.functions import SqliteOddsSource

    source = SqliteOddsSource("liga_mx_2026", source="polymarket",
                              data_root=str(seeded_data_root))
    decisions = full_analysis.run(
        "m1", "liga_mx_2026", client=fake_client, market_source=source,
        allow_draft=True,
    )
    assert len(decisions) == 1
    assert decisions[0]["mode"] == "AUTO"


def test_full_analysis_blocks_draft_by_default(fake_client):
    with pytest.raises(NoActiveStrategyError, match="No hay estrategia aprobada"):
        full_analysis.run("lmx_001", "liga_mx_2026", client=fake_client)


def test_full_analysis_allows_draft_with_dry_run(monkeypatch, fake_client):
    monkeypatch.setattr(full_analysis.research_tools, "scan_event", lambda *args, **kwargs: [])

    decisions = full_analysis.run(
        "lmx_001", "liga_mx_2026", client=fake_client,
        broker=PolymarketBroker(live=False), allow_draft=True,
    )

    assert decisions == []


def test_full_analysis_rejects_live_broker_for_draft(fake_client):
    with pytest.raises(NoActiveStrategyError, match="sólo dry-run"):
        full_analysis.run(
            "lmx_001", "liga_mx_2026", client=fake_client,
            broker=SimpleNamespace(live=True), allow_draft=True,
        )
