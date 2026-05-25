import time
import uuid
import abc
import logging
from typing import Optional, List, Dict, Any
from gptprime.memory_core import get_memory
from gptprime.tool_forge import get_forge

class GPTPrimeAgent(abc.ABC):
    """
    Base class for all GPTPrime agents.
    Provides unified access to MemoryCore and ToolForge.
    """
    def __init__(self):
        self.name = "BaseAgent"
        self.role = "General Purpose Agent"
        self.session_id: Optional[str] = None
        self.start_time = time.time()
        
        # Stats tracking
        self.task_count = 0
        self.success_count = 0
        self.fail_count = 0
        
        # Core components
        self.memory = get_memory()
        self.forge = get_forge()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format=f'%(asctime)s - {self.name} - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(self.name)

    def _init_session(self, task: str):
        """Initialize or reset a session for a task."""
        self.session_id = self.memory.start_session(self.name, task)
        self.task_count += 1
        self.log(f"Session started: {self.session_id} for task: {task}")

    def remember(self, fact: str, category: str = "general", confidence: float = 1.0):
        """Store a fact in long-term memory."""
        self.memory.store_fact(
            agent=self.name,
            domain=category,
            fact=fact,
            confidence=confidence,
            source_session=self.session_id
        )
        self.log(f"Fact remembered: [{category}] {fact[:50]}...")

    def recall(self, query: str, limit: int = 5) -> List[Dict]:
        """Search long-term memory for relevant facts."""
        facts = self.memory.search_facts(query, limit=limit)
        self.log(f"Recalled {len(facts)} facts for query: '{query}'")
        return facts

    def use_tool(self, tool_name: str, **kwargs) -> Dict:
        """Execute a tool from ToolForge and log the result."""
        try:
            result = self.forge.run(
                tool_name=tool_name,
                agent=self.name,
                session_id=self.session_id,
                **kwargs
            )
            
            if result.success:
                self.success_count += 1
            else:
                self.fail_count += 1
                self.log(f"Tool error ({tool_name}): {result.error}", level="error")
            
            return result.to_dict()
        except Exception as e:
            self.fail_count += 1
            err_msg = f"Exception in use_tool ({tool_name}): {str(e)}"
            self.log(err_msg, level="error")
            
            # Log exception to memory if session exists
            if self.session_id:
                self.memory.log_exchange(
                    self.session_id, self.name, "tool",
                    f"CRITICAL ERROR in {tool_name}: {err_msg}",
                    cost_usd=0.0
                )
            
            return {
                "tool": tool_name,
                "success": False,
                "output": None,
                "error": err_msg,
                "ts": time.time()
            }

    def log(self, message: str, level: str = "info"):
        """Structured logging to memory and stdout."""
        if level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        else:
            self.logger.info(message)
            
        if self.session_id:
            # Log as a system-level exchange for tracking
            self.memory.log_exchange(
                session_id=self.session_id,
                agent=self.name,
                role="system",
                content=message
            )

    def report_status(self, status: str, task: str, result: str = None):
        """Send a Telegram status update via ToolForge."""
        msg = f"🤖 *Agent:* {self.name}\n📍 *Status:* {status}\n📝 *Task:* {task}"
        if result:
            msg += f"\n✅ *Result:* {result[:500]}"
        
        self.use_tool("telegram_send", message=msg)

    @abc.abstractmethod
    def run(self, task: str) -> str:
        """Entry point for the agent to perform a task."""
        pass

    def execute(self, task: str) -> str:
        """Wrapper around run() to handle session lifecycle and error reporting."""
        self._init_session(task)
        self.report_status("Starting", task)
        
        try:
            result = self.run(task)
            self.memory.end_session(self.session_id, status="completed")
            self.report_status("Completed", task, result)
            return result
        except Exception as e:
            self.fail_count += 1
            err_msg = f"Agent failed: {str(e)}"
            self.log(err_msg, level="error")
            self.memory.end_session(self.session_id, status="failed")
            self.report_status("Failed", task, err_msg)
            return err_msg
