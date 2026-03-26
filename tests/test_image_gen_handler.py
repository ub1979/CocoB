# =============================================================================
# test_image_gen_handler.py -- Unit tests for ImageGenHandler
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch

from skillforge.core.image_gen_handler import (
    ImageGenHandler,
    create_image_gen_handler,
    IMAGE_GEN_TOOL_NAMES,
    DEFAULT_SIZE,
    DEFAULT_PROVIDER,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def handler():
    """Create an ImageGenHandler without MCP manager."""
    return ImageGenHandler()


@pytest.fixture
def mock_mcp_manager():
    """Create a mock MCP manager with an image generation tool."""
    mcp = MagicMock()
    mcp.get_all_tools.return_value = {
        "dall-e": [
            {"name": "generate_image", "description": "Generate image from prompt"},
            {"name": "list_models", "description": "List available models"},
        ],
    }
    mcp.call_tool_sync.return_value = {
        "path": "/tmp/generated_image.png",
        "url": "https://example.com/image.png",
    }
    return mcp


@pytest.fixture
def handler_with_mcp(mock_mcp_manager):
    """Create an ImageGenHandler with a mock MCP manager."""
    return ImageGenHandler(mcp_manager=mock_mcp_manager)


# =============================================================================
# Test: has_image_gen_commands
# =============================================================================

class TestHasImageGenCommands:
    """Test detection of image_gen blocks in responses."""

    def test_has_commands_true(self, handler):
        response = "Here is your image:\n```image_gen\nPROMPT: A sunset\n```"
        assert handler.has_image_gen_commands(response) is True

    def test_has_commands_false(self, handler):
        response = "Just a normal response with no code blocks."
        assert handler.has_image_gen_commands(response) is False

    def test_has_commands_wrong_block_type(self, handler):
        response = "```schedule\nACTION: create\n```"
        assert handler.has_image_gen_commands(response) is False

    def test_has_commands_case_insensitive(self, handler):
        response = "```IMAGE_GEN\nPROMPT: A sunset\n```"
        assert handler.has_image_gen_commands(response) is True

    def test_has_commands_with_surrounding_text(self, handler):
        response = (
            "I'll generate that image for you.\n"
            "```image_gen\n"
            "PROMPT: A beautiful mountain landscape\n"
            "```\n"
            "Hope you like it!"
        )
        assert handler.has_image_gen_commands(response) is True

    def test_has_commands_empty_block(self, handler):
        response = "```image_gen\n```"
        assert handler.has_image_gen_commands(response) is True

    def test_has_commands_no_newline_after_tag(self, handler):
        """Block without newline after image_gen should not match."""
        response = "```image_genPROMPT: test```"
        assert handler.has_image_gen_commands(response) is False


# =============================================================================
# Test: parse_block
# =============================================================================

class TestParseBlock:
    """Test parsing of image_gen block content."""

    def test_parse_all_fields(self, handler):
        content = (
            "ACTION: generate\n"
            "PROMPT: A beautiful sunset over mountains\n"
            "STYLE: realistic\n"
            "SIZE: 1024x1024\n"
            "PROVIDER: dall-e\n"
        )
        result = handler.parse_block(content)
        assert result['ACTION'] == 'generate'
        assert result['PROMPT'] == 'A beautiful sunset over mountains'
        assert result['STYLE'] == 'realistic'
        assert result['SIZE'] == '1024x1024'
        assert result['PROVIDER'] == 'dall-e'

    def test_parse_prompt_only(self, handler):
        content = "PROMPT: A sunset\n"
        result = handler.parse_block(content)
        assert result['PROMPT'] == 'A sunset'
        assert 'ACTION' not in result
        assert 'STYLE' not in result

    def test_parse_multiline_prompt(self, handler):
        content = (
            "PROMPT: A beautiful sunset\n"
            "with golden clouds and purple sky\n"
            "SIZE: 512x512\n"
        )
        result = handler.parse_block(content)
        assert 'golden clouds' in result['PROMPT']
        assert result['SIZE'] == '512x512'

    def test_parse_with_negative_prompt(self, handler):
        content = (
            "PROMPT: A happy dog\n"
            "NEGATIVE_PROMPT: blurry, low quality\n"
        )
        result = handler.parse_block(content)
        assert result['PROMPT'] == 'A happy dog'
        assert result['NEGATIVE_PROMPT'] == 'blurry, low quality'

    def test_parse_with_count(self, handler):
        content = (
            "PROMPT: A sunset\n"
            "COUNT: 3\n"
        )
        result = handler.parse_block(content)
        assert result['COUNT'] == '3'

    def test_parse_empty_content(self, handler):
        result = handler.parse_block("")
        assert result == {}

    def test_parse_whitespace_handling(self, handler):
        content = "  PROMPT:   A sunset over mountains  \n  SIZE:  512x512  \n"
        result = handler.parse_block(content)
        assert result['PROMPT'] == 'A sunset over mountains'
        assert result['SIZE'] == '512x512'

    def test_parse_unknown_key_as_continuation(self, handler):
        """Unknown keys should be treated as continuation of previous value."""
        content = (
            "PROMPT: A sunset\n"
            "UNKNOWN_KEY: some value\n"
            "SIZE: 512x512\n"
        )
        result = handler.parse_block(content)
        assert 'UNKNOWN_KEY' not in result
        # UNKNOWN_KEY: some value becomes continuation of PROMPT
        assert 'UNKNOWN_KEY: some value' in result['PROMPT']
        assert result['SIZE'] == '512x512'

    def test_parse_colon_in_value(self, handler):
        """Colons in values should be preserved."""
        content = "PROMPT: Time: 6pm sunset\n"
        result = handler.parse_block(content)
        assert result['PROMPT'] == 'Time: 6pm sunset'


# =============================================================================
# Test: extract_commands
# =============================================================================

class TestExtractCommands:
    """Test extraction of commands from full LLM responses."""

    def test_extract_single_command(self, handler):
        response = (
            "Let me generate that:\n"
            "```image_gen\n"
            "PROMPT: A sunset\n"
            "SIZE: 1024x1024\n"
            "```\n"
        )
        commands = handler.extract_commands(response)
        assert len(commands) == 1
        assert commands[0]['PROMPT'] == 'A sunset'

    def test_extract_multiple_commands(self, handler):
        response = (
            "```image_gen\n"
            "PROMPT: A sunset\n"
            "```\n"
            "And also:\n"
            "```image_gen\n"
            "PROMPT: A sunrise\n"
            "```\n"
        )
        commands = handler.extract_commands(response)
        assert len(commands) == 2
        assert commands[0]['PROMPT'] == 'A sunset'
        assert commands[1]['PROMPT'] == 'A sunrise'

    def test_extract_no_commands(self, handler):
        response = "Just a normal response."
        commands = handler.extract_commands(response)
        assert commands == []

    def test_extract_skips_empty_prompt(self, handler):
        """Commands without PROMPT should be skipped."""
        response = (
            "```image_gen\n"
            "SIZE: 1024x1024\n"
            "STYLE: realistic\n"
            "```\n"
        )
        commands = handler.extract_commands(response)
        assert commands == []

    def test_extract_with_action(self, handler):
        response = (
            "```image_gen\n"
            "ACTION: generate\n"
            "PROMPT: A dog\n"
            "```\n"
        )
        commands = handler.extract_commands(response)
        assert len(commands) == 1
        assert commands[0].get('ACTION') == 'generate'


# =============================================================================
# Test: execute_commands (without MCP)
# =============================================================================

class TestExecuteCommandsNoMCP:
    """Test execute_commands when no MCP manager is available."""

    @pytest.mark.asyncio
    async def test_no_mcp_returns_error(self, handler):
        response = (
            "```image_gen\n"
            "PROMPT: A sunset\n"
            "```\n"
        )
        cleaned, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 1
        assert results[0]['success'] is False
        assert 'No image generation provider' in results[0]['error']
        # Block should be stripped from cleaned response
        assert '```image_gen' not in cleaned

    @pytest.mark.asyncio
    async def test_no_mcp_error_mentions_mcp_setup(self, handler):
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert 'MCP server' in results[0]['error']

    @pytest.mark.asyncio
    async def test_missing_prompt_returns_error(self, handler_with_mcp):
        """Even with MCP, missing PROMPT should error."""
        response = "```image_gen\nSIZE: 1024x1024\n```"
        # This block has no PROMPT, so extract_commands will skip it
        _, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        # No commands extracted (PROMPT is required)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_cleans_blocks_from_response(self, handler):
        response = (
            "Here is your image:\n"
            "```image_gen\n"
            "PROMPT: A sunset\n"
            "```\n"
            "Enjoy!"
        )
        cleaned, _ = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert '```image_gen' not in cleaned
        assert 'Here is your image:' in cleaned
        assert 'Enjoy!' in cleaned

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, handler):
        response = "```image_gen\nACTION: delete\nPROMPT: test\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 1
        assert results[0]['success'] is False
        assert 'Unknown action' in results[0]['error']


# =============================================================================
# Test: execute_commands (with MCP)
# =============================================================================

class TestExecuteCommandsWithMCP:
    """Test execute_commands when MCP manager is available."""

    @pytest.mark.asyncio
    async def test_mcp_generation_success(self, handler_with_mcp, mock_mcp_manager):
        response = "```image_gen\nPROMPT: A sunset\nSIZE: 1024x1024\n```"
        cleaned, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 1
        assert results[0]['success'] is True
        assert results[0]['prompt'] == 'A sunset'
        mock_mcp_manager.call_tool_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_generation_with_style(self, handler_with_mcp, mock_mcp_manager):
        response = "```image_gen\nPROMPT: Mountains\nSTYLE: watercolor\n```"
        _, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert results[0]['success'] is True
        # The MCP call should include style in the prompt
        call_args = mock_mcp_manager.call_tool_sync.call_args
        assert 'watercolor' in call_args[0][2]['prompt']

    @pytest.mark.asyncio
    async def test_mcp_generation_with_provider(self, handler_with_mcp, mock_mcp_manager):
        response = "```image_gen\nPROMPT: A cat\nPROVIDER: dall-e\n```"
        _, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert results[0]['success'] is True
        assert results[0]['provider'] == 'dall-e'

    @pytest.mark.asyncio
    async def test_mcp_tool_call_failure(self, handler_with_mcp, mock_mcp_manager):
        """When MCP tool call raises an exception, should return error."""
        mock_mcp_manager.call_tool_sync.side_effect = Exception("Connection refused")
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        # Should fall through to "no provider" error after MCP failure
        assert len(results) == 1
        assert results[0]['success'] is False

    @pytest.mark.asyncio
    async def test_mcp_no_image_gen_tool(self, handler):
        """MCP connected but no image gen tool found."""
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {
            "filesystem": [
                {"name": "read_file", "description": "Read a file"},
            ],
        }
        handler.mcp_manager = mcp
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert results[0]['success'] is False
        assert 'No image generation provider' in results[0]['error']

    @pytest.mark.asyncio
    async def test_mcp_result_string_url(self, handler):
        """MCP returns a URL string directly."""
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {
            "dall-e": [{"name": "generate_image", "description": "Generate"}],
        }
        mcp.call_tool_sync.return_value = "https://example.com/generated.png"
        handler.mcp_manager = mcp
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert results[0]['success'] is True
        assert results[0]['image_url'] == "https://example.com/generated.png"

    @pytest.mark.asyncio
    async def test_mcp_result_string_path(self, handler):
        """MCP returns a file path string directly."""
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {
            "sd": [{"name": "generate_image", "description": "Generate"}],
        }
        mcp.call_tool_sync.return_value = "/tmp/output.png"
        handler.mcp_manager = mcp
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert results[0]['success'] is True
        assert results[0]['image_path'] == "/tmp/output.png"

    @pytest.mark.asyncio
    async def test_multiple_commands_with_mcp(self, handler_with_mcp, mock_mcp_manager):
        response = (
            "```image_gen\nPROMPT: A sunset\n```\n"
            "```image_gen\nPROMPT: A sunrise\n```"
        )
        _, results = await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 2
        assert all(r['success'] for r in results)
        assert mock_mcp_manager.call_tool_sync.call_count == 2


# =============================================================================
# Test: _try_mcp_generation
# =============================================================================

class TestTryMCPGeneration:
    """Test the MCP tool discovery and calling logic."""

    def test_no_mcp_manager(self, handler):
        result = handler._try_mcp_generation("test prompt", "1024x1024", "auto", "")
        assert result is None

    def test_no_tools_available(self, handler):
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {}
        handler.mcp_manager = mcp
        result = handler._try_mcp_generation("test prompt", "1024x1024", "auto", "")
        assert result is None

    def test_finds_generate_image_tool(self, handler_with_mcp, mock_mcp_manager):
        result = handler_with_mcp._try_mcp_generation(
            "A sunset", "1024x1024", "auto", "",
        )
        assert result is not None
        assert result['success'] is True
        mock_mcp_manager.call_tool_sync.assert_called_once_with(
            "dall-e", "generate_image",
            {"prompt": "A sunset", "size": "1024x1024"},
        )

    def test_passes_negative_prompt(self, handler_with_mcp, mock_mcp_manager):
        handler_with_mcp._try_mcp_generation(
            "A sunset", "1024x1024", "auto", "blurry",
        )
        call_args = mock_mcp_manager.call_tool_sync.call_args
        assert call_args[0][2]['negative_prompt'] == 'blurry'

    def test_provider_specific_search(self, handler):
        """When provider is specified, should prefer that server."""
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {
            "dall-e": [{"name": "generate_image", "description": "Generate"}],
            "sd": [{"name": "generate_image", "description": "Generate"}],
        }
        mcp.call_tool_sync.return_value = {"path": "/tmp/img.png"}
        handler.mcp_manager = mcp
        handler._try_mcp_generation("test", "512x512", "dall-e", "")
        call_args = mcp.call_tool_sync.call_args
        assert call_args[0][0] == "dall-e"

    def test_provider_fallback_when_not_found(self, handler):
        """When specified provider has no image tool, fall back to any server."""
        mcp = MagicMock()
        mcp.get_all_tools.return_value = {
            "unknown-server": [{"name": "read_file", "description": "Read"}],
            "sd": [{"name": "generate_image", "description": "Generate"}],
        }
        mcp.call_tool_sync.return_value = {"path": "/tmp/img.png"}
        handler.mcp_manager = mcp
        result = handler._try_mcp_generation("test", "512x512", "unknown-server", "")
        assert result is not None
        call_args = mcp.call_tool_sync.call_args
        assert call_args[0][0] == "sd"

    def test_get_all_tools_exception(self, handler):
        """Exception in get_all_tools should return None gracefully."""
        mcp = MagicMock()
        mcp.get_all_tools.side_effect = Exception("Connection lost")
        handler.mcp_manager = mcp
        result = handler._try_mcp_generation("test", "512x512", "auto", "")
        assert result is None

    def test_call_tool_sync_exception(self, handler_with_mcp, mock_mcp_manager):
        """Exception in call_tool_sync should return None."""
        mock_mcp_manager.call_tool_sync.side_effect = Exception("Timeout")
        result = handler_with_mcp._try_mcp_generation(
            "test", "512x512", "auto", "",
        )
        assert result is None

    def test_various_tool_names(self, handler):
        """Should recognize various image generation tool names."""
        for tool_name in IMAGE_GEN_TOOL_NAMES:
            mcp = MagicMock()
            mcp.get_all_tools.return_value = {
                "server": [{"name": tool_name, "description": "Generate"}],
            }
            mcp.call_tool_sync.return_value = {"path": "/tmp/img.png"}
            handler.mcp_manager = mcp
            result = handler._try_mcp_generation("test", "512x512", "auto", "")
            assert result is not None, f"Failed to find tool: {tool_name}"


# =============================================================================
# Test: format_response
# =============================================================================

class TestFormatResponse:
    """Test the format_response method."""

    def test_format_with_path(self, handler):
        result = handler.format_response("/tmp/image.png", "A sunset")
        assert "Image Generated" in result
        assert "A sunset" in result
        assert "/tmp/image.png" in result

    def test_format_without_path(self, handler):
        result = handler.format_response("", "A sunset")
        assert "Image Generated" in result
        assert "A sunset" in result

    def test_format_response_includes_prompt(self, handler):
        result = handler.format_response("/path/img.png", "mountain landscape")
        assert "mountain landscape" in result


# =============================================================================
# Test: _format_results
# =============================================================================

class TestFormatResults:
    """Test the _format_results method."""

    def test_format_success_result(self, handler):
        results = [{
            "success": True,
            "action": "generate",
            "prompt": "A sunset",
            "style": "watercolor",
            "size": "1024x1024",
            "image_path": "/tmp/image.png",
            "image_url": "",
        }]
        text = handler._format_results(results)
        assert "Image Generated" in text
        assert "A sunset" in text
        assert "watercolor" in text
        assert "1024x1024" in text
        assert "/tmp/image.png" in text

    def test_format_success_with_url(self, handler):
        results = [{
            "success": True,
            "action": "generate",
            "prompt": "A cat",
            "style": "",
            "size": "",
            "image_path": "",
            "image_url": "https://example.com/cat.png",
        }]
        text = handler._format_results(results)
        assert "https://example.com/cat.png" in text

    def test_format_error_result(self, handler):
        results = [{
            "success": False,
            "error": "No image generation provider available.",
        }]
        text = handler._format_results(results)
        assert "Image Generation Error" in text
        assert "No image generation provider" in text

    def test_format_mixed_results(self, handler):
        results = [
            {"success": True, "prompt": "A sunset", "image_path": "/tmp/a.png",
             "image_url": "", "style": "", "size": ""},
            {"success": False, "error": "Tool failed"},
        ]
        text = handler._format_results(results)
        assert "Image Generated" in text
        assert "Image Generation Error" in text

    def test_format_empty_results(self, handler):
        text = handler._format_results([])
        assert text == ""


# =============================================================================
# Test: set_mcp_manager
# =============================================================================

class TestSetMCPManager:
    """Test the set_mcp_manager method."""

    def test_set_mcp_manager(self, handler):
        assert handler.mcp_manager is None
        mcp = MagicMock()
        handler.set_mcp_manager(mcp)
        assert handler.mcp_manager is mcp

    def test_replace_mcp_manager(self, handler_with_mcp):
        new_mcp = MagicMock()
        handler_with_mcp.set_mcp_manager(new_mcp)
        assert handler_with_mcp.mcp_manager is new_mcp


# =============================================================================
# Test: convenience function
# =============================================================================

class TestConvenienceFunction:
    """Test the create_image_gen_handler factory function."""

    def test_create_without_mcp(self):
        handler = create_image_gen_handler()
        assert isinstance(handler, ImageGenHandler)
        assert handler.mcp_manager is None

    def test_create_with_mcp(self):
        mcp = MagicMock()
        handler = create_image_gen_handler(mcp_manager=mcp)
        assert isinstance(handler, ImageGenHandler)
        assert handler.mcp_manager is mcp


# =============================================================================
# Test: Pattern constants
# =============================================================================

class TestPatternConstants:
    """Test the regex pattern and constants."""

    def test_block_pattern_matches(self):
        pattern = ImageGenHandler.IMAGE_GEN_BLOCK_PATTERN
        text = "```image_gen\nPROMPT: test\n```"
        match = pattern.search(text)
        assert match is not None
        assert 'PROMPT: test' in match.group(1)

    def test_block_pattern_multiline(self):
        pattern = ImageGenHandler.IMAGE_GEN_BLOCK_PATTERN
        text = "```image_gen\nPROMPT: test\nSIZE: 512x512\n```"
        match = pattern.search(text)
        assert match is not None

    def test_default_size(self):
        assert DEFAULT_SIZE == "1024x1024"

    def test_default_provider(self):
        assert DEFAULT_PROVIDER == "auto"

    def test_image_gen_tool_names_contains_common(self):
        assert "generate_image" in IMAGE_GEN_TOOL_NAMES
        assert "create_image" in IMAGE_GEN_TOOL_NAMES
        assert "text_to_image" in IMAGE_GEN_TOOL_NAMES


# =============================================================================
# Test: Edge cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_exception_in_handler_is_caught(self, handler):
        """Handler exceptions should be caught and returned as error results."""
        # Patch _handle_generate to raise
        original = handler._handle_generate

        async def raising_handler(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        handler._handle_generate = raising_handler
        response = "```image_gen\nPROMPT: test\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 1
        assert results[0]['success'] is False
        assert 'Unexpected error' in results[0]['error']

    @pytest.mark.asyncio
    async def test_default_action_is_generate(self, handler):
        """When ACTION is not specified, should default to generate."""
        response = "```image_gen\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        # Should attempt generation (not error about unknown action)
        assert len(results) == 1
        # Without MCP, it returns "no provider" not "unknown action"
        assert 'Unknown action' not in results[0].get('error', '')

    @pytest.mark.asyncio
    async def test_create_action_alias(self, handler):
        """ACTION: create should be treated same as generate."""
        response = "```image_gen\nACTION: create\nPROMPT: A sunset\n```"
        _, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert len(results) == 1
        assert 'Unknown action' not in results[0].get('error', '')

    @pytest.mark.asyncio
    async def test_response_with_no_blocks_passes_through(self, handler):
        """A response with no image_gen blocks should pass through unchanged."""
        response = "This is a normal response."
        cleaned, results = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert cleaned == response
        assert results == []

    @pytest.mark.asyncio
    async def test_style_appended_to_prompt_for_mcp(self, handler_with_mcp, mock_mcp_manager):
        """Style should be appended to prompt when calling MCP."""
        response = "```image_gen\nPROMPT: Mountains\nSTYLE: oil painting\n```"
        await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        call_args = mock_mcp_manager.call_tool_sync.call_args
        prompt_sent = call_args[0][2]['prompt']
        assert 'Mountains' in prompt_sent
        assert 'oil painting' in prompt_sent

    @pytest.mark.asyncio
    async def test_negative_prompt_passed_to_mcp(self, handler_with_mcp, mock_mcp_manager):
        """Negative prompt should be passed as an argument to MCP tool."""
        response = "```image_gen\nPROMPT: A dog\nNEGATIVE_PROMPT: blurry\n```"
        await handler_with_mcp.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        call_args = mock_mcp_manager.call_tool_sync.call_args
        assert call_args[0][2].get('negative_prompt') == 'blurry'

    @pytest.mark.asyncio
    async def test_result_text_appended_to_cleaned(self, handler):
        """Error messages should be appended to the cleaned response."""
        response = "Here:\n```image_gen\nPROMPT: test\n```\nDone."
        cleaned, _ = await handler.execute_commands(
            response, channel="test", user_id="user1", session_key="sess1",
        )
        assert 'Image Generation Error' in cleaned
        assert 'Here:' in cleaned


# =============================================================================
# End of File : test_image_gen_handler.py
# =============================================================================
