# File: backend/main.py
# Author: Gemini
# Date: July 17, 2024
# Description: The main entry point for the MINI S backend server.
# This file initializes the FastAPI application, manages the application lifecycle
# (LLMProvider, AgentManager), and defines a full suite of RESTful API endpoints
# for interacting with AI models and agents.

from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
from contextlib import asynccontextmanager

# --- Import Core Modules ---
from llm_provider import LLMProvider
from agent_manager import AgentManager
from agent import Agent

# --- Pydantic Models for API Data Validation ---

class AgentConfig(BaseModel):
    """Defines the structure for an agent's configuration."""
    agent_id: str
    name: str
    role: str
    model_id: str

class CreateAgentRequest(BaseModel):
    """Defines the structure for a request to create a new agent."""
    name: str = Field(..., example="PythonExpert")
    role: str = Field(..., example="A world-class Python programmer who provides expert advice.")
    model_id: str = Field(..., example="qwen-7b-chat-gguf")

class AgentThinkRequest(BaseModel):
    """Defines the structure for a request for an agent to 'think'."""
    prompt: str
    generation_config: Optional[Dict[str, Any]] = None

class AgentThinkResponse(BaseModel):
    """Defines the structure for the response from an agent's 'think' process."""
    agent_id: str
    response: str

class GenerationRequest(BaseModel):
    """Defines the structure for a direct text generation request."""
    model_id: str
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class GenerationResponse(BaseModel):
    """Defines the structure for a direct text generation response."""
    model_id: str
    generated_text: str
    prompt_used: str

# --- Application Lifecycle Management ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan events.
    Initializes singleton services on startup.
    """
    print("Application startup...")
    # Initialize the LLMProvider singleton instance.
    llm_provider = LLMProvider(config_path="config.yaml")
    app.state.llm_provider = llm_provider
    print("LLMProvider initialized.")
    
    # Initialize the AgentManager singleton, passing the provider instance.
    app.state.agent_manager = AgentManager(llm_provider=llm_provider)
    print("AgentManager initialized.")
    
    yield
    
    print("Application shutdown...")


# --- Application Initialization ---
app = FastAPI(
    title="MINI S Autonomous AI System",
    description="Backend server for managing and coordinating offline AI agents.",
    version="0.2.0", # Version updated to reflect new features
    lifespan=lifespan
)


# --- API Endpoints ---

# -- Root Endpoint --
@app.get("/", tags=["Status"])
async def root():
    """Provides a simple status message to confirm the server is running."""
    return {"status": "ok", "message": "MINI S Backend is running."}

# -- Agent Management Endpoints --
@app.post("/api/v1/agents", response_model=AgentConfig, status_code=201, tags=["Agent Management"])
async def create_agent(request: CreateAgentRequest):
    """Creates a new AI agent and registers it with the system."""
    try:
        manager = app.state.agent_manager
        new_agent = manager.create_agent(
            name=request.name,
            role=request.role,
            model_id=request.model_id
        )
        return new_agent.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

@app.get("/api/v1/agents", response_model=List[AgentConfig], tags=["Agent Management"])
async def list_agents():
    """Lists all currently active agents in the system."""
    manager = app.state.agent_manager
    return manager.list_agents()

@app.get("/api/v1/agents/{agent_id}", response_model=AgentConfig, tags=["Agent Management"])
async def get_agent(agent_id: str):
    """Retrieves detailed configuration for a specific agent."""
    manager = app.state.agent_manager
    agent = manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")
    return agent.to_dict()

@app.delete("/api/v1/agents/{agent_id}", status_code=204, tags=["Agent Management"])
async def delete_agent(agent_id: str):
    """Deletes an agent from the system."""
    manager = app.state.agent_manager
    if not manager.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")
    return None # Return no content on successful deletion

# -- Agent Interaction Endpoint --
@app.post("/api/v1/agents/{agent_id}/think", response_model=AgentThinkResponse, tags=["Agent Interaction"])
async def agent_think(agent_id: str, request: AgentThinkRequest):
    """Triggers an agent's thinking process with a given prompt."""
    manager = app.state.agent_manager
    agent = manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID '{agent_id}' not found.")
    
    try:
        response_text = agent.think(
            user_prompt=request.prompt,
            generation_config=request.generation_config
        )
        return AgentThinkResponse(agent_id=agent_id, response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during agent thinking: {e}")

# -- Direct LLM Generation Endpoint (for testing/utility) --
@app.post("/api/v1/generate", response_model=GenerationResponse, tags=["LLM Utility"])
async def generate_text(request: GenerationRequest):
    """Directly generates text using a specified local LLM, bypassing the agent structure."""
    try:
        llm_provider = app.state.llm_provider
        generated_text = llm_provider.generate(
            model_id=request.model_id,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        return GenerationResponse(model_id=request.model_id, generated_text=generated_text, prompt_used=request.prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


# --- Server Execution ---
if __name__ == "__main__":
    print("Starting MINI S backend server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
