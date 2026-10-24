import json

import pytest

import config
from api import cricbuzz_client as cc
from scripts import pin_requirements, setup_db
from utils import db_connection as db


@pytest.fixture
def tmp_db(tmp_path):
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 'built.db').as_posix()}"
    db._engine = None
    yield tmp_path / "built.db"
    db.get_engine().dispose()
    db._engine = None


# ------------------------------------------------------------ setup_db script
def test_setup_db_schema_only(tmp_db):
    assert setup_db.main(["--no-seed"]) == 0
    assert tmp_db.exists()
    counts = db.table_counts()
    assert len(counts) == 8 and sum(counts.values()) == 0


def test_setup_db_with_seed_and_repeat_is_safe(tmp_db):
    assert setup_db.main([]) == 0
    first = db.table_counts()
    assert first["matches"] == 450 and first["players"] == 120
    assert setup_db.main([]) == 0                    # running again changes nothing
    assert db.table_counts() == first


def test_setup_db_reset(tmp_db):
    setup_db.main([])
    db.execute("DELETE FROM batting_performances")
    assert setup_db.main(["--reset", "--yes"]) == 0
    assert db.table_counts()["batting_performances"] > 0


def test_setup_db_reset_can_be_cancelled(tmp_db, monkeypatch):
    setup_db.main(["--no-seed"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert setup_db.main(["--reset"]) == 1
    assert tmp_db.exists()


def test_setup_db_loads_saved_api_responses(tmp_db, tmp_path, monkeypatch):
    saved = tmp_path / "raw"
    saved.mkdir()
    data = {"typeMatches": [{"matchType": "International", "seriesMatches": [
        {"seriesAdWrapper": {"seriesId": 7, "seriesName": "S", "matches": [
            {"matchInfo": {"matchId": 1, "seriesId": 7, "matchDesc": "1st",
                           "matchFormat": "ODI", "state": "Complete",
                           "status": "India won by 5 wkts",
                           "team1": {"teamId": 2, "teamName": "India", "teamSName": "IND"},
                           "team2": {"teamId": 3, "teamName": "Nepal", "teamSName": "NEP"},
                           "venueInfo": {"id": 9, "ground": "Eden Gardens", "city": "Kolkata"}}}]}}]}]}
    (saved / "matches_v1_live_abc.json").write_text(json.dumps(data))
    (saved / "matches_v1_recent_def.json").write_text("{not json")        # must be skipped
    (saved / "matches_v1_other.json").write_text(json.dumps({"x": 1}))   # no matches inside
    monkeypatch.setattr(setup_db, "RAW_DIR", saved)
    assert setup_db.main(["--from-cache"]) == 0
    counts = db.table_counts()
    assert counts["matches"] == 1 + 450             # 1 API match + the sample data
    # the sample data reuses the API's "India" team instead of creating a second one
    assert int(db.run_query("SELECT COUNT(*) n FROM teams WHERE team_name='India'")["n"].iloc[0]) == 1


# --------------------------------------------------------- pin_requirements
def test_read_names_ignores_comments_and_blanks(tmp_path):
    f = tmp_path / "r.in"
    f.write_text("streamlit  # the app\n\n# a comment\npandas\n")
    assert pin_requirements.read_names(f) == ["streamlit", "pandas"]


def test_pin_reports_missing_packages():
    pinned, missing = pin_requirements.pin(["pytest", "definitely-not-a-package-xyz"])
    assert pinned[0].startswith("pytest==") and missing == ["definitely-not-a-package-xyz"]


# ----------------------------------------------------- client HTTP behaviour
class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "RAW_DIR", tmp_path)
    monkeypatch.setattr(cc, "QUOTA_FILE", tmp_path / "quota.json")
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    return cc.CricbuzzClient()


def script(client, monkeypatch, *responses):
    """Make client.session.get return the given responses in order."""
    calls = []
    queue = list(responses)

    def fake_get(url, **kwargs):
        calls.append(url)
        return queue.pop(0)

    monkeypatch.setattr(client.session, "get", fake_get)
    return calls


def test_success_is_cached_and_quota_remembered(client, monkeypatch, tmp_path):
    calls = script(client, monkeypatch,
                   FakeResponse(200, {"ok": 1}, {"x-ratelimit-requests-remaining": "187"}))
    assert client.get("/a/b") == {"ok": 1}
    assert client.get("/a/b") == {"ok": 1}            # second call comes from the saved file
    assert len(calls) == 1
    assert client.quota_remaining == "187"
    assert json.loads((tmp_path / "quota.json").read_text())["remaining"] == 187


def test_bypassing_the_cache_asks_the_api_again(client, monkeypatch):
    calls = script(client, monkeypatch, FakeResponse(200, {"v": 1}), FakeResponse(200, {"v": 2}))
    assert client.get("/a") == {"v": 1}
    assert client.get("/a", use_cache=False) == {"v": 2}
    assert len(calls) == 2


@pytest.mark.parametrize("status", [401, 403, 404, 422])
def test_client_errors_fail_immediately(client, monkeypatch, status):
    calls = script(client, monkeypatch, FakeResponse(status))
    with pytest.raises(cc.CricbuzzAPIError, match=str(status)):
        client.get("/a")
    assert len(calls) == 1                            # no retries, no wasted quota


def test_server_errors_stop_after_two_attempts(client, monkeypatch):
    calls = script(client, monkeypatch, FakeResponse(500), FakeResponse(500), FakeResponse(200))
    with pytest.raises(cc.CricbuzzAPIError, match="500"):
        client.get("/a")
    assert len(calls) == 2


def test_rate_limit_is_retried_then_succeeds(client, monkeypatch):
    calls = script(client, monkeypatch, FakeResponse(429), FakeResponse(200, {"ok": 1}))
    assert client.get("/a") == {"ok": 1}
    assert len(calls) == 2


def test_rate_limit_gives_up_eventually(client, monkeypatch):
    script(client, monkeypatch, FakeResponse(429), FakeResponse(429), FakeResponse(429))
    with pytest.raises(cc.CricbuzzAPIError, match="Gave up"):
        client.get("/a")
