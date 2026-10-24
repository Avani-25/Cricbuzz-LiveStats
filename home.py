"""Home page: project overview, database metrics and system health."""
import streamlit as st

from services import health_service
from utils import db_connection as db

st.title("🏏 Cricbuzz LiveStats")
st.caption("Real-time cricket insights & SQL-based analytics")


@st.cache_data(ttl=30)
def load_counts() -> dict:
    """Return table row counts, cached for 30 seconds."""
    return db.table_counts()


try:
    counts = load_counts()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Players", counts.get("players", 0))
    col2.metric("Matches", counts.get("matches", 0))
    col3.metric("Teams", counts.get("teams", 0))
    col4.metric("Venues", counts.get("venues", 0))
except Exception as exc:  # database missing or locked
    st.warning(f"Database not ready yet: {exc}")

st.write(
    "This app combines live data from the Cricbuzz API with a SQL database "
    "to show live matches, player rankings, 25 analytical queries and "
    "player record management."
)

st.subheader("How to use it")
st.markdown(
    "- **Live Matches**: current and recent matches from the API\n"
    "- **Top Stats**: career leaders by format, with charts\n"
    "- **SQL Queries**: the 25 analytical queries, plus a safe custom SELECT\n"
    "- **CRUD Operations**: add, edit and delete player records"
)
st.info("Match results, teams, venues and series come from the Cricbuzz API. "
        "Player profiles, career stats and scorecards are generated sample data "
        "(see the README).")

ICONS = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
with st.expander("🩺 System health"):
    if st.button("Re-run checks", key="home_health"):
        st.rerun()
    for item in health_service.run_checks():
        st.write(f"{ICONS[item['status']]} **{item['name']}**: {item['detail']}")
