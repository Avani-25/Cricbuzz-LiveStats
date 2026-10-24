"""Live and recent matches from the API: fetching, display tables, scorecards."""
import json
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.exc import IntegrityError

import config
from api.cricbuzz_client import CricbuzzAPIError, CricbuzzClient
from services.match_service import flatten_matches
from utils.friendly import friendly_error
from utils import db_connection as db

logger = logging.getLogger(__name__)

UI_RETRIES = 2          # a page should not make the user wait through many retries
KINDS = {"Live": "live_matches", "Recent": "recent_matches"}
COLUMNS = ["match_id", "match_type", "series", "match_desc", "match_format",
           "state", "status", "team1", "team2", "score1", "score2",
           "venue", "city", "start_utc"]


# ------------------------------------------------------------------ parsing
def _score_text(team_score):
    """{'inngs1': {'runs': 245, 'wickets': 6, 'overs': 50}} -> '245/6 (50)'."""
    if not isinstance(team_score, dict):
        return ""
    parts = []
    for key in sorted(k for k in team_score if str(k).startswith("inngs")):
        inn = team_score[key] or {}
        runs = inn.get("runs")
        if runs is None:
            continue
        wickets, overs = inn.get("wickets"), inn.get("overs")
        text = str(runs) + (f"/{wickets}" if wickets not in (None, 10) else "")
        if overs is not None:
            text += f" ({overs})"
        parts.append(text)
    return " & ".join(parts)


def _start_text(ms):
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def matches_to_frame(data):
    """Flatten the typeMatches JSON into one display row per match."""
    rows = []
    for type_block in (data or {}).get("typeMatches", []):
        for series_block in type_block.get("seriesMatches", []):
            wrapper = series_block.get("seriesAdWrapper")
            if not wrapper:
                continue
            for item in wrapper.get("matches", []):
                info = item.get("matchInfo") or {}
                if info.get("matchId") is None:
                    continue
                score = item.get("matchScore") or {}
                venue = info.get("venueInfo") or {}
                rows.append({
                    "match_id": info["matchId"],
                    "match_type": type_block.get("matchType"),
                    "series": info.get("seriesName") or wrapper.get("seriesName"),
                    "match_desc": info.get("matchDesc"),
                    "match_format": info.get("matchFormat"),
                    "state": info.get("state") or "",
                    "status": info.get("status") or "",
                    "team1": (info.get("team1") or {}).get("teamName"),
                    "team2": (info.get("team2") or {}).get("teamName"),
                    "score1": _score_text(score.get("team1Score")),
                    "score2": _score_text(score.get("team2Score")),
                    "venue": venue.get("ground"),
                    "city": venue.get("city"),
                    "start_utc": _start_text(info.get("startDate")),
                })
    return pd.DataFrame(rows, columns=COLUMNS)


def state_icon(state):
    """Return a coloured dot for a match state (live, complete, delayed...)."""
    s = (state or "").lower()
    if "progress" in s or s == "live":
        return "🟢"
    if "complete" in s or "result" in s:
        return "⚪"
    if any(w in s for w in ("delay", "rain", "stumps", "break", "lunch", "tea", "innings")):
        return "🟠"
    if any(w in s for w in ("toss", "preview", "upcoming")):
        return "🔵"
    return "⚫"


# ----------------------------------------------------------------- fetching
def fetch_matches(kind):
    """Fetch live or recent matches. Returns (raw_json | None, meta).

    If the API fails, falls back to the last saved response (meta['stale']).
    """
    path = config.ENDPOINTS.get(KINDS[kind])
    if not path or path == "TODO":
        return None, {"stale": False, "quota": None,
                      "error": f"No '{KINDS[kind]}' endpoint is registered in config.ENDPOINTS."}
    client = CricbuzzClient()
    try:
        data = client.get(path, use_cache=False, retries=UI_RETRIES)   # always ask the API
        return data, {"stale": False, "error": None, "quota": client.quota_remaining}
    except CricbuzzAPIError as exc:
        saved = client._cache_file(path, None)
        if saved.exists():
            logger.warning("API failed, using saved response: %s", exc)
            return (json.loads(saved.read_text(encoding="utf-8")),
                    {"stale": True, "error": str(exc), "friendly": friendly_error(exc),
                     "quota": client.quota_remaining})
        return None, {"stale": False, "error": str(exc), "friendly": friendly_error(exc),
                      "quota": client.quota_remaining}


def sync_to_db(data):
    """Save the matches (and their teams, venues, series) into the database."""
    rows = flatten_matches(data)
    try:
        db.upsert_rows("teams", rows["teams"], ["team_id"])
        db.upsert_rows("venues", rows["venues"], ["venue_id"])
        db.upsert_rows("series", rows["series"], ["series_id"])
        db.upsert_rows("matches", rows["matches"], ["match_id"])
    except IntegrityError as exc:
        return False, f"Could not save: {exc.orig}"
    return True, (f"Saved {len(rows['matches'])} matches, {len(rows['teams'])} teams, "
                  f"{len(rows['venues'])} venues, {len(rows['series'])} series.")


# --------------------------------------------------------------- scorecards
BAT_COLS = {"batName": "Batter", "runs": "R", "balls": "B", "fours": "4s",
            "sixes": "6s", "strikeRate": "SR", "outDesc": "Dismissal"}
BOWL_COLS = {"bowlName": "Bowler", "overs": "O", "maidens": "M", "runs": "R",
             "wickets": "W", "economy": "Econ"}


def fetch_scorecard(match_id, fresh=False):
    """Fetch one match scorecard (1 API call unless it is already saved)."""
    path = config.ENDPOINTS.get("scorecard")
    if not path or path == "TODO":
        raise ValueError("No 'scorecard' endpoint is registered in config.ENDPOINTS.")
    return CricbuzzClient().get(path.format(match_id=match_id), use_cache=not fresh,
                                retries=UI_RETRIES)


def _table(records, columns):
    if not records:
        return None
    df = pd.DataFrame(records)
    present = [c for c in columns if c in df.columns]
    return df[present].rename(columns=columns) if present else None


def scorecard_tables(data):
    """Return [(title, batting_df, bowling_df), ...]; empty if the shape is unknown."""
    out = []
    for inn in (data or {}).get("scoreCard") or []:
        bat = inn.get("batTeamDetails") or {}
        bowl = inn.get("bowlTeamDetails") or {}
        bat_df = _table(list((bat.get("batsmenData") or {}).values()), BAT_COLS)
        bowl_df = _table(list((bowl.get("bowlersData") or {}).values()), BOWL_COLS)
        if bat_df is None and bowl_df is None:
            continue
        score = inn.get("scoreDetails") or {}
        total = ""
        if score.get("runs") is not None:
            total = f" {score['runs']}/{score.get('wickets', '?')} ({score.get('overs', '?')} ov)"
        title = f"{bat.get('batTeamName', 'Innings')} · innings {inn.get('inningsId', '')}{total}"
        out.append((title, bat_df, bowl_df))
    return out
