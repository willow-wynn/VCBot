"""
Response Formatter for VCBot Discord Commands

This module provides centralized response formatting for Discord bot commands,
handling text sanitization, chunking for Discord limits, and file attachment
for long responses.

Consolidates scattered response handling logic from main.py and command_utils.py
into a single, testable, and maintainable system.
"""

import discord
import tempfile
from pathlib import Path
from typing import List, Optional, Union
from dataclasses import dataclass
from io import StringIO


@dataclass
class FormattedResponse:
    """Represents a formatted response ready for Discord delivery."""
    
    # Core response data
    content: str
    chunks: List[str]
    
    # File handling
    is_file: bool = False
    filename: Optional[str] = None
    file_content: Optional[str] = None
    
    # Metadata
    was_sanitized: bool = False
    original_length: int = 0
    chunk_count: int = 0
    
    def __post_init__(self):
        """Calculate metadata after initialization."""
        self.chunk_count = len(self.chunks)
        if not self.original_length:
            self.original_length = len(self.content)


class ResponseFormatter:
    """Centralized Discord response formatting system."""
    
    # Discord limits and thresholds
    MAX_MESSAGE_LENGTH = 1900  # Safe limit for Discord messages (2000 - buffer)
    MAX_TOTAL_LENGTH = 30000   # Threshold for switching to file attachment
    MAX_CHUNKS = 5            # Maximum number of chunks before forcing file
    
    # File settings
    DEFAULT_FILENAME = "response.txt"
    FILE_ENCODING = "utf-8"
    
    @staticmethod
    def sanitize(text: str) -> tuple[str, bool]:
        """
        Sanitize text to prevent mass pings and other Discord issues.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Tuple of (sanitized_text, was_changed)
        """
        if not text:
            return "", False
            
        original = text
        sanitized = (
            text.replace("@everyone", "@ everyone")
                .replace("@here", "@ here")
                .replace("<@&", "< @&")  # Only break role mentions, not user mentions
        )
        
        return sanitized, sanitized != original
    
    @classmethod
    def chunk_text(cls, text: str, max_length: int = None) -> List[str]:
        """
        Split text into Discord-safe chunks, preferring line breaks.
        
        Args:
            text: Text to split
            max_length: Maximum length per chunk (defaults to MAX_MESSAGE_LENGTH)
            
        Returns:
            List of text chunks
        """
        if max_length is None:
            max_length = cls.MAX_MESSAGE_LENGTH
            
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by lines first to avoid breaking mid-sentence
        lines = text.split('\n')
        
        for line in lines:
            # If the line itself is too long, we'll have to split it
            if len(line) > max_length:
                # Add current chunk if it has content
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # Split the long line
                while len(line) > max_length:
                    chunks.append(line[:max_length])
                    line = line[max_length:]
                
                # Add remainder (even if empty, to preserve structure)
                current_chunk = line
            else:
                # Check if adding this line would exceed the limit
                test_chunk = current_chunk + ('\n' if current_chunk else '') + line
                
                if len(test_chunk) > max_length:
                    # Save current chunk and start new one
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    # Add line to current chunk
                    current_chunk = test_chunk
        
        # Add final chunk if it has content
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    @classmethod
    def should_use_file(cls, text: str, force_file: bool = False) -> bool:
        """
        Determine if response should be sent as file attachment.
        
        Args:
            text: Text to evaluate
            force_file: Force file attachment regardless of length
            
        Returns:
            True if should use file, False otherwise
        """
        if force_file:
            return True
            
        # Check total length
        if len(text) > cls.MAX_TOTAL_LENGTH:
            return True
        
        # Check if it would create too many chunks
        chunks = cls.chunk_text(text)
        if len(chunks) > cls.MAX_CHUNKS:
            return True
            
        return False
    
    @classmethod
    def format_response(cls, 
                       text: str, 
                       force_file: bool = False,
                       filename: Optional[str] = None) -> FormattedResponse:
        """
        Format a response for Discord delivery.
        
        Args:
            text: Response text to format
            force_file: Force file attachment regardless of length
            filename: Custom filename for file attachment
            
        Returns:
            FormattedResponse object ready for Discord
        """
        if not text:
            return FormattedResponse(
                content="",
                chunks=["*Empty response*"],
                original_length=0
            )
        
        # Sanitize the text
        sanitized_text, was_sanitized = cls.sanitize(text)
        
        # Determine if file is needed
        use_file = cls.should_use_file(sanitized_text, force_file)
        
        if use_file:
            # Create file response
            return FormattedResponse(
                content=sanitized_text,
                chunks=["Response attached as file due to length."],
                is_file=True,
                filename=filename or cls.DEFAULT_FILENAME,
                file_content=sanitized_text,
                was_sanitized=was_sanitized,
                original_length=len(text)
            )
        else:
            # Create chunked response
            chunks = cls.chunk_text(sanitized_text)
            return FormattedResponse(
                content=sanitized_text,
                chunks=chunks,
                is_file=False,
                was_sanitized=was_sanitized,
                original_length=len(text)
            )
    
    @classmethod
    async def send_response(cls, 
                          interaction: discord.Interaction,
                          formatted: FormattedResponse,
                          completion_message: str = "Complete.",
                          query_header: Optional[str] = None) -> None:
        """
        Send a formatted response to Discord.
        
        Args:
            interaction: Discord interaction object
            formatted: FormattedResponse to send
            completion_message: Message for ephemeral completion notification
            query_header: Optional header to show original query
        """
        # Send completion notification (ephemeral)
        await interaction.followup.send(completion_message, ephemeral=True)
        
        # Send query header if provided
        if query_header:
            # Sanitize and truncate header to fit in one message
            safe_header, _ = cls.sanitize(query_header)
            if len(safe_header) > cls.MAX_MESSAGE_LENGTH:
                safe_header = safe_header[:cls.MAX_MESSAGE_LENGTH-3] + "..."
            await interaction.channel.send(safe_header)
        
        if formatted.is_file:
            # Send as file attachment
            file_obj = discord.File(
                StringIO(formatted.file_content), 
                filename=formatted.filename
            )
            await interaction.channel.send(
                formatted.chunks[0],  # Usually "Response attached as file..."
                file=file_obj
            )
        else:
            # Send as text chunks
            for chunk in formatted.chunks:
                await interaction.channel.send(chunk)
    
    @classmethod
    def format_ai_response(cls,
                          ai_response,  # AIResponse object
                          query: str,
                          user_mention: str) -> tuple[FormattedResponse, str, str]:
        """
        Format an AI response with query header and completion message.
        
        Args:
            ai_response: AIResponse object from AI service
            query: Original user query
            user_mention: User mention string for header
            
        Returns:
            Tuple of (FormattedResponse, completion_message, query_header)
        """
        # Format the main response
        formatted = cls.format_response(ai_response.text)
        
        # Create completion message with token info
        completion_message = (
            f"Complete. Input tokens: {ai_response.input_tokens}, "
            f"Output tokens: {ai_response.output_tokens}"
        )
        
        # Create query header
        truncated_query = query[:1900] if len(query) > 1900 else query
        query_header = f"Query from {user_mention}: {truncated_query}\n\nResponse:"
        
        return formatted, completion_message, query_header
    
    @classmethod
    def format_bill_search_response(cls,
                                  bills: List,
                                  query: str) -> FormattedResponse:
        """
        Format a bill search response.
        
        Args:
            bills: List of bill results
            query: Original search query
            
        Returns:
            FormattedResponse object
        """
        if not bills:
            return cls.format_response(f"No bills found matching '{query}'.")
        
        # Build response text
        response_lines = [f"Found {len(bills)} bills matching '{query}':\n"]
        
        for i, bill in enumerate(bills, 1):
            if hasattr(bill, 'title') and hasattr(bill, 'reference'):
                response_lines.append(f"{i}. {bill.reference} - {bill.title}")
            else:
                response_lines.append(f"{i}. {str(bill)}")
        
        response_text = "\n".join(response_lines)
        return cls.format_response(response_text)
    
    @classmethod
    def format_file_response(cls,
                           file_path: Union[str, Path],
                           description: str = "File attached.") -> FormattedResponse:
        """
        Format a response that includes a file attachment (not text file).
        
        Args:
            file_path: Path to file to attach
            description: Description message to send with file
            
        Returns:
            FormattedResponse with file path information
        """
        return FormattedResponse(
            content=description,
            chunks=[description],
            is_file=False,  # This is for actual file attachments, not text files
            filename=str(file_path),
            was_sanitized=False,
            original_length=len(description)
        )


# Convenience functions for backward compatibility
def sanitize(text: str) -> str:
    """Legacy function for backward compatibility."""
    sanitized, _ = ResponseFormatter.sanitize(text)
    return sanitized


def chunk_text(text: str, max_length: int = 1900) -> List[str]:
    """Legacy function for backward compatibility."""
    return ResponseFormatter.chunk_text(text, max_length)


# Export main classes and functions
__all__ = [
    'FormattedResponse',
    'ResponseFormatter', 
    'sanitize',
    'chunk_text'
]