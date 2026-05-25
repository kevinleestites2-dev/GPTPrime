from gptprime.agent_base import GPTPrimeAgent

class MetaGPTAgent(GPTPrimeAgent):
    """
    MetaGPT specializing in multi-role orchestration (Engineer, PM, QA).
    The organizational brain of CerberusPrime.
    """
    def __init__(self):
        super().__init__()
        self.name = "MetaGPT"
        self.role = "Team Orchestrator"

    def run(self, task: str) -> str:
        self.log(f"Orchestrating team for: {task}")
        
        # Simulate role assignment
        roles = ["Product Manager", "Architect", "Engineer", "QA"]
        for role in roles:
            self.log(f"Role assigned: {role}")
            self.use_tool("run_shell", command=f"echo 'Role {role} working on {task}'")
            
        result = f"MetaGPT orchestrated a full team cycle for: {task}. PR ready for review."
        self.remember(result, category="devops")
        return result
