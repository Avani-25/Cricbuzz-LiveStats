"""Database access: one shared SQLAlchemy engine and safe helpers."""
import logging
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

import config

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_engine = None


class _StdDev:
    """SQLite aggregate: sample standard deviation (MySQL/PostgreSQL have STDDEV built in)."""

    def __init__(self):
        self.n, self.mean, self.m2 = 0, 0.0, 0.0

    def step(self, value):
        if value is None:
            return
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    def finalize(self):
        return (self.m2 / (self.n - 1)) ** 0.5 if self.n > 1 else None


def _resolve_url(url: str) -> str:
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////"):
        rel = url[len(prefix):]
        if rel != ":memory:" and not Path(rel).drive:
            abs_path = PROJECT_ROOT / rel
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{abs_path.as_posix()}"
    return url


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = _resolve_url(config.DATABASE_URL)
        _engine = create_engine(url, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _enable_foreign_keys(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys = ON")
                cur.close()
                dbapi_conn.create_aggregate("STDDEV", 1, _StdDev)
    return _engine


def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a SELECT with bound parameters and return a DataFrame."""
    with get_engine().connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def run_readonly(sql: str, max_rows: int = 5000, timeout_s: float = 5.0) -> pd.DataFrame:
    """Run user-supplied SQL on a read-only connection with a time limit."""
    with get_engine().connect() as conn:
        raw = conn.connection.driver_connection
        started = time.monotonic()
        raw.execute("PRAGMA query_only = ON")
        raw.set_progress_handler(
            lambda: 1 if time.monotonic() - started > timeout_s else 0, 100_000)
        try:
            return pd.read_sql_query(text(sql), conn).head(max_rows)
        finally:
            raw.set_progress_handler(None, 0)
            raw.execute("PRAGMA query_only = OFF")


def execute(sql: str, params: dict | None = None) -> int:
    """Run INSERT/UPDATE/DELETE in a transaction and return the affected row count."""
    with get_engine().begin() as conn:
        return conn.execute(text(sql), params or {}).rowcount


def upsert_rows(table: str, rows: list[dict], conflict_cols: list[str]) -> int:
    """Insert rows; if the conflict columns already exist, update the rest.

    `table` and column names come from our own code, never from user input.
    All dicts in `rows` must have the same keys.
    """
    if not rows:
        return 0
    cols = list(rows[0].keys())
    updates = [c for c in cols if c not in conflict_cols]
    action = ("UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in updates)
              if updates else "NOTHING")
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) "
           f"VALUES ({', '.join(':' + c for c in cols)}) "
           f"ON CONFLICT({', '.join(conflict_cols)}) DO {action}")
    with get_engine().begin() as conn:
        conn.execute(text(sql), rows)
    return len(rows)


def init_db(schema_path=None) -> None:
    """Create all tables and indexes from sql/schema.sql (safe to re-run)."""
    schema_path = Path(schema_path or PROJECT_ROOT / "sql" / "schema.sql")
    raw = get_engine().raw_connection()
    try:
        raw.executescript(schema_path.read_text(encoding="utf-8"))
        raw.commit()
    finally:
        raw.close()


def table_counts() -> dict:
    """Return {table_name: row_count} for every user table."""
    names = run_query(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")["name"].tolist()
    return {n: int(run_query(f'SELECT COUNT(*) AS n FROM "{n}"')["n"].iloc[0])
            for n in names}
