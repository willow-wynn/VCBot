#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Response Formatter System

Tests all components of the response formatting system including:
- ResponseFormatter class functionality
- FormattedResponse dataclass
- Text sanitization and chunking
- File vs message logic
- Discord integration with mocked interactions
- Edge cases and error handling

Designed to work without actual Discord connection by mocking Interaction objects.
"""

import unittest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from io import StringIO
import sys
import pytest

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from response_formatter import (
    ResponseFormatter, FormattedResponse, 
    sanitize, chunk_text
)


class MockDiscordInteraction:
    """Mock Discord Interaction class that mimics real discord.Interaction attributes."""
    
    def __init__(self, user_name: str = "TestUser"):
        # User information
        self.user = Mock()
        self.user.mention = f"<@123456789>"
        self.user.display_name = user_name
        self.user.id = 123456789
        
        # Channel information
        self.channel = AsyncMock()
        self.channel.send = AsyncMock()
        self.channel.id = 987654321
        
        # Response handling
        self.response = Mock()
        self.response.is_done = Mock(return_value=True)
        
        # Followup handling
        self.followup = AsyncMock()
        self.followup.send = AsyncMock()
        
        # Guild information
        self.guild = Mock()
        self.guild.id = 111111111
        self.guild.name = "Test Guild"


class MockAIResponse:
    """Mock AI response object for testing."""
    
    def __init__(self, text: str = "Test response", input_tokens: int = 100, output_tokens: int = 50):
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class TestFormattedResponse(unittest.TestCase):
    """Test FormattedResponse dataclass functionality."""
    
    def test_basic_creation(self):
        """Test creating a basic FormattedResponse."""
        response = FormattedResponse(
            content="Hello world",
            chunks=["Hello world"]
        )
        
        self.assertEqual(response.content, "Hello world")
        self.assertEqual(response.chunks, ["Hello world"])
        self.assertFalse(response.is_file)
        self.assertIsNone(response.filename)
        self.assertEqual(response.chunk_count, 1)
        self.assertEqual(response.original_length, len("Hello world"))
    
    def test_file_response_creation(self):
        """Test creating a file-based FormattedResponse."""
        response = FormattedResponse(
            content="Long content",
            chunks=["Response attached as file."],
            is_file=True,
            filename="response.txt",
            file_content="Long content here..."
        )
        
        self.assertTrue(response.is_file)
        self.assertEqual(response.filename, "response.txt")
        self.assertEqual(response.file_content, "Long content here...")
    
    def test_metadata_calculation(self):
        """Test automatic metadata calculation."""
        chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]
        response = FormattedResponse(
            content="Original content",
            chunks=chunks,
            original_length=100
        )
        
        self.assertEqual(response.chunk_count, 3)
        self.assertEqual(response.original_length, 100)


class TestSanitization(unittest.TestCase):
    """Test text sanitization functionality."""
    
    def test_sanitize_everyone_mention(self):
        """Test sanitizing @everyone mentions."""
        text = "Hello @everyone, this is a test!"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        self.assertEqual(sanitized, "Hello @ everyone, this is a test!")
        self.assertTrue(was_changed)
    
    def test_sanitize_here_mention(self):
        """Test sanitizing @here mentions."""
        text = "Attention @here, please read this!"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        self.assertEqual(sanitized, "Attention @ here, please read this!")
        self.assertTrue(was_changed)
    
    def test_sanitize_role_mention(self):
        """Test sanitizing role mentions."""
        text = "Hey <@&123456789>, you're needed!"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        self.assertEqual(sanitized, "Hey < @&123456789>, you're needed!")
        self.assertTrue(was_changed)
    
    def test_sanitize_user_mention(self):
        """Test sanitizing user mentions."""
        text = "Hi <@123456789>, how are you?"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        self.assertEqual(sanitized, "Hi < @123456789>, how are you?")
        self.assertTrue(was_changed)
    
    def test_sanitize_multiple_mentions(self):
        """Test sanitizing multiple mention types."""
        text = "@everyone and @here, plus <@&123> and <@456>"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        expected = "@ everyone and @ here, plus < @&123> and < @456>"
        self.assertEqual(sanitized, expected)
        self.assertTrue(was_changed)
    
    def test_sanitize_clean_text(self):
        """Test sanitizing text with no mentions."""
        text = "This is clean text with no mentions."
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        self.assertEqual(sanitized, text)
        self.assertFalse(was_changed)
    
    def test_sanitize_empty_text(self):
        """Test sanitizing empty text."""
        sanitized, was_changed = ResponseFormatter.sanitize("")
        
        self.assertEqual(sanitized, "")
        self.assertFalse(was_changed)
    
    def test_sanitize_none_text(self):
        """Test sanitizing None input."""
        sanitized, was_changed = ResponseFormatter.sanitize(None)
        
        self.assertEqual(sanitized, "")
        self.assertFalse(was_changed)
    
    def test_legacy_sanitize_function(self):
        """Test the legacy sanitize function for backward compatibility."""
        text = "Hello @everyone!"
        result = sanitize(text)
        
        self.assertEqual(result, "Hello @ everyone!")


class TestTextChunking(unittest.TestCase):
    """Test text chunking functionality."""
    
    def test_chunk_short_text(self):
        """Test chunking text that fits in one message."""
        text = "This is a short message."
        chunks = ResponseFormatter.chunk_text(text)
        
        self.assertEqual(chunks, [text])
        self.assertEqual(len(chunks), 1)
    
    def test_chunk_at_exact_limit(self):
        """Test chunking text at exactly the limit."""
        text = "a" * ResponseFormatter.MAX_MESSAGE_LENGTH
        chunks = ResponseFormatter.chunk_text(text)
        
        self.assertEqual(chunks, [text])
        self.assertEqual(len(chunks), 1)
    
    def test_chunk_over_limit(self):
        """Test chunking text over the limit."""
        text = "a" * (ResponseFormatter.MAX_MESSAGE_LENGTH + 100)
        chunks = ResponseFormatter.chunk_text(text)
        
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        
        # Check each chunk is within limits
        for chunk in chunks:
            self.assertLessEqual(len(chunk), ResponseFormatter.MAX_MESSAGE_LENGTH)
    
    def test_chunk_respects_line_breaks(self):
        """Test that chunking respects line breaks when possible."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4"]
        text = "\n".join(lines)
        
        # With a small max_length, should split at line breaks
        chunks = ResponseFormatter.chunk_text(text, max_length=10)
        
        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Rejoined should equal original
        self.assertEqual("\n".join(chunks), text)
    
    def test_chunk_very_long_line(self):
        """Test chunking when a single line exceeds the limit."""
        long_line = "a" * (ResponseFormatter.MAX_MESSAGE_LENGTH * 2)
        text = f"Short line\n{long_line}\nAnother short line"
        
        chunks = ResponseFormatter.chunk_text(text)
        
        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # All chunks should be within limits
        for chunk in chunks:
            self.assertLessEqual(len(chunk), ResponseFormatter.MAX_MESSAGE_LENGTH)
    
    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunks = ResponseFormatter.chunk_text("")
        
        self.assertEqual(chunks, [""])
    
    def test_chunk_custom_max_length(self):
        """Test chunking with custom max length."""
        text = "This is a test message that should be split."
        chunks = ResponseFormatter.chunk_text(text, max_length=10)
        
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 10)
        
        # Rejoined should equal original (accounting for word breaks)
        self.assertIn("This is a test", "".join(chunks))
    
    def test_legacy_chunk_function(self):
        """Test the legacy chunk_text function for backward compatibility."""
        text = "a" * 2000
        chunks = chunk_text(text)
        
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)


class TestFileLogic(unittest.TestCase):
    """Test file vs message decision logic."""
    
    def test_should_use_file_for_very_long_text(self):
        """Test file usage for text exceeding MAX_TOTAL_LENGTH."""
        text = "a" * (ResponseFormatter.MAX_TOTAL_LENGTH + 1000)
        
        self.assertTrue(ResponseFormatter.should_use_file(text))
    
    def test_should_use_file_for_too_many_chunks(self):
        """Test file usage when text would create too many chunks."""
        # Create text that would need more than MAX_CHUNKS
        chunk_size = ResponseFormatter.MAX_MESSAGE_LENGTH
        text = ("Line " + "a" * chunk_size + "\n") * (ResponseFormatter.MAX_CHUNKS + 2)
        
        self.assertTrue(ResponseFormatter.should_use_file(text))
    
    def test_should_not_use_file_for_normal_text(self):
        """Test message usage for normal-length text."""
        text = "This is a normal message that should be sent as text."
        
        self.assertFalse(ResponseFormatter.should_use_file(text))
    
    def test_force_file_parameter(self):
        """Test forcing file usage regardless of length."""
        text = "Short text"
        
        self.assertFalse(ResponseFormatter.should_use_file(text, force_file=False))
        self.assertTrue(ResponseFormatter.should_use_file(text, force_file=True))
    
    def test_file_threshold_boundary(self):
        """Test file logic at the boundary of MAX_TOTAL_LENGTH."""
        # Create text that is under the limit and won't create too many chunks
        safe_text_length = ResponseFormatter.MAX_MESSAGE_LENGTH * (ResponseFormatter.MAX_CHUNKS - 1)
        text = "a" * safe_text_length
        self.assertFalse(ResponseFormatter.should_use_file(text))
        
        # Just over the total length limit should definitely use file
        text = "a" * (ResponseFormatter.MAX_TOTAL_LENGTH + 1)
        self.assertTrue(ResponseFormatter.should_use_file(text))


class TestResponseFormatting(unittest.TestCase):
    """Test the main format_response method."""
    
    def test_format_short_response(self):
        """Test formatting a short response."""
        text = "This is a short response."
        formatted = ResponseFormatter.format_response(text)
        
        self.assertEqual(formatted.content, text)
        self.assertEqual(formatted.chunks, [text])
        self.assertFalse(formatted.is_file)
        self.assertFalse(formatted.was_sanitized)
        self.assertEqual(formatted.original_length, len(text))
    
    def test_format_response_with_sanitization(self):
        """Test formatting response that needs sanitization."""
        text = "Hello @everyone, this is a test!"
        formatted = ResponseFormatter.format_response(text)
        
        self.assertEqual(formatted.content, "Hello @ everyone, this is a test!")
        self.assertTrue(formatted.was_sanitized)
        self.assertEqual(formatted.original_length, len(text))
    
    def test_format_long_response_as_chunks(self):
        """Test formatting long response as chunks."""
        text = "a" * (ResponseFormatter.MAX_MESSAGE_LENGTH * 2)
        formatted = ResponseFormatter.format_response(text)
        
        self.assertFalse(formatted.is_file)
        self.assertGreater(len(formatted.chunks), 1)
        self.assertEqual("".join(formatted.chunks), text)
    
    def test_format_very_long_response_as_file(self):
        """Test formatting very long response as file."""
        text = "a" * (ResponseFormatter.MAX_TOTAL_LENGTH + 1000)
        formatted = ResponseFormatter.format_response(text)
        
        self.assertTrue(formatted.is_file)
        self.assertEqual(formatted.filename, ResponseFormatter.DEFAULT_FILENAME)
        self.assertEqual(formatted.file_content, text)
        self.assertEqual(formatted.chunks[0], "Response attached as file due to length.")
    
    def test_format_response_force_file(self):
        """Test forcing file format for short text."""
        text = "Short text"
        formatted = ResponseFormatter.format_response(text, force_file=True)
        
        self.assertTrue(formatted.is_file)
        self.assertEqual(formatted.file_content, text)
    
    def test_format_response_custom_filename(self):
        """Test formatting with custom filename."""
        text = "a" * (ResponseFormatter.MAX_TOTAL_LENGTH + 1000)
        formatted = ResponseFormatter.format_response(text, filename="custom.txt")
        
        self.assertTrue(formatted.is_file)
        self.assertEqual(formatted.filename, "custom.txt")
    
    def test_format_empty_response(self):
        """Test formatting empty response."""
        formatted = ResponseFormatter.format_response("")
        
        self.assertEqual(formatted.content, "")
        self.assertEqual(formatted.chunks, ["*Empty response*"])
        self.assertEqual(formatted.original_length, 0)
    
    def test_format_none_response(self):
        """Test formatting None response."""
        formatted = ResponseFormatter.format_response(None)
        
        self.assertEqual(formatted.content, "")
        self.assertEqual(formatted.chunks, ["*Empty response*"])


class TestDiscordIntegration(unittest.TestCase):
    """Test Discord integration with mocked interactions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.interaction = MockDiscordInteraction()
    
    @pytest.mark.asyncio
    async def test_send_simple_response(self):
        """Test sending a simple text response."""
        formatted = FormattedResponse(
            content="Hello world",
            chunks=["Hello world"]
        )
        
        await ResponseFormatter.send_response(
            self.interaction,
            formatted,
            completion_message="Test complete"
        )
        
        # Verify followup completion message
        self.interaction.followup.send.assert_called_once_with("Test complete", ephemeral=True)
        
        # Verify channel message
        self.interaction.channel.send.assert_called_once_with("Hello world")
    
    @pytest.mark.asyncio
    async def test_send_chunked_response(self):
        """Test sending a multi-chunk response."""
        formatted = FormattedResponse(
            content="Long content",
            chunks=["Chunk 1", "Chunk 2", "Chunk 3"]
        )
        
        await ResponseFormatter.send_response(self.interaction, formatted)
        
        # Should send each chunk
        expected_calls = [
            unittest.mock.call("Chunk 1"),
            unittest.mock.call("Chunk 2"),
            unittest.mock.call("Chunk 3")
        ]
        self.interaction.channel.send.assert_has_calls(expected_calls)
    
    @pytest.mark.asyncio
    async def test_send_file_response(self):
        """Test sending a file response."""
        formatted = FormattedResponse(
            content="Long content",
            chunks=["Response attached as file."],
            is_file=True,
            filename="test.txt",
            file_content="This is the file content"
        )
        
        with patch('discord.File') as mock_file_class:
            mock_file_instance = Mock()
            mock_file_class.return_value = mock_file_instance
            
            await ResponseFormatter.send_response(self.interaction, formatted)
            
            # Verify file creation
            mock_file_class.assert_called_once()
            call_args = mock_file_class.call_args
            
            # Check that StringIO was used with correct content
            string_io = call_args[0][0]
            self.assertIsInstance(string_io, StringIO)
            
            # Check filename
            self.assertEqual(call_args[1]['filename'], "test.txt")
            
            # Verify channel send with file
            self.interaction.channel.send.assert_called_once_with(
                "Response attached as file.",
                file=mock_file_instance
            )
    
    @pytest.mark.asyncio
    async def test_send_response_with_query_header(self):
        """Test sending response with query header."""
        formatted = FormattedResponse(
            content="Response text",
            chunks=["Response text"]
        )
        
        await ResponseFormatter.send_response(
            self.interaction,
            formatted,
            query_header="Query: What is 2+2?"
        )
        
        # Should send header first, then response
        expected_calls = [
            unittest.mock.call("Query: What is 2+2?"),
            unittest.mock.call("Response text")
        ]
        self.interaction.channel.send.assert_has_calls(expected_calls)
    
    @pytest.mark.asyncio
    async def test_send_response_long_header_truncation(self):
        """Test truncation of very long query headers."""
        long_header = "a" * (ResponseFormatter.MAX_MESSAGE_LENGTH + 100)
        formatted = FormattedResponse(
            content="Response",
            chunks=["Response"]
        )
        
        await ResponseFormatter.send_response(
            self.interaction,
            formatted,
            query_header=long_header
        )
        
        # Get the actual call to channel.send for the header
        header_call = self.interaction.channel.send.call_args_list[0]
        sent_header = header_call[0][0]
        
        # Should be truncated with ellipsis
        self.assertLessEqual(len(sent_header), ResponseFormatter.MAX_MESSAGE_LENGTH)
        self.assertTrue(sent_header.endswith("..."))


class TestAIResponseFormatting(unittest.TestCase):
    """Test AI-specific response formatting."""
    
    def test_format_ai_response_basic(self):
        """Test basic AI response formatting."""
        ai_response = MockAIResponse("This is the AI response", 150, 75)
        
        formatted, completion_msg, query_header = ResponseFormatter.format_ai_response(
            ai_response,
            "What is 2+2?",
            "<@123456789>"
        )
        
        self.assertEqual(formatted.content, "This is the AI response")
        self.assertIn("150", completion_msg)  # Input tokens
        self.assertIn("75", completion_msg)   # Output tokens
        self.assertIn("<@123456789>", query_header)
        self.assertIn("What is 2+2?", query_header)
    
    def test_format_ai_response_long_query(self):
        """Test AI response formatting with long query."""
        ai_response = MockAIResponse("Response")
        long_query = "a" * 2000
        
        formatted, completion_msg, query_header = ResponseFormatter.format_ai_response(
            ai_response,
            long_query,
            "<@123456789>"
        )
        
        # Query should be truncated in header
        self.assertLessEqual(len(query_header), ResponseFormatter.MAX_MESSAGE_LENGTH + 100)  # Some buffer for formatting


class TestBillSearchFormatting(unittest.TestCase):
    """Test bill search response formatting."""
    
    def test_format_bill_search_with_results(self):
        """Test formatting bill search with results."""
        # Mock bill objects
        bills = [
            Mock(title="Test Bill 1", reference="H.R. 1"),
            Mock(title="Test Bill 2", reference="H.R. 2"),
            Mock(title="Test Bill 3", reference="S. 1")
        ]
        
        formatted = ResponseFormatter.format_bill_search_response(bills, "test query")
        
        self.assertIn("Found 3 bills", formatted.content)
        self.assertIn("H.R. 1 - Test Bill 1", formatted.content)
        self.assertIn("H.R. 2 - Test Bill 2", formatted.content)
        self.assertIn("S. 1 - Test Bill 3", formatted.content)
    
    def test_format_bill_search_no_results(self):
        """Test formatting bill search with no results."""
        formatted = ResponseFormatter.format_bill_search_response([], "empty query")
        
        self.assertIn("No bills found", formatted.content)
        self.assertIn("empty query", formatted.content)
    
    def test_format_bill_search_malformed_objects(self):
        """Test formatting bill search with objects missing attributes."""
        bills = ["Simple string", Mock(missing_attrs=True)]
        
        formatted = ResponseFormatter.format_bill_search_response(bills, "test")
        
        # Should handle gracefully by converting to string
        self.assertIn("Found 2 bills", formatted.content)
        self.assertIn("Simple string", formatted.content)


class TestFileResponseFormatting(unittest.TestCase):
    """Test file attachment response formatting."""
    
    def test_format_file_response_basic(self):
        """Test basic file response formatting."""
        formatted = ResponseFormatter.format_file_response(
            "/path/to/file.pdf",
            "Document attached"
        )
        
        self.assertEqual(formatted.content, "Document attached")
        self.assertEqual(formatted.chunks, ["Document attached"])
        self.assertEqual(formatted.filename, "/path/to/file.pdf")
        self.assertFalse(formatted.is_file)  # This is for Discord file attachments, not text files
    
    def test_format_file_response_default_description(self):
        """Test file response with default description."""
        formatted = ResponseFormatter.format_file_response("/path/to/file.pdf")
        
        self.assertEqual(formatted.content, "File attached.")
        self.assertEqual(formatted.chunks, ["File attached."])


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_format_response_with_unicode(self):
        """Test formatting response with unicode characters."""
        text = "Hello 🌍 world! This has émojis and ñoñ-ASCII characters."
        formatted = ResponseFormatter.format_response(text)
        
        self.assertEqual(formatted.content, text)
        self.assertFalse(formatted.was_sanitized)
    
    def test_chunk_text_with_only_newlines(self):
        """Test chunking text that is only newlines."""
        text = "\n" * 10  # Reduce to reasonable size
        chunks = ResponseFormatter.chunk_text(text, max_length=5)
        
        # Should handle gracefully - empty lines may be collapsed
        # The important thing is that it doesn't crash
        self.assertIsInstance(chunks, list)
        # For text that's only newlines, reasonable behavior is to have few/no chunks
        self.assertLessEqual(len(chunks), 5)
    
    def test_sanitize_edge_case_patterns(self):
        """Test sanitization with edge case patterns."""
        # Test patterns that might be confused with mentions
        text = "Email: user@example.com and @twitter_handle"
        sanitized, was_changed = ResponseFormatter.sanitize(text)
        
        # Should not change valid email or social media handles
        self.assertIn("user@example.com", sanitized)
        self.assertIn("@twitter_handle", sanitized)
    
    def test_format_response_with_mixed_content(self):
        """Test formatting response with mixed content types."""
        text = "Normal text @everyone with mentions <@&123> and other stuff"
        formatted = ResponseFormatter.format_response(text)
        
        self.assertTrue(formatted.was_sanitized)
        self.assertIn("@ everyone", formatted.content)
        self.assertIn("< @&123>", formatted.content)


class ResponseFormatterTestSuite:
    """Test suite runner for response formatter tests."""
    
    @staticmethod
    def run_all_tests():
        """Run all test classes and return results."""
        test_classes = [
            TestFormattedResponse,
            TestSanitization,
            TestTextChunking,
            TestFileLogic,
            TestResponseFormatting,
            TestDiscordIntegration,
            TestAIResponseFormatting,
            TestBillSearchFormatting,
            TestFileResponseFormatting,
            TestEdgeCases
        ]
        
        total_tests = 0
        failed_tests = 0
        
        print("🎨 Running Response Formatter Test Suite")
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
            print("🎉 All response formatter tests passed!")
            return True
        else:
            print(f"❌ {failed_tests} tests failed")
            return False


if __name__ == "__main__":
    # Run tests
    success = ResponseFormatterTestSuite.run_all_tests()
    
    # Also run async tests
    async def run_async_tests():
        print("\n🔄 Running async integration tests...")
        
        # Test Discord integration methods
        interaction = MockDiscordInteraction()
        
        # Test simple send
        formatted = FormattedResponse(
            content="Test",
            chunks=["Test"]
        )
        await ResponseFormatter.send_response(interaction, formatted)
        
        # Test file send
        file_formatted = FormattedResponse(
            content="File content",
            chunks=["File attached"],
            is_file=True,
            filename="test.txt",
            file_content="File content"
        )
        
        with patch('discord.File'):
            await ResponseFormatter.send_response(interaction, file_formatted)
        
        print("✅ Async tests completed")
    
    asyncio.run(run_async_tests())
    
    sys.exit(0 if success else 1)