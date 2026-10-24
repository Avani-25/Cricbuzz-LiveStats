"""Cricbuzz LiveStats: entry point and navigation."""
import logging

import streamlit as st

from utils.bootstrap import ensure_database
from utils.errors import handle_page_errors
from utils.logging_setup import setup_logging
from utils.runtime import DEMO_NOTICE, is_demo_mode

setup_logging()
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Cricbuzz LiveStats",
    page_icon="🏏",
    layout="wide",
)


@st.cache_resource(show_spinner="Setting up the database...")
def prepare_database():
    """Build the database on the first run of a fresh install (once per process)."""
    return ensure_database()


try:
    prepare_database()
except Exception:
    logger.exception("Automatic database setup failed")   # pages still show friendly errors

if is_demo_mode():
    st.sidebar.info(DEMO_NOTICE)

pages = [
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/live_matches.py", title="Live Matches", icon="📡"),
    st.Page("pages/top_stats.py", title="Top Stats", icon="🏆"),
    st.Page("pages/sql_queries.py", title="SQL Queries", icon="🧮"),
    st.Page("pages/crud_operations.py", title="CRUD Operations", icon="🛠"),
]

navigation = st.navigation(pages)
handle_page_errors(navigation.run)
