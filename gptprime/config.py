import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
GPTPRIME_DIR = BASE_DIR / "gptprime"
DEFAULT_WORKSPACE = GPTPRIME_DIR / "workspace"

# Ensure workspace exists
DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)

# API Keys & Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Database Paths
GPTPRIME_MEMORY_DB = os.getenv("GPTPRIME_MEMORY_DB", str(GPTPRIME_DIR / "gptprime_memory.db"))

# Execution Defaults
STATUS_API_PORT = int(os.getenv("STATUS_API_PORT", 7200))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
CODE_EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", 15))
SHELL_TIMEOUT = int(os.getenv("SHELL_TIMEOUT", 10))

# Export CONFIG dict for convenience
CONFIG = {
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    "GITHUB_TOKEN": GITHUB_TOKEN,
    "SERPER_API_KEY": SERPER_API_KEY,
    "GPTPRIME_MEMORY_DB": GPTPRIME_MEMORY_DB,
    "GPTPRIME_WORKSPACE": str(DEFAULT_WORKSPACE),
    "STATUS_API_PORT": STATUS_API_PORT,
    "LOG_LEVEL": LOG_LEVEL,
    "MAX_RETRIES": MAX_RETRIES,
    "CODE_EXEC_TIMEOUT": CODE_EXEC_TIMEOUT,
    "SHELL_TIMEOUT": SHELL_TIMEOUT
}
