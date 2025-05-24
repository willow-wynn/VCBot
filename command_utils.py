"""
Utilities for Discord command handlers.

This module contains helper functions for building context,
formatting responses, and handling errors in command handlers.
"""

import discord
from typing import List
from google.genai import types
from response_formatter import ResponseFormatter
from logging_config import logger


async def build_channel_context(channel: discord.TextChannel, 
                              bot_id: int,
                              limit: int = 50) -> List[types.Content]:
    """Build conversation context from channel history.
    
    Args:
        channel: Discord channel to get history from
        bot_id: Bot's user ID for determining message roles
        limit: Number of messages to retrieve
        
    Returns:
        List of Content objects for Gemini
    """
    history = [
        msg async for msg in channel.history(limit=limit) 
        if msg.content.strip() and not msg.content.startswith("Complete.")
    ]
    
    context = []
    for msg in reversed(history):  # oldest first
        # Determine role based on author
        is_bot = msg.author.id == bot_id
        
        # Special handling for "Query from" messages
        if is_bot and msg.content.startswith("Query from"):
            # Extract the actual query from "Query from Username: query text"
            # Format: "Query from {user}: {query}"
            if ": " in msg.content:
                parts = msg.content.split(": ", 1)
                username_part = parts[0].replace("Query from ", "")
                query_text = parts[1]
                # Format as user message with username prefix
                text_part = types.Part.from_text(text=f"{username_part}: {query_text}")
                role = 'user'  # Treat as user message
            else:
                # Fallback if format is unexpected
                text_part = types.Part.from_text(text=msg.content)
                role = 'user'
        elif is_bot:
            # Regular bot message
            text_part = types.Part.from_text(text=msg.content)
            role = 'assistant'
        else:
            # User message - prefix with username
            text_part = types.Part.from_text(text=f"{msg.author.display_name}: {msg.content}")
            role = 'user'
        
        context.append(types.Content(role=role, parts=[text_part]))
    
    return context


# Legacy functions for backward compatibility
def sanitize(text: str) -> str:
    """Legacy sanitize function - use ResponseFormatter.sanitize() for new code."""
    sanitized, _ = ResponseFormatter.sanitize(text)
    return sanitized


def chunk_text(text: str, max_length: int = 1900) -> List[str]:
    """Legacy chunk function - use ResponseFormatter.chunk_text() for new code."""
    return ResponseFormatter.chunk_text(text, max_length)


async def send_chunked_response(channel: discord.TextChannel, 
                              text: str,
                              prefix: str = "") -> None:
    """Send a long response in chunks.
    
    Args:
        channel: Channel to send to
        text: Text to send
        prefix: Optional prefix for first message
    """
    formatted = ResponseFormatter.format_response(text)
    
    if prefix:
        await channel.send(prefix)
    
    if formatted.is_file:
        # For very long responses, send as file
        from io import StringIO
        file_obj = discord.File(
            StringIO(formatted.file_content),
            filename=formatted.filename
        )
        await channel.send(formatted.chunks[0], file=file_obj)
    else:
        for chunk in formatted.chunks:
            await channel.send(chunk)


async def send_ai_response(interaction: discord.Interaction,
                         ai_response,
                         query: str) -> None:
    """Send AI response to Discord using ResponseFormatter.
    
    Args:
        interaction: Discord interaction
        ai_response: AIResponse object
        query: Original query
    """
    # Format the response using the new system
    formatted, completion_message, query_header = ResponseFormatter.format_ai_response(
        ai_response,
        query,
        interaction.user.mention
    )
    
    # Send using the new unified method
    await ResponseFormatter.send_response(
        interaction,
        formatted,
        completion_message,
        query_header
    )
    
    # Send PDF attachments if present (for bill search results)
    if hasattr(ai_response, 'file_attachments') and ai_response.file_attachments:
        import discord
        from pathlib import Path
        
        logger.info(f"Sending {len(ai_response.file_attachments)} PDF attachments")
        
        for pdf_path in ai_response.file_attachments:
            try:
                pdf_file = Path(pdf_path)
                if pdf_file.exists() and pdf_file.stat().st_size > 0:
                    # Discord has a 25MB file size limit
                    if pdf_file.stat().st_size > 25 * 1024 * 1024:
                        await interaction.followup.send(
                            f"📄 **{pdf_file.stem}** - File too large to attach (>25MB)",
                            ephemeral=False
                        )
                    else:
                        with open(pdf_file, 'rb') as f:
                            discord_file = discord.File(f, filename=pdf_file.name)
                            await interaction.followup.send(
                                f"📄 **{pdf_file.stem}**",
                                file=discord_file,
                                ephemeral=False
                            )
                else:
                    logger.warning(f"PDF file not found or empty: {pdf_path}")
                    
            except Exception as e:
                logger.error(f"Failed to send PDF attachment {pdf_path}: {e}")
                await interaction.followup.send(
                    f"❌ Failed to attach PDF: {Path(pdf_path).name}",
                    ephemeral=True
                )


async def handle_command_error(interaction: discord.Interaction, 
                             error: Exception,
                             error_message: str = "An error occurred") -> None:
    """Handle command errors consistently.
    
    Args:
        interaction: Discord interaction
        error: The exception that occurred
        error_message: User-friendly error message
    """
    print(f"Error in command: {error}")
    
    # Send error to user
    if interaction.response.is_done():
        await interaction.followup.send(
            f"{error_message}: {error}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"{error_message}: {error}",
            ephemeral=True
        )