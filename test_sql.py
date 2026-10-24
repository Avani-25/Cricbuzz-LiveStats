import pytest

import config
from services import sql_service
from sql.queries import QUERIES
from utils import db_connection as db
from utils import seed_data


@pytest.fixture(scope="module", autouse=True)
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "t.db"
    config.DATABASE_URL = f"sqlite:///{path.as_posix()}"
    db._engine = None
    db.init_db()
    seed_data.run_seed()
    yield
    db.get_engine().dispose()
    db._engine = None


def test_there_are_25_numbered_questions():
    numbered = {k[:3] for k in QUERIES}
    assert numbered == {f"q{i:02d}" for i in range(1, 26)}


@pytest.mark.parametrize("key", list(QUERIES))
def test_every_query_runs_and_returns_rows(key):
    df = sql_service.run_named(key)
    assert len(df) > 0, f"{key} returned no rows"


def test_q03_is_sorted_and_limited():
    df = sql_service.run_named("q03")
    assert len(df) == 10 and df["total_runs"].is_monotonic_decreasing


def test_q17_percentages_are_sane():
    df = sql_service.run_named("q17")
    assert set(df["decision"]) == {"bat", "bowl", "overall"}
    assert df["win_pct"].between(0, 100).all()


def test_q23_has_all_four_form_labels():
    forms = set(sql_service.run_named("q23")["form"])
    assert forms == {"Excellent Form", "Good Form", "Average Form", "Poor Form"}


@pytest.mark.parametrize("sql,ok", [
    ("SELECT * FROM players", True),
    ("select 1;", True),
    ("WITH x AS (SELECT 1 a) SELECT * FROM x", True),
    ("SELECT * FROM players WHERE full_name = 'Update Me'", True),   # keyword inside a string
    ("DELETE FROM players", False),
    ("SELECT 1; DROP TABLE players", False),
    ("SELECT * FROM players; SELECT 2", False),
    ("PRAGMA table_info(players)", False),
    ("UPDATE players SET country = 'x'", False),
    ("", False),
    ("SELECT 1 -- ; DROP TABLE players", True),                       # inside a comment
])
def test_validate_select(sql, ok):
    assert sql_service.validate_select(sql)[0] is ok


def test_readonly_connection_blocks_writes():
    before = db.table_counts()["players"]
    with pytest.raises(Exception):
        db.run_readonly("DELETE FROM players")
    assert db.table_counts()["players"] == before
    db.execute("UPDATE players SET country = country WHERE player_id = -1")  # writes work again


def test_custom_runner_reports_errors_and_timeouts():
    df, err = sql_service.run_custom("SELECT * FROM no_such_table")
    assert df is None and "SQL error" in err
    slow = ("WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM r) "
            "SELECT COUNT(*) FROM r")
    df, err = sql_service.run_custom(slow)
    assert df is None and "5 seconds" in err
