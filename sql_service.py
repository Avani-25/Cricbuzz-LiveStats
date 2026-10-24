"""Run the stored analytics queries and (safely) user-written SELECT statements."""
import re

import pandas as pd

from sql.queries import QUERIES
from utils import db_connection as db

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|"
    r"vacuum|reindex|truncate|grant|revoke)\b", re.IGNORECASE)
MAX_ROWS = 5000


def _strip_noise(sql: str) -> str:
    """Remove comments and string literals so keyword checks only see real SQL."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_select(sql: str):
    """Return (ok, message). Only a single SELECT / WITH statement is allowed."""
    cleaned = _strip_noise(sql or "").strip().rstrip(";").strip()
    if not cleaned:
        return False, "Please enter a query."
    if ";" in cleaned:
        return False, "Only one statement at a time is allowed."
    if not re.match(r"(select|with)\b", cleaned, re.IGNORECASE):
        return False, "Only SELECT queries are allowed."
    bad = _FORBIDDEN.search(cleaned)
    if bad:
        return False, f"'{bad.group(0).upper()}' is not allowed in this runner."
    return True, ""


def run_named(key: str) -> pd.DataFrame:
    """Run one of the stored queries by key (e.g. 'q05')."""
    return db.run_query(QUERIES[key]["sql"])


def run_custom(sql: str):
    """Validate and run user SQL read-only. Returns (DataFrame | None, error | None)."""
    ok, message = validate_select(sql)
    if not ok:
        return None, message
    try:
        return db.run_readonly(sql, max_rows=MAX_ROWS), None
    except Exception as exc:   # pandas and SQLAlchemy both wrap the real database error
        cause = exc.__cause__ or exc
        text = str(getattr(cause, "orig", cause))
        if "interrupted" in text.lower():
            return None, "The query took longer than 5 seconds and was stopped."
        return None, f"SQL error: {text.splitlines()[0]}"


def schema_overview() -> pd.DataFrame:
    """Table and column names so users know what they can query."""
    rows = []
    for table in db.table_counts():
        info = db.run_query(f'PRAGMA table_info("{table}")')   # names come from sqlite_master
        rows.append({"table": table, "columns": ", ".join(info["name"])})
    return pd.DataFrame(rows)
