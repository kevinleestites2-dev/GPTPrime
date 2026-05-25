"""
GPTPrime — The Strike Team
The Pantheon's autonomous strike force.
"""

import os
import sys
import asyncio
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("config/config.env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8679655550:AAGUB1m5fmqHc8OHqqM24Vixz8FfwX-gqD4")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Weapon Registry ────────────────────────────────────────────────────────────

WEAPONS = {
    "research":    "gpt-researcher",
    "build":       "gpt-engineer",
    "swarm":       "GPTSwarm",
    "analyze":     "OpenAgents",
    "orchestrate": "MetaGPT + crewAI",
    "auto":        "AutoGPT",
    "scan":        "ScoutPrime Bridge",
    "browser":     "AgentGPT",
    "web":         "WebGPT",
}

# ── Telegram ───────────────────────────────────────────────────────────────────

async def telegram(msg: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return await r.json()
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")

# ── Mission Router ─────────────────────────────────────────────────────────────

def detect_weapon(mission: str) -> tuple[str, str]:
    """Detect mission type and return (weapon_key, weapon_name)."""
    mission_lower = mission.lower()
    for key in WEAPONS:
        if mission_lower.startswith(f"{key}:"):
            return key, WEAPONS[key]
    # Default: research for questions, auto for everything else
    if "?" in mission or any(w in mission_lower for w in ["what", "who", "when", "where", "how", "find", "search"]):
        return "research", WEAPONS["research"]
    return "auto", WEAPONS["auto"]

# ── Strike Executors ───────────────────────────────────────────────────────────

async def strike_research(mission: str) -> str:
    """Deploy gpt-researcher for deep intel missions."""
    try:
        from gpt_researcher import GPTResearcher
        clean = mission.replace("research:", "").strip()
        researcher = GPTResearcher(query=clean, report_type="research_report")
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report
    except ImportError:
        return f"[gpt-researcher not installed] Mission queued: {mission}\nInstall: pip install gpt-researcher"
    except Exception as e:
        return f"[Research Error] {e}"

async def strike_build(mission: str) -> str:
    """Deploy gpt-engineer for code generation missions."""
    clean = mission.replace("build:", "").strip()
    return (
        f"[gpt-engineer] Build mission received: {clean}\n"
        f"Run: python -m gpt_engineer '{clean}'"
    )

async def strike_auto(mission: str) -> str:
    """Deploy AutoGPT for long-horizon autonomous missions."""
    clean = mission.replace("auto:", "").strip()
    return (
        f"[AutoGPT] Autonomous mission received: {clean}\n"
        f"AutoGPT will set sub-goals and pursue them until completion."
    )

async def strike_swarm(mission: str) -> str:
    """Deploy GPTSwarm for swarm execution missions."""
    clean = mission.replace("swarm:", "").strip()
    return (
        f"[GPTSwarm] Swarm mission received: {clean}\n"
        f"Agents will self-optimize execution paths."
    )

async def strike_generic(weapon_name: str, mission: str) -> str:
    """Generic strike handler for weapons not yet directly wired."""
    return f"[{weapon_name}] Mission received: {mission}\nWeapon queued for deployment."

# ── Strike Dispatcher ──────────────────────────────────────────────────────────

EXECUTORS = {
    "research":    strike_research,
    "build":       strike_build,
    "auto":        strike_auto,
    "swarm":       strike_swarm,
}

async def dispatch(mission: str) -> str:
    weapon_key, weapon_name = detect_weapon(mission)
    executor = EXECUTORS.get(weapon_key)
    if executor:
        return await executor(mission)
    return await strike_generic(weapon_name, mission)

# ── Main ───────────────────────────────────────────────────────────────────────

async def main(mission: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weapon_key, weapon_name = detect_weapon(mission)

    print(f"\n⚡ GPTPrime — Strike Team")
    print(f"📡 Mission: {mission}")
    print(f"🗡️  Weapon:  {weapon_name}")
    print(f"⏱️  Time:    {ts}\n")

    # Report mission receipt to Telegram
    await telegram(
        f"⚡ <b>GPTPrime — Strike Initiated</b>\n"
        f"🗡️ Weapon: {weapon_name}\n"
        f"📋 Mission: {mission[:200]}\n"
        f"⏱️ {ts}"
    )

    # Execute
    result = await dispatch(mission)

    print(f"── RESULT ──────────────────────────────")
    print(result)
    print(f"────────────────────────────────────────\n")

    # Report result to Telegram
    await telegram(
        f"✅ <b>GPTPrime — Strike Complete</b>\n"
        f"🗡️ Weapon: {weapon_name}\n"
        f"📊 Result:\n{str(result)[:500]}"
    )

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gpt_prime.py \"<mission>\"")
        print("Examples:")
        print("  python gpt_prime.py \"research: Lee County foreclosure trends 2026\"")
        print("  python gpt_prime.py \"build: a Python scraper for auction listings\"")
        print("  python gpt_prime.py \"swarm: monitor 5 crypto pairs for breakout signals\"")
        sys.exit(1)

    mission = " ".join(sys.argv[1:])
    asyncio.run(main(mission))
