"""Loading, checking and saving match and team data."""
import os

import pandas as pd

from .config import CONFIG, project_path

VALID_SCORES = {(line["home"], line["away"]) for line in CONFIG["scoring"]["scorelines"]}


def load_teams():
    return pd.read_csv(project_path("teams"), encoding="utf-8").set_index("team_id")


def team_names():
    return load_teams()["name"]


def load_active_matches():
    path = project_path("active_matches")
    return pd.read_csv(path, encoding="utf-8") if path.exists() else pd.DataFrame()


def load_matches(active=None):
    """The workbook plus the active season, in the same columns."""
    history = pd.read_excel(project_path("history"), sheet_name="matches")
    active = load_active_matches() if active is None else active
    if active.empty:
        return history
    return pd.concat([history, active.assign(date=pd.to_datetime(active.date))], ignore_index=True)


def merge_matches(old, new):
    """Newer results win. Matches that drop off the TVF page are kept."""
    if new.empty:
        return old
    merged = new if old.empty else pd.concat([old, new]).drop_duplicates("match_id", keep="last")
    # each pairing happens once per regular season, so a repeat means TVF renumbered its matches
    regular = merged[merged.phase == "regular"]
    repeats = regular[regular.duplicated(["season", "home_id", "away_id"], keep=False)]
    if not repeats.empty:
        raise ValueError(f"Same regular-season match twice: {repeats.match_id.tolist()}")
    return merged.sort_values(["date", "match_id"]).reset_index(drop=True)


def validate_matches(df, teams):
    """Stop before anything is saved if the combined data cannot be right."""
    if df.match_id.duplicated().any():
        raise ValueError(f"Duplicate match ids: {df.match_id[df.match_id.duplicated()].tolist()}")
    unknown = (set(df.home_id) | set(df.away_id)) - set(teams.index)
    if unknown:
        raise ValueError(f"Teams missing from teams.csv: {sorted(unknown)}")
    same_team = df[df.home_id == df.away_id]
    if not same_team.empty:
        raise ValueError(f"Team playing itself: {same_team.match_id.tolist()}")
    rated = df[df.use_for_elo == "Y"]
    scores = zip(rated.home_sets, rated.away_sets)
    bad = [m for m, score in zip(rated.match_id, scores) if score not in VALID_SCORES]
    if bad:
        raise ValueError(f"Scores the model cannot rate: {bad}")


def write_text(path, text):
    """Write to a temporary file first, so a crash never leaves a half-written file."""
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as file:
        file.write(text)
    os.replace(temporary, path)
