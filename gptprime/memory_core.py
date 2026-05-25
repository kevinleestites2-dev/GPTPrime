#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              G P T P R I M E  —  M E M O R Y  C O R E          ║
║              Persistent Long-Term Memory Layer                   ║
╠══════════════════════════════════════════════════════════════════╣
║  What this does:                                                 ║
║    - SQLite-backed persistent memory shared across all 11 agents ║
║    - Stores: sessions, tasks, outputs, agent performance, facts  ║
║    - Semantic search via keyword index (no external API needed)  ║
║    - Auto-summarizes old sessions to stay lean                   ║
║    - Thread-safe — multiple agents read/write simultaneously     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import time
import threading
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────
DB_PATH      = os.getenv("GPTPRIME_MEMORY_DB", "gptprime/gptprime_memory.db")
MAX_RAW_DAYS = int(os.getenv("MEMORY_RAW_RETENTION_DAYS", "7"))   # raw logs kept 7 days
MAX_FACTS    = int(os.getenv("MEMORY_MAX_FACTS", "10000"))         # max distilled facts

_lock = threading.Lock()


# ── Schema ────────────────────────────────────────────────────────
SCHEMA = """
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_agent  ON sessions(agent);
CREATE INDEX IF NOT EXISTS idx_exchanges_sess  ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS idx_facts_domain    ON facts(domain);
CREATE INDEX IF NOT EXISTS idx_facts_agent     ON facts(agent);
CREATE INDEX IF NOT EXISTS idx_scores_agent    ON agent_scores(agent);
"""


# ── Core ──────────────────────────────────────────────────────────
class MemoryCore:
    """
    Central memory system for all GPTPrime agents.
    One instance, shared across the process via get_memory().
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent writes
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        with _lock:
            conn = self._conn()
            conn.executescript(SCHEMA)
            conn.commit()
            conn.close()

    # ── Sessions ──────────────────────────────────────────────────

    def start_session(self, agent: str, task: str, metadata: dict = None) -> str:
        """Open a new agent session. Returns session_id."""
        sid = hashlib.sha256(f"{agent}{task}{time.time()}".encode()).hexdigest()[:16]
        with _lock:
            conn = self._conn()
            conn.execute(
                "INSERT INTO sessions (id, agent, task, status, started_at, metadata) VALUES (?,?,?,?,?,?)",
                (sid, agent, task, "running", time.time(), json.dumps(metadata or {}))
            )
            conn.commit()
            conn.close()
        return sid

    def end_session(self, session_id: str, status: str = "completed", score: float = None):
        """Close a session with optional SAFLA-G score."""
        with _lock:
            conn = self._conn()
            conn.execute(
                "UPDATE sessions SET status=?, ended_at=?, score=? WHERE id=?",
                (status, time.time(), score, session_id)
            )
            conn.commit()
            conn.close()

    def get_session(self, session_id: str) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── Exchanges ─────────────────────────────────────────────────

    def log_exchange(self, session_id: str, agent: str, role: str,
                     content: str, tokens: int = 0, cost_usd: float = 0.0):
        """Log a single message/exchange within a session."""
        with _lock:
            conn = self._conn()
            conn.execute(
                "INSERT INTO exchanges (session_id, agent, role, content, tokens, cost_usd, ts) VALUES (?,?,?,?,?,?,?)",
                (session_id, agent, role, content, tokens, cost_usd, time.time())
            )
            conn.commit()
            conn.close()

    def get_session_history(self, session_id: str) -> List[Dict]:
        """Get full exchange history for a session."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM exchanges WHERE session_id=? ORDER BY ts ASC", (session_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_agent_recent_history(self, agent: str, limit: int = 20) -> List[Dict]:
        """Get the N most recent exchanges for an agent across all sessions."""
        conn = self._conn()
        rows = conn.execute(
            """SELECT e.* FROM exchanges e
               JOIN sessions s ON e.session_id = s.id
               WHERE s.agent=? ORDER BY e.ts DESC LIMIT ?""",
            (agent, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in reversed(rows)]

    # ── Facts ─────────────────────────────────────────────────────

    def store_fact(self, agent: str, domain: str, fact: str,
                   confidence: float = 1.0, source_session: str = None) -> int:
        """Distill and store a fact for long-term memory."""
        keywords = " ".join(set(
            w.lower() for w in fact.split() if len(w) > 3
        ))
        with _lock:
            conn = self._conn()
            cursor = conn.execute(
                """INSERT INTO facts (agent, domain, fact, confidence, source_session, created_at, keywords)
                   VALUES (?,?,?,?,?,?,?)""",
                (agent, domain, fact, confidence, source_session, time.time(), keywords)
            )
            fid = cursor.lastrowid
            conn.commit()
            conn.close()
        self._prune_facts()
        return fid

    def search_facts(self, query: str, domain: str = None, limit: int = 10) -> List[Dict]:
        """Keyword search over stored facts."""
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        if not keywords:
            return []

        conditions = " OR ".join(["keywords LIKE ?" for _ in keywords])
        params = [f"%{k}%" for k in keywords]

        if domain:
            conditions = f"({conditions}) AND domain=?"
            params.append(domain)

        params.append(limit)

        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM facts WHERE {conditions} ORDER BY confidence DESC, access_count DESC LIMIT ?",
            params
        ).fetchall()

        # Update access stats
        if rows:
            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE facts SET accessed_at=?, access_count=access_count+1 WHERE id IN ({','.join('?'*len(ids))})",
                [time.time()] + ids
            )
            conn.commit()
        conn.close()
        return [dict(r) for r in rows]

    def get_facts_by_agent(self, agent: str, limit: int = 50) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM facts WHERE agent=? ORDER BY created_at DESC LIMIT ?",
            (agent, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _prune_facts(self):
        """Keep facts table lean — remove lowest confidence if over limit."""
        conn = self._conn()
        count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        if count > MAX_FACTS:
            excess = count - MAX_FACTS
            conn.execute(
                """DELETE FROM facts WHERE id IN (
                   SELECT id FROM facts ORDER BY confidence ASC, access_count ASC LIMIT ?)""",
                (excess,)
            )
            conn.commit()
        conn.close()

    # ── Agent Scores ──────────────────────────────────────────────

    def record_score(self, agent: str, task_type: str, score: float):
        """Record a SAFLA-G performance score for an agent."""
        with _lock:
            conn = self._conn()
            conn.execute(
                "INSERT INTO agent_scores (agent, task_type, score, ts) VALUES (?,?,?,?)",
                (agent, task_type, score, time.time())
            )
            conn.commit()
            conn.close()

    def get_agent_avg_score(self, agent: str, days: int = 7) -> Optional[float]:
        """Average score for an agent over the last N days."""
        since = time.time() - (days * 86400)
        conn = self._conn()
        row = conn.execute(
            "SELECT AVG(score) as avg FROM agent_scores WHERE agent=? AND ts > ?",
            (agent, since)
        ).fetchone()
        conn.close()
        return row["avg"] if row and row["avg"] is not None else None

    def get_best_agent_for_task(self, task_type: str) -> Optional[str]:
        """Returns the agent with the highest avg score for a given task type."""
        conn = self._conn()
        row = conn.execute(
            """SELECT agent, AVG(score) as avg_score
               FROM agent_scores WHERE task_type=?
               GROUP BY agent ORDER BY avg_score DESC LIMIT 1""",
            (task_type,)
        ).fetchone()
        conn.close()
        return row["agent"] if row else None

    def get_leaderboard(self) -> List[Dict]:
        """All agents ranked by overall average score."""
        conn = self._conn()
        rows = conn.execute(
            """SELECT agent, AVG(score) as avg_score, COUNT(*) as total_tasks
               FROM agent_scores GROUP BY agent ORDER BY avg_score DESC"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── World State ───────────────────────────────────────────────

    def set_state(self, key: str, value: Any, updated_by: str = "system"):
        """Set a shared world state value."""
        with _lock:
            conn = self._conn()
            conn.execute(
                """INSERT INTO world_state (key, value, updated_by, updated_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                   updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
                (key, json.dumps(value), updated_by, time.time())
            )
            conn.commit()
            conn.close()

    def get_state(self, key: str, default=None) -> Any:
        """Get a shared world state value."""
        conn = self._conn()
        row = conn.execute("SELECT value FROM world_state WHERE key=?", (key,)).fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
        return default

    def get_all_state(self) -> Dict[str, Any]:
        """Dump full world state."""
        conn = self._conn()
        rows = conn.execute("SELECT key, value FROM world_state").fetchall()
        conn.close()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    # ── Maintenance ───────────────────────────────────────────────

    def prune_old_exchanges(self):
        """Delete raw exchanges older than MAX_RAW_DAYS."""
        cutoff = time.time() - (MAX_RAW_DAYS * 86400)
        with _lock:
            conn = self._conn()
            deleted = conn.execute(
                "DELETE FROM exchanges WHERE ts < ?", (cutoff,)
            ).rowcount
            conn.commit()
            conn.close()
        return deleted

    def stats(self) -> Dict:
        """Return memory system stats."""
        conn = self._conn()
        stats = {
            "sessions_total":   conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "sessions_running": conn.execute("SELECT COUNT(*) FROM sessions WHERE status='running'").fetchone()[0],
            "exchanges_total":  conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0],
            "facts_total":      conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
            "world_state_keys": conn.execute("SELECT COUNT(*) FROM world_state").fetchone()[0],
            "agents_tracked":   conn.execute("SELECT COUNT(DISTINCT agent) FROM agent_scores").fetchone()[0],
            "db_path":          self.db_path,
        }
        conn.close()
        return stats


# ── Singleton ─────────────────────────────────────────────────────
_memory_instance: Optional[MemoryCore] = None

def get_memory(db_path: str = DB_PATH) -> MemoryCore:
    """Get or create the global MemoryCore instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryCore(db_path)
    return _memory_instance


# ── CLI test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🧠 MemoryCore — Boot Test")
    mem = get_memory()

    # Session test
    sid = mem.start_session("gpt-researcher", "Research Lee County auction trends")
    mem.log_exchange(sid, "gpt-researcher", "user", "What are the top auction opportunities in Lee County?", tokens=15, cost_usd=0.0001)
    mem.log_exchange(sid, "gpt-researcher", "assistant", "Based on recent data, the top ZIP codes are...", tokens=120, cost_usd=0.0008)
    mem.end_session(sid, status="completed", score=0.87)

    # Fact test
    mem.store_fact("gpt-researcher", "research", "Lee County ZIP 33903 has avg spread of $150k on foreclosures", confidence=0.9, source_session=sid)
    mem.store_fact("crewai", "ops", "Telegram bot token must be set in env before deploy", confidence=1.0)

    # Score test
    mem.record_score("gpt-researcher", "research", 0.87)
    mem.record_score("crewai", "ops", 0.91)
    mem.record_score("MetaGPT", "code", 0.78)

    # World state test
    mem.set_state("gptprime_version", "2.0.0", updated_by="system")
    mem.set_state("last_cycle", {"ts": time.time(), "agent": "gpt-researcher"}, updated_by="gpt-researcher")

    # Search test
    results = mem.search_facts("Lee County auction")
    print(f"\n🔍 Fact search 'Lee County auction': {len(results)} result(s)")
    for r in results:
        print(f"   [{r['domain']}] {r['fact'][:80]}...")

    # Leaderboard
    print(f"\n🏆 Agent Leaderboard:")
    for entry in mem.get_leaderboard():
        print(f"   {entry['agent']:20s} avg={entry['avg_score']:.2f}  tasks={entry['total_tasks']}")

    # Stats
    print(f"\n📊 Memory Stats:")
    for k, v in mem.stats().items():
        print(f"   {k}: {v}")

    print("\n✅ MemoryCore online.")
