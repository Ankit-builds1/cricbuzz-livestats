"""CRUD Operations: create, read, update and delete players."""
import streamlit as st

from utils.db_connection import execute, run_query
from utils.ui import section, setup_page

setup_page('CRUD Operations', '🛠️',
           'Create, read, update and delete player records with validated forms.',
           badges=("Forms", "Parameterised SQL"))


ROLES = ["Batsman", "Bowler", "All-rounder", "Wicket-keeper", "WK-Batsman",
         "Batting Allrounder", "Bowling Allrounder"]

tab_c, tab_r, tab_u, tab_d = st.tabs(["➕ Create", "📖 Read", "✏️ Update", "🗑️ Delete"])

# ---------------- CREATE
with tab_c:
    with st.form("create", clear_on_submit=True):
        name = st.text_input("Full name *")
        c1, c2 = st.columns(2)
        country = c1.text_input("Country")
        role = c2.selectbox("Playing role", ROLES)
        bat = c1.text_input("Batting style", "Right Handed Bat")
        bowl = c2.text_input("Bowling style")
        if st.form_submit_button("Add player"):
            if not name.strip():
                st.error("Name is required.")
            else:
                new_id = int(run_query("SELECT COALESCE(MAX(player_id), 0) + 1 AS id "
                                       "FROM players WHERE player_id < 9000000").id[0])
                execute("INSERT INTO players (player_id, full_name, country, playing_role, "
                        "batting_style, bowling_style) VALUES (?,?,?,?,?,?)",
                        (new_id, name.strip(), country or None, role, bat or None, bowl or None))
                st.success(f"Added {name} (id {new_id})")

# ---------------- READ
with tab_r:
    search = st.text_input("Search by name or country")
    df = run_query("""SELECT * FROM players
                      WHERE full_name LIKE ? OR country LIKE ?
                      ORDER BY full_name LIMIT 200""", (f"%{search}%", f"%{search}%"))
    st.caption(f"Showing {len(df)} players (max 200)")
    st.dataframe(df, hide_index=True, width="stretch")


def pick_player(key):
    """Searchable player picker; returns the selected row or None."""
    term = st.text_input("Find player", key=f"{key}_search")
    if not term:
        return None
    df = run_query("SELECT * FROM players WHERE full_name LIKE ? ORDER BY full_name LIMIT 50",
                   (f"%{term}%",))
    if df.empty:
        st.warning("No player found.")
        return None
    label = st.selectbox("Select", [f"{r.full_name} (id {r.player_id})" for r in df.itertuples()],
                         key=f"{key}_pick")
    return df.iloc[[f"{r.full_name} (id {r.player_id})" for r in df.itertuples()].index(label)]


# ---------------- UPDATE
with tab_u:
    p = pick_player("upd")
    if p is not None:
        with st.form("update"):
            name = st.text_input("Full name", p.full_name)
            c1, c2 = st.columns(2)
            country = c1.text_input("Country", p.country or "")
            role = c2.selectbox("Playing role", ROLES,
                                index=ROLES.index(p.playing_role) if p.playing_role in ROLES else 0)
            bat = c1.text_input("Batting style", p.batting_style or "")
            bowl = c2.text_input("Bowling style", p.bowling_style or "")
            if st.form_submit_button("Save changes"):
                execute("""UPDATE players SET full_name=?, country=?, playing_role=?,
                           batting_style=?, bowling_style=? WHERE player_id=?""",
                        (name, country or None, role, bat or None, bowl or None, int(p.player_id)))
                st.success("Player updated.")

# ---------------- DELETE
with tab_d:
    p = pick_player("del")
    if p is not None:
        used = run_query("""SELECT (SELECT COUNT(*) FROM batting_scores WHERE player_id=?) +
                                   (SELECT COUNT(*) FROM bowling_figures WHERE player_id=?) AS n""",
                         (int(p.player_id), int(p.player_id))).n[0]
        if used:
            st.warning(f"{p.full_name} has {used} match records; they will be deleted too.")
        if st.checkbox(f"Yes, permanently delete {p.full_name}"):
            if st.button("Delete", type="primary"):
                for t in ("batting_scores", "bowling_figures", "player_career_stats", "players"):
                    execute(f"DELETE FROM {t} WHERE player_id=?", (int(p.player_id),))
                st.success("Player deleted.")
