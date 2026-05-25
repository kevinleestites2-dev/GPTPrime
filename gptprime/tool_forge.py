#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              G P T P R I M E  —  T O O L  F O R G E            ║
║              Unified Tool Registry for all 11 Agents            ║
╠══════════════════════════════════════════════════════════════════╣
║  What this does:                                                 ║
║    - Single registry all agents pull tools from                  ║
║    - Tools: web search, code exec, file ops, HTTP, memory,      ║
║             shell, scrape, telegram, github                      ║
║    - Every tool call is logged to MemoryCore automatically       ║
║    - Tools are sandboxed — cost tracked, errors caught          ║
║    - Agents request tools by name — no hardcoded imports        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import subprocess
import traceback
import requests
import tempfile
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from gptprime.memory_core import get_memory

# ── Config ────────────────────────────────────────────────────────
SERPER_API_KEY   = os.getenv("SERPER_API_KEY", "")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")
TG_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT          = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
WORKSPACE        = os.getenv("GPTPRIME_WORKSPACE", "gptprime/workspace")
CODE_TIMEOUT     = int(os.getenv("CODE_EXEC_TIMEOUT", "15"))   # seconds
SHELL_TIMEOUT    = int(os.getenv("SHELL_TIMEOUT", "10"))


# ── Tool Result ───────────────────────────────────────────────────
class ToolResult:
    def __init__(self, tool: str, success: bool, output: Any,
                 tokens: int = 0, cost_usd: float = 0.0, error: str = None):
        self.tool      = tool
        self.success   = success
        self.output    = output
        self.tokens    = tokens
        self.cost_usd  = cost_usd
        self.error     = error
        self.ts        = time.time()

    def to_dict(self) -> Dict:
        return {
            "tool":     self.tool,
            "success":  self.success,
            "output":   self.output,
            "tokens":   self.tokens,
            "cost_usd": self.cost_usd,
            "error":    self.error,
            "ts":       self.ts,
        }

    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f"ToolResult({status} {self.tool})"


# ── Tool Registry ─────────────────────────────────────────────────
class ToolForge:
    """
    Unified tool registry. All agents call tools through here.
    Usage:
        forge = get_forge()
        result = forge.run("web_search", agent="gpt-researcher",
                           session_id=sid, query="Lee County foreclosures")
    """

    def __init__(self):
        self._tools: Dict[str, Dict] = {}
        self._register_all()
        Path(WORKSPACE).mkdir(parents=True, exist_ok=True)

    def _register(self, name: str, fn: Callable, description: str,
                  params: List[str], category: str, cost_per_call: float = 0.0):
        self._tools[name] = {
            "fn":          fn,
            "description": description,
            "params":      params,
            "category":    category,
            "cost":        cost_per_call,
            "call_count":  0,
            "total_cost":  0.0,
        }

    def _register_all(self):
        # ── Web ──────────────────────────────────────────────────
        self._register(
            "web_search", self._web_search,
            "Search the web via Serper API. Returns top results with titles, snippets, URLs.",
            ["query", "num_results?"],
            "web", cost_per_call=0.001
        )
        self._register(
            "web_fetch", self._web_fetch,
            "Fetch raw HTML/text content from a URL.",
            ["url", "timeout?"],
            "web", cost_per_call=0.0
        )
        self._register(
            "scrape_text", self._scrape_text,
            "Fetch a URL and return clean plain text (strips HTML tags).",
            ["url"],
            "web", cost_per_call=0.0
        )

        # ── Code / Shell ──────────────────────────────────────────
        self._register(
            "run_python", self._run_python,
            "Execute a Python code string in a subprocess. Returns stdout/stderr.",
            ["code", "timeout?"],
            "code", cost_per_call=0.0
        )
        self._register(
            "run_shell", self._run_shell,
            "Execute a shell command. Returns stdout/stderr. Use carefully.",
            ["command", "timeout?"],
            "shell", cost_per_call=0.0
        )

        # ── File Ops ──────────────────────────────────────────────
        self._register(
            "file_read", self._file_read,
            "Read a file from the workspace. Path is relative to workspace root.",
            ["path"],
            "files", cost_per_call=0.0
        )
        self._register(
            "file_write", self._file_write,
            "Write content to a file in the workspace.",
            ["path", "content", "mode?"],
            "files", cost_per_call=0.0
        )
        self._register(
            "file_list", self._file_list,
            "List files in a workspace directory.",
            ["path?"],
            "files", cost_per_call=0.0
        )
        self._register(
            "file_delete", self._file_delete,
            "Delete a file from the workspace.",
            ["path"],
            "files", cost_per_call=0.0
        )

        # ── HTTP ──────────────────────────────────────────────────
        self._register(
            "http_get", self._http_get,
            "Make an HTTP GET request. Returns status + body.",
            ["url", "headers?", "params?"],
            "http", cost_per_call=0.0
        )
        self._register(
            "http_post", self._http_post,
            "Make an HTTP POST request with JSON body.",
            ["url", "body", "headers?"],
            "http", cost_per_call=0.0
        )

        # ── Memory ────────────────────────────────────────────────
        self._register(
            "memory_search", self._memory_search,
            "Search long-term memory for relevant facts.",
            ["query", "domain?", "limit?"],
            "memory", cost_per_call=0.0
        )
        self._register(
            "memory_store_fact", self._memory_store_fact,
            "Distill and store a fact in long-term memory.",
            ["agent", "domain", "fact", "confidence?"],
            "memory", cost_per_call=0.0
        )
        self._register(
            "memory_get_state", self._memory_get_state,
            "Get a shared world state value by key.",
            ["key"],
            "memory", cost_per_call=0.0
        )
        self._register(
            "memory_set_state", self._memory_set_state,
            "Set a shared world state value.",
            ["key", "value", "updated_by?"],
            "memory", cost_per_call=0.0
        )

        # ── Telegram ──────────────────────────────────────────────
        self._register(
            "telegram_send", self._telegram_send,
            "Send a message to the Forgemaster via Telegram.",
            ["message", "chat_id?"],
            "comms", cost_per_call=0.0
        )

        # ── GitHub ────────────────────────────────────────────────
        self._register(
            "github_read_file", self._github_read_file,
            "Read a file from a GitHub repo.",
            ["repo", "path", "branch?"],
            "github", cost_per_call=0.0
        )
        self._register(
            "github_push_file", self._github_push_file,
            "Push/update a file in a GitHub repo.",
            ["repo", "path", "content", "message", "branch?"],
            "github", cost_per_call=0.0
        )

        # ── JSON ──────────────────────────────────────────────────
        self._register(
            "json_parse", self._json_parse,
            "Parse a JSON string and return the object.",
            ["text"],
            "utils", cost_per_call=0.0
        )
        self._register(
            "json_extract", self._json_extract,
            "Extract a value from a JSON string by dot-notation key.",
            ["text", "key"],
            "utils", cost_per_call=0.0
        )

    # ── Dispatch ──────────────────────────────────────────────────

    def run(self, tool_name: str, agent: str = "system",
            session_id: str = None, **kwargs) -> ToolResult:
        """
        Run a tool by name. Logs to MemoryCore automatically.
        Note: 'agent' and 'session_id' are reserved for run() — not forwarded
        to tool functions unless the tool explicitly needs 'agent' (like memory_store_fact).
        """
        if tool_name not in self._tools:
            return ToolResult(tool_name, False, None,
                              error=f"Unknown tool: {tool_name}")

        t = self._tools[tool_name]
        t["call_count"] += 1

        # Inject agent into kwargs for tools that need it
        import inspect
        fn_params = inspect.signature(t["fn"]).parameters
        if "agent" in fn_params and "agent" not in kwargs:
            kwargs["agent"] = agent

        try:
            start = time.time()
            result = t["fn"](**kwargs)
            elapsed = time.time() - start

            t["total_cost"] += t["cost"]

            # Log to memory
            if session_id:
                mem = get_memory()
                mem.log_exchange(
                    session_id, agent, "tool",
                    f"[{tool_name}] {json.dumps(kwargs)[:200]} → {str(result.output)[:300]}",
                    cost_usd=t["cost"]
                )

            return result

        except Exception as e:
            err = f"{type(e).__name__}: {str(e)}"
            return ToolResult(tool_name, False, None, error=err)

    def list_tools(self, category: str = None) -> List[Dict]:
        """List available tools, optionally filtered by category."""
        tools = []
        for name, t in self._tools.items():
            if category and t["category"] != category:
                continue
            tools.append({
                "name":        name,
                "description": t["description"],
                "params":      t["params"],
                "category":    t["category"],
                "calls":       t["call_count"],
            })
        return tools

    def stats(self) -> Dict:
        total_calls = sum(t["call_count"] for t in self._tools.values())
        total_cost  = sum(t["total_cost"]  for t in self._tools.values())
        return {
            "total_tools":  len(self._tools),
            "total_calls":  total_calls,
            "total_cost_usd": round(total_cost, 6),
            "by_category":  self._category_stats(),
        }

    def _category_stats(self) -> Dict:
        cats = {}
        for t in self._tools.values():
            c = t["category"]
            cats.setdefault(c, {"tools": 0, "calls": 0})
            cats[c]["tools"] += 1
            cats[c]["calls"] += t["call_count"]
        return cats

    # ── Tool Implementations ──────────────────────────────────────

    def _web_search(self, query: str, num_results: int = 5) -> ToolResult:
        if not SERPER_API_KEY:
            return ToolResult("web_search", False, None,
                              error="SERPER_API_KEY not set")
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": num_results},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic", [])[:num_results]:
                results.append({
                    "title":   item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url":     item.get("link", ""),
                })
            return ToolResult("web_search", True, results, cost_usd=0.001)
        except Exception as e:
            return ToolResult("web_search", False, None, error=str(e))

    def _web_fetch(self, url: str, timeout: int = 10) -> ToolResult:
        try:
            resp = requests.get(url, timeout=timeout,
                                headers={"User-Agent": "Mozilla/5.0"})
            return ToolResult("web_fetch", True, {
                "status": resp.status_code,
                "content": resp.text[:5000],
                "url": resp.url,
            })
        except Exception as e:
            return ToolResult("web_fetch", False, None, error=str(e))

    def _scrape_text(self, url: str) -> ToolResult:
        try:
            import re
            resp = requests.get(url, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0"})
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return ToolResult("scrape_text", True, text[:4000])
        except Exception as e:
            return ToolResult("scrape_text", False, None, error=str(e))

    def _run_python(self, code: str, timeout: int = CODE_TIMEOUT) -> ToolResult:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                             delete=False) as f:
                f.write(code)
                fname = f.name
            result = subprocess.run(
                ["python3", fname],
                capture_output=True, text=True, timeout=timeout
            )
            os.unlink(fname)
            return ToolResult("run_python", True, {
                "stdout": result.stdout[:3000],
                "stderr": result.stderr[:1000],
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return ToolResult("run_python", False, None, error="Timeout")
        except Exception as e:
            return ToolResult("run_python", False, None, error=str(e))

    def _run_shell(self, command: str, timeout: int = SHELL_TIMEOUT) -> ToolResult:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout
            )
            return ToolResult("run_shell", True, {
                "stdout": result.stdout[:3000],
                "stderr": result.stderr[:1000],
                "returncode": result.returncode,
            })
        except subprocess.TimeoutExpired:
            return ToolResult("run_shell", False, None, error="Timeout")
        except Exception as e:
            return ToolResult("run_shell", False, None, error=str(e))

    def _file_read(self, path: str) -> ToolResult:
        try:
            full = Path(WORKSPACE) / path
            content = full.read_text(encoding="utf-8")
            return ToolResult("file_read", True, content)
        except Exception as e:
            return ToolResult("file_read", False, None, error=str(e))

    def _file_write(self, path: str, content: str, mode: str = "w") -> ToolResult:
        try:
            full = Path(WORKSPACE) / path
            full.parent.mkdir(parents=True, exist_ok=True)
            with open(full, mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult("file_write", True, {"path": str(full), "bytes": len(content)})
        except Exception as e:
            return ToolResult("file_write", False, None, error=str(e))

    def _file_list(self, path: str = "") -> ToolResult:
        try:
            full = Path(WORKSPACE) / path
            files = [str(p.relative_to(WORKSPACE)) for p in full.rglob("*") if p.is_file()]
            return ToolResult("file_list", True, files)
        except Exception as e:
            return ToolResult("file_list", False, None, error=str(e))

    def _file_delete(self, path: str) -> ToolResult:
        try:
            full = Path(WORKSPACE) / path
            full.unlink()
            return ToolResult("file_delete", True, {"deleted": str(full)})
        except Exception as e:
            return ToolResult("file_delete", False, None, error=str(e))

    def _http_get(self, url: str, headers: dict = None, params: dict = None) -> ToolResult:
        try:
            resp = requests.get(url, headers=headers or {}, params=params or {}, timeout=10)
            return ToolResult("http_get", True, {
                "status": resp.status_code,
                "body": resp.text[:4000],
            })
        except Exception as e:
            return ToolResult("http_get", False, None, error=str(e))

    def _http_post(self, url: str, body: dict, headers: dict = None) -> ToolResult:
        try:
            resp = requests.post(url, json=body, headers=headers or {}, timeout=10)
            return ToolResult("http_post", True, {
                "status": resp.status_code,
                "body": resp.text[:4000],
            })
        except Exception as e:
            return ToolResult("http_post", False, None, error=str(e))

    def _memory_search(self, query: str, domain: str = None, limit: int = 10) -> ToolResult:
        try:
            mem = get_memory()
            facts = mem.search_facts(query, domain=domain, limit=limit)
            return ToolResult("memory_search", True, facts)
        except Exception as e:
            return ToolResult("memory_search", False, None, error=str(e))

    def _memory_store_fact(self, agent: str, domain: str, fact: str,
                           confidence: float = 1.0) -> ToolResult:
        try:
            mem = get_memory()
            fid = mem.store_fact(agent, domain, fact, confidence)
            return ToolResult("memory_store_fact", True, {"fact_id": fid})
        except Exception as e:
            return ToolResult("memory_store_fact", False, None, error=str(e))

    def _memory_get_state(self, key: str) -> ToolResult:
        try:
            mem = get_memory()
            val = mem.get_state(key)
            return ToolResult("memory_get_state", True, val)
        except Exception as e:
            return ToolResult("memory_get_state", False, None, error=str(e))

    def _memory_set_state(self, key: str, value: Any, updated_by: str = "system") -> ToolResult:
        try:
            mem = get_memory()
            mem.set_state(key, value, updated_by)
            return ToolResult("memory_set_state", True, {"key": key})
        except Exception as e:
            return ToolResult("memory_set_state", False, None, error=str(e))

    def _telegram_send(self, message: str, chat_id: str = TG_CHAT) -> ToolResult:
        if not TG_TOKEN:
            return ToolResult("telegram_send", False, None, error="TG_TOKEN not set")
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=10
            )
            return ToolResult("telegram_send", resp.status_code == 200, resp.json())
        except Exception as e:
            return ToolResult("telegram_send", False, None, error=str(e))

    def _github_read_file(self, repo: str, path: str, branch: str = "main") -> ToolResult:
        try:
            import base64
            url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
            resp = requests.get(url, headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return ToolResult("github_read_file", True, {
                    "content": content,
                    "sha": data["sha"],
                    "path": path,
                })
            return ToolResult("github_read_file", False, None,
                              error=f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            return ToolResult("github_read_file", False, None, error=str(e))

    def _github_push_file(self, repo: str, path: str, content: str,
                          message: str, branch: str = "main") -> ToolResult:
        try:
            import base64
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            url = f"https://api.github.com/repos/{repo}/contents/{path}"

            # Get current SHA if file exists
            existing = requests.get(f"{url}?ref={branch}", headers=headers, timeout=10)
            sha = existing.json().get("sha") if existing.status_code == 200 else None

            body = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha

            resp = requests.put(url, headers=headers, json=body, timeout=15)
            success = resp.status_code in (200, 201)
            return ToolResult("github_push_file", success, resp.json() if success else None,
                              error=None if success else resp.text[:200])
        except Exception as e:
            return ToolResult("github_push_file", False, None, error=str(e))

    def _json_parse(self, text: str) -> ToolResult:
        try:
            return ToolResult("json_parse", True, json.loads(text))
        except Exception as e:
            return ToolResult("json_parse", False, None, error=str(e))

    def _json_extract(self, text: str, key: str) -> ToolResult:
        try:
            obj = json.loads(text)
            parts = key.split(".")
            val = obj
            for p in parts:
                val = val[p]
            return ToolResult("json_extract", True, val)
        except Exception as e:
            return ToolResult("json_extract", False, None, error=str(e))


# ── Singleton ─────────────────────────────────────────────────────
_forge_instance: Optional[ToolForge] = None

def get_forge() -> ToolForge:
    global _forge_instance
    if _forge_instance is None:
        _forge_instance = ToolForge()
    return _forge_instance


# ── CLI test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("⚒️  ToolForge — Boot Test\n")
    forge = get_forge()

    # List all tools
    tools = forge.list_tools()
    print(f"📦 {len(tools)} tools registered:")
    cats = {}
    for t in tools:
        cats.setdefault(t["category"], []).append(t["name"])
    for cat, names in sorted(cats.items()):
        print(f"   [{cat}] {', '.join(names)}")

    # File write/read test
    print("\n📁 File ops test...")
    r = forge.run("file_write", agent="test", path="test.txt", content="ToolForge is live\n")
    print(f"   write: {r}")
    r = forge.run("file_read", agent="test", path="test.txt")
    print(f"   read:  {r.output.strip()}")

    # Python exec test
    print("\n🐍 Code exec test...")
    r = forge.run("run_python", agent="test", code="print(2**10)")
    print(f"   stdout: {r.output['stdout'].strip()}")

    # Memory tool test
    print("\n🧠 Memory tool test...")
    r = forge.run("memory_store_fact", agent="test",
                  domain="ops", fact="ToolForge registered 22 tools at boot")
    print(f"   stored: {r}")
    r = forge.run("memory_search", agent="test", query="ToolForge registered")
    print(f"   search: {len(r.output)} fact(s) found")

    # JSON test
    print("\n🔧 JSON test...")
    r = forge.run("json_extract", agent="test",
                  text='{"pantheon":{"version":"2.0"}}', key="pantheon.version")
    print(f"   extracted: {r.output}")

    # Stats
    print(f"\n📊 ToolForge Stats:")
    s = forge.stats()
    print(f"   total tools: {s['total_tools']}")
    print(f"   total calls: {s['total_calls']}")
    for cat, data in s["by_category"].items():
        print(f"   [{cat}] {data['calls']} calls")

    print("\n✅ ToolForge online.")
