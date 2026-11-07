"""Set and match probabilities. Elo gives an expected score on the S_MAP scale, not a win
probability, so first find the per-set win probability that produces that expected score."""
from math import comb

import numpy as np
import pandas as pd

from .config import CONFIG
from .elo import MODEL, S_MAP, expected_score

SETS_TO_WIN = CONFIG["scoring"]["sets_to_win"]
MAX_SETS = 2 * SETS_TO_WIN - 1
SCORELINES = list(S_MAP)
HOME_WINS = [i for i, (home, _) in enumerate(SCORELINES) if home == SETS_TO_WIN]
SIMULATION = CONFIG["simulation"]


def scoreline_probability(home, away, p_set):
    q = 1 - p_set
    if home == SETS_TO_WIN:
        return comb(SETS_TO_WIN - 1 + away, away) * p_set**home * q**away
    return comb(SETS_TO_WIN - 1 + home, home) * p_set**home * q**away


def expected_score_of_set_probability(p_set):
    return sum(scoreline_probability(h, a, p_set) * S_MAP[h, a] for h, a in SCORELINES)


P_SET_GRID = np.linspace(0.001, 0.999, 999)
EXPECTED_GRID = expected_score_of_set_probability(P_SET_GRID)


def set_probability(e):
    return np.interp(e, EXPECTED_GRID, P_SET_GRID)


def win_probability(e):
    """Exact chance that the home team wins the match, for an expected score e."""
    p_set = set_probability(e)
    return sum(scoreline_probability(*SCORELINES[i], p_set) for i in HOME_WINS)


def simulate_match(home, away, ratings, H=MODEL["H"], S=MODEL["S"], n_sims=SIMULATION["n_sims"], seed=None):
    p_set = set_probability(expected_score(ratings[home], ratings[away], H, S))

    # play every set per simulation, then cut each match off at the set where a team reaches the target
    rng = np.random.default_rng(seed)
    home_takes_set = rng.random((n_sims, MAX_SETS)) < p_set
    home_sets = home_takes_set.cumsum(axis=1)
    away_sets = (~home_takes_set).cumsum(axis=1)
    last_set = ((home_sets == SETS_TO_WIN) | (away_sets == SETS_TO_WIN)).argmax(axis=1)
    rows = np.arange(n_sims)
    final_home, final_away = home_sets[rows, last_set], away_sets[rows, last_set]

    scorelines = pd.Series({f"{h}-{a}": np.mean((final_home == h) & (final_away == a))
                            for h, a in SCORELINES})
    return {"home_win": np.mean(final_home == SETS_TO_WIN), "p_set": p_set, "scorelines": scorelines}
