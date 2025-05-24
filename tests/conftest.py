"""
Test configuration and fixtures for VCBot tests.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import discord
from google import genai


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class MockDiscordMessage:
    """Mock Discord Message class that mimics the real discord.Message interface."""
    
    def __init__(
        self,
        content: str = "",
        author_bot: bool = False,
        channel_id: int = 12345,
        author_name: str = "TestUser",
        jump_url: str = "https://discord.com/channels/guild/channel/message"
    ):
        # Core message attributes
        self.content = content
        self.channel = Mock()
        self.channel.id = channel_id
        self.jump_url = jump_url
        self.created_at = datetime.now(timezone.utc)
        
        # Author attributes
        self.author = Mock()
        self.author.bot = author_bot
        self.author.display_name = author_name
        self.author.name = author_name
        self.author.id = 123456789
        
        # Guild attributes (optional)
        self.guild = Mock()
        self.guild.id = 987654321
        self.guild.name = "Test Guild"
        
        # Additional message attributes
        self.attachments = []
        self.embeds = []
        self.reactions = []
        self.mentions = []
        self.reference = None
        self.edited_at = None
        
    def __str__(self):
        return f"MockMessage(content='{self.content[:30]}...', author={self.author.name})"


class MockBotState:
    """Mock BotState class for testing handler functions."""
    
    def __init__(self):
        # Channel IDs
        self.clerk_channel_id = 11111
        self.news_channel_id = 22222
        self.sign_channel_id = 33333
        
        # File paths
        self.news_file = "/tmp/test_news.txt"
        
        # Mock services
        self.file_manager = Mock()
        self.bill_service = AsyncMock()
        self.reference_service = Mock()
        
        # Mock channels dict
        self.channels = {
            'records': Mock()
        }
        
    def get_channel(self, name: str):
        """Mock get_channel method."""
        return self.channels.get(name)


@pytest.fixture
def mock_discord_message():
    """Fixture for creating mock Discord messages."""
    return MockDiscordMessage


@pytest.fixture
def mock_bot_state():
    """Fixture for creating mock bot state."""
    return MockBotState()


@pytest.fixture
def sample_messages(mock_discord_message):
    """Fixture providing various types of test messages."""
    return {
        'human_clerk': mock_discord_message(
            content="H.R. 123 - Test Bill",
            author_bot=False,
            channel_id=11111
        ),
        'bot_clerk': mock_discord_message(
            content="Bot message in clerk",
            author_bot=True,
            channel_id=11111
        ),
        'news': mock_discord_message(
            content="Breaking news: Test successful!",
            channel_id=22222
        ),
        'sign_with_docs': mock_discord_message(
            content="Signed: https://docs.google.com/document/d/123/edit",
            channel_id=33333
        ),
        'sign_without_docs': mock_discord_message(
            content="Regular message without links",
            channel_id=33333
        ),
        'unknown_channel': mock_discord_message(
            content="Message in unknown channel",
            channel_id=99999
        )
    }


@pytest.fixture
def mock_discord_client():
    """Mock Discord client."""
    client = Mock(spec=discord.Client)
    client.user = Mock()
    client.user.id = 123456789
    client.user.name = "TestBot"
    client.get_channel = Mock(return_value=Mock())
    client.get_guild = Mock(return_value=Mock())
    client.bot_state = MockBotState()
    return client


@pytest.fixture
def mock_interaction():
    """Mock Discord interaction."""
    interaction = Mock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = Mock()
    interaction.user.id = 12345
    interaction.user.display_name = "TestUser"
    interaction.user.mention = "<@12345>"
    interaction.user.roles = [Mock(name="Admin")]
    interaction.channel = Mock()
    interaction.channel.id = 12345
    interaction.guild = Mock()
    interaction.guild.id = 98765
    interaction.client = mock_discord_client()
    return interaction


@pytest.fixture
def mock_genai_client():
    """Mock Gemini AI client."""
    client = Mock(spec=genai.Client)
    
    # Mock response with proper structure
    response = Mock()
    response.text = "AI response"
    
    # Mock candidate with content and parts
    candidate = Mock()
    part = Mock()
    part.text = "AI response"
    part.function_call = None  # No function call by default
    
    candidate.content = Mock()
    candidate.content.parts = [part]
    candidate.finish_reason = "STOP"
    
    # Setup candidates list
    response.candidates = [candidate]
    
    # Mock usage metadata
    response.usage_metadata = Mock()
    response.usage_metadata.prompt_token_count = 10
    response.usage_metadata.candidates_token_count = 20
    
    # Mock models
    client.models = Mock()
    client.models.generate_content = Mock(return_value=response)
    
    # Mock chat session for backward compatibility
    chat = AsyncMock()
    chat.send_message = AsyncMock(return_value=response)
    
    client.chats = Mock()
    client.chats.create = Mock(return_value=chat)
    
    return client


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_file_manager(temp_dir):
    """Mock FileManager."""
    from file_manager import FileManager
    return FileManager(temp_dir)


@pytest.fixture
def sample_bill():
    """Sample bill for testing."""
    from models import Bill, BillType
    return Bill(
        identifier="hr-123",
        title="Test Bill Act of 2024",
        bill_type=BillType.HR,
        reference_number=123,
        text_content="This is a test bill.\n\nSection 1: Testing\nSection 2: More testing",
        sponsor="Rep. Test User"
    )


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    from models import Query
    return Query(
        user_id=12345,
        user_name="TestUser",
        query="What is the purpose of HR 123?",
        response="HR 123 is a test bill for testing purposes.",
        channel_id=98765
    )