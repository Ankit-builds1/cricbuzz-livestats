"""Fantasy XI engine: expected points per player + optimal team selection.

Points (Dream11-style, simplified):
  batting  : 1/run, +1 per four, +2 per six, +8 for 50, +16 for 100, -2 for a duck
  bowling  : 25/wicket, +4 for 3W, +8 for 5W, +12 per maiden (ODI/T20)
  fielding : 8/catch, 12/stumping (career rate per match)
Selection is solved exactly as an integer linear program (scipy.optimize.milp).
"""
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

ROLE_LIMITS = {"WK": (1, 4), "BAT": (3, 6), "AR": (1, 4), "BOWL": (3, 6)}


def role_group(role):
    r = (role or "").lower()
    if "wk" in r or "wicket" in r:
        return "WK"
    if "allrounder" in r or "all-rounder" in r:
        return "AR"
    if "bowl" in r:
        return "BOWL"
    return "BAT"


def player_pool(run_query, team_ids, fmt, recent_years=2, per_team=16):
    """Recent players for each team in a format, with expected fantasy points."""
    ph = ",".join("?" * len(team_ids))
    df = run_query(f"""
        WITH recent AS (
            SELECT match_id, match_date FROM matches
            WHERE match_format = ? AND match_date >= DATE((SELECT MAX(match_date) FROM matches
                                                           WHERE match_format = ?), ?)),
        appear AS (
            SELECT player_id, team_id, match_id FROM batting_scores WHERE team_id IN ({ph})
            UNION SELECT player_id, team_id, match_id FROM bowling_figures WHERE team_id IN ({ph}))
        SELECT a.player_id, a.team_id, COUNT(DISTINCT a.match_id) AS recent_matches,
               MAX(r.match_date) AS last_played
        FROM appear a JOIN recent r USING (match_id)
        GROUP BY a.player_id, a.team_id HAVING recent_matches >= 3""",
        (fmt, fmt, f"-{recent_years} years", *team_ids, *team_ids))
    if df.empty:
        return df
    df = (df.sort_values(["team_id", "recent_matches", "last_played"], ascending=[True, False, False])
            .groupby("team_id").head(per_team))
    ids = ",".join(str(int(x)) for x in df.player_id)

    last10 = run_query(f"""
        WITH pm AS (
            SELECT DISTINCT b.player_id, b.match_id, m.match_date FROM (
                SELECT player_id, match_id FROM batting_scores WHERE player_id IN ({ids})
                UNION SELECT player_id, match_id FROM bowling_figures WHERE player_id IN ({ids})) b
            JOIN matches m USING (match_id) WHERE m.match_format = ?),
        ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY match_date DESC) rn FROM pm),
        bat AS (SELECT player_id, match_id, SUM(runs) runs, SUM(fours) f, SUM(sixes) s,
                       SUM(CASE WHEN runs >= 100 THEN 16 WHEN runs >= 50 THEN 8 ELSE 0 END) bonus,
                       SUM(CASE WHEN runs = 0 AND is_out = 1 THEN -2 ELSE 0 END) duck
                FROM batting_scores WHERE player_id IN ({ids}) GROUP BY 1, 2),
        bowl AS (SELECT player_id, match_id, SUM(wickets) w, SUM(maidens) md,
                        SUM(CASE WHEN wickets >= 5 THEN 8 WHEN wickets >= 3 THEN 4 ELSE 0 END) wb
                 FROM bowling_figures WHERE player_id IN ({ids}) GROUP BY 1, 2)
        SELECT r.player_id, COUNT(*) AS games,
               AVG(COALESCE(bat.runs, 0)) AS avg_runs, AVG(COALESCE(bowl.w, 0)) AS avg_wkts,
               AVG(COALESCE(bat.runs + bat.f + 2 * bat.s + bat.bonus + bat.duck, 0)) AS bat_pts,
               AVG(COALESCE(25 * bowl.w + bowl.wb + CASE WHEN ? = 'TEST' THEN 0 ELSE 12 * bowl.md END, 0)) AS bowl_pts
        FROM ranked r
        LEFT JOIN bat USING (player_id, match_id) LEFT JOIN bowl USING (player_id, match_id)
        WHERE r.rn <= 10 GROUP BY r.player_id""", (fmt, fmt))
    label = {"TEST": "Test", "ODI": "ODI", "T20": "T20I"}[fmt]
    field = run_query(f"""
        SELECT player_id, 1.0 * (8 * COALESCE(catches, 0) + 12 * COALESCE(stumpings, 0))
                          / NULLIF(matches, 0) AS field_pts
        FROM player_career_stats WHERE format = ? AND player_id IN ({ids})""", (label,))
    info = run_query(f"""SELECT p.player_id, p.full_name, p.playing_role, t.team_name, t.team_id
                         FROM players p, teams t WHERE p.player_id IN ({ids})""")
    df = (df.merge(last10, on="player_id", how="left")
            .merge(field, on="player_id", how="left")
            .merge(info, on=["player_id", "team_id"], how="left"))
    df = df.fillna({"bat_pts": 0, "bowl_pts": 0, "field_pts": 0, "avg_runs": 0, "avg_wkts": 0})
    df["exp_points"] = (df.bat_pts + df.bowl_pts + df.field_pts).round(1)
    df["role"] = df.playing_role.map(role_group)
    # bowlers who rarely bowl but bat a lot get reclassified, and vice versa
    df.loc[(df.role == "BOWL") & (df.avg_wkts < 0.3) & (df.avg_runs > 20), "role"] = "BAT"
    df.loc[(df.role == "BAT") & (df.avg_wkts >= 1.0), "role"] = "AR"
    # credits 7.0-10.5 scaled by expected points (stars cost more)
    pts = df.exp_points
    rank = pts.rank(pct=True)
    df["credits"] = (7 + 3.5 * rank).round(1).clip(7, 10.5)
    return df.sort_values("exp_points", ascending=False).reset_index(drop=True)


def best_xi(pool, budget=100.0, max_per_team=7):
    """Pick the 11 maximising expected points under fantasy rules (exact MILP)."""
    n = len(pool)
    c = -pool.exp_points.values                         # maximise points
    rows, lo, hi = [np.ones(n)], [11], [11]             # exactly 11 players
    rows.append(pool.credits.values); lo.append(0); hi.append(budget)
    for role, (a, b) in ROLE_LIMITS.items():
        rows.append((pool.role == role).astype(float).values); lo.append(a); hi.append(b)
    for t in pool.team_id.unique():
        rows.append((pool.team_id == t).astype(float).values); lo.append(1); hi.append(max_per_team)
    res = milp(c, constraints=LinearConstraint(np.array(rows), lo, hi),
               integrality=np.ones(n), bounds=Bounds(0, 1))
    if not res.success:
        return None
    xi = pool[res.x > 0.5].sort_values("exp_points", ascending=False).copy()
    xi["tag"] = ""
    xi.iloc[0, xi.columns.get_loc("tag")] = "C"
    xi.iloc[1, xi.columns.get_loc("tag")] = "VC"
    xi["proj"] = xi.exp_points * xi.tag.map({"C": 2.0, "VC": 1.5}).fillna(1.0)
    return xi
