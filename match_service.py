"""Turn Cricbuzz match-list JSON into rows for our database tables."""
import re
from datetime import datetime, timezone

WON_RE = re.compile(
    r"^(?P<team>.+?)\s+won by\s+(?P<n>\d+)\s+(?P<unit>runs?|wkts?|wickets?)",
    re.IGNORECASE)
TOSS_RE = re.compile(
    r"^(?P<team>.+?)\s*opt(?:ed)?\s+to\s+(?P<dec>bat|bowl)", re.IGNORECASE)


def ms_to_date(value):
    """Epoch milliseconds (string or int) -> 'YYYY-MM-DD', or None."""
    try:
        ts = int(value) / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _team_id_from_text(label, team1, team2):
    """Match a team label from status text to team1/team2 ids."""
    label = (label or "").strip().lower()
    for team in (team1, team2):
        if label and label in (str(team.get("name", "")).lower(),
                               str(team.get("short", "")).lower()):
            return team["id"]
    return None


def parse_status(status, team1, team2):
    """Extract winner, margin and toss info from the human-readable status."""
    out = {"winner_id": None, "victory_margin": None, "victory_type": None,
           "toss_winner_id": None, "toss_decision": None}
    status = (status or "").strip()

    m = WON_RE.match(status)
    if m:
        out["winner_id"] = _team_id_from_text(m["team"], team1, team2)
        out["victory_margin"] = int(m["n"])
        unit = m["unit"].lower()
        out["victory_type"] = "runs" if unit.startswith("run") else "wickets"
    elif "tied" in status.lower():
        out["victory_type"] = "tie"
    elif "no result" in status.lower():
        out["victory_type"] = "no result"

    t = TOSS_RE.match(status)
    if t:
        out["toss_winner_id"] = _team_id_from_text(t["team"], team1, team2)
        out["toss_decision"] = t["dec"].lower()
    return out


def flatten_matches(data):
    """Walk typeMatches -> seriesMatches -> matches and build table rows.

    Returns a dict of lists: teams, venues, series, matches, plus 'skipped'.
    Missing keys never crash the loop; incomplete matches are counted and skipped.
    """
    teams, venues, series, matches = {}, {}, {}, {}
    skipped = 0

    for type_block in data.get("typeMatches", []):
        for series_block in type_block.get("seriesMatches", []):
            wrapper = series_block.get("seriesAdWrapper")
            if not wrapper:
                continue
            for item in wrapper.get("matches", []):
                info = item.get("matchInfo") or {}
                t1, t2 = info.get("team1") or {}, info.get("team2") or {}
                team1 = {"id": t1.get("teamId"), "name": t1.get("teamName"),
                         "short": t1.get("teamSName")}
                team2 = {"id": t2.get("teamId"), "name": t2.get("teamName"),
                         "short": t2.get("teamSName")}

                if (info.get("matchId") is None or team1["id"] is None
                        or team2["id"] is None or team1["id"] == team2["id"]
                        or not team1["name"] or not team2["name"]):
                    skipped += 1
                    continue

                for t in (team1, team2):
                    teams[t["id"]] = {"team_id": t["id"], "team_name": t["name"],
                                      "short_name": t["short"], "country": None}

                venue = info.get("venueInfo") or {}
                venue_id = venue.get("id")
                if venue_id is None or not venue.get("ground"):
                    venue_id = None   # venue_name is NOT NULL in the schema
                else:
                    venues[venue_id] = {"venue_id": venue_id,
                                        "venue_name": venue.get("ground"),
                                        "city": venue.get("city"),
                                        "country": None, "capacity": None}

                series_id = info.get("seriesId") or wrapper.get("seriesId")
                series_name = info.get("seriesName") or wrapper.get("seriesName")
                if series_id is None or not series_name:
                    series_id = None  # series_name is NOT NULL in the schema
                else:
                    series[series_id] = {
                        "series_id": series_id,
                        "series_name": series_name,
                        "host_country": None,
                        "match_type": info.get("matchFormat"),
                        "start_date": ms_to_date(info.get("seriesStartDt")),
                        "total_matches": None}

                parsed = parse_status(info.get("status"), team1, team2)
                matches[info["matchId"]] = {
                    "match_id": info["matchId"], "series_id": series_id,
                    "match_desc": info.get("matchDesc"),
                    "match_format": info.get("matchFormat"),
                    "match_date": ms_to_date(info.get("startDate")),
                    "team1_id": team1["id"], "team2_id": team2["id"],
                    "venue_id": venue_id, **parsed,
                    "state": info.get("state")}

    return {"teams": list(teams.values()), "venues": list(venues.values()),
            "series": list(series.values()), "matches": list(matches.values()),
            "skipped": skipped}

