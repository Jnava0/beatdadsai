@@ .. @@
 import uuid
 import logging
 from typing import Dict, Optional, List
 
 # Import our core classes and the new database manager
 from agent import Agent
 from llm_provider import LLMProvider
 from database import DatabaseManager
+from tools.tool_manager import ToolManager
+from message_broker import MessageBroker
+from task_scheduler import TaskScheduler
 
 logger = logging.getLogger(__name__)
 
@@ .. @@
     def __new__(cls, *args, **kwargs):
-        # We don't need a lock here as FastAPI's lifespan ensures it's called once.
         if cls._instance is None:
             cls._instance = super().__new__(cls)
         return cls._instance
 
-    def __init__(self, llm_provider: LLMProvider, db_manager: DatabaseManager):
+    def __init__(self, llm_provider: LLMProvider, db_manager: DatabaseManager, tool_manager: ToolManager, message_broker: MessageBroker = None, task_scheduler: TaskScheduler = None):
         """
         Initializes the AgentManager with necessary service providers.
 
         Args:
             llm_provider (LLMProvider): The shared instance of the LLM provider.
             db_manager (DatabaseManager): The shared instance of the database manager.
+            tool_manager (ToolManager): The shared instance of the tool manager.
+            message_broker (MessageBroker): The message broker for agent communication.
+            task_scheduler (TaskScheduler): The task scheduler for coordinated work.
         """
         if not hasattr(self, 'initialized'):
-            logger.info("Initializing AgentManager with Database Persistence.")
+            logger.info("Initializing Enhanced AgentManager with Multi-Agent Support.")
             self._llm_provider = llm_provider
             self._db_manager = db_manager
-            # No more in-memory storage. The database is the source of truth.
+            self._tool_manager = tool_manager
+            self._message_broker = message_broker
+            self._task_scheduler = task_scheduler
+            self._active_agents: Dict[str, Agent] = {}  # Currently running agents
             self.initialized = True
             logger.info("AgentManager initialized.")
 
-    def create_agent(self, name: str, role: str, model_id: str) -> Agent:
+    def create_agent(
+        self, 
+        name: str, 
+        role: str, 
+        model_id: str, 
+        allowed_tool_names: Optional[List[str]] = None,
+        autonomy_level: str = "medium",
+        communication_rights: Optional[List[str]] = None,
+        memory_scope: str = "task_limited"
+    ) -> Agent:
         """
-        Creates a new agent instance and saves its configuration to the database.
+        Creates a new enhanced agent instance and saves its configuration to the database.
 
         Args:
             name (str): The human-readable name for the new agent.
             role (str): The detailed role and purpose of the agent.
             model_id (str): The ID of the LLM the agent should use.
+            allowed_tool_names (List[str], optional): List of tools this agent can use.
+            autonomy_level (str): Level of autonomy (low, medium, high).
+            communication_rights (List[str], optional): Communication permissions.
+            memory_scope (str): Memory persistence scope.
 
         Returns:
             Agent: The newly created agent instance.
@@ .. @@
         agent_id = uuid.uuid4()
         
         query = """
-            INSERT INTO agents (agent_id, name, role, model_id)
-            VALUES (%s, %s, %s, %s);
+            INSERT INTO agents (agent_id, name, role, model_id, allowed_tools, autonomy_level, communication_rights, memory_scope)
+            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
         """
-        params = (str(agent_id), name, role, model_id)
+        import json
+        params = (
+            str(agent_id), 
+            name, 
+            role, 
+            model_id,
+            json.dumps(allowed_tool_names or []),
+            autonomy_level,
+            json.dumps(communication_rights or ["agent_to_agent"]),
+            memory_scope
+        )
         
         self._db_manager.execute_query(query, params)
         logger.info(f"Agent '{name}' with ID {agent_id} saved to database.")
         
         # Return a fully instantiated Agent object
-        return Agent(
+        agent = Agent(
             agent_id=str(agent_id),
             name=name,
             role=role,
             model_id=model_id,
-            llm_provider=self._llm_provider
+            llm_provider=self._llm_provider,
+            tool_manager=self._tool_manager,
+            allowed_tool_names=allowed_tool_names,
+            message_broker=self._message_broker,
+            task_scheduler=self._task_scheduler,
+            autonomy_level=autonomy_level,
+            communication_rights=communication_rights or ["agent_to_agent"],
+            memory_scope=memory_scope
         )
+        
+        return agent
+
+    def start_agent(self, agent_id: str) -> bool:
+        """
+        Start an agent (load it into active memory and begin processing).
+        """
+        try:
+            if agent_id in self._active_agents:
+                logger.warning(f"Agent {agent_id} is already active")
+                return True
+            
+            agent = self.get_agent(agent_id)
+            if not agent:
+                logger.error(f"Agent {agent_id} not found")
+                return False
+            
+            # Register agent with message broker if available
+            if self._message_broker:
+                self._message_broker.register_agent(agent_id)
+            
+            # Start agent's processing loop
+            agent.start()
+            self._active_agents[agent_id] = agent
+            
+            logger.info(f"Started agent: {agent_id}")
+            return True
+            
+        except Exception as e:
+            logger.error(f"Failed to start agent {agent_id}: {e}")
+            return False
+
+    def stop_agent(self, agent_id: str) -> bool:
+        """
+        Stop an active agent.
+        """
+        try:
+            if agent_id not in self._active_agents:
+                logger.warning(f"Agent {agent_id} is not active")
+                return True
+            
+            agent = self._active_agents[agent_id]
+            agent.stop()
+            
+            # Unregister from message broker
+            if self._message_broker:
+                self._message_broker.unregister_agent(agent_id)
+            
+            del self._active_agents[agent_id]
+            
+            logger.info(f"Stopped agent: {agent_id}")
+            return True
+            
+        except Exception as e:
+            logger.error(f"Failed to stop agent {agent_id}: {e}")
+            return False
 
     def get_agent(self, agent_id: str) -> Optional[Agent]:
@@ .. @@
         Returns:
             Optional[Agent]: The agent instance if found, otherwise None.
         """
         query = "SELECT agent_id, name, role, model_id FROM agents WHERE agent_id = %s;"
+        # Check if agent is already active
+        if agent_id in self._active_agents:
+            return self._active_agents[agent_id]
+        
+        query = """
+            SELECT agent_id, name, role, model_id, allowed_tools, autonomy_level, communication_rights, memory_scope 
+            FROM agents WHERE agent_id = %s;
+        """
         params = (agent_id,)
         
         result = self._db_manager.execute_query(query, params, fetch='one')
         
         if result:
-            db_agent_id, name, role, model_id = result
+            import json
+            db_agent_id, name, role, model_id, allowed_tools, autonomy_level, communication_rights, memory_scope = result
+            
             # Reconstruct the agent object with the necessary providers.
             return Agent(
                 agent_id=str(db_agent_id),
                 name=name,
                 role=role,
                 model_id=model_id,
-                llm_provider=self._llm_provider
+                llm_provider=self._llm_provider,
+                tool_manager=self._tool_manager,
+                allowed_tool_names=json.loads(allowed_tools) if allowed_tools else None,
+                message_broker=self._message_broker,
+                task_scheduler=self._task_scheduler,
+                autonomy_level=autonomy_level or "medium",
+                communication_rights=json.loads(communication_rights) if communication_rights else ["agent_to_agent"],
+                memory_scope=memory_scope or "task_limited"
             )
         return None
 
@@ .. @@
         Returns:
             List[Dict]: A list of agent configuration dictionaries.
         """
-        query = "SELECT agent_id, name, role, model_id FROM agents ORDER BY created_at DESC;"
+        query = """
+            SELECT agent_id, name, role, model_id, allowed_tools, autonomy_level, communication_rights, memory_scope 
+            FROM agents ORDER BY created_at DESC;
+        """
         results = self._db_manager.execute_query(query, fetch='all')
         
         if not results:
             return []
             
+        import json
         # Convert list of tuples into list of dictionaries
-        return [
-            {"agent_id": str(row[0]), "name": row[1], "role": row[2], "model_id": row[3]}
-            for row in results
-        ]
+        agents = []
+        for row in results:
+            agent_data = {
+                "agent_id": str(row[0]), 
+                "name": row[1], 
+                "role": row[2], 
+                "model_id": row[3],
+                "allowed_tools": json.loads(row[4]) if row[4] else [],
+                "autonomy_level": row[5] or "medium",
+                "communication_rights": json.loads(row[6]) if row[6] else ["agent_to_agent"],
+                "memory_scope": row[7] or "task_limited",
+                "status": "active" if str(row[0]) in self._active_agents else "inactive"
+            }
+            agents.append(agent_data)
+        
+        return agents
 
     def delete_agent(self, agent_id: str) -> bool:
@@ .. @@
         Returns:
             bool: True if the agent was found and deleted, False otherwise.
         """
+        # Stop agent if it's active
+        if agent_id in self._active_agents:
+            self.stop_agent(agent_id)
+        
         # First, check if the agent exists to provide a more accurate return value.
         if not self.get_agent(agent_id):
             return False
@@ .. @@
         self._db_manager.execute_query(query, params)
         logger.info(f"Agent with ID '{agent_id}' deleted from database.")
         return True
+
+    def get_active_agents(self) -> Dict[str, Agent]:
+        """Get all currently active agents."""
+        return self._active_agents.copy()
+
+    def get_agent_status(self, agent_id: str) -> Dict[str, any]:
+        """Get detailed status information for an agent."""
+        status = {
+            "agent_id": agent_id,
+            "active": agent_id in self._active_agents,
+            "exists": self.get_agent(agent_id) is not None
+        }
+        
+        if agent_id in self._active_agents:
+            agent = self._active_agents[agent_id]
+            status.update({
+                "name": agent.name,
+                "model_id": agent.model_id,
+                "autonomy_level": getattr(agent, 'autonomy_level', 'unknown'),
+                "message_queue_size": self._message_broker.get_agent_queue_size(agent_id) if self._message_broker else 0,
+                "current_tasks": len(self._task_scheduler.get_agent_workload(agent_id)) if self._task_scheduler else 0
+            })
+        
+        return status
+
+    def broadcast_message(self, sender_id: str, message: str, message_type: str = "notification") -> bool:
+        """Send a message to all active agents."""
+        if not self._message_broker:
+            return False
+        
+        try:
+            msg = self._message_broker.create_message(
+                sender=sender_id,
+                recipient="ALL",
+                content=message,
+                message_type=getattr(self._message_broker.MessageType, message_type.upper(), self._message_broker.MessageType.NOTIFICATION)
+            )
+            
+            return self._message_broker.send_message(msg)
+            
+        except Exception as e:
+            logger.error(f"Failed to broadcast message: {e}")
+            return False
+
+    def create_team(self, team_name: str, agent_ids: List[str], leader_id: Optional[str] = None) -> bool:
+        """Create a team of agents with optional leader."""
+        try:
+            # Create a broadcast channel for the team
+            if self._message_broker:
+                for agent_id in agent_ids:
+                    self._message_broker.join_broadcast_channel(agent_id, f"team_{team_name}")
+            
+            # If there's a leader, give them special permissions
+            if leader_id and leader_id in agent_ids:
+                # Could implement leader-specific logic here
+                pass
+            
+            logger.info(f"Created team '{team_name}' with {len(agent_ids)} agents")
+            return True
+            
+        except Exception as e:
+            logger.error(f"Failed to create team: {e}")
+            return False
+
+    def get_system_stats(self) -> Dict[str, any]:
+        """Get comprehensive system statistics."""
+        stats = {
+            "total_agents": len(self.list_agents()),
+            "active_agents": len(self._active_agents),
+            "available_models": len(self._llm_provider.models_config),
+            "available_tools": len(self._tool_manager.get_all_tools()) if self._tool_manager else 0
+        }
+        
+        if self._message_broker:
+            stats.update(self._message_broker.get_system_stats())
+        
+        if self._task_scheduler:
+            # Add task scheduler stats if available
+            pass
+        
+        return stats