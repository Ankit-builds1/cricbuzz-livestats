# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Live Matches page: current matches + scorecards from the Cricbuzz API."""
import pandas as pd
import streamlit as st

from data_loader import iter_matches
from utils.api_client import fetch, quota_paused
from utils.ui import section, setup_page

setup_page('Live Matches', '⚡',
           'Live, recent and upcoming international matches with full scorecards.',
           badges=("Cricbuzz API", "Auto-cached"))


col_a, col_b = st.columns([3, 1])
feed = col_a.radio("Feed", ["Live", "Recent", "Upcoming"], horizontal=True)
if col_b.button("🔄 Refresh"):
    st.cache_data.clear()


@st.cache_data(ttl=120)
def get_feed(name):
    """Fetch a match feed (cached 2 min in Streamlit, 5 min on disk)."""
    return fetch(f"matches/v1/{name.lower()}")


@st.cache_data(ttl=300)
def get_scorecard(match_id):
    return fetch(f"mcenter/v1/{match_id}/hscard", max_age=300)


matches = list(iter_matches(get_feed(feed)))
if quota_paused():
    st.caption("🟡 Showing the most recently cached data — the free Cricbuzz API quota is used up "
               "for this month and refreshes automatically when it resets.")
if not matches:
    st.warning("No matches available right now (or the API quota is exhausted and no cache exists).")
    st.stop()

labels = {f"{m['team1']['teamSName']} vs {m['team2']['teamSName']} — "
          f"{m.get('matchDesc', '')} ({m.get('matchFormat', '')})": m for m in matches}
choice = st.selectbox(f"{len(matches)} matches found", list(labels))
m = labels[choice]
v = m.get("venueInfo", {})

st.subheader(f"{m['team1']['teamName']} vs {m['team2']['teamName']}")
c1, c2, c3 = st.columns(3)
c1.markdown(f"**Series:** {m.get('seriesName')}")
c2.markdown(f"**Venue:** {v.get('ground')}, {v.get('city')}")
c3.markdown(f"**State:** {m.get('state')}")
st.info(m.get("status", ""))

if m.get("state") == "Upcoming" or m.get("state") == "Preview":
    st.stop()

card = get_scorecard(m["matchId"])
if not card or not card.get("scorecard"):
    st.caption("Scorecard not available for this match.")
    st.stop()

for inn in card["scorecard"]:
    st.markdown(f"### {inn.get('batteamname')} — {inn.get('score')}/{inn.get('wickets')} "
                f"({inn.get('overs')} ov)")
    bat = pd.DataFrame([{
        "Batter": b["name"], "Dismissal": b.get("outdec", ""), "R": b.get("runs", 0),
        "B": b.get("balls", 0), "4s": b.get("fours", 0), "6s": b.get("sixes", 0),
        "SR": b.get("strkrate")} for b in inn.get("batsman", []) if b.get("balls") or b.get("outdec")])
    bowl = pd.DataFrame([{
        "Bowler": w["name"], "O": w.get("overs"), "M": w.get("maidens"), "R": w.get("runs"),
        "W": w.get("wickets"), "Econ": w.get("economy")} for w in inn.get("bowler", [])])
    l, r = st.columns([3, 2])
    l.dataframe(bat, hide_index=True, width="stretch")
    r.dataframe(bowl, hide_index=True, width="stretch")
