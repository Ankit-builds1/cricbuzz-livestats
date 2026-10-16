# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Top Player Stats: ICC rankings (API) + career leaders (database)."""
import pandas as pd
import streamlit as st

from utils.api_client import fetch
from utils.db_connection import run_query
from utils.ui import section, setup_page

setup_page('Top Player Stats', '📊',
           'Official ICC rankings and all-time career leaderboards.',
           badges=("ICC rankings", "Career leaders"))


tab_rank, tab_career = st.tabs(["🏆 ICC Rankings (API)", "📈 Career Leaders (Database)"])

with tab_rank:
    c1, c2 = st.columns(2)
    cat = c1.selectbox("Category", ["batsmen", "bowlers", "allrounders"])
    fmt = c2.selectbox("Format", ["odi", "test", "t20"])
    data = fetch(f"stats/v1/rankings/{cat}?formatType={fmt}", max_age=86400 * 7)
    rows = (data or {}).get("rank", [])[:20]
    if rows:
        df = pd.DataFrame(rows)[["rank", "name", "country", "rating"]]
        df["rating"] = pd.to_numeric(df["rating"])
        l, r = st.columns([2, 3])
        l.dataframe(df, hide_index=True, width="stretch")
        r.bar_chart(df.head(10).set_index("name")["rating"], horizontal=True)
    else:
        st.warning("Rankings unavailable (API quota exhausted and nothing cached).")

with tab_career:
    fmt2 = st.selectbox("Format ", ["ODI", "Test", "T20I"])
    stat = st.radio("Leaderboard", ["Most runs", "Highest score", "Most wickets",
                                    "Best batting average", "Most centuries"], horizontal=True)
    col = {"Most runs": "runs", "Highest score": "highest_score", "Most wickets": "wickets",
           "Best batting average": "batting_average", "Most centuries": "hundreds"}[stat]
    df = run_query(f"""
        SELECT p.full_name AS player, p.country, s.matches, s.{col} AS value
        FROM player_career_stats s JOIN players p USING (player_id)
        WHERE s.format = ? AND s.{col} IS NOT NULL
          {"AND s.innings >= 10" if col == "batting_average" else ""}
        ORDER BY s.{col} DESC LIMIT 10""", (fmt2,))
    l, r = st.columns([2, 3])
    l.dataframe(df.rename(columns={"value": stat}), hide_index=True, width="stretch")
    if not df.empty:
        r.bar_chart(df.set_index("player")["value"], horizontal=True)
