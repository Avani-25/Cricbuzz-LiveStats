import pytest

import config
from models.validators import validate_player, validate_stats
from services import crud_service as crud
from utils import db_connection as db

GOOD = {"full_name": "Test Batter", "country": "India", "playing_role": "Batsman",
        "batting_style": "Right-hand bat", "bowling_style": None}
STATS = {"format": "ODI", "matches": 10, "innings": 10, "runs": 400,
         "highest_score": 120, "centuries": 1, "fifties": 2, "wickets": 0}


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Every test gets its own empty database."""
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    db._engine = None
    db.init_db()
    yield
    db.get_engine().dispose()
    db._engine = None


def test_create_read_update_delete():
    r = crud.create_player(GOOD, STATS)
    assert r.ok and r.player_id >= crud.NEW_PLAYER_ID_FLOOR
    assert crud.get_player(r.player_id)["full_name"] == "Test Batter"
    assert len(crud.get_stats(r.player_id)) == 1

    upd = dict(GOOD, full_name="Renamed Batter", playing_role="All-rounder",
               bowling_style="Legbreak")
    assert crud.update_player(r.player_id, upd).ok
    assert crud.get_player(r.player_id)["playing_role"] == "All-rounder"

    assert crud.delete_player(r.player_id).ok
    assert crud.get_player(r.player_id) is None
    assert crud.get_stats(r.player_id).empty


def test_validation_blocks_bad_input():
    assert not crud.create_player(dict(GOOD, full_name="X")).ok
    assert not crud.create_player(dict(GOOD, full_name="Bob123")).ok
    assert not crud.create_player(dict(GOOD, playing_role="Umpire")).ok
    assert not crud.create_player(dict(GOOD, playing_role="Bowler")).ok  # no style
    assert crud.list_players().empty                                     # nothing saved


def test_bad_stats_roll_back_the_player():
    r = crud.create_player(GOOD, dict(STATS, highest_score=999))
    assert not r.ok
    assert crud.list_players().empty


def test_duplicate_player_rejected():
    assert crud.create_player(GOOD).ok
    assert not crud.create_player(dict(GOOD, full_name="test batter")).ok


def test_delete_removes_child_rows_first():
    p = crud.create_player(GOOD, STATS).player_id
    db.execute("INSERT INTO teams (team_id, team_name) VALUES (1,'A'),(2,'B')")
    db.execute("INSERT INTO matches (match_id, team1_id, team2_id) VALUES (1,1,2)")
    db.execute("INSERT INTO batting_performances (match_id, player_id, innings_no, runs) "
               "VALUES (1, :p, 1, 50)", {"p": p})
    assert crud.player_footprint(p)["batting_rows"] == 1
    assert crud.delete_player(p).ok          # would hit a FK error if order was wrong
    assert db.table_counts()["batting_performances"] == 0


def test_sql_injection_text_is_inert():
    crud.create_player(GOOD)
    evil = "'; DROP TABLE players; --"
    assert crud.list_players(search=evil).empty
    assert not crud.create_player(dict(GOOD, full_name=evil)).ok
    assert db.table_counts()["players"] == 1


def test_unknown_ids():
    assert not crud.update_player(424242, GOOD).ok
    assert not crud.delete_player(424242).ok
    assert not crud.save_stats(424242, STATS).ok


def test_validators_directly():
    _, errs = validate_player(GOOD)
    assert errs == []
    _, errs = validate_stats(dict(STATS, matches="abc"))
    assert errs
    _, errs = validate_stats(dict(STATS, innings=50, matches=10))
    assert errs
