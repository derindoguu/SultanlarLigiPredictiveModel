import pandas as pd
import pytest

from sultanlar.data import load_matches, load_teams, merge_matches, validate_matches, write_text


def matches(*rows):
    columns = ["match_id", "season", "date", "phase", "home_id", "away_id", "home_sets", "away_sets", "use_for_elo"]
    return pd.DataFrame(rows, columns=columns)


FIRST = ("2026-27-R001", "2026-27", "2026-10-03", "regular", "FEN", "VAK", 3, 1, "Y")
SECOND = ("2026-27-R002", "2026-27", "2026-10-04", "regular", "VAK", "FEN", 3, 0, "Y")


def test_merge_keeps_old_matches_that_left_the_page():
    merged = merge_matches(matches(FIRST), matches(SECOND))
    assert merged.match_id.tolist() == ["2026-27-R001", "2026-27-R002"]


def test_merge_replaces_a_changed_result():
    corrected = FIRST[:6] + (3, 2, "Y")
    merged = merge_matches(matches(FIRST), matches(corrected))
    assert merged.away_sets.tolist() == [2]


def test_merge_with_nothing_new_changes_nothing():
    assert merge_matches(matches(FIRST), pd.DataFrame()).equals(matches(FIRST))


def test_merge_catches_renumbered_matches():
    renumbered = ("2026-27-R501",) + FIRST[1:]
    with pytest.raises(ValueError, match="twice"):
        merge_matches(matches(FIRST), matches(renumbered))


def test_playoffs_may_repeat_a_pairing():
    game_1 = ("2026-27-P001", "2026-27", "2027-04-01", "playoff", "FEN", "VAK", 3, 1, "Y")
    game_3 = ("2026-27-P003", "2026-27", "2027-04-08", "playoff", "FEN", "VAK", 3, 2, "Y")
    assert len(merge_matches(matches(game_1), matches(game_3))) == 2


@pytest.mark.parametrize("bad, message", [
    (FIRST[:4] + ("XXX",) + FIRST[5:], "teams.csv"),
    (FIRST[:5] + ("FEN",) + FIRST[6:], "playing itself"),
    (FIRST[:6] + (2, 2, "Y"), "cannot rate"),
])
def test_validate_rejects_bad_data(bad, message):
    with pytest.raises(ValueError, match=message):
        validate_matches(matches(bad), load_teams())


def test_saved_data_is_valid():
    validate_matches(load_matches(), load_teams())


def test_write_text_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "ratings.csv"
    write_text(target, "a,b\n")
    assert target.read_bytes() == b"a,b\n"
    assert [p.name for p in tmp_path.iterdir()] == ["ratings.csv"]
