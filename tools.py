"""
Tool definitions using the new registry system.

This module registers all VCBot tools with the centralized registry,
replacing the scattered tool definitions.
"""

from pathlib import Path
from registry import registry
import geminitools
from settings import settings, KNOWLEDGE_FILES


# Register the call_knowledge tool
@registry.register(
    name="call_knowledge",
    description="calls a specific piece or pieces of information from your knowledge base.",
    parameters={
        "type": "object",
        "properties": {
            "file_to_call": {
                "type": "string",
                "enum": ["rules", "constitution", "server_information", "house_rules", "senate_rules"],
                "description": "which knowledge files to call",
            },
        },
        "required": ["file_to_call"]
    }
)
def call_knowledge(file_to_call: str) -> str:
    """Call knowledge file from knowledge base.
    
    Args:
        file_to_call: The knowledge file to retrieve
        
    Returns:
        Contents of the knowledge file
    """
    return geminitools.call_knowledge(file_to_call)


# Register the call_other_channel_context tool
@registry.register(
    name="call_other_channel_context",
    description="calls information from another channel in the server",
    parameters={
        "type": "object",
        "properties": {
            "channel_to_call": {
                "type": "string",
                "enum": ["server-announcements", "twitter-rp", "official-rp-news", "virtual-congress-chat", "staff-announcements", "election-announcements", "house-floor", "senate-floor"],
                "description": "which channel to call information from."
            },
            "number_of_messages_called": {
                "type": "integer",
                "description": "how many messages to return from the channel in question. Maximum 50. Request 10 unless otherwise specified."
            },
            "search_query": {
                "type": "string",
                "description": "what specific information to search for in the channel. will only return information that directly matches the search query. leave blank unless user explicitly asks for query."
            },
        },
        "required": ["channel_to_call", "number_of_messages_called"]
    },
    needs_client=True  # Flag to indicate this tool needs Discord client injection
)
def call_other_channel_context(channel_to_call: str, number_of_messages_called: int, search_query: str = None) -> str:
    """Call information from another channel in the server.
    
    Note: This is a placeholder - actual implementation is in the registry wrapper.
    Discord client will be injected automatically by the registry.
    
    Args:
        channel_to_call: Name of the channel to call
        number_of_messages_called: Number of messages to retrieve
        search_query: Optional search query to filter messages
        
    Returns:
        Formatted string of messages from the channel
    """
    # This function is never called directly - the registry uses a wrapper
    raise NotImplementedError("This function must be called through the registry with client injection")


# Register the call_bill_search tool
@registry.register(
    name="call_bill_search",
    description="calls a simple RAG system for vector search through the legislative corpus",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "the question the user is asking about the legislation. this will be used to search through the corpus and will return the top result. phrasing the question as a question likely results in better outputs.",
            },
            "top_k": {
                "type": "integer",
                "description": "the number of results to return from the corpus. 5 is a good number for most queries. 10 is the maximum. Assign a value of 1 if the user is asking about a single specific bill.",
            },
            "reconstruct_bills_from_chunks": {
                "type": "boolean",
                "description": "whether or not to reconstruct the bills from the chunks returned. Use for discussion about specific bill. If the user is asking about a general topic, set to false with high top_k.",
            },
        },
        "required": ["query", "top_k", "reconstruct_bills_from_chunks"] 
    }
)
def call_bill_search(query: str, top_k: int, reconstruct_bills_from_chunks: bool) -> any:
    """Call the RAG system for vector search through legislative corpus.
    
    Args:
        query: The search query
        top_k: Number of results to return
        reconstruct_bills_from_chunks: Whether to reconstruct full bills
        
    Returns:
        Search results from the bill corpus
    """
    return geminitools.search_bills(query, top_k, reconstruct_bills_from_chunks)


# Function to create tool functions with client injection for backward compatibility
def create_tools_with_client(discord_client):
    """Create tool functions with Discord client injected for backward compatibility.
    
    This function maintains the same interface as the old create_tools function
    but now works with the new registry system.
    
    Args:
        discord_client: Discord client instance
        
    Returns:
        Dictionary mapping tool names to functions
    """
    # Create wrapper functions that inject the client
    def _tool_call_knowledge(**kw):
        return call_knowledge(kw["file_to_call"])

    async def _tool_call_other_channel_context(**kw):
        return await call_other_channel_context(
            kw["channel_to_call"],
            kw["number_of_messages_called"],
            kw.get("search_query"),
            client=discord_client
        )

    def _tool_call_bill_search(**kw):
        return call_bill_search(
            kw["query"],
            kw["top_k"],
            kw.get("reconstruct_bills_from_chunks"),
        )

    return {
        "call_knowledge": _tool_call_knowledge,
        "call_other_channel_context": _tool_call_other_channel_context,
        "call_bill_search": _tool_call_bill_search,
    }