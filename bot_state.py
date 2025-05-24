"""
Bot state management for VCBot.

This module encapsulates all runtime state for the bot, eliminating the need
for global variables scattered throughout the codebase.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import discord
from google import genai
from google.genai import types

from settings import Settings
from services import AIService, BillService, ReferenceService
from file_manager import FileManager
from pathlib import Path
from message_router import MessageRouter, MessageHandler, not_bot_message, contains_google_docs
from repositories import BillReferenceRepository, QueryLogRepository, BillRepository, VectorRepository


@dataclass
class BotState:
    """Encapsulates all bot runtime state."""
    
    # Discord state
    client: discord.Client
    
    # AI state
    genai_client: genai.Client
    tools: Any  # Gemini tools declaration
    
    # Configuration
    bot_id: int
    discord_token: str
    guild_id: int
    
    # Channel IDs (for reference before channels are loaded)
    records_channel_id: int
    news_channel_id: int
    sign_channel_id: int
    clerk_channel_id: int
    main_chat_id: int
    
    # File paths
    bill_ref_file: str
    news_file: str
    queries_file: str
    
    # Fields with defaults must come last
    channels: Dict[str, discord.TextChannel] = field(default_factory=dict)
    tool_functions: Optional[Dict[str, callable]] = None
    
    # Service instances
    ai_service: Optional[AIService] = None
    bill_service: Optional[BillService] = None
    reference_service: Optional[ReferenceService] = None
    file_manager: Optional[FileManager] = None
    message_router: Optional[MessageRouter] = None
    
    # Repository instances
    bill_reference_repo: Optional[BillReferenceRepository] = None
    query_log_repo: Optional[QueryLogRepository] = None
    bill_repo: Optional[BillRepository] = None
    vector_repo: Optional[VectorRepository] = None
    
    @classmethod
    def from_settings(cls, client: discord.Client, settings: Settings):
        """Initialize BotState from settings."""
        return cls(
            client=client,
            genai_client=genai.Client(api_key=settings.gemini_api_key),
            tools=None,  # Set separately after initialization
            bot_id=settings.bot_id,
            discord_token=settings.discord_token,
            guild_id=settings.guild_id,
            records_channel_id=settings.channels.records_channel,
            news_channel_id=settings.channels.news_channel,
            sign_channel_id=settings.channels.sign_channel,
            clerk_channel_id=settings.channels.clerk_channel,
            main_chat_id=settings.channels.main_chat,
            bill_ref_file=str(settings.file_storage.bill_ref_file),
            news_file=str(settings.file_storage.news_file),
            queries_file=str(settings.file_storage.queries_file),
            channels={},  # Populated in on_ready
            tool_functions=None,  # Set in on_ready
        )
    
    def initialize_channels(self):
        """Initialize Discord channel objects from IDs."""
        self.channels['records'] = self.client.get_channel(self.records_channel_id)
        self.channels['news'] = self.client.get_channel(self.news_channel_id)
        self.channels['sign'] = self.client.get_channel(self.sign_channel_id)
        self.channels['clerk'] = self.client.get_channel(self.clerk_channel_id)
        self.channels['main_chat'] = self.client.get_channel(self.main_chat_id)
        
        # Log channel initialization
        for name, channel in self.channels.items():
            if channel:
                print(f"{name.title()} Channel: {channel.id}: {channel.name}")
            else:
                print(f"{name.title()} Channel: Not Found (ID: {getattr(self, f'{name}_channel_id', 'Unknown')})")
    
    def get_channel(self, name: str) -> Optional[discord.TextChannel]:
        """Get a channel by name."""
        return self.channels.get(name)
    
    def set_tools(self, tools: Any):
        """Set the Gemini tools declaration."""
        self.tools = tools
    
    def set_tool_functions(self, tool_functions: Dict[str, callable]):
        """Set the tool functions dictionary."""
        self.tool_functions = tool_functions
    
    def initialize_services(self, bill_directories: Dict[str, str], vector_pickle_path: str):
        """Initialize service instances.
        
        Args:
            bill_directories: Dictionary of bill storage directories
            vector_pickle_path: Path to vector pickle file
        """
        # Initialize file manager first
        self.file_manager = FileManager(Path.cwd())
        
        # Initialize repositories
        self.bill_reference_repo = BillReferenceRepository(Path(self.bill_ref_file))
        self.query_log_repo = QueryLogRepository(Path(self.queries_file))
        self.bill_repo = BillRepository(
            text_dir=Path(bill_directories.get("billtexts", "billtexts")),
            pdf_dir=Path(bill_directories.get("billpdfs", "billpdfs")),
            metadata_dir=Path(bill_directories.get("billmeta", "billmeta"))
        )
        self.vector_repo = VectorRepository(Path(vector_pickle_path))
        
        # Initialize services with repositories
        self.ai_service = AIService(
            genai_client=self.genai_client,
            tools=self.tools,
            tool_functions=self.tool_functions,
            file_manager=self.file_manager,
            discord_client=self.client
        )
        
        self.bill_service = BillService(
            genai_client=self.genai_client,
            bill_directories=bill_directories,
            file_manager=self.file_manager
        )
        
        self.reference_service = ReferenceService(
            ref_file_path=self.bill_ref_file,
            file_manager=self.file_manager,
            repository=self.bill_reference_repo
        )
    
    def initialize_message_router(self):
        """Initialize message router with dynamic channel IDs."""
        from message_router import router, handle_clerk_message, handle_news_message, handle_sign_message
        from logging_config import logger
        
        # Register handlers with actual channel IDs
        router.add_channel_handler(
            self.clerk_channel_id,
            MessageHandler(
                func=handle_clerk_message,
                conditions=[not_bot_message],
                description=f"Clerk channel handler ({self.clerk_channel_id})"
            )
        )
        
        router.add_channel_handler(
            self.news_channel_id,
            MessageHandler(
                func=handle_news_message,
                conditions=[],
                description=f"News channel handler ({self.news_channel_id})"
            )
        )
        
        router.add_channel_handler(
            self.sign_channel_id,
            MessageHandler(
                func=handle_sign_message,
                conditions=[contains_google_docs],
                description=f"Sign channel handler ({self.sign_channel_id})"
            )
        )
        
        self.message_router = router
        logger.info(f"Message router initialized with {len(router._channel_handlers)} channel handlers")