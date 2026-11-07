"""Reading the fixture from the TVF website."""
import html
import json
import logging
import re
import time
import urllib.error
import urllib.request

import pandas as pd

from .config import CONFIG

TVF = CONFIG["tvf"]
LEAGUE_POINTS = {(line["home"], line["away"]): line["league_points"] for line in CONFIG["scoring"]["scorelines"]}
MAX_SETS = 2 * CONFIG["scoring"]["sets_to_win"] - 1
REQUIRED_FIELDS = {"SEZON", "TARIH", "KUMEID", "TURID", "HAFTA", "MACNO", "ATAKIMI", "BTAKIMI",
                   "SETA", "SETB", "SONUCDURUMU", "HUKMEN"}
FINISHED = "K"

log = logging.getLogger(__name__)


def fetch_page():
    request = urllib.request.Request(TVF["url"], headers={"User-Agent": TVF["user_agent"]})
    for attempt in range(1, TVF["attempts"] + 1):
        try:
            with urllib.request.urlopen(request, timeout=TVF["timeout_seconds"]) as response:
                return response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == TVF["attempts"]:
                raise
            log.warning("TVF request failed (%s), attempt %d of %d", error, attempt, TVF["attempts"])
            time.sleep(TVF["retry_wait_seconds"] * attempt)


def unwrap(value):
    """Livewire stores every array as [value, {"s": "arr"}]."""
    if isinstance(value, list) and len(value) == 2 and isinstance(value[1], dict) and "s" in value[1]:
        return unwrap(value[0])
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    if isinstance(value, dict):
        return {k: unwrap(v) for k, v in value.items()}
    return value


def collect_rows(value, rows):
    if isinstance(value, dict):
        if "SEZON" in value and "TARIH" in value:
            rows.append(value)
        else:
            for v in value.values():
                collect_rows(v, rows)
    elif isinstance(value, list):
        for v in value:
            collect_rows(v, rows)


def parse_fixture(page):
    """The fixture is embedded in the page as a Livewire snapshot, one dict per match.

    An empty fixture is normal between seasons. A page without the snapshot means the site changed.
    """
    snapshots = [unwrap(json.loads(html.unescape(s))["data"]) for s in re.findall(r'wire:snapshot="([^"]*)"', page)]
    fixtures = [s["leagueFixture"] for s in snapshots if "leagueFixture" in s]
    if not fixtures:
        raise ValueError("No fixture data on the TVF page: the site layout may have changed")
    rows = []
    collect_rows(fixtures, rows)
    for row in rows:
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"TVF fixture is missing fields {sorted(missing)}: the site layout may have changed")
    return [row for row in rows if row["KUMEID"] == TVF["competition_id"]]


def team_id(name, teams):
    """TVF names carry sponsors that change, so teams are matched on the part of the name that stays."""
    found = {tid for tid, keyword in teams["tvf_keyword"].items() if keyword in name}
    if len(found) != 1:
        raise ValueError(f"Cannot match TVF team {name!r} (found {sorted(found)}): update teams.csv")
    return found.pop()


def short_season(season):
    return f"{season[:4]}-{season[-2:]}"


def set_points(row):
    points = [(int(row.get(f"SETA{i}") or 0), int(row.get(f"SETB{i}") or 0)) for i in range(1, MAX_SETS + 1)]
    return [p for p in points if p != (0, 0)]


def to_match(row, teams):
    """Turn a TVF row into a row of the matches sheet. Unplayed matches give None."""
    if row["SONUCDURUMU"] != FINISHED:
        return None
    label = f"{row['TARIH']} {row['ATAKIMI']} v {row['BTAKIMI']}"
    score = int(row["SETA"]), int(row["SETB"])
    if score not in LEAGUE_POINTS:
        raise ValueError(f"Impossible score {score[0]}-{score[1]}: {label}")
    points = set_points(row)
    forfeit = row["HUKMEN"] not in ("", "0")
    if not forfeit:
        won = sum(h > a for h, a in points), sum(a > h for h, a in points)
        if won != score:
            raise ValueError(f"Set scores {points} do not give {score[0]}-{score[1]}: {label}")

    season = short_season(row["SEZON"])
    regular = row["TURID"] == TVF["regular_season_type"]
    home, away = team_id(row["ATAKIMI"], teams), team_id(row["BTAKIMI"], teams)
    match = {
        "match_id": f"{season}-{'R' if regular else 'P'}{int(row['MACNO']):03d}",
        "season": season,
        "date": pd.to_datetime(row["TARIH"], format="%d.%m.%Y").date().isoformat(),
        "phase": "regular" if regular else "playoff",
        "round": f"Week {int(row['HAFTA'])}" if regular else row["TURID"],
        "home_id": home,
        "away_id": away,
        "home_name (source)": row["ATAKIMI"],
        "away_name (source)": row["BTAKIMI"],
        "home_sets": score[0],
        "away_sets": score[1],
    }
    for i in range(MAX_SETS):
        match[f"s{i + 1}_home"] = points[i][0] if i < len(points) else None
        match[f"s{i + 1}_away"] = points[i][1] if i < len(points) else None
    league_points = LEAGUE_POINTS[score]
    match.update({
        "home_points_total": sum(p[0] for p in points),
        "away_points_total": sum(p[1] for p in points),
        "winner_id": home if score[0] > score[1] else away,
        "home_league_pts": league_points[0] if regular else None,
        "away_league_pts": league_points[1] if regular else None,
        "use_for_elo": "N" if forfeit else "Y",
        "data_flag": "Forfeit (hükmen): leave out of Elo" if forfeit else None,
        "source": TVF["url"],
    })
    return match


def finished_matches(rows, teams):
    return pd.DataFrame([m for m in (to_match(row, teams) for row in rows) if m])
