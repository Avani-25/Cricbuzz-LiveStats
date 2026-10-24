"""CRUD page: create, read, update and delete players and their career stats."""
import streamlit as st

from models.validators import (BATTING_STYLES, BOWLING_STYLES, FORMATS, ROLES)
from services import crud_service as crud
from utils.runtime import DEMO_NOTICE, is_demo_mode

st.title("🛠 Player Management")
st.caption("Create, read, update and delete player records and career stats.")

if is_demo_mode():
    st.warning(DEMO_NOTICE)

NONE = "(none)"
INT_FIELDS = [   # (field, label, maximum, widget-key suffix)
    ("matches", "Matches", 1000, "m"), ("innings", "Innings", 2000, "i"),
    ("runs", "Runs", 50000, "r"), ("highest_score", "Highest score", 500, "h"),
    ("centuries", "Centuries", 200, "c"), ("fifties", "Fifties", 400, "f"),
    ("wickets", "Wickets", 2000, "w"), ("catches", "Catches", 1000, "ca"),
    ("stumpings", "Stumpings", 500, "st"),
]


def flash(result):
    """Remember a result message across the rerun that follows a change."""
    st.session_state["flash"] = (result.ok, result.message)


def show_flash():
    """Show the success or error message saved before the last rerun."""
    msg = st.session_state.pop("flash", None)
    if msg:
        (st.success if msg[0] else st.error)(msg[1])


def style_index(options, value):
    """Index of a style in a selectbox list that starts with a '(none)' option."""
    return options.index(value) + 1 if value in options else 0


def stats_inputs(prefix, row=None):
    """Career-stat widgets; `row` pre-fills them when editing."""
    row = row or {}

    def g(key, default=0):
        return row.get(key) if row.get(key) is not None else default

    cols = st.columns(3)
    s = {}
    for i, (field, label, high, suffix) in enumerate(INT_FIELDS):
        s[field] = cols[i % 3].number_input(
            label, 0, high, int(g(field)), key=f"{prefix}_{suffix}")
    d1, d2, d3, d4 = st.columns(4)
    st.caption("Averages: leave at 0 to store nothing.")
    for col, key, label, hi in [(d1, "batting_avg", "Batting avg", 200.0),
                                (d2, "strike_rate", "Strike rate", 400.0),
                                (d3, "bowling_avg", "Bowling avg", 500.0),
                                (d4, "economy_rate", "Economy", 36.0)]:
        v = col.number_input(label, 0.0, hi, float(g(key, 0.0)), step=0.1,
                             key=f"{prefix}_{key}")
        s[key] = v if v > 0 else None
    return s


def player_fields(prefix, row=None):
    """Draw the player profile inputs and return their values as a dict."""
    row = row or {}
    name = st.text_input("Full name", row.get("full_name", ""), key=f"{prefix}_name")
    country = st.text_input("Country", row.get("country") or "", key=f"{prefix}_country")
    role = st.selectbox("Playing role", ROLES,
                        index=ROLES.index(row["playing_role"]) if row.get("playing_role") in ROLES else 0,
                        key=f"{prefix}_role")
    bat = st.selectbox("Batting style", [NONE] + BATTING_STYLES,
                       index=style_index(BATTING_STYLES, row.get("batting_style")),
                       key=f"{prefix}_bat")
    bowl = st.selectbox("Bowling style", [NONE] + BOWLING_STYLES,
                        index=style_index(BOWLING_STYLES, row.get("bowling_style")),
                        key=f"{prefix}_bowl")
    return {"full_name": name, "country": country, "playing_role": role,
            "batting_style": None if bat == NONE else bat,
            "bowling_style": None if bowl == NONE else bowl}


def pick_player(label, key):
    """Selectbox of all players; returns the chosen player_id or None."""
    players = crud.list_players()
    if players.empty:
        st.info("No players yet. Add one in the Create tab.")
        return None
    labels = {int(r.player_id): f"{r.full_name} · {r.country} · #{r.player_id}"
              for r in players.itertuples()}
    return st.selectbox(label, list(labels), format_func=labels.get, key=key)


show_flash()
tab_create, tab_read, tab_update, tab_delete = st.tabs(
    ["➕ Create", "🔎 Read", "✏️ Update", "🗑 Delete"])

# ------------------------------------------------------------------ CREATE
with tab_create:
    with st.form("create_player", clear_on_submit=False):
        data = player_fields("new")
        add_stats = st.checkbox("Also add career stats", key="new_add_stats")
        fmt = st.selectbox("Format", FORMATS, key="new_fmt")
        with st.expander("Career stats (used only if the box above is ticked)"):
            stats = stats_inputs("new")
        submitted = st.form_submit_button("Save player")
    if submitted:
        result = crud.create_player(data, {"format": fmt, **stats} if add_stats else None)
        if result.ok:
            flash(result)
            st.rerun()
        else:
            for err in result.errors:
                st.error(err)

# -------------------------------------------------------------------- READ
with tab_read:
    c1, c2, c3 = st.columns(3)
    search = c1.text_input("Search by name", key="read_search")
    role = c2.selectbox("Role", ["All"] + ROLES, key="read_role")
    country = c3.selectbox("Country", ["All"] + crud.list_countries(), key="read_country")
    df = crud.list_players(search.strip() or None,
                           None if role == "All" else role,
                           None if country == "All" else country)
    st.caption(f"{len(df)} players")
    st.dataframe(df, width="stretch", hide_index=True)
    if not df.empty:
        st.download_button("⬇ Download CSV", df.to_csv(index=False),
                           "players.csv", "text/csv")
        pid = pick_player("Show career stats for", "read_pick")
        if pid:
            stats_df = crud.get_stats(pid)
            if stats_df.empty:
                st.info("No career stats stored for this player.")
            else:
                st.dataframe(stats_df.drop(columns=["player_id"]),
                             width="stretch", hide_index=True)

# ------------------------------------------------------------------ UPDATE
with tab_update:
    pid = pick_player("Player to edit", "upd_pick")
    if pid:
        player = crud.get_player(pid)
        st.subheader("Profile")
        with st.form(f"update_profile_{pid}"):
            data = player_fields(f"upd{pid}", player)
            if st.form_submit_button("Update profile"):
                result = crud.update_player(pid, data)
                if result.ok:
                    flash(result)
                    st.rerun()
                else:
                    for err in result.errors:
                        st.error(err)

        st.subheader("Career stats")
        fmt = st.selectbox("Format", FORMATS, key=f"upd_fmt_{pid}")
        existing = crud.get_stats(pid)
        row = existing[existing["format"] == fmt]
        row = row.iloc[0].to_dict() if not row.empty else None
        st.caption("Editing existing stats." if row
                   else "No stats yet for this format; saving will create them.")
        with st.form(f"update_stats_{pid}_{fmt}"):
            stats = stats_inputs(f"us{pid}{fmt}", row)
            if st.form_submit_button("Save stats"):
                result = crud.save_stats(pid, {"format": fmt, **stats})
                if result.ok:
                    flash(result)
                    st.rerun()
                else:
                    for err in result.errors:
                        st.error(err)

# ------------------------------------------------------------------ DELETE
with tab_delete:
    pid = pick_player("Player to delete", "del_pick")
    if pid:
        player = crud.get_player(pid)
        foot = crud.player_footprint(pid)
        st.warning(
            f"Deleting **{player['full_name']}** also removes {foot['career_stats']} "
            f"career-stat rows, {foot['batting_rows']} batting rows and "
            f"{foot['bowling_rows']} bowling rows. This cannot be undone.")
        confirm = st.checkbox("I understand and want to delete this player",
                              key=f"del_confirm_{pid}")
        if st.button("Delete player", type="primary", disabled=not confirm,
                     key=f"del_btn_{pid}"):
            result = crud.delete_player(pid)
            flash(result)
            st.rerun()
