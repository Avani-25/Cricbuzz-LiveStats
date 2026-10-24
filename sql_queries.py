"""SQL analytics page: 25 stored queries plus a safe custom SELECT runner."""
import streamlit as st

from services import sql_service
from sql.queries import LEVELS, QUERIES

st.title("🧮 SQL Analytics")
st.caption("Run the project's 25 analytical queries or write your own SELECT.")

tab_named, tab_custom = st.tabs(["📚 Project queries", "⌨️ Custom SQL"])


@st.cache_data(ttl=60, show_spinner=False)
def cached_run(key):
    """Run a stored query by key, cached for 60 seconds."""
    return sql_service.run_named(key)


with tab_named:
    level = st.radio("Level", LEVELS, horizontal=True, key="sql_level")
    keys = [k for k, q in QUERIES.items() if q["level"] == level]
    key = st.selectbox(
        "Query", keys, key=f"sql_pick_{level}",
        format_func=lambda k: f"{k.upper()} · {QUERIES[k]['title']}")

    st.code(QUERIES[key]["sql"], language="sql")
    try:
        df = cached_run(key)
        st.caption(f"{len(df)} rows")
        if df.empty:
            st.info("This query returned no rows. The database may not hold enough data yet.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("⬇ Download CSV", df.to_csv(index=False),
                               f"{key}.csv", "text/csv", key=f"dl_{key}")
    except Exception as exc:
        st.error(f"Could not run this query: {exc}")

with tab_custom:
    with st.expander("Tables and columns"):
        st.dataframe(sql_service.schema_overview(), width="stretch", hide_index=True)
    st.caption("Read-only: one SELECT (or WITH ... SELECT), at most 5,000 rows, 5-second limit.")

    with st.form("custom_sql"):
        sql = st.text_area(
            "Your query", height=160, key="custom_sql_text",
            value="SELECT full_name, country, playing_role\nFROM players\nLIMIT 10")
        run = st.form_submit_button("▶ Run query")

    if run:
        result, error = sql_service.run_custom(sql)
        if error:
            st.error(error)
        else:
            st.caption(f"{len(result)} rows")
            st.dataframe(result, width="stretch", hide_index=True)
            st.download_button("⬇ Download CSV", result.to_csv(index=False),
                               "custom_query.csv", "text/csv", key="dl_custom")
