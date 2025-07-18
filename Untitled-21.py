# File: backend/main.py
# Author: Gemini
# Date: July 17, 2025
# Description: Main API entry point, now with an endpoint to list available tools.

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
from contextlib import asynccontextmanager
import logging
import uuid

# --- Import Core Modules ---
from llm_provider import LLMProvider
from agent_manager import AgentManager
from logging_config import setup_logging
from database import DatabaseManager, init_db
from tools.tool_manager import ToolManager

# --- Setup ---
setup_logging()
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
class ToolConfig(BaseModel):
    name: str
    description: str

class AgentConfig(BaseModel):
    agent_id: uuid.UUID
    name: str
    role: str
    model_id: str
    allowed_tools: List[str]

class CreateAgentRequest(BaseModel):
    name: str = Field(..., example="WebResearcher")
    role: str = Field(..., example="An AI that answers questions by browsing the web.")
    model_id: str = Field(..., example="qwen-7b-chat-gguf")
    allowed_tool_names: Optional[List[str]] = Field(None, example=["web_scraper"])

class AgentThinkRequest(BaseModel):
    prompt: str

class AgentThinkResponse(BaseModel):
    agent_id: str
    response: str

# --- Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup sequence initiated.")
    db_manager = DatabaseManager()
    init_db()
    app.state.db_manager = db_manager
    tool_manager = ToolManager()
    app.state.tool_manager = tool_manager
    llm_provider = LLMProvider()
    app.state.llm_provider = llm_provider
    app.state.agent_manager = AgentManager(
        llm_provider=llm_provider, 
        db_manager=db_manager,
        tool_manager=tool_manager
    )
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutdown sequence initiated.")
    db_manager.close_all_connections()
    logger.info("Shutdown complete.")

# --- FastAPI App ---
app = FastAPI(
    title="MINI S Autonomous AI System",
    description="Backend server for managing tool-aware, persistent AI agents.",
    version="0.6.0", # Version updated for tool listing
    lifespan=lifespan
)

# --- API Endpoints ---

# -- System Endpoints --
@app.get("/api/v1/tools", response_model=List[ToolConfig], tags=["System"])
async def list_available_tools():
    """Lists all tools discovered and loaded by the ToolManager."""
    tool_manager = app.state.tool_manager
    # Use the to_dict() method from our base tool class for serialization
    return [tool.to_dict() for tool in tool_manager.get_all_tools()]

# All other endpoints remain the same...
@app.get("/", tags=["Status"])
async def root():
    return {"status": "ok", "message": "MINI S Backend is running."}

@app.post("/api/v1/agents", response_model=AgentConfig, status_code=201, tags=["Agent Management"])
async def create_agent(request: CreateAgentRequest):
    manager = app.state.agent_manager
    new_agent = manager.create_agent(
        name=request.name, role=request.role, model_id=request.model_id,
        allowed_tool_names=request.allowed_tool_names
    )
    return new_agent.to_dict()

@app.get("/api/v1/agents", response_model=List[AgentConfig], tags=["Agent Management"])
async def list_agents():
    return app.state.agent_manager.list_agents()

@app.get("/api/v1/agents/{agent_id}", response_model=AgentConfig, tags=["Agent Management"])
async def get_agent(agent_id: str):
    agent = app.state.agent_manager.get_agent(agent_id)
    if not agent: raise HTTPException(status_code=404, detail="Agent not found.")
    return agent.to_dict()

@app.delete("/api/v1/agents/{agent_id}", status_code=204, tags=["Agent Management"])
async def delete_agent(agent_id: str):
    if not app.state.agent_manager.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found.")
    return None

@app.post("/api/v1/agents/{agent_id}/think", response_model=AgentThinkResponse, tags=["Agent Interaction"])
async def agent_think(agent_id: str, request: AgentThinkRequest):
    agent = app.state.agent_manager.get_agent(agent_id)
    if not agent: raise HTTPException(status_code=404, detail="Agent not found.")
    response_text = agent.think(user_prompt=request.prompt)
    return AgentThinkResponse(agent_id=agent_id, response=response_text)

# --- Server Execution ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
