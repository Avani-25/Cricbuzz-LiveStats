"""Plain-language error messages (no Streamlit dependency)."""


def friendly_error(exc: BaseException) -> str:
    """Turn a technical exception into a message a user can act on."""
    text = str(exc)
    low = text.lower()
    name = type(exc).__name__

    if name == "CricbuzzAPIError":
        if low.startswith(("401", "403")):
            return ("The API rejected your key. Check RAPIDAPI_KEY in .env and that "
                    "you are subscribed to the Cricbuzz API on RapidAPI.")
        if low.startswith("404"):
            return "That API endpoint was not found. Check the paths in config.ENDPOINTS."
        if low.startswith("429"):
            return "The API rate limit or monthly quota has been reached. Try again later."
        if low.startswith(("500", "502", "503", "504")):
            return "The Cricbuzz API had a server problem. Try again in a few minutes."
        return "The API could not be reached after several tries. Check your connection."
    if name in ("ConnectionError", "Timeout", "ReadTimeout", "ConnectTimeout"):
        return "Could not reach the API. Check your internet connection and try again."
    if "database is locked" in low:
        return "The database is busy. Wait a moment and try again."
    if "no such table" in low:
        return "The database has not been set up yet. Run notebooks/02_database_setup.ipynb."
    if "unable to open database" in low:
        return "The database file could not be opened. Check DATABASE_URL in .env."
    return "Something went wrong. Please try again."
