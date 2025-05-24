from typing import Dict, Callable, Optional, List, Any
import discord
from dataclasses import dataclass, field
from logging_config import logger
from exceptions import VCBotError, BillProcessingError
import asyncio
import re

@dataclass
class MessageHandler:
    """Represents a message handler with optional conditions"""
    func: Callable[[discord.Message, Any], None]  # Using Any instead of 'BotState' to avoid forward reference
    conditions: List[Callable[[discord.Message], bool]] = field(default_factory=list)
    description: str = ""

class MessageRouter:
    """Routes Discord messages to appropriate handlers based on channel ID"""
    
    def __init__(self):
        self._channel_handlers: Dict[int, List[MessageHandler]] = {}
        self._global_handlers: List[MessageHandler] = []
    
    def register_channel(self, channel_id: int, conditions: List[Callable] = None):
        """Decorator to register a channel-specific handler"""
        def decorator(func):
            handler = MessageHandler(
                func=func,
                conditions=conditions or [],
                description=f"Handler for channel {channel_id}"
            )
            
            if channel_id not in self._channel_handlers:
                self._channel_handlers[channel_id] = []
            self._channel_handlers[channel_id].append(handler)
            
            logger.debug(f"Registered handler {func.__name__} for channel {channel_id}")
            return func
        return decorator
    
    def register_global(self, conditions: List[Callable] = None):
        """Decorator to register a global handler (runs on all messages)"""
        def decorator(func):
            handler = MessageHandler(
                func=func,
                conditions=conditions or [],
                description="Global message handler"
            )
            self._global_handlers.append(handler)
            logger.debug(f"Registered global handler {func.__name__}")
            return func
        return decorator
    
    def add_channel_handler(self, channel_id: int, handler: MessageHandler):
        """Programmatically add a channel handler"""
        if channel_id not in self._channel_handlers:
            self._channel_handlers[channel_id] = []
        self._channel_handlers[channel_id].append(handler)
        logger.debug(f"Added handler {handler.description} for channel {channel_id}")
    
    async def route(self, message: discord.Message, bot_state) -> None:
        """Route message to appropriate handlers"""
        try:
            # Run global handlers first
            for handler in self._global_handlers:
                if await self._should_execute(handler, message):
                    await self._execute_handler(handler, message, bot_state)
            
            # Run channel-specific handlers
            channel_handlers = self._channel_handlers.get(message.channel.id, [])
            for handler in channel_handlers:
                if await self._should_execute(handler, message):
                    await self._execute_handler(handler, message, bot_state)
                    
        except Exception as e:
            logger.exception(f"Error routing message from {message.author} in {message.channel}: {e}")
            # Don't re-raise to prevent bot from crashing
    
    async def _should_execute(self, handler: MessageHandler, message: discord.Message) -> bool:
        """Check if handler should execute based on conditions"""
        try:
            for condition in handler.conditions:
                if asyncio.iscoroutinefunction(condition):
                    if not await condition(message):
                        return False
                else:
                    if not condition(message):
                        return False
            return True
        except Exception as e:
            logger.warning(f"Error checking conditions for handler: {e}")
            return False
    
    async def _execute_handler(self, handler: MessageHandler, message: discord.Message, bot_state) -> None:
        """Execute a message handler safely"""
        try:
            if asyncio.iscoroutinefunction(handler.func):
                await handler.func(message, bot_state)
            else:
                handler.func(message, bot_state)
        except VCBotError as e:
            logger.error(f"Bot error in message handler {handler.description}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in message handler {handler.description}: {e}")

# Create router instance
router = MessageRouter()

# Condition functions
def not_bot_message(message: discord.Message) -> bool:
    """Condition: message is not from a bot"""
    return not message.author.bot

def contains_google_docs(message: discord.Message) -> bool:
    """Condition: message contains Google Docs link"""
    return "docs.google.com" in message.content

# Handler functions
async def handle_clerk_message(message: discord.Message, bot_state):
    """Handle clerk channel messages for bill reference updates"""
    logger.debug(f"Processing clerk message from {message.author}")
    
    try:
        # Import dynamically to avoid circular import
        import importlib
        main_module = importlib.import_module('main')
        update_bill_reference = getattr(main_module, 'update_bill_reference')
        await update_bill_reference(message, bot_state)
    except Exception as e:
        logger.error(f"Failed to update bill reference: {e}")

async def handle_news_message(message: discord.Message, bot_state):
    """Handle news channel messages by appending to news file"""
    logger.debug(f"Appending news message to {bot_state.news_file}")
    
    try:
        # Use async file append
        from async_utils import append_file
        await append_file(bot_state.news_file, message.content + "\n")
    except Exception as e:
        logger.error(f"Failed to append to news file: {e}")

async def handle_sign_message(message: discord.Message, bot_state):
    """Handle bill signing messages with Google Docs links"""
    logger.info(f"Processing bill signing message from {message.author}")
    
    # Notify records channel
    link = message.jump_url
    records_channel = bot_state.get_channel('records')
    if records_channel:
        await records_channel.send(f'<@&1269061253964238919>, a new bill has been signed! {link}')
    
    # Extract and process Google Doc link
    match = re.search(r"https?://docs\.google\.com/\S+", message.content)
    if match:
        doc_link = match.group(0)
        logger.info(f"Found Google Doc link in sign channel: {doc_link}")
        
        try:
            if bot_state.bill_service:
                await bot_state.bill_service.add_bill(doc_link, "bills")
                logger.info("Bill successfully added to database.")
            else:
                logger.error("Bill service not initialized")
        except BillProcessingError as e:
            logger.error(f"Failed to add bill: {e}")
            if records_channel:
                await records_channel.send(f"Error adding bill to database: {str(e)}")
        except Exception as e:
            logger.exception(f"Unexpected error adding bill to database")
            if records_channel:
                await records_channel.send(f"Unexpected error adding bill. Please check logs.")