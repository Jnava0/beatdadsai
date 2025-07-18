# File: backend/main.py
# Author: Gemini
# Date: July 17, 2024
# Description: The main entry point for the MINI S backend server.
# This file initializes the FastAPI application and defines the root endpoint.

# Import the FastAPI framework
from fastapi import FastAPI
import uvicorn

# --- Application Initialization ---
# Create an instance of the FastAPI class. This instance will be the main
# point of interaction for all of our API.
# We add metadata like title and version for documentation purposes.
app = FastAPI(
    title="MINI S Autonomous AI System",
    description="Backend server for managing and coordinating offline AI agents.",
    version="0.1.0",
)


# --- API Endpoints ---
# The @app.get("/") decorator tells FastAPI that the function below
# is in charge of handling requests that go to the root URL ("/").
@app.get("/")
async def root():
    """
    Root endpoint for the API.
    Provides a simple status message to confirm the server is running.
    """
    return {"status": "ok", "message": "MINI S Backend is running."}


# --- Server Execution ---
# This block allows the script to be run directly using `python main.py`.
# It starts the Uvicorn server, which is an ASGI server needed to run FastAPI.
# - `host="0.0.0.0"` makes the server accessible on the local network.
# - `port=8000` specifies the port to run on.
# - `reload=True` enables auto-reloading when code changes, which is useful for development.
if __name__ == "__main__":
    print("Starting MINI S backend server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

