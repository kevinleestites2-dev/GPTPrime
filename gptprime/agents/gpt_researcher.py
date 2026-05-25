from gptprime.agent_base import GPTPrimeAgent

class GPTResearcherAgent(GPTPrimeAgent):
    """
    gpt-researcher specializing in deep research and intelligence gathering.
    The backbone of ScoutPrime.
    """
    def __init__(self):
        super().__init__()
        self.name = "gpt-researcher"
        self.role = "Research Specialist"

    def run(self, task: str) -> str:
        self.log(f"Initiating deep research: {task}")
        
        # Gather info from various sources
        self.use_tool("web_search", query=f"deep analysis of {task}")
        self.use_tool("web_search", query=f"market trends {task}")
        
        # Compile report
        result = f"gpt-researcher compiled a comprehensive intelligence report on: {task}"
        self.remember(f"Intel summary: {task} - findings logged.", category="intelligence")
        return result
