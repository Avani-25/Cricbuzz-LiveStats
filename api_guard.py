"""A daily cap on real API calls, so a public app cannot use up the monthly quota."""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BUDGET_FILE = Path(__file__).resolve().parent.parent / "data" / "api_budget.json"
_lock = threading.Lock()
_state = {"date": None, "used": 0}


def daily_limit() -> int:
    """Calls allowed per UTC day from API_DAILY_BUDGET; 0 (the default) means unlimited."""
    try:
        return max(0, int(os.getenv("API_DAILY_BUDGET", "0")))
    except ValueError:
        return 0


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _sync_with_today() -> None:
    """Reset the in-memory counter on a new day, restoring today's saved count if any."""
    today = _today()
    if _state["date"] == today:
        return
    used = 0
    try:
        saved = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
        if saved.get("date") == today:
            used = int(saved.get("used", 0))
    except (OSError, ValueError, TypeError):
        pass
    _state.update(date=today, used=used)


def _save() -> None:
    try:
        BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        BUDGET_FILE.write_text(json.dumps(_state), encoding="utf-8")
    except OSError:
        logger.warning("Could not save the API budget file; counting in memory only")


def allow_call() -> bool:
    """Reserve one API call. Returns False once today's budget is used up."""
    limit = daily_limit()
    if limit == 0:
        return True
    with _lock:
        _sync_with_today()
        if _state["used"] >= limit:
            logger.warning("Daily API budget of %s calls is used up", limit)
            return False
        _state["used"] += 1
        _save()
        return True


def usage() -> dict:
    """Return {'limit', 'used'} for today (limit 0 means unlimited)."""
    with _lock:
        _sync_with_today()
        return {"limit": daily_limit(), "used": _state["used"]}
