from scripts.nfl_sota_experiment import build_rows


def _game(game_id, week, home_score, away_score):
    return {
        "id": game_id, "week_id": f"2025_REG_w{week}", "home_team_id": "KC",
        "away_team_id": "BUF", "home_score": home_score, "away_score": away_score,
        "moneyline_home": -120, "moneyline_away": 110,
    }


def _stats(game_id, kc_epa, buf_epa):
    common = {"defensive_epa_per_play": 0.0, "success_rate": 0.5,
              "explosive_play_rate": 0.1, "proe": 0.0}
    return {game_id: {
        "KC": {**common, "offensive_epa_per_play": kc_epa},
        "BUF": {**common, "offensive_epa_per_play": buf_epa},
    }}


def test_features_are_walk_forward_without_current_game_leakage():
    games = [_game(f"g{i}", i, 24, 17) for i in range(1, 6)]
    stats = {}
    for i in range(1, 6):
        stats.update(_stats(f"g{i}", 0.1 * i, -0.1 * i))
    rows = build_rows(games, stats)
    assert len(rows) == 1  # cuatro juegos de warmup, predice el quinto
    assert rows[0]["fixture_id"] == "g5"
    assert rows[0]["features"][4] > 0  # usa g1-g4; g5 se agrega después
