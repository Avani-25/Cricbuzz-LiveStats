"""Central configuration: every setting is read from here."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- API settings ---
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")
API_BASE_URL = os.getenv("API_BASE_URL")
API_TIMEOUT = (10, 60)   # (connect, read) seconds
API_RETRIES = 3

# --- Database settings ---
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/cricbuzz.db")

# --- App settings ---
LIVE_CACHE_TTL = int(os.getenv("LIVE_CACHE_TTL", "60"))   # seconds a live result is reused


# --- Endpoint registry: copy exact paths from the RapidAPI code snippets ---
ENDPOINTS = {
    "live_matches":   "/matches/v1/live",                      # confirmed
    "recent_matches": "/matches/v1/recent",                    # likely
    "series_list":    "/series/v1/international",              # likely
    "series_matches": "/series/v1/{series_id}",                # likely
    "teams_list":     "/teams/v1/international",               # likely
    "team_players":   "/teams/v1/{team_id}/players",            # likely
    "scorecard":      "/mcenter/v1/{match_id}/scard",          # likely
    "player_stats":   "/stats/v1/player/{player_id}",          # likely
    "top_stats":      "/stats/v1/rankings/batsmen",            # likely (may need ?formatType=odi)
    "venue_info":     "TODO",                                   # unsure, check sidebar
}



