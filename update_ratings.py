"""Add finished matches from the TVF site, then refresh the ratings and dashboard data.

    python update_ratings.py             fetch from TVF and update
    python update_ratings.py --offline   rebuild the outputs from the saved data
"""
import argparse
import logging

from sultanlar import tvf
from sultanlar.config import project_path
from sultanlar.data import load_active_matches, load_matches, load_teams, merge_matches, validate_matches, write_text
from sultanlar.elo import run_elo
from sultanlar.outputs import dashboard_data, dashboard_script, ratings_table

log = logging.getLogger("update_ratings")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="skip TVF and rebuild from the saved data")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    teams = load_teams()
    saved = load_active_matches()
    active = saved
    if not args.offline:
        rows = tvf.parse_fixture(tvf.fetch_page())
        active = merge_matches(saved, tvf.finished_matches(rows, teams))
        if not rows:
            log.warning("The TVF fixture is empty, which is normal between seasons")

    df = load_matches(active)
    validate_matches(df, teams)
    games, ratings = run_elo(df)
    table = ratings_table(df, ratings, teams["name"])
    data = dashboard_data(df, games, table, teams["name"])

    # everything above can fail safely, because nothing is saved until here
    write_text(project_path("active_matches"), active.to_csv(index=False, lineterminator="\n"))
    write_text(project_path("ratings"), table.to_csv(index=False, lineterminator="\n"))
    write_text(project_path("dashboard_data"), dashboard_script(data))
    log.info("%d new matches, %d in %s, last played %s, %d teams rated",
             len(active) - len(saved), (df.season == data["season"]).sum(), data["season"], data["lastMatch"], len(table))


if __name__ == "__main__":
    main()
