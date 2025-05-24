"""Error handling utilities for VCBot"""

import functools
import traceback
import asyncio
from typing import Any, Callable, Optional, Union
import discord
from datetime import datetime
import json

from exceptions import (
    VCBotError, ConfigurationError, BillProcessingError, AIServiceError,
    PermissionError, ToolExecutionError, DiscordAPIError, RateLimitError,
    NetworkError, TimeoutError as VCBotTimeoutError, ParseError
)
from logging_config import logger


# Transient errors that should trigger retries
TRANSIENT_ERRORS = (NetworkError, TimeoutError, RateLimitError)


class ErrorHandler:
    """Centralized error handling with retry logic"""
    
    def __init__(self, bot_channel_id: int = 1327483297202176080, 
                 admin_user_id: int = 975873526923931699):
        self.bot_channel_id = bot_channel_id
        self.admin_user_id = admin_user_id
        self.max_retries = 3
        self.base_delay = 1.0  # Base delay for exponential backoff
    
    async def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except TRANSIENT_ERRORS as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Transient error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise
            except Exception:
                # Non-transient errors should not be retried
                raise
        
        # If we get here, all retries failed
        raise last_error
    
    async def handle_error(self, error: Exception, interaction: discord.Interaction, 
                          context: Optional[dict] = None) -> None:
        """Handle an error with appropriate logging and user notification"""
        
        # Log the full stack trace
        logger.error(f"Error in command {interaction.command.name if interaction.command else 'unknown'}:", exc_info=True)
        
        # Log additional context if provided
        if context:
            logger.error(f"Error context: {json.dumps(context, indent=2, default=str)}")
        
        # Determine if this is a serious error
        is_serious = self._is_serious_error(error)
        
        # Get user-friendly error message
        user_message = self._get_user_message(error)
        
        # Send response to user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ {user_message}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {user_message}",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
        
        # Alert admin for serious errors
        if is_serious:
            await self._alert_admin(error, interaction, context)
    
    def _is_serious_error(self, error: Exception) -> bool:
        """Determine if an error is serious enough to alert admin"""
        # Configuration and permission errors are serious
        if isinstance(error, (ConfigurationError, PermissionError)):
            return True
        
        # Repeated failures after retries are serious
        if isinstance(error, TRANSIENT_ERRORS):
            return True
        
        # Unknown errors (not VCBotError subclasses) are serious
        if not isinstance(error, VCBotError):
            return True
        
        return False
    
    def _get_user_message(self, error: Exception) -> str:
        """Get user-friendly error message"""
        # For beta transparency, include the actual error
        if isinstance(error, VCBotError):
            base_message = str(error)
        else:
            base_message = f"{type(error).__name__}: {str(error)}"
        
        # Add helpful context for specific error types
        if isinstance(error, PermissionError):
            return f"{base_message}. Please contact an admin if you believe you should have access."
        elif isinstance(error, NetworkError):
            return f"{base_message}. This is likely temporary, please try again."
        elif isinstance(error, (TimeoutError, VCBotTimeoutError)):
            return f"{base_message}. The operation took too long, please try again."
        elif isinstance(error, ParseError):
            return f"{base_message}. The response format was unexpected."
        
        return base_message
    
    async def _alert_admin(self, error: Exception, interaction: discord.Interaction,
                          context: Optional[dict] = None) -> None:
        """Alert admin about serious errors"""
        try:
            bot_channel = interaction.client.get_channel(self.bot_channel_id)
            if bot_channel:
                error_details = {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "command": interaction.command.name if interaction.command else "unknown",
                    "user": f"{interaction.user.name} ({interaction.user.id})",
                    "channel": f"{interaction.channel.name if interaction.channel else 'DM'}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                if context:
                    error_details["context"] = context
                
                # Create error embed
                embed = discord.Embed(
                    title="🚨 Serious Error Detected",
                    description=f"<@{self.admin_user_id}> Error in {error_details['command']} command",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(name="Error Type", value=error_details["error_type"], inline=True)
                embed.add_field(name="User", value=error_details["user"], inline=True)
                embed.add_field(name="Channel", value=error_details["channel"], inline=True)
                embed.add_field(name="Error Message", value=str(error)[:1024], inline=False)
                
                await bot_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to alert admin: {e}")


# Global error handler instance
error_handler = ErrorHandler()


def handle_errors(error_message: str = "An error occurred"):
    """Decorator to handle errors in Discord commands"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            try:
                # For commands that might have transient errors, use retry logic
                if any(hasattr(func, attr) for attr in ['uses_network', 'uses_ai']):
                    return await error_handler.retry_with_backoff(
                        func, interaction, *args, **kwargs
                    )
                else:
                    return await func(interaction, *args, **kwargs)
            except Exception as e:
                # Gather context for debugging
                context = {
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "function": func.__name__
                }
                
                # Add any VCBotError context
                if isinstance(e, VCBotError) and e.context:
                    context.update(e.context)
                
                await error_handler.handle_error(e, interaction, context)
        
        return wrapper
    return decorator


def mark_uses_network(func):
    """Mark a function as using network operations (for retry logic)"""
    func.uses_network = True
    return func


def mark_uses_ai(func):
    """Mark a function as using AI services (for retry logic)"""
    func.uses_ai = True
    return func