"""Build the project database from scratch with one command.

Run from the project root with the virtual environment active:

    python -m scripts.setup_db                  # tables + sample data
    python -m scripts.setup_db --from-cache     # also load matches saved in data/raw/
    python -m scripts.setup_db --no-seed        # tables only, no sample data
    python -m scripts.setup_db --reset          # delete the database first (asks to confirm)

API matches are loaded before the sample data, so the sample data can reuse their
teams and venues. Running it again is safe: rows are updated, never duplicated.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.match_service import flatten_matches  # noqa: E402
from utils import db_connection as db  # noqa: E402
from utils import seed_data  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"


def db_file():
    """Return the SQLite file path, or None when another database is configured."""
    url = db.get_engine().url
    if url.get_backend_name() == "sqlite" and url.database:
        return Path(url.database)
    return None


def load_cached_matches():
    """Load every saved live/recent response from data/raw/ and return the match count."""
    total = 0
    for path in sorted(RAW_DIR.glob("matches_v1_*.json")):
        try:
            rows = flatten_matches(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            print(f"  skipped {path.name} (not valid JSON)")
            continue
        if not rows["matches"]:
            print(f"  skipped {path.name} (no matches inside)")
            continue
        db.upsert_rows("teams", rows["teams"], ["team_id"])
        db.upsert_rows("venues", rows["venues"], ["venue_id"])
        db.upsert_rows("series", rows["series"], ["series_id"])
        db.upsert_rows("matches", rows["matches"], ["match_id"])
        print(f"  loaded {len(rows['matches'])} matches from {path.name}")
        total += len(rows["matches"])
    return total


def reset_database(assume_yes):
    """Delete the SQLite file. Returns False if the user declines or it is not SQLite."""
    path = db_file()
    if path is None:
        print("--reset only works with the default SQLite database.")
        return False
    if path.exists():
        if not assume_yes:
            answer = input(f"Delete {path} and rebuild it? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled. Nothing was changed.")
                return False
        db.get_engine().dispose()
        path.unlink()
        db._engine = None
        print(f"Deleted {path}")
    return True


def main(argv=None):
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(description="Build the Cricbuzz LiveStats database.")
    parser.add_argument("--from-cache", action="store_true",
                        help="load matches saved in data/raw/ (makes no API calls)")
    parser.add_argument("--no-seed", action="store_true", help="skip the generated sample data")
    parser.add_argument("--reset", action="store_true", help="delete the existing database first")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = parser.parse_args(argv)

    if args.reset and not reset_database(args.yes):
        return 1

    db.init_db()
    print("Tables ready.")
    if args.from_cache:
        loaded = load_cached_matches()
        print(f"{loaded} API matches loaded." if loaded else "No saved API matches found.")
    if not args.no_seed:
        print("Sample data:", seed_data.run_seed())

    print("\nRow counts:")
    for table, count in db.table_counts().items():
        print(f"  {table:24} {count:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
