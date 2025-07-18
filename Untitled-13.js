// File: frontend/api.js
// Author: Gemini
// Date: July 17, 2024
// Description: A dedicated module for all API communications with the MINI S backend.
// This centralizes fetch logic, making the application easier to maintain and debug.

const API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * A generic fetch wrapper to handle common logic like setting headers,
 * and handling HTTP errors.
 * @param {string} endpoint - The API endpoint to call (e.g., '/agents').
 * @param {object} [options={}] - The options object for the fetch call (method, body, etc.).
 * @param {string} [responseType='json'] - The expected response type ('json' or 'text').
 * @returns {Promise<any>} The response from the API.
 * @throws {Error} If the network request fails or the API returns an error status.
 */
async function apiRequest(endpoint, options = {}, responseType = 'json') {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
        headers: {
            'Accept': responseType === 'json' ? 'application/json' : 'text/plain',
        },
        ...options,
    };
    
    // Add Content-Type header for POST/PUT requests with a body
    if (options.body) {
        config.headers['Content-Type'] = 'application/json';
    }

    try {
        const response = await fetch(url, config);

        if (!response.ok) {
            const errorText = await response.text();
            let errorDetail = errorText;
            try {
                // Try to parse as JSON for detailed error messages from FastAPI
                const errorData = JSON.parse(errorText);
                errorDetail = errorData.detail || errorText;
            } catch (e) {
                // Not a JSON error, use the raw text
            }
            throw new Error(errorDetail || `HTTP error! Status: ${response.status}`);
        }
        
        if (response.status === 204) {
            return null;
        }

        if (responseType === 'text') {
            return await response.text();
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API request failed for endpoint '${endpoint}':`, error);
        throw error;
    }
}

// --- Agent Management Functions ---

export function getAgents() {
    return apiRequest('/agents');
}

export function getAgent(agentId) {
    return apiRequest(`/agents/${agentId}`);
}

export function createAgent(name, role, modelId) {
    return apiRequest('/agents', {
        method: 'POST',
        body: JSON.stringify({ name, role, model_id: modelId }),
    });
}

export function deleteAgent(agentId) {
    return apiRequest(`/agents/${agentId}`, {
        method: 'DELETE',
    });
}

// --- Agent Interaction Functions ---

export function agentThink(agentId, prompt, generationConfig = {}) {
    return apiRequest(`/agents/${agentId}/think`, {
        method: 'POST',
        body: JSON.stringify({ prompt, generation_config: generationConfig }),
    });
}

// --- System & Utility Functions ---

/**
 * Fetches the system logs from the backend.
 * @returns {Promise<string>} A promise that resolves to the raw log text.
 */
export function getSystemLogs() {
    return apiRequest('/logs', {}, 'text');
}


export async function getAvailableModels() {
    console.warn("getAvailableModels() is using placeholder data.");
    return ['qwen-7b-chat-gguf', 'llama2-7b-chat-hf']; 
}