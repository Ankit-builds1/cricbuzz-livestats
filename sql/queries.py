# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""The 25 SQL practice questions for the Cricbuzz LiveStats analytics page.

Each entry: (level, question text, SQL). Written for SQLite; the STDDEV
in Q19/Q23 uses SQRT, which utils/db_connection.py registers.
Formats: matches.match_format = 'TEST' | 'ODI' | 'T20';
         player_career_stats.format = 'Test' | 'ODI' | 'T20I'.
"""

QUERIES = [
# ---------------------------------------------------------------- Beginner
("Beginner", "Q1. Players who represent India: full name, role, batting & bowling style.",
"""SELECT full_name, playing_role, batting_style, bowling_style
FROM players
WHERE country = 'India'
ORDER BY full_name;"""),

("Beginner", "Q2. Matches played in the last 30 days (most recent first).",
"""SELECT m.match_desc, t1.team_name AS team1, t2.team_name AS team2,
       v.venue_name || ', ' || COALESCE(v.city, '') AS venue, m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.match_date >= DATE('now', '-30 days') AND m.state = 'Complete'
ORDER BY m.match_date DESC;"""),

("Beginner", "Q3. Top 10 ODI run scorers: runs, average, centuries.",
"""SELECT p.full_name, s.runs AS total_runs, s.batting_average, s.hundreds AS centuries
FROM player_career_stats s
JOIN players p ON p.player_id = s.player_id
WHERE s.format = 'ODI'
ORDER BY s.runs DESC
LIMIT 10;"""),

("Beginner", "Q4. Venues with capacity above 50,000.",
"""SELECT venue_name, city, country, capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC;"""),

("Beginner", "Q5. Number of matches won by each team.",
"""SELECT t.team_name, COUNT(*) AS total_wins
FROM matches m
JOIN teams t ON t.team_id = m.winner_id
GROUP BY t.team_name
ORDER BY total_wins DESC;"""),

("Beginner", "Q6. Number of players in each playing role.",
"""SELECT playing_role, COUNT(*) AS player_count
FROM players
WHERE playing_role IS NOT NULL
GROUP BY playing_role
ORDER BY player_count DESC;"""),

("Beginner", "Q7. Highest individual score in each format.",
"""SELECT format, MAX(highest_score) AS highest_score
FROM player_career_stats
GROUP BY format
ORDER BY highest_score DESC;"""),

("Beginner", "Q8. Series that started in 2024.",
"""SELECT series_name, host_country, match_type, start_date, total_matches
FROM series
WHERE STRFTIME('%Y', start_date) = '2024'
ORDER BY start_date;"""),

# ------------------------------------------------------------ Intermediate
("Intermediate", "Q9. All-rounders with 1000+ runs and 50+ wickets.",
"""SELECT p.full_name, s.runs AS total_runs, s.wickets AS total_wickets, s.format
FROM player_career_stats s
JOIN players p ON p.player_id = s.player_id
WHERE s.runs > 1000 AND s.wickets > 50
ORDER BY s.runs DESC;"""),

("Intermediate", "Q10. Last 20 completed matches with winner and margin.",
"""SELECT m.match_desc, t1.team_name AS team1, t2.team_name AS team2,
       w.team_name AS winner, m.victory_margin, m.victory_type, v.venue_name, m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
JOIN teams w  ON w.team_id  = m.winner_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.state = 'Complete'
ORDER BY m.match_date DESC
LIMIT 20;"""),

("Intermediate", "Q11. Runs by format for players with 2+ formats, plus overall average.",
"""SELECT p.full_name,
       SUM(CASE WHEN s.format = 'Test' THEN s.runs END) AS test_runs,
       SUM(CASE WHEN s.format = 'ODI'  THEN s.runs END) AS odi_runs,
       SUM(CASE WHEN s.format = 'T20I' THEN s.runs END) AS t20i_runs,
       ROUND(AVG(s.batting_average), 2) AS overall_batting_avg
FROM player_career_stats s
JOIN players p ON p.player_id = s.player_id
GROUP BY p.player_id
HAVING COUNT(DISTINCT s.format) >= 2
ORDER BY (COALESCE(test_runs,0) + COALESCE(odi_runs,0) + COALESCE(t20i_runs,0)) DESC;"""),

("Intermediate", "Q12. Team wins at home vs away (venue country = team country).",
"""WITH team_matches AS (
    SELECT m.match_id, m.team1_id AS team_id, m.winner_id, v.country AS venue_country FROM matches m JOIN venues v USING (venue_id)
    UNION ALL
    SELECT m.match_id, m.team2_id, m.winner_id, v.country FROM matches m JOIN venues v USING (venue_id)
)
SELECT t.team_name,
       SUM(CASE WHEN tm.venue_country = t.country  AND tm.winner_id = t.team_id THEN 1 ELSE 0 END) AS home_wins,
       SUM(CASE WHEN tm.venue_country <> t.country AND tm.winner_id = t.team_id THEN 1 ELSE 0 END) AS away_wins
FROM team_matches tm
JOIN teams t ON t.team_id = tm.team_id
WHERE t.country IS NOT NULL
GROUP BY t.team_name
ORDER BY home_wins + away_wins DESC;"""),

("Intermediate", "Q13. Partnerships of 100+ between consecutive batters.",
"""SELECT p1.full_name AS batter_1, p2.full_name AS batter_2,
       a.runs + b.runs AS partnership_runs, a.innings_no AS innings, a.match_id
FROM batting_scores a
JOIN batting_scores b ON b.match_id = a.match_id AND b.innings_no = a.innings_no
                     AND b.batting_position = a.batting_position + 1
JOIN players p1 ON p1.player_id = a.player_id
JOIN players p2 ON p2.player_id = b.player_id
WHERE a.runs + b.runs >= 100
ORDER BY partnership_runs DESC;"""),

("Intermediate", "Q14. Bowlers with 3+ matches at a venue (4+ overs each): economy & wickets.",
"""SELECT p.full_name, v.venue_name,
       COUNT(DISTINCT bf.match_id) AS matches_played,
       SUM(bf.wickets) AS total_wickets,
       ROUND(AVG(bf.economy), 2) AS avg_economy
FROM bowling_figures bf
JOIN matches m ON m.match_id = bf.match_id
JOIN venues v ON v.venue_id = m.venue_id
JOIN players p ON p.player_id = bf.player_id
WHERE bf.overs >= 4
GROUP BY bf.player_id, v.venue_id
HAVING COUNT(DISTINCT bf.match_id) >= 3
ORDER BY avg_economy;"""),

("Intermediate", "Q15. Player performance in close matches (<50 runs or <5 wickets).",
"""WITH close_matches AS (
    SELECT match_id, winner_id FROM matches
    WHERE (victory_type = 'runs' AND victory_margin < 50)
       OR (victory_type = 'wickets' AND victory_margin < 5)
)
SELECT p.full_name,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       COUNT(DISTINCT b.match_id) AS close_matches_played,
       COUNT(DISTINCT CASE WHEN cm.winner_id = b.team_id THEN b.match_id END) AS close_matches_won
FROM batting_scores b
JOIN close_matches cm ON cm.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY b.player_id
HAVING close_matches_played >= 3
ORDER BY avg_runs DESC;"""),

("Intermediate", "Q16. Yearly batting since 2020 (players with 5+ matches that year).",
"""SELECT p.full_name, STRFTIME('%Y', m.match_date) AS year,
       COUNT(DISTINCT b.match_id) AS matches,
       ROUND(1.0 * SUM(b.runs) / COUNT(DISTINCT b.match_id), 2) AS avg_runs_per_match,
       ROUND(AVG(b.strike_rate), 2) AS avg_strike_rate
FROM batting_scores b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2020-01-01'
GROUP BY b.player_id, year
HAVING matches >= 5
ORDER BY p.full_name, year;"""),

# ---------------------------------------------------------------- Advanced
("Advanced", "Q17. Does winning the toss help? Win % by toss decision.",
"""SELECT toss_decision,
       COUNT(*) AS matches,
       SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) AS toss_winner_won,
       ROUND(100.0 * SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) / COUNT(*), 2) AS win_pct
FROM matches
WHERE toss_winner_id IS NOT NULL AND winner_id IS NOT NULL
GROUP BY toss_decision;"""),

("Advanced", "Q18. Most economical bowlers in ODI/T20 (10+ matches, 2+ overs/match).",
"""SELECT p.full_name,
       COUNT(DISTINCT bf.match_id) AS matches,
       SUM(bf.wickets) AS total_wickets,
       ROUND(SUM(bf.runs_given) / SUM(bf.overs), 2) AS economy_rate
FROM bowling_figures bf
JOIN matches m ON m.match_id = bf.match_id
JOIN players p ON p.player_id = bf.player_id
WHERE m.match_format IN ('ODI', 'T20')
GROUP BY bf.player_id
HAVING matches >= 10 AND SUM(bf.overs) / matches >= 2
ORDER BY economy_rate
LIMIT 20;"""),

("Advanced", "Q19. Most consistent batters since 2022 (lowest std-dev, 10+ balls/innings).",
"""SELECT p.full_name,
       COUNT(*) AS innings,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       ROUND(SQRT(AVG(b.runs * b.runs) - AVG(b.runs) * AVG(b.runs)), 2) AS std_dev_runs
FROM batting_scores b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2022-01-01' AND b.balls >= 10
GROUP BY b.player_id
HAVING innings >= 5
ORDER BY std_dev_runs
LIMIT 20;"""),

("Advanced", "Q20. Matches and batting average per format (20+ total matches).",
"""SELECT p.full_name,
       COUNT(DISTINCT CASE WHEN m.match_format = 'TEST' THEN m.match_id END) AS test_matches,
       COUNT(DISTINCT CASE WHEN m.match_format = 'ODI'  THEN m.match_id END) AS odi_matches,
       COUNT(DISTINCT CASE WHEN m.match_format = 'T20'  THEN m.match_id END) AS t20_matches,
       ROUND(1.0 * SUM(CASE WHEN m.match_format='TEST' THEN b.runs END) / NULLIF(SUM(CASE WHEN m.match_format='TEST' THEN b.is_out END), 0), 2) AS test_avg,
       ROUND(1.0 * SUM(CASE WHEN m.match_format='ODI'  THEN b.runs END) / NULLIF(SUM(CASE WHEN m.match_format='ODI'  THEN b.is_out END), 0), 2) AS odi_avg,
       ROUND(1.0 * SUM(CASE WHEN m.match_format='T20'  THEN b.runs END) / NULLIF(SUM(CASE WHEN m.match_format='T20'  THEN b.is_out END), 0), 2) AS t20_avg
FROM batting_scores b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY b.player_id
HAVING COUNT(DISTINCT m.match_id) >= 20
ORDER BY COUNT(DISTINCT m.match_id) DESC;"""),

("Advanced", "Q21. Weighted performance ranking (batting + bowling + fielding) per format.",
"""WITH scores AS (
    SELECT p.full_name, s.format,
           ROUND( COALESCE(s.runs,0) * 0.01 + COALESCE(s.batting_average,0) * 0.5 + COALESCE(s.strike_rate,0) * 0.3, 2) AS batting_pts,
           ROUND( CASE WHEN COALESCE(s.wickets,0) > 0
                       THEN s.wickets * 2 + (50 - s.bowling_average) * 0.5 + (6 - s.economy) * 2
                       ELSE 0 END, 2) AS bowling_pts,
           COALESCE(s.catches,0) * 3 + COALESCE(s.stumpings,0) * 5 AS fielding_pts
    FROM player_career_stats s
    JOIN players p ON p.player_id = s.player_id
)
SELECT * FROM (
    SELECT format, full_name, batting_pts, bowling_pts, fielding_pts,
           ROUND(batting_pts + bowling_pts + fielding_pts, 2) AS total_score,
           RANK() OVER (PARTITION BY format ORDER BY batting_pts + bowling_pts + fielding_pts DESC) AS rank_in_format
    FROM scores
) WHERE rank_in_format <= 10
ORDER BY format, rank_in_format;"""),

("Advanced", "Q22. Head-to-head records (5+ meetings in the last 3 years).",
"""WITH h2h AS (
    SELECT MIN(team1_id, team2_id) AS team_a, MAX(team1_id, team2_id) AS team_b,
           winner_id, victory_margin, victory_type, toss_winner_id, toss_decision
    FROM matches
    WHERE match_date >= DATE('now', '-3 years') AND winner_id IS NOT NULL
)
SELECT ta.team_name AS team_a, tb.team_name AS team_b,
       COUNT(*) AS matches_played,
       SUM(winner_id = team_a) AS team_a_wins,
       SUM(winner_id = team_b) AS team_b_wins,
       ROUND(AVG(CASE WHEN winner_id = team_a THEN victory_margin END), 1) AS team_a_avg_margin,
       ROUND(AVG(CASE WHEN winner_id = team_b THEN victory_margin END), 1) AS team_b_avg_margin,
       SUM(victory_type = 'runs')    AS won_batting_first,
       SUM(victory_type = 'wickets') AS won_chasing,
       ROUND(100.0 * SUM(winner_id = team_a) / COUNT(*), 1) AS team_a_win_pct,
       ROUND(100.0 * SUM(winner_id = team_b) / COUNT(*), 1) AS team_b_win_pct
FROM h2h
JOIN teams ta ON ta.team_id = h2h.team_a
JOIN teams tb ON tb.team_id = h2h.team_b
GROUP BY team_a, team_b
HAVING matches_played >= 5
ORDER BY matches_played DESC;"""),

("Advanced", "Q23. Recent form (last 10 innings) categorised Excellent/Good/Average/Poor.",
"""WITH ranked AS (
    SELECT b.player_id, b.runs, b.strike_rate,
           ROW_NUMBER() OVER (PARTITION BY b.player_id ORDER BY m.match_date DESC, b.innings_no DESC) AS rn
    FROM batting_scores b JOIN matches m ON m.match_id = b.match_id
),
form AS (
    SELECT player_id,
           AVG(CASE WHEN rn <= 5 THEN runs END) AS avg_last5,
           AVG(runs) AS avg_last10,
           AVG(CASE WHEN rn <= 5 THEN strike_rate END) AS sr_last5,
           AVG(strike_rate) AS sr_last10,
           SUM(runs >= 50) AS fifties,
           SQRT(AVG(runs * runs) - AVG(runs) * AVG(runs)) AS std_dev
    FROM ranked WHERE rn <= 10
    GROUP BY player_id HAVING COUNT(*) = 10
)
SELECT p.full_name,
       ROUND(avg_last5, 1) AS avg_last_5, ROUND(avg_last10, 1) AS avg_last_10,
       ROUND(sr_last5, 1) AS sr_last_5, ROUND(sr_last10, 1) AS sr_last_10,
       fifties AS scores_50_plus, ROUND(std_dev, 1) AS consistency_std_dev,
       CASE WHEN avg_last5 >= 40 AND fifties >= 3 THEN 'Excellent Form'
            WHEN avg_last5 >= 25 THEN 'Good Form'
            WHEN avg_last5 >= 15 THEN 'Average Form'
            ELSE 'Poor Form' END AS form_category
FROM form JOIN players p ON p.player_id = form.player_id
ORDER BY avg_last5 DESC;"""),

("Advanced", "Q24. Best batting partnerships (pairs with 5+ partnerships).",
"""WITH pairs AS (
    SELECT MIN(a.player_id, b.player_id) AS p1, MAX(a.player_id, b.player_id) AS p2,
           a.runs + b.runs AS partnership
    FROM batting_scores a
    JOIN batting_scores b ON b.match_id = a.match_id AND b.innings_no = a.innings_no
                         AND b.batting_position = a.batting_position + 1
)
SELECT x.full_name AS batter_1, y.full_name AS batter_2,
       COUNT(*) AS partnerships,
       ROUND(AVG(partnership), 1) AS avg_partnership,
       SUM(partnership > 50) AS fifty_plus,
       MAX(partnership) AS highest,
       ROUND(100.0 * SUM(partnership > 50) / COUNT(*), 1) AS success_rate_pct
FROM pairs
JOIN players x ON x.player_id = pairs.p1
JOIN players y ON y.player_id = pairs.p2
GROUP BY p1, p2
HAVING partnerships >= 5
ORDER BY success_rate_pct DESC, avg_partnership DESC
LIMIT 20;"""),

("Advanced", "Q25. Quarterly performance trend & career phase (6+ quarters, 3+ matches each).",
"""WITH quarterly AS (
    SELECT b.player_id,
           STRFTIME('%Y', m.match_date) || '-Q' || ((CAST(STRFTIME('%m', m.match_date) AS INTEGER) + 2) / 3) AS quarter,
           AVG(b.runs) AS avg_runs, AVG(b.strike_rate) AS avg_sr
    FROM batting_scores b JOIN matches m ON m.match_id = b.match_id
    GROUP BY b.player_id, quarter
    HAVING COUNT(DISTINCT b.match_id) >= 3
),
trend AS (
    SELECT player_id, quarter, avg_runs, avg_sr,
           avg_runs - LAG(avg_runs) OVER (PARTITION BY player_id ORDER BY quarter) AS change
    FROM quarterly
),
summary AS (
    SELECT player_id, COUNT(*) AS quarters,
           ROUND(AVG(avg_runs), 1) AS career_avg_runs,
           ROUND(AVG(avg_sr), 1) AS career_avg_sr,
           SUM(change > 2) AS improving_qtrs,
           SUM(change < -2) AS declining_qtrs,
           SUM(change BETWEEN -2 AND 2) AS stable_qtrs
    FROM trend GROUP BY player_id HAVING quarters >= 6
)
SELECT p.full_name, quarters, career_avg_runs, career_avg_sr,
       improving_qtrs, declining_qtrs, stable_qtrs,
       CASE WHEN improving_qtrs > declining_qtrs + 1 THEN 'Career Ascending'
            WHEN declining_qtrs > improving_qtrs + 1 THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM summary JOIN players p ON p.player_id = summary.player_id
ORDER BY career_avg_runs DESC;"""),
]
