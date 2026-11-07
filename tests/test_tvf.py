import html
import json

import pandas as pd
import pytest

from sultanlar import tvf

TEAMS = pd.DataFrame({"tvf_keyword": {"FEN": "FENERBAHÇE", "VAK": "VAKIFBANK"}})


def row(**changes):
    finished = {
        "SEZON": "2026-2027", "TARIH": "03.10.2026", "KUMEID": "SULTANLAR", "TURID": "LE", "HAFTA": "1", "MACNO": "7",
        "ATAKIMI": "FENERBAHÇE MEDICANA", "BTAKIMI": "VAKIFBANK", "SETA": "3", "SETB": "1", "SONUCDURUMU": "K",
        "HUKMEN": "0", "SETA1": "25", "SETB1": "20", "SETA2": "20", "SETB2": "25", "SETA3": "25", "SETB3": "20",
        "SETA4": "25", "SETB4": "20", "SETA5": "", "SETB5": "",
    }
    return {**finished, **changes}


def page(fixture):
    data = {"slug": "sultanlar-ligi", "leagueFixture": [{"1": [[fixture, {"s": "arr"}]]}, {"s": "arr"}]}
    snapshot = html.escape(json.dumps({"data": data}), quote=True)
    return f'<div wire:snapshot="{snapshot}"></div>'


def test_parse_fixture_reads_the_snapshot():
    rows = tvf.parse_fixture(page([row(), row(KUMEID="ERKEKLER")]))
    assert [r["MACNO"] for r in rows] == ["7"]


def test_empty_fixture_is_allowed_between_seasons():
    assert tvf.parse_fixture(page([])) == []


def test_page_without_fixture_is_an_error():
    with pytest.raises(ValueError, match="layout"):
        tvf.parse_fixture("<html></html>")


def test_missing_field_is_an_error():
    broken = row()
    del broken["SETA"]
    with pytest.raises(ValueError, match="missing fields"):
        tvf.parse_fixture(page([broken]))


def test_to_match_converts_a_finished_row():
    match = tvf.to_match(row(), TEAMS)
    assert match["match_id"] == "2026-27-R007"
    assert match["date"] == "2026-10-03"
    assert (match["home_id"], match["away_id"], match["winner_id"]) == ("FEN", "VAK", "FEN")
    assert (match["home_points_total"], match["away_points_total"]) == (95, 85)
    assert (match["home_league_pts"], match["away_league_pts"]) == (3, 0)
    assert match["use_for_elo"] == "Y"


def test_unplayed_match_is_skipped():
    assert tvf.to_match(row(SONUCDURUMU=""), TEAMS) is None


def test_five_set_match_splits_league_points():
    five_sets = row(SETA="3", SETB="2", SETA4="20", SETB4="25", SETA5="15", SETB5="10")
    match = tvf.to_match(five_sets, TEAMS)
    assert (match["home_league_pts"], match["away_league_pts"]) == (2, 1)


def test_playoff_gets_its_own_id_and_no_league_points():
    match = tvf.to_match(row(TURID="PO"), TEAMS)
    assert match["match_id"] == "2026-27-P007"
    assert pd.isna(match["home_league_pts"])


def test_forfeit_stays_out_of_elo():
    forfeit = row(HUKMEN="1", SETA="3", SETB="0", SETA1="", SETB1="", SETA2="", SETB2="", SETA3="", SETB3="",
                  SETA4="", SETB4="")
    assert tvf.to_match(forfeit, TEAMS)["use_for_elo"] == "N"


@pytest.mark.parametrize("bad, message", [
    ({"SETA1": "10", "SETB1": "25"}, "do not give"),
    ({"SETA": "2", "SETB": "2"}, "Impossible score"),
    ({"ATAKIMI": "BİLİNMEYEN SPOR"}, "update teams.csv"),
])
def test_bad_rows_stop_the_update(bad, message):
    with pytest.raises(ValueError, match=message):
        tvf.to_match(row(**bad), TEAMS)
