"""Tests for AIService."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from google.genai import types
from services.ai_service import AIService
from exceptions import AIServiceError, ToolExecutionError


class TestAIService:
    """Test cases for AIService."""
    
    @pytest.fixture
    def ai_service(self, mock_genai_client, mock_file_manager):
        """Create an AIService instance."""
        # Mock tools
        tools = Mock()
        tool_functions = {
            "test_tool": Mock(return_value="tool result"),
            "async_tool": AsyncMock(return_value="async tool result")
        }
        
        return AIService(
            genai_client=mock_genai_client,
            tools=tools,
            tool_functions=tool_functions,
            file_manager=mock_file_manager
        )
    
    @pytest.mark.asyncio
    async def test_process_query_simple(self, ai_service):
        """Test processing a simple query without tools."""
        # Setup
        query = "What is the capital of France?"
        context = []
        user_id = 12345
        
        # Execute
        response = await ai_service.process_query(query, context, user_id)
        
        # Verify
        assert response.text == "AI response"
        assert not response.used_tools
        assert response.input_tokens == 10
        assert response.output_tokens == 20
    
    @pytest.mark.asyncio
    async def test_process_query_with_context(self, ai_service):
        """Test processing query with conversation context."""
        # Setup
        query = "Tell me more about that"
        context = [
            types.Content(parts=[types.Part(text="User: What is Python?")]),
            types.Content(parts=[types.Part(text="Assistant: Python is a programming language.")])
        ]
        user_id = 12345
        
        # Execute
        response = await ai_service.process_query(query, context, user_id)
        
        # Verify generate_content was called with context
        ai_service.genai_client.models.generate_content.assert_called_once()
        call_args = ai_service.genai_client.models.generate_content.call_args
        assert "contents" in call_args[1]
        assert call_args[1]["contents"] == context
    
    @pytest.mark.asyncio
    async def test_process_query_with_tool_call(self, ai_service):
        """Test processing query that triggers tool use."""
        # Setup mock response with tool call
        tool_call = Mock()
        tool_call.name = "test_tool"
        tool_call.args = {"param": "value"}
        
        # First response with tool call
        mock_response1 = Mock()
        mock_response1.text = ""
        mock_response1.candidates = Mock()
        mock_response1.candidates.__getitem__ = Mock(return_value=Mock())
        mock_response1.candidates[0].content = Mock()
        mock_response1.candidates[0].content.parts = [Mock()]
        mock_response1.candidates[0].content.parts[0].function_call = tool_call
        mock_response1.usage_metadata = Mock(prompt_token_count=10, candidates_token_count=20)
        
        # Second response with final text
        mock_response2 = Mock()
        mock_response2.text = "Final response"
        mock_response2.candidates = Mock()
        mock_response2.candidates.__getitem__ = Mock(return_value=Mock())
        mock_response2.candidates[0].content = Mock()
        mock_response2.candidates[0].content.parts = []
        mock_response2.usage_metadata = Mock(prompt_token_count=15, candidates_token_count=25)
        
        # Setup mock to return both responses
        ai_service.genai_client.models.generate_content.side_effect = [mock_response1, mock_response2]
        
        # Execute
        response = await ai_service.process_query("Use the test tool", [], 12345)
        
        # Verify
        assert response.text == "Final response"
        assert response.used_tools
        assert ai_service.tool_functions["test_tool"].called
    
    @pytest.mark.asyncio
    async def test_save_query_log(self, ai_service, temp_dir):
        """Test saving query log to CSV."""
        # Setup
        log_file = temp_dir / "queries.csv"
        
        # Execute
        await ai_service.save_query_log(
            query="Test query",
            response="Test response",
            file_path=str(log_file)
        )
        
        # Verify
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test query" in content
        assert "Test response" in content
    
    def test_build_system_prompt(self, ai_service):
        """Test system prompt generation."""
        # Test with user ID (no is_admin parameter in actual implementation)
        prompt = ai_service._build_system_prompt(123)
        assert "Virtual Congress" in prompt
        assert "helper" in prompt.lower()
        assert "Gemini" in prompt
    
    @pytest.mark.asyncio
    async def test_execute_tool_sync(self, ai_service):
        """Test executing synchronous tool."""
        # Setup
        function_call = Mock()
        function_call.name = "test_tool"
        function_call.args = {"param": "value"}
        
        # Execute
        result = await ai_service._execute_tool(function_call)
        
        # Verify
        assert result == "tool result"
        ai_service.tool_functions["test_tool"].assert_called_with(param="value")
    
    @pytest.mark.asyncio
    async def test_execute_tool_async(self, ai_service):
        """Test executing asynchronous tool."""
        # Setup
        function_call = Mock()
        function_call.name = "async_tool"
        function_call.args = {"param": "value"}
        
        # Execute
        result = await ai_service._execute_tool(function_call)
        
        # Verify
        assert result == "async tool result"
        ai_service.tool_functions["async_tool"].assert_called_with(param="value")
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, ai_service):
        """Test executing non-existent tool."""
        # Setup
        function_call = Mock()
        function_call.name = "nonexistent_tool"
        function_call.args = {}
        
        # Execute & Verify
        with pytest.raises(ToolExecutionError) as exc_info:
            await ai_service._execute_tool(function_call)
        assert "Unknown tool" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, ai_service):
        """Test tool execution error handling."""
        # Setup tool that raises exception
        ai_service.tool_functions["error_tool"] = Mock(side_effect=ValueError("Tool error"))
        
        function_call = Mock()
        function_call.name = "error_tool"
        function_call.args = {}
        
        # Execute & Verify
        with pytest.raises(ToolExecutionError) as exc_info:
            await ai_service._execute_tool(function_call)
        assert "Tool error" in str(exc_info.value)


class TestAIServiceIntegration:
    """Integration tests for AIService."""
    
    @pytest.fixture
    def ai_service(self, mock_genai_client, mock_file_manager):
        """Create AI service for integration tests."""
        tools = Mock()
        tool_functions = {
            "test_tool": Mock(return_value="tool result"),
            "async_tool": AsyncMock(return_value="async tool result")
        }
        
        return AIService(
            genai_client=mock_genai_client,
            tools=tools,
            tool_functions=tool_functions,
            file_manager=mock_file_manager
        )
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, ai_service):
        """Test a full conversation with multiple turns."""
        # First query
        response1 = await ai_service.process_query(
            "What is HR 123?",
            [],
            12345
        )
        assert response1.text == "AI response"
        
        # Follow-up with context
        context = [
            types.Content(parts=[types.Part(text="User: What is HR 123?")]),
            types.Content(parts=[types.Part(text=f"Assistant: {response1.text}")])
        ]
        
        response2 = await ai_service.process_query(
            "What are its main provisions?",
            context,
            12345
        )
        assert response2.text == "AI response"
    
    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self, ai_service):
        """Test handling of rate limits."""
        # Setup mock to simulate rate limit error
        ai_service.genai_client.models.generate_content.side_effect = Exception("Rate limit exceeded")
        
        # Execute & Verify
        with pytest.raises(AIServiceError):
            await ai_service.process_query("Test", [], 12345)
    
    @pytest.mark.asyncio
    async def test_registry_integration(self, ai_service):
        """Test integration with tool registry."""
        with patch('services.ai_service.registry') as mock_registry:
            # Setup registry tool
            mock_tool = Mock()
            mock_tool.name = "registry_tool"
            mock_registry.get_tool.return_value = mock_tool
            mock_registry.execute = AsyncMock(return_value="registry result")
            
            # Setup function call
            function_call = Mock()
            function_call.name = "registry_tool"
            function_call.args = {"test": "value"}
            
            # Execute
            result = await ai_service._execute_tool(function_call)
            
            # Verify
            assert result == "registry result"
            mock_registry.execute.assert_called_with("registry_tool", test="value")