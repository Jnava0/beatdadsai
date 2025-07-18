# File: backend/tools/base_tool.py
# Author: Gemini
# Date: July 17, 2025
# Description: Defines the abstract base class for all tools available to agents.

from abc import ABC, abstractmethod
from typing import Any, Dict

class Tool(ABC):
    """
    An abstract base class that defines the standard interface for all tools.
    
    Each tool must have a name, a description of what it does and what its
    input should be, and an execute method.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        A detailed description of what the tool does, what its input is,
        and what its output will be. This is used by the agent's LLM to
        decide when and how to use the tool.
        """
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """
        Executes the tool with the given arguments.

        Args:
            **kwargs: The arguments required for the tool, as specified
                      in its description.

        Returns:
            The result of the tool's execution, typically a string.
        """
        pass

    def to_dict(self) -> Dict[str, str]:
        """Serializes the tool's metadata to a dictionary."""
        return {
            "name": self.name,
            "description": self.description
        }
