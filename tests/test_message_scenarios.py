#!/usr/bin/env python3
"""
Real-world message routing scenarios test.

This test simulates actual Discord message scenarios that would occur
in the VCBot environment to ensure the message router handles them correctly.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from message_router import MessageRouter, MessageHandler, not_bot_message, contains_google_docs


class RealisticDiscordMessage:
    """Very realistic Discord Message mock based on discord.py documentation."""
    
    def __init__(self, content, channel_id, author_bot=False, author_name="TestUser", guild_id=987654321):
        # Core attributes from discord.py Message class
        self.content = content
        self.created_at = datetime.now(timezone.utc)
        self.edited_at = None
        self.jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/123456789"
        
        # Channel info
        self.channel = Mock()
        self.channel.id = channel_id
        self.channel.name = f"channel-{channel_id}"
        self.channel.type = "text"
        
        # Author info  
        self.author = Mock()
        self.author.id = 123456789 if not author_bot else 987654321
        self.author.name = author_name
        self.author.display_name = author_name
        self.author.bot = author_bot
        self.author.avatar = None
        
        # Guild info
        self.guild = Mock()
        self.guild.id = guild_id
        self.guild.name = "Virtual Congress"
        
        # Additional attributes
        self.attachments = []
        self.embeds = []
        self.mentions = []
        self.reactions = []
        self.reference = None  # For reply chains
        self.flags = Mock()
        
    def __repr__(self):
        return f"<Message id=123456789 channel={self.channel.name} author={self.author.name}>"


class VCBotMessageScenarios:
    """Test realistic VCBot message scenarios."""
    
    def __init__(self):
        # Channel IDs based on actual VCBot setup
        self.CLERK_CHANNEL = 1037456401708105780  # From main.py
        self.NEWS_CHANNEL = 22222  # Mock
        self.SIGN_CHANNEL = 33333  # Mock
        self.MAIN_CHAT = 654467992272371712  # From main.py
        self.BOT_HELPER = 1327483297202176080  # From main.py
        
        self.test_results = []
    
    def log_result(self, test_name, success, details=""):
        """Log test result."""
        status = "✅" if success else "❌"
        print(f"  {status} {test_name}")
        if details:
            print(f"    {details}")
        self.test_results.append((test_name, success, details))
    
    async def test_clerk_channel_scenarios(self):
        """Test various clerk channel message scenarios."""
        print("\n📋 Testing Clerk Channel Scenarios")
        
        router = MessageRouter()
        calls = []
        
        async def mock_clerk_handler(msg, state):
            calls.append(f"clerk:{msg.content[:20]}")
        
        # Register clerk handler with realistic conditions
        router.add_channel_handler(
            self.CLERK_CHANNEL,
            MessageHandler(
                func=mock_clerk_handler,
                conditions=[not_bot_message],
                description="Clerk channel bill reference handler"
            )
        )
        
        mock_state = Mock()
        
        # Scenario 1: Human user posts bill reference
        bill_msg = RealisticDiscordMessage(
            content="H.R. 123 - The Test Bill Act of 2025",
            channel_id=self.CLERK_CHANNEL,
            author_bot=False,
            author_name="RepresentativeSmith"
        )
        
        await router.route(bill_msg, mock_state)
        self.log_result(
            "Human bill reference in clerk channel", 
            len(calls) == 1 and "clerk:H.R. 123" in calls[0]
        )
        
        # Scenario 2: Bot message should be ignored
        bot_msg = RealisticDiscordMessage(
            content="Bot: Bill H.R. 123 has been processed",
            channel_id=self.CLERK_CHANNEL,
            author_bot=True,
            author_name="VCBot"
        )
        
        calls.clear()
        await router.route(bot_msg, mock_state)
        self.log_result(
            "Bot message ignored in clerk channel",
            len(calls) == 0
        )
        
        # Scenario 3: Multiple bill references in one message
        multi_bill_msg = RealisticDiscordMessage(
            content="Processing H.R. 456, S. 789, and H.Res. 101 for today's session",
            channel_id=self.CLERK_CHANNEL,
            author_bot=False,
            author_name="ClerkStaff"
        )
        
        calls.clear()
        await router.route(multi_bill_msg, mock_state)
        self.log_result(
            "Multiple bill references handled",
            len(calls) == 1 and "clerk:Processing" in calls[0]
        )
    
    async def test_news_channel_scenarios(self):
        """Test news channel message scenarios."""
        print("\n📰 Testing News Channel Scenarios")
        
        router = MessageRouter()
        news_content = []
        
        async def mock_news_handler(msg, state):
            news_content.append(msg.content)
        
        router.add_channel_handler(
            self.NEWS_CHANNEL,
            MessageHandler(
                func=mock_news_handler,
                conditions=[],  # No conditions - all messages logged
                description="News channel logger"
            )
        )
        
        mock_state = Mock()
        
        # Scenario 1: Official news announcement
        official_news = RealisticDiscordMessage(
            content="BREAKING: Virtual Congress passes landmark climate legislation with bipartisan support",
            channel_id=self.NEWS_CHANNEL,
            author_name="NewsBot"
        )
        
        await router.route(official_news, mock_state)
        self.log_result(
            "Official news announcement logged",
            len(news_content) == 1 and "BREAKING" in news_content[0]
        )
        
        # Scenario 2: Multi-line news update
        multiline_news = RealisticDiscordMessage(
            content="""Committee Update:
            - Finance Committee met today
            - 3 bills advanced to floor
            - Next meeting scheduled for Friday""",
            channel_id=self.NEWS_CHANNEL,
            author_name="CommitteeChair"
        )
        
        news_content.clear()
        await router.route(multiline_news, mock_state)
        self.log_result(
            "Multi-line news update logged",
            len(news_content) == 1 and "Committee Update" in news_content[0]
        )
        
        # Scenario 3: Bot and human messages both logged
        bot_news = RealisticDiscordMessage(
            content="Automated daily summary: 15 bills in committee, 3 on floor",
            channel_id=self.NEWS_CHANNEL,
            author_bot=True,
            author_name="AutoNewsBot"
        )
        
        news_content.clear()
        await router.route(bot_news, mock_state)
        self.log_result(
            "Bot news messages also logged",
            len(news_content) == 1 and "Automated daily summary" in news_content[0]
        )
    
    async def test_sign_channel_scenarios(self):
        """Test bill signing channel scenarios."""
        print("\n✍️  Testing Bill Signing Channel Scenarios")
        
        router = MessageRouter()
        signed_bills = []
        notifications_sent = []
        
        async def mock_sign_handler(msg, state):
            signed_bills.append(msg.content)
            # Mock sending notification
            notifications_sent.append(f"Bill signed: {msg.jump_url}")
        
        router.add_channel_handler(
            self.SIGN_CHANNEL,
            MessageHandler(
                func=mock_sign_handler,
                conditions=[contains_google_docs],
                description="Bill signing processor"
            )
        )
        
        mock_state = Mock()
        
        # Scenario 1: Presidential signature with Google Doc
        presidential_sign = RealisticDiscordMessage(
            content="I hereby sign into law H.R. 123 - The Test Act. Full text: https://docs.google.com/document/d/1234567890abcdef/edit",
            channel_id=self.SIGN_CHANNEL,
            author_name="President"
        )
        
        await router.route(presidential_sign, mock_state)
        self.log_result(
            "Presidential signature with Google Doc processed",
            len(signed_bills) == 1 and "hereby sign" in signed_bills[0]
        )
        
        # Scenario 2: Message without Google Doc should be ignored
        no_doc_msg = RealisticDiscordMessage(
            content="I am considering signing H.R. 456 after review",
            channel_id=self.SIGN_CHANNEL,
            author_name="President"
        )
        
        signed_bills.clear()
        await router.route(no_doc_msg, mock_state)
        self.log_result(
            "Message without Google Doc ignored",
            len(signed_bills) == 0
        )
        
        # Scenario 3: Multiple Google Doc links in one message
        multi_doc_sign = RealisticDiscordMessage(
            content="Signing both H.R. 789 (https://docs.google.com/document/d/first) and S. 456 (docs.google.com/document/d/second)",
            channel_id=self.SIGN_CHANNEL,
            author_name="President"
        )
        
        signed_bills.clear()
        await router.route(multi_doc_sign, mock_state)
        self.log_result(
            "Multiple Google Doc links handled",
            len(signed_bills) == 1 and "Signing both" in signed_bills[0]
        )
        
        # Scenario 4: Google Sheets/Forms links also trigger handler
        sheets_msg = RealisticDiscordMessage(
            content="Budget spreadsheet signed: docs.google.com/spreadsheets/d/budget123",
            channel_id=self.SIGN_CHANNEL,
            author_name="President"
        )
        
        signed_bills.clear()
        await router.route(sheets_msg, mock_state)
        self.log_result(
            "Google Sheets links also processed",
            len(signed_bills) == 1
        )
    
    async def test_multi_channel_routing(self):
        """Test routing across multiple channels simultaneously."""
        print("\n🔀 Testing Multi-Channel Routing")
        
        router = MessageRouter()
        all_calls = []
        
        async def clerk_handler(msg, state):
            all_calls.append(f"CLERK:{msg.author.name}")
        
        async def news_handler(msg, state):
            all_calls.append(f"NEWS:{msg.author.name}")
        
        async def sign_handler(msg, state):
            all_calls.append(f"SIGN:{msg.author.name}")
        
        # Register all handlers
        router.add_channel_handler(self.CLERK_CHANNEL, MessageHandler(clerk_handler, [not_bot_message]))
        router.add_channel_handler(self.NEWS_CHANNEL, MessageHandler(news_handler, []))
        router.add_channel_handler(self.SIGN_CHANNEL, MessageHandler(sign_handler, [contains_google_docs]))
        
        mock_state = Mock()
        
        # Send messages to all channels
        messages = [
            RealisticDiscordMessage("H.R. 999", self.CLERK_CHANNEL, author_name="Rep1"),
            RealisticDiscordMessage("Breaking news", self.NEWS_CHANNEL, author_name="NewsUser"),
            RealisticDiscordMessage("Signed: docs.google.com/test", self.SIGN_CHANNEL, author_name="President"),
            RealisticDiscordMessage("Random message", 99999, author_name="RandomUser")  # Unknown channel
        ]
        
        for msg in messages:
            await router.route(msg, mock_state)
        
        expected_calls = {"CLERK:Rep1", "NEWS:NewsUser", "SIGN:President"}
        actual_calls = set(all_calls)
        
        self.log_result(
            "Multi-channel routing works correctly",
            expected_calls == actual_calls,
            f"Expected: {expected_calls}, Got: {actual_calls}"
        )
    
    async def test_error_resilience(self):
        """Test system resilience to errors."""
        print("\n🛡️  Testing Error Resilience")
        
        router = MessageRouter()
        successful_calls = []
        
        def error_handler(msg, state):
            if "error" in msg.content:
                raise ValueError(f"Handler error for: {msg.content}")
            successful_calls.append(msg.content)
        
        def error_condition(msg):
            if "condition_error" in msg.content:
                raise RuntimeError("Condition evaluation error")
            return True
        
        router.add_channel_handler(
            12345,
            MessageHandler(
                func=error_handler,
                conditions=[error_condition],
                description="Error-prone handler"
            )
        )
        
        mock_state = Mock()
        
        # Test messages that should cause errors
        test_messages = [
            RealisticDiscordMessage("normal message", 12345),  # Should work
            RealisticDiscordMessage("error message", 12345),   # Handler error
            RealisticDiscordMessage("condition_error message", 12345),  # Condition error
            RealisticDiscordMessage("another normal message", 12345),  # Should work
        ]
        
        for msg in test_messages:
            # Should not raise exceptions
            await router.route(msg, mock_state)
        
        # Only normal messages should have been processed
        expected_successful = ["normal message", "another normal message"]
        
        self.log_result(
            "System resilient to handler errors",
            successful_calls == expected_successful,
            f"Successfully processed: {successful_calls}"
        )
    
    async def test_global_handlers(self):
        """Test global message handlers."""
        print("\n🌍 Testing Global Handlers")
        
        router = MessageRouter()
        global_calls = []
        
        @router.register_global()
        async def global_logger(msg, state):
            global_calls.append(f"GLOBAL:{msg.channel.id}")
        
        mock_state = Mock()
        
        # Send messages to various channels
        channels = [self.CLERK_CHANNEL, self.NEWS_CHANNEL, 99999, 88888]
        for i, channel_id in enumerate(channels):
            msg = RealisticDiscordMessage(f"Message {i}", channel_id)
            await router.route(msg, mock_state)
        
        expected_global_calls = [f"GLOBAL:{ch}" for ch in channels]
        
        self.log_result(
            "Global handlers process all messages",
            global_calls == expected_global_calls,
            f"Global calls: {len(global_calls)}, Expected: {len(expected_global_calls)}"
        )
    
    async def run_all_scenarios(self):
        """Run all test scenarios."""
        print("🚀 VCBot Message Router - Real-World Scenarios Test")
        print("=" * 70)
        
        scenarios = [
            self.test_clerk_channel_scenarios,
            self.test_news_channel_scenarios,
            self.test_sign_channel_scenarios,
            self.test_multi_channel_routing,
            self.test_error_resilience,
            self.test_global_handlers
        ]
        
        for scenario in scenarios:
            try:
                await scenario()
            except Exception as e:
                print(f"  ❌ Scenario failed with error: {e}")
                self.test_results.append((scenario.__name__, False, str(e)))
        
        # Print summary
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        
        print("\n" + "=" * 70)
        print("📊 SCENARIO TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        print(f"📈 Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All real-world scenarios pass! Message router is production-ready!")
        else:
            print(f"\n⚠️  {total - passed} scenarios need attention before production deployment.")
        
        return passed == total


async def main():
    """Run scenario tests."""
    tester = VCBotMessageScenarios()
    success = await tester.run_all_scenarios()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)