"""
Tool registry system for VCBot.

This module provides a centralized tool registry that replaces runtime type checking
with compile-time tool registration and proper parameter validation.
"""

import inspect
import asyncio
from typing import Dict, Callable, Any, Optional, List
from dataclasses import dataclass
from logging_config import logger


@dataclass
class Tool:
    """Represents a registered tool with metadata and validation."""
    name: str
    func: Callable
    description: str
    parameters: Dict[str, Any]
    needs_client: bool = False
    is_async: bool = False
    
    def __post_init__(self):
        """Automatically detect if the function is async."""
        self.is_async = inspect.iscoroutinefunction(self.func)
        logger.debug(f"Registered tool '{self.name}' - async: {self.is_async}, needs_client: {self.needs_client}")


class ToolRegistry:
    """Centralized registry for all bot tools."""
    
    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: Dict[str, Tool] = {}
        self._discord_client = None
        self._tool_wrappers: Dict[str, Callable] = {}
        logger.debug("Tool registry initialized")
    
    def set_discord_client(self, client):
        """Set the Discord client for tools that need it."""
        self._discord_client = client
        self._create_tool_wrappers()
        logger.debug("Discord client set in tool registry")
    
    def _create_tool_wrappers(self):
        """Create wrapper functions for tools that need client injection."""
        import geminitools
        
        # Create wrapper for call_other_channel_context
        async def call_other_channel_context_wrapper(channel_to_call: str, number_of_messages_called: int, search_query: str = None) -> str:
            if self._discord_client is None:
                raise RuntimeError("Discord client not set in tool registry")
            
            try:
                raw_messages = await geminitools.call_other_channel_context(
                    channel_to_call, 
                    number_of_messages_called, 
                    search_query, 
                    client=self._discord_client
                )
                
                if raw_messages is None:
                    return "No messages found or channel access failed."
                
                # Format messages as expected by the AI system
                return "\n".join(f"{m.author}: {m.content}" for m in raw_messages)
            except Exception as e:
                logger.error(f"Error in call_other_channel_context wrapper: {e}")
                return f"Failed to retrieve messages from channel '{channel_to_call}': {str(e)}"
        
        # Store wrapper functions
        self._tool_wrappers["call_other_channel_context"] = call_other_channel_context_wrapper
    
    def register(self, name: str, description: str, parameters: Dict[str, Any], needs_client: bool = False):
        """Decorator to register a tool function.
        
        Args:
            name: Tool name (must match Gemini tool declaration)
            description: Tool description
            parameters: Tool parameter schema
            needs_client: Whether this tool needs Discord client injection
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            tool = Tool(
                name=name,
                func=func,
                description=description,
                parameters=parameters,
                needs_client=needs_client
            )
            self._tools[name] = tool
            logger.info(f"Registered tool: {name} (async: {tool.is_async}, needs_client: {needs_client})")
            return func
        return decorator
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_gemini_declarations(self) -> List[Dict[str, Any]]:
        """Get Gemini-compatible tool declarations.
        
        Returns:
            List of tool declarations for Gemini
        """
        declarations = []
        for tool in self._tools.values():
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        logger.debug(f"Generated {len(declarations)} Gemini tool declarations")
        return declarations
    
    async def execute(self, name: str, **kwargs) -> Any:
        """Execute a tool by name with parameter validation.
        
        Args:
            name: Tool name
            **kwargs: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool not found or validation fails
            RuntimeError: If tool execution fails
        """
        tool = self._tools.get(name)
        if not tool:
            available_tools = ", ".join(self._tools.keys())
            raise ValueError(f"Unknown tool: {name}. Available tools: {available_tools}")
        
        # Validate parameters (basic validation - Gemini provides more detailed validation)
        required_params = []
        if "required" in tool.parameters:
            required_params = tool.parameters["required"]
        
        missing_params = [param for param in required_params if param not in kwargs]
        if missing_params:
            raise ValueError(f"Missing required parameters for tool '{name}': {missing_params}")
        
        logger.debug(f"Executing tool '{name}' with args: {list(kwargs.keys())}")
        
        try:
            # Use wrapper function for tools that need client injection
            if tool.needs_client and name in self._tool_wrappers:
                func_to_call = self._tool_wrappers[name]
            else:
                func_to_call = tool.func
            
            # Execute the function
            if asyncio.iscoroutinefunction(func_to_call):
                result = await func_to_call(**kwargs)
            else:
                result = func_to_call(**kwargs)
            
            logger.debug(f"Tool '{name}' executed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Failed to execute tool '{name}': {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def validate_tool_function(self, func: Callable, expected_params: List[str]) -> bool:
        """Validate that a function matches expected parameters.
        
        Args:
            func: Function to validate
            expected_params: List of expected parameter names
            
        Returns:
            True if function signature matches, False otherwise
        """
        try:
            sig = inspect.signature(func)
            func_params = list(sig.parameters.keys())
            
            # Check if all expected params are present (allow extra params)
            missing = [param for param in expected_params if param not in func_params]
            if missing:
                logger.warning(f"Function {func.__name__} missing parameters: {missing}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating function {func.__name__}: {e}")
            return False


# Global registry instance
registry = ToolRegistry()

# Backward compatibility: maintain the old TOOLS dict interface
TOOLS = {}