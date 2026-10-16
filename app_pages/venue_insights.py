"""Venue Insights: how a ground plays - scores, chasing, toss, top performers."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.db_connection import run_query
from utils.ui import ACCENT, COLOR_A, COLOR_B, MUTED, section, setup_page

setup_page("Venue Insights", "🏟️",
           "How every international ground plays — par scores, chasing, toss and top performers.",
           badges=("650+ venues", "Innings totals incl. extras"))
CFG = {"displayModeBar": False}


@st.cache_data(ttl=3600)
def venue_list():
    return run_query("""
        SELECT v.venue_id, v.venue_name, v.city, v.country, v.capacity, COUNT(*) AS matches
        FROM venues v JOIN matches m USING (venue_id)
        JOIN innings_summary i USING (match_id)
        WHERE i.innings_no = 1
        GROUP BY v.venue_id HAVING matches >= 5 ORDER BY matches DESC""")


@st.cache_data(ttl=3600)
def venue_matches(vid, fmt):
    return run_query("""
        SELECT m.match_id, m.match_date, m.match_format, m.toss_winner_id, m.toss_decision,
               m.winner_id, m.victory_type,
               i1.team_id AS bat1, i1.runs AS r1, i1.wickets AS w1,
               i2.team_id AS bat2, i2.runs AS r2, i2.wickets AS w2,
               t1.team_name AS bat1_name, t2.team_name AS bat2_name
        FROM matches m
        JOIN innings_summary i1 ON i1.match_id = m.match_id AND i1.innings_no = 1
        LEFT JOIN innings_summary i2 ON i2.match_id = m.match_id AND i2.innings_no = 2
        JOIN teams t1 ON t1.team_id = i1.team_id
        LEFT JOIN teams t2 ON t2.team_id = i2.team_id
        WHERE m.venue_id = ? AND m.match_format = ?
        ORDER BY m.match_date""", (int(vid), fmt))


vl = venue_list()
vl["label"] = vl.venue_name + " · " + vl.country.fillna("—") + " (" + vl.matches.astype(str) + ")"
c1, c2, c3 = st.columns([3, 6, 2])
country = c1.selectbox("Country", ["All"] + sorted(vl.country.dropna().unique()),
                       index=1 + sorted(vl.country.dropna().unique()).index("India")
                       if "India" in vl.country.values else 0)
opts = vl if country == "All" else vl[vl.country == country]
v_label = c2.selectbox("Venue", opts.label)
V = opts[opts.label == v_label].iloc[0]
fmts = run_query("SELECT match_format, COUNT(*) n FROM matches WHERE venue_id=? GROUP BY 1 ORDER BY n DESC",
                 (int(V.venue_id),))
fmt_map = {"T20": "T20I", "ODI": "ODI", "TEST": "Test"}
fmt = c3.selectbox("Format", fmts.match_format, format_func=lambda f: fmt_map.get(f, f))

df = venue_matches(V.venue_id, fmt)
if df.empty:
    st.info("No completed innings recorded for this venue and format.")
    st.stop()
res = df[df.winner_id.notna()]
bat_first_win = (res.winner_id == res.bat1).mean() * 100 if len(res) else 0
toss_win = (res.winner_id == res.toss_winner_id).mean() * 100 if len(res) else 0
par = df.r1.median()

# ------------------------------------------------------------- KPIs
k = st.columns(6)
k[0].metric("Matches", len(df), f"{df.match_date.min()[:4]}–{df.match_date.max()[:4]}", delta_color="off")
k[1].metric("Par 1st-innings score", f"{par:.0f}")
k[2].metric("Avg 2nd innings", f"{df.r2.mean():.0f}" if df.r2.notna().any() else "—")
k[3].metric("Bat-first wins", f"{bat_first_win:.0f}%")
k[4].metric("Chasing wins", f"{100 - bat_first_win:.0f}%" if len(res) else "—")
k[5].metric("Capacity", f"{int(V.capacity):,}" if pd.notna(V.capacity) else "—")

verdict = ("🏏 **Batting-first ground** — setting a target wins more often." if bat_first_win >= 55 else
           "🎯 **Chasing ground** — teams prefer to bowl first." if bat_first_win <= 45 else
           "⚖️ **Balanced ground** — no strong advantage batting first or chasing.")
st.info(f"{verdict}  Toss winners went on to win **{toss_win:.0f}%** of matches here.")

c1, c2 = st.columns([3, 2])
with c1:
    section("First-innings scores over time")
    fig = go.Figure()
    fig.add_scatter(x=df.match_date, y=df.r1, mode="markers", name="1st innings",
                    marker=dict(color=COLOR_A, size=8, opacity=.7),
                    text=df.bat1_name, hovertemplate="%{text}: %{y}<br>%{x}<extra></extra>")
    if df.r2.notna().any():
        fig.add_scatter(x=df.match_date, y=df.r2, mode="markers", name="2nd innings",
                        marker=dict(color=COLOR_B, size=8, opacity=.6),
                        text=df.bat2_name, hovertemplate="%{text}: %{y}<br>%{x}<extra></extra>")
    trend = df.assign(y=df.match_date.str[:4]).groupby("y").r1.mean()
    fig.add_scatter(x=[f"{y}-07-01" for y in trend.index], y=trend.values, name="Yearly avg (1st)",
                    line=dict(color=ACCENT, width=3, shape="spline"), mode="lines")
    fig.add_hline(y=par, line_dash="dot", line_color=MUTED, annotation_text=f"par {par:.0f}")
    fig.update_layout(height=400, yaxis_title="Runs")
    st.plotly_chart(fig, width="stretch", config=CFG)
with c2:
    section("Toss decisions & outcomes")
    t = res.assign(decision=res.toss_decision.fillna("unknown"),
                   toss_won_match=res.winner_id == res.toss_winner_id)
    g = t.groupby("decision").agg(n=("match_id", "size"), won=("toss_won_match", "mean")).reset_index()
    fig = go.Figure(go.Pie(labels=g.decision.str.title() + " first", values=g.n, hole=.62,
                           marker=dict(colors=[COLOR_A, COLOR_B, MUTED]), sort=False,
                           customdata=(g.won * 100).round(0),
                           hovertemplate="%{label}: %{value} times<br>won %{customdata}%<extra></extra>"))
    fig.update_layout(height=400, annotations=[dict(text=f"{toss_win:.0f}%<br><span style='font-size:11px'>toss→win</span>",
                                                     showarrow=False, font=dict(size=22))])
    st.plotly_chart(fig, width="stretch", config=CFG)

c3, c4 = st.columns(2)
with c3:
    section("Distribution of 1st-innings totals")
    fig = go.Figure(go.Histogram(x=df.r1, nbinsx=14, marker_color=COLOR_A, opacity=.85))
    fig.add_vline(x=par, line_dash="dot", line_color=ACCENT, annotation_text="par")
    fig.update_layout(height=320, xaxis_title="Runs", yaxis_title="Matches", bargap=.06)
    st.plotly_chart(fig, width="stretch", config=CFG)
with c4:
    section("Win % by target band (chasing)")
    ch = res[res.r2.notna()].copy()
    if len(ch) >= 5:
        ch["band"] = pd.qcut(ch.r1, q=min(4, ch.r1.nunique()), duplicates="drop")
        g = ch.groupby("band", observed=True).apply(
            lambda d: (d.winner_id == d.bat2).mean() * 100, include_groups=False)
        fig = go.Figure(go.Bar(x=[f"{int(i.left)+1}–{int(i.right)}" for i in g.index], y=g.values.round(0),
                               marker_color=COLOR_B, text=g.values.round(0), textposition="outside"))
        fig.update_layout(height=320, xaxis_title="Target set (1st-innings score)",
                          yaxis_title="Chase success %", yaxis_range=[0, 110])
        st.plotly_chart(fig, width="stretch", config=CFG)
    else:
        st.caption("Not enough completed chases.")

ids = ",".join(str(int(x)) for x in df.match_id)
l, r = st.columns(2)
with l:
    section("Top run-scorers here")
    st.dataframe(run_query(f"""
        SELECT p.full_name AS player, COUNT(*) AS inns, SUM(b.runs) AS runs,
               ROUND(1.0*SUM(b.runs)/NULLIF(SUM(b.is_out),0),1) AS avg, MAX(b.runs) AS best,
               ROUND(100.0*SUM(b.runs)/NULLIF(SUM(b.balls),0),1) AS sr
        FROM batting_scores b JOIN players p USING (player_id)
        WHERE b.match_id IN ({ids}) GROUP BY b.player_id ORDER BY runs DESC LIMIT 10"""),
        hide_index=True, width="stretch")
with r:
    section("Top wicket-takers here")
    st.dataframe(run_query(f"""
        SELECT p.full_name AS player, COUNT(*) AS inns, SUM(w.wickets) AS wkts,
               ROUND(1.0*SUM(w.runs_given)/NULLIF(SUM(w.wickets),0),1) AS avg,
               ROUND(AVG(w.economy),2) AS econ, MAX(w.wickets) AS best_w
        FROM bowling_figures w JOIN players p USING (player_id)
        WHERE w.match_id IN ({ids}) GROUP BY w.player_id ORDER BY wkts DESC LIMIT 10"""),
        hide_index=True, width="stretch")

section("Records")
hi, lo = df.loc[df.r1.idxmax()], df.loc[df.r1.idxmin()]
best_chase = res[(res.winner_id == res.bat2) & res.r2.notna()].sort_values("r2", ascending=False).head(1)
x1, x2, x3 = st.columns(3)
x1.metric("Highest total", f"{hi.r1}/{hi.w1}", f"{hi.bat1_name} · {hi.match_date[:4]}", delta_color="off")
x2.metric("Lowest total", f"{lo.r1}/{lo.w1}", f"{lo.bat1_name} · {lo.match_date[:4]}", delta_color="off")
if len(best_chase):
    bc = best_chase.iloc[0]
    x3.metric("Highest successful chase", f"{bc.r2}/{bc.w2}", f"{bc.bat2_name} · {bc.match_date[:4]}",
              delta_color="off")
