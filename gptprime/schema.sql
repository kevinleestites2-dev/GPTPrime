-- GPTPrime v2.0 Database Schema
-- Single source of truth for the Pantheon persistent memory

-- Every agent execution is a session
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    task        TEXT NOT NULL,
    status      TEXT DEFAULT 'running',   -- running | completed | failed
    started_at  REAL NOT NULL,
    ended_at    REAL,
    score       REAL,                     -- SAFLA-G score (0.0 - 1.0)
    metadata    TEXT DEFAULT '{}'
);

-- Raw input/output pairs per session
CREATE TABLE IF NOT EXISTS exchanges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    agent       TEXT NOT NULL,
    role        TEXT NOT NULL,            -- user | assistant | tool
    content     TEXT NOT NULL,
    tokens      INTEGER DEFAULT 0,
    cost_usd    REAL DEFAULT 0.0,
    ts          REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Distilled facts — what agents learned, persists forever
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,            -- which agent produced this
    domain      TEXT NOT NULL,            -- research | code | ops | finance | general
    fact        TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,         -- 0.0 - 1.0
    source_session TEXT,
    created_at  REAL NOT NULL,
    accessed_at REAL,
    access_count INTEGER DEFAULT 0,
    keywords    TEXT DEFAULT ''           -- space-separated for search
);

-- Agent performance over time
CREATE TABLE IF NOT EXISTS agent_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    task_type   TEXT NOT NULL,
    score       REAL NOT NULL,
    cycles      INTEGER DEFAULT 1,
    ts          REAL NOT NULL
);

-- World state — key/value store for shared agent context
CREATE TABLE IF NOT EXISTS world_state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_by  TEXT NOT NULL,
    updated_at  REAL NOT NULL
);

-- Tasks Queue (for POST /inject)
CREATE TABLE IF NOT EXISTS tasks_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    task        TEXT NOT NULL,
    status      TEXT DEFAULT 'pending', -- pending | processing | completed | failed
    created_at  REAL NOT NULL,
    metadata    TEXT DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_agent  ON sessions(agent);
CREATE INDEX IF NOT EXISTS idx_exchanges_sess  ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_facts_domain    ON facts(domain);
CREATE INDEX IF NOT EXISTS idx_facts_agent     ON facts(agent);
CREATE INDEX IF NOT EXISTS idx_scores_agent    ON agent_scores(agent);
CREATE INDEX IF NOT EXISTS idx_queue_status    ON tasks_queue(status);
