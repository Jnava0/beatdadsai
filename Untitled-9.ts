// File: frontend/api.js
// Author: Gemini
// Date: July 17, 2024
// Description: A dedicated module for all API communications with the MINI S backend.
// This centralizes fetch logic, making the application easier to maintain and debug.

const API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * A generic fetch wrapper to handle common logic like setting headers,
 * parsing JSON, and handling HTTP errors.
 * @param {string} endpoint - The API endpoint to call (e.g., '/agents').
 * @param {object} [options={}] - The options object for the fetch call (method, body, etc.).
 * @returns {Promise<any>} The JSON response from the API.
 * @throws {Error} If the network request fails or the API returns an error status.
 */
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        ...options,
    };

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            // Try to parse the error body for a more detailed message from the backend.
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || `HTTP error! Status: ${response.status}`);
        }
        
        // For 204 No Content, there is no body to parse.
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error(`API request failed for endpoint '${endpoint}':`, error);
        // Re-throw the error so the calling function can handle it, e.g., to show a UI notification.
        throw error;
    }
}

// --- Agent Management Functions ---

/**
 * Fetches the list of all agents from the backend.
 * @returns {Promise<Array<object>>} A promise that resolves to an array of agent configuration objects.
 */
export function getAgents() {
    return apiRequest('/agents');
}

/**
 * Retrieves a single agent by its ID.
 * @param {string} agentId - The ID of the agent to fetch.
 * @returns {Promise<object>} A promise that resolves to the agent's configuration object.
 */
export function getAgent(agentId) {
    return apiRequest(`/agents/${agentId}`);
}

/**
 * Sends a request to create a new agent.
 * @param {string} name - The name of the new agent.
 * @param {string} role - The role description for the new agent.
 * @param {string} modelId - The model ID the agent will use.
 * @returns {Promise<object>} A promise that resolves to the newly created agent's configuration.
 */
export function createAgent(name, role, modelId) {
    return apiRequest('/agents', {
        method: 'POST',
        body: JSON.stringify({ name, role, model_id: modelId }),
    });
}

/**
 * Sends a request to delete an agent.
 * @param {string} agentId - The ID of the agent to delete.
 * @returns {Promise<null>} A promise that resolves when the agent is successfully deleted.
 */
export function deleteAgent(agentId) {
    return apiRequest(`/agents/${agentId}`, {
        method: 'DELETE',
    });
}


// --- Agent Interaction Functions ---

/**
 * Sends a prompt to a specific agent to get a response.
 * @param {string} agentId - The ID of the agent to interact with.
 * @param {string} prompt - The user prompt for the agent.
 * @param {object} [generationConfig] - Optional configuration for the LLM (e.g., max_tokens).
 * @returns {Promise<object>} A promise that resolves to the agent's response object.
 */
export function agentThink(agentId, prompt, generationConfig = {}) {
    return apiRequest(`/agents/${agentId}/think`, {
        method: 'POST',
        body: JSON.stringify({ prompt, generation_config: generationConfig }),
    });
}

// --- LLM Utility Functions ---

/**
 * Fetches the list of available models from the backend.
 * NOTE: This endpoint doesn't exist yet, but we are designing the API module
 * to be forward-compatible. We will add the endpoint to the backend later.
 * For now, we will mock this or derive it from the agents list.
 * @returns {Promise<Array<string>>} A promise that resolves to a list of available model IDs.
 */
export async function getAvailableModels() {
    // Placeholder: In a future step, we'll create a dedicated backend endpoint for this.
    // For now, we can't get this info directly, so we'll return a hardcoded list
    // or infer from a config file if we had one on the frontend.
    console.warn("getAvailableModels() is using placeholder data.");
    // This would ideally come from an endpoint like GET /api/v1/models
    return ['qwen-7b-chat-gguf', 'llama2-7b-chat-hf']; 
}
