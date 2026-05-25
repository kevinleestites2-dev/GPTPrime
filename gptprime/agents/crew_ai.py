from gptprime.agent_base import GPTPrimeAgent

class CrewAIAgent(GPTPrimeAgent):
    """
    crewAI specializing in role-playing collaborative agent crews.
    Focuses on synergistic multi-agent workflows.
    """
    def __init__(self):
        super().__init__()
        self.name = "crewAI"
        self.role = "Workflow Collaborator"

    def run(self, task: str) -> str:
        self.log(f"Setting up collaborative crew for: {task}")
        
        # Define crew roles
        self.log("Defining Researcher and Writer roles.")
        self.use_tool("run_python", code="print('Crew formed and task delegated')")
        
        result = f"crewAI synergistic crew completed: {task}"
        self.remember(result, category="collaboration")
        return result
