// File: frontend/agent-view.js
// Author: Gemini
// Date: July 17, 2024
// Description: Manages all UI and logic for the Agent Manager view.
// This includes rendering agents, handling creation, deletion, and interaction.

import { getAgents, createAgent, deleteAgent, agentThink, getAvailableModels } from './api.js';

// --- DOM Element References ---
const agentViewContainer = document.getElementById('view-agents');
let modelsCache = []; // Cache for available models to avoid repeated API calls.

/**
 * Creates the HTML for a single agent card.
 * @param {object} agent - The agent configuration object.
 * @returns {string} The HTML string for the agent card.
 */
function createAgentCardHTML(agent) {
    return `
        <div id="agent-card-${agent.agent_id}" class="bg-gray-800 border border-gray-700 rounded-lg p-5 flex flex-col transition-shadow hover:shadow-lg hover:shadow-cyan-500/10">
            <div class="flex-grow">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-xl font-bold text-white">${agent.name}</h3>
                    <span class="text-xs font-mono bg-gray-700 text-cyan-400 px-2 py-1 rounded">${agent.model_id}</span>
                </div>
                <p class="text-gray-400 text-sm mb-4 h-20 overflow-y-auto">${agent.role}</p>
                <p class="text-xs font-mono text-gray-500">ID: ${agent.agent_id}</p>
            </div>
            <div class="mt-5 pt-4 border-t border-gray-700 flex justify-end space-x-3">
                <button data-agent-id="${agent.agent_id}" class="btn-delete-agent bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors">Delete</button>
                <button data-agent-id="${agent.agent_id}" data-agent-name="${agent.name}" class="btn-chat-agent bg-cyan-600 hover:bg-cyan-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors">Chat</button>
            </div>
        </div>
    `;
}

/**
 * Fetches agents from the API and renders them on the page.
 */
async function renderAgentList() {
    const agentListContainer = document.getElementById('agent-list-container');
    if (!agentListContainer) return;

    try {
        agentListContainer.innerHTML = '<p>Loading agents...</p>';
        const agents = await getAgents();
        
        if (agents.length === 0) {
            agentListContainer.innerHTML = '<p class="text-gray-400 text-center col-span-full">No agents found. Create one to get started!</p>';
        } else {
            agentListContainer.innerHTML = agents.map(createAgentCardHTML).join('');
        }
    } catch (error) {
        agentListContainer.innerHTML = `<p class="text-red-400 text-center col-span-full">Error loading agents: ${error.message}</p>`;
    }
}

/**
 * Renders a modal dialog for creating or interacting with agents.
 * @param {object} config - Configuration for the modal.
 * @param {string} config.title - The title of the modal.
 * @param {string} config.bodyHTML - The HTML content for the modal's body.
 * @param {string} config.footerHTML - The HTML content for the modal's footer.
 */
function showModal({ title, bodyHTML, footerHTML }) {
    // Remove any existing modal first
    const existingModal = document.getElementById('app-modal');
    if (existingModal) existingModal.remove();

    const modalHTML = `
        <div id="app-modal" class="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
            <div class="bg-gray-800 rounded-lg shadow-2xl w-full max-w-lg border border-gray-700">
                <div class="p-5 border-b border-gray-700 flex justify-between items-center">
                    <h3 class="text-xl font-bold text-white">${title}</h3>
                    <button id="modal-close-btn" class="text-gray-400 hover:text-white">&times;</button>
                </div>
                <div class="p-5">${bodyHTML}</div>
                <div class="p-5 bg-gray-800 border-t border-gray-700 flex justify-end space-x-3">${footerHTML}</div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    document.getElementById('modal-close-btn').addEventListener('click', () => {
        document.getElementById('app-modal').remove();
    });
}

/**
 * Shows the modal for creating a new agent.
 */
async function showCreateAgentModal() {
    // Fetch available models if not already cached
    if (modelsCache.length === 0) {
        try {
            modelsCache = await getAvailableModels();
        } catch (error) {
            alert(`Could not fetch available models: ${error.message}`);
            return;
        }
    }

    const modelOptions = modelsCache.map(modelId => `<option value="${modelId}">${modelId}</option>`).join('');

    showModal({
        title: 'Create New Agent',
        bodyHTML: `
            <form id="create-agent-form">
                <div class="mb-4">
                    <label for="agent-name" class="block text-sm font-medium text-gray-300 mb-1">Name</label>
                    <input type="text" id="agent-name" required class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:ring-cyan-500 focus:border-cyan-500" placeholder="e.g., CodeCrafter">
                </div>
                <div class="mb-4">
                    <label for="agent-role" class="block text-sm font-medium text-gray-300 mb-1">Role/Purpose</label>
                    <textarea id="agent-role" required rows="4" class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:ring-cyan-500 focus:border-cyan-500" placeholder="A world-class Python programmer..."></textarea>
                </div>
                <div>
                    <label for="agent-model" class="block text-sm font-medium text-gray-300 mb-1">Language Model</label>
                    <select id="agent-model" required class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:ring-cyan-500 focus:border-cyan-500">
                        ${modelOptions}
                    </select>
                </div>
            </form>
        `,
        footerHTML: `
            <button id="modal-cancel-btn" class="bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 px-4 rounded-lg">Cancel</button>
            <button id="modal-submit-btn" type="submit" form="create-agent-form" class="bg-cyan-600 hover:bg-cyan-700 text-white font-semibold py-2 px-4 rounded-lg">Create Agent</button>
        `
    });

    document.getElementById('modal-cancel-btn').addEventListener('click', () => document.getElementById('app-modal').remove());
    document.getElementById('create-agent-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('agent-name').value;
        const role = document.getElementById('agent-role').value;
        const modelId = document.getElementById('agent-model').value;
        
        const submitBtn = document.getElementById('modal-submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        try {
            await createAgent(name, role, modelId);
            document.getElementById('app-modal').remove();
            await renderAgentList(); // Refresh the list
        } catch (error) {
            alert(`Failed to create agent: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Agent';
        }
    });
}

/**
 * Shows the chat modal for a specific agent.
 * @param {string} agentId - The ID of the agent to chat with.
 * @param {string} agentName - The name of the agent.
 */
function showChatModal(agentId, agentName) {
    showModal({
        title: `Chat with ${agentName}`,
        bodyHTML: `
            <div id="chat-history" class="h-80 overflow-y-auto bg-gray-900 p-4 rounded-lg mb-4 border border-gray-700">
                <!-- Chat messages will be appended here -->
            </div>
            <form id="chat-form">
                <textarea id="chat-prompt" required rows="3" class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white" placeholder="Enter your prompt..."></textarea>
            </form>
        `,
        footerHTML: `
            <button id="modal-cancel-btn" class="bg-gray-600 hover:bg-gray-700 text-white font-semibold py-2 px-4 rounded-lg">Close</button>
            <button id="modal-submit-btn" type="submit" form="chat-form" class="bg-cyan-600 hover:bg-cyan-700 text-white font-semibold py-2 px-4 rounded-lg">Send</button>
        `
    });

    const chatHistory = document.getElementById('chat-history');
    const addMessage = (sender, message) => {
        const messageHTML = `
            <div class="mb-3">
                <p class="font-bold ${sender === 'User' ? 'text-cyan-400' : 'text-purple-400'}">${sender}</p>
                <p class="text-gray-300 whitespace-pre-wrap">${message}</p>
            </div>
        `;
        chatHistory.insertAdjacentHTML('beforeend', messageHTML);
        chatHistory.scrollTop = chatHistory.scrollHeight; // Auto-scroll
    };

    document.getElementById('modal-cancel-btn').addEventListener('click', () => document.getElementById('app-modal').remove());
    document.getElementById('chat-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const promptInput = document.getElementById('chat-prompt');
        const prompt = promptInput.value;
        if (!prompt) return;

        addMessage('User', prompt);
        promptInput.value = ''; // Clear input

        const submitBtn = document.getElementById('modal-submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Thinking...';
        
        try {
            const result = await agentThink(agentId, prompt);
            addMessage(agentName, result.response.trim());
        } catch (error) {
            addMessage('System', `Error: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Send';
        }
    });
}

/**
 * Initializes the Agent Manager view, sets up event listeners.
 */
export function initAgentView() {
    // Set the initial HTML structure for the view
    agentViewContainer.innerHTML = `
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-3xl font-bold text-white">Agent Manager</h2>
            <button id="btn-create-agent" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                + Create Agent
            </button>
        </div>
        <div id="agent-list-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            <!-- Agent cards will be rendered here -->
        </div>
    `;

    // Render the initial list of agents
    renderAgentList();

    // Add event listener for the create agent button
    document.getElementById('btn-create-agent').addEventListener('click', showCreateAgentModal);

    // Add delegated event listeners for delete and chat buttons
    agentViewContainer.addEventListener('click', async (e) => {
        const target = e.target.closest('button');
        if (!target) return;

        const agentId = target.dataset.agentId;

        if (target.classList.contains('btn-delete-agent')) {
            if (confirm(`Are you sure you want to delete agent ${agentId}?`)) {
                try {
                    await deleteAgent(agentId);
                    // Remove the card from the DOM directly for a faster UI response
                    document.getElementById(`agent-card-${agentId}`).remove();
                } catch (error) {
                    alert(`Failed to delete agent: ${error.message}`);
                }
            }
        }

        if (target.classList.contains('btn-chat-agent')) {
            const agentName = target.dataset.agentName;
            showChatModal(agentId, agentName);
        }
    });
}