#!/usr/bin/env python3
import json
import sqlite3
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.getenv("GPTPRIME_MEMORY_DB", "gptprime/gptprime_memory.db")

AGENT_ROLES = {
    "GPTSwarm": "Self-optimizing swarm graphs",
    "gpt-engineer": "Full codebase generator",
    "AutoGPT": "Mission autonomy",
    "AgentGPT": "Browser-deployed agents",
    "gpt-researcher": "Deep research backbone",
    "OpenAgents": "Data analysis & plugins",
    "MetaGPT": "Multi-role orchestration",
    "swarms": "Enterprise multi-agent swarm",
    "WebGPT": "In-browser GPT inference",
    "crewAI": "Role-playing agent crews",
    "magic": "Command Center OS"
}

class StatusHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def _get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == "/health":
            self._handle_health()
        elif path == "/agents":
            self._handle_agents()
        elif path.startswith("/agents/"):
            agent_name = path.split("/")[-1]
            self._handle_agent_detail(agent_name)
        elif path == "/memory":
            self._handle_memory()
        elif path == "/tools":
            self._handle_tools()
        elif path == "/tasks":
            limit = int(query.get("limit", [20])[0])
            self._handle_tasks(limit)
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _handle_health(self):
        self._set_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "version": "2.0",
            "timestamp": time.time()
        }).encode())

    def _handle_agents(self):
        self._set_headers()
        conn = self._get_db()
        agents_data = []
        try:
            for name, role in AGENT_ROLES.items():
                row_perf = conn.execute(
                    "SELECT COUNT(*) as total, AVG(score) as avg_score FROM agent_scores WHERE agent=?",
                    (name,)
                ).fetchone()
                row_status = conn.execute(
                    "SELECT status, task, started_at FROM sessions WHERE agent=? ORDER BY started_at DESC LIMIT 1",
                    (name,)
                ).fetchone()
                
                agents_data.append({
                    "name": name,
                    "role": role,
                    "status": row_status["status"] if row_status else "idle",
                    "last_task": row_status["task"] if row_status else None,
                    "success_rate": row_perf["avg_score"] if row_perf and row_perf["avg_score"] else 0.0,
                    "total_tasks": row_perf["total"] if row_perf else 0
                })
        except Exception as e:
            print(f"Error fetching agents: {e}")
        finally:
            conn.close()
        self.wfile.write(json.dumps(agents_data).encode())

    def _handle_agent_detail(self, name):
        if name not in AGENT_ROLES:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Agent not found"}).encode())
            return
        
        self._set_headers()
        conn = self._get_db()
        data = {"name": name, "role": AGENT_ROLES[name]}
        try:
            row = conn.execute(
                "SELECT COUNT(*) as total, AVG(score) as avg_score FROM agent_scores WHERE agent=?",
                (name,)
            ).fetchone()
            data["stats"] = {
                "total_tasks": row["total"],
                "avg_score": row["avg_score"]
            }
            tasks = conn.execute(
                "SELECT id, task, status, started_at, score FROM sessions WHERE agent=? ORDER BY started_at DESC LIMIT 10",
                (name,)
            ).fetchall()
            data["recent_tasks"] = [dict(t) for t in tasks]
        finally:
            conn.close()
        self.wfile.write(json.dumps(data).encode())

    def _handle_memory(self):
        self._set_headers()
        conn = self._get_db()
        stats = {}
        try:
            stats["facts_count"] = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            stats["sessions_count"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            stats["db_size_kb"] = os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0
        finally:
            conn.close()
        self.wfile.write(json.dumps(stats).encode())

    def _handle_tools(self):
        self._set_headers()
        conn = self._get_db()
        tool_counts = {}
        try:
            rows = conn.execute("SELECT content FROM exchanges WHERE role='tool'").fetchall()
            for r in rows:
                content = r["content"]
                if content.startswith("[") and "]" in content:
                    name = content[1:content.find("]")]
                    tool_counts[name] = tool_counts.get(name, 0) + 1
        finally:
            conn.close()
        self.wfile.write(json.dumps(tool_counts).encode())

    def _handle_tasks(self, limit):
        self._set_headers()
        conn = self._get_db()
        tasks = []
        try:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            tasks = [dict(r) for r in rows]
        finally:
            conn.close()
        self.wfile.write(json.dumps(tasks).encode())

    def do_POST(self):
        if self.path == "/inject":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                agent = data.get("agent")
                task = data.get("task")
                if not agent or not task:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Missing agent or task"}).encode())
                    return
                
                conn = self._get_db()
                conn.execute(
                    "INSERT INTO tasks_queue (agent, task, created_at) VALUES (?, ?, ?)",
                    (agent, task, time.time())
                )
                conn.commit()
                conn.close()
                
                self._set_headers(201)
                self.wfile.write(json.dumps({"status": "queued", "agent": agent, "task": task}).encode())
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self._set_headers(404)

def run(port=7200):
    server_address = ('', port)
    httpd = HTTPServer(server_address, StatusHandler)
    print(f"GPTPrime Status API running on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
