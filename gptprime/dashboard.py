#!/usr/bin/env python3
import os
import sqlite3
import time
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

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

class Dashboard:
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None

    def _get_db_conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_data(self) -> Dict[str, Any]:
        data = {
            "agents": [],
            "memory": {},
            "tools": [],
            "health": {}
        }
        
        if not os.path.exists(DB_PATH):
            return data

        try:
            conn = self._get_db_conn()
            
            # 1. Agent Stats
            # Join sessions and agent_scores to get full picture
            for name, role in AGENT_ROLES.items():
                # Status: Check if any session is 'running'
                row_status = conn.execute(
                    "SELECT status, task, started_at FROM sessions WHERE agent=? ORDER BY started_at DESC LIMIT 1",
                    (name,)
                ).fetchone()
                
                # Completed/Failed counts from agent_scores
                row_perf = conn.execute(
                    "SELECT COUNT(*) as total, AVG(score) as avg_score FROM agent_scores WHERE agent=?",
                    (name,)
                ).fetchone()
                
                # Failed count (score < 0.5 as proxy or if status was failed)
                row_failed = conn.execute(
                    "SELECT COUNT(*) as failed FROM sessions WHERE agent=? AND status='failed'",
                    (name,)
                ).fetchone()
                
                status = "IDLE"
                last_task = "N/A"
                last_active = "N/A"
                if row_status:
                    status = row_status["status"].upper()
                    last_task = row_status["task"]
                    last_active = datetime.fromtimestamp(row_status["started_at"]).strftime("%H:%M:%S")
                
                completed = row_perf["total"] if row_perf else 0
                failed = row_failed["failed"] if row_failed else 0
                avg_score = row_perf["avg_score"] if row_perf and row_perf["avg_score"] else 0.0
                
                data["agents"].append({
                    "name": name,
                    "role": role,
                    "status": status,
                    "last_task": (last_task[:57] + "...") if len(last_task) > 60 else last_task,
                    "completed": completed,
                    "failed": failed,
                    "last_active": last_active,
                    "success_rate": f"{avg_score*100:.1f}%"
                })

            # 2. Memory Stats
            facts_count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            sessions_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            db_size = os.path.getsize(DB_PATH) / 1024
            data["memory"] = {
                "facts": facts_count,
                "sessions": sessions_count,
                "size_kb": round(db_size, 2)
            }

            # 3. Tool Stats
            # Extract tool names from exchanges role='tool' content "[name] ..."
            tool_rows = conn.execute(
                "SELECT content FROM exchanges WHERE role='tool'"
            ).fetchall()
            tool_counts = {}
            for r in tool_rows:
                content = r["content"]
                if content.startswith("[") and "]" in content:
                    tool_name = content[1:content.find("]")]
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            
            top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            data["tools"] = top_tools

            # 4. System Health
            total_tasks = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            avg_system_score = conn.execute("SELECT AVG(score) FROM agent_scores").fetchone()[0] or 0.0
            uptime_row = conn.execute("SELECT MIN(started_at) FROM sessions").fetchone()
            uptime_str = "N/A"
            if uptime_row and uptime_row[0]:
                uptime_sec = time.time() - uptime_row[0]
                h, m = divmod(int(uptime_sec // 60), 60)
                uptime_str = f"{h}h {m}m"

            data["health"] = {
                "uptime": uptime_str,
                "total_tasks": total_tasks,
                "success_rate": f"{avg_system_score*100:.1f}%"
            }

            conn.close()
        except sqlite3.OperationalError:
            # Handle missing tables
            pass
            
        return data

    def render_plain(self, data):
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"=== GPTPrime v2.0 — Strike Team Dashboard | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        print("\nAGENT STATUS")
        print(f"{'Agent':<15} {'Status':<10} {'Success':<8} {'Last Active':<12} {'Task'}")
        print("-" * 80)
        for a in data["agents"]:
            print(f"{a['name']:<15} {a['status']:<10} {a['success_rate']:<8} {a['last_active']:<12} {a['last_task']}")
        
        print(f"\nMEMORY: {data['memory'].get('facts', 0)} facts, {data['memory'].get('sessions', 0)} sessions ({data['memory'].get('size_kb', 0)} KB)")
        print("TOOLS: " + ", ".join([f"{t[0]} ({t[1]})" for t in data["tools"]]))
        print(f"HEALTH: Uptime {data['health'].get('uptime', 'N/A')}, Tasks {data['health'].get('total_tasks', 0)}, Success {data['health'].get('success_rate', '0%')}")

    def generate_rich_layout(self, data) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=7)
        )
        
        # Header
        layout["header"].update(Panel(
            f"[bold cyan]GPTPrime v2.0 — Strike Team Dashboard[/bold cyan] | [white]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/white]",
            box=box.ROUNDED
        ))
        
        # Main Agent Table
        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Agent", style="bold yellow")
        table.add_column("Status")
        table.add_column("Success", justify="right")
        table.add_column("Last Active", justify="center")
        table.add_column("Current/Last Task", ratio=1)
        
        for a in data["agents"]:
            status_color = "green" if a["status"] == "RUNNING" else "white"
            if a["status"] == "ERROR": status_color = "red"
            
            table.add_row(
                a["name"],
                f"[{status_color}]{a['status']}[/{status_color}]",
                a["success_rate"],
                a["last_active"],
                a["last_task"]
            )
        layout["main"].update(table)
        
        # Footer stats
        mem_str = f"🧠 Memory: [bold]{data['memory'].get('facts', 0)}[/bold] facts | [bold]{data['memory'].get('sessions', 0)}[/bold] sessions | [bold]{data['memory'].get('size_kb', 0)}[/bold] KB"
        tool_str = "🛠️ Top Tools: " + " | ".join([f"[cyan]{t[0]}[/cyan] ({t[1]})" for t in data["tools"]])
        health_str = f"🚀 System: Uptime [bold]{data['health'].get('uptime', 'N/A')}[/bold] | Total Tasks [bold]{data['health'].get('total_tasks', 0)}[/bold] | Success [bold green]{data['health'].get('success_rate', '0%')}[/bold green]"
        
        layout["footer"].update(Panel(
            f"{mem_str}\n{tool_str}\n\n{health_str}",
            title="System Stats",
            box=box.ROUNDED
        ))
        
        return layout

    def run(self, once=False):
        if once:
            data = self.fetch_data()
            if RICH_AVAILABLE:
                self.console.print(self.generate_rich_layout(data))
            else:
                self.render_plain(data)
            return

        if RICH_AVAILABLE:
            with Live(self.generate_rich_layout(self.fetch_data()), refresh_per_second=1, screen=True) as live:
                while True:
                    live.update(self.generate_rich_layout(self.fetch_data()))
                    time.sleep(5)
        else:
            while True:
                self.render_plain(self.fetch_data())
                time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPTPrime Dashboard")
    parser.add_argument("--once", action="store_true", help="Print once and exit")
    args = parser.parse_args()
    
    dashboard = Dashboard()
    try:
        dashboard.run(once=args.once)
    except KeyboardInterrupt:
        sys.exit(0)
