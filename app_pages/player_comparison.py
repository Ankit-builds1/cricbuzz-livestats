# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Player Comparison: a professional head-to-head analytics dashboard."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils.db_connection import run_query
from utils.photos import get_photo, initials
from utils.ui import ACCENT, BORDER, COLOR_A, COLOR_B, MUTED, section, setup_page

setup_page("Player Comparison", "⚔️",
           "Head-to-head career analytics from 184,000+ real international innings.",
           badges=("Tests · ODIs · T20Is", "2001 → today", "Cricsheet + Cricbuzz"))
FMT_SQL = {"All formats": ("TEST", "ODI", "T20"), "Test": ("TEST",), "ODI": ("ODI",), "T20I": ("T20",)}
PLOT_CFG = {"displayModeBar": False}


# ------------------------------------------------------------------ data
@st.cache_data(ttl=3600)
def player_list():
    df = run_query("""
        SELECT p.player_id, p.full_name, p.country, p.playing_role, p.gender,
               COUNT(DISTINCT b.match_id) AS matches
        FROM players p JOIN batting_scores b USING (player_id)
        GROUP BY p.player_id HAVING matches >= 10
        ORDER BY matches DESC""")
    df["label"] = (df.full_name + " · " + df.country.fillna("—")
                   + np.where(df.gender == "female", " (W)", ""))
    return df


@st.cache_data(ttl=3600)
def batting(pid):
    return run_query("""
        SELECT b.match_id, m.match_date, m.match_format AS fmt, b.innings_no, b.batting_position AS pos,
               b.runs, b.balls, b.fours, b.sixes, b.is_out, b.team_id,
               CASE WHEN m.team1_id = b.team_id THEN t2.team_name ELSE t1.team_name END AS opponent,
               v.country AS venue_country, bt.country AS team_country,
               CASE WHEN m.winner_id = b.team_id THEN 1 ELSE 0 END AS won
        FROM batting_scores b
        JOIN matches m USING (match_id)
        JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
        LEFT JOIN teams bt ON bt.team_id = b.team_id
        LEFT JOIN venues v ON v.venue_id = m.venue_id
        WHERE b.player_id = ? ORDER BY m.match_date, b.innings_no""", (int(pid),))


@st.cache_data(ttl=3600)
def bowling(pid):
    return run_query("""
        SELECT w.match_id, m.match_date, m.match_format AS fmt, w.overs, w.maidens,
               w.runs_given, w.wickets
        FROM bowling_figures w JOIN matches m USING (match_id)
        WHERE w.player_id = ? ORDER BY m.match_date""", (int(pid),))


@st.cache_data(ttl=3600)
def population(fmts, gender):
    """Per-player batting/bowling rates for percentile ranking (20+ innings)."""
    ph = ",".join("?" * len(fmts))
    bat = run_query(f"""
        SELECT b.player_id, COUNT(*) inns, 1.0*SUM(runs)/NULLIF(SUM(is_out),0) avg,
               100.0*SUM(runs)/NULLIF(SUM(balls),0) sr,
               100.0*SUM(runs>=50)/COUNT(*) fifty_rate,
               100.0*(SUM(fours)*4+SUM(sixes)*6)/NULLIF(SUM(runs),0) boundary_pct
        FROM batting_scores b JOIN matches m USING(match_id) JOIN players p USING(player_id)
        WHERE m.match_format IN ({ph}) AND COALESCE(p.gender,'male') = ?
        GROUP BY b.player_id HAVING inns >= 20""", (*fmts, gender))
    bowl = run_query(f"""
        SELECT w.player_id, COUNT(*) b_inns, 1.0*SUM(wickets)/COUNT(*) wpi,
               6.0*SUM(runs_given)/NULLIF(SUM(CAST(overs AS INT)*6 + ROUND((overs-CAST(overs AS INT))*10)),0) econ
        FROM bowling_figures w JOIN matches m USING(match_id) JOIN players p USING(player_id)
        WHERE m.match_format IN ({ph}) AND COALESCE(p.gender,'male') = ?
        GROUP BY w.player_id HAVING b_inns >= 20""", (*fmts, gender))
    return bat, bowl


def balls_of(overs):
    o = overs.fillna(0)
    return (o.astype(int) * 6 + ((o - o.astype(int)) * 10).round()).astype(int)


def summarize(bat, bowl):
    outs = bat.is_out.sum()
    balls = balls_of(bowl.overs).sum() if len(bowl) else 0
    best = bowl.sort_values(["wickets", "runs_given"], ascending=[False, True]).head(1)
    return {
        "Matches": bat.match_id.nunique(), "Innings": len(bat), "Runs": int(bat.runs.sum()),
        "Average": round(bat.runs.sum() / outs, 2) if outs else None,
        "Strike rate": round(100 * bat.runs.sum() / bat.balls.sum(), 2) if bat.balls.sum() else None,
        "Highest": int(bat.runs.max()) if len(bat) else 0,
        "100s": int((bat.runs >= 100).sum()), "50s": int(((bat.runs >= 50) & (bat.runs < 100)).sum()),
        "Ducks": int(((bat.runs == 0) & (bat.is_out == 1)).sum()),
        "4s": int(bat.fours.sum()), "6s": int(bat.sixes.sum()),
        "Wickets": int(bowl.wickets.sum()) if len(bowl) else 0,
        "Bowl avg": round(bowl.runs_given.sum() / bowl.wickets.sum(), 2) if len(bowl) and bowl.wickets.sum() else None,
        "Economy": round(6 * bowl.runs_given.sum() / balls, 2) if balls else None,
        "5W hauls": int((bowl.wickets >= 5).sum()) if len(bowl) else 0,
        "Best": f"{int(best.wickets.iloc[0])}/{int(best.runs_given.iloc[0])}" if len(best) else "—",
        "Win % (batted)": round(100 * bat.groupby("match_id").won.max().mean(), 1) if len(bat) else None,
    }


# ------------------------------------------------------------- controls
players = player_list()
labels = players.label.tolist()
idx = lambda name, fallback: next((i for i, l in enumerate(labels) if l.startswith(name)), fallback)
c1, c2, c3 = st.columns([5, 5, 3])
a_label = c1.selectbox("Player A", labels, index=idx("Virat Kohli", 0))
b_label = c2.selectbox("Player B", labels, index=idx("Joe Root", 1))
fmt_name = c3.selectbox("Format", list(FMT_SQL))
fmts = FMT_SQL[fmt_name]

A = players[players.label == a_label].iloc[0]
B = players[players.label == b_label].iloc[0]
if A.player_id == B.player_id:
    st.warning("Pick two different players.")
    st.stop()

ba, bb = batting(A.player_id), batting(B.player_id)
wa, wb = bowling(A.player_id), bowling(B.player_id)
ba, bb = ba[ba.fmt.isin(fmts)], bb[bb.fmt.isin(fmts)]
wa, wb = wa[wa.fmt.isin(fmts)], wb[wb.fmt.isin(fmts)]
if ba.empty or bb.empty:
    st.info(f"One of the players has no {fmt_name} innings. Try another format.")
    st.stop()
sa, sb = summarize(ba, wa), summarize(bb, wb)


# ------------------------------------------------------------ hero cards
@st.cache_data(ttl=86400 * 7, show_spinner=False)
def photo(name):
    return get_photo(name)


def player_card(p, s, color, bat):
    span = f"{bat.match_date.min()[:4]}–{bat.match_date.max()[:4]}"
    ph = photo(p.full_name)
    if ph and ph.get("img"):
        avatar = (f'<img src="{ph["img"]}" style="width:96px;height:96px;border-radius:50%;'
                  f'object-fit:cover;object-position:top;border:3px solid {color};flex-shrink:0">')
    else:
        avatar = (f'<div style="width:96px;height:96px;border-radius:50%;display:flex;align-items:center;'
                  f'justify-content:center;font-size:2rem;font-weight:800;background:{color}22;'
                  f'color:{color};border:3px solid {color};flex-shrink:0">{initials(p.full_name)}</div>')
    bio = (f'<div class="meta" style="font-style:italic">{ph["desc"]} · '
           f'<a href="{ph["url"]}" target="_blank" style="color:{color}">Wikipedia ↗</a></div>'
           if ph and ph.get("desc") else "")
    cells = [("Matches", s["Matches"]), ("Runs", f'{s["Runs"]:,}'),
             ("Average", s["Average"] or "—"), ("Wickets", s["Wickets"])]
    grid = "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cells)
    return f"""<div class="pcard"><div class="stripe" style="background:{color}"></div>
      <div style="display:flex;gap:18px;align-items:center">{avatar}<div>
      <p class="name" style="color:{color}">{p.full_name}</p>
      <div class="meta">{p.country or '—'} · {p.playing_role or '—'} · {span}
        {' · Women' if p.gender == 'female' else ''}</div>{bio}</div></div>
      <div class="grid">{grid}</div></div>"""


l, m, r = st.columns([10, 1, 10])
l.markdown(player_card(A, sa, COLOR_A, ba), unsafe_allow_html=True)
m.markdown('<div class="vs"><span>VS</span></div>', unsafe_allow_html=True)
r.markdown(player_card(B, sb, COLOR_B, bb), unsafe_allow_html=True)

tab_over, tab_bat, tab_bowl, tab_ctx = st.tabs(
    ["📋 Overview", "🏏 Batting deep-dive", "🎯 Bowling", "🌍 Context & opposition"])

# --------------------------------------------------------------- overview
with tab_over:
    left, right = st.columns([6, 5])
    with left:
        section("Skill radar — percentile vs peers")
        gender = A.gender if A.gender == B.gender and A.gender else "male"
        pop_bat, pop_bowl = population(fmts, gender)

        def pct(series, value, lower_better=False):
            s = series.dropna()
            if value is None or pd.isna(value) or s.empty:
                return 0
            p = 100 * (s < value).mean()
            return round(100 - p if lower_better else p, 1)

        def profile(s, bat, bowl):
            bpct = 100 * (bat.fours.sum() * 4 + bat.sixes.sum() * 6) / max(bat.runs.sum(), 1)
            return [pct(pop_bat.avg, s["Average"]), pct(pop_bat.sr, s["Strike rate"]),
                    pct(pop_bat.fifty_rate, 100 * (s["50s"] + s["100s"]) / max(s["Innings"], 1)),
                    pct(pop_bat.boundary_pct, bpct),
                    pct(pop_bowl.wpi, s["Wickets"] / max(len(bowl), 1)) if len(bowl) else 0,
                    pct(pop_bowl.econ, s["Economy"], lower_better=True) if s["Economy"] else 0]

        axes = ["Average", "Strike rate", "50+ conversion", "Boundary %", "Wickets / inn", "Economy"]
        fig = go.Figure()
        for p, s, bat, bowl, col in ((A, sa, ba, wa, COLOR_A), (B, sb, bb, wb, COLOR_B)):
            v = profile(s, bat, bowl)
            fig.add_trace(go.Scatterpolar(r=v + v[:1], theta=axes + axes[:1], fill="toself",
                                          name=p.full_name, line=dict(color=col, width=2.5),
                                          opacity=0.75,
                                          hovertemplate="%{theta}: %{r:.0f}th percentile<extra></extra>"))
        fig.update_layout(height=430, polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor=BORDER, tickfont=dict(color=MUTED, size=10)),
            angularaxis=dict(gridcolor=BORDER)))
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
        st.caption(f"Percentile among {'women' if gender == 'female' else 'men'} with 20+ "
                   f"{fmt_name} innings · 100 = best in the world.")

    with right:
        section("Head-to-head numbers")
        better_low = {"Ducks", "Economy", "Bowl avg"}
        rows = ["Matches", "Runs", "Average", "Strike rate", "Highest", "100s", "50s",
                "Ducks", "4s", "6s", "Wickets", "Economy", "5W hauls", "Best", "Win % (batted)"]
        html = ""
        for k in rows:
            va, vb = sa[k], sb[k]
            ca = cb = "tie"
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and va != vb:
                a_wins = (va < vb) if k in better_low else (va > vb)
                ca, cb = ("win-a", "") if a_wins else ("", "win-b")
            fa = f"{va:,}" if isinstance(va, int) else (va if va is not None else "—")
            fb = f"{vb:,}" if isinstance(vb, int) else (vb if vb is not None else "—")
            html += f'<div class="cmp"><div class="l {ca}">{fa}</div><div class="m">{k}</div><div class="r {cb}">{fb}</div></div>'
        st.markdown(html, unsafe_allow_html=True)

    section("Career race — cumulative runs by innings")
    fig = go.Figure()
    for p, bat, col in ((A, ba, COLOR_A), (B, bb, COLOR_B)):
        fig.add_trace(go.Scatter(x=np.arange(1, len(bat) + 1), y=bat.runs.cumsum(), name=p.full_name,
                                 line=dict(color=col, width=3), fill="tozeroy",
                                 fillcolor=col.replace("#", "rgba(") if False else None,
                                 hovertemplate="Innings %{x}<br>%{y:,} runs<extra>" + p.full_name + "</extra>"))
    fig.update_layout(height=360, xaxis_title="Innings number", yaxis_title="Career runs")
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

# ----------------------------------------------------------- batting tab
with tab_bat:
    section("Runs per calendar year")
    yr = pd.concat([ba.assign(player=A.full_name), bb.assign(player=B.full_name)])
    yr["year"] = yr.match_date.str[:4]
    agg = yr.groupby(["year", "player"]).agg(runs=("runs", "sum"), outs=("is_out", "sum"),
                                              inns=("runs", "size")).reset_index()
    agg["avg"] = (agg.runs / agg.outs.replace(0, np.nan)).round(1)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for p, col in ((A.full_name, COLOR_A), (B.full_name, COLOR_B)):
        d = agg[agg.player == p]
        fig.add_bar(x=d.year, y=d.runs, name=f"{p} runs", marker_color=col, opacity=0.85,
                    hovertemplate="%{x}: %{y:,} runs<extra></extra>")
        fig.add_scatter(x=d.year, y=d.avg, name=f"{p} avg", mode="lines+markers",
                        line=dict(color=col, dash="dot", width=2), secondary_y=True,
                        hovertemplate="%{x}: avg %{y}<extra></extra>")
    fig.update_layout(height=400, barmode="group")
    fig.update_yaxes(title_text="Runs", secondary_y=False)
    fig.update_yaxes(title_text="Average", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    c1, c2 = st.columns(2)
    with c1:
        section("Form curve — rolling 10-innings average")
        fig = go.Figure()
        for p, bat, col in ((A, ba, COLOR_A), (B, bb, COLOR_B)):
            fig.add_scatter(x=pd.to_datetime(bat.match_date), y=bat.runs.rolling(10, min_periods=3).mean(),
                            name=p.full_name, line=dict(color=col, width=2.5, shape="spline"))
        fig.update_layout(height=360, yaxis_title="Runs (rolling avg)")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with c2:
        section("Score distribution")
        bins, names = [-1, 9, 29, 49, 99, 10000], ["0–9", "10–29", "30–49", "50–99", "100+"]
        fig = go.Figure()
        for p, bat, col in ((A, ba, COLOR_A), (B, bb, COLOR_B)):
            dist = pd.cut(bat.runs, bins, labels=names).value_counts(normalize=True).reindex(names) * 100
            fig.add_bar(x=names, y=dist.round(1), name=p.full_name, marker_color=col,
                        hovertemplate="%{x}: %{y:.1f}% of innings<extra></extra>")
        fig.update_layout(height=360, barmode="group", yaxis_title="% of innings")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    c3, c4 = st.columns(2)
    with c3:
        section("Run sources")
        fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}] * 2],
                            subplot_titles=[A.full_name, B.full_name])
        for i, (bat, col) in enumerate(((ba, COLOR_A), (bb, COLOR_B)), start=1):
            fours, sixes = bat.fours.sum() * 4, bat.sixes.sum() * 6
            other = max(bat.runs.sum() - fours - sixes, 0)
            fig.add_pie(labels=["Running", "Fours", "Sixes"], values=[other, fours, sixes], hole=.6,
                        marker=dict(colors=["#334155", col, ACCENT]), row=1, col=i, sort=False,
                        textinfo="percent")
        fig.update_layout(height=340, showlegend=True)
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with c4:
        section("Batting position")
        fig = go.Figure()
        for p, bat, col in ((A, ba, COLOR_A), (B, bb, COLOR_B)):
            pos = bat.pos.clip(upper=8).value_counts().sort_index()
            fig.add_bar(x=[f"#{int(i)}" if i < 8 else "#8+" for i in pos.index], y=pos.values,
                        name=p.full_name, marker_color=col)
        fig.update_layout(height=340, barmode="group", yaxis_title="Innings")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    section("Every innings — runs vs balls faced")
    fig = go.Figure()
    for p, bat, col in ((A, ba, COLOR_A), (B, bb, COLOR_B)):
        fig.add_scatter(x=bat.balls, y=bat.runs, mode="markers", name=p.full_name,
                        marker=dict(color=col, size=7, opacity=.55, line=dict(width=0)),
                        text=bat.opponent + " · " + bat.match_date,
                        hovertemplate="%{y} (%{x} balls)<br>%{text}<extra></extra>")
    mx = max(ba.balls.max(), bb.balls.max())
    for sr, dash in ((100, "dash"), (150, "dot")):
        fig.add_scatter(x=[0, mx], y=[0, mx * sr / 100], mode="lines", name=f"SR {sr}",
                        line=dict(color=MUTED, dash=dash, width=1), hoverinfo="skip")
    fig.update_layout(height=420, xaxis_title="Balls faced", yaxis_title="Runs")
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

# ----------------------------------------------------------- bowling tab
with tab_bowl:
    if wa.empty and wb.empty:
        st.info("Neither player has bowled in this format.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"{A.full_name} wickets", sa["Wickets"], delta=sa["Wickets"] - sb["Wickets"])
        k2.metric(f"{B.full_name} wickets", sb["Wickets"], delta=sb["Wickets"] - sa["Wickets"])
        k3.metric(f"{A.full_name} economy", sa["Economy"] or "—")
        k4.metric(f"{B.full_name} economy", sb["Economy"] or "—")
        c1, c2 = st.columns(2)
        with c1:
            section("Wickets per year")
            fig = go.Figure()
            for p, w, col in ((A, wa, COLOR_A), (B, wb, COLOR_B)):
                if len(w):
                    g = w.groupby(w.match_date.str[:4]).wickets.sum()
                    fig.add_bar(x=g.index, y=g.values, name=p.full_name, marker_color=col)
            fig.update_layout(height=360, barmode="group")
            st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
        with c2:
            section("Economy rate per year")
            fig = go.Figure()
            for p, w, col in ((A, wa, COLOR_A), (B, wb, COLOR_B)):
                if len(w):
                    w = w.assign(balls=balls_of(w.overs))
                    g = w.groupby(w.match_date.str[:4]).agg(r=("runs_given", "sum"), b=("balls", "sum"))
                    g = g[g.b >= 60]
                    fig.add_scatter(x=g.index, y=(6 * g.r / g.b).round(2), name=p.full_name,
                                    mode="lines+markers", line=dict(color=col, width=2.5))
            fig.update_layout(height=360, yaxis_title="Runs per over")
            st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
        section("Wickets in an innings — how often")
        fig = go.Figure()
        for p, w, col in ((A, wa, COLOR_A), (B, wb, COLOR_B)):
            if len(w):
                d = w.wickets.clip(upper=5).value_counts().reindex(range(6), fill_value=0)
                fig.add_bar(x=["0", "1", "2", "3", "4", "5+"], y=d.values, name=p.full_name, marker_color=col)
        fig.update_layout(height=320, barmode="group", xaxis_title="Wickets in innings",
                          yaxis_title="Innings")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

# ----------------------------------------------------------- context tab
with tab_ctx:
    c1, c2 = st.columns([3, 2])
    with c1:
        section("Batting average vs top opponents")
        opp = pd.concat([ba.assign(player=A.full_name), bb.assign(player=B.full_name)])
        top = opp.opponent.value_counts().head(8).index
        g = (opp[opp.opponent.isin(top)].groupby(["opponent", "player"])
             .apply(lambda d: d.runs.sum() / max(d.is_out.sum(), 1), include_groups=False)
             .round(1).reset_index(name="avg"))
        fig = go.Figure()
        for p, col in ((A.full_name, COLOR_A), (B.full_name, COLOR_B)):
            d = g[g.player == p]
            fig.add_bar(y=d.opponent, x=d.avg, name=p, orientation="h", marker_color=col)
        fig.update_layout(height=420, barmode="group", xaxis_title="Average",
                          yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)
    with c2:
        section("Home vs away")
        rows = []
        for p, bat in ((A.full_name, ba), (B.full_name, bb)):
            home = bat.venue_country == bat.team_country.str.replace(" Women", "")
            for where, d in (("Home", bat[home]), ("Away", bat[~home])):
                rows.append({"player": p, "where": where,
                             "avg": round(d.runs.sum() / max(d.is_out.sum(), 1), 1)})
        hv = pd.DataFrame(rows)
        fig = go.Figure()
        for p, col in ((A.full_name, COLOR_A), (B.full_name, COLOR_B)):
            d = hv[hv.player == p]
            fig.add_bar(x=d["where"], y=d.avg, name=p, marker_color=col, text=d.avg,
                        textposition="outside")
        fig.update_layout(height=420, barmode="group", yaxis_title="Batting average")
        st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

    section("Impact — average in wins vs losses")
    rows = []
    for p, bat in ((A.full_name, ba), (B.full_name, bb)):
        for res, d in (("In wins", bat[bat.won == 1]), ("In losses / draws", bat[bat.won == 0])):
            rows.append({"player": p, "res": res, "avg": round(d.runs.sum() / max(d.is_out.sum(), 1), 1),
                         "n": len(d)})
    iv = pd.DataFrame(rows)
    fig = go.Figure()
    for p, col in ((A.full_name, COLOR_A), (B.full_name, COLOR_B)):
        d = iv[iv.player == p]
        fig.add_bar(x=d.res, y=d.avg, name=p, marker_color=col, text=d.avg, textposition="outside",
                    customdata=d.n, hovertemplate="%{x}: avg %{y} (%{customdata} innings)<extra></extra>")
    fig.update_layout(height=360, barmode="group", yaxis_title="Batting average")
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)

st.caption("Data: Cricsheet ball-by-ball (cricsheet.org) + Cricbuzz API · "
           "Photos: Wikipedia / Wikimedia Commons (openly licensed) · "
           "Win % = share of matches the player's team won when the player batted.")
