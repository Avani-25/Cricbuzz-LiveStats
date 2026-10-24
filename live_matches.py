"""Live matches page: current and recent matches from the Cricbuzz API."""
import streamlit as st

import config
from services import live_service as live
from utils.friendly import friendly_error

st.title("📡 Live Matches")
st.caption("Data from the Cricbuzz API. Cached for 60 seconds to protect the free quota.")


@st.cache_data(ttl=config.LIVE_CACHE_TTL, show_spinner="Fetching live matches...")
def get_live():
    """Fetch live matches (cached for the live TTL)."""
    return live.fetch_matches("Live")


@st.cache_data(ttl=300, show_spinner="Fetching recent matches...")
def get_recent():
    """Fetch recent matches (cached for 5 minutes)."""
    return live.fetch_matches("Recent")


top = st.columns([2, 1, 1])
kind = top[0].radio("Show", ["Live", "Recent"], horizontal=True, key="lm_kind")
if top[1].button("🔄 Refresh now", key="lm_refresh"):
    get_live.clear()
    get_recent.clear()
    st.rerun()

data, meta = get_live() if kind == "Live" else get_recent()

if meta.get("quota") is not None:
    top[2].metric("API calls left", meta["quota"])
if meta.get("stale"):
    st.warning("Showing the last saved response. "
               f"{meta.get('friendly', 'The API could not be reached.')}")
    st.caption(f"Technical detail: {meta['error'][:150]}")
elif data is None:
    st.error(meta.get("friendly") or f"Could not load matches: {meta.get('error')}")
    if meta.get("error"):
        st.caption(f"Technical detail: {meta['error'][:150]}")
    st.stop()

df = live.matches_to_frame(data)
if df.empty:
    st.info(f"No {kind.lower()} matches right now.")
    st.stop()

# ----------------------------------------------------------------- filters
f1, f2, f3, f4 = st.columns(4)
types = f1.multiselect("Type", sorted(df["match_type"].dropna().unique()), key="lm_types")
states = f2.multiselect("State", sorted(df["state"].unique()), key="lm_states")
formats = f3.multiselect("Format", sorted(df["match_format"].dropna().unique()), key="lm_formats")
team = f4.text_input("Team contains", key="lm_team").strip().lower()

view = df
if types:
    view = view[view["match_type"].isin(types)]
if states:
    view = view[view["state"].isin(states)]
if formats:
    view = view[view["match_format"].isin(formats)]
if team:
    view = view[view["team1"].str.lower().str.contains(team, na=False, regex=False)
                | view["team2"].str.lower().str.contains(team, na=False, regex=False)]

limit = st.slider("Matches to show", 5, 50, 15, key="lm_limit")
st.caption(f"{len(view)} of {len(df)} matches match your filters")

tab_cards, tab_table = st.tabs(["🃏 Cards", "📋 Table"])

with tab_cards:
    for r in view.head(limit).itertuples():
        with st.container(border=True):
            head = st.columns([3, 1])
            head[0].markdown(f"**{r.team1}** vs **{r.team2}**")
            head[1].markdown(f"{live.state_icon(r.state)} {r.state or 'n/a'}")
            st.caption(f"{r.series} · {r.match_desc} · {r.match_format}")
            if r.score1 or r.score2:
                st.write(f"{r.team1}: **{r.score1 or '-'}**  |  {r.team2}: **{r.score2 or '-'}**")
            if r.status:
                st.write(r.status)
            where = ", ".join(x for x in (r.venue, r.city) if x)
            st.caption(f"📍 {where or 'venue unknown'}" + (f" · {r.start_utc}" if r.start_utc else ""))

            box = f"sc_{r.match_id}"
            if st.button("📋 Scorecard (1 API call)", key=f"scbtn_{r.match_id}"):
                try:
                    st.session_state[box] = live.fetch_scorecard(
                        r.match_id, fresh=(r.state or "").lower() != "complete")
                except Exception as exc:
                    st.session_state[box] = {"_error": friendly_error(exc)}
            card = st.session_state.get(box)
            if card is not None:
                if "_error" in card:
                    st.error(f"Could not load the scorecard. {card['_error']}")
                else:
                    tables = live.scorecard_tables(card)
                    if not tables:
                        st.warning("Scorecard format not recognised. Raw data:")
                        st.json(card, expanded=False)
                    for title, bat, bowl in tables:
                        st.markdown(f"**{title}**")
                        if bat is not None:
                            st.dataframe(bat, width="stretch", hide_index=True)
                        if bowl is not None:
                            st.dataframe(bowl, width="stretch", hide_index=True)

with tab_table:
    st.dataframe(view.drop(columns=["match_id"]), width="stretch", hide_index=True)
    st.download_button("⬇ Download CSV", view.to_csv(index=False),
                       f"{kind.lower()}_matches.csv", "text/csv", key="lm_dl")

st.divider()
if st.button("💾 Save these matches to the database", key="lm_sync"):
    ok, message = live.sync_to_db(data)
    (st.success if ok else st.error)(message)
