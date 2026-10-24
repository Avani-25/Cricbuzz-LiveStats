"""Top-player statistics from the database, plus optional API rankings."""
import pandas as pd

import config
from utils import db_connection as db

# metric label -> (column, sort direction). Columns come from this whitelist only.
BAT_METRICS = {
    "Most runs": ("runs", "DESC"),
    "Highest score": ("highest_score", "DESC"),
    "Best batting average": ("batting_avg", "DESC"),
    "Most centuries": ("centuries", "DESC"),
    "Most fifties": ("fifties", "DESC"),
    "Best strike rate": ("strike_rate", "DESC"),
}
BOWL_METRICS = {
    "Most wickets": ("wickets", "DESC"),
    "Best bowling average": ("bowling_avg", "ASC"),
    "Best economy rate": ("economy_rate", "ASC"),
}
FIELD_METRICS = {
    "Most catches": ("catches", "DESC"),
    "Most stumpings": ("stumpings", "DESC"),
}


def _top(metrics, metric, fmt, n, where_extra, params, columns):
    column, direction = metrics[metric]          # KeyError = invalid metric, never SQL
    sql = f"""
        SELECT p.full_name AS player, p.country, p.playing_role, {columns}
        FROM player_career_stats c
        JOIN players p ON p.player_id = c.player_id
        WHERE c.format = :fmt AND c.{column} IS NOT NULL {where_extra}
        ORDER BY c.{column} {direction}, c.matches DESC
        LIMIT :n"""
    return db.run_query(sql, {"fmt": fmt, "n": int(n), **params})


def top_batters(fmt, metric, n=10, min_matches=10):
    """Top batters for a format by one of BAT_METRICS (parameterized, whitelisted column)."""
    return _top(BAT_METRICS, metric, fmt, n, "AND c.matches >= :mm",
                {"mm": int(min_matches)},
                "c.matches, c.runs, c.highest_score, c.batting_avg, "
                "c.strike_rate, c.centuries, c.fifties")


def top_bowlers(fmt, metric, n=10, min_wickets=20):
    """Top bowlers for a format by one of BOWL_METRICS."""
    return _top(BOWL_METRICS, metric, fmt, n, "AND c.wickets >= :mw",
                {"mw": int(min_wickets)},
                "c.matches, c.wickets, c.bowling_avg, c.economy_rate")


def top_fielders(fmt, metric, n=10):
    """Top fielders for a format by catches or stumpings."""
    return _top(FIELD_METRICS, metric, fmt, n, "AND c.matches > 0", {},
                "c.matches, c.catches, c.stumpings")


def allrounders(fmt, min_runs=500, min_wickets=20):
    """All-rounders who meet minimum runs and wickets in a format."""
    return db.run_query(
        """
        SELECT p.full_name AS player, p.country, c.matches, c.runs, c.wickets,
               c.batting_avg, c.bowling_avg
        FROM player_career_stats c
        JOIN players p ON p.player_id = c.player_id
        WHERE c.format = :fmt AND p.playing_role = 'All-rounder'
          AND c.runs >= :r AND c.wickets >= :w
        ORDER BY c.runs + 20 * c.wickets DESC""",
        {"fmt": fmt, "r": int(min_runs), "w": int(min_wickets)})


def leaders(fmt):
    """Headline numbers for the page: top run scorer and top wicket taker."""
    bat = top_batters(fmt, "Most runs", 1, 1)
    bowl = top_bowlers(fmt, "Most wickets", 1, 1)
    return (bat.iloc[0].to_dict() if len(bat) else None,
            bowl.iloc[0].to_dict() if len(bowl) else None)


# --------------------------------------------------------------- API (optional)
CATEGORY_SUFFIX = {"Batsmen": "batsmen", "Bowlers": "bowlers", "All-rounders": "allrounders"}
API_FORMATS = {"Test": "test", "ODI": "odi", "T20I": "t20"}


def ranking_path(category):
    """Build the rankings path from the registered `top_stats` endpoint."""
    base = config.ENDPOINTS.get("top_stats")
    if not base or base == "TODO":
        return None
    return base.rsplit("/", 1)[0] + "/" + CATEGORY_SUFFIX[category]


def fetch_rankings(category, fmt):
    """Fetch official rankings (1 API call; cached on disk afterwards)."""
    from api.cricbuzz_client import CricbuzzClient
    path = ranking_path(category)
    if path is None:
        raise ValueError("No 'top_stats' endpoint is registered in config.ENDPOINTS.")
    return CricbuzzClient().get(path, params={"formatType": API_FORMATS[fmt]})


def records_from_json(data):
    """Find the first list of dicts (3+ items) anywhere in a JSON blob -> DataFrame."""
    stack = [data]
    while stack:
        item = stack.pop(0)
        if isinstance(item, list):
            if len(item) >= 3 and all(isinstance(x, dict) for x in item):
                return pd.json_normalize(item)
            stack.extend(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
    return None
