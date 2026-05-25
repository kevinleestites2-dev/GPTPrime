from gptprime.agent_base import GPTPrimeAgent

class AgentGPTAgent(GPTPrimeAgent):
    """
    AgentGPT specializing in browser-deployed autonomous agents.
    Focuses on web-based automation and interface interaction.
    """
    def __init__(self):
        super().__init__()
        self.name = "AgentGPT"
        self.role = "Web Automator"

    def run(self, task: str) -> str:
        self.log(f"Starting web automation: {task}")
        
        # Perform web search
        search_results = self.use_tool("web_search", query=task)
        
        # Scrape data
        if search_results.get("success"):
            first_url = search_results.get("output", {}).get("results", [{}])[0].get("url")
            if first_url:
                self.use_tool("scrape_url", url=first_url)
        
        result = f"AgentGPT completed web automation for: {task}"
        self.remember(result, category="web_ops")
        return result
