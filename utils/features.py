"""Feature engineering for the match win predictor.

Every feature is computed only from matches BEFORE the match date,
so the model never sees the future (no data leakage).
"""
import pandas as pd

ALL_COLUMNS = ["is_test", "is_odi", "is_t20", "team1_home", "team2_home",
               "team1_won_toss", "toss_bat_first",
               "team1_form", "team2_form", "h2h_team1_rate", "form_diff"]
# h2h_team1_rate is shown in the UI but excluded from the model: on this
# dataset it got a counter-intuitive (negative) weight, i.e. it was noise.
FEATURES = [c for c in ALL_COLUMNS if c != "h2h_team1_rate"]


def load_history(run_query):
    """All completed matches with a winner, plus venue country and team countries."""
    return run_query("""
        SELECT m.match_id, m.match_date, m.match_format, m.team1_id, m.team2_id,
               m.toss_winner_id, m.toss_decision, m.winner_id,
               v.country AS venue_country, t1.country AS t1_country, t2.country AS t2_country
        FROM matches m
        LEFT JOIN venues v ON v.venue_id = m.venue_id
        JOIN teams t1 ON t1.team_id = m.team1_id
        JOIN teams t2 ON t2.team_id = m.team2_id
        WHERE m.winner_id IS NOT NULL AND m.toss_winner_id IS NOT NULL
        ORDER BY m.match_date""")


def team_form(hist, team_id, before, n=10):
    """Win rate of a team in its last `n` matches before a date (0.5 if unknown)."""
    past = hist[(hist.match_date < before) &
                ((hist.team1_id == team_id) | (hist.team2_id == team_id))].tail(n)
    return 0.5 if past.empty else (past.winner_id == team_id).mean()


def h2h_rate(hist, t1, t2, before):
    """Share of past meetings won by t1 (0.5 if they never met)."""
    past = hist[(hist.match_date < before) &
                (((hist.team1_id == t1) & (hist.team2_id == t2)) |
                 ((hist.team1_id == t2) & (hist.team2_id == t1)))]
    return 0.5 if past.empty else (past.winner_id == t1).mean()


def make_row(hist, date, fmt, t1, t2, t1_country, t2_country, venue_country,
             toss_winner, toss_decision):
    """Build one feature row (used for both training and live prediction)."""
    f1, f2 = team_form(hist, t1, date), team_form(hist, t2, date)
    return {
        "is_test": int(fmt == "TEST"), "is_odi": int(fmt == "ODI"), "is_t20": int(fmt == "T20"),
        "team1_home": int(venue_country == t1_country),
        "team2_home": int(venue_country == t2_country),
        "team1_won_toss": int(toss_winner == t1),
        "toss_bat_first": int(toss_decision == "bat"),
        "team1_form": f1, "team2_form": f2,
        "h2h_team1_rate": h2h_rate(hist, t1, t2, date),
        "form_diff": f1 - f2,
    }


def build_training_set(hist):
    """Feature matrix X and target y (1 = team1 won) for every historical match."""
    rows = [make_row(hist, r.match_date, r.match_format, r.team1_id, r.team2_id,
                     r.t1_country, r.t2_country, r.venue_country,
                     r.toss_winner_id, r.toss_decision) for r in hist.itertuples()]
    X = pd.DataFrame(rows, columns=ALL_COLUMNS)
    y = (hist.winner_id == hist.team1_id).astype(int).values
    return X, y


def mirror(X, y):
    """Symmetric augmentation: add every match again with Team A/B swapped and
    the label flipped, so the model cannot learn a bias toward the 'Team A' slot."""
    Xm = X.copy()
    Xm["team1_home"], Xm["team2_home"] = X["team2_home"], X["team1_home"]
    Xm["team1_form"], Xm["team2_form"] = X["team2_form"], X["team1_form"]
    Xm["team1_won_toss"] = 1 - X["team1_won_toss"]
    Xm["h2h_team1_rate"] = 1 - X["h2h_team1_rate"]
    Xm["form_diff"] = -X["form_diff"]
    both = pd.concat([X, Xm], ignore_index=True)
    return both[FEATURES], list(y) + [1 - v for v in y]
