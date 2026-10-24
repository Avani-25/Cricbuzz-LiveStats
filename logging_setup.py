"""Central logging: rotating log file, console warnings, secrets redacted."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "cricbuzz.log"
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


class RedactingFormatter(logging.Formatter):
    """Replace secret values (the API key) with *** in every log line."""

    def format(self, record):
        text = super().format(record)
        key = getattr(config, "RAPIDAPI_KEY", None)
        if key and len(str(key)) > 6:
            text = text.replace(str(key), "***")
        return text


def setup_logging(level=logging.INFO):
    """Configure logging once per process (safe to call on every Streamlit rerun)."""
    global _configured
    if _configured:
        return LOG_FILE
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    formatter = RedactingFormatter(_FORMAT)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000,
                                       backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(console)

    for noisy in ("urllib3", "watchdog", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True
    logging.getLogger(__name__).info("Logging started")
    return LOG_FILE
