"""SQL Analytics: run the 25 practice queries or a custom SELECT."""
import streamlit as st

from sql.queries import QUERIES
from utils.db_connection import run_query
from utils.ui import section, setup_page

setup_page('SQL Analytics', '🔍',
           '25 analytical SQL questions — from basic SELECTs to CTEs and window functions.',
           badges=("SQLite", "25 queries", "Read-only sandbox"))


level = st.radio("Level", ["Beginner", "Intermediate", "Advanced"], horizontal=True)
options = [q for q in QUERIES if q[0] == level]
question = st.selectbox("Question", [q[1] for q in options])
sql = next(q[2] for q in options if q[1] == question)

with st.expander("Show SQL", expanded=False):
    st.code(sql, language="sql")

try:
    df = run_query(sql)
    st.caption(f"{len(df)} rows")
    st.dataframe(df, hide_index=True, width="stretch")
except RuntimeError as e:
    st.error(str(e))

st.divider()
section("✍️ Custom SQL query")
st.caption("Read-only: only SELECT / WITH statements are allowed. "
           "Tables: teams, venues, players, series, matches, batting_scores, "
           "bowling_figures, player_career_stats")
custom = st.text_area("SQL", "SELECT * FROM players LIMIT 10;", height=120)
if st.button("Run query"):
    first = custom.strip().split(None, 1)[0].upper() if custom.strip() else ""
    if first not in ("SELECT", "WITH") or ";" in custom.strip().rstrip(";"):
        st.error("Only a single SELECT/WITH query is allowed here. Use the CRUD page to modify data.")
    else:
        try:
            st.dataframe(run_query(custom), hide_index=True, width="stretch")
        except RuntimeError as e:
            st.error(str(e))
