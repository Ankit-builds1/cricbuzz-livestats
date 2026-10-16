"""Import REAL international match history from Cricsheet (cricsheet.org).

Cricsheet publishes free ball-by-ball data for every international match
(Tests, ODIs, T20Is - men & women). This script:
  1. downloads the zips + player register (if not already in data/raw/)
  2. aggregates deliveries into batting_scores / bowling_figures per player
  3. fills teams, venues, series, matches, players, player_career_stats
Player IDs use Cricsheet's Cricbuzz key where available, so they link
directly to players fetched from the Cricbuzz API.

Data licence: Cricsheet data is free to use (see cricsheet.org).
"""
import csv
import hashlib
import json
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
DB_PATH = BASE / "data" / "cricbuzz.db"
FILES = {
    "tests_json.zip": "https://cricsheet.org/downloads/tests_json.zip",
    "odis_json.zip": "https://cricsheet.org/downloads/odis_json.zip",
    "t20s_json.zip": "https://cricsheet.org/downloads/t20s_json.zip",
    "people.csv": "https://cricsheet.org/register/people.csv",
    "names.csv": "https://cricsheet.org/register/names.csv",
}
FORMAT = {"Test": "TEST", "ODI": "ODI", "T20": "T20"}
NOT_BOWLER_WICKETS = {"run out", "retired hurt", "retired out", "obstructing the field",
                      "retired not out", "handled the ball", "timed out"}
CAPACITY = {  # known stadium capacities, matched by name fragment
    "Narendra Modi": 132000, "Melbourne Cricket Ground": 100024, "Eden Gardens": 68000,
    "Perth Stadium": 60000, "Optus Stadium": 60000, "Adelaide Oval": 53583,
    "Sydney Cricket Ground": 48000, "Eden Park": 42000, "Chinnaswamy": 40000,
    "Rajiv Gandhi International": 55000, "Brisbane Cricket Ground": 42000, "Gabba": 42000,
    "MA Chidambaram": 50000, "Arun Jaitley": 41820, "Feroz Shah Kotla": 41820,
    "Wankhede": 33108, "Lord's": 31100, "Kennington Oval": 27500, "Old Trafford": 26000,
    "Edgbaston": 25000, "Headingley": 18350, "Gaddafi": 27000, "National Stadium, Karachi": 34228,
    "Premadasa": 35000, "Galle": 35000, "Newlands": 25000, "Wanderers": 34000,
    "Kingsmead": 25000, "SuperSport Park": 22000, "Shere Bangla": 25000,
    "Kensington Oval": 28000, "Dubai International": 25000, "Sharjah": 27000,
    "Sheikh Zayed": 20000, "Hagley Oval": 18000, "Basin Reserve": 11600,
    "Greenfield International": 55000, "Barabati": 45000, "Holkar": 30000,
}


def download():
    """Download Cricsheet files that are not already present."""
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        path = RAW / name
        if not path.exists():
            print(f"Downloading {name} ...")
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            path.write_bytes(r.content)


def stable_int(text, base):
    """Deterministic integer ID from a string (same input -> same ID)."""
    return base + int(hashlib.md5(text.encode()).hexdigest()[:7], 16) % 900000


def load_register():
    """Map Cricsheet person id -> (our player_id, best full name)."""
    names = defaultdict(list)
    with open(RAW / "names.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names[row["identifier"]].append(row["name"])
    reg = {}
    with open(RAW / "people.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["identifier"]
            cb = row.get("key_cricbuzz", "").strip()
            pid = int(cb) if cb.isdigit() else stable_int(cid, 5000000)
            variants = names.get(cid, []) + [row["name"]]
            # prefer the longest multi-word variant without initials ("Virat Kohli" over "V Kohli")
            full = max(variants, key=lambda n: (len(n.split()) > 1 and not n.split()[0].isupper(), len(n)))
            reg[cid] = (pid, full)
    return reg


def overs_str(balls):
    return float(f"{balls // 6}.{balls % 6}")


def parse_match(d, reg):
    """Aggregate one Cricsheet match into batting, bowling and fielding rows."""
    info = d["info"]
    people = info.get("registry", {}).get("people", {})
    pid = lambda name: reg.get(people.get(name), (stable_int(name, 5000000), name))[0]
    batting, bowling, fielding, totals = [], [], Counter(), []
    for inn_no, inn in enumerate(d.get("innings", []), start=1):
        if inn.get("super_over"):
            continue
        bat_team = inn["team"]
        bowl_team = next((t for t in info["teams"] if t != bat_team), None)
        order, bat = [], defaultdict(lambda: {"runs": 0, "balls": 0, "4s": 0, "6s": 0, "out": 0})
        tot = {"runs": 0, "wkts": 0, "balls": 0}
        bowl = defaultdict(lambda: {"balls": 0, "runs": 0, "wkts": 0, "maidens": 0})
        for over in inn.get("overs", []):
            over_runs = defaultdict(int)
            for dl in over["deliveries"]:
                for p in (dl["batter"], dl["non_striker"]):
                    if p not in order:
                        order.append(p)
                extras = dl.get("extras", {})
                r = dl["runs"]["batter"]
                tot["runs"] += dl["runs"]["total"]
                tot["wkts"] += len(dl.get("wickets", []))
                tot["balls"] += "wides" not in extras and "noballs" not in extras
                b = bat[dl["batter"]]
                b["runs"] += r
                if "wides" not in extras:
                    b["balls"] += 1
                b["4s"] += r == 4
                b["6s"] += r == 6
                bw = bowl[dl["bowler"]]
                conceded = r + extras.get("wides", 0) + extras.get("noballs", 0)
                bw["runs"] += conceded
                over_runs[dl["bowler"]] += conceded
                if "wides" not in extras and "noballs" not in extras:
                    bw["balls"] += 1
                for w in dl.get("wickets", []):
                    bat[w["player_out"]]["out"] = 1
                    if w["player_out"] not in order:
                        order.append(w["player_out"])
                    if w["kind"] not in NOT_BOWLER_WICKETS:
                        bw["wkts"] += 1
                    if w["kind"] == "caught and bowled":
                        fielding[(dl["bowler"], "c")] += 1
                    for f in w.get("fielders", []):
                        if "name" in f and not f.get("substitute"):
                            fielding[(f["name"], "st" if w["kind"] == "stumped" else
                                      "c" if w["kind"] == "caught" else "ro")] += 1
            for name, runs in over_runs.items():
                if runs == 0 and len(over["deliveries"]) >= 6:
                    bowl[name]["maidens"] += 1
        totals.append((bat_team, inn_no, tot["runs"], tot["wkts"], tot["balls"]))
        for pos, name in enumerate(order, start=1):
            b = bat[name]
            batting.append((pid(name), bat_team, inn_no, pos, b["runs"], b["balls"], b["4s"],
                            b["6s"], round(100 * b["runs"] / b["balls"], 2) if b["balls"] else 0,
                            b["out"]))
        for name, s in bowl.items():
            ov = s["balls"] / 6
            bowling.append((pid(name), bowl_team, inn_no, overs_str(s["balls"]), s["maidens"],
                            s["runs"], s["wkts"], round(s["runs"] / ov, 2) if ov else None))
    return batting, bowling, {(pid(n), k): v for (n, k), v in fielding.items()}, totals


def team_name(name, gender):
    return f"{name} Women" if gender == "female" and not name.endswith("Women") else name


def main():
    download()
    reg = load_register()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(matches)")]
    if "is_sample" not in cols:
        cur.execute("ALTER TABLE matches ADD COLUMN is_sample INTEGER DEFAULT 0")
    if "source" not in cols:
        cur.execute("ALTER TABLE matches ADD COLUMN source TEXT DEFAULT 'cricbuzz_api'")
    pcols = [r[1] for r in cur.execute("PRAGMA table_info(players)")]
    if "gender" not in pcols:
        cur.execute("ALTER TABLE players ADD COLUMN gender TEXT")

    cur.execute("""CREATE TABLE IF NOT EXISTS innings_summary (
        match_id INTEGER, innings_no INTEGER, team_id INTEGER,
        runs INTEGER, wickets INTEGER, balls INTEGER,
        PRIMARY KEY (match_id, innings_no))""")
    cur.execute("DELETE FROM innings_summary WHERE match_id >= 8000000")
    # remove old synthetic sample data and any previous Cricsheet import
    old = "SELECT match_id FROM matches WHERE match_id >= 8000000"
    for t in ("batting_scores", "bowling_figures"):
        cur.execute(f"DELETE FROM {t} WHERE match_id IN ({old})")
    cur.execute("DELETE FROM matches WHERE match_id >= 8000000")
    cur.execute("DELETE FROM series WHERE series_id >= 90000")
    cur.execute("DELETE FROM players WHERE player_id >= 9000000")
    cur.execute("DELETE FROM venues WHERE venue_id >= 90000")
    # API profile rows have catches = NULL; everything else is derived and rebuilt
    cur.execute("DELETE FROM player_career_stats WHERE catches IS NOT NULL")
    cur.execute("DELETE FROM player_career_stats WHERE player_id NOT IN (SELECT player_id FROM players)")
    # roles not from an API profile (no batting_style) are re-derived below
    cur.execute("UPDATE players SET playing_role = NULL WHERE batting_style IS NULL")

    teams = {r[1]: r[0] for r in cur.execute("SELECT team_id, team_name FROM teams")}
    existing = {(r[0], frozenset((r[1], r[2]))) for r in cur.execute(
        "SELECT match_date, team1_id, team2_id FROM matches")}
    venues, series = {}, {}
    venue_teams = defaultdict(Counter)
    fielding_totals = Counter()
    player_team = defaultdict(Counter)
    player_gender = {}
    n_matches = 0

    for zname in ("tests_json.zip", "odis_json.zip", "t20s_json.zip"):
        with zipfile.ZipFile(RAW / zname) as z:
            files = [f for f in z.namelist() if f.endswith(".json")]
            print(f"{zname}: {len(files)} matches")
            for fname in files:
                d = json.loads(z.read(fname))
                info = d["info"]
                fmt = FORMAT.get(info.get("match_type"))
                if not fmt or len(info.get("teams", [])) != 2:
                    continue
                g = info.get("gender", "male")
                t_names = [team_name(t, g) for t in info["teams"]]
                tids = []
                for t in t_names:
                    if t not in teams:
                        teams[t] = stable_int(t, 70000)
                        cur.execute("INSERT OR IGNORE INTO teams (team_id, team_name, country) "
                                    "VALUES (?,?,?)", (teams[t], t, t.replace(" Women", "")))
                    tids.append(teams[t])
                date = info["dates"][0]
                if (date, frozenset(tids)) in existing:
                    continue  # already loaded from the Cricbuzz API
                vname = info.get("venue", "Unknown")
                if vname not in venues:
                    venues[vname] = (stable_int(vname, 90000) , info.get("city"))
                vid = venues[vname][0]
                for t in t_names:  # host = team that plays most often in this city
                    venue_teams[info.get("city") or vname][t.replace(" Women", "")] += 1
                ev = info.get("event", {}).get("name") or f"{' v '.join(t_names)} {info.get('season')}"
                skey = (ev, info.get("season"), fmt)
                if skey not in series:
                    series[skey] = {"id": stable_int("|".join(map(str, skey)), 100000),
                                    "start": date, "end": date, "n": 0, "venues": Counter()}
                s = series[skey]
                s["start"], s["end"] = min(s["start"], date), max(s["end"], date)
                s["n"] += 1
                s["venues"][vname] += 1

                toss = info.get("toss", {})
                out = info.get("outcome", {})
                winner = teams.get(team_name(out["winner"], g)) if "winner" in out else None
                by = out.get("by", {})
                vtype = "runs" if "runs" in by else "wickets" if "wickets" in by else None
                margin = by.get("runs") or by.get("wickets")
                status = (f"{team_name(out['winner'], g)} won by {margin} {vtype}" if winner and margin
                          else out.get("result", "No result").title())
                mid = 8000000 + n_matches
                cur.execute(
                    """INSERT INTO matches (match_id, series_id, match_desc, match_format, team1_id,
                       team2_id, venue_id, match_date, state, status_text, toss_winner_id,
                       toss_decision, winner_id, victory_margin, victory_type, is_sample, source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'cricsheet')""",
                    (mid, s["id"], f"{ev} (Match {info.get('event', {}).get('match_number', '')})".replace(" (Match )", ""),
                     fmt, tids[0], tids[1], vid, date, "Complete", status,
                     teams.get(team_name(toss["winner"], g)) if "winner" in toss else None,
                     toss.get("decision"), winner, margin, vtype))
                bat, bowl, field, totals = parse_match(d, reg)
                cur.executemany("INSERT INTO innings_summary VALUES (?,?,?,?,?,?)",
                                [(mid, i, teams[team_name(t, g)], r, w, b) for t, i, r, w, b in totals])
                cur.executemany(
                    """INSERT INTO batting_scores (match_id, player_id, team_id, innings_no,
                       batting_position, runs, balls, fours, sixes, strike_rate, is_out)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [(mid, r[0], teams[team_name(r[1], g)], *r[2:]) for r in bat])
                cur.executemany(
                    """INSERT INTO bowling_figures (match_id, player_id, team_id, innings_no,
                       overs, maidens, runs_given, wickets, economy) VALUES (?,?,?,?,?,?,?,?,?)""",
                    [(mid, r[0], teams.get(team_name(r[1], g)) if r[1] else None, *r[2:]) for r in bowl])
                for k, v in field.items():
                    fielding_totals[(k[0], fmt, k[1])] += v
                for team, plist in info.get("players", {}).items():
                    for name in plist:
                        p = reg.get(info.get("registry", {}).get("people", {}).get(name))
                        if p:
                            player_team[p][team.replace(" Women", "")] += 1
                            player_gender[p[0]] = g
                n_matches += 1

    # venues with country = team that plays there most often (the host)
    for vname, (vid, city) in venues.items():
        vt = venue_teams[city or vname]
        country = vt.most_common(1)[0][0] if vt else None
        cap = next((c for k, c in CAPACITY.items() if k.lower() in vname.lower()), None)
        cur.execute("INSERT OR REPLACE INTO venues VALUES (?,?,?,?,?)", (vid, vname, city, country, cap))
    vcountry = {v[0]: c for v, c in ((venues[n], cur.execute(
        "SELECT country FROM venues WHERE venue_id=?", (venues[n][0],)).fetchone()[0]) for n in venues)}
    for (ev, season, fmt), s in series.items():
        host = vcountry.get(venues[s["venues"].most_common(1)[0][0]][0])
        label = {"TEST": "Test", "ODI": "ODI", "T20": "T20I"}[fmt]
        cur.execute("INSERT OR REPLACE INTO series VALUES (?,?,?,?,?,?,?)",
                    (s["id"], f"{ev} ({season})", host, label, s["start"], s["end"], s["n"]))
    # API venues: fill country from Cricsheet venues in the same city
    cur.execute("""UPDATE venues SET country = (SELECT v2.country FROM venues v2
                   WHERE v2.city = venues.city AND v2.country IS NOT NULL LIMIT 1)
                   WHERE country IS NULL""")
    # international teams: country = team name
    cur.execute("UPDATE teams SET country = REPLACE(team_name, ' Women', '') WHERE country IS NULL")

    # players: insert/update name, country (main team) and gender
    for (pid, full), tc in player_team.items():
        country = tc.most_common(1)[0][0]
        cur.execute("INSERT OR IGNORE INTO players (player_id, full_name, country) VALUES (?,?,?)",
                    (pid, full, country))
        cur.execute("UPDATE players SET country = COALESCE(country, ?), gender = ? WHERE player_id = ?",
                    (country, player_gender.get(pid), pid))
    dups = cur.execute("""
        SELECT c.player_id, a.player_id FROM players c
        JOIN players a ON a.full_name = c.full_name AND a.country = c.country
        WHERE c.player_id >= 5000000 AND a.player_id < 5000000""").fetchall()
    for new_id, api_id in dups:
        for t in ("batting_scores", "bowling_figures"):
            cur.execute(f"UPDATE {t} SET player_id = ? WHERE player_id = ?", (api_id, new_id))
        cur.execute("UPDATE players SET gender = COALESCE(gender, (SELECT gender FROM players "
                    "WHERE player_id = ?)) WHERE player_id = ?", (new_id, api_id))
        cur.execute("DELETE FROM players WHERE player_id = ?", (new_id,))
    fielding_totals = Counter({(dict(dups).get(p, p), f, k): v for (p, f, k), v in fielding_totals.items()})
    print(f"Merged {len(dups)} duplicate players (Cricsheet ↔ Cricbuzz API)")
    conn.commit()

    # career stats per format from all match rows (API profile rows are kept)
    cur.execute("DELETE FROM player_career_stats WHERE player_id IN "
                "(SELECT player_id FROM players WHERE playing_role IS NULL OR player_id >= 5000000)")
    cur.execute("""
        INSERT OR IGNORE INTO player_career_stats
        SELECT b.player_id,
               CASE m.match_format WHEN 'TEST' THEN 'Test' WHEN 'ODI' THEN 'ODI' ELSE 'T20I' END AS fmt,
               COUNT(DISTINCT b.match_id), COUNT(*), SUM(b.runs), MAX(b.runs),
               ROUND(1.0 * SUM(b.runs) / NULLIF(SUM(b.is_out), 0), 2),
               ROUND(100.0 * SUM(b.runs) / NULLIF(SUM(b.balls), 0), 2),
               SUM(b.runs >= 100), SUM(b.runs BETWEEN 50 AND 99),
               NULL, NULL, NULL, 0, 0
        FROM batting_scores b JOIN matches m USING (match_id)
        GROUP BY b.player_id, fmt""")
    cur.execute("""
        WITH bw AS (
            SELECT w.player_id,
                   CASE m.match_format WHEN 'TEST' THEN 'Test' WHEN 'ODI' THEN 'ODI' ELSE 'T20I' END AS fmt,
                   COUNT(DISTINCT w.match_id) AS mt, SUM(w.wickets) AS wk, SUM(w.runs_given) AS rg,
                   SUM(CAST(w.overs AS INT) * 6 + ROUND((w.overs - CAST(w.overs AS INT)) * 10)) AS balls
            FROM bowling_figures w JOIN matches m USING (match_id) GROUP BY 1, 2)
        INSERT INTO player_career_stats (player_id, format, matches, innings, runs, wickets,
                                         bowling_average, economy, catches, stumpings)
        SELECT player_id, fmt, mt, 0, 0, wk, ROUND(1.0 * rg / NULLIF(wk, 0), 2),
               ROUND(6.0 * rg / NULLIF(balls, 0), 2), 0, 0 FROM bw WHERE true
        ON CONFLICT (player_id, format) DO UPDATE SET
            matches = MAX(COALESCE(player_career_stats.matches, 0), excluded.matches),
            wickets = COALESCE(player_career_stats.wickets, excluded.wickets),
            bowling_average = COALESCE(player_career_stats.bowling_average, excluded.bowling_average),
            economy = COALESCE(player_career_stats.economy, excluded.economy)""")
    label = {"TEST": "Test", "ODI": "ODI", "T20": "T20I"}
    for (p, fmt, kind), v in fielding_totals.items():
        col = {"c": "catches", "st": "stumpings"}.get(kind)
        if col:
            cur.execute(f"UPDATE player_career_stats SET {col} = COALESCE({col}, 0) + ? "
                        "WHERE player_id = ? AND format = ?", (v, p, label[fmt]))

    # derive playing role where the API gave none
    cur.execute("""
        WITH s AS (
            SELECT p.player_id,
                   (SELECT SUM(stumpings) FROM player_career_stats c WHERE c.player_id = p.player_id) AS st,
                   (SELECT 1.0 * SUM(runs) / NULLIF(SUM(is_out), 0) FROM batting_scores b WHERE b.player_id = p.player_id) AS avg,
                   (SELECT COUNT(*) FROM batting_scores b WHERE b.player_id = p.player_id) AS inns,
                   (SELECT AVG(overs) FROM bowling_figures w WHERE w.player_id = p.player_id) AS ov,
                   (SELECT COUNT(*) FROM bowling_figures w WHERE w.player_id = p.player_id) AS bowl_inns
            FROM players p WHERE p.playing_role IS NULL)
        UPDATE players SET playing_role = (
            SELECT CASE WHEN st >= 1 THEN 'Wicket-keeper'
                        WHEN bowl_inns >= 0.5 * inns AND ov >= 3 AND COALESCE(avg, 0) >= 20 THEN 'All-rounder'
                        WHEN bowl_inns >= 0.5 * inns AND ov >= 2 THEN 'Bowler'
                        ELSE 'Batsman' END
            FROM s WHERE s.player_id = players.player_id)
        WHERE playing_role IS NULL""")
    conn.commit()
    for t in ("matches", "players", "teams", "venues", "series", "batting_scores",
              "bowling_figures", "player_career_stats"):
        print(f"{t:22s}", cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
