# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""ETL: pull matches from the Cricbuzz API and load them into the database."""
import re
from datetime import datetime, timezone

from utils.api_client import fetch
from utils.db_connection import get_connection, init_db


def ms_to_date(ms):
    """Convert a Cricbuzz millisecond timestamp string to 'YYYY-MM-DD'."""
    if not ms:
        return None
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_result(status, team1, team2):
    """Extract (winner_id, margin, victory_type) from text like
    'India won by 45 runs' or 'Bulgaria Women won by 2 wkts'."""
    m = re.match(r"(.+?) won by (\d+) (run|wkt|wicket)", status or "")
    if not m:
        return None, None, None
    name, margin, kind = m.group(1).strip(), int(m.group(2)), m.group(3)
    winner = None
    for t in (team1, team2):
        if t["teamName"] == name or t.get("teamSName") == name:
            winner = t["teamId"]
    return winner, margin, "runs" if kind == "run" else "wickets"


def iter_matches(data):
    """Yield every matchInfo dict from a matches/v1/* response."""
    for type_block in (data or {}).get("typeMatches", []):
        for sm in type_block.get("seriesMatches", []):
            wrapper = sm.get("seriesAdWrapper")
            if wrapper:
                for match in wrapper.get("matches", []):
                    yield match["matchInfo"]


def load_matches(endpoint):
    """Fetch an endpoint and upsert teams, venues, series and matches."""
    data = fetch(endpoint)
    count = 0
    with get_connection() as conn:
        for info in iter_matches(data):
            t1, t2, v = info["team1"], info["team2"], info.get("venueInfo", {})
            for t in (t1, t2):
                conn.execute(
                    "INSERT OR IGNORE INTO teams (team_id, team_name, short_name) VALUES (?,?,?)",
                    (t["teamId"], t["teamName"], t.get("teamSName")))
            if v.get("id"):
                conn.execute(
                    "INSERT OR IGNORE INTO venues (venue_id, venue_name, city) VALUES (?,?,?)",
                    (v["id"], v.get("ground"), v.get("city")))
            conn.execute(
                """INSERT OR IGNORE INTO series (series_id, series_name, match_type, start_date, end_date)
                   VALUES (?,?,?,?,?)""",
                (info["seriesId"], info["seriesName"], info.get("matchFormat"),
                 ms_to_date(info.get("seriesStartDt")), ms_to_date(info.get("seriesEndDt"))))
            winner, margin, vtype = parse_result(info.get("status"), t1, t2)
            conn.execute(
                """INSERT OR REPLACE INTO matches
                   (match_id, series_id, match_desc, match_format, team1_id, team2_id, venue_id,
                    match_date, state, status_text, winner_id, victory_margin, victory_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (info["matchId"], info["seriesId"], info.get("matchDesc"), info.get("matchFormat"),
                 t1["teamId"], t2["teamId"], v.get("id"), ms_to_date(info.get("startDate")),
                 info.get("state"), info.get("status"), winner, margin, vtype))
            count += 1
        conn.commit()
    print(f"{endpoint}: loaded {count} matches")


def to_float(x):
    """Safely convert API strings like '3.5' to float."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_scorecard(conn, match_id, team1_id, team2_id):
    """Fetch one match scorecard and insert players, batting and bowling rows."""
    card = fetch(f"mcenter/v1/{match_id}/hscard", max_age=86400 * 30)
    if not card or not card.get("scorecard"):
        return False
    names = {r[0]: r[1] for r in conn.execute(
        "SELECT team_name, team_id FROM teams WHERE team_id IN (?,?)", (team1_id, team2_id))}
    names = {k: v for k, v in names.items()}
    for inn in card["scorecard"]:
        inn_no = inn.get("inningsid")
        bat_team = names.get(inn.get("batteamname"))
        bowl_team = team2_id if bat_team == team1_id else team1_id
        for pos, b in enumerate(inn.get("batsman", []), start=1):
            if not b.get("balls") and not b.get("runs") and not b.get("outdec"):
                continue  # did not bat
            conn.execute("INSERT OR IGNORE INTO players (player_id, full_name) VALUES (?,?)",
                         (b["id"], b["name"]))
            conn.execute(
                """INSERT INTO batting_scores (match_id, player_id, team_id, innings_no,
                   batting_position, runs, balls, fours, sixes, strike_rate, is_out)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (match_id, b["id"], bat_team, inn_no, pos, b.get("runs", 0), b.get("balls", 0),
                 b.get("fours", 0), b.get("sixes", 0), to_float(b.get("strkrate")),
                 0 if (b.get("outdec") or "").startswith("not out") else 1))
        for bw in inn.get("bowler", []):
            conn.execute("INSERT OR IGNORE INTO players (player_id, full_name) VALUES (?,?)",
                         (bw["id"], bw["name"]))
            conn.execute(
                """INSERT INTO bowling_figures (match_id, player_id, team_id, innings_no,
                   overs, maidens, runs_given, wickets, economy)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (match_id, bw["id"], bowl_team, inn_no, to_float(bw.get("overs")),
                 bw.get("maidens", 0), bw.get("runs", 0), bw.get("wickets", 0),
                 to_float(bw.get("economy"))))
    return True


def load_scorecards(limit=25):
    """Load scorecards for completed matches that don't have one yet.

    `limit` caps API calls per run to protect the free-tier quota.
    """
    with get_connection() as conn:
        todo = conn.execute(
            """SELECT match_id, team1_id, team2_id FROM matches
               WHERE state = 'Complete'
                 AND match_id NOT IN (SELECT DISTINCT match_id FROM batting_scores)
               ORDER BY match_date DESC LIMIT ?""", (limit,)).fetchall()
        done = 0
        for match_id, t1, t2 in todo:
            if load_scorecard(conn, match_id, t1, t2):
                done += 1
                conn.commit()
    print(f"Scorecards loaded: {done}/{len(todo)}")


def table_to_dict(data):
    """Turn Cricbuzz's {'headers': [...], 'values': [...]} career table into
    {'Test': {'Runs': '9230', ...}, 'ODI': {...}, 'T20': {...}}."""
    if not data or "headers" not in data:
        return {}
    formats = data["headers"][1:]
    out = {f: {} for f in formats}
    for row in data.get("values", []):
        label, *vals = row["values"]
        for f, v in zip(formats, vals):
            out[f][label] = v
    return out


def num(x, cast=float):
    """Convert '46.85' / '-' / None safely to a number (or None)."""
    try:
        return cast(x)
    except (TypeError, ValueError):
        return None


FORMAT_MAP = {"Test": "Test", "ODI": "ODI", "T20": "T20I"}  # ignore IPL


def load_player(conn, player_id):
    """Fetch profile + career batting/bowling for one player and save them."""
    prof = fetch(f"stats/v1/player/{player_id}", max_age=86400 * 30)
    if not prof:
        return False
    conn.execute(
        """UPDATE players SET full_name=?, country=?, playing_role=?,
           batting_style=?, bowling_style=? WHERE player_id=?""",
        (prof.get("name"), prof.get("intlTeam"), prof.get("role"),
         prof.get("bat"), prof.get("bowl"), player_id))
    bat = table_to_dict(fetch(f"stats/v1/player/{player_id}/batting", max_age=86400 * 30))
    bowl = table_to_dict(fetch(f"stats/v1/player/{player_id}/bowling", max_age=86400 * 30))
    for api_fmt, fmt in FORMAT_MAP.items():
        b, w = bat.get(api_fmt, {}), bowl.get(api_fmt, {})
        if not num(b.get("Matches"), int):
            continue  # never played this format
        conn.execute(
            """INSERT OR REPLACE INTO player_career_stats VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (player_id, fmt, num(b.get("Matches"), int), num(b.get("Innings"), int),
             num(b.get("Runs"), int), num(b.get("Highest"), int), num(b.get("Average")),
             num(b.get("SR")), num(b.get("100s"), int), num(b.get("50s"), int),
             num(w.get("Wickets"), int), num(w.get("Avg")), num(w.get("Eco")),
             None, None))  # catches/stumpings not in this endpoint
    return True


def load_players(limit=30):
    """Enrich players with no profile yet, most-appearing players first.
    Uses 3 API calls per player, so `limit` protects the free quota."""
    with get_connection() as conn:
        todo = [r[0] for r in conn.execute(
            """SELECT p.player_id FROM players p
               LEFT JOIN batting_scores b ON b.player_id = p.player_id
               WHERE p.playing_role IS NULL
               GROUP BY p.player_id ORDER BY COUNT(b.id) DESC LIMIT ?""", (limit,))]
        done = 0
        for pid in todo:
            if load_player(conn, pid):
                done += 1
                conn.commit()
    print(f"Player profiles loaded: {done}/{len(todo)}")


def load_ranked_players():
    """Seed `players` with ICC top-ranked batters, bowlers and all-rounders
    across Test/ODI/T20 (9 API calls). Returns their IDs for priority loading."""
    ids = []
    with get_connection() as conn:
        for cat in ("batsmen", "bowlers", "allrounders"):
            for fmt in ("test", "odi", "t20"):
                data = fetch(f"stats/v1/rankings/{cat}?formatType={fmt}", max_age=86400 * 7)
                rows = (data or {}).get("rank", [])
                for r in rows[:25]:
                    pid = num(r.get("id"), int)
                    if not pid:
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO players (player_id, full_name, country) VALUES (?,?,?)",
                        (pid, r.get("name"), r.get("country")))
                    ids.append(pid)
        conn.commit()
    ids = list(dict.fromkeys(ids))  # de-duplicate, keep order
    print(f"Ranked players seeded: {len(ids)}")
    return ids


def load_players_by_id(player_ids, limit=40):
    """Load full profiles for specific players that don't have one yet."""
    with get_connection() as conn:
        todo = [pid for pid in player_ids if conn.execute(
            "SELECT 1 FROM players WHERE player_id=? AND playing_role IS NULL", (pid,)).fetchone()][:limit]
        done = sum(1 for pid in todo if load_player(conn, pid) and not conn.commit())
    print(f"Ranked player profiles loaded: {done}/{len(todo)}")


if __name__ == "__main__":
    init_db()
    for ep in ("matches/v1/live", "matches/v1/recent", "matches/v1/upcoming"):
        load_matches(ep)
    load_scorecards(limit=25)
    ranked = load_ranked_players()
    load_players_by_id(ranked, limit=40)
