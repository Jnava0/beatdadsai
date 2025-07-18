# File: backend/main.py
# Author: Gemini
# Date: July 17, 2024
# Description: The main entry point for the MINI S backend server.
# This file initializes the FastAPI application, manages the LLMProvider lifecycle,
# and defines API endpoints for interacting with the AI models.

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

# --- Import Core Modules ---
# Import our custom LLMProvider to manage AI models.
from llm_provider import LLMProvider

# --- Pydantic Models for API Data Validation ---
# These models define the expected structure for our API requests and responses.
# FastAPI uses them to validate incoming data and to serialize outgoing data.
# It also uses them to auto-generate interactive API documentation.

class GenerationRequest(BaseModel):
    """Defines the structure for a text generation request."""
    model_id: str
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.7

class GenerationResponse(BaseModel):
    """Defines the structure for a text generation response."""
    model_id: str
    generated_text: str
    prompt_used: str


# --- Application Lifecycle Management ---
# The 'lifespan' context manager is the modern way in FastAPI to handle
# setup and teardown logic. It ensures our LLMProvider is initialized
# on startup and can be gracefully shut down if needed.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan events.
    Initializes the LLMProvider on startup.
    """
    print("Application startup...")
    # Initialize the LLMProvider singleton instance. It will load the configuration
    # but will not load the actual models into memory until they are first requested.
    app.state.llm_provider = LLMProvider(config_path="config.yaml")
    print("LLMProvider initialized.")
    yield
    # --- Teardown logic can be placed here (e.g., cleaning up resources) ---
    print("Application shutdown...")


# --- Application Initialization ---
# We pass the lifespan manager to the FastAPI constructor.
app = FastAPI(
    title="MINI S Autonomous AI System",
    description="Backend server for managing and coordinating offline AI agents.",
    version="0.1.0",
    lifespan=lifespan
)


# --- API Endpoints ---

@app.get("/")
async def root():
    """
    Root endpoint for the API.
    Provides a simple status message to confirm the server is running.
    """
    return {"status": "ok", "message": "MINI S Backend is running."}


@app.post("/api/v1/generate", response_model=GenerationResponse)
async def generate_text(request: GenerationRequest):
    """
    Handles a request to generate text using a specified local LLM.

    This endpoint takes a model_id and a prompt, then uses the LLMProvider
    to generate a response. It includes robust error handling.
    """
    try:
        # Access the provider instance from the application state.
        llm_provider = app.state.llm_provider
        
        # Call the provider's generate method with the request parameters.
        generated_text = llm_provider.generate(
            model_id=request.model_id,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        # Return a successful response using our Pydantic model.
        return GenerationResponse(
            model_id=request.model_id,
            generated_text=generated_text,
            prompt_used=request.prompt
        )
    except FileNotFoundError as e:
        # Handle cases where the config file is missing.
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail="Server configuration error: config.yaml not found.")
    except ValueError as e:
        # Handle invalid model IDs or other value-related errors from the provider.
        print(f"ERROR: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ImportError as e:
        # Handle missing optional dependencies (e.g., transformers, llama-cpp-python).
        print(f"ERROR: {e}")
        raise HTTPException(status_code=501, detail=f"Dependency error: {e}")
    except Exception as e:
        # Catch any other unexpected errors during model loading or generation.
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


# --- Server Execution ---
if __name__ == "__main__":
    print("Starting MINI S backend server...")
    # Note: The host "0.0.0.0" makes the server accessible on your network.
    # For local development, you can also use "127.0.0.1".
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
