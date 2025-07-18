# File: backend/agent.py
# Author: Gemini
# Date: July 17, 2025
# Description: Defines the advanced, tool-aware AI Agent class.
# This version implements a ReAct (Reason+Act) loop for autonomous tool use.

import uuid
import json
import logging
from typing import Dict, Any, List, Optional

from llm_provider import LLMProvider
from tools.base_tool import Tool
from tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)

class Agent:
    """
    An advanced, tool-aware agent that can reason about problems,
    select and execute tools, and formulate answers based on observations.
    """

    def __init__(
        self,
        name: str,
        role: str,
        model_id: str,
        llm_provider: LLMProvider,
        tool_manager: ToolManager,
        allowed_tool_names: List[str] = None,
        agent_id: str = None
    ):
        """
        Initializes the tool-aware agent.

        Args:
            name (str): The name of the agent.
            role (str): The specific role or function of the agent.
            model_id (str): The ID of the language model to be used.
            llm_provider (LLMProvider): The central provider for LLM access.
            tool_manager (ToolManager): The manager that provides tool instances.
            allowed_tool_names (List[str], optional): A list of tool names this agent
                is permitted to use. If None, it can use all available tools.
            agent_id (str, optional): A pre-existing ID for the agent.
        """
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.role = role
        self.model_id = model_id
        self.llm_provider = llm_provider
        self.tool_manager = tool_manager
        
        # Determine the agent's toolset
        if allowed_tool_names:
            self.tools = [t for t in tool_manager.get_all_tools() if t.name in allowed_tool_names]
        else:
            self.tools = tool_manager.get_all_tools()
            
        self.system_prompt = self._create_system_prompt()
        
        logger.info(f"Agent '{self.name}' created with {len(self.tools)} tools.")

    def _create_system_prompt(self) -> str:
        """Constructs the system prompt, including descriptions of available tools."""
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
        
        return (
            f"You are {self.name}, an advanced AI agent. Your role is: {self.role}.\n\n"
            "To solve problems, you can use a thinking process. You will be given a user query and a history of your previous actions.\n"
            "Based on this, you must decide on your next action. You have two choices:\n"
            "1. **Use a tool**: If you need more information, respond with a JSON object specifying the tool and its arguments. The format MUST be:\n"
            '```json\n{"tool": "tool_name", "args": {"arg_name": "value"}}\n```\n'
            "2. **Provide a final answer**: If you have enough information, provide the final answer as a plain string.\n\n"
            "Here are the tools available to you:\n"
            f"{tool_descriptions if self.tools else 'No tools available.'}\n\n"
            "Begin your thought process now."
        )

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parses the LLM's response to find a tool call or a final answer."""
        try:
            # Look for a JSON block for the tool call
            json_block_match = response[response.find('```json'):response.rfind('```') + 3]
            if json_block_match:
                json_content = json_block_match.strip('```json').strip()
                parsed = json.loads(json_content)
                if 'tool' in parsed and 'args' in parsed:
                    return {"type": "tool_call", "data": parsed}
        except (json.JSONDecodeError, IndexError):
            # Not a valid tool call, or no JSON block found
            pass
        
        # If no valid tool call is found, assume it's the final answer.
        return {"type": "final_answer", "data": response}

    def think(self, user_prompt: str, max_iterations: int = 5) -> str:
        """
        The core ReAct (Reason + Act) thinking loop of the agent.

        Args:
            user_prompt (str): The initial query from the user.
            max_iterations (int): The maximum number of tool-use cycles to prevent infinite loops.

        Returns:
            str: The final answer from the agent.
        """
        history = f"User Query: {user_prompt}\n"
        
        for i in range(max_iterations):
            logger.info(f"Agent '{self.name}' starting iteration {i+1}/{max_iterations}")
            
            full_prompt = f"{self.system_prompt}\n\n--- Conversation History ---\n{history}\n\nYour Action:"
            
            # 1. REASON: Agent decides on the next action
            llm_response = self.llm_provider.generate(self.model_id, full_prompt)
            parsed_action = self._parse_llm_response(llm_response)
            
            # 2. ACT: Agent executes the action
            if parsed_action["type"] == "final_answer":
                logger.info(f"Agent '{self.name}' decided on a final answer.")
                return parsed_action["data"]
            
            if parsed_action["type"] == "tool_call":
                tool_name = parsed_action["data"]["tool"]
                tool_args = parsed_action["data"]["args"]
                
                tool = self.tool_manager.get_tool(tool_name)
                if tool and tool in self.tools:
                    try:
                        logger.info(f"Agent '{self.name}' executing tool '{tool_name}' with args: {tool_args}")
                        tool_result = tool.execute(**tool_args)
                        history += f"\nAction: Used tool '{tool_name}' with arguments {tool_args}.\nObservation: {tool_result}\n"
                    except Exception as e:
                        logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
                        history += f"\nAction: Used tool '{tool_name}'.\nObservation: Error executing tool: {e}\n"
                else:
                    logger.warning(f"Agent '{self.name}' tried to use unavailable tool: {tool_name}")
                    history += f"\nAction: Tried to use tool '{tool_name}'.\nObservation: Error: Tool not available.\n"
        
        logger.warning(f"Agent '{self.name}' reached max iterations. Returning current history.")
        return "I could not determine a final answer within the allowed number of steps."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "model_id": self.model_id,
            "allowed_tools": [tool.name for tool in self.tools]
        }

# --- Example Usage ---
if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()

    try:
        print("--- Testing Tool-Aware Agent ---")
        provider = LLMProvider(config_path="config.yaml")
        tool_mgr = ToolManager()
        
        # Create a researcher agent that can use the web scraper
        researcher_agent = Agent(
            name="WebResearcher",
            role="An AI agent that answers questions by finding information on the web.",
            model_id='qwen-7b-chat-gguf', # Use a model good at following JSON format
            llm_provider=provider,
            tool_manager=tool_mgr,
            allowed_tool_names=["web_scraper"]
        )
        
        print("\n--- Agent System Prompt ---")
        print(researcher_agent.system_prompt)
        
        # Ask a question that requires web access
        query = "What is the main purpose of the James Webb Space Telescope according to Wikipedia?"
        print(f"\n--- Starting 'think' loop for query: {query} ---")
        
        final_answer = researcher_agent.think(query)
        
        print("\n--- Final Answer Received ---")
        print(final_answer)

    except Exception as e:
        logger.critical("An error occurred during agent testing.", exc_info=True)
