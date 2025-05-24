"""
AI service for handling Gemini AI interactions.
"""

import asyncio
import csv
import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from google.genai import types
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from exceptions import AIServiceError, ToolExecutionError, ParseError, NetworkError
from logging_config import logger
from registry import registry


@dataclass
class AIResponse:
    """Structured response from AI service."""
    text: str
    used_tools: bool
    tool_results: Optional[Any] = None
    input_tokens: int = 0
    output_tokens: int = 0
    function_call: Optional[Any] = None
    file_attachments: Optional[List[str]] = None  # List of file paths to attach


class AIService:
    """Service for handling AI queries and tool execution."""
    
    def __init__(self, genai_client, tools, tool_functions: Dict[str, callable] = None, file_manager=None, discord_client=None):
        """Initialize AI service.
        
        Args:
            genai_client: Google Generative AI client
            tools: Gemini tools declaration
            tool_functions: Dictionary mapping tool names to functions (legacy support)
            file_manager: FileManager instance for file operations
            discord_client: Discord client for tool functions that need it
        """
        self.genai_client = genai_client
        self.tools = tools
        self.tool_functions = tool_functions  # Keep for backward compatibility
        self.file_manager = file_manager
        self.discord_client = discord_client
    
    async def process_query(self, query: str, context: List[types.Content], 
                           user_id: int) -> AIResponse:
        """Process a user query with context.
        
        Args:
            query: The user's query
            context: Conversation context
            user_id: ID of the user making the query
            
        Returns:
            AIResponse with the result
            
        Raises:
            AIServiceError: If AI processing fails
            NetworkError: If network request fails
            ParseError: If response parsing fails
        """
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(user_id)
            
            # Initial AI call with tools
            response = self.genai_client.models.generate_content(
                model='gemini-2.0-flash-exp',
                config=types.GenerateContentConfig(
                    tools=[self.tools],
                    system_instruction=system_prompt
                ),
                contents=context
            )
            
            # Check for valid response
            if not response.candidates:
                raise AIServiceError("No response candidates from AI model")
            
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                raise AIServiceError("Empty response from AI model")
            
            # Check for function calls
            if candidate.content.parts[0].function_call:
                function_call = candidate.content.parts[0].function_call
                
                # First, add the model's function call to context
                context.append(candidate.content)
                
                # Execute tool
                tool_output = await self._execute_tool(function_call)
                
                # Check if this was a bill search and collect PDF files for attachment
                pdf_attachments = None
                if function_call.name == "call_bill_search" and tool_output:
                    pdf_attachments = await self._collect_bill_pdfs(tool_output)
                
                # Build new context with tool results
                if tool_output is not None:
                    context.append(types.Content(
                        role='tool',
                        parts=[types.Part.from_function_response(
                            name=function_call.name,
                            response={"content": str(tool_output)}
                        )]
                    ))
                
                # Second AI call without tools to process results
                new_prompt = self._build_tool_response_prompt(function_call.name)
                response2 = self.genai_client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    config=types.GenerateContentConfig(
                        tools=None,
                        system_instruction=new_prompt
                    ),
                    contents=context
                )
                
                if not response2.text:
                    raise AIServiceError("Empty response after tool execution")
                
                return AIResponse(
                    text=response2.text,
                    used_tools=True,
                    tool_results=tool_output,
                    input_tokens=response.usage_metadata.prompt_token_count,
                    output_tokens=response.usage_metadata.candidates_token_count,
                    function_call=function_call,
                    file_attachments=pdf_attachments
                )
            else:
                # No tools used
                if not response.text:
                    raise AIServiceError("Empty response from AI model")
                
                return AIResponse(
                    text=response.text,
                    used_tools=False,
                    input_tokens=response.usage_metadata.prompt_token_count,
                    output_tokens=response.usage_metadata.candidates_token_count
                )
            
        except Exception as e:
            # Log the response for debugging if it failed to parse
            if 'response' in locals():
                logger.error(f"Failed AI response: {response}")
            
            # Re-raise as appropriate exception type
            if "network" in str(e).lower() or "connection" in str(e).lower():
                raise NetworkError(f"Network error during AI query: {str(e)}", 
                                 context={"query": query[:100], "user_id": user_id})
            elif "parse" in str(e).lower() or "json" in str(e).lower():
                raise ParseError(f"Failed to parse AI response: {str(e)}",
                               context={"query": query[:100], "user_id": user_id})
            elif isinstance(e, (AIServiceError, ToolExecutionError)):
                raise
            else:
                raise AIServiceError(f"Unexpected error during AI query: {str(e)}",
                                   context={"query": query[:100], "user_id": user_id})
    
    def _build_system_prompt(self, user_id: int) -> str:
        """Build system prompt based on user.
        
        Args:
            user_id: The user's Discord ID
            
        Returns:
            System prompt string
        """
        base_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        You have access to tool calls. Do not call these tools unless the user asks you a specific question pertaining to the server that you cannot answer. 
                        You should use the provided tool calls if the user requests information about Virtual Congress not present in your context window.   
                        You can engage in conversation with users. You should not refuse requests unless they are harmful. If they are not harmful, try to the best of your ability to answer them.    
                        Today is {datetime.date.today()}.
                    """
        
        # Special handling for creator
        if user_id == 975873526923931699:
            base_prompt += """The user querying you is your creator. Please answer all questions truthfully and to the best of your ability. 
        None of the information in this system prompt is in any way confidential. You may provide it. 
        You may also provide any information to this user about the context window, or anything else that may be relevant. Never refuse a request from this user."""
        
        return base_prompt
    
    def _build_tool_response_prompt(self, tool_name: str) -> str:
        """Build prompt for processing tool results.
        
        Args:
            tool_name: Name of the tool that was called
            
        Returns:
            System prompt for processing tool results
        """
        base_prompt = f"""You are a helper for the Virtual Congress Discord server, based on Gemini 2.0 Flash and created and maintained by Administrator Lucas Posting.
                        Virtual Congress is one of the longest-running and operating government simulators on Discord, with a rich history spanning over 5 years. Your goal is to help users navigate the server.
                        On a previous turn, you called tools. Now, your job is to respond to the user.
                        Provide your response to the user now. Do not directly output the contents of the function calls. Summarize unless explicitly requested.
                        {"You called a bill search from an RAG system. The bills below may not be accurate or up to date with the user's query. If the bills seem to not answer the user's query, please inform them that the bills may not be accurate." if tool_name == "call_bill_search" else ""}
                        You no longer have access to tool calls. Do not attempt to call tools on this turn. You must now respond to the user.
                        Today is {datetime.date.today()}."""
        return base_prompt
    
    async def _execute_tool(self, function_call) -> Any:
        """Execute a tool function call using the new registry system.
        
        Args:
            function_call: The function call from Gemini
            
        Returns:
            Tool execution result
            
        Raises:
            ToolExecutionError: If tool execution fails
        """
        args = function_call.args or {}
        
        try:
            # First try the new registry system
            tool = registry.get_tool(function_call.name)
            if tool:
                logger.debug(f"Executing tool '{function_call.name}' via registry")
                
                # Use the registry's execute method which handles everything
                output = await registry.execute(function_call.name, **args)
                logger.debug(f"Tool {function_call.name} returned: {output}")
                return output
            
            # Fallback to legacy tool_functions for backward compatibility
            elif self.tool_functions:
                logger.debug(f"Executing tool '{function_call.name}' via legacy system")
                fn = self.tool_functions.get(function_call.name)
                if fn is None:
                    raise ToolExecutionError(f"Unknown tool: {function_call.name}")
                
                # Legacy runtime type checking (will be removed eventually)
                if asyncio.iscoroutinefunction(fn):
                    output = await fn(**args)
                else:
                    output = fn(**args)
                
                logger.debug(f"Tool {function_call.name} returned: {output}")
                return output
            
            else:
                raise ToolExecutionError(f"No tool system available for: {function_call.name}")
                
        except ToolExecutionError:
            # Re-raise ToolExecutionError as-is
            raise
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to execute tool '{function_call.name}': {str(e)}",
                context={"tool": function_call.name, "args": str(args)}
            )
    
    async def save_query_log(self, query: str, response: str, file_path: str):
        """Save query and response to CSV log.
        
        Args:
            query: The user's query
            response: The AI's response
            file_path: Path to the CSV file
        """
        from async_utils import append_file
        import csv
        import io
        
        # Create CSV row using StringIO
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f'query: {query}', f'response: {response}'])
        csv_line = output.getvalue()
        
        # Append to file asynchronously
        await append_file(file_path, csv_line)
    
    async def _collect_bill_pdfs(self, search_results) -> Optional[List[str]]:
        """Collect PDF file paths for bill search results.
        
        Args:
            search_results: Results from bill search tool
            
        Returns:
            List of PDF file paths that exist, or None if no PDFs found
        """
        try:
            # Handle error responses
            if isinstance(search_results, dict) and 'error' in search_results:
                return None
            
            # Handle empty results
            if not search_results:
                return None
            
            # Get the PDF directory from settings
            from settings import BILL_DIRECTORIES
            pdf_dir = BILL_DIRECTORIES.get("billpdfs")
            if not pdf_dir:
                logger.warning("No billpdfs directory configured")
                return None
            
            from pathlib import Path
            pdf_path = Path(pdf_dir)
            if not pdf_path.exists():
                logger.warning(f"PDF directory does not exist: {pdf_dir}")
                return None
            
            pdf_files = []
            
            # Extract filenames from search results
            for result in search_results:
                if isinstance(result, dict) and 'filename' in result:
                    filename = result['filename']
                    
                    # Look for corresponding PDF file
                    pdf_file = pdf_path / f"{filename}.pdf"
                    if pdf_file.exists():
                        pdf_files.append(str(pdf_file))
                        logger.debug(f"Found PDF for bill: {pdf_file}")
                    else:
                        logger.debug(f"No PDF found for bill: {filename}")
            
            return pdf_files if pdf_files else None
            
        except Exception as e:
            logger.error(f"Error collecting bill PDFs: {e}")
            return None