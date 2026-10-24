"""Create / read / update / delete for players and their career stats."""
import logging
from dataclasses import dataclass, field

from sqlalchemy import text

from models.validators import validate_player, validate_stats
from utils import db_connection as db

logger = logging.getLogger(__name__)

NEW_PLAYER_ID_FLOOR = 1_000_000   # user-created players start above API/seed IDs

STAT_COLUMNS = ["matches", "innings", "runs", "highest_score", "batting_avg",
                "strike_rate", "centuries", "fifties", "wickets", "bowling_avg",
                "economy_rate", "catches", "stumpings"]


@dataclass
class Result:
    """Outcome of a CRUD action: success flag, message, player id and any errors."""
    ok: bool
    message: str
    player_id: int | None = None
    errors: list = field(default_factory=list)


def _fail(errors):
    logger.info("CRUD rejected: %s", " ".join(errors))
    return Result(False, " ".join(errors), errors=list(errors))


# ---------------------------------------------------------------- READ
def list_players(search=None, role=None, country=None):
    """Players matching optional filters (all values are bound parameters)."""
    return db.run_query(
        """
        SELECT player_id, full_name, country, playing_role,
               batting_style, bowling_style
        FROM players
        WHERE (:search IS NULL OR full_name LIKE '%' || :search || '%')
          AND (:role IS NULL OR playing_role = :role)
          AND (:country IS NULL OR country = :country)
        ORDER BY full_name
        """,
        {"search": search or None, "role": role or None, "country": country or None},
    )


def list_countries():
    """Return the distinct player countries, sorted."""
    df = db.run_query("SELECT DISTINCT country FROM players "
                      "WHERE country IS NOT NULL ORDER BY country")
    return df["country"].tolist()


def get_player(player_id):
    """Return one player as a dict, or None if the id does not exist."""
    df = db.run_query("SELECT * FROM players WHERE player_id = :i", {"i": player_id})
    return None if df.empty else df.iloc[0].to_dict()


def get_stats(player_id):
    """Return all career-stat rows (one per format) for a player."""
    return db.run_query(
        "SELECT * FROM player_career_stats WHERE player_id = :i ORDER BY format",
        {"i": player_id})


def player_footprint(player_id):
    """How many rows depend on this player (shown before a delete)."""
    def count(table):          # table names are fixed strings below, never user input
        return int(db.run_query(
            f"SELECT COUNT(*) n FROM {table} WHERE player_id = :i",
            {"i": player_id})["n"].iloc[0])

    return {"career_stats": count("player_career_stats"),
            "batting_rows": count("batting_performances"),
            "bowling_rows": count("bowling_performances")}


# -------------------------------------------------------------- CREATE
def _insert_stats(conn, player_id, stats):
    cols = ["player_id", "format"] + STAT_COLUMNS
    params = {"player_id": player_id, **{k: stats.get(k) for k in ["format"] + STAT_COLUMNS}}
    updates = ", ".join(f"{c} = excluded.{c}" for c in STAT_COLUMNS)
    conn.execute(text(
        f"INSERT INTO player_career_stats ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)}) "
        f"ON CONFLICT(player_id, format) DO UPDATE SET {updates}"), params)


def create_player(data, stats=None):
    """Add a player (and optionally one career-stats row) in one transaction."""
    clean, errors = validate_player(data)
    clean_stats = None
    if stats:
        clean_stats, stat_errors = validate_stats(stats)
        errors += stat_errors
    if errors:
        return _fail(errors)

    with db.get_engine().begin() as conn:
        dup = conn.execute(text(
            "SELECT 1 FROM players WHERE lower(full_name) = lower(:n) "
            "AND lower(country) = lower(:c)"),
            {"n": clean["full_name"], "c": clean["country"]}).first()
        if dup:
            return _fail([f"{clean['full_name']} ({clean['country']}) already exists."])
        new_id = conn.execute(text(
            "SELECT MAX(COALESCE(MAX(player_id), 0), :floor) + 1 FROM players"),
            {"floor": NEW_PLAYER_ID_FLOOR - 1}).scalar()
        conn.execute(text(
            "INSERT INTO players (player_id, full_name, country, playing_role, "
            "batting_style, bowling_style) VALUES (:player_id, :full_name, "
            ":country, :playing_role, :batting_style, :bowling_style)"),
            {"player_id": new_id, **clean})
        if clean_stats:
            _insert_stats(conn, new_id, clean_stats)
    logger.info("CRUD create: player %s (ID %s)", clean["full_name"], new_id)
    return Result(True, f"Added {clean['full_name']} (ID {new_id}).", new_id)


# -------------------------------------------------------------- UPDATE
def update_player(player_id, data):
    """Validate and update a player's profile; returns a Result."""
    clean, errors = validate_player(data)
    if errors:
        return _fail(errors)
    with db.get_engine().begin() as conn:
        dup = conn.execute(text(
            "SELECT 1 FROM players WHERE lower(full_name) = lower(:n) "
            "AND lower(country) = lower(:c) AND player_id <> :i"),
            {"n": clean["full_name"], "c": clean["country"], "i": player_id}).first()
        if dup:
            return _fail([f"Another player named {clean['full_name']} "
                          f"({clean['country']}) already exists."])
        changed = conn.execute(text(
            "UPDATE players SET full_name = :full_name, country = :country, "
            "playing_role = :playing_role, batting_style = :batting_style, "
            "bowling_style = :bowling_style WHERE player_id = :i"),
            {"i": player_id, **clean}).rowcount
    if not changed:
        return _fail([f"No player with ID {player_id}."])
    logger.info("CRUD update: player ID %s", player_id)
    return Result(True, f"Updated {clean['full_name']}.", player_id)


def save_stats(player_id, stats):
    """Insert or replace one player's career stats for one format."""
    clean, errors = validate_stats(stats)
    if errors:
        return _fail(errors)
    if get_player(player_id) is None:
        return _fail([f"No player with ID {player_id}."])
    with db.get_engine().begin() as conn:
        _insert_stats(conn, player_id, clean)
    logger.info("CRUD stats saved: player ID %s, format %s", player_id, clean["format"])
    return Result(True, f"Saved {clean['format']} stats.", player_id)


# -------------------------------------------------------------- DELETE
def delete_stats(player_id, fmt):
    """Delete one player's stats row for a single format."""
    n = db.execute("DELETE FROM player_career_stats "
                   "WHERE player_id = :i AND format = :f", {"i": player_id, "f": fmt})
    if not n:
        return _fail([f"No {fmt} stats for player {player_id}."])
    logger.info("CRUD stats deleted: player ID %s, format %s", player_id, fmt)
    return Result(True, f"Deleted {fmt} stats.", player_id)


def delete_player(player_id):
    """Delete a player and everything that references them, atomically."""
    player = get_player(player_id)
    if player is None:
        return _fail([f"No player with ID {player_id}."])
    with db.get_engine().begin() as conn:      # children first, then the parent
        counts = {}
        for table in ("batting_performances", "bowling_performances",
                      "player_career_stats"):
            counts[table] = conn.execute(
                text(f"DELETE FROM {table} WHERE player_id = :i"),
                {"i": player_id}).rowcount
        conn.execute(text("DELETE FROM players WHERE player_id = :i"),
                     {"i": player_id})
    extra = sum(counts.values())
    logger.warning("CRUD delete: player %s (ID %s) and %s related rows",
                   player["full_name"], player_id, extra)
    return Result(True, f"Deleted {player['full_name']} and {extra} related rows.",
                  player_id)
