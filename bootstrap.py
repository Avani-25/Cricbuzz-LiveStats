"""First-run setup: build the database automatically when the app starts with none."""
import logging

from utils import db_connection as db
from utils.runtime import env_flag

logger = logging.getLogger(__name__)


def database_is_empty() -> bool:
    """True when there are no tables, or both players and matches are empty."""
    try:
        counts = db.table_counts()
    except Exception:
        return True
    return not counts or (counts.get("players", 0) == 0 and counts.get("matches", 0) == 0)


def ensure_database() -> str:
    """Create the tables and, if the database is empty, the sample data.

    Returns 'disabled', 'ready' (nothing to do) or 'seeded'. Set AUTO_SETUP=0 to switch it off.
    """
    if not env_flag("AUTO_SETUP", True):
        return "disabled"
    db.init_db()                      # CREATE ... IF NOT EXISTS, safe to repeat
    if not database_is_empty():
        return "ready"
    from utils import seed_data       # imported late: only needed on a first run
    summary = seed_data.run_seed()
    logger.info("Empty database detected: seeded sample data %s", summary)
    return "seeded"
