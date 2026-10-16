"""Broadcast-style design system shared by every page.

- render_chrome(): global CSS, sidebar logo and the scrolling results ticker
- setup_page():    scoreboard-style page header
- section():       "lower-third" style section titles
- a light Plotly template so all charts match
"""
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

GREEN = "#0A8754"      # brand / accent
NAVY = "#1E293B"
COLOR_A = "#1D4ED8"    # player / team A (royal blue)
COLOR_B = "#E4572E"    # player / team B (broadcast orange)
ACCENT = GREEN
MUTED = "#64748B"
CARD = "#FFFFFF"
BORDER = "#E2E8F0"
LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo.svg"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, select, textarea {{ font-family: 'Inter', sans-serif; }}
h1, h2, h3, .cond {{ font-family: 'Barlow Condensed', sans-serif !important; letter-spacing: .01em; }}
.block-container {{ padding-top: 1rem; padding-bottom: 3rem; max-width: 1440px; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #06603C 0%, #0A8754 55%, #0B7A4D 100%); }}
[data-testid="stSidebar"] * {{ color: #ECFDF5 !important; }}
[data-testid="stSidebarNav"] a {{ border-radius: 10px; margin: 2px 6px; padding: 6px 10px; }}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(255,255,255,.12); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: #FFFFFF; box-shadow: 0 4px 14px rgba(0,0,0,.18); }}
[data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: {GREEN} !important; font-weight: 700; }}
[data-testid="stNavSectionHeader"], [data-testid="stSidebarNavSeparator"] {{ opacity: .75; text-transform: uppercase;
    letter-spacing: .14em; font-size: .7rem !important; }}
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ background:#fff; border-radius:12px; padding:4px 8px; height: 3rem; }}

/* ---------- ticker ---------- */
.ticker {{ display:flex; align-items:stretch; background:{NAVY}; border-radius: 12px; overflow:hidden;
           margin: 4px 0 16px; box-shadow: 0 6px 18px rgba(15,23,42,.18); }}
.ticker .tag {{ background:{COLOR_B}; color:#fff; font-family:'Barlow Condensed'; font-weight:800; font-size:1rem;
                padding: 8px 16px; letter-spacing:.08em; white-space:nowrap; display:flex; align-items:center; gap:6px; }}
.ticker .tag .dot {{ width:8px; height:8px; border-radius:50%; background:#fff; animation: blink 1.2s infinite; }}
.ticker .track {{ overflow:hidden; flex:1; display:flex; align-items:center; }}
.ticker .move {{ display:inline-flex; gap:42px; white-space:nowrap; padding-left:100%; animation: scroll 70s linear infinite;
                 color:#E2E8F0; font-size:.88rem; }}
.ticker:hover .move {{ animation-play-state: paused; }}
.ticker b {{ color:#fff; }} .ticker .fmt {{ color:#86EFAC; font-weight:700; font-size:.72rem; margin-right:6px; }}
@keyframes scroll {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-100%); }} }}
@keyframes blink {{ 50% {{ opacity:.2; }} }}

/* ---------- scoreboard header ---------- */
.board {{ display:flex; border-radius: 16px; overflow:hidden; margin-bottom: 18px;
          box-shadow: 0 10px 30px rgba(15,23,42,.12); border:1px solid {BORDER}; }}
.board .icon {{ background:{GREEN}; color:#fff; font-size:2.2rem; display:flex; align-items:center;
                justify-content:center; min-width:96px; }}
.board .body {{ background: linear-gradient(110deg, {NAVY} 0%, #0F3B2E 100%); color:#fff; padding: 16px 24px; flex:1;
                position:relative; }}
.board .body:after {{ content:""; position:absolute; right:0; top:0; bottom:0; width:220px;
                      background: repeating-linear-gradient(135deg, rgba(255,255,255,.05) 0 12px, transparent 12px 24px); }}
.board h1 {{ color:#fff !important; margin:0; font-size:2.3rem; font-weight:800; text-transform:uppercase; line-height:1.05; }}
.board p {{ margin:6px 0 0; color:#CBD5E1; font-size:.95rem; }}
.badge {{ display:inline-block; padding:2px 10px; margin: 0 6px 6px 0; border-radius: 4px; font-size:.7rem; font-weight:700;
          letter-spacing:.06em; text-transform:uppercase; background: rgba(255,255,255,.12); color:#BBF7D0;
          border:1px solid rgba(187,247,208,.35); }}

/* ---------- lower-third section title ---------- */
.section {{ display:flex; align-items:stretch; margin: 26px 0 12px; }}
.section .k {{ background:{GREEN}; width:10px; border-radius: 4px 0 0 4px; }}
.section .t {{ background:{NAVY}; color:#fff; font-family:'Barlow Condensed'; font-weight:700; font-size:1.15rem;
               text-transform:uppercase; letter-spacing:.06em; padding: 4px 16px 4px 12px;
               clip-path: polygon(0 0, 100% 0, calc(100% - 14px) 100%, 0 100%); padding-right: 30px; }}

/* ---------- cards, metrics, tables ---------- */
.card {{ background:{CARD}; border:1px solid {BORDER}; border-radius: 14px; padding: 18px 20px;
         box-shadow: 0 4px 16px rgba(15,23,42,.06); transition: transform .15s, box-shadow .15s; }}
.card:hover {{ transform: translateY(-3px); box-shadow: 0 12px 28px rgba(15,23,42,.12); }}
[data-testid="stMetric"] {{ background:{CARD}; border:1px solid {BORDER}; border-top: 4px solid {GREEN};
                            border-radius: 12px; padding: 12px 16px; box-shadow: 0 4px 14px rgba(15,23,42,.05); }}
[data-testid="stMetricValue"] {{ font-family:'Barlow Condensed'; font-weight:800; font-size: 2rem !important; color:{NAVY}; }}
[data-testid="stMetricLabel"] p {{ text-transform: uppercase; letter-spacing:.06em; font-size:.72rem !important;
                                   color:{MUTED} !important; font-weight:600; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; border-radius: 12px; overflow:hidden; }}
div[data-testid="stTabs"] button[role="tab"] {{ font-family:'Barlow Condensed'; font-size:1.05rem; font-weight:700;
                                                 text-transform:uppercase; letter-spacing:.04em; }}
div[data-testid="stTabs"] button[aria-selected="true"] {{ color:{GREEN}; }}
.stButton button[kind="primary"], .stFormSubmitButton button {{ background:{GREEN}; border:none; font-weight:700;
    text-transform:uppercase; letter-spacing:.05em; border-radius: 8px; }}
[data-testid="stPageLink"] a {{ color:{GREEN} !important; font-weight:600; }}

/* ---------- comparison widgets ---------- */
.pcard {{ background:{CARD}; border:1px solid {BORDER}; border-radius: 16px; padding: 18px 22px; position:relative;
          overflow:hidden; box-shadow: 0 8px 24px rgba(15,23,42,.08); }}
.pcard .stripe {{ position:absolute; left:0; top:0; bottom:0; width:7px; }}
.pcard .name {{ font-family:'Barlow Condensed'; font-size: 1.9rem; font-weight: 800; margin: 0; text-transform:uppercase; }}
.pcard .meta {{ color:{MUTED}; font-size:.88rem; margin-top:2px; }}
.pcard .grid {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; margin-top: 14px;
                border-top:1px dashed {BORDER}; padding-top: 12px; }}
.pcard .k {{ color:{MUTED}; font-size:.68rem; text-transform:uppercase; letter-spacing:.08em; font-weight:600; }}
.pcard .v {{ font-family:'Barlow Condensed'; font-size:1.6rem; font-weight:800; color:{NAVY}; }}
.vs {{ display:flex; align-items:center; justify-content:center; height:100%; }}
.vs span {{ background:{NAVY}; color:#fff; font-family:'Barlow Condensed'; font-weight:800; font-size:1.4rem;
            width:56px; height:56px; border-radius:50%; display:flex; align-items:center; justify-content:center;
            box-shadow: 0 0 0 5px {GREEN}33; }}
.cmp {{ display:grid; grid-template-columns: 1fr auto 1fr; align-items:center; gap:10px; background:{CARD};
        border:1px solid {BORDER}; border-radius: 10px; padding: 7px 16px; margin-bottom: 6px; }}
.cmp .l {{ text-align:right; font-family:'Barlow Condensed'; font-weight:700; font-size:1.25rem; }}
.cmp .r {{ text-align:left;  font-family:'Barlow Condensed'; font-weight:700; font-size:1.25rem; }}
.cmp .m {{ background:{NAVY}; color:#fff; font-size:.7rem; text-transform:uppercase; letter-spacing:.08em;
           min-width: 150px; text-align:center; padding: 4px 8px; border-radius: 4px; font-weight:600; }}
.win-a {{ color:{COLOR_A}; }} .win-b {{ color:{COLOR_B}; }} .tie {{ color:{NAVY}; }}
footer {{ visibility:hidden; }}
</style>
"""


@st.cache_data(ttl=600)
def _ticker_items():
    from utils.db_connection import run_query
    df = run_query("""
        SELECT m.match_format, t1.short_name s1, t1.team_name n1, t2.short_name s2, t2.team_name n2,
               m.status_text, m.state
        FROM matches m JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id
        WHERE m.status_text IS NOT NULL AND m.state IN ('Complete', 'In Progress')
        ORDER BY m.match_date DESC, m.match_id DESC LIMIT 18""")
    fmt = {"T20": "T20", "ODI": "ODI", "TEST": "TEST"}
    return [f'<span><span class="fmt">{fmt.get(r.match_format, r.match_format)}</span>'
            f'<b>{r.s1 or r.n1} v {r.s2 or r.n2}</b> — {r.status_text}</span>' for r in df.itertuples()]


def render_chrome():
    """Global CSS + sidebar logo + results ticker. Called once by main.py."""
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO.exists():
        st.logo(str(LOGO), size="large")
    try:
        items = "".join(_ticker_items())
    except Exception:  # ticker must never break a page
        items = ""
    if items:
        st.markdown(f'<div class="ticker"><div class="tag"><span class="dot"></span>RESULTS</div>'
                    f'<div class="track"><div class="move">{items}</div></div></div>',
                    unsafe_allow_html=True)


def setup_page(title, icon, subtitle="", badges=()):
    """Scoreboard-style page header (page config is set once in main.py)."""
    b = "".join(f'<span class="badge">{x}</span>' for x in badges)
    st.markdown(f'<div class="board"><div class="icon">{icon}</div><div class="body">{b}'
                f'<h1>{title}</h1><p>{subtitle}</p></div></div>', unsafe_allow_html=True)


def section(text):
    st.markdown(f'<div class="section"><div class="k"></div><div class="t">{text}</div></div>',
                unsafe_allow_html=True)


def _template():
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        font=dict(family="Inter, sans-serif", color="#334155", size=13),
        title=dict(font=dict(family="Barlow Condensed", size=18, color=NAVY)),
        xaxis=dict(gridcolor="#EEF2F7", zerolinecolor="#E2E8F0", linecolor="#CBD5E1"),
        yaxis=dict(gridcolor="#EEF2F7", zerolinecolor="#E2E8F0", linecolor="#CBD5E1"),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=12, r=12, t=40, b=12),
        hoverlabel=dict(bgcolor=NAVY, font_color="#fff", font_family="Inter", bordercolor=NAVY),
        colorway=[COLOR_A, COLOR_B, GREEN, "#7C3AED", "#DB2777", "#CA8A04"],
    )
    return t


pio.templates["livestats"] = _template()
pio.templates.default = "livestats"
