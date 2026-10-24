"""Hosting safety: automatic first-run setup, the daily API cap, and demo mode."""
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest
import requests

import config
from api import cricbuzz_client as cc
from services import api_guard, health_service, live_service
from utils import bootstrap
from utils import db_connection as db
from utils import runtime


@pytest.fixture
def tmp_db(tmp_path):
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    db._engine = None
    yield
    db.get_engine().dispose()
    db._engine = None


@pytest.fixture
def budget(monkeypatch, tmp_path):
    """Isolated budget file and counter."""
    monkeypatch.setattr(api_guard, "BUDGET_FILE", tmp_path / "api_budget.json")
    monkeypatch.setattr(api_guard, "_state", {"date": None, "used": 0})
    monkeypatch.delenv("API_DAILY_BUDGET", raising=False)


# ----------------------------------------------------------- runtime flags
@pytest.mark.parametrize("value,expected", [
    ("1", True), ("true", True), ("YES", True), (" on ", True),
    ("0", False), ("false", False), ("", False), ("nonsense", False),
])
def test_env_flag_values(monkeypatch, value, expected):
    monkeypatch.setenv("SOME_FLAG", value)
    assert runtime.env_flag("SOME_FLAG") is expected


def test_env_flag_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert runtime.env_flag("SOME_FLAG") is False
    assert runtime.env_flag("SOME_FLAG", True) is True


def test_demo_mode_switch(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    assert runtime.is_demo_mode()
    monkeypatch.setenv("DEMO_MODE", "0")
    assert not runtime.is_demo_mode()


# --------------------------------------------------- first-run database setup
def test_empty_install_builds_itself(tmp_db):
    assert bootstrap.ensure_database() == "seeded"
    counts = db.table_counts()
    assert counts["players"] == 120 and counts["matches"] == 450


def test_existing_data_is_never_touched(tmp_db):
    bootstrap.ensure_database()
    db.execute("DELETE FROM batting_performances")
    before = db.table_counts()
    assert bootstrap.ensure_database() == "ready"
    assert db.table_counts() == before                  # no re-seeding over real data


def test_setup_can_be_switched_off(tmp_db, monkeypatch):
    monkeypatch.setenv("AUTO_SETUP", "0")
    assert bootstrap.ensure_database() == "disabled"
    assert db.table_counts() == {}                      # nothing was created


def test_tables_without_data_count_as_empty(tmp_db):
    db.init_db()
    assert bootstrap.database_is_empty()
    assert bootstrap.ensure_database() == "seeded"


# ------------------------------------------------------------ daily API cap
def test_no_cap_means_unlimited(budget):
    assert all(api_guard.allow_call() for _ in range(50))
    assert api_guard.usage()["limit"] == 0


def test_cap_blocks_after_the_limit(budget, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "3")
    assert [api_guard.allow_call() for _ in range(5)] == [True, True, True, False, False]
    assert api_guard.usage() == {"limit": 3, "used": 3}


def test_bad_cap_value_falls_back_to_unlimited(budget, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "lots")
    assert api_guard.daily_limit() == 0 and api_guard.allow_call()


def test_cap_survives_a_restart_on_the_same_day(budget, monkeypatch, tmp_path):
    monkeypatch.setenv("API_DAILY_BUDGET", "5")
    for _ in range(4):
        api_guard.allow_call()
    monkeypatch.setattr(api_guard, "_state", {"date": None, "used": 0})   # simulate a new process
    assert api_guard.usage()["used"] == 4
    assert api_guard.allow_call() and not api_guard.allow_call()


def test_cap_resets_on_a_new_day(budget, monkeypatch, tmp_path):
    monkeypatch.setenv("API_DAILY_BUDGET", "2")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    (tmp_path / "api_budget.json").write_text(json.dumps({"date": yesterday, "used": 2}))
    assert api_guard.usage()["used"] == 0
    assert api_guard.allow_call()


def test_corrupt_budget_file_is_ignored(budget, monkeypatch, tmp_path):
    monkeypatch.setenv("API_DAILY_BUDGET", "2")
    (tmp_path / "api_budget.json").write_text("{not json")
    assert api_guard.allow_call()


def test_unwritable_budget_file_still_enforces_in_memory(budget, monkeypatch, tmp_path):
    monkeypatch.setenv("API_DAILY_BUDGET", "2")
    monkeypatch.setattr(api_guard, "BUDGET_FILE", tmp_path / "missing_dir" / "x" / "b.json")
    monkeypatch.setattr(type(api_guard.BUDGET_FILE), "write_text",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    assert [api_guard.allow_call() for _ in range(3)] == [True, True, False]


def test_cap_holds_under_concurrent_visitors(budget, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "10")
    results = []
    threads = [threading.Thread(target=lambda: results.append(api_guard.allow_call()))
               for _ in range(40)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(results) == 10                           # never 11, however many visitors


# ------------------------------------------- the cap inside the real client
class FakeResponse:
    status_code = 200
    headers = {}
    text = "{}"

    def json(self):
        return {"ok": 1}


@pytest.fixture
def client(budget, monkeypatch, tmp_path):
    monkeypatch.setattr(cc, "RAW_DIR", tmp_path)
    monkeypatch.setattr(cc, "QUOTA_FILE", tmp_path / "quota.json")
    c = cc.CricbuzzClient()
    calls = []
    monkeypatch.setattr(c.session, "get", lambda url, **kw: calls.append(url) or FakeResponse())
    c.calls = calls
    return c


def test_client_stops_calling_the_api_when_the_budget_is_gone(client, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "2")
    client.get("/a", use_cache=False)
    client.get("/b", use_cache=False)
    with pytest.raises(cc.CricbuzzAPIError, match="429"):
        client.get("/c", use_cache=False)
    assert len(client.calls) == 2                       # the third never left the machine


def test_saved_responses_do_not_cost_budget(client, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "1")
    client.get("/a")                                    # real call, now saved
    for _ in range(5):
        assert client.get("/a") == {"ok": 1}            # served from disk
    assert len(client.calls) == 1 and api_guard.usage()["used"] == 1


def test_each_retry_attempt_counts_against_the_budget(client, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "5")
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)

    def offline(url, **kw):
        client.calls.append(url)
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(client.session, "get", offline)
    with pytest.raises(cc.CricbuzzAPIError):
        client.get("/a", use_cache=False)
    assert api_guard.usage()["used"] == 3               # 3 attempts = 3 requests spent


def test_live_page_falls_back_to_saved_data_when_budget_is_gone(budget, monkeypatch, tmp_path):
    monkeypatch.setenv("API_DAILY_BUDGET", "1")
    monkeypatch.setattr(cc, "RAW_DIR", tmp_path)
    monkeypatch.setattr(cc, "QUOTA_FILE", tmp_path / "quota.json")
    saved = {"typeMatches": []}
    path = config.ENDPOINTS["live_matches"]
    cc.CricbuzzClient._cache_file(path, None).write_text(json.dumps(saved))
    api_guard.allow_call()                              # today's single call is already spent
    data, meta = live_service.fetch_matches("Live")
    assert data == saved and meta["stale"] is True
    assert "quota" in meta["friendly"].lower()          # the user sees a plain explanation


# ------------------------------------------------------------- health panel
def test_health_reports_the_cap_and_mode(budget, monkeypatch):
    monkeypatch.setenv("API_DAILY_BUDGET", "4")
    monkeypatch.setenv("DEMO_MODE", "1")
    api_guard.allow_call()
    assert "1 of 4" in health_service.check_budget()["detail"]
    assert health_service.check_budget()["status"] == "ok"
    assert "Demo" in health_service.check_mode()["detail"]
    for _ in range(5):
        api_guard.allow_call()
    assert health_service.check_budget()["status"] == "warn"


def test_health_budget_when_uncapped(budget):
    assert "No cap" in health_service.check_budget()["detail"]
