import json
import logging

import pytest

import config
from api.cricbuzz_client import CricbuzzAPIError
from services import crud_service as crud
from services import health_service as health
from utils import db_connection as db
from utils import errors, logging_setup


@pytest.fixture
def fresh_db(tmp_path):
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    db._engine = None
    db.init_db()
    yield
    db.get_engine().dispose()
    db._engine = None


# ------------------------------------------------------------ friendly errors
@pytest.mark.parametrize("exc,expected", [
    (CricbuzzAPIError("401 for /x: bad"), "rejected your key"),
    (CricbuzzAPIError("403 for /x"), "rejected your key"),
    (CricbuzzAPIError("404 for /x"), "endpoint was not found"),
    (CricbuzzAPIError("429 for /x"), "quota"),
    (CricbuzzAPIError("503 for /x"), "server problem"),
    (CricbuzzAPIError("Gave up on /x after retries"), "could not be reached"),
    (RuntimeError("database is locked"), "busy"),
    (RuntimeError("no such table: players"), "not been set up"),
    (RuntimeError("unable to open database file"), "DATABASE_URL"),
    (ValueError("boom"), "Something went wrong"),
])
def test_friendly_error_messages(exc, expected):
    assert expected in errors.friendly_error(exc)


def test_friendly_error_never_leaks_internals():
    msg = errors.friendly_error(RuntimeError("secret path C:\\Users\\x\\key.txt"))
    assert "C:\\" not in msg


# ------------------------------------------------------- page safety net
def test_handle_page_errors_shows_reference_and_logs(monkeypatch, caplog):
    shown = []
    monkeypatch.setattr(errors.st, "error", lambda m: shown.append(m))
    monkeypatch.setattr(config, "DEBUG", False, raising=False)

    def broken_page():
        raise ValueError("kaboom with details")

    with caplog.at_level(logging.ERROR):
        errors.handle_page_errors(broken_page)
    assert len(shown) == 1 and "Reference:" in shown[0]
    assert "kaboom" not in shown[0]                   # details stay out of the UI
    assert "kaboom with details" in caplog.text       # ...but are in the log


def test_handle_page_errors_lets_streamlit_control_flow_through():
    from streamlit.runtime.scriptrunner import StopException
    with pytest.raises(StopException):
        errors.handle_page_errors(lambda: (_ for _ in ()).throw(StopException()))


def test_handle_page_errors_is_quiet_when_page_is_fine(monkeypatch):
    shown = []
    monkeypatch.setattr(errors.st, "error", lambda m: shown.append(m))
    errors.handle_page_errors(lambda: None)
    assert shown == []


# ------------------------------------------------------------------ logging
def test_api_key_is_redacted_from_log_lines(monkeypatch):
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "SUPERSECRETKEY123456", raising=False)
    fmt = logging_setup.RedactingFormatter("%(message)s")
    record = logging.LogRecord("t", logging.INFO, __file__, 1,
                               "calling with key SUPERSECRETKEY123456 now", None, None)
    out = fmt.format(record)
    assert "SUPERSECRETKEY123456" not in out and "***" in out


def test_setup_logging_is_idempotent():
    logging_setup.setup_logging()
    handlers = len(logging.getLogger().handlers)
    logging_setup.setup_logging()
    assert len(logging.getLogger().handlers) == handlers
    assert logging_setup.LOG_FILE.exists()


def test_crud_actions_are_audited(fresh_db, caplog):
    good = {"full_name": "Audit Player", "country": "India", "playing_role": "Batsman",
            "batting_style": "Right-hand bat", "bowling_style": None}
    with caplog.at_level(logging.INFO):
        pid = crud.create_player(good).player_id
        crud.delete_player(pid)
    assert "CRUD create" in caplog.text and "CRUD delete" in caplog.text


# ------------------------------------------------------------------- health
def test_health_database_ok(fresh_db):
    items = {i["name"]: i for i in health.check_database()}
    assert items["Database"]["status"] == "ok"
    assert items["Foreign keys"]["status"] == "ok"


def test_health_database_missing_tables(tmp_path):
    config.DATABASE_URL = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    db._engine = None
    try:
        items = health.check_database()
        assert items[0]["status"] == "fail" and "Missing tables" in items[0]["detail"]
    finally:
        db.get_engine().dispose()
        db._engine = None


def test_health_api_config(monkeypatch):
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "your_key_here", raising=False)
    monkeypatch.setitem(config.ENDPOINTS, "venue_info", "TODO")
    items = {i["name"]: i for i in health.check_api_config()}
    assert items["API key"]["status"] == "fail"
    assert items["Endpoints"]["status"] == "warn" and "venue_info" in items["Endpoints"]["detail"]
    monkeypatch.setattr(config, "RAPIDAPI_KEY", "a-real-looking-key-123", raising=False)
    assert {i["name"]: i for i in health.check_api_config()}["API key"]["status"] == "ok"


@pytest.mark.parametrize("remaining,status", [(150, "ok"), (10, "warn"), (0, "fail")])
def test_health_quota_levels(monkeypatch, tmp_path, remaining, status):
    quota = tmp_path / "quota.json"
    quota.write_text(json.dumps({"remaining": remaining, "checked_at": "now"}))
    monkeypatch.setattr(health, "QUOTA_FILE", quota)
    assert health.check_quota()["status"] == status


def test_health_quota_unknown_and_corrupt(monkeypatch, tmp_path):
    monkeypatch.setattr(health, "QUOTA_FILE", tmp_path / "nope.json")
    assert health.check_quota()["status"] == "warn"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    monkeypatch.setattr(health, "QUOTA_FILE", bad)
    assert health.check_quota()["status"] == "warn"


def test_run_checks_returns_well_formed_results(fresh_db):
    for item in health.run_checks():
        assert item["status"] in ("ok", "warn", "fail") and item["name"] and item["detail"]


def test_client_remembers_quota(monkeypatch, tmp_path):
    from api import cricbuzz_client as cc
    monkeypatch.setattr(cc, "QUOTA_FILE", tmp_path / "quota.json")
    cc._remember_quota("187")
    assert json.loads((tmp_path / "quota.json").read_text())["remaining"] == 187
    cc._remember_quota("not-a-number")                 # must not raise
