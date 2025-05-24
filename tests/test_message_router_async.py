#!/usr/bin/env python3
"""
Async Test Runner for Message Router System

Properly runs async tests with asyncio support.
"""

import asyncio
import unittest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, mock_open

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_message_router import (
    MockDiscordMessage, MockBotState, TestMessageRouter, 
    TestHandlerFunctions, TestIntegration
)


class AsyncTestRunner:
    """Test runner that properly handles async test methods."""
    
    @staticmethod
    async def run_async_test_class(test_class_instance):
        """Run all async test methods in a test class."""
        test_methods = [method for method in dir(test_class_instance) 
                       if method.startswith('test_') and 
                       asyncio.iscoroutinefunction(getattr(test_class_instance, method))]
        
        results = []
        for method_name in test_methods:
            method = getattr(test_class_instance, method_name)
            try:
                await method()
                results.append((method_name, True, None))
                print(f"  ✅ {method_name}")
            except Exception as e:
                results.append((method_name, False, str(e)))
                print(f"  ❌ {method_name}: {e}")
        
        return results


async def main():
    """Run all async message router tests."""
    print("🔄 Running Async Message Router Tests")
    print("=" * 50)
    
    total_tests = 0
    failed_tests = 0
    
    # Test MessageRouter async methods
    print("\n📋 Testing MessageRouter async methods")
    router_test = TestMessageRouter()
    router_test.setUp()
    
    router_results = await AsyncTestRunner.run_async_test_class(router_test)
    total_tests += len(router_results)
    failed_tests += sum(1 for _, passed, _ in router_results if not passed)
    
    # Test handler functions
    print("\n📋 Testing Handler Functions")
    handler_test = TestHandlerFunctions()
    handler_test.setUp()
    
    handler_results = await AsyncTestRunner.run_async_test_class(handler_test)
    total_tests += len(handler_results)
    failed_tests += sum(1 for _, passed, _ in handler_results if not passed)
    
    # Test integration scenarios
    print("\n📋 Testing Integration Scenarios")
    integration_test = TestIntegration()
    integration_test.setUp()
    
    integration_results = await AsyncTestRunner.run_async_test_class(integration_test)
    total_tests += len(integration_results)
    failed_tests += sum(1 for _, passed, _ in integration_results if not passed)
    
    # Test realistic Discord scenarios
    print("\n📋 Testing Realistic Discord Scenarios")
    await test_realistic_scenarios()
    total_tests += 4  # Number of realistic scenarios
    
    print("\n" + "=" * 50)
    print(f"📊 ASYNC TESTS SUMMARY")
    print(f"Total: {total_tests}, Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("🎉 All async tests passed!")
        return True
    else:
        print(f"❌ {failed_tests} async tests failed")
        return False


async def test_realistic_scenarios():
    """Test realistic Discord message scenarios."""
    from message_router import MessageRouter, MessageHandler, not_bot_message, contains_google_docs
    
    # Create router with realistic setup
    router = MessageRouter()
    mock_state = MockBotState()
    
    # Test scenario 1: User posts bill reference in clerk channel
    print("  🧪 Testing clerk channel bill reference...")
    executed = []
    
    async def mock_clerk_handler(msg, state):
        executed.append(f"clerk-{msg.content}")
    
    router.add_channel_handler(
        mock_state.clerk_channel_id,
        MessageHandler(
            func=mock_clerk_handler,
            conditions=[not_bot_message],
            description="Mock clerk handler"
        )
    )
    
    user_message = MockDiscordMessage(
        content="HR123 - Healthcare Reform Act passed 250-180",
        channel_id=mock_state.clerk_channel_id,
        author_is_bot=False
    )
    
    await router.route(user_message, mock_state)
    assert len(executed) == 1
    print("    ✅ User message processed correctly")
    
    # Test scenario 2: Bot message should be ignored
    bot_message = MockDiscordMessage(
        content="Automated update: HR123 recorded",
        channel_id=mock_state.clerk_channel_id,
        author_is_bot=True
    )
    
    await router.route(bot_message, mock_state)
    assert len(executed) == 1  # Should not increase
    print("    ✅ Bot message correctly ignored")
    
    # Test scenario 3: News channel message
    print("  🧪 Testing news channel message...")
    news_executed = []
    
    async def mock_news_handler(msg, state):
        news_executed.append(msg.content)
    
    router.add_channel_handler(
        mock_state.news_channel_id,
        MessageHandler(func=mock_news_handler, description="Mock news handler")
    )
    
    news_message = MockDiscordMessage(
        content="BREAKING: Supreme Court ruling affects Congressional procedures",
        channel_id=mock_state.news_channel_id
    )
    
    await router.route(news_message, mock_state)
    assert len(news_executed) == 1
    print("    ✅ News message processed correctly")
    
    # Test scenario 4: Sign channel with Google Docs
    print("  🧪 Testing sign channel with Google Docs...")
    sign_executed = []
    
    async def mock_sign_handler(msg, state):
        sign_executed.append(f"signed-{msg.content[:20]}...")
    
    router.add_channel_handler(
        mock_state.sign_channel_id,
        MessageHandler(
            func=mock_sign_handler,
            conditions=[contains_google_docs],
            description="Mock sign handler"
        )
    )
    
    sign_message = MockDiscordMessage(
        content="President signs H.R. 456: https://docs.google.com/document/d/abc123/edit",
        channel_id=mock_state.sign_channel_id
    )
    
    await router.route(sign_message, mock_state)
    assert len(sign_executed) == 1
    print("    ✅ Sign message with Google Docs processed correctly")
    
    # Test scenario 5: Sign channel without Google Docs should be ignored
    no_docs_message = MockDiscordMessage(
        content="General discussion about the bill signing ceremony",
        channel_id=mock_state.sign_channel_id
    )
    
    await router.route(no_docs_message, mock_state)
    assert len(sign_executed) == 1  # Should not increase
    print("    ✅ Sign message without Google Docs correctly ignored")


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)