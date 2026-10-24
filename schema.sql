PRAGMA foreign_keys = ON;

-- ---------- Reference tables ----------
CREATE TABLE IF NOT EXISTS teams (
    team_id     INTEGER PRIMARY KEY,
    team_name   TEXT NOT NULL UNIQUE,
    short_name  TEXT,
    country     TEXT
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id    INTEGER PRIMARY KEY,
    venue_name  TEXT NOT NULL,
    city        TEXT,
    country     TEXT,
    capacity    INTEGER CHECK (capacity IS NULL OR capacity > 0)
);

CREATE TABLE IF NOT EXISTS series (
    series_id      INTEGER PRIMARY KEY,
    series_name    TEXT NOT NULL,
    host_country   TEXT,
    match_type     TEXT,          -- Test / ODI / T20I / mixed
    start_date     TEXT,          -- ISO date: YYYY-MM-DD
    total_matches  INTEGER CHECK (total_matches IS NULL OR total_matches >= 0)
);

CREATE TABLE IF NOT EXISTS players (
    player_id      INTEGER PRIMARY KEY,
    full_name      TEXT NOT NULL,
    country        TEXT,
    playing_role   TEXT,          -- Batsman / Bowler / All-rounder / Wicket-keeper
    batting_style  TEXT,
    bowling_style  TEXT
);

-- ---------- Matches ----------
CREATE TABLE IF NOT EXISTS matches (
    match_id        INTEGER PRIMARY KEY,
    series_id       INTEGER REFERENCES series(series_id),
    match_desc      TEXT,
    match_format    TEXT,          -- Test / ODI / T20I / T20
    match_date      TEXT,          -- ISO date
    team1_id        INTEGER NOT NULL REFERENCES teams(team_id),
    team2_id        INTEGER NOT NULL REFERENCES teams(team_id),
    venue_id        INTEGER REFERENCES venues(venue_id),
    toss_winner_id  INTEGER REFERENCES teams(team_id),
    toss_decision   TEXT CHECK (toss_decision IS NULL OR toss_decision IN ('bat', 'bowl')),
    winner_id       INTEGER REFERENCES teams(team_id),
    victory_margin  INTEGER CHECK (victory_margin IS NULL OR victory_margin >= 0),
    victory_type    TEXT CHECK (victory_type IS NULL OR victory_type IN ('runs', 'wickets', 'tie', 'no result')),
    state           TEXT,          -- Complete / In Progress / Delay ...
    CHECK (team1_id <> team2_id)
);

-- ---------- Career statistics ----------
CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id      INTEGER NOT NULL REFERENCES players(player_id),
    format         TEXT NOT NULL CHECK (format IN ('Test', 'ODI', 'T20I')),
    matches        INTEGER DEFAULT 0,
    innings        INTEGER DEFAULT 0,
    runs           INTEGER DEFAULT 0,
    highest_score  INTEGER DEFAULT 0,
    batting_avg    REAL,
    strike_rate    REAL,
    centuries      INTEGER DEFAULT 0,
    fifties        INTEGER DEFAULT 0,
    wickets        INTEGER DEFAULT 0,
    bowling_avg    REAL,
    economy_rate   REAL,
    catches        INTEGER DEFAULT 0,
    stumpings      INTEGER DEFAULT 0,
    PRIMARY KEY (player_id, format)
);

-- ---------- Per-match performances ----------
CREATE TABLE IF NOT EXISTS batting_performances (
    perf_id          INTEGER PRIMARY KEY,
    match_id         INTEGER NOT NULL REFERENCES matches(match_id),
    player_id        INTEGER NOT NULL REFERENCES players(player_id),
    team_id          INTEGER REFERENCES teams(team_id),
    innings_no       INTEGER NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    batting_position INTEGER CHECK (batting_position BETWEEN 1 AND 11),
    runs             INTEGER NOT NULL DEFAULT 0 CHECK (runs >= 0),
    balls_faced      INTEGER NOT NULL DEFAULT 0 CHECK (balls_faced >= 0),
    fours            INTEGER DEFAULT 0,
    sixes            INTEGER DEFAULT 0,
    strike_rate      REAL,
    is_out           INTEGER DEFAULT 1 CHECK (is_out IN (0, 1)),
    UNIQUE (match_id, player_id, innings_no)
);

CREATE TABLE IF NOT EXISTS bowling_performances (
    perf_id        INTEGER PRIMARY KEY,
    match_id       INTEGER NOT NULL REFERENCES matches(match_id),
    player_id      INTEGER NOT NULL REFERENCES players(player_id),
    team_id        INTEGER REFERENCES teams(team_id),
    innings_no     INTEGER NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    overs          REAL NOT NULL DEFAULT 0 CHECK (overs >= 0),
    maidens        INTEGER DEFAULT 0,
    runs_conceded  INTEGER NOT NULL DEFAULT 0 CHECK (runs_conceded >= 0),
    wickets        INTEGER NOT NULL DEFAULT 0 CHECK (wickets BETWEEN 0 AND 10),
    economy_rate   REAL,
    UNIQUE (match_id, player_id, innings_no)
);

-- ---------- Indexes (on columns used in JOIN / WHERE / GROUP BY) ----------
CREATE INDEX IF NOT EXISTS idx_players_country    ON players(country);
CREATE INDEX IF NOT EXISTS idx_players_role       ON players(playing_role);
CREATE INDEX IF NOT EXISTS idx_matches_date       ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_winner     ON matches(winner_id);
CREATE INDEX IF NOT EXISTS idx_matches_venue      ON matches(venue_id);
CREATE INDEX IF NOT EXISTS idx_matches_series     ON matches(series_id);
CREATE INDEX IF NOT EXISTS idx_series_start       ON series(start_date);
CREATE INDEX IF NOT EXISTS idx_bat_match          ON batting_performances(match_id);
CREATE INDEX IF NOT EXISTS idx_bat_player         ON batting_performances(player_id);
CREATE INDEX IF NOT EXISTS idx_bowl_match         ON bowling_performances(match_id);
CREATE INDEX IF NOT EXISTS idx_bowl_player        ON bowling_performances(player_id);


