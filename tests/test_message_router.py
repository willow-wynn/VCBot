#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Message Router System

Tests all components of the message routing system including:
- MessageRouter class functionality
- MessageHandler creation and execution
- Condition functions
- Handler functions with mocked file operations
- Error handling and edge cases

Designed to work without actual Discord connection by mocking Message objects.
"""

import unittest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from pathlib import Path
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from message_router import (
    MessageRouter, MessageHandler, router,
    not_bot_message, contains_google_docs,
    handle_clerk_message, handle_news_message, handle_sign_message
)
from exceptions import VCBotError, BillProcessingError


class MockDiscordMessage:
    """Mock Discord Message class that mimics real discord.Message attributes."""
    
    def __init__(self, content: str = "", channel_id: int = 12345, author_is_bot: bool = False):
        # Core message attributes
        self.content = content
        self.created_at = datetime.now()
        self.edited_at = None
        self.jump_url = f"https://discord.com/channels/guild/{channel_id}/message123"
        
        # Channel information
        self.channel = Mock()
        self.channel.id = channel_id
        self.channel.name = f"test-channel-{channel_id}"
        
        # Author information
        self.author = Mock()
        self.author.bot = author_is_bot
        self.author.id = 123456789 if not author_is_bot else 987654321
        self.author.name = "TestUser" if not author_is_bot else "TestBot"
        self.author.display_name = "TestUser" if not author_is_bot else "TestBot"
        
        # Guild information
        self.guild = Mock()
        self.guild.id = 111111111
        self.guild.name = "Test Guild"
        
        # Additional attributes
        self.attachments = []
        self.embeds = []
        self.reactions = []
        self.mentions = []
        self.reference = None


class MockBotState:
    """Mock BotState class for testing handlers."""
    
    def __init__(self):
        self.clerk_channel_id = 11111
        self.news_channel_id = 22222
        self.sign_channel_id = 33333
        self.news_file = "/tmp/test_news.txt"
        
        # Mock services
        self.file_manager = Mock()
        self.file_manager.append_text = Mock()  # Explicitly add the method
        self.bill_service = Mock()
        self.reference_service = Mock()
        
        # Mock channels
        self.channels = {
            'records': Mock(),
            'news': Mock(), 
            'sign': Mock(),
            'clerk': Mock()
        }
        
    def get_channel(self, name: str):
        return self.channels.get(name)


class TestConditionFunctions(unittest.TestCase):
    """Test condition functions used by message router."""
    
    def test_not_bot_message_with_user(self):
        """Test not_bot_message condition with user message."""
        message = MockDiscordMessage(content="Hello", author_is_bot=False)
        self.assertTrue(not_bot_message(message))
    
    def test_not_bot_message_with_bot(self):
        """Test not_bot_message condition with bot message."""
        message = MockDiscordMessage(content="Hello", author_is_bot=True)
        self.assertFalse(not_bot_message(message))
    
    def test_contains_google_docs_positive(self):
        """Test contains_google_docs with Google Docs URL."""
        message = MockDiscordMessage(content="Check this out: https://docs.google.com/document/d/123/edit")
        self.assertTrue(contains_google_docs(message))
    
    def test_contains_google_docs_negative(self):
        """Test contains_google_docs without Google Docs URL."""
        message = MockDiscordMessage(content="Just a regular message")
        self.assertFalse(contains_google_docs(message))
    
    def test_contains_google_docs_partial_match(self):
        """Test contains_google_docs with partial URL."""
        message = MockDiscordMessage(content="Visit google.com for more info")
        self.assertFalse(contains_google_docs(message))
    
    def test_contains_google_docs_sheets(self):
        """Test contains_google_docs with Google Sheets URL."""
        message = MockDiscordMessage(content="Here's the data: https://docs.google.com/spreadsheets/d/123/")
        self.assertTrue(contains_google_docs(message))


class TestMessageHandler(unittest.TestCase):
    """Test MessageHandler dataclass functionality."""
    
    def test_message_handler_creation(self):
        """Test creating a MessageHandler instance."""
        def test_func(msg, state):
            return "test"
        
        def test_condition(msg):
            return True
        
        handler = MessageHandler(
            func=test_func,
            conditions=[test_condition],
            description="Test handler"
        )
        
        self.assertEqual(handler.func, test_func)
        self.assertEqual(len(handler.conditions), 1)
        self.assertEqual(handler.description, "Test handler")
    
    def test_message_handler_default_conditions(self):
        """Test MessageHandler with default empty conditions."""
        def test_func(msg, state):
            return "test"
        
        handler = MessageHandler(func=test_func, description="Test")
        self.assertEqual(len(handler.conditions), 0)


class TestMessageRouter(unittest.TestCase):
    """Test MessageRouter class functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.router = MessageRouter()
        self.mock_bot_state = MockBotState()
        
    def test_router_initialization(self):
        """Test MessageRouter initialization."""
        self.assertIsInstance(self.router._channel_handlers, dict)
        self.assertIsInstance(self.router._global_handlers, list)
        self.assertEqual(len(self.router._channel_handlers), 0)
        self.assertEqual(len(self.router._global_handlers), 0)
    
    def test_add_channel_handler(self):
        """Test adding a channel handler programmatically."""
        def test_handler(msg, state):
            return "handled"
        
        handler = MessageHandler(func=test_handler, description="Test")
        self.router.add_channel_handler(12345, handler)
        
        self.assertIn(12345, self.router._channel_handlers)
        self.assertEqual(len(self.router._channel_handlers[12345]), 1)
        self.assertEqual(self.router._channel_handlers[12345][0], handler)
    
    def test_multiple_handlers_same_channel(self):
        """Test adding multiple handlers to the same channel."""
        def handler1(msg, state):
            return "handler1"
        
        def handler2(msg, state):
            return "handler2"
        
        h1 = MessageHandler(func=handler1, description="Handler 1")
        h2 = MessageHandler(func=handler2, description="Handler 2")
        
        self.router.add_channel_handler(12345, h1)
        self.router.add_channel_handler(12345, h2)
        
        self.assertEqual(len(self.router._channel_handlers[12345]), 2)
    
    async def test_route_to_correct_channel(self):
        """Test routing message to correct channel handler."""
        executed = []
        
        def test_handler(msg, state):
            executed.append(f"handled-{msg.channel.id}")
        
        handler = MessageHandler(func=test_handler, description="Test")
        self.router.add_channel_handler(12345, handler)
        
        message = MockDiscordMessage(channel_id=12345)
        await self.router.route(message, self.mock_bot_state)
        
        self.assertEqual(executed, ["handled-12345"])
    
    async def test_route_no_handler(self):
        """Test routing message with no matching handler."""
        message = MockDiscordMessage(channel_id=99999)
        
        # Should not raise exception
        await self.router.route(message, self.mock_bot_state)
    
    async def test_condition_filtering(self):
        """Test that conditions properly filter handler execution."""
        executed = []
        
        def test_handler(msg, state):
            executed.append("executed")
        
        def false_condition(msg):
            return False
        
        handler = MessageHandler(
            func=test_handler,
            conditions=[false_condition],
            description="Test"
        )
        self.router.add_channel_handler(12345, handler)
        
        message = MockDiscordMessage(channel_id=12345)
        await self.router.route(message, self.mock_bot_state)
        
        # Should not execute due to false condition
        self.assertEqual(executed, [])
    
    async def test_async_handler_execution(self):
        """Test execution of async handler functions."""
        executed = []
        
        async def async_handler(msg, state):
            executed.append("async-executed")
        
        handler = MessageHandler(func=async_handler, description="Async Test")
        self.router.add_channel_handler(12345, handler)
        
        message = MockDiscordMessage(channel_id=12345)
        await self.router.route(message, self.mock_bot_state)
        
        self.assertEqual(executed, ["async-executed"])
    
    async def test_error_handling_in_router(self):
        """Test that errors in handlers don't crash the router."""
        def failing_handler(msg, state):
            raise Exception("Test error")
        
        handler = MessageHandler(func=failing_handler, description="Failing")
        self.router.add_channel_handler(12345, handler)
        
        message = MockDiscordMessage(channel_id=12345)
        
        # Should not raise exception
        await self.router.route(message, self.mock_bot_state)


class TestHandlerFunctions(unittest.TestCase):
    """Test individual handler functions with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_bot_state = MockBotState()
    
    @patch('importlib.import_module')
    async def test_handle_clerk_message_success(self, mock_import):
        """Test clerk message handler with successful update."""
        # Mock the update_bill_reference function
        mock_main = Mock()
        mock_update_func = AsyncMock(return_value="Updated HR to 123")
        mock_main.update_bill_reference = mock_update_func
        mock_import.return_value = mock_main
        
        message = MockDiscordMessage(content="HR123 has been passed", author_is_bot=False)
        
        await handle_clerk_message(message, self.mock_bot_state)
        
        mock_update_func.assert_called_once_with(message, self.mock_bot_state)
    
    @patch('importlib.import_module')
    async def test_handle_clerk_message_error(self, mock_import):
        """Test clerk message handler with error in update function."""
        # Mock the update function to raise an exception
        mock_main = Mock()
        mock_update_func = AsyncMock(side_effect=Exception("Update failed"))
        mock_main.update_bill_reference = mock_update_func
        mock_import.return_value = mock_main
        
        message = MockDiscordMessage(content="HR123", author_is_bot=False)
        
        # Should not raise exception
        await handle_clerk_message(message, self.mock_bot_state)
    
    async def test_handle_news_message_with_file_manager(self):
        """Test news message handler using file manager."""
        message = MockDiscordMessage(content="Breaking news: New bill passed!")
        
        # Ensure file_manager is properly mocked
        self.mock_bot_state.file_manager = Mock()
        self.mock_bot_state.file_manager.append_text = Mock()
        
        await handle_news_message(message, self.mock_bot_state)
        
        self.mock_bot_state.file_manager.append_text.assert_called_once_with(
            "Breaking news: New bill passed!\n", 
            self.mock_bot_state.news_file
        )
    
    @patch('builtins.open', new_callable=mock_open)
    async def test_handle_news_message_fallback(self, mock_file):
        """Test news message handler fallback to direct file operation."""
        # Disable file manager
        self.mock_bot_state.file_manager = None
        
        message = MockDiscordMessage(content="Emergency news update")
        
        await handle_news_message(message, self.mock_bot_state)
        
        mock_file.assert_called_once_with(self.mock_bot_state.news_file, "a")
        mock_file().write.assert_called_once_with("Emergency news update\n")
    
    async def test_handle_sign_message_with_google_docs(self):
        """Test sign message handler with Google Docs link."""
        message = MockDiscordMessage(
            content="New bill signed: https://docs.google.com/document/d/123/edit",
            channel_id=33333
        )
        
        # Mock records channel
        records_channel = AsyncMock()
        self.mock_bot_state.channels['records'] = records_channel
        
        # Mock bill service
        self.mock_bot_state.bill_service.add_bill = AsyncMock()
        
        await handle_sign_message(message, self.mock_bot_state)
        
        # Verify notification sent to records channel
        records_channel.send.assert_called_once()
        call_args = records_channel.send.call_args[0][0]
        self.assertIn("new bill has been signed", call_args)
        
        # Verify bill service called
        self.mock_bot_state.bill_service.add_bill.assert_called_once_with(
            "https://docs.google.com/document/d/123/edit", 
            "bills"
        )
    
    async def test_handle_sign_message_bill_service_error(self):
        """Test sign message handler with bill service error."""
        message = MockDiscordMessage(
            content="Bill: https://docs.google.com/document/d/123/edit"
        )
        
        # Mock records channel
        records_channel = AsyncMock()
        self.mock_bot_state.channels['records'] = records_channel
        
        # Mock bill service to raise error
        self.mock_bot_state.bill_service.add_bill = AsyncMock(
            side_effect=BillProcessingError("Failed to process bill")
        )
        
        await handle_sign_message(message, self.mock_bot_state)
        
        # Should still send notification but also send error message
        self.assertEqual(records_channel.send.call_count, 2)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete message routing system."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.router = MessageRouter()
        self.mock_bot_state = MockBotState()
        
        # Set up handlers like in bot_state.py
        self.router.add_channel_handler(
            self.mock_bot_state.clerk_channel_id,
            MessageHandler(
                func=handle_clerk_message,
                conditions=[not_bot_message],
                description="Clerk channel handler"
            )
        )
        
        self.router.add_channel_handler(
            self.mock_bot_state.news_channel_id,
            MessageHandler(
                func=handle_news_message,
                conditions=[],
                description="News channel handler"
            )
        )
        
        self.router.add_channel_handler(
            self.mock_bot_state.sign_channel_id,
            MessageHandler(
                func=handle_sign_message,
                conditions=[contains_google_docs],
                description="Sign channel handler"
            )
        )
    
    async def test_clerk_channel_routing(self):
        """Test complete routing for clerk channel message."""
        with patch('importlib.import_module') as mock_import:
            mock_main = Mock()
            mock_update_func = AsyncMock()
            mock_main.update_bill_reference = mock_update_func
            mock_import.return_value = mock_main
            
            message = MockDiscordMessage(
                content="HR123 passed",
                channel_id=self.mock_bot_state.clerk_channel_id,
                author_is_bot=False
            )
            
            await self.router.route(message, self.mock_bot_state)
            
            mock_update_func.assert_called_once()
    
    async def test_clerk_channel_bot_message_ignored(self):
        """Test that bot messages in clerk channel are ignored."""
        with patch('importlib.import_module') as mock_import:
            mock_main = Mock()
            mock_update_func = AsyncMock()
            mock_main.update_bill_reference = mock_update_func
            mock_import.return_value = mock_main
            
            message = MockDiscordMessage(
                content="HR123 passed",
                channel_id=self.mock_bot_state.clerk_channel_id,
                author_is_bot=True  # Bot message
            )
            
            await self.router.route(message, self.mock_bot_state)
            
            # Should not call update function due to bot condition
            mock_update_func.assert_not_called()
    
    async def test_news_channel_routing(self):
        """Test complete routing for news channel message."""
        message = MockDiscordMessage(
            content="Important news update",
            channel_id=self.mock_bot_state.news_channel_id
        )
        
        await self.router.route(message, self.mock_bot_state)
        
        self.mock_bot_state.file_manager.append_text.assert_called_once()
    
    async def test_sign_channel_routing_with_docs(self):
        """Test complete routing for sign channel with Google Docs."""
        message = MockDiscordMessage(
            content="Signed: https://docs.google.com/document/d/123/",
            channel_id=self.mock_bot_state.sign_channel_id
        )
        
        # Mock required services
        records_channel = AsyncMock()
        self.mock_bot_state.channels['records'] = records_channel
        self.mock_bot_state.bill_service.add_bill = AsyncMock()
        
        await self.router.route(message, self.mock_bot_state)
        
        # Verify both notification and bill processing
        records_channel.send.assert_called()
        self.mock_bot_state.bill_service.add_bill.assert_called()
    
    async def test_sign_channel_no_docs_ignored(self):
        """Test that sign channel messages without Google Docs are ignored."""
        message = MockDiscordMessage(
            content="Just a regular message",
            channel_id=self.mock_bot_state.sign_channel_id
        )
        
        records_channel = AsyncMock()
        self.mock_bot_state.channels['records'] = records_channel
        
        await self.router.route(message, self.mock_bot_state)
        
        # Should not process since no Google Docs link
        records_channel.send.assert_not_called()
    
    async def test_unknown_channel_ignored(self):
        """Test that messages from unknown channels are ignored."""
        message = MockDiscordMessage(
            content="Some message",
            channel_id=99999  # Unknown channel
        )
        
        # Should not raise any exceptions
        await self.router.route(message, self.mock_bot_state)


class MessageRouterTestSuite:
    """Test suite runner for message router tests."""
    
    @staticmethod
    def run_all_tests():
        """Run all test classes and return results."""
        test_classes = [
            TestConditionFunctions,
            TestMessageHandler,
            TestMessageRouter,
            TestHandlerFunctions,
            TestIntegration
        ]
        
        total_tests = 0
        failed_tests = 0
        
        print("🔧 Running Message Router Test Suite")
        print("=" * 60)
        
        for test_class in test_classes:
            print(f"\n📋 Running {test_class.__name__}")
            
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            runner = unittest.TextTestRunner(verbosity=1, stream=open(os.devnull, 'w'))
            result = runner.run(suite)
            
            total_tests += result.testsRun
            failed_tests += len(result.failures) + len(result.errors)
            
            if result.failures or result.errors:
                print(f"  ❌ {len(result.failures + result.errors)} failed")
                for failure in result.failures + result.errors:
                    print(f"    • {failure[0]}: {failure[1].splitlines()[0]}")
            else:
                print(f"  ✅ All {result.testsRun} tests passed")
        
        print("\n" + "=" * 60)
        print(f"📊 TOTAL: {total_tests} tests, {failed_tests} failed")
        
        if failed_tests == 0:
            print("🎉 All message router tests passed!")
            return True
        else:
            print(f"❌ {failed_tests} tests failed")
            return False


if __name__ == "__main__":
    # Run tests
    success = MessageRouterTestSuite.run_all_tests()
    
    # Also run async tests
    async def run_async_tests():
        print("\n🔄 Running async integration tests...")
        
        # Test the actual router instance
        test_router = MessageRouter()
        mock_state = MockBotState()
        
        # Test basic routing
        message = MockDiscordMessage(content="Test message")
        await test_router.route(message, mock_state)
        
        print("✅ Async tests completed")
    
    asyncio.run(run_async_tests())
    
    sys.exit(0 if success else 1)