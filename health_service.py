"""System health checks. None of these call the API, so they cost no quota."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import config
from services import api_guard
from utils import db_connection as db
from utils.runtime import is_demo_mode

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
QUOTA_FILE = PROJECT_ROOT / "data" / "quota.json"
LOG_DIR = PROJECT_ROOT / "logs"
EXPECTED_TABLES = {"teams", "venues", "series", "players", "matches",
                   "player_career_stats", "batting_performances", "bowling_performances"}
SEED_ID = 900_000


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}   # ok | warn | fail


def check_database():
    """Check the database opens, has every table and no orphan rows."""
    try:
        counts = db.table_counts()
    except Exception as exc:
        return [_check("Database", "fail", f"Cannot open the database: {exc}")]
    missing = EXPECTED_TABLES - set(counts)
    if missing:
        return [_check("Database", "fail",
                       f"Missing tables: {', '.join(sorted(missing))}. Run the schema setup.")]
    out = [_check("Database", "ok", f"{len(counts)} tables, {sum(counts.values()):,} rows")]
    try:
        problems = len(db.run_query("PRAGMA foreign_key_check"))
        out.append(_check("Foreign keys", "ok" if not problems else "fail",
                          "No orphan rows" if not problems else f"{problems} rows break a foreign key"))
        api = int(db.run_query("SELECT COUNT(*) n FROM matches WHERE match_id < :s",
                               {"s": SEED_ID})["n"].iloc[0])
        sample = counts["matches"] - api
        out.append(_check("Data mix", "ok" if counts["matches"] else "warn",
                          f"{api} API matches, {sample} sample matches"))
    except Exception as exc:
        out.append(_check("Database details", "warn", str(exc)))
    return out


def check_api_config():
    """Check the API key, URLs and endpoint registry in the configuration."""
    out = []
    key = getattr(config, "RAPIDAPI_KEY", None)
    if not key or str(key).startswith("your_key"):
        out.append(_check("API key", "fail", "RAPIDAPI_KEY is missing in .env (live pages need it)"))
    else:
        out.append(_check("API key", "ok", "Present (not shown)"))
    if not getattr(config, "API_BASE_URL", None) or not getattr(config, "RAPIDAPI_HOST", None):
        out.append(_check("API URL / host", "fail", "API_BASE_URL or RAPIDAPI_HOST is missing in .env"))
    todo = [k for k, v in getattr(config, "ENDPOINTS", {}).items() if v == "TODO"]
    out.append(_check("Endpoints", "warn" if todo else "ok",
                      f"Not set: {', '.join(todo)}" if todo else "All registered"))
    return out


def check_quota():
    """Report the last known API quota saved by the client."""
    try:
        info = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
        remaining, when = int(info["remaining"]), info.get("checked_at", "unknown time")
    except (OSError, ValueError, KeyError, TypeError):
        return _check("API quota", "warn", "Unknown until the first API call is made")
    status = "fail" if remaining <= 0 else "warn" if remaining < 20 else "ok"
    return _check("API quota", status, f"{remaining} calls left (as of {when})")


def check_budget():
    """Report today's use of the app's own daily API call cap."""
    use = api_guard.usage()
    if not use["limit"]:
        return _check("Daily API cap", "ok", "No cap set (add API_DAILY_BUDGET when hosting publicly)")
    status = "warn" if use["used"] >= use["limit"] else "ok"
    return _check("Daily API cap", status, f"{use['used']} of {use['limit']} calls used today (UTC)")


def check_mode():
    """Report whether the app is running in demo mode."""
    if is_demo_mode():
        return _check("Mode", "ok", "Demo mode (sample data, changes are temporary)")
    return _check("Mode", "ok", "Normal mode")


def check_cache():
    """Report how many saved API responses exist and how old the newest is."""
    files = list(RAW_DIR.glob("*.json")) if RAW_DIR.exists() else []
    if not files:
        return _check("Saved responses", "warn", "None yet (the fallback for API outages)")
    newest = max(f.stat().st_mtime for f in files)
    age_h = (datetime.now(timezone.utc).timestamp() - newest) / 3600
    return _check("Saved responses", "ok", f"{len(files)} files, newest {age_h:.1f} h old")


def check_logs():
    """Check the logs folder is writable."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        probe = LOG_DIR / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return _check("Logs", "ok", f"Writable ({LOG_DIR.name}/)")
    except OSError as exc:
        return _check("Logs", "warn", f"Cannot write logs: {exc}")


def run_checks():
    """Run every health check and return a list of status dictionaries."""
    results = check_database() + check_api_config() + [
        check_quota(), check_budget(), check_mode(), check_cache(), check_logs()]
    bad = [r["name"] for r in results if r["status"] == "fail"]
    if bad:
        logger.warning("Health check failures: %s", ", ".join(bad))
    return results
