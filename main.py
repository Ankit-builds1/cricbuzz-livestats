"""Cricbuzz LiveStats - app entry point and navigation.

Run with:  streamlit run main.py
"""
import streamlit as st

st.set_page_config(page_title="Cricbuzz LiveStats", page_icon="🏏", layout="wide",
                   initial_sidebar_state="expanded")

from utils.db_connection import init_db  # noqa: E402
from utils.ui import render_chrome       # noqa: E402

init_db()

P = "app_pages/"
nav = st.navigation({
    "": [st.Page(P + "home.py", title="Home", icon="🏠", default=True)],
    "Live": [st.Page(P + "live_matches.py", title="Live Matches", icon="⚡"),
             st.Page(P + "top_stats.py", title="Top Player Stats", icon="📊")],
    "Analytics": [st.Page(P + "player_comparison.py", title="Player Comparison", icon="⚔️"),
                  st.Page(P + "venue_insights.py", title="Venue Insights", icon="🏟️"),
                  st.Page(P + "win_predictor.py", title="Win Predictor", icon="🤖"),
                  st.Page(P + "sql_analytics.py", title="SQL Analytics", icon="🔍")],
    "Tools": [st.Page(P + "fantasy_xi.py", title="Fantasy XI", icon="🏆"),
              st.Page(P + "crud.py", title="CRUD Operations", icon="🛠️")],
})
render_chrome()
nav.run()
