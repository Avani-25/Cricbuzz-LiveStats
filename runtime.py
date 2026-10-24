"""Settings that describe where the app is running (read from environment variables)."""
import os

DEMO_NOTICE = ("Demo mode: player stats and scorecards are generated sample data, "
               "and any changes you make are lost when the app restarts.")


def env_flag(name: str, default: bool = False) -> bool:
    """Read an on/off environment variable ('1', 'true', 'yes', 'on' mean on)."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_demo_mode() -> bool:
    """True when DEMO_MODE is switched on (set it in the hosting secrets)."""
    return env_flag("DEMO_MODE", False)
