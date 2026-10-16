-- Cricbuzz LiveStats database schema (SQLite-compatible)

CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY,
    team_name   TEXT NOT NULL,
    short_name  TEXT,
    country     TEXT
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id    INTEGER PRIMARY KEY,
    venue_name  TEXT NOT NULL,
    city        TEXT,
    country     TEXT,
    capacity    INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    player_id     INTEGER PRIMARY KEY,
    full_name     TEXT NOT NULL,
    country       TEXT,
    playing_role  TEXT,      -- Batsman / Bowler / All-rounder / Wicket-keeper
    batting_style TEXT,
    bowling_style TEXT
);

CREATE TABLE IF NOT EXISTS series (
    series_id      INTEGER PRIMARY KEY,
    series_name    TEXT NOT NULL,
    host_country   TEXT,
    match_type     TEXT,     -- Test / ODI / T20I
    start_date     DATE,
    end_date       DATE,
    total_matches  INTEGER
);

CREATE TABLE IF NOT EXISTS matches (
    match_id        INTEGER PRIMARY KEY,
    series_id       INTEGER REFERENCES series(series_id),
    match_desc      TEXT,
    match_format    TEXT,    -- TEST / ODI / T20
    team1_id        INTEGER REFERENCES teams(team_id),
    team2_id        INTEGER REFERENCES teams(team_id),
    venue_id        INTEGER REFERENCES venues(venue_id),
    match_date      DATE,
    state           TEXT,    -- Complete / In Progress / Upcoming
    status_text     TEXT,
    toss_winner_id  INTEGER REFERENCES teams(team_id),
    toss_decision   TEXT,    -- bat / bowl
    winner_id       INTEGER REFERENCES teams(team_id),
    victory_margin  INTEGER,
    victory_type    TEXT     -- runs / wickets
);

CREATE TABLE IF NOT EXISTS batting_scores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id         INTEGER REFERENCES matches(match_id),
    player_id        INTEGER REFERENCES players(player_id),
    team_id          INTEGER REFERENCES teams(team_id),
    innings_no       INTEGER,
    batting_position INTEGER,
    runs             INTEGER,
    balls            INTEGER,
    fours            INTEGER,
    sixes            INTEGER,
    strike_rate      REAL,
    is_out           INTEGER   -- 1 = out, 0 = not out
);

CREATE TABLE IF NOT EXISTS bowling_figures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER REFERENCES matches(match_id),
    player_id   INTEGER REFERENCES players(player_id),
    team_id     INTEGER REFERENCES teams(team_id),
    innings_no  INTEGER,
    overs       REAL,
    maidens     INTEGER,
    runs_given  INTEGER,
    wickets     INTEGER,
    economy     REAL
);

CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id       INTEGER REFERENCES players(player_id),
    format          TEXT,     -- Test / ODI / T20I
    matches         INTEGER,
    innings         INTEGER,
    runs            INTEGER,
    highest_score   INTEGER,
    batting_average REAL,
    strike_rate     REAL,
    hundreds        INTEGER,
    fifties         INTEGER,
    wickets         INTEGER,
    bowling_average REAL,
    economy         REAL,
    catches         INTEGER,
    stumpings       INTEGER,
    PRIMARY KEY (player_id, format)
);

-- Team innings totals (incl. extras), filled by import_cricsheet.py
CREATE TABLE IF NOT EXISTS innings_summary (
    match_id    INTEGER REFERENCES matches(match_id),
    innings_no  INTEGER,
    team_id     INTEGER REFERENCES teams(team_id),
    runs        INTEGER,
    wickets     INTEGER,
    balls       INTEGER,
    PRIMARY KEY (match_id, innings_no)
);

-- Indexes on columns the analytics queries filter/join on
CREATE INDEX IF NOT EXISTS idx_matches_date    ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_bat_player      ON batting_scores(player_id);
CREATE INDEX IF NOT EXISTS idx_bat_match       ON batting_scores(match_id);
CREATE INDEX IF NOT EXISTS idx_bowl_player     ON bowling_figures(player_id);
CREATE INDEX IF NOT EXISTS idx_players_country ON players(country);
CREATE INDEX IF NOT EXISTS idx_matches_venue  ON matches(venue_id);
CREATE INDEX IF NOT EXISTS idx_bowl_match     ON bowling_figures(match_id);
