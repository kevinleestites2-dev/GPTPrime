from gptprime.agent_base import GPTPrimeAgent

class GPTEngineerAgent(GPTPrimeAgent):
    """
    gpt-engineer specializing in codebase generation from prompt.
    Builds full applications and modular components.
    """
    def __init__(self):
        super().__init__()
        self.name = "gpt-engineer"
        self.role = "Codebase Architect"

    def run(self, task: str) -> str:
        self.log(f"Generating codebase for: {task}")
        
        # Check for existing code templates
        templates = self.use_tool("file_list", path="templates")
        
        # Logic to generate code
        self.use_tool("file_write", path=f"builds/{self.session_id}/main.py", content="# Generated code\nprint('Hello World')")
        
        result = f"gpt-engineer generated code for: {task}. Build saved to builds/{self.session_id}/"
        self.remember(f"Codebase generated for {task} in builds/{self.session_id}/", category="code")
        return result
