"""The files the update produces: ratings.csv and the data behind the dashboard."""
import json

import pandas as pd

from .config import CONFIG
from .elo import MODEL
from .evaluation import EVALUATION, model_record
from .simulation import SIMULATION, SETS_TO_WIN


def ratings_table(df, ratings, names):
    """Current teams, strongest first."""
    current = df[df.season == df.season.max()]
    in_league = set(current.home_id) | set(current.away_id)
    table = pd.DataFrame(ratings.items(), columns=["team_id", "elo"])
    table = table[table.team_id.isin(in_league)].assign(team=lambda d: d.team_id.map(names))
    return table.sort_values("elo", ascending=False)[["team_id", "team", "elo"]].round({"elo": 1}).reset_index(drop=True)


def fixture_names(df):
    """Each team's name in its latest match of the current season, sponsor included, exactly as the source wrote it."""
    current = df[df.season == df.season.max()]
    columns = ["date", "match_id", "team", "name"]
    appearances = pd.concat([
        current[["date", "match_id", f"{side}_id", f"{side}_name (source)"]].set_axis(columns, axis=1)
        for side in ("home", "away")
    ])
    latest = appearances.sort_values(["date", "match_id"], kind="stable").groupby("team").name.last()
    return latest.sort_index().to_dict()


def recent_form(games, team_ids, names):
    """Each team's latest results, oldest first, with the team's own sets first in the score."""
    form = {}
    for team in team_ids:
        played = games[(games.home_id == team) | (games.away_id == team)].tail(CONFIG["dashboard"]["form_matches"])
        form[team] = []
        for m in played.itertuples():
            at_home = m.home_id == team
            own, other = (m.home_sets, m.away_sets) if at_home else (m.away_sets, m.home_sets)
            form[team].append({"won": bool(own > other), "score": f"{own}-{other}",
                               "opponent": names[m.away_id if at_home else m.home_id]})
    return form


def head_to_head(games, team_ids):
    """Wins between each pair of teams, keyed by the two ids in alphabetical order."""
    records = {}
    for m in games[games.home_id.isin(team_ids) & games.away_id.isin(team_ids)].itertuples():
        first, second = sorted((m.home_id, m.away_id))
        wins = records.setdefault(f"{first}-{second}", {first: 0, second: 0})
        wins[m.home_id if m.home_sets > m.away_sets else m.away_id] += 1
    return dict(sorted(records.items()))


def dashboard_data(df, games, table, names):
    season = df.season.max()
    team_ids = table.team_id.tolist()
    full_names = fixture_names(df)
    return {
        "season": season,
        "lastMatch": df[df.season == season].date.max().date().isoformat(),
        "teams": [{"id": t.team_id, "name": t.team, "fullName": full_names.get(t.team_id, t.team), "elo": t.elo}
                  for t in table.itertuples()],
        "homeAdvantage": MODEL["H"],
        "scale": MODEL["S"],
        "newTeamRating": MODEL["start"] + MODEL["promoted"],
        "setsToWin": SETS_TO_WIN,
        "scorelines": [{"home": line["home"], "away": line["away"], "score": line["score"],
                        "points": line["league_points"]} for line in CONFIG["scoring"]["scorelines"]],
        "nSims": SIMULATION["n_sims"],
        "seed": SIMULATION["seed"],
        "cautionThreshold": EVALUATION["caution_threshold"],
        "record": model_record(games),
        "form": recent_form(games, team_ids, names),
        "headToHead": head_to_head(games, team_ids),
        "historyStart": df.season.min(),
    }


def dashboard_script(data):
    """A script rather than JSON, because browsers block fetch on a file opened by double-click."""
    return "window.DASHBOARD_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
