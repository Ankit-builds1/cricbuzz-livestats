"""Home / landing page."""
import plotly.graph_objects as go
import streamlit as st

from utils.db_connection import run_query
from utils.ui import BORDER, COLOR_A, COLOR_B, GREEN, MUTED, NAVY, section


@st.cache_data(ttl=600)
def counts():
    return run_query("""
        SELECT (SELECT COUNT(*) FROM matches) matches, (SELECT COUNT(*) FROM players) players,
               (SELECT COUNT(*) FROM teams) teams, (SELECT COUNT(*) FROM venues) venues,
               (SELECT COUNT(*) FROM batting_scores) + (SELECT COUNT(*) FROM bowling_figures) records,
               (SELECT MAX(match_date) FROM matches) latest""").iloc[0]


c = counts()
st.markdown(f"""
<div style="border-radius:20px;overflow:hidden;box-shadow:0 18px 40px rgba(15,23,42,.18);margin-bottom:20px;
            background:linear-gradient(115deg,{NAVY} 0%,#0F3B2E 55%,{GREEN} 100%);position:relative">
  <div style="position:absolute;right:-60px;top:-60px;width:320px;height:320px;border-radius:50%;
              border:40px solid rgba(255,255,255,.06)"></div>
  <div style="position:absolute;right:120px;bottom:-90px;width:220px;height:220px;border-radius:50%;
              border:28px solid rgba(228,87,46,.25)"></div>
  <div style="padding:38px 40px;position:relative">
    <span class="badge">Live Cricbuzz API</span><span class="badge">Cricsheet ball-by-ball</span>
    <span class="badge">SQL · ML · Optimisation</span>
    <h1 style="color:#fff;font-family:'Barlow Condensed';font-size:3.4rem;font-weight:800;margin:8px 0 0;
               text-transform:uppercase;line-height:1">Cricbuzz LiveStats</h1>
    <div style="color:#BBF7D0;font-family:'Barlow Condensed';font-size:1.5rem;font-weight:600;
                text-transform:uppercase;letter-spacing:.05em">Real-time cricket insights & SQL-based analytics</div>
    <p style="color:#CBD5E1;max-width:680px;margin-top:10px">Every international Test, ODI and T20I since 2001 —
       {c.matches:,} matches and {c.players:,} players — combined with live scores from the Cricbuzz API.</p>
  </div>
</div>""", unsafe_allow_html=True)

k = st.columns(6)
for col, (label, val) in zip(k, [("Matches", f"{c.matches:,}"), ("Players", f"{c.players:,}"),
                                 ("Teams", f"{c.teams:,}"), ("Venues", f"{c.venues:,}"),
                                 ("Performance records", f"{c.records:,}"), ("Latest match", c.latest)]):
    col.metric(label, val)

section("Explore the app")
PAGES = [
    ("⚡", "Live Matches", "Live, recent & upcoming matches with full scorecards.", "app_pages/live_matches.py", COLOR_B),
    ("⚔️", "Player Comparison", "Photos, skill radar, career race & 14 head-to-head charts.", "app_pages/player_comparison.py", COLOR_A),
    ("🏟️", "Venue Insights", "Par scores, chasing success and toss impact for every ground.", "app_pages/venue_insights.py", GREEN),
    ("🏆", "Fantasy XI", "The optimal fantasy team for any match-up and budget.", "app_pages/fantasy_xi.py", "#CA8A04"),
    ("🤖", "Win Predictor", "Machine-learning win probability for any fixture.", "app_pages/win_predictor.py", "#7C3AED"),
    ("📊", "Top Player Stats", "ICC rankings and all-time career leaderboards.", "app_pages/top_stats.py", COLOR_A),
    ("🔍", "SQL Analytics", "25 SQL questions — from SELECT to window functions.", "app_pages/sql_analytics.py", NAVY),
    ("🛠️", "CRUD Operations", "Create, read, update & delete player records.", "app_pages/crud.py", MUTED),
]
for row in (PAGES[:4], PAGES[4:]):
    cols = st.columns(4)
    for col, (icon, name, desc, path, color) in zip(cols, row):
        with col:
            st.markdown(f'<div class="card" style="min-height:150px;border-top:5px solid {color}">'
                        f'<div style="font-size:2rem">{icon}</div>'
                        f'<div style="font-family:Barlow Condensed;font-weight:800;font-size:1.35rem;'
                        f'text-transform:uppercase;color:{NAVY};margin-top:2px">{name}</div>'
                        f'<div style="color:{MUTED};font-size:.86rem;margin-top:2px">{desc}</div></div>',
                        unsafe_allow_html=True)
            st.page_link(path, label=f"Open {name} →")

left, right = st.columns([3, 2])
with left:
    section("Matches by year")
    yr = run_query("""SELECT SUBSTR(match_date,1,4) y, match_format f, COUNT(*) n FROM matches
                      GROUP BY 1, 2 ORDER BY 1""")
    fig = go.Figure()
    for f, col, name in (("TEST", NAVY, "Test"), ("ODI", COLOR_A, "ODI"), ("T20", COLOR_B, "T20I")):
        d = yr[yr.f == f]
        fig.add_bar(x=d.y, y=d.n, name=name, marker_color=col)
    fig.update_layout(barmode="stack", height=340, yaxis_title="Matches")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
with right:
    section("How it works")
    steps = [(COLOR_B, "Cricbuzz API", "live matches, scorecards, rankings, profiles"),
             (COLOR_A, "Cricsheet", "10,000+ historical matches, ball-by-ball"),
             (GREEN, "Python ETL → SQLite", "cleaned, linked by player ID, indexed"),
             (NAVY, "Analytics layer", "SQL · scikit-learn · SciPy optimisation · Plotly"),
             ("#7C3AED", "Streamlit", "9 interactive pages")]
    html = "".join(f'<div style="display:flex;gap:12px;align-items:center;margin-bottom:10px">'
                   f'<div style="width:12px;height:38px;border-radius:4px;background:{c_}"></div>'
                   f'<div><div style="font-weight:700;color:{NAVY}">{t}</div>'
                   f'<div style="color:{MUTED};font-size:.84rem">{d}</div></div></div>' for c_, t, d in steps)
    st.markdown(f'<div class="card">{html}</div>', unsafe_allow_html=True)

st.caption("Data: Cricbuzz Cricket API (RapidAPI) · Cricsheet (cricsheet.org) · Photos: Wikimedia Commons. "
           "100% real data, no synthetic records.")
