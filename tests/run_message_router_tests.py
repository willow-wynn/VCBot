#!/usr/bin/env python3
"""
Simplified test runner for Message Router tests with proper async handling.
"""

import asyncio
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from message_router import (
    MessageRouter, MessageHandler, router,
    not_bot_message, contains_google_docs,
    handle_clerk_message, handle_news_message, handle_sign_message
)
from exceptions import VCBotError, BillProcessingError


class MockDiscordMessage:
    """Mock Discord Message class."""
    
    def __init__(self, content="", author_bot=False, channel_id=12345, author_name="TestUser", jump_url="https://discord.com/test"):
        self.content = content
        self.channel = Mock()
        self.channel.id = channel_id
        self.jump_url = jump_url
        self.created_at = datetime.now(timezone.utc)
        
        self.author = Mock()
        self.author.bot = author_bot
        self.author.display_name = author_name
        self.author.name = author_name
        self.author.id = 123456789


class MockBotState:
    """Mock BotState class."""
    
    def __init__(self):
        self.clerk_channel_id = 11111
        self.news_channel_id = 22222
        self.sign_channel_id = 33333
        self.news_file = "/tmp/test_news.txt"
        
        self.file_manager = Mock()
        self.bill_service = AsyncMock()
        self.reference_service = Mock()
        
        self.channels = {'records': Mock()}
        
    def get_channel(self, name: str):
        return self.channels.get(name)


class MessageRouterTestSuite:
    """Test suite for message router system."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def run_test(self, test_name, test_func):
        """Run a single test and track results."""
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            print(f"  ✅ {test_name}")
            self.passed += 1
        except Exception as e:
            print(f"  ❌ {test_name}: {str(e)}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
    
    def test_condition_functions(self):
        """Test condition functions."""
        print("\n🧪 Testing Condition Functions")
        
        def test_not_bot_message_human():
            msg = MockDiscordMessage(author_bot=False)
            assert not_bot_message(msg) == True
        
        def test_not_bot_message_bot():
            msg = MockDiscordMessage(author_bot=True)
            assert not_bot_message(msg) == False
        
        def test_contains_google_docs_positive():
            msg = MockDiscordMessage(content="Check out https://docs.google.com/document/d/123/edit")
            assert contains_google_docs(msg) == True
        
        def test_contains_google_docs_negative():
            msg = MockDiscordMessage(content="Regular message without links")
            assert contains_google_docs(msg) == False
        
        self.run_test("not_bot_message with human", test_not_bot_message_human)
        self.run_test("not_bot_message with bot", test_not_bot_message_bot)
        self.run_test("contains_google_docs positive", test_contains_google_docs_positive)
        self.run_test("contains_google_docs negative", test_contains_google_docs_negative)
    
    def test_message_router_class(self):
        """Test MessageRouter class functionality."""
        print("\n🧪 Testing MessageRouter Class")
        
        def test_router_initialization():
            router = MessageRouter()
            assert router._channel_handlers == {}
            assert router._global_handlers == []
        
        def test_add_channel_handler():
            router = MessageRouter()
            handler = MessageHandler(func=lambda msg, state: None)
            router.add_channel_handler(12345, handler)
            assert 12345 in router._channel_handlers
            assert len(router._channel_handlers[12345]) == 1
        
        async def test_route_execution():
            router = MessageRouter()
            calls = []
            
            def test_handler(msg, state):
                calls.append("called")
            
            handler = MessageHandler(func=test_handler)
            router.add_channel_handler(12345, handler)
            
            msg = MockDiscordMessage(channel_id=12345)
            state = MockBotState()
            
            await router.route(msg, state)
            assert calls == ["called"]
        
        async def test_condition_filtering():
            router = MessageRouter()
            calls = []
            
            def test_handler(msg, state):
                calls.append("called")
            
            def always_false(msg):
                return False
            
            handler = MessageHandler(func=test_handler, conditions=[always_false])
            router.add_channel_handler(12345, handler)
            
            msg = MockDiscordMessage(channel_id=12345)
            state = MockBotState()
            
            await router.route(msg, state)
            assert calls == []  # Handler should not be called due to condition
        
        self.run_test("router initialization", test_router_initialization)
        self.run_test("add channel handler", test_add_channel_handler)
        self.run_test("route execution", test_route_execution)
        self.run_test("condition filtering", test_condition_filtering)
    
    def test_handler_functions(self):
        """Test handler functions."""
        print("\n🧪 Testing Handler Functions")
        
        async def test_handle_news_message():
            msg = MockDiscordMessage(content="Test news")
            state = MockBotState()
            
            await handle_news_message(msg, state)
            state.file_manager.append_text.assert_called_once_with("Test news\n", state.news_file)
        
        async def test_handle_news_message_fallback():
            msg = MockDiscordMessage(content="Test news fallback")
            state = MockBotState()
            state.file_manager = None
            
            # Use a real temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                state.news_file = tmp.name
            
            try:
                await handle_news_message(msg, state)
                
                # Check file content
                with open(state.news_file, 'r') as f:
                    content = f.read()
                    assert content == "Test news fallback\n"
            finally:
                if os.path.exists(state.news_file):
                    os.unlink(state.news_file)
        
        async def test_handle_sign_message():
            msg = MockDiscordMessage(
                content="Signed: https://docs.google.com/document/d/123/edit",
                jump_url="https://discord.com/test"
            )
            state = MockBotState()
            
            records_channel = Mock()
            records_channel.send = AsyncMock()
            state.channels['records'] = records_channel
            
            await handle_sign_message(msg, state)
            
            # Check notification was sent
            records_channel.send.assert_called()
            # Check bill service was called
            state.bill_service.add_bill.assert_called_once()
        
        async def test_handle_clerk_message():
            msg = MockDiscordMessage(content="H.R. 123 - Test Bill")
            state = MockBotState()
            
            mock_update_function = AsyncMock()
            with patch('importlib.import_module') as mock_import:
                mock_main_module = Mock()
                mock_main_module.update_bill_reference = mock_update_function
                mock_import.return_value = mock_main_module
                
                await handle_clerk_message(msg, state)
                mock_update_function.assert_called_once_with(msg, state)
        
        self.run_test("handle news message", test_handle_news_message)
        self.run_test("handle news message fallback", test_handle_news_message_fallback)
        self.run_test("handle sign message", test_handle_sign_message)
        self.run_test("handle clerk message", test_handle_clerk_message)
    
    def test_integration(self):
        """Test end-to-end integration."""
        print("\n🧪 Testing Integration")
        
        async def test_complete_routing():
            router = MessageRouter()
            state = MockBotState()
            
            # Add handlers like in the real system
            router.add_channel_handler(
                state.clerk_channel_id,
                MessageHandler(func=handle_clerk_message, conditions=[not_bot_message])
            )
            
            router.add_channel_handler(
                state.news_channel_id,
                MessageHandler(func=handle_news_message, conditions=[])
            )
            
            router.add_channel_handler(
                state.sign_channel_id,
                MessageHandler(func=handle_sign_message, conditions=[contains_google_docs])
            )
            
            # Test clerk message (human)
            clerk_msg = MockDiscordMessage(
                content="H.R. 456 - Integration Test",
                channel_id=state.clerk_channel_id,
                author_bot=False
            )
            
            mock_update_function = AsyncMock()
            with patch('importlib.import_module') as mock_import:
                mock_main_module = Mock()
                mock_main_module.update_bill_reference = mock_update_function
                mock_import.return_value = mock_main_module
                
                await router.route(clerk_msg, state)
                mock_update_function.assert_called_once()
            
            # Test news message
            news_msg = MockDiscordMessage(
                content="Integration news",
                channel_id=state.news_channel_id
            )
            
            await router.route(news_msg, state)
            state.file_manager.append_text.assert_called_with("Integration news\n", state.news_file)
            
            # Test sign message with docs
            sign_msg = MockDiscordMessage(
                content="Signed: docs.google.com/document/d/123",
                channel_id=state.sign_channel_id
            )
            
            records_channel = Mock()
            records_channel.send = AsyncMock()
            state.channels['records'] = records_channel
            
            await router.route(sign_msg, state)
            state.bill_service.add_bill.assert_called()
        
        async def test_condition_filtering_integration():
            router = MessageRouter()
            state = MockBotState()
            
            router.add_channel_handler(
                state.clerk_channel_id,
                MessageHandler(func=handle_clerk_message, conditions=[not_bot_message])
            )
            
            # Bot message should be ignored
            bot_msg = MockDiscordMessage(
                content="Bot message",
                channel_id=state.clerk_channel_id,
                author_bot=True
            )
            
            with patch('importlib.import_module') as mock_import:
                mock_main_module = Mock()
                mock_main_module.update_bill_reference = AsyncMock()
                mock_import.return_value = mock_main_module
                
                await router.route(bot_msg, state)
                mock_main_module.update_bill_reference.assert_not_called()
        
        self.run_test("complete routing", test_complete_routing)
        self.run_test("condition filtering integration", test_condition_filtering_integration)
    
    def test_error_handling(self):
        """Test error handling."""
        print("\n🧪 Testing Error Handling")
        
        async def test_handler_error_isolation():
            router = MessageRouter()
            
            def error_handler(msg, state):
                raise ValueError("Test error")
            
            handler = MessageHandler(func=error_handler)
            router.add_channel_handler(12345, handler)
            
            msg = MockDiscordMessage(channel_id=12345)
            state = MockBotState()
            
            # Should not raise an exception
            await router.route(msg, state)
        
        async def test_condition_error_handling():
            router = MessageRouter()
            
            def error_condition(msg):
                raise ValueError("Condition error")
            
            def normal_handler(msg, state):
                pass  # Should not be called
            
            handler = MessageHandler(func=normal_handler, conditions=[error_condition])
            router.add_channel_handler(12345, handler)
            
            msg = MockDiscordMessage(channel_id=12345)
            state = MockBotState()
            
            # Should not raise an exception
            await router.route(msg, state)
        
        async def test_bill_processing_error():
            msg = MockDiscordMessage(content="docs.google.com/document/error")
            state = MockBotState()
            state.bill_service.add_bill.side_effect = BillProcessingError("Test error")
            
            records_channel = Mock()
            records_channel.send = AsyncMock()
            state.channels['records'] = records_channel
            
            # Should not raise an exception
            await handle_sign_message(msg, state)
            records_channel.send.assert_called()
        
        self.run_test("handler error isolation", test_handler_error_isolation)
        self.run_test("condition error handling", test_condition_error_handling)
        self.run_test("bill processing error", test_bill_processing_error)
    
    def run_all_tests(self):
        """Run all test suites."""
        print("🚀 Starting Message Router Test Suite")
        print("=" * 60)
        
        self.test_condition_functions()
        self.test_message_router_class()
        self.test_handler_functions()
        self.test_integration()
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Success Rate: {(self.passed / (self.passed + self.failed)) * 100:.1f}%")
        
        if self.errors:
            print("\n❌ Failed Tests:")
            for name, error in self.errors:
                print(f"  • {name}: {error}")
        
        return self.failed == 0


def main():
    """Main test runner."""
    suite = MessageRouterTestSuite()
    success = suite.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n💥 {suite.failed} tests failed!")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())