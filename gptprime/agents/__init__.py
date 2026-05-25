from .gpt_swarm import GPTSwarmAgent
from .gpt_engineer import GPTEngineerAgent
from .auto_gpt import AutoGPTAgent
from .agent_gpt import AgentGPTAgent
from .gpt_researcher import GPTResearcherAgent
from .open_agents import OpenAgentsAgent
from .meta_gpt import MetaGPTAgent
from .swarms_agent import SwarmsAgent
from .web_gpt import WebGPTAgent
from .crew_ai import CrewAIAgent
from .magicrew import MagicrewAgent

ALL_AGENTS = [
    GPTSwarmAgent,
    GPTEngineerAgent,
    AutoGPTAgent,
    AgentGPTAgent,
    GPTResearcherAgent,
    OpenAgentsAgent,
    MetaGPTAgent,
    SwarmsAgent,
    WebGPTAgent,
    CrewAIAgent,
    MagicrewAgent
]

AGENT_REGISTRY = {agent().name: agent for agent in ALL_AGENTS}
# Note: In the registry we use the class so it can be instantiated later, 
# but AGENT_REGISTRY[name] returns the class. 
# Re-mapping to name -> Class.
AGENT_REGISTRY = {
    "GPTSwarm": GPTSwarmAgent,
    "gpt-engineer": GPTEngineerAgent,
    "AutoGPT": AutoGPTAgent,
    "AgentGPT": AgentGPTAgent,
    "gpt-researcher": GPTResearcherAgent,
    "OpenAgents": OpenAgentsAgent,
    "MetaGPT": MetaGPTAgent,
    "Swarms": SwarmsAgent,
    "WebGPT": WebGPTAgent,
    "crewAI": CrewAIAgent,
    "Magicrew": MagicrewAgent
}
