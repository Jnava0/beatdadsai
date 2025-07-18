# File: backend/agent_manager.py
# Author: Gemini
# Date: July 17, 2024
# Description: Manages the lifecycle of all AI agents in the system.
# This version is upgraded to use a PostgreSQL database for persistence.

import uuid
import logging
from typing import Dict, Optional, List

# Import our core classes and the new database manager
from agent import Agent
from llm_provider import LLMProvider
from database import DatabaseManager

logger = logging.getLogger(__name__)

class AgentManager:
    """
    A thread-safe singleton class to manage all agent instances.
    It acts as a central registry, creating, retrieving, and deleting agents
    from the persistent PostgreSQL database.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        # We don't need a lock here as FastAPI's lifespan ensures it's called once.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, llm_provider: LLMProvider, db_manager: DatabaseManager):
        """
        Initializes the AgentManager with necessary service providers.

        Args:
            llm_provider (LLMProvider): The shared instance of the LLM provider.
            db_manager (DatabaseManager): The shared instance of the database manager.
        """
        if not hasattr(self, 'initialized'):
            logger.info("Initializing AgentManager with Database Persistence.")
            self._llm_provider = llm_provider
            self._db_manager = db_manager
            # No more in-memory storage. The database is the source of truth.
            self.initialized = True
            logger.info("AgentManager initialized.")

    def create_agent(self, name: str, role: str, model_id: str) -> Agent:
        """
        Creates a new agent instance and saves its configuration to the database.

        Args:
            name (str): The human-readable name for the new agent.
            role (str): The detailed role and purpose of the agent.
            model_id (str): The ID of the LLM the agent should use.

        Returns:
            Agent: The newly created agent instance.
        """
        if model_id not in self._llm_provider.models_config:
            raise ValueError(f"Model ID '{model_id}' is not a valid, configured model.")

        agent_id = uuid.uuid4()
        
        query = """
            INSERT INTO agents (agent_id, name, role, model_id)
            VALUES (%s, %s, %s, %s);
        """
        params = (str(agent_id), name, role, model_id)
        
        self._db_manager.execute_query(query, params)
        logger.info(f"Agent '{name}' with ID {agent_id} saved to database.")
        
        # Return a fully instantiated Agent object
        return Agent(
            agent_id=str(agent_id),
            name=name,
            role=role,
            model_id=model_id,
            llm_provider=self._llm_provider
        )

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """
        Retrieves an agent's data from the database and reconstructs the Agent object.

        Args:
            agent_id (str): The UUID of the agent to retrieve.

        Returns:
            Optional[Agent]: The agent instance if found, otherwise None.
        """
        query = "SELECT agent_id, name, role, model_id FROM agents WHERE agent_id = %s;"
        params = (agent_id,)
        
        result = self._db_manager.execute_query(query, params, fetch='one')
        
        if result:
            db_agent_id, name, role, model_id = result
            # Reconstruct the agent object with the necessary providers.
            return Agent(
                agent_id=str(db_agent_id),
                name=name,
                role=role,
                model_id=model_id,
                llm_provider=self._llm_provider
            )
        return None

    def list_agents(self) -> List[Dict]:
        """
        Returns a list of configurations for all agents stored in the database.

        Returns:
            List[Dict]: A list of agent configuration dictionaries.
        """
        query = "SELECT agent_id, name, role, model_id FROM agents ORDER BY created_at DESC;"
        results = self._db_manager.execute_query(query, fetch='all')
        
        if not results:
            return []
            
        # Convert list of tuples into list of dictionaries
        return [
            {"agent_id": str(row[0]), "name": row[1], "role": row[2], "model_id": row[3]}
            for row in results
        ]

    def delete_agent(self, agent_id: str) -> bool:
        """
        Deletes an agent from the database.

        Args:
            agent_id (str): The UUID of the agent to delete.

        Returns:
            bool: True if the agent was found and deleted, False otherwise.
        """
        # First, check if the agent exists to provide a more accurate return value.
        if not self.get_agent(agent_id):
            return False
            
        query = "DELETE FROM agents WHERE agent_id = %s;"
        params = (agent_id,)
        
        self._db_manager.execute_query(query, params)
        logger.info(f"Agent with ID '{agent_id}' deleted from database.")
        return True
