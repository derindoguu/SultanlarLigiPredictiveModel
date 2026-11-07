"""The Elo model."""
import numpy as np

from .config import CONFIG

MODEL = CONFIG["model"]
S_MAP = {(line["home"], line["away"]): line["score"] for line in CONFIG["scoring"]["scorelines"]}


def expected_score(home_elo, away_elo, H=MODEL["H"], S=MODEL["S"]):
    """Expected match score on the S_MAP scale. This is not a win probability."""
    return 1 / (1 + 10 ** ((away_elo - (home_elo + H)) / S))


def run_elo(df, K=MODEL["K"], H=MODEL["H"], S=MODEL["S"], start=MODEL["start"],
            promoted=MODEL["promoted"], revert=MODEL["revert"]):
    games = df[df.use_for_elo == "Y"].sort_values(["date", "match_id"], kind="stable").copy()
    first_season = games.season.iloc[0]
    ratings = {}
    season = None
    pre_home, pre_away, probs = [], [], []
    for m in games.itertuples():
        # new season: pull every rating part of the way back to the league average
        if m.season != season:
            if ratings:
                mean = np.mean(list(ratings.values()))
                ratings = {t: mean + (r - mean) * (1 - revert) for t, r in ratings.items()}
            season = m.season
        # teams in the first season start at 1500, promoted teams start lower
        init = start if season == first_season else start + promoted
        rh = ratings.get(m.home_id, init)
        ra = ratings.get(m.away_id, init)
        e = expected_score(rh, ra, H, S)
        pre_home.append(rh); pre_away.append(ra); probs.append(e)   # store BEFORE update
        s = S_MAP[(m.home_sets, m.away_sets)]
        d = K * (s - e)
        ratings[m.home_id] = rh + d
        ratings[m.away_id] = ra - d
    games["elo_home"], games["elo_away"], games["p_home"] = pre_home, pre_away, probs
    return games, ratings
