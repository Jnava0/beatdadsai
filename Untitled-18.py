# File: backend/tools/tool_manager.py
# Author: Gemini
# Date: July 17, 2025
# Description: A manager for discovering, loading, and providing access to all agent tools.

import os
import importlib
import inspect
import logging
from typing import Dict, List, Optional

from tools.base_tool import Tool

logger = logging.getLogger(__name__)

class ToolManager:
    """
    A singleton class that dynamically discovers and manages all available tools.
    It scans the 'tools' directory for any class that inherits from the base Tool class,
    instantiates it, and makes it available to the agents.
    """
    _instance = None
    _tools: Dict[str, Tool] = {}

    def __new__(cls):
        if cls._instance is None:
            logger.info("Initializing ToolManager singleton.")
            cls._instance = super().__new__(cls)
            cls._instance._discover_and_load_tools()
        return cls._instance

    def _discover_and_load_tools(self):
        """
        Scans the 'tools' directory for Python files, imports them, and
        instantiates any classes that are subclasses of the base Tool.
        """
        if self._tools: # Ensure this runs only once
            return

        tools_dir = os.path.dirname(__file__)
        logger.info(f"Discovering tools in directory: {tools_dir}")

        for filename in os.listdir(tools_dir):
            # Look for Python files, excluding this file and the base class file.
            if filename.endswith(".py") and not filename.startswith("_") and "base_tool" not in filename and "tool_manager" not in filename:
                module_name = f"tools.{filename[:-3]}"
                try:
                    module = importlib.import_module(module_name)
                    
                    # Find all classes within the imported module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        # Check if the class is a subclass of Tool and not Tool itself
                        if issubclass(obj, Tool) and obj is not Tool:
                            tool_instance = obj() # Instantiate the tool
                            if tool_instance.name in self._tools:
                                logger.warning(f"Duplicate tool name '{tool_instance.name}' found. Overwriting.")
                            self._tools[tool_instance.name] = tool_instance
                            logger.info(f"Successfully loaded tool: '{tool_instance.name}'")

                except Exception as e:
                    logger.error(f"Failed to load tool from {module_name}: {e}", exc_info=True)
        
        if not self._tools:
            logger.warning("No tools were discovered or loaded.")

    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Retrieves a specific tool by its name.
        
        Args:
            name (str): The name of the tool to retrieve.
            
        Returns:
            Optional[Tool]: The tool instance if found, otherwise None.
        """
        return self._tools.get(name)

    def get_all_tools(self) -> List[Tool]:
        """Returns a list of all loaded tool instances."""
        return list(self._tools.values())

    def get_all_tool_descriptions(self) -> str:
        """
        Generates a formatted string of all tool names and descriptions.
        This is crucial for injecting the available tools into the agent's prompt.
        
        Returns:
            str: A formatted, human-readable string describing all available tools.
        """
        if not self._tools:
            return "No tools available."

        descriptions = ["You have access to the following tools:"]
        for tool in self.get_all_tools():
            descriptions.append(f"- Tool: {tool.name}\n  Description: {tool.description}")
        
        return "\n".join(descriptions)

# --- Example Usage ---
if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()

    print("--- Testing ToolManager ---")
    tool_manager = ToolManager()
    
    print("\n--- All Tool Descriptions ---")
    all_descriptions = tool_manager.get_all_tool_descriptions()
    print(all_descriptions)
    
    print("\n--- Retrieving a specific tool ---")
    scraper_tool = tool_manager.get_tool("web_scraper")
    if scraper_tool:
        print(f"Found tool: {scraper_tool.name}")
        # Test execution via the manager
        result = scraper_tool.execute(url="https://example.com")
        print("Execution result:", result)
    else:
        print("web_scraper tool not found.")
