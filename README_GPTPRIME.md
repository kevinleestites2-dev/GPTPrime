# GPTPrime v2.0 — The Strike Team

GPTPrime v2.0 is an autonomous, multi-agent orchestrator designed for high-velocity strike operations. It integrates 11 specialized AI agents into a unified command structure, backed by a persistent long-term memory layer (MemoryCore), a unified tool registry (ToolForge), and an asynchronous message bus (CommandBus). This system allows for complex, multi-stage task execution with minimal human intervention.

## Architecture

```text
       ┌───────────────────────────────────────────────────┐
       │                  FORGEMASTER (CLI)                │
       └─────────────────────────┬─────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │          LAUNCHER.PY          │
                 └───────────────┬───────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
 ┌───────▼───────┐       ┌───────▼───────┐       ┌───────▼───────┐
 │  MemoryCore   │◄─────►│  CommandBus   │◄─────►│   ToolForge   │
 │   (SQLite)    │       │   (Pub/Sub)   │       │  (Registry)   │
 └───────────────┘       └───────┬───────┘       └───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         │                                               │
 ┌───────▼───────┐       ┌───────────────┐       ┌───────▼───────┐
 │    Agent 1    │       │    Agent ...  │       │    Agent 11   │
 │ (GPTSwarm)    │       │    (crewAI)   │       │    (magic)    │
 └───────────────┘       └───────────────┘       └───────────────┘
```

## The Strike Team (11 Agents)

| Agent | Role | Focus |
| :--- | :--- | :--- |
| **GPTSwarm** | Swarm Architect | Self-optimizing agent graphs & execution paths |
| **gpt-engineer** | Code Architect | Full codebase generation from single prompts |
| **AutoGPT** | Mission Lead | Long-horizon autonomy & task decomposition |
| **AgentGPT** | Web Vanguard | Browser-native autonomous execution |
| **gpt-researcher** | Intelligence | Deep research, aggregation & synthesis |
| **OpenAgents** | Data Specialist | Analysis, plugin management & data pipelines |
| **MetaGPT** | PM/QA | Multi-role orchestration (Engineer, PM, QA) |
| **swarms** | Production Swarm | Enterprise-grade multi-agent coordination |
| **WebGPT** | Local Edge | In-browser GPT inference (WebGPU) |
| **crewAI** | Strike Force | Collaborative role-playing agent crews |
| **magic (Magicrew)** | Command Center | Workflow OS, IM & Sandboxed execution |

## Quick Start

Launch the entire stack with a single command:

```bash
python launch.py
```

## CLI Commands

- `run <agent> <task>`: Execute a specific agent with a specific task.
- `broadcast <task>`: Send a task to all agents simultaneously.
- `pipeline <t1>:<p1> -> <t2>:<p2>`: Chain tasks across multiple agents/topics.
- `status`: View the live status of all agents and system components.
- `memory <query>`: Search the shared long-term memory for specific facts.
- `tools`: List all tools available in the ToolForge.
- `agents`: List all 11 agents with their roles and current stats.
- `inject <json>`: Manually publish a message to the CommandBus.
- `help`: Display the command help menu.
- `exit`: Gracefully shut down all agents and system services.

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | API Token for status notifications | - |
| `TELEGRAM_CHAT_ID` | Recipient for Telegram alerts | 7135054241 |
| `GITHUB_TOKEN` | Auth for GitHub tool integrations | - |
| `SERPER_API_KEY` | Key for web search operations | - |
| `STATUS_API_PORT` | Port for the background Status API | 7200 |
| `GPTPRIME_WORKSPACE` | Root dir for agent file operations | `gptprime/workspace` |

## File Structure

```text
.
├── gptprime/
│   ├── agents/            # Agent implementations (Registry)
│   ├── bus_worker.py      # Background bus processing
│   ├── command_bus.py     # Pub/Sub infrastructure
│   ├── config.py          # Central configuration
│   ├── launcher.py        # Master orchestrator
│   ├── memory_core.py     # Persistence layer
│   ├── status_api.py      # HTTP status reporting
│   ├── tool_forge.py      # Unified tool registry
│   └── workspace/         # Sandboxed file storage
├── launch.py              # Entrypoint
└── README_GPTPRIME.md     # Documentation
```
