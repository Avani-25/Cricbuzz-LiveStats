"""Top player statistics page: tables and charts from the database."""
import plotly.express as px
import streamlit as st

from models.validators import FORMATS
from services import stats_service as stats

st.title("🏆 Top Player Stats")
st.caption("Career leaders by format. Player statistics in this project are "
           "sample data (see the README).")

c1, c2, c3 = st.columns([2, 1, 1])
fmt = c1.radio("Format", FORMATS, horizontal=True, key="ts_format")
top_n = c2.slider("Top N", 5, 20, 10, key="ts_n")
min_matches = c3.number_input("Min. matches", 0, 200, 20, key="ts_min")

bat_leader, bowl_leader = stats.leaders(fmt)
m1, m2 = st.columns(2)
if bat_leader:
    m1.metric("Top run scorer", bat_leader["player"], f"{bat_leader['runs']:,} runs")
if bowl_leader:
    m2.metric("Top wicket taker", bowl_leader["player"], f"{bowl_leader['wickets']:,} wickets")


def bar(df, value_col, title):
    """Draw a horizontal bar chart and the table beneath it."""
    if df.empty:
        st.info("No players match these filters.")
        return
    fig = px.bar(df.sort_values(value_col, ascending=value_col in
                                ("bowling_avg", "economy_rate")),
                 x=value_col, y="player", color="country", orientation="h",
                 text=value_col, title=title)
    fig.update_layout(yaxis_title=None, legend_title_text="Country", height=420)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(df, width="stretch", hide_index=True)


tab_bat, tab_bowl, tab_all, tab_field = st.tabs(
    ["🏏 Batting", "🎯 Bowling", "⚖️ All-rounders", "🧤 Fielding"])

with tab_bat:
    metric = st.selectbox("Category", list(stats.BAT_METRICS), key="ts_bat_metric")
    df = stats.top_batters(fmt, metric, top_n, min_matches)
    bar(df, stats.BAT_METRICS[metric][0], f"{metric} · {fmt}")

with tab_bowl:
    metric = st.selectbox("Category", list(stats.BOWL_METRICS), key="ts_bowl_metric")
    min_w = st.number_input("Min. wickets", 0, 500, 20, key="ts_min_w")
    df = stats.top_bowlers(fmt, metric, top_n, min_w)
    bar(df, stats.BOWL_METRICS[metric][0], f"{metric} · {fmt}")

with tab_all:
    r, w = st.columns(2)
    min_runs = r.number_input("Min. runs", 0, 20000, 500, key="ts_ar_runs")
    min_wk = w.number_input("Min. wickets", 0, 500, 20, key="ts_ar_wkts")
    df = stats.allrounders(fmt, min_runs, min_wk)
    if df.empty:
        st.info("No all-rounders match these filters.")
    else:
        fig = px.scatter(df, x="runs", y="wickets", color="country", size="matches",
                         hover_name="player", title=f"All-rounders · {fmt}")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(df, width="stretch", hide_index=True)

with tab_field:
    metric = st.selectbox("Category", list(stats.FIELD_METRICS), key="ts_field_metric")
    df = stats.top_fielders(fmt, metric, top_n)
    bar(df, stats.FIELD_METRICS[metric][0], f"{metric} · {fmt}")

# ------------------------------------------------------------ optional API data
with st.expander("🌐 Official rankings from the Cricbuzz API (uses 1 API call)"):
    st.caption("Fetched only when you press the button, then cached on disk. "
               "If the API rejects the request, the error is shown here.")
    a1, a2 = st.columns(2)
    category = a1.selectbox("Category", list(stats.CATEGORY_SUFFIX), key="ts_api_cat")
    api_fmt = a2.selectbox("Format", list(stats.API_FORMATS), key="ts_api_fmt")
    if st.button("Fetch rankings", key="ts_api_btn"):
        try:
            st.session_state["api_rankings"] = stats.fetch_rankings(category, api_fmt)
        except Exception as exc:
            st.session_state.pop("api_rankings", None)
            st.error(f"Could not fetch rankings: {exc}")
    data = st.session_state.get("api_rankings")
    if data is not None:
        table = stats.records_from_json(data)
        if table is None:
            st.warning("Could not find a table in the response. Raw data:")
            st.json(data)
        else:
            st.dataframe(table, width="stretch", hide_index=True)
