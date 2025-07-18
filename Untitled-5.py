# File: backend/agent.py
# Author: Gemini
# Date: July 17, 2024
# Description: Defines the core AI Agent class for the MINI S system.
# This class serves as the blueprint for all specialized agents.

import uuid
from typing import Dict, Any

# Import our LLMProvider to give agents the ability to use language models.
from llm_provider import LLMProvider

class Agent:
    """
    The core Agent class. Each instance represents a configurable, independent AI agent.

    Attributes:
        agent_id (str): A unique identifier for the agent.
        name (str): A human-readable name for the agent (e.g., "CodeMaster").
        role (str): A detailed description of the agent's purpose and personality.
                    This is used as part of the system prompt.
        model_id (str): The identifier of the LLM this agent will use, as defined
                        in config.yaml.
        llm_provider (LLMProvider): The shared instance of the LLM provider.
        system_prompt (str): The base prompt that defines the agent's behavior.
    """

    def __init__(
        self,
        name: str,
        role: str,
        model_id: str,
        llm_provider: LLMProvider,
        agent_id: str = None
    ):
        """
        Initializes an instance of the Agent class.

        Args:
            name (str): The name of the agent.
            role (str): The specific role or function of the agent.
            model_id (str): The ID of the language model to be used.
            llm_provider (LLMProvider): The central provider for LLM access.
            agent_id (str, optional): A pre-existing ID for the agent. If None,
                                      a new unique ID is generated.
        """
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.role = role
        self.model_id = model_id
        self.llm_provider = llm_provider
        
        # The system prompt is crucial. It sets the context and "rules" for the LLM,
        # ensuring the agent behaves according to its defined role.
        self.system_prompt = self._create_system_prompt()
        
        print(f"Agent '{self.name}' (ID: {self.agent_id}) created. Role: {self.role}")

    def _create_system_prompt(self) -> str:
        """
        Constructs the system prompt based on the agent's profile.
        This prompt will be prepended to all interactions to guide the LLM.
        """
        return (
            f"You are {self.name}, an advanced AI agent. "
            f"Your role is: {self.role}. "
            "You must act and respond strictly within this role. "
            "Be concise, professional, and focused on the task at hand."
        )

    def think(self, user_prompt: str, generation_config: Dict[str, Any] = None) -> str:
        """
        The core reasoning loop of the agent.
        It takes a user prompt, combines it with the system prompt, and queries the LLM.

        Args:
            user_prompt (str): The input or query for the agent to process.
            generation_config (Dict[str, Any], optional): A dictionary of parameters
                to override the default generation settings (e.g., max_tokens, temperature).

        Returns:
            str: The raw text response from the LLM.
        """
        if generation_config is None:
            generation_config = {}

        # Construct the full prompt for the LLM.
        full_prompt = f"{self.system_prompt}\n\nUser Query: {user_prompt}\n\n{self.name}'s Response:"
        
        print(f"Agent '{self.name}' is thinking with model '{self.model_id}'...")

        # Use the LLM provider to generate a response.
        response = self.llm_provider.generate(
            model_id=self.model_id,
            prompt=full_prompt,
            max_tokens=generation_config.get('max_tokens', 1024),
            temperature=generation_config.get('temperature', 0.7)
        )
        
        # Basic post-processing: strip the original prompt from the response if present.
        # This is common as some models include the prompt in their output.
        if self.name in response:
             response = response.split(f"{self.name}'s Response:")[-1].strip()

        return response

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the agent's configuration to a dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "model_id": self.model_id,
        }

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    # This block demonstrates how to create and use an Agent instance.
    # It requires a running LLMProvider and a valid config.yaml.
    
    try:
        print("--- Testing Agent Class ---")
        # 1. Initialize the LLM Provider
        provider = LLMProvider(config_path="config.yaml")

        # 2. Define the agent's profile
        # IMPORTANT: Make sure 'qwen-7b-chat-gguf' is a valid model_id in your config.yaml
        agent_name = "PythonExpert"
        agent_role = "A world-class Python programmer who provides expert advice, writes clean, efficient code, and helps debug complex problems."
        agent_model_id = 'qwen-7b-chat-gguf' 

        # 3. Create an instance of the Agent
        python_agent = Agent(
            name=agent_name,
            role=agent_role,
            model_id=agent_model_id,
            llm_provider=provider
        )

        # 4. Interact with the agent
        query = "Explain the difference between a list and a tuple in Python."
        print(f"\nQuerying agent '{python_agent.name}': {query}")
        
        agent_response = python_agent.think(query)
        
        print(f"\n--- Agent Response ---")
        print(agent_response)
        print("------------------------")
        
        # 5. Test serialization
        print("\nAgent configuration (serialized):")
        print(python_agent.to_dict())

    except Exception as e:
        print(f"\nAn error occurred during agent testing: {e}")
        print("Please ensure your 'config.yaml' is correctly set up with valid model paths and IDs.")

