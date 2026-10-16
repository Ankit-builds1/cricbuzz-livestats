"""Win Predictor: ML model estimates each team's chance of winning."""
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from utils.db_connection import run_query
from utils.features import load_history, make_row
from utils.ui import section, setup_page

setup_page('Win Predictor', '🤖',
           'Machine-learning win probability from form, home advantage, toss and format.',
           badges=("scikit-learn", "No data leakage"))


MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "win_model.pkl"
@st.cache_resource(show_spinner="Loading model…")
def load_model():
    """Load the saved model; if missing or incompatible (e.g. different
    scikit-learn version on the server), retrain it from the database."""
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        from train_model import train
        return train(verbose=False)


@st.cache_data(ttl=600)
def get_history():
    return load_history(run_query)


bundle, hist = load_model(), get_history()
teams = run_query("SELECT team_id, team_name, country FROM teams "
                  "WHERE country IS NOT NULL ORDER BY team_name")
venues = run_query("SELECT venue_id, venue_name, country FROM venues "
                   "WHERE country IS NOT NULL ORDER BY venue_name")

c1, c2 = st.columns(2)
t1_name = c1.selectbox("Team A", teams.team_name, index=0)
t2_name = c2.selectbox("Team B", teams.team_name[teams.team_name != t1_name])
t1 = teams[teams.team_name == t1_name].iloc[0]
t2 = teams[teams.team_name == t2_name].iloc[0]

c3, c4, c5, c6 = st.columns(4)
fmt = c3.selectbox("Format", ["ODI", "T20", "TEST"])
venue_name = c4.selectbox("Venue", venues.venue_name)
venue_country = venues[venues.venue_name == venue_name].country.iloc[0]
toss_name = c5.selectbox("Toss won by", [t1_name, t2_name])
decision = c6.selectbox("Toss decision", ["bat", "bowl"])

if st.button("🔮 Predict winner", type="primary"):
    row = make_row(hist, date.today().isoformat(), fmt, int(t1.team_id), int(t2.team_id),
                   t1.country, t2.country, venue_country,
                   int(t1.team_id) if toss_name == t1_name else int(t2.team_id), decision)
    X = pd.DataFrame([row], columns=bundle["features"])
    p1 = float(bundle["model"].predict_proba(X)[0, 1])

    st.divider()
    a, b = st.columns(2)
    a.metric(t1_name, f"{p1:.0%}")
    b.metric(t2_name, f"{1 - p1:.0%}")
    st.progress(p1, text=f"{t1_name} {p1:.0%}  ·  {t2_name} {1 - p1:.0%}")
    favourite = t1_name if p1 >= 0.5 else t2_name
    st.success(f"**Predicted favourite: {favourite}**")

    section("Why? Key inputs")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"{t1.team_name} form (last 10)", f"{row['team1_form']:.0%}")
    k2.metric(f"{t2.team_name} form (last 10)", f"{row['team2_form']:.0%}")
    k3.metric(f"H2H wins for {t1.team_name}", f"{row['h2h_team1_rate']:.0%}")
    k4.metric("Home team", t1_name if row["team1_home"] else t2_name if row["team2_home"] else "Neutral")

with st.expander("ℹ️ About the model"):
    st.markdown(f"""
- **Algorithm:** {bundle['name']} (best of Logistic Regression vs Gradient Boosting by ROC-AUC)
- **Trained on:** {bundle['n_matches']} matches · time-based split (train on older 80%, test on newest 20%)
- **Test metrics:** {bundle['metrics']}
- **No leakage:** every feature uses only matches *before* the match date.
- Cricket is high-variance; even professional models reach only ~60–65% accuracy.
""")
