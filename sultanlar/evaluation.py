"""How well the model has done on past matches."""
import pandas as pd

from .config import CONFIG
from .simulation import win_probability

EVALUATION = CONFIG["evaluation"]


def group_record(predicted, won):
    if predicted.empty:
        return None
    return {"matches": int(len(predicted)), "predicted": float(predicted.mean()), "actual": float(won.mean())}


def model_record(games):
    """Accuracy, plus how the simulated win chances held up at both extremes."""
    seasons = sorted(games.season.unique())
    tested = games[games.season.isin(seasons[EVALUATION["burn_in_seasons"]:])]
    home_won = tested.home_sets > tested.away_sets
    win_chance = pd.Series(win_probability(tested.p_home), index=tested.index)
    threshold = EVALUATION["caution_threshold"]
    high, low = win_chance > threshold, win_chance < 1 - threshold
    return {
        "matches": int(len(tested)),
        "accuracy": float(((tested.p_home > 0.5) == home_won).mean()),
        "firstSeason": tested.season.min(),
        "lastSeason": tested.season.max(),
        "high": group_record(win_chance[high], home_won[high]),
        "low": group_record(win_chance[low], home_won[low]),
    }
