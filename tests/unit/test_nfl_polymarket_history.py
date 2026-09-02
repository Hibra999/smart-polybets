from datetime import UTC, datetime
from types import SimpleNamespace

from scripts.nfl_polymarket_history import match_contracts


def test_matches_only_full_game_moneyline_by_teams_and_kickoff():
    kickoff = datetime(2025, 9, 5, 0, 20, tzinfo=UTC)

    def market(slug):
        return SimpleNamespace(
            slug=slug,
            condition_id="condition",
            sports=SimpleNamespace(sports_market_type="moneyline", game_start_time=kickoff),
            outcomes=SimpleNamespace(
                yes=SimpleNamespace(label="Cowboys", token_id="away-token"),
                no=SimpleNamespace(label="Eagles", token_id="home-token"),
            ),
            trading=SimpleNamespace(fees_enabled=False),
        )

    event = SimpleNamespace(
        markets=[
            market("nfl-phi-dal-2025-09-04"),
            market("nfl-phi-dal-2025-09-04-1h-moneyline"),
        ]
    )
    fixtures = [
        {
            "id": "2025_01_DAL_PHI",
            "week_id": "2025_REG_w1",
            "home_team_id": "PHI",
            "away_team_id": "DAL",
            "kickoff_utc": kickoff.isoformat(),
        }
    ]

    assert match_contracts([event], fixtures) == [
        {
            "fixture_id": "2025_01_DAL_PHI",
            "season": "2025",
            "kickoff_utc": kickoff.isoformat(),
            "home_team_id": "PHI",
            "away_team_id": "DAL",
            "condition_id": "condition",
            "home_token_id": "home-token",
            "away_token_id": "away-token",
            "snapshot_utc": "",
            "home_price_t24h": "",
            "fees_enabled": False,
        }
    ]
