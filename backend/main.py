@@ .. @@
 from fastapi import FastAPI, HTTPException
 from pydantic import BaseModel, Field
-from typing import List, Optional, Dict, Any
+from typing import List, Optional, Dict, Any, Union
 import uvicorn
 from contextlib import asynccontextmanager
 import logging
 import uuid
+import asyncio
 
 # --- Import Core Modules ---
 from llm_provider import LLMProvider
 from agent_manager import AgentManager
 from logging_config import setup_logging
 from database import DatabaseManager, init_db
 from tools.tool_manager import ToolManager
+from message_broker import MessageBroker
+from task_scheduler import TaskScheduler, TaskPriority, TaskStatus
 
 # --- Setup ---
 setup_logging()
@@ .. @@
 class CreateAgentRequest(BaseModel):
     name: str = Field(..., example="WebResearcher")
     role: str = Field(..., example="An AI that answers questions by browsing the web.")
     model_id: str = Field(..., example="qwen-7b-chat-gguf")
-    allowed_tool_names: Optional[List[str]] = Field(None, example=["web_scraper"])
+    allowed_tool_names: Optional[List[str]] = Field(None, example=["web_scraper", "file_manager"])
+    autonomy_level: str = Field("medium", example="medium")
+    communication_rights: Optional[List[str]] = Field(["agent_to_agent"], example=["agent_to_agent", "agent_to_user"])
+    memory_scope: str = Field("task_limited", example="persistent")
 
 class AgentThinkRequest(BaseModel):
     prompt: str
+    max_iterations: Optional[int] = Field(5, description="Maximum thinking iterations")
 
 class AgentThinkResponse(BaseModel):
     agent_id: str
     response: str
+    iterations_used: Optional[int] = None
+
+class CreateTaskRequest(BaseModel):
+    title: str = Field(..., example="Build a simple web application")
+    description: str = Field(..., example="Create a basic HTML/CSS/JS web app with a contact form")
+    assigned_agent: Optional[str] = Field(None, example="agent-uuid")
+    priority: str = Field("medium", example="high")
+    due_date: Optional[str] = Field(None, example="2025-01-20T10:00:00")
+    dependencies: Optional[List[str]] = Field([], example=[])
+
+class TaskResponse(BaseModel):
+    task_id: str
+    title: str
+    description: str
+    assigned_agent: Optional[str]
+    created_by: str
+    status: str
+    priority: str
+    created_at: str
+    updated_at: str
+    progress: float
+
+class SendMessageRequest(BaseModel):
+    recipient: str = Field(..., example="agent-uuid-or-ALL")
+    content: str = Field(..., example="Please help me with this task")
+    message_type: str = Field("request", example="request")
+    requires_response: bool = Field(False)
+
+class SystemStatsResponse(BaseModel):
+    total_agents: int
+    active_agents: int
+    available_models: int
+    available_tools: int
+    total_queued_messages: int
+    active_conversations: int
 
 # --- Application Lifecycle ---
 @asynccontextmanager
 async def lifespan(app: FastAPI):
     logger.info("Application startup sequence initiated.")
+    
+    # Initialize core services
     db_manager = DatabaseManager()
     init_db()
     app.state.db_manager = db_manager
+    
     tool_manager = ToolManager()
     app.state.tool_manager = tool_manager
+    
     llm_provider = LLMProvider()
     app.state.llm_provider = llm_provider
+    
+    # Initialize communication and coordination services
+    message_broker = MessageBroker(db_manager)
+    await message_broker.start()
+    app.state.message_broker = message_broker
+    
+    task_scheduler = TaskScheduler(db_manager, message_broker)
+    await task_scheduler.start()
+    app.state.task_scheduler = task_scheduler
+    
+    # Initialize enhanced agent manager
     app.state.agent_manager = AgentManager(
         llm_provider=llm_provider, 
         db_manager=db_manager,
-        tool_manager=tool_manager
+        tool_manager=tool_manager,
+        message_broker=message_broker,
+        task_scheduler=task_scheduler
     )
+    
     logger.info("Application startup complete.")
     yield
+    
     logger.info("Application shutdown sequence initiated.")
+    await message_broker.stop()
+    await task_scheduler.stop()
     db_manager.close_all_connections()
     logger.info("Shutdown complete.")
 
@@ .. @@
 app = FastAPI(
     title="MINI S Autonomous AI System",
-    description="Backend server for managing tool-aware, persistent AI agents.",
-    version="0.6.0", # Version updated for tool listing
+    description="Enhanced backend server for managing collaborative, autonomous AI agents with multi-modal capabilities.",
+    version="1.0.0",
     lifespan=lifespan
 )
 
@@ .. @@
 @app.post("/api/v1/agents", response_model=AgentConfig, status_code=201, tags=["Agent Management"])
 async def create_agent(request: CreateAgentRequest):
     manager = app.state.agent_manager
     new_agent = manager.create_agent(
-        name=request.name, role=request.role, model_id=request.model_id,
-        allowed_tool_names=request.allowed_tool_names
+        name=request.name, 
+        role=request.role, 
+        model_id=request.model_id,
+        allowed_tool_names=request.allowed_tool_names,
+        autonomy_level=request.autonomy_level,
+        communication_rights=request.communication_rights,
+        memory_scope=request.memory_scope
     )
     return new_agent.to_dict()
 
@@ .. @@
 @app.post("/api/v1/agents/{agent_id}/think", response_model=AgentThinkResponse, tags=["Agent Interaction"])
 async def agent_think(agent_id: str, request: AgentThinkRequest):
     agent = app.state.agent_manager.get_agent(agent_id)
     if not agent: raise HTTPException(status_code=404, detail="Agent not found.")
-    response_text = agent.think(user_prompt=request.prompt)
-    return AgentThinkResponse(agent_id=agent_id, response=response_text)
+    
+    try:
+        response_text = agent.think(
+            user_prompt=request.prompt, 
+            max_iterations=request.max_iterations
+        )
+        return AgentThinkResponse(
+            agent_id=agent_id, 
+            response=response_text,
+            iterations_used=request.max_iterations  # Could track actual iterations used
+        )
+    except Exception as e:
+        raise HTTPException(status_code=500, detail=f"Agent thinking failed: {str(e)}")
+
+# -- Agent Control Endpoints --
+@app.post("/api/v1/agents/{agent_id}/start", tags=["Agent Control"])
+async def start_agent(agent_id: str):
+    """Start an agent (activate it for processing)"""
+    manager = app.state.agent_manager
+    if manager.start_agent(agent_id):
+        return {"message": f"Agent {agent_id} started successfully"}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to start agent")
+
+@app.post("/api/v1/agents/{agent_id}/stop", tags=["Agent Control"])
+async def stop_agent(agent_id: str):
+    """Stop an active agent"""
+    manager = app.state.agent_manager
+    if manager.stop_agent(agent_id):
+        return {"message": f"Agent {agent_id} stopped successfully"}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to stop agent")
+
+@app.get("/api/v1/agents/{agent_id}/status", tags=["Agent Control"])
+async def get_agent_status(agent_id: str):
+    """Get detailed status of an agent"""
+    manager = app.state.agent_manager
+    status = manager.get_agent_status(agent_id)
+    if not status["exists"]:
+        raise HTTPException(status_code=404, detail="Agent not found")
+    return status
+
+# -- Task Management Endpoints --
+@app.post("/api/v1/tasks", response_model=TaskResponse, status_code=201, tags=["Task Management"])
+async def create_task(request: CreateTaskRequest):
+    """Create a new task"""
+    scheduler = app.state.task_scheduler
+    
+    # Convert priority string to enum
+    priority_map = {"low": TaskPriority.LOW, "medium": TaskPriority.MEDIUM, "high": TaskPriority.HIGH, "critical": TaskPriority.CRITICAL}
+    priority = priority_map.get(request.priority.lower(), TaskPriority.MEDIUM)
+    
+    # Parse due date if provided
+    due_date = None
+    if request.due_date:
+        from datetime import datetime
+        try:
+            due_date = datetime.fromisoformat(request.due_date.replace('Z', '+00:00'))
+        except ValueError:
+            raise HTTPException(status_code=400, detail="Invalid due_date format. Use ISO format.")
+    
+    task = await scheduler.create_task(
+        title=request.title,
+        description=request.description,
+        created_by="admin",  # Could be extracted from auth context
+        assigned_agent=request.assigned_agent,
+        priority=priority,
+        due_date=due_date,
+        dependencies=request.dependencies
+    )
+    
+    return TaskResponse(**task.to_dict())
+
+@app.get("/api/v1/tasks", response_model=List[TaskResponse], tags=["Task Management"])
+async def list_tasks(status: Optional[str] = None, assigned_agent: Optional[str] = None):
+    """List all tasks with optional filtering"""
+    scheduler = app.state.task_scheduler
+    
+    # Get all tasks (in a real implementation, you'd query the database)
+    all_tasks = list(scheduler.tasks.values())
+    
+    # Apply filters
+    if status:
+        all_tasks = [t for t in all_tasks if t.status.value == status]
+    if assigned_agent:
+        all_tasks = [t for t in all_tasks if t.assigned_agent == assigned_agent]
+    
+    return [TaskResponse(**task.to_dict()) for task in all_tasks]
+
+@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse, tags=["Task Management"])
+async def get_task(task_id: str):
+    """Get a specific task"""
+    scheduler = app.state.task_scheduler
+    if task_id not in scheduler.tasks:
+        raise HTTPException(status_code=404, detail="Task not found")
+    
+    task = scheduler.tasks[task_id]
+    return TaskResponse(**task.to_dict())
+
+@app.post("/api/v1/tasks/{task_id}/assign/{agent_id}", tags=["Task Management"])
+async def assign_task(task_id: str, agent_id: str):
+    """Assign a task to an agent"""
+    scheduler = app.state.task_scheduler
+    if await scheduler.assign_task(task_id, agent_id):
+        return {"message": f"Task {task_id} assigned to agent {agent_id}"}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to assign task")
+
+@app.post("/api/v1/tasks/{task_id}/complete", tags=["Task Management"])
+async def complete_task(task_id: str, result: Optional[str] = None):
+    """Mark a task as completed"""
+    scheduler = app.state.task_scheduler
+    if await scheduler.complete_task(task_id, result):
+        return {"message": f"Task {task_id} marked as completed"}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to complete task")
+
+# -- Communication Endpoints --
+@app.post("/api/v1/agents/{agent_id}/message", tags=["Communication"])
+async def send_message_to_agent(agent_id: str, request: SendMessageRequest):
+    """Send a message to an agent"""
+    broker = app.state.message_broker
+    
+    message = broker.create_message(
+        sender="admin",  # Could be extracted from auth context
+        recipient=request.recipient,
+        content=request.content,
+        message_type=getattr(broker.MessageType, request.message_type.upper(), broker.MessageType.REQUEST),
+        requires_response=request.requires_response
+    )
+    
+    if await broker.send_message(message):
+        return {"message": "Message sent successfully", "message_id": message.id}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to send message")
+
+@app.get("/api/v1/agents/{agent_id}/messages", tags=["Communication"])
+async def get_agent_messages(agent_id: str, limit: int = 50):
+    """Get recent messages for an agent"""
+    broker = app.state.message_broker
+    
+    # This would need to be implemented in the message broker
+    # For now, return a placeholder
+    return {"messages": [], "agent_id": agent_id, "limit": limit}
+
+@app.post("/api/v1/broadcast", tags=["Communication"])
+async def broadcast_message(request: SendMessageRequest):
+    """Broadcast a message to all active agents"""
+    manager = app.state.agent_manager
+    
+    if manager.broadcast_message("admin", request.content, request.message_type):
+        return {"message": "Broadcast sent successfully"}
+    else:
+        raise HTTPException(status_code=400, detail="Failed to send broadcast")
+
+# -- System Information Endpoints --
+@app.get("/api/v1/system/stats", response_model=SystemStatsResponse, tags=["System"])
+async def get_system_stats():
+    """Get comprehensive system statistics"""
+    manager = app.state.agent_manager
+    stats = manager.get_system_stats()
+    
+    return SystemStatsResponse(
+        total_agents=stats.get("total_agents", 0),
+        active_agents=stats.get("active_agents", 0),
+        available_models=stats.get("available_models", 0),
+        available_tools=stats.get("available_tools", 0),
+        total_queued_messages=stats.get("total_queued_messages", 0),
+        active_conversations=stats.get("active_conversations", 0)
+    )
+
+@app.get("/api/v1/system/health", tags=["System"])
+async def health_check():
+    """System health check"""
+    try:
+        # Check database connection
+        db_manager = app.state.db_manager
+        db_manager.execute_query("SELECT 1", fetch='one')
+        
+        # Check if core services are running
+        broker_running = app.state.message_broker._running
+        scheduler_running = app.state.task_scheduler._running
+        
+        return {
+            "status": "healthy",
+            "database": "connected",
+            "message_broker": "running" if broker_running else "stopped",
+            "task_scheduler": "running" if scheduler_running else "stopped",
+            "timestamp": "2025-01-17T10:00:00Z"  # Would use actual timestamp
+        }
+    except Exception as e:
+        raise HTTPException(status_code=503, detail=f"System unhealthy: {str(e)}")
+
+# -- Workshop Mode Endpoints --
+@app.post("/api/v1/workshop/create", tags=["Workshop Mode"])
+async def create_workshop(
+    name: str = Field(..., example="Web App Development"),
+    description: str = Field(..., example="Build a complete web application"),
+    agent_ids: List[str] = Field(..., example=["agent1", "agent2", "agent3"]),
+    leader_id: Optional[str] = Field(None, example="agent1")
+):
+    """Create a new workshop session with multiple agents"""
+    manager = app.state.agent_manager
+    
+    # Create team
+    if manager.create_team(name, agent_ids, leader_id):
+        # Create main workshop task
+        scheduler = app.state.task_scheduler
+        workshop_task = await scheduler.create_task(
+            title=f"Workshop: {name}",
+            description=description,
+            created_by="admin",
+            assigned_agent=leader_id,
+            priority=TaskPriority.HIGH
+        )
+        
+        return {
+            "workshop_id": workshop_task.id,
+            "name": name,
+            "description": description,
+            "team_size": len(agent_ids),
+            "leader": leader_id,
+            "status": "created"
+        }
+    else:
+        raise HTTPException(status_code=400, detail="Failed to create workshop")
 
 # --- Server Execution ---
 if __name__ == "__main__":
-    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
+    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)