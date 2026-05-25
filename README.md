# ⚡ GPTPrime — The Strike Team

> *The Pantheon's autonomous strike force. 11 specialized GPT-powered weapons. One mission: execute.*

GPTPrime doesn't support the Pantheon. It **is** the tip of the spear — autonomous execution across research, code generation, market ops, and organizational intelligence.

---

## 🗡️ The Arsenal

| Weapon | Role | Repo |
|--------|------|------|
| **GPTSwarm** | Self-optimizing swarm graphs — agents evolve their own execution paths | kevinleestites2-dev/GPTSwarm |
| **gpt-engineer** | Full codebases from a single prompt — autonomous build engine | kevinleestites2-dev/gpt-engineer |
| **AutoGPT** | Long-horizon mission autonomy — sets and pursues its own objectives | kevinleestites2-dev/AutoGPT |
| **AgentGPT** | Browser-deployed autonomous agents — zero infrastructure | kevinleestites2-dev/AgentGPT |
| **gpt-researcher** | Deep research backbone — ScoutPrime intelligence layer | kevinleestites2-dev/gpt-researcher |
| **OpenAgents** | Data analysis, web, and plugin platform — open execution surface | kevinleestites2-dev/OpenAgents |
| **MetaGPT** | Multi-role orchestration (Engineer + PM + QA) — CerberusPrime's brain | kevinleestites2-dev/MetaGPT |
| **swarms** | Enterprise-grade production multi-agent orchestration | kevinleestites2-dev/swarms |
| **WebGPT** | In-browser GPT inference via WebGPU — zero API cost | kevinleestites2-dev/WebGPT |
| **crewAI** | Role-playing agent crews — collaborative strike execution | kevinleestites2-dev/crewAI |
| **Magicrew** | 🏛️ The War Room — Command Center OS. All units report here. | kevinleestites2-dev/magic |

---

## 🏛️ Architecture

```
FORGEMASTER
     │
     ▼
┌─────────────────┐
│   GPTPrime Core  │  ← Mission Router + Orchestrator
│  gpt_prime.py   │
└────────┬────────┘
         │
    ┌────┴─────────────────────────────────┐
    │         STRIKE WEAPONS               │
    ├──────────────────────────────────────┤
    │ Research    → gpt-researcher         │
    │ Build       → gpt-engineer           │
    │ Swarm       → GPTSwarm / swarms      │
    │ Autonomous  → AutoGPT / AgentGPT     │
    │ Orchestrate → MetaGPT / crewAI       │
    │ Data/Web    → OpenAgents / WebGPT    │
    └──────────────┬───────────────────────┘
                   │
         ┌─────────▼──────────┐
         │      Magicrew       │
         │   (War Room OS)     │
         │  Results + Reports  │
         └─────────┬───────────┘
                   │
            Telegram Report
```

---

## ⚙️ Core — `gpt_prime.py`

The mission router. Accepts a mission string, detects the type, deploys the right weapon, reports to Telegram.

**Mission Types:**
- `research:` → gpt-researcher
- `build:` → gpt-engineer
- `swarm:` → GPTSwarm
- `analyze:` → OpenAgents
- `orchestrate:` → MetaGPT + crewAI
- `auto:` → AutoGPT (long-horizon)
- `scan:` → ScoutPrime bridge

---

## 🚀 Quick Start

```bash
git clone https://github.com/kevinleestites2-dev/GPTPrime
cd GPTPrime
pip install -r requirements.txt
cp config/config.example.env config/config.env
# Add your API keys to config.env
python gpt_prime.py "research: Lee County foreclosure auction trends May 2026"
```

---

## 📡 Reporting

Every mission fires a Telegram update:
- Mission received
- Weapon deployed
- Result delivered
- Errors caught and reported

No silent strikes. Every action is visible.

---

## 🔗 Pantheon Position

```
FluxPrime (The Ocean)
    └── GPTPrime (The Strike Team)  ← YOU ARE HERE
            └── Magicrew (The War Room)
                    └── All results, artifacts, governance
```

GPTPrime sits between FluxPrime's mission autonomy and Magicrew's command structure. FluxPrime sets the objective. GPTPrime executes the strike. Magicrew receives the result.

---

*Built by the Forgemaster. Part of the Pantheon.*
