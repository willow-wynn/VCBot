#!/usr/bin/env python3
"""
Production-mimicking tests for Response Formatter System

Tests the response formatter in scenarios that mimic actual production usage,
including integration with Discord.py objects and real AI responses.
"""

import asyncio
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from io import StringIO

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from response_formatter import ResponseFormatter, FormattedResponse


class ProductionResponseFormatterTests:
    """Production-mimicking tests for response formatter."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []
    
    def assert_true(self, condition, message="Assertion failed"):
        """Simple assertion helper."""
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  ✅ Test {self.tests_run}: PASS")
        else:
            self.failures.append(f"Test {self.tests_run}: {message}")
            print(f"  ❌ Test {self.tests_run}: FAIL - {message}")
    
    def test_real_ai_response_formatting(self):
        """Test formatting responses that mimic real AI outputs."""
        print("\n📋 Testing Real AI Response Formatting")
        
        # Test with a realistic AI response about congressional rules
        ai_text = """Based on the House Rules and congressional procedures, here are the key points about bill passage:

1. **Introduction Phase**: Bills must be introduced by a Representative and assigned a number (H.R. for House bills, H.Res. for House resolutions).

2. **Committee Review**: Most bills are referred to the appropriate committee(s) for detailed review, markup, and potential amendments.

3. **Floor Consideration**: If approved by committee, bills proceed to the House floor for debate and voting.

4. **Voting Process**: 
   - Voice vote for routine matters
   - Division vote when voice vote is unclear  
   - Recorded vote (roll call) for final passage of most bills

5. **Senate Process**: House-passed bills then go to the Senate for similar consideration.

The specific requirements for passage depend on the type of legislation and whether it's a regular bill, joint resolution, or constitutional amendment."""
        
        formatted = ResponseFormatter.format_response(ai_text)
        
        self.assert_true(
            not formatted.is_file,
            "Normal AI response should not require file attachment"
        )
        
        self.assert_true(
            len(formatted.chunks) >= 1,
            "AI response should produce at least one chunk"
        )
        
        self.assert_true(
            formatted.was_sanitized == False,
            "Clean AI response should not need sanitization"
        )
        
        # Test total length preservation
        reconstructed = "".join(formatted.chunks)
        self.assert_true(
            len(reconstructed) == len(ai_text),
            "Chunked text should preserve original length"
        )
    
    def test_malicious_content_sanitization(self):
        """Test sanitization of potentially malicious content."""
        print("\n📋 Testing Malicious Content Sanitization")
        
        malicious_content = """
        URGENT: @everyone @here please check this immediately!
        
        Attention <@&123456789> (Admin role) - we need your action on this bill.
        
        Personal message for <@987654321> about the vote.
        """
        
        formatted = ResponseFormatter.format_response(malicious_content)
        
        self.assert_true(
            formatted.was_sanitized,
            "Malicious content should be marked as sanitized"
        )
        
        self.assert_true(
            "@ everyone" in formatted.content,
            "Should sanitize @everyone mentions"
        )
        
        self.assert_true(
            "@ here" in formatted.content, 
            "Should sanitize @here mentions"
        )
        
        self.assert_true(
            "< @&" in formatted.content,
            "Should sanitize role mentions"  
        )
        
        self.assert_true(
            "< @9" in formatted.content,
            "Should sanitize user mentions"
        )
    
    def test_very_long_bill_text(self):
        """Test handling of very long bill texts."""
        print("\n📋 Testing Very Long Bill Text")
        
        # Simulate a very long bill (like a comprehensive spending bill)
        bill_sections = []
        for section in range(1, 101):  # 100 sections
            bill_sections.append(f"""
SECTION {section}: APPROPRIATIONS FOR DEPARTMENT X-{section}

(a) GENERAL PROVISION - There is hereby appropriated for fiscal year 2024, out of any money in the Treasury not otherwise appropriated, for the Department of Example-{section}, the sum of ${'1' * 50} dollars for the following purposes:

(1) Administrative expenses including personnel, equipment, and facilities;
(2) Program operations and maintenance;
(3) Capital improvements and infrastructure development;
(4) Research and development initiatives;
(5) Grants and cooperative agreements with state and local entities.

(b) LIMITATIONS - None of the funds appropriated under this section may be used for purposes not explicitly authorized under existing law.

(c) REPORTING REQUIREMENTS - The Secretary shall submit quarterly reports to Congress on the use of these funds.
""")
        
        very_long_bill = "\n".join(bill_sections)
        
        formatted = ResponseFormatter.format_response(very_long_bill)
        
        self.assert_true(
            formatted.is_file,
            "Very long bill should be sent as file attachment"
        )
        
        self.assert_true(
            formatted.filename.endswith('.txt'),
            "File should have .txt extension"
        )
        
        self.assert_true(
            formatted.file_content == formatted.content,
            "File content should match formatted content"
        )
        
        self.assert_true(
            "Response attached as file" in formatted.chunks[0],
            "Should indicate file attachment to user"
        )
    
    async def test_discord_integration_simulation(self):
        """Test integration with simulated Discord objects."""
        print("\n📋 Testing Discord Integration Simulation")
        
        # Create mock Discord interaction that behaves like the real thing
        interaction = Mock()
        interaction.user.mention = "<@123456789>"
        interaction.user.display_name = "TestCongressman"
        interaction.followup.send = AsyncMock()
        interaction.channel.send = AsyncMock()
        
        # Mock AI response
        ai_response = Mock()
        ai_response.text = "The Affordable Care Act contains several key provisions for healthcare coverage..."
        ai_response.input_tokens = 250
        ai_response.output_tokens = 180
        
        query = "What are the main provisions of the Affordable Care Act?"
        
        # Test the complete AI response formatting workflow
        formatted, completion_msg, query_header = ResponseFormatter.format_ai_response(
            ai_response, query, interaction.user.mention
        )
        
        await ResponseFormatter.send_response(
            interaction, formatted, completion_msg, query_header
        )
        
        # Verify the interaction calls
        self.assert_true(
            interaction.followup.send.called,
            "Should send completion message via followup"
        )
        
        self.assert_true(
            interaction.channel.send.called,
            "Should send content via channel"
        )
        
        # Check completion message format
        followup_call = interaction.followup.send.call_args
        completion_text = followup_call[0][0]
        
        self.assert_true(
            "Input tokens: 250" in completion_text,
            "Completion message should include input tokens"
        )
        
        self.assert_true(
            "Output tokens: 180" in completion_text,
            "Completion message should include output tokens"
        )
        
        # Check that ephemeral flag is set
        self.assert_true(
            followup_call[1]['ephemeral'] == True,
            "Completion message should be ephemeral"
        )
    
    def test_edge_case_responses(self):
        """Test edge cases that might occur in production."""
        print("\n📋 Testing Edge Case Responses")
        
        # Test empty response
        formatted_empty = ResponseFormatter.format_response("")
        self.assert_true(
            "*Empty response*" in formatted_empty.chunks[0],
            "Empty response should be handled gracefully"
        )
        
        # Test None response  
        formatted_none = ResponseFormatter.format_response(None)
        self.assert_true(
            "*Empty response*" in formatted_none.chunks[0],
            "None response should be handled gracefully"
        )
        
        # Test response with only whitespace
        formatted_whitespace = ResponseFormatter.format_response("   \n\n   \t  ")
        self.assert_true(
            len(formatted_whitespace.chunks) >= 1,
            "Whitespace response should produce chunks"
        )
        
        # Test response with unicode characters (emojis, accents)
        unicode_text = "🏛️ Congressional Update: The résumé of the naïve café owner was reviewed 📋"
        formatted_unicode = ResponseFormatter.format_response(unicode_text)
        self.assert_true(
            "🏛️" in formatted_unicode.content,
            "Unicode characters should be preserved"
        )
        
        self.assert_true(
            "résumé" in formatted_unicode.content,
            "Accented characters should be preserved"
        )
    
    def test_bill_search_formatting(self):
        """Test formatting of bill search results."""
        print("\n📋 Testing Bill Search Formatting")
        
        # Mock bill objects similar to what the actual system returns
        mock_bills = []
        for i in range(1, 6):
            bill = Mock()
            bill.title = f"Test Bill {i} - Important Legislation Act of 2024"
            bill.reference = f"H.R. {i}"
            mock_bills.append(bill)
        
        formatted = ResponseFormatter.format_bill_search_response(
            mock_bills, "healthcare reform"
        )
        
        self.assert_true(
            "Found 5 bills" in formatted.content,
            "Should indicate number of bills found"
        )
        
        self.assert_true(
            "H.R. 1 - Test Bill 1" in formatted.content,
            "Should include bill reference and title"
        )
        
        self.assert_true(
            "healthcare reform" in formatted.content,
            "Should include original search query"
        )
        
        # Test empty search results
        empty_formatted = ResponseFormatter.format_bill_search_response([], "nonexistent topic")
        self.assert_true(
            "No bills found" in empty_formatted.content,
            "Should handle empty search results gracefully"
        )
    
    async def run_all_tests(self):
        """Run all production-mimicking tests."""
        print("🎭 Running Production-Mimicking Response Formatter Tests")
        print("=" * 60)
        
        self.test_real_ai_response_formatting()
        self.test_malicious_content_sanitization() 
        self.test_very_long_bill_text()
        await self.test_discord_integration_simulation()
        self.test_edge_case_responses()
        self.test_bill_search_formatting()
        
        print("\n" + "=" * 60)
        print(f"📊 PRODUCTION TESTS: {self.tests_passed}/{self.tests_run} passed")
        
        if self.failures:
            print("\n❌ FAILED TESTS:")
            for failure in self.failures:
                print(f"  • {failure}")
            return False
        else:
            print("🎉 All production tests passed!")
            return True


async def main():
    """Main test runner."""
    tester = ProductionResponseFormatterTests()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ Response formatter is production-ready!")
        sys.exit(0)
    else:
        print("\n❌ Production tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())