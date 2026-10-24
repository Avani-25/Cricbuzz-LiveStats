"""Every page must load without an exception against a freshly built database."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config
from services import live_service
from utils import db_connection as db
from utils import seed_data

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["home", "live_matches", "top_stats", "sql_queries", "crud_operations"]

LIVE_JSON = {"typeMatches": [{"matchType": "International", "seriesMatches": [
    {"seriesAdWrapper": {"seriesId": 7, "seriesName": "Test Series", "matches": [
        {"matchInfo": {"matchId": 101, "seriesId": 7, "matchDesc": "1st", "matchFormat": "ODI",
                       "state": "In Progress", "status": "Team A opt to bat",
                       "team1": {"teamId": 1, "teamName": "Team A", "teamSName": "TA"},
                       "team2": {"teamId": 2, "teamName": "Team B", "teamSName": "TB"},
                       "venueInfo": {"id": 5, "ground": "Ground", "city": "City"}}}]}}]}]}


class FakeClient:
    quota_remaining = "50"

    def get(self, path, params=None, use_cache=True, retries=None):
        return LIVE_JSON

    def _cache_file(self, path, params):
        return Path("/nonexistent/saved.json")


@pytest.fixture(scope="module", autouse=True)
def app_env(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "smoke.db"
    config.DATABASE_URL = f"sqlite:///{path.as_posix()}"
    db._engine = None
    db.init_db()
    seed_data.run_seed()
    live_service.CricbuzzClient = FakeClient       # pages never hit the real API
    yield
    db.get_engine().dispose()
    db._engine = None


@pytest.mark.parametrize("page", PAGES)
def test_page_loads_without_exception(page):
    at = AppTest.from_file(str(ROOT / "pages" / f"{page}.py"), default_timeout=60).run()
    assert not at.exception, f"{page}: {at.exception}"


def test_live_page_shows_the_fake_match():
    at = AppTest.from_file(str(ROOT / "pages" / "live_matches.py"), default_timeout=60).run()
    assert any("Team A" in m.value for m in at.markdown)


def test_sql_page_runs_every_stored_query():
    from sql.queries import QUERIES
    at = AppTest.from_file(str(ROOT / "pages" / "sql_queries.py"), default_timeout=60).run()
    for level in ("Beginner", "Intermediate", "Advanced"):
        at.radio(key="sql_level").set_value(level).run()
        keys = [k for k, q in QUERIES.items() if q["level"] == level]
        for key in keys:
            at.selectbox(key=f"sql_pick_{level}").select(key).run()
            assert not at.exception, f"{key}: {at.exception}"
            assert not at.error, f"{key}: {[e.value for e in at.error]}"


def test_top_stats_works_for_every_format():
    at = AppTest.from_file(str(ROOT / "pages" / "top_stats.py"), default_timeout=60).run()
    for fmt in ("Test", "ODI", "T20I"):
        at.radio(key="ts_format").set_value(fmt).run()
        assert not at.exception, f"{fmt}: {at.exception}"


def test_json_fixture_is_valid():                     # guards the fixture itself
    assert json.loads(json.dumps(LIVE_JSON)) == LIVE_JSON
