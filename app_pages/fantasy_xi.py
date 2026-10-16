"""Fantasy XI Builder: optimal fantasy team for any match-up."""
from concurrent.futures import ThreadPoolExecutor

import plotly.graph_objects as go
import streamlit as st

from utils.db_connection import run_query
from utils.fantasy import ROLE_LIMITS, best_xi, player_pool
from utils.photos import get_photo, initials
from utils.ui import ACCENT, BORDER, CARD, COLOR_A, COLOR_B, MUTED, section, setup_page

setup_page("Fantasy XI Builder", "🏆",
           "Picks the mathematically best 11 for a match-up from each player's last 10 games.",
           badges=("Integer optimisation", "100-credit budget", "Dream11-style points"))


@st.cache_data(ttl=3600)
def teams():
    return run_query("""SELECT t.team_id, t.team_name, COUNT(*) AS n FROM teams t
                        JOIN matches m ON t.team_id IN (m.team1_id, m.team2_id)
                        WHERE m.match_date >= DATE('now', '-3 years')
                        GROUP BY t.team_id HAVING n >= 15 ORDER BY n DESC""")


@st.cache_data(ttl=3600, show_spinner="Scoring players…")
def pool_for(t1, t2, fmt):
    return player_pool(run_query, [t1, t2], fmt)


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def photos(names):
    with ThreadPoolExecutor(8) as ex:
        return dict(zip(names, ex.map(get_photo, names)))


tm = teams()
names = tm.team_name.tolist()
c1, c2, c3, c4 = st.columns([4, 4, 2, 2])
a = c1.selectbox("Team A", names, index=names.index("India") if "India" in names else 0)
b = c2.selectbox("Team B", [n for n in names if n != a],
                 index=max([n for n in names if n != a].index("Australia"), 0) if "Australia" in names and a != "Australia" else 0)
fmt_label = c3.selectbox("Format", ["T20I", "ODI", "Test"])
budget = c4.slider("Credits", 90.0, 110.0, 100.0, 0.5)
fmt = {"T20I": "T20", "ODI": "ODI", "Test": "TEST"}[fmt_label]
ta, tb = (int(tm[tm.team_name == x].team_id.iloc[0]) for x in (a, b))

pool = pool_for(ta, tb, fmt)
if pool.empty or pool.team_id.nunique() < 2:
    st.warning(f"Not enough recent {fmt_label} data for {a} vs {b}. Try another format.")
    st.stop()

with st.expander(f"⚙️ Customise — {len(pool)} players in the pool"):
    must = st.multiselect("Must include", pool.full_name.tolist())
    excl = st.multiselect("Exclude (injured / rested)", [n for n in pool.full_name if n not in must])
work = pool[~pool.full_name.isin(excl)].copy()
if must:
    work.loc[work.full_name.isin(must), "exp_points"] += 1000   # force-in, removed below
xi = best_xi(work, budget=budget)
if xi is None:
    st.error("No valid XI under these constraints — raise credits or remove some must-picks.")
    st.stop()
xi["exp_points"] = xi.exp_points.where(~xi.full_name.isin(must), xi.exp_points - 1000)
xi = xi.sort_values("exp_points", ascending=False)
xi["tag"] = ["C", "VC"] + [""] * (len(xi) - 2)
xi["proj"] = xi.exp_points * xi.tag.map({"C": 2.0, "VC": 1.5}).fillna(1.0)

# ------------------------------------------------------------- KPI strip
k1, k2, k3, k4 = st.columns(4)
k1.metric("Projected points", f"{xi.proj.sum():.0f}")
k2.metric("Credits used", f"{xi.credits.sum():.1f} / {budget:.0f}")
k3.metric(f"{a} · {b}", f"{(xi.team_id == ta).sum()} – {(xi.team_id == tb).sum()}")
k4.metric("Captain", xi.iloc[0].full_name.split()[-1], f"{xi.iloc[0].exp_points:.0f} pts × 2")

# ------------------------------------------------------------ pitch view
pics = photos(tuple(xi.full_name))
colors = {ta: COLOR_A, tb: COLOR_B}


def chip(r):
    col = colors[r.team_id]
    ph = pics.get(r.full_name)
    face = (f'<img src="{ph["img"]}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;'
            f'object-position:top;border:3px solid {col}">' if ph and ph.get("img") else
            f'<div style="width:64px;height:64px;border-radius:50%;display:flex;align-items:center;'
            f'justify-content:center;font-weight:800;font-size:1.3rem;background:#fff;color:{col};'
            f'border:3px solid {col};margin:auto">{initials(r.full_name)}</div>')
    tag = (f'<div style="position:absolute;top:-6px;right:14px;background:{ACCENT if r.tag == "C" else "#FACC15"};'
           f'color:#0B1220;font-weight:800;font-size:.7rem;border-radius:999px;padding:2px 7px">{r.tag}</div>'
           if r.tag else "")
    return (f'<div style="position:relative;text-align:center;width:120px">{tag}'
            f'<div style="display:flex;justify-content:center">{face}</div>'
            f'<div style="background:rgba(11,18,32,.85);border-radius:8px;margin-top:6px;padding:4px 6px">'
            f'<div style="font-weight:700;font-size:.82rem;color:#fff;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">{r.full_name}</div>'
            f'<div style="color:#CBD5E1;font-size:.72rem">{r.credits} cr · {r.exp_points:.0f} pts</div></div></div>')


rows_html = ""
for role, title in (("WK", "Wicket-keepers"), ("BAT", "Batters"), ("AR", "All-rounders"), ("BOWL", "Bowlers")):
    grp = xi[xi.role == role]
    if grp.empty:
        continue
    chips = "".join(chip(r) for r in grp.itertuples())
    rows_html += (f'<div style="color:#D1FAE5;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;'
                  f'text-align:center;margin:14px 0 8px;opacity:.8">{title}</div>'
                  f'<div style="display:flex;justify-content:center;gap:18px;flex-wrap:wrap">{chips}</div>')

left, right = st.columns([7, 4])
with left:
    section("Your optimal XI")
    st.markdown(
        f'<div style="background:radial-gradient(ellipse at center, #15803d 0%, #166534 45%, #14532d 100%);'
        f'border-radius:28px;padding:18px 10px 26px;border:2px solid #22c55e55;position:relative">'
        f'<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:70px;'
        f'height:46%;background:#d6c48a33;border-radius:6px"></div>{rows_html}</div>',
        unsafe_allow_html=True)
    st.caption(f"🔵 {a}   🟠 {b}   ·   C = captain (2×)  ·  VC = vice-captain (1.5×)")

with right:
    section("Projected points")
    d = xi.sort_values("proj")
    fig = go.Figure(go.Bar(
        x=d.proj, y=d.full_name, orientation="h",
        marker_color=[colors[t] for t in d.team_id],
        text=[f"{p:.0f}{' (C)' if t == 'C' else ' (VC)' if t == 'VC' else ''}" for p, t in zip(d.proj, d.tag)],
        textposition="outside", hovertemplate="%{y}: %{x:.1f} pts<extra></extra>"))
    fig.update_layout(height=470, xaxis_title="Projected fantasy points", margin=dict(l=0, r=40))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    section("Team balance")
    bal = xi.role.value_counts().reindex(ROLE_LIMITS.keys(), fill_value=0)
    fig = go.Figure(go.Bar(x=list(bal.index), y=bal.values, marker_color=ACCENT,
                           text=[f"{v} ({ROLE_LIMITS[r][0]}–{ROLE_LIMITS[r][1]})" for r, v in bal.items()],
                           textposition="outside"))
    fig.update_layout(height=220, yaxis=dict(range=[0, 7], visible=False), margin=dict(t=10))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

section("Full player pool — value for money")
pool_plot = work.assign(picked=work.player_id.isin(xi.player_id),
                        exp_points=work.exp_points.where(~work.full_name.isin(must), work.exp_points - 1000))
fig = go.Figure()
for team_id, col, name in ((ta, COLOR_A, a), (tb, COLOR_B, b)):
    d = pool_plot[pool_plot.team_id == team_id]
    fig.add_scatter(x=d.credits, y=d.exp_points, mode="markers+text", name=name,
                    text=d.full_name.str.split().str[-1], textposition="top center",
                    textfont=dict(size=10, color=MUTED),
                    marker=dict(color=col, size=[16 if p else 9 for p in d.picked],
                                line=dict(color=["white" if p else col for p in d.picked], width=2)),
                    hovertemplate="%{customdata}<br>%{x} cr · %{y:.1f} pts<extra></extra>",
                    customdata=d.full_name + " (" + d.role + ")")
fig.update_layout(height=430, xaxis_title="Credits (cost)", yaxis_title="Expected points / match")
st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
st.caption("Large white-ringed dots = selected. Top-left = best value (high points, low cost).")

with st.expander("📋 Pool table & scoring rules"):
    show = work.assign(selected=work.player_id.isin(xi.player_id).map({True: "✅", False: ""}))
    st.dataframe(show[["selected", "full_name", "team_name", "role", "credits", "exp_points",
                       "bat_pts", "bowl_pts", "field_pts", "games", "recent_matches"]]
                 .round(1).rename(columns={"full_name": "player", "team_name": "team"}),
                 hide_index=True, width="stretch")
    st.markdown("""
**Points:** 1/run · +1 per four · +2 per six · +8 for 50 · +16 for 100 · −2 duck ·
25/wicket · +4 for 3W · +8 for 5W · +12 per maiden (ODI/T20) · 8/catch · 12/stumping.
**Expected points** = average over the player's last 10 matches in this format (fielding from career rate).
**Rules:** 11 players · max 7 from one team · WK 1–4 · BAT 3–6 · AR 1–4 · BOWL 3–6 · credits ≤ budget.
**Optimiser:** exact Mixed-Integer Linear Programming (`scipy.optimize.milp`).
""")
