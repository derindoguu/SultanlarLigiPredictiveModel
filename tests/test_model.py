import numpy as np
import pandas as pd
import pytest

from sultanlar.config import CONFIG
from sultanlar.data import load_matches, load_teams
from sultanlar.elo import expected_score, run_elo
from sultanlar.evaluation import model_record
from sultanlar.outputs import dashboard_data, dashboard_script, fixture_names, head_to_head, ratings_table, recent_form
from sultanlar.simulation import (expected_score_of_set_probability, scoreline_probability, set_probability,
                                  simulate_match, win_probability, SCORELINES)

HISTORY_SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]


@pytest.fixture(scope="module")
def df():
    return load_matches()


def test_ratings_on_the_workbook_are_unchanged(df):
    """The ratings the notebook gave at the end of 2025-26, before any refactoring."""
    _, ratings = run_elo(df[df.season.isin(HISTORY_SEASONS)])
    assert ratings["VAK"] == pytest.approx(1958.207726, abs=1e-5)
    assert ratings["BAH"] == pytest.approx(1052.277978, abs=1e-5)


def test_ratings_only_move_between_the_two_teams(df):
    _, ratings = run_elo(df[df.season == "2021-22"])
    assert np.mean(list(ratings.values())) == pytest.approx(1500)


def test_equal_teams_on_neutral_ground():
    assert expected_score(1500, 1500, H=0) == 0.5
    assert win_probability(0.5) == pytest.approx(0.5, abs=1e-3)


def test_scoreline_probabilities_sum_to_one():
    for p_set in (0.1, 0.5, 0.9):
        assert sum(scoreline_probability(h, a, p_set) for h, a in SCORELINES) == pytest.approx(1)


def test_set_probability_inverts_expected_score():
    assert expected_score_of_set_probability(set_probability(0.7)) == pytest.approx(0.7, abs=1e-4)


def test_simulation_matches_the_exact_probability():
    ratings = {"A": 1700, "B": 1600}
    result = simulate_match("A", "B", ratings, seed=1)
    assert result["home_win"] == pytest.approx(win_probability(expected_score(1700, 1600)), abs=0.01)
    assert result["scorelines"].sum() == pytest.approx(1)


def test_simulation_is_reproducible():
    ratings = {"A": 1700, "B": 1600}
    assert simulate_match("A", "B", ratings, seed=7)["home_win"] == simulate_match("A", "B", ratings, seed=7)["home_win"]


def test_outputs_are_identical_on_every_run(df):
    def build():
        games, ratings = run_elo(df)
        table = ratings_table(df, ratings, load_teams()["name"])
        return dashboard_script(dashboard_data(df, games, table, load_teams()["name"]))
    assert build() == build()


def test_dashboard_data_describes_the_latest_season(df):
    games, ratings = run_elo(df)
    table = ratings_table(df, ratings, load_teams()["name"])
    data = dashboard_data(df, games, table, load_teams()["name"])
    assert data["season"] == df.season.max()
    elos = [team["elo"] for team in data["teams"]]
    assert elos == sorted(elos, reverse=True)
    assert all(team["name"] == team["name"] and team["name"] for team in data["teams"])


def test_model_record_covers_seasons_after_the_burn_in(df):
    games, _ = run_elo(df)
    record = model_record(games)
    assert record["firstSeason"] == sorted(games.season.unique())[1]
    assert 0.5 < record["accuracy"] < 1
    assert record["high"]["matches"] > 0 and record["low"]["matches"] > 0


def test_model_record_copes_with_no_extreme_matches():
    games = pd.DataFrame({"season": ["2021-22", "2022-23"], "home_sets": [3, 3], "away_sets": [0, 1], "p_home": [0.55, 0.55]})
    record = model_record(games)
    assert record["high"] is None and record["low"] is None


def played(*rows):
    columns = ["home_id", "away_id", "home_sets", "away_sets"]
    return pd.DataFrame(rows, columns=columns)


def test_recent_form_is_oldest_first_from_the_teams_side():
    games = played(("A", "B", 3, 0), ("C", "A", 3, 1))
    form = recent_form(games, ["A"], {"B": "Bee", "C": "Sea"})["A"]
    assert form == [{"won": True, "score": "3-0", "opponent": "Bee"}, {"won": False, "score": "1-3", "opponent": "Sea"}]


def test_recent_form_keeps_only_the_latest_matches():
    games = played(*[("A", "B", 3, 0)] * 8)
    assert len(recent_form(games, ["A"], {"B": "Bee"})["A"]) == CONFIG["dashboard"]["form_matches"]


def test_head_to_head_counts_both_venues_and_skips_old_teams():
    games = played(("B", "A", 3, 0), ("A", "B", 3, 2), ("A", "B", 0, 3), ("A", "Z", 3, 0))
    assert head_to_head(games, ["A", "B"]) == {"A-B": {"A": 1, "B": 2}}


def test_fixture_names_use_the_latest_match_of_the_current_season():
    df = pd.DataFrame({
        "season": ["2025-26", "2026-27", "2026-27"],
        "date": pd.to_datetime(["2026-03-01", "2026-10-03", "2026-10-10"]),
        "match_id": ["a", "b", "c"],
        "home_id": ["GS", "GS", "FEN"], "away_id": ["FEN", "FEN", "GS"],
        "home_name (source)": ["Galatasaray", "GALATASARAY", "FENERBAHÇE MEDICANA"],
        "away_name (source)": ["Fenerbahçe", "FENERBAHÇE", "GALATASARAY DAIKIN"],
    })
    assert fixture_names(df) == {"FEN": "FENERBAHÇE MEDICANA", "GS": "GALATASARAY DAIKIN"}
