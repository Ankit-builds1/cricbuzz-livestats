# 🏏 Cricbuzz LiveStats — Real-Time Cricket Insights & SQL-Based Analytics

A broadcast-style cricket analytics web app that combines **live data from the Cricbuzz API**
with **every international match since 2001** (Cricsheet ball-by-ball data) in a SQL database,
and layers SQL analytics, machine learning and optimisation on top.

**🔗 Live demo:** [_add your Streamlit Cloud link here_](https://cricbuzz-livestats-ankit.streamlit.app/)

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B)
![SQLite](https://img.shields.io/badge/SQL-SQLite-003B57) ![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-F7931E)

---

## ✨ Features

| Page | What it does |
|---|---|
| 🏠 **Home** | Landing page, database stats, results ticker, architecture |
| ⚡ **Live Matches** | Live / recent / upcoming matches with full batting & bowling scorecards (Cricbuzz API) |
| 📊 **Top Player Stats** | ICC rankings (API) + all-time career leaderboards (DB) |
| ⚔️ **Player Comparison** | Player photos, percentile skill radar, career race, runs per year, form curve, score distribution, run sources, home/away, vs-opponents, impact in wins — 14 charts |
| 🏟️ **Venue Insights** | Par scores, bat-first vs chase win %, toss impact, chase success by target, top performers, records |
| 🤖 **Win Predictor** | ML win probability (Logistic Regression / Gradient Boosting) from form, home, toss & format |
| 🔍 **SQL Analytics** | 25 SQL questions (beginner → CTEs & window functions) + read-only custom query box |
| 🏆 **Fantasy XI** | Optimal fantasy team under a credit budget, solved exactly with Mixed-Integer Linear Programming |
| 🛠️ **CRUD Operations** | Create / read / update / delete players with validated forms |

## 🧱 Architecture

```
Cricbuzz API (RapidAPI) ──┐                      ┌──> SQL analytics (25 queries)
                          ├─> Python ETL ─> SQLite ├──> ML win predictor (scikit-learn)
Cricsheet ball-by-ball ───┘   (pandas)            ├──> Fantasy optimiser (SciPy MILP)
                                                  └──> Streamlit + Plotly UI (9 pages)
```

**Database (9 tables):** `teams`, `venues`, `players`, `series`, `matches`, `batting_scores`,
`bowling_figures`, `player_career_stats`, `innings_summary` — see [`sql/schema.sql`](sql/schema.sql).

| Data | Volume |
|---|---|
| Matches | 10,000+ (Tests, ODIs, T20Is · men & women · 2001 → today) |
| Players | 9,400+ (linked to Cricbuzz player IDs) |
| Batting + bowling records | 310,000+ |

## 📁 Project structure

```
cricbuzz_livestats/
├── main.py               # entry point + navigation
├── app_pages/            # the 9 Streamlit pages
├── utils/
│   ├── db_connection.py  # centralised DB connection (SQLite)
│   ├── api_client.py     # Cricbuzz API client: retries, disk cache, quota handling
│   ├── features.py       # ML feature engineering (no data leakage)
│   ├── fantasy.py        # fantasy points + MILP optimiser
│   ├── photos.py         # player photos via Wikipedia (Wikimedia Commons)
│   └── ui.py             # broadcast design system + Plotly theme
├── sql/
│   ├── schema.sql        # table definitions + indexes
│   └── queries.py        # the 25 SQL practice questions
├── data_loader.py        # ETL: Cricbuzz API → DB
├── import_cricsheet.py   # ETL: Cricsheet history → DB
├── train_model.py        # trains the win predictor
├── test_queries.py       # checks all 25 queries return data
├── models/win_model.pkl
└── data/cricbuzz.db      # ready-to-use database
```

## 🚀 Run locally

```bash
git clone https://github.com/Ankit-builds1/cricbuzz-livestats.git
cd cricbuzz-livestats
python -m venv venv && venv\Scripts\activate      # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
streamlit run main.py
```

The repo ships with a ready database, so the app works immediately.
To rebuild data from scratch:

```bash
python import_cricsheet.py   # downloads & imports match history (~1 min)
python data_loader.py        # live/recent matches, scorecards, players (needs API key)
python train_model.py        # retrain the ML model
python test_queries.py       # verify all 25 SQL queries
```

## 🔑 API key configuration

1. Sign up at [RapidAPI](https://rapidapi.com) and subscribe to **Cricbuzz Cricket** (free BASIC plan).
2. Create a `.env` file in the project root (never commit it — it is in `.gitignore`):

```
RAPIDAPI_KEY=your_key_here
RAPIDAPI_HOST=cricbuzz-cricket.p.rapidapi.com
```

On Streamlit Cloud, add the same two lines under **App settings → Secrets**.

> The free plan allows 200 calls/month. The client caches every response on disk and, when the
> quota is reached (HTTP 429), pauses API calls and serves cached data automatically.

## 🧮 SQL practice (25 questions)

Beginner (Q1–8): filtering, grouping, sorting · Intermediate (Q9–16): joins, self-joins for
partnerships, CTEs, conditional aggregation · Advanced (Q17–25): `RANK()`, `ROW_NUMBER()`, `LAG()`,
standard deviation, form & career-phase classification. All answers in [`sql/queries.py`](sql/queries.py).

## 🛡️ Engineering practices

- PEP 8 style, docstrings on all functions, modular `utils/` package
- Exception handling for every API call and DB operation; parameterised SQL (no injection)
- Secrets in `.env` / Streamlit secrets — never in code
- Read-only guard on the custom SQL box
- ML: time-based train/test split, symmetric augmentation, no feature leakage

## 📜 Data sources & credits

- **Cricbuzz Cricket API** via RapidAPI — live matches, scorecards, rankings, player profiles
- **[Cricsheet](https://cricsheet.org)** — open ball-by-ball data for international cricket
- **Wikipedia / Wikimedia Commons** — openly licensed player photos

## ⚖️ Licence & authorship

© 2026 **Ankit Dash** ([@Ankit-builds1](https://github.com/Ankit-builds1)). **All rights reserved.**
This code is shared for portfolio and evaluation purposes only — copying, re-hosting or submitting
it as your own work is not permitted. See [LICENSE](LICENSE).
