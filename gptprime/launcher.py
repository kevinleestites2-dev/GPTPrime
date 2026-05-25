import os
import sys
import time
import json
import threading
import signal
from datetime import datetime
from typing import Dict, List, Any, Optional

# Local imports
from gptprime.config import CONFIG, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from gptprime.memory_core import get_memory
from gptprime.tool_forge import get_forge

# Banner Constant
BANNER = """
╔══════════════════════════════════════════════════╗
║   G P T P R I M E  v 2 . 0  —  S T R I K E      ║
║   11-Agent Autonomous Strike Team                 ║
║   Memory: ONLINE | Tools: ONLINE | Bus: ONLINE   ║
╚══════════════════════════════════════════════════╝
"""

class Launcher:
    def __init__(self):
        self.memory = None
        self.forge = None
        self.bus = None
        self.worker = None
        self.status_api = None
        self.agents = {}
        self.running = True

    def initialize(self):
        print(BANNER)
        
        # 1. Initialize MemoryCore
        print("Initializing MemoryCore...")
        self.memory = get_memory()
        
        # 2. Initialize ToolForge
        print("Initializing ToolForge...")
        self.forge = get_forge()
        
        # 3. Initialize CommandBus (Guard with try/except)
        try:
            from gptprime.command_bus import CommandBus
            print("Initializing CommandBus...")
            self.bus = CommandBus()
        except ImportError:
            print("⚠️ CommandBus module not found. Skipping...")
        except Exception as e:
            print(f"❌ Error initializing CommandBus: {e}")

        # 4. Start BusWorker daemon thread (Guard with try/except)
        try:
            from gptprime.bus_worker import BusWorker
            if self.bus:
                print("Starting BusWorker...")
                self.worker = BusWorker(self.bus)
                self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
                self.worker_thread.start()
        except ImportError:
            if self.bus: print("⚠️ BusWorker module not found. Skipping...")
        except Exception as e:
            print(f"❌ Error starting BusWorker: {e}")

        # 5. Start StatusAPI in a background thread (Guard with try/except)
        try:
            from gptprime.status_api import StatusAPI
            print(f"Starting StatusAPI on port {CONFIG['STATUS_API_PORT']}...")
            self.status_api = StatusAPI(port=CONFIG['STATUS_API_PORT'])
            self.api_thread = threading.Thread(target=self.status_api.run, daemon=True)
            self.api_thread.start()
        except ImportError:
            print("⚠️ StatusAPI module not found. Skipping...")
        except Exception as e:
            print(f"❌ Error starting StatusAPI: {e}")

        # 6. Instantiate all 11 agents (Guard with try/except)
        try:
            from gptprime.agents import AGENT_REGISTRY
            print("Instantiating agents...")
            for name, agent_cls in AGENT_REGISTRY.items():
                try:
                    agent_instance = agent_cls(memory=self.memory, forge=self.forge)
                    self.agents[name] = agent_instance
                    # Subscribe each agent to the CommandBus
                    if self.bus and hasattr(agent_instance, 'default_topics'):
                        for topic in agent_instance.default_topics:
                            self.bus.subscribe(topic, agent_instance.on_message)
                except Exception as ae:
                    print(f"  ❌ Failed to load agent {name}: {ae}")
        except ImportError:
            print("⚠️ gptprime.agents module not found. Agents not loaded.")
        except Exception as e:
            print(f"❌ Error loading agents: {e}")

        # 7. Telegram startup notification
        self.notify_startup()

        # 8. Print per-agent status table
        self.print_status_table()

    def notify_startup(self):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🚀 GPTPrime v2.0 ONLINE — {len(self.agents)} agents loaded — {timestamp}"
        if TELEGRAM_BOT_TOKEN:
            try:
                import requests
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
            except Exception as e:
                print(f"⚠️ Failed to send Telegram notification: {e}")
        else:
            print(f"📢 Notification: {msg}")

    def print_status_table(self):
        print("\nAGENT STATUS")
        print(f"{'Name':<20} | {'Role':<30} | {'Topics':<20} | {'Status'}")
        print("-" * 85)
        if not self.agents:
            print("No agents loaded.")
        for name, agent in self.agents.items():
            role = getattr(agent, 'role', 'Unknown')
            topics = ",".join(getattr(agent, 'default_topics', []))
            status = "READY"
            print(f"{name:<20} | {role[:30]:<30} | {topics[:20]:<20} | {status}")
        print("\n")

    def shutdown(self):
        print("\nShutting down GPTPrime v2.0...")
        self.running = False
        
        # Telegram shutdown notice
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"🛑 GPTPrime v2.0 SHUTDOWN — {timestamp}"
        if TELEGRAM_BOT_TOKEN:
            try:
                import requests
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
            except: pass
        
        # Close DB connections if necessary
        # MemoryCore uses local connections per thread/call, so no global close needed here 
        # unless get_memory() instance needs cleanup.
        
        print("Goodbye.")
        sys.exit(0)

    def run_cli(self):
        while self.running:
            try:
                cmd_line = input("GPTPrime> ").strip()
                if not cmd_line: continue
                
                parts = cmd_line.split()
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd == "exit":
                    self.shutdown()
                elif cmd == "help":
                    self.print_help()
                elif cmd == "status":
                    self.print_status_table()
                elif cmd == "agents":
                    self.list_agents()
                elif cmd == "tools":
                    self.list_tools()
                elif cmd == "memory":
                    self.search_memory(args)
                elif cmd == "run":
                    self.run_agent(args)
                elif cmd == "broadcast":
                    self.broadcast_task(args)
                elif cmd == "inject":
                    self.inject_bus(args)
                elif cmd == "pipeline":
                    self.run_pipeline(args)
                else:
                    print(f"Unknown command: {cmd}. Type 'help' for available commands.")
            except KeyboardInterrupt:
                self.shutdown()
            except Exception as e:
                print(f"Error in CLI: {e}")

    def print_help(self):
        print("""
AVAILABLE COMMANDS:
  run <agent> <task>      — Run a specific agent with a task
  broadcast <task>        — Send task to ALL agents, collect results
  pipeline <t1>:<p1> -> <t2>:<p2> — Run a chained pipeline
  status                  — Print live status table
  memory <query>          — Search memory for query
  tools                   — List all available tools
  agents                  — List all 11 agents with roles and stats
  inject <json>           — Publish raw message to CommandBus
  help                    — Print this help
  exit                    — Graceful shutdown
""")

    def list_agents(self):
        print("\nSTRIKE TEAM AGENTS")
        for name, agent in self.agents.items():
            print(f"  [{name}] {getattr(agent, 'role', 'No role defined')}")
        if not self.agents:
            print("  No agents loaded.")

    def list_tools(self):
        tools = self.forge.list_tools()
        print("\nAVAILABLE TOOLS")
        for t in tools:
            print(f"  - {t['name']}: {t['description']}")

    def search_memory(self, args):
        if not args:
            print("Usage: memory <query>")
            return
        query = " ".join(args)
        results = self.memory.search_facts(query, limit=5)
        print(f"\nMemory search results for '{query}':")
        for r in results:
            print(f"  [{r['domain']}] {r['fact']}")
        if not results:
            print("  No results found.")

    def run_agent(self, args):
        if len(args) < 2:
            print("Usage: run <agent> <task>")
            return
        agent_name = args[0]
        task = " ".join(args[1:])
        if agent_name not in self.agents:
            print(f"Agent '{agent_name}' not found.")
            return
        
        agent = self.agents[agent_name]
        print(f"Running {agent_name}...")
        try:
            # Assuming agents have a 'run' method
            if hasattr(agent, 'run'):
                result = agent.run(task)
                print(f"Result: {result}")
            else:
                print(f"Agent {agent_name} does not have a 'run' method.")
        except Exception as e:
            print(f"Error running agent: {e}")

    def broadcast_task(self, args):
        if not args:
            print("Usage: broadcast <task>")
            return
        task = " ".join(args)
        print(f"Broadcasting task to {len(self.agents)} agents...")
        for name, agent in self.agents.items():
            if hasattr(agent, 'run'):
                print(f"[{name}] Starting...")
                # In a real scenario, this might be async/threaded
                try:
                    res = agent.run(task)
                    print(f"[{name}] Result: {res}")
                except Exception as e:
                    print(f"[{name}] Error: {e}")

    def inject_bus(self, args):
        if not self.bus:
            print("CommandBus not initialized.")
            return
        if not args:
            print("Usage: inject <json>")
            return
        try:
            data = json.loads(" ".join(args))
            topic = data.get("topic", "general")
            payload = data.get("payload", {})
            self.bus.publish(topic, payload)
            print(f"Injected into topic '{topic}'")
        except Exception as e:
            print(f"Error injecting into bus: {e}")

    def run_pipeline(self, args):
        if not args:
            print("Usage: pipeline <topic1>:<payload1> -> <topic2>:<payload2> -> ...")
            return
        # Basic implementation of pipeline logic
        raw_pipe = " ".join(args)
        stages = [s.strip() for s in raw_pipe.split("->")]
        print(f"Executing pipeline with {len(stages)} stages...")
        # Pipeline logic would typically use the Bus or a sequencer
        print("Pipeline execution logic not fully implemented yet.")

def main():
    launcher = Launcher()
    launcher.initialize()
    launcher.run_cli()

if __name__ == "__main__":
    main()
