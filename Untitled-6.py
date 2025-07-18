# File: backend/agent_manager.py
# Author: Gemini
# Date: July 17, 2024
# Description: Manages the lifecycle of all AI agents in the system.
# This includes creation, storage, retrieval, and listing of agents.

from threading import Lock
from typing import Dict, Optional, List

# Import our core classes
from agent import Agent
from llm_provider import LLMProvider

class AgentManager:
    """
    A thread-safe singleton class to manage all agent instances.
    It acts as a central registry, ensuring that agent data is handled
    consistently and preventing race conditions in a multi-agent environment.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        # Singleton pattern ensures a single, shared instance of the manager.
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, llm_provider: LLMProvider):
        """
        Initializes the AgentManager.

        Args:
            llm_provider (LLMProvider): The shared instance of the LLM provider,
                                        which is required to create agents.
        """
        if not hasattr(self, 'initialized'):
            with self._lock:
                if not hasattr(self, 'initialized'):
                    print("Initializing AgentManager...")
                    # For now, agents are stored in-memory. This will be replaced
                    # with a PostgreSQL backend in a future phase.
                    self._agents: Dict[str, Agent] = {}
                    self._llm_provider = llm_provider
                    self.initialized = True
                    print("AgentManager initialized.")

    def create_agent(self, name: str, role: str, model_id: str) -> Agent:
        """
        Creates a new agent, assigns it a unique ID, and stores it.

        Args:
            name (str): The human-readable name for the new agent.
            role (str): The detailed role and purpose of the agent.
            model_id (str): The ID of the LLM the agent should use.

        Returns:
            Agent: The newly created agent instance.
        
        Raises:
            ValueError: If the specified model_id is not found in the LLM provider's config.
        """
        # The LLMProvider will raise a ValueError if the model_id is invalid,
        # which we let propagate up to the API layer for proper error handling.
        if model_id not in self._llm_provider.models_config:
            raise ValueError(f"Model ID '{model_id}' is not a valid, configured model.")

        new_agent = Agent(
            name=name,
            role=role,
            model_id=model_id,
            llm_provider=self._llm_provider
        )
        
        # Use a lock to ensure thread-safe modification of the agents dictionary.
        with self._lock:
            self._agents[new_agent.agent_id] = new_agent
        
        print(f"Agent '{name}' created and registered with ID: {new_agent.agent_id}")
        return new_agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Retrieves a single agent by its unique ID.

        Args:
            agent_id (str): The UUID of the agent to retrieve.

        Returns:
            Optional[Agent]: The agent instance if found, otherwise None.
        """
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(self) -> List[Dict]:
        """
        Returns a list of configurations for all registered agents.
        This is suitable for display in a UI or for API responses.

        Returns:
            List[Dict]: A list of dictionaries, where each dictionary
                        represents the configuration of an agent.
        """
        with self._lock:
            # We call to_dict() on each agent to get its serializable representation.
            return [agent.to_dict() for agent in self._agents.values()]

    def delete_agent(self, agent_id: str) -> bool:
        """
        Deletes an agent from the manager.

        Args:
            agent_id (str): The UUID of the agent to delete.

        Returns:
            bool: True if the agent was found and deleted, False otherwise.
        """
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                print(f"Agent with ID '{agent_id}' has been deleted.")
                return True
            return False

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    # This block demonstrates the functionality of the AgentManager.
    try:
        print("\n--- Testing AgentManager Class ---")
        provider = LLMProvider(config_path="config.yaml")
        manager = AgentManager(llm_provider=provider)
        
        # 1. Create a couple of agents
        print("\n1. Creating agents...")
        # IMPORTANT: Replace with valid model IDs from your config.yaml
        agent1_model = 'qwen-7b-chat-gguf'
        agent2_model = 'llama2-7b-chat-hf' if 'llama2-7b-chat-hf' in provider.models_config else agent1_model

        researcher = manager.create_agent(
            name="DataDigger",
            role="An AI agent that specializes in finding and summarizing information.",
            model_id=agent1_model
        )
        coder = manager.create_agent(
            name="CodeCrafter",
            role="An AI agent that writes elegant and efficient Python code.",
            model_id=agent2_model
        )

        # 2. List all agents
        print("\n2. Listing all registered agents:")
        all_agents = manager.list_agents()
        import json
        print(json.dumps(all_agents, indent=2))
        assert len(all_agents) == 2

        # 3. Get a specific agent
        print(f"\n3. Retrieving agent with ID: {researcher.agent_id}")
        retrieved_agent = manager.get_agent(researcher.agent_id)
        assert retrieved_agent is not None
        print(f"Retrieved agent's name: {retrieved_agent.name}")
        assert retrieved_agent.name == "DataDigger"

        # 4. Use the retrieved agent to think
        print("\n4. Testing agent's 'think' method after retrieval...")
        query = "What is the capital of France?"
        response = retrieved_agent.think(query)
        print(f"Query: {query}\nResponse: {response.strip()}")

        # 5. Delete an agent
        print(f"\n5. Deleting agent: {coder.agent_id}")
        was_deleted = manager.delete_agent(coder.agent_id)
        assert was_deleted
        
        # 6. Verify deletion
        print("\n6. Listing agents after deletion:")
        all_agents_after_delete = manager.list_agents()
        print(json.dumps(all_agents_after_delete, indent=2))
        assert len(all_agents_after_delete) == 1
        assert manager.get_agent(coder.agent_id) is None

        print("\n--- AgentManager test completed successfully! ---")

    except Exception as e:
        print(f"\nAn error occurred during AgentManager testing: {e}")
        print("Please check your 'config.yaml' and ensure model dependencies are installed.")
