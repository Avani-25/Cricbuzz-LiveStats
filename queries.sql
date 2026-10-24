-- Cricbuzz LiveStats: 25 analytical queries (SQLite)

-- Q01 [Beginner] Players who represent India
SELECT full_name, playing_role, batting_style, bowling_style
FROM players
WHERE country = 'India'
ORDER BY full_name;

-- Q02 [Beginner] Matches played in the last 30 days
SELECT m.match_desc,
       t1.team_name AS team1,
       t2.team_name AS team2,
       v.venue_name,
       v.city,
       m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.match_date >= date('now', '-30 day')
  AND m.match_date <= date('now')
ORDER BY m.match_date DESC, m.match_id DESC;

-- Q03 [Beginner] Top 10 ODI run scorers
SELECT p.full_name,
       c.runs AS total_runs,
       c.batting_avg,
       c.centuries
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.format = 'ODI'
ORDER BY c.runs DESC
LIMIT 10;

-- Q04 [Beginner] Venues with capacity above 50,000
SELECT venue_name, city, country, capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC;

-- Q05 [Beginner] Total wins per team
SELECT t.team_name, COUNT(*) AS total_wins
FROM matches m
JOIN teams t ON t.team_id = m.winner_id
WHERE m.winner_id IS NOT NULL
GROUP BY t.team_id, t.team_name
ORDER BY total_wins DESC, t.team_name;

-- Q06 [Beginner] Players per playing role
SELECT playing_role, COUNT(*) AS player_count
FROM players
WHERE playing_role IS NOT NULL
GROUP BY playing_role
ORDER BY player_count DESC;

-- Q07 [Beginner] Highest individual score in each format
SELECT format, MAX(highest_score) AS highest_score
FROM player_career_stats
GROUP BY format
ORDER BY CASE format WHEN 'Test' THEN 1 WHEN 'ODI' THEN 2 ELSE 3 END;

-- Q08 [Beginner] Series that started in 2024
SELECT series_name, host_country, match_type, start_date, total_matches
FROM series
WHERE start_date >= '2024-01-01' AND start_date < '2025-01-01'
ORDER BY start_date;

-- Q09 [Intermediate] All-rounders with 1000+ runs and 50+ wickets
SELECT p.full_name,
       c.runs    AS total_runs,
       c.wickets AS total_wickets,
       c.format
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE p.playing_role = 'All-rounder'
  AND c.runs > 1000
  AND c.wickets > 50
ORDER BY c.runs DESC;

-- Q10 [Intermediate] Last 20 completed matches
SELECT m.match_desc,
       t1.team_name AS team1,
       t2.team_name AS team2,
       w.team_name  AS winning_team,
       m.victory_margin,
       m.victory_type,
       v.venue_name,
       m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
LEFT JOIN teams w  ON w.team_id = m.winner_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.state = 'Complete'
ORDER BY m.match_date DESC, m.match_id DESC
LIMIT 20;

-- Q11 [Intermediate] Runs by format and overall batting average (players in 2+ formats)
SELECT p.full_name,
       SUM(CASE WHEN c.format = 'Test' THEN c.runs END) AS test_runs,
       SUM(CASE WHEN c.format = 'ODI'  THEN c.runs END) AS odi_runs,
       SUM(CASE WHEN c.format = 'T20I' THEN c.runs END) AS t20i_runs,
       -- combined average = total runs / total dismissals (dismissals = runs / avg)
       ROUND(SUM(CASE WHEN c.batting_avg > 0 THEN c.runs END) * 1.0
             / SUM(CASE WHEN c.batting_avg > 0 THEN c.runs * 1.0 / c.batting_avg END), 2)
             AS overall_batting_avg
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.player_id IN (SELECT player_id
                      FROM player_career_stats
                      GROUP BY player_id
                      HAVING COUNT(DISTINCT format) >= 2)
GROUP BY p.player_id, p.full_name
ORDER BY overall_batting_avg DESC;

-- Q12 [Intermediate] Home vs away performance by team
WITH team_matches AS (
    SELECT team1_id AS team_id, match_id, venue_id, winner_id FROM matches
    WHERE state = 'Complete'
    UNION ALL
    SELECT team2_id, match_id, venue_id, winner_id FROM matches
    WHERE state = 'Complete'
)
SELECT t.team_name,
       SUM(CASE WHEN v.country = t.country THEN 1 ELSE 0 END) AS home_played,
       SUM(CASE WHEN v.country = t.country AND tm.winner_id = t.team_id THEN 1 ELSE 0 END) AS home_wins,
       SUM(CASE WHEN v.country <> t.country THEN 1 ELSE 0 END) AS away_played,
       SUM(CASE WHEN v.country <> t.country AND tm.winner_id = t.team_id THEN 1 ELSE 0 END) AS away_wins
FROM team_matches tm
JOIN teams t  ON t.team_id  = tm.team_id
JOIN venues v ON v.venue_id = tm.venue_id
WHERE t.country IS NOT NULL AND v.country IS NOT NULL
GROUP BY t.team_id, t.team_name
ORDER BY home_wins + away_wins DESC;

-- Q13 [Intermediate] Batting partnerships of 100+ (consecutive batters)
SELECT pa.full_name AS batter_1,
       pb.full_name AS batter_2,
       a.runs + b.runs AS partnership_runs,
       a.innings_no,
       m.match_desc,
       m.match_date
FROM batting_performances a
JOIN batting_performances b
  ON  b.match_id = a.match_id
  AND b.innings_no = a.innings_no
  AND b.batting_position = a.batting_position + 1
JOIN players pa ON pa.player_id = a.player_id
JOIN players pb ON pb.player_id = b.player_id
JOIN matches m  ON m.match_id = a.match_id
WHERE a.runs + b.runs >= 100
ORDER BY partnership_runs DESC, m.match_date DESC;

-- Q14 [Intermediate] Bowling at venues (3+ matches, 4+ overs each)
SELECT p.full_name,
       v.venue_name,
       COUNT(DISTINCT b.match_id)   AS matches_played,
       ROUND(AVG(b.economy_rate), 2) AS avg_economy,
       SUM(b.wickets)                AS total_wickets
FROM bowling_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN venues v  ON v.venue_id = m.venue_id
JOIN players p ON p.player_id = b.player_id
WHERE b.overs >= 4
GROUP BY b.player_id, m.venue_id
HAVING COUNT(DISTINCT b.match_id) >= 3
ORDER BY avg_economy ASC, total_wickets DESC;

-- Q15 [Intermediate] Batters in close matches
-- close = won by < 50 runs OR by < 5 wickets
WITH close_matches AS (
    SELECT match_id, winner_id
    FROM matches
    WHERE (victory_type = 'runs'    AND victory_margin < 50)
       OR (victory_type = 'wickets' AND victory_margin < 5)
)
SELECT p.full_name,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       COUNT(DISTINCT b.match_id) AS close_matches_played,
       COUNT(DISTINCT CASE WHEN cm.winner_id = b.team_id THEN b.match_id END) AS close_matches_won
FROM batting_performances b
JOIN close_matches cm ON cm.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY b.player_id, p.full_name
ORDER BY avg_runs DESC;

-- Q16 [Intermediate] Yearly batting trend since 2020 (5+ matches per year)
SELECT p.full_name,
       substr(m.match_date, 1, 4) AS year,
       COUNT(DISTINCT b.match_id) AS matches_played,
       ROUND(SUM(b.runs) * 1.0 / COUNT(DISTINCT b.match_id), 2) AS avg_runs_per_match,
       ROUND(AVG(b.strike_rate), 2) AS avg_strike_rate
FROM batting_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2020-01-01'
GROUP BY b.player_id, p.full_name, year
HAVING COUNT(DISTINCT b.match_id) >= 5
ORDER BY p.full_name, year;

-- Q17 [Advanced] Does winning the toss help?
WITH decided AS (
    SELECT toss_decision, toss_winner_id, winner_id
    FROM matches
    WHERE toss_winner_id IS NOT NULL
      AND toss_decision  IS NOT NULL
      AND winner_id      IS NOT NULL
),
by_decision AS (
    SELECT toss_decision AS decision,
           COUNT(*) AS matches,
           SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) AS toss_winner_won
    FROM decided
    GROUP BY toss_decision
    UNION ALL
    SELECT 'overall', COUNT(*),
           SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END)
    FROM decided
)
SELECT decision, matches, toss_winner_won,
       ROUND(100.0 * toss_winner_won / matches, 2) AS win_pct
FROM by_decision
ORDER BY CASE decision WHEN 'bat' THEN 1 WHEN 'bowl' THEN 2 ELSE 3 END;

-- Q18 [Advanced] Most economical limited-overs bowlers
-- overs are stored as 3.4 = 3 overs 4 balls, so convert to true overs first
WITH spells AS (
    SELECT bp.player_id, bp.match_id, bp.runs_conceded, bp.wickets,
           CAST(bp.overs AS INTEGER)
             + (bp.overs - CAST(bp.overs AS INTEGER)) * 10.0 / 6 AS true_overs
    FROM bowling_performances bp
    JOIN matches m ON m.match_id = bp.match_id
    WHERE m.match_format IN ('ODI', 'T20I', 'T20')
)
SELECT p.full_name,
       COUNT(DISTINCT s.match_id)                      AS matches_bowled,
       ROUND(SUM(s.true_overs), 1)                     AS total_overs,
       SUM(s.wickets)                                  AS total_wickets,
       ROUND(SUM(s.runs_conceded) / SUM(s.true_overs), 2) AS economy_rate
FROM spells s
JOIN players p ON p.player_id = s.player_id
GROUP BY s.player_id, p.full_name
HAVING COUNT(DISTINCT s.match_id) >= 10
   AND SUM(s.true_overs) / COUNT(DISTINCT s.match_id) >= 2
ORDER BY economy_rate ASC;

-- Q19 [Advanced] Batting consistency since 2022
-- at least 5 innings are required so the standard deviation means something
SELECT p.full_name,
       COUNT(*)                  AS innings,
       ROUND(AVG(b.runs), 2)     AS avg_runs,
       ROUND(STDDEV(b.runs), 2)  AS std_dev_runs
FROM batting_performances b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2022-01-01'
  AND b.balls_faced >= 10
GROUP BY b.player_id, p.full_name
HAVING COUNT(*) >= 5
ORDER BY std_dev_runs ASC;

-- Q20 [Advanced] Matches and batting average by format (20+ matches)
SELECT p.full_name,
       SUM(CASE WHEN c.format = 'Test' THEN c.matches END) AS test_matches,
       SUM(CASE WHEN c.format = 'ODI'  THEN c.matches END) AS odi_matches,
       SUM(CASE WHEN c.format = 'T20I' THEN c.matches END) AS t20_matches,
       MAX(CASE WHEN c.format = 'Test' THEN c.batting_avg END) AS test_avg,
       MAX(CASE WHEN c.format = 'ODI'  THEN c.batting_avg END) AS odi_avg,
       MAX(CASE WHEN c.format = 'T20I' THEN c.batting_avg END) AS t20_avg
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
GROUP BY c.player_id, p.full_name
HAVING SUM(c.matches) >= 20
ORDER BY SUM(c.matches) DESC;

-- Q21 [Advanced] Weighted performance ranking (top 10 per format)
WITH scored AS (
    SELECT c.player_id, c.format,
           c.runs * 0.01 + COALESCE(c.batting_avg, 0) * 0.5
             + COALESCE(c.strike_rate, 0) * 0.3                         AS batting_points,
           CASE WHEN c.wickets > 0
                THEN c.wickets * 2
                     + (50 - COALESCE(c.bowling_avg, 50)) * 0.5
                     + (6  - COALESCE(c.economy_rate, 6)) * 2
                ELSE 0 END                                              AS bowling_points,
           c.catches * 3 + c.stumpings * 5                              AS fielding_points
    FROM player_career_stats c
),
ranked AS (
    SELECT s.*,
           batting_points + bowling_points + fielding_points AS total_points,
           RANK() OVER (PARTITION BY format
                        ORDER BY batting_points + bowling_points + fielding_points DESC) AS rank_in_format
    FROM scored s
)
SELECT r.format, r.rank_in_format AS rank, p.full_name,
       ROUND(r.batting_points, 1)  AS batting_pts,
       ROUND(r.bowling_points, 1)  AS bowling_pts,
       ROUND(r.fielding_points, 1) AS fielding_pts,
       ROUND(r.total_points, 1)    AS total_pts
FROM ranked r
JOIN players p ON p.player_id = r.player_id
WHERE r.rank_in_format <= 10
ORDER BY CASE r.format WHEN 'Test' THEN 1 WHEN 'ODI' THEN 2 ELSE 3 END, r.rank_in_format;

-- Q22 [Advanced] Head-to-head record (pairs with 5+ matches in the last 3 years)
WITH pair_matches AS (
    SELECT MIN(team1_id, team2_id) AS team_a,
           MAX(team1_id, team2_id) AS team_b,
           winner_id, victory_type, victory_margin
    FROM matches
    WHERE state = 'Complete'
      AND match_date >= date('now', '-3 year')
)
SELECT ta.team_name AS team_a,
       tb.team_name AS team_b,
       COUNT(*) AS total_matches,
       SUM(CASE WHEN pm.winner_id = pm.team_a THEN 1 ELSE 0 END) AS wins_a,
       SUM(CASE WHEN pm.winner_id = pm.team_b THEN 1 ELSE 0 END) AS wins_b,
       ROUND(AVG(CASE WHEN pm.winner_id = pm.team_a AND pm.victory_type = 'runs'    THEN pm.victory_margin END), 1) AS a_avg_runs_margin,
       ROUND(AVG(CASE WHEN pm.winner_id = pm.team_a AND pm.victory_type = 'wickets' THEN pm.victory_margin END), 1) AS a_avg_wkts_margin,
       ROUND(AVG(CASE WHEN pm.winner_id = pm.team_b AND pm.victory_type = 'runs'    THEN pm.victory_margin END), 1) AS b_avg_runs_margin,
       ROUND(AVG(CASE WHEN pm.winner_id = pm.team_b AND pm.victory_type = 'wickets' THEN pm.victory_margin END), 1) AS b_avg_wkts_margin,
       ROUND(100.0 * SUM(CASE WHEN pm.winner_id = pm.team_a THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_pct_a,
       ROUND(100.0 * SUM(CASE WHEN pm.winner_id = pm.team_b THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_pct_b
FROM pair_matches pm
JOIN teams ta ON ta.team_id = pm.team_a
JOIN teams tb ON tb.team_id = pm.team_b
GROUP BY pm.team_a, pm.team_b
HAVING COUNT(*) >= 5
ORDER BY total_matches DESC, team_a;

-- Q22B [Advanced] Head-to-head: batting first vs bowling first by venue
WITH oriented AS (
    SELECT m.match_id, m.venue_id, m.winner_id,
           MIN(m.team1_id, m.team2_id) AS team_a,
           MAX(m.team1_id, m.team2_id) AS team_b,
           CASE WHEN m.toss_decision = 'bat' THEN m.toss_winner_id
                WHEN m.toss_winner_id = m.team1_id THEN m.team2_id
                ELSE m.team1_id END AS bat_first_id
    FROM matches m
    WHERE m.state = 'Complete'
      AND m.match_date >= date('now', '-3 year')
      AND m.toss_winner_id IS NOT NULL
      AND m.toss_decision  IS NOT NULL
      AND m.winner_id      IS NOT NULL
),
eligible AS (
    SELECT MIN(team1_id, team2_id) AS team_a,
           MAX(team1_id, team2_id) AS team_b
    FROM matches
    WHERE state = 'Complete' AND match_date >= date('now', '-3 year')
    GROUP BY 1, 2
    HAVING COUNT(*) >= 5
)
SELECT ta.team_name AS team_a, tb.team_name AS team_b, v.venue_name,
       COUNT(*) AS matches,
       SUM(CASE WHEN o.winner_id =  o.bat_first_id THEN 1 ELSE 0 END) AS won_batting_first,
       SUM(CASE WHEN o.winner_id <> o.bat_first_id THEN 1 ELSE 0 END) AS won_bowling_first
FROM oriented o
JOIN eligible e ON e.team_a = o.team_a AND e.team_b = o.team_b
JOIN teams ta ON ta.team_id = o.team_a
JOIN teams tb ON tb.team_id = o.team_b
JOIN venues v ON v.venue_id = o.venue_id
GROUP BY o.team_a, o.team_b, o.venue_id
ORDER BY team_a, team_b, matches DESC;

-- Q23 [Advanced] Recent form: last 10 batting performances
-- Form rules (documented so they can be tuned):
--   Excellent: last-5 average >= 40 AND at least 3 scores above 50 in last 10
--   Good: last-5 average >= 28    Average: >= 18    otherwise Poor
WITH ranked AS (
    SELECT b.player_id, b.runs, b.strike_rate,
           ROW_NUMBER() OVER (PARTITION BY b.player_id
                              ORDER BY m.match_date DESC, m.match_id DESC, b.innings_no DESC) AS rn
    FROM batting_performances b
    JOIN matches m ON m.match_id = b.match_id
    WHERE b.strike_rate IS NOT NULL AND m.match_date IS NOT NULL
),
agg AS (
    SELECT player_id,
           AVG(CASE WHEN rn <= 5 THEN runs END)          AS avg_last5,
           AVG(runs)                                     AS avg_last10,
           AVG(CASE WHEN rn <= 5 THEN strike_rate END)   AS sr_last5,
           AVG(CASE WHEN rn >  5 THEN strike_rate END)   AS sr_prev5,
           SUM(CASE WHEN runs > 50 THEN 1 ELSE 0 END)    AS scores_over_50,
           STDDEV(runs)                                  AS sd_runs
    FROM ranked
    WHERE rn <= 10
    GROUP BY player_id
    HAVING COUNT(*) = 10
)
SELECT p.full_name,
       ROUND(a.avg_last5, 1)  AS avg_last5,
       ROUND(a.avg_last10, 1) AS avg_last10,
       ROUND(a.sr_last5 - a.sr_prev5, 1) AS strike_rate_trend,
       a.scores_over_50,
       ROUND(a.sd_runs, 1) AS std_dev_runs,
       ROUND(a.sd_runs / NULLIF(a.avg_last10, 0), 2) AS variability,
       CASE WHEN a.avg_last5 >= 40 AND a.scores_over_50 >= 3 THEN 'Excellent Form'
            WHEN a.avg_last5 >= 28 THEN 'Good Form'
            WHEN a.avg_last5 >= 18 THEN 'Average Form'
            ELSE 'Poor Form' END AS form
FROM agg a
JOIN players p ON p.player_id = a.player_id
ORDER BY a.avg_last5 DESC;

-- Q24 [Advanced] Best batting partnerships (5+ together)
WITH pairs AS (
    SELECT MIN(a.player_id, b.player_id) AS p1,
           MAX(a.player_id, b.player_id) AS p2,
           a.runs + b.runs AS partnership_runs
    FROM batting_performances a
    JOIN batting_performances b
      ON  b.match_id = a.match_id
      AND b.innings_no = a.innings_no
      AND b.batting_position = a.batting_position + 1
),
agg AS (
    SELECT p1, p2,
           COUNT(*) AS partnerships,
           AVG(partnership_runs) AS avg_runs,
           SUM(CASE WHEN partnership_runs > 50 THEN 1 ELSE 0 END) AS over_50,
           MAX(partnership_runs) AS highest
    FROM pairs
    GROUP BY p1, p2
    HAVING COUNT(*) >= 5
)
SELECT RANK() OVER (ORDER BY 100.0 * over_50 / partnerships DESC, avg_runs DESC) AS rank,
       pa.full_name AS player_1, pb.full_name AS player_2,
       partnerships,
       ROUND(avg_runs, 1) AS avg_partnership,
       over_50 AS partnerships_over_50,
       highest AS highest_partnership,
       ROUND(100.0 * over_50 / partnerships, 1) AS success_rate_pct
FROM agg
JOIN players pa ON pa.player_id = agg.p1
JOIN players pb ON pb.player_id = agg.p2
ORDER BY rank
LIMIT 50;

-- Q25 [Advanced] Career phase from quarterly performance (summary)
-- Looks at each player's most recent 6-8 qualifying quarters (3+ matches each).
-- Newer half vs older half: +10% = ascending, -10% = declining, else stable.
WITH q AS (
    SELECT b.player_id,
           strftime('%Y', m.match_date) || '-Q'
             || ((CAST(strftime('%m', m.match_date) AS INTEGER) + 2) / 3) AS quarter,
           COUNT(DISTINCT b.match_id) AS matches,
           AVG(b.runs)        AS avg_runs,
           AVG(b.strike_rate) AS avg_sr
    FROM batting_performances b
    JOIN matches m ON m.match_id = b.match_id
    WHERE m.match_date IS NOT NULL
    GROUP BY b.player_id, quarter
    HAVING COUNT(DISTINCT b.match_id) >= 3
),
numbered AS (
    SELECT q.*,
           ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY quarter DESC) AS rn_desc,
           COUNT(*)     OVER (PARTITION BY player_id) AS total_quarters
    FROM q
),
recent AS (
    SELECT *, MIN(total_quarters, 8) AS used
    FROM numbered
    WHERE total_quarters >= 6 AND rn_desc <= 8
),
phase AS (
    SELECT player_id, MAX(total_quarters) AS quarters_available, MAX(used) AS quarters_used,
           AVG(CASE WHEN rn_desc <= used / 2 THEN avg_runs END) AS newer_avg_runs,
           AVG(CASE WHEN rn_desc >  used / 2 THEN avg_runs END) AS older_avg_runs,
           AVG(CASE WHEN rn_desc <= used / 2 THEN avg_sr END)   AS newer_avg_sr,
           AVG(CASE WHEN rn_desc >  used / 2 THEN avg_sr END)   AS older_avg_sr
    FROM recent
    GROUP BY player_id
)
SELECT p.full_name, quarters_available, quarters_used,
       ROUND(older_avg_runs, 1) AS older_avg_runs,
       ROUND(newer_avg_runs, 1) AS newer_avg_runs,
       ROUND(older_avg_sr, 1)   AS older_avg_sr,
       ROUND(newer_avg_sr, 1)   AS newer_avg_sr,
       ROUND(100.0 * (newer_avg_runs - older_avg_runs) / NULLIF(older_avg_runs, 0), 1) AS runs_change_pct,
       CASE WHEN newer_avg_runs > older_avg_runs * 1.10 THEN 'Career Ascending'
            WHEN newer_avg_runs < older_avg_runs * 0.90 THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM phase
JOIN players p ON p.player_id = phase.player_id
ORDER BY runs_change_pct DESC;

-- Q25B [Advanced] Quarter-by-quarter detail with change vs previous quarter
WITH q AS (
    SELECT b.player_id,
           strftime('%Y', m.match_date) || '-Q'
             || ((CAST(strftime('%m', m.match_date) AS INTEGER) + 2) / 3) AS quarter,
           COUNT(DISTINCT b.match_id) AS matches,
           AVG(b.runs)        AS avg_runs,
           AVG(b.strike_rate) AS avg_sr
    FROM batting_performances b
    JOIN matches m ON m.match_id = b.match_id
    WHERE m.match_date IS NOT NULL
    GROUP BY b.player_id, quarter
    HAVING COUNT(DISTINCT b.match_id) >= 3
),
eligible AS (
    SELECT player_id FROM q GROUP BY player_id HAVING COUNT(*) >= 6
),
changes AS (
    SELECT q.*,
           LAG(avg_runs) OVER (PARTITION BY player_id ORDER BY quarter) AS prev_avg_runs
    FROM q
    WHERE player_id IN (SELECT player_id FROM eligible)
)
SELECT p.full_name, c.quarter, c.matches,
       ROUND(c.avg_runs, 1) AS avg_runs,
       ROUND(c.avg_sr, 1)   AS avg_strike_rate,
       ROUND(100.0 * (c.avg_runs - c.prev_avg_runs) / NULLIF(c.prev_avg_runs, 0), 1) AS change_pct,
       CASE WHEN c.prev_avg_runs IS NULL THEN 'first quarter'
            WHEN c.avg_runs > c.prev_avg_runs * 1.10 THEN 'improving'
            WHEN c.avg_runs < c.prev_avg_runs * 0.90 THEN 'declining'
            ELSE 'stable' END AS trend
FROM changes c
JOIN players p ON p.player_id = c.player_id
ORDER BY p.full_name, c.quarter;
