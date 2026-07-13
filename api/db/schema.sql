-- ═══════════════════════════════════════════════════════════════════════════
-- Barça Chat Database Schema
-- PostgreSQL 16 + pgvector
-- ═══════════════════════════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─────────────────────────────────────────────────────────────────────────────
-- STRUCTURED TABLES  (served by sql_query tool)
-- ─────────────────────────────────────────────────────────────────────────────

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id          SERIAL PRIMARY KEY,
    api_id      INTEGER UNIQUE,           -- football-data.org team id
    name        VARCHAR(150) NOT NULL,
    short_name  VARCHAR(80),
    tla         VARCHAR(5),
    crest_url   TEXT,
    founded     INTEGER,
    venue       VARCHAR(150)
);

-- Players
CREATE TABLE IF NOT EXISTS players (
    id              SERIAL PRIMARY KEY,
    api_id          INTEGER UNIQUE,       -- football-data.org person id
    team_id         INTEGER REFERENCES teams(id) ON DELETE SET NULL,
    name            VARCHAR(150) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    position        VARCHAR(50),
    nationality     VARCHAR(100),
    date_of_birth   DATE,
    shirt_number    INTEGER,
    contract_until  DATE
);

-- Competitions (La Liga, UCL, Copa del Rey, etc.)
CREATE TABLE IF NOT EXISTS competitions (
    id          SERIAL PRIMARY KEY,
    api_id      INTEGER UNIQUE,           -- football-data.org competition id
    code        VARCHAR(10),              -- e.g. 'PD' for La Liga
    name        VARCHAR(150) NOT NULL,
    area        VARCHAR(100),
    season      VARCHAR(10)               -- e.g. '2024/25'
);

-- Matches / Fixtures
CREATE TABLE IF NOT EXISTS matches (
    id              SERIAL PRIMARY KEY,
    api_id          INTEGER UNIQUE,
    competition_id  INTEGER REFERENCES competitions(id),
    season          VARCHAR(10),
    matchday        INTEGER,
    match_date      TIMESTAMPTZ,
    home_team_id    INTEGER REFERENCES teams(id),
    away_team_id    INTEGER REFERENCES teams(id),
    home_score      INTEGER,
    away_score      INTEGER,
    status          VARCHAR(20) DEFAULT 'FINISHED', -- SCHEDULED|LIVE|PAUSED|FINISHED|POSTPONED
    stage           VARCHAR(50),
    source          VARCHAR(20) DEFAULT 'football-data' -- 'openfootball' | 'football-data'
);

-- La Liga / Competition Standings (snapshot, refreshed nightly)
CREATE TABLE IF NOT EXISTS standings (
    id              SERIAL PRIMARY KEY,
    competition_id  INTEGER REFERENCES competitions(id),
    season          VARCHAR(10),
    team_id         INTEGER REFERENCES teams(id),
    position        INTEGER,
    played_games    INTEGER,
    won             INTEGER,
    draw            INTEGER,
    lost            INTEGER,
    goals_for       INTEGER,
    goals_against   INTEGER,
    goal_difference INTEGER,
    points          INTEGER,
    form            VARCHAR(25),      -- e.g. 'W,W,D,L,W'
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (competition_id, season, team_id)
);

-- Player Season Statistics
CREATE TABLE IF NOT EXISTS player_stats (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER REFERENCES players(id),
    competition_id  INTEGER REFERENCES competitions(id),
    season          VARCHAR(10),
    goals           INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    appearances     INTEGER DEFAULT 0,
    minutes_played  INTEGER DEFAULT 0,
    yellow_cards    INTEGER DEFAULT 0,
    red_cards       INTEGER DEFAULT 0,
    UNIQUE (player_id, competition_id, season)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- RAG / KNOWLEDGE BASE  (served by barca_knowledge tool)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          SERIAL PRIMARY KEY,
    source_file VARCHAR(200),
    chunk_index INTEGER,
    content     TEXT NOT NULL,
    -- Gemini dimensions
    embedding   vector(3072),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- No index for embeddings since dimension > 2000. Exact search is fast enough for small data.

-- ─────────────────────────────────────────────────────────────────────────────
-- Helpful indexes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS matches_home_team_idx  ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS matches_away_team_idx  ON matches(away_team_id);
CREATE INDEX IF NOT EXISTS matches_date_idx       ON matches(match_date DESC);
CREATE INDEX IF NOT EXISTS matches_comp_idx       ON matches(competition_id);
CREATE INDEX IF NOT EXISTS players_team_idx       ON players(team_id);
CREATE INDEX IF NOT EXISTS standings_comp_idx     ON standings(competition_id, season);
CREATE INDEX IF NOT EXISTS player_stats_player_idx ON player_stats(player_id);
