# =============================================================================
# test_think_levels.py — Unit tests for /think level control
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch
from coco_b.core.router import MessageRouter


@pytest.fixture
def router():
    """Create a router with mocked dependencies."""
    mock_session_mgr = MagicMock()
    mock_session_mgr.get_or_create_session.return_value = {"sessionId": "test"}
    mock_session_mgr.get_session_key.return_value = "test:direct:user1"
    mock_session_mgr.get_conversation_history.return_value = []

    mock_llm = MagicMock()
    mock_llm.provider_name = "test"
    mock_llm.model_name = "test-model"
    mock_llm.chat.return_value = "Hello!"
    mock_llm.check_context_size.return_value = {"needs_compaction": False}

    router = MessageRouter(
        session_manager=mock_session_mgr,
        llm_provider=mock_llm,
    )
    return router


# =============================================================================
# TestThinkLevelConstants
# =============================================================================

class TestThinkLevelConstants:
    """Test THINK_LEVELS constant is properly defined."""

    def test_all_levels_exist(self, router):
        expected = ["off", "minimal", "low", "medium", "high", "xhigh"]
        for level in expected:
            assert level in router.THINK_LEVELS

    def test_each_level_has_temperature(self, router):
        for level, info in router.THINK_LEVELS.items():
            assert "temperature" in info
            assert isinstance(info["temperature"], (int, float))

    def test_each_level_has_description(self, router):
        for level, info in router.THINK_LEVELS.items():
            assert "description" in info
            assert len(info["description"]) > 0

    def test_temperature_ordering(self, router):
        levels = ["off", "minimal", "low", "medium", "high", "xhigh"]
        temps = [router.THINK_LEVELS[l]["temperature"] for l in levels]
        assert temps == sorted(temps), "Temperatures should be in ascending order"

    def test_off_is_zero(self, router):
        assert router.THINK_LEVELS["off"]["temperature"] == 0.0

    def test_medium_is_default(self, router):
        assert router.THINK_LEVELS["medium"]["temperature"] == 0.7


# =============================================================================
# TestThinkCommand
# =============================================================================

class TestThinkCommand:
    """Test /think command handling."""

    def test_think_no_args_shows_current(self, router):
        result = router.handle_command("/think", "test:direct:user1")
        assert "medium" in result  # Default level
        assert "Available levels" in result

    def test_think_set_valid_level(self, router):
        result = router.handle_command("/think high", "test:direct:user1")
        assert "high" in result
        assert "test:direct:user1" in router._think_levels
        assert router._think_levels["test:direct:user1"] == "high"

    def test_think_set_off(self, router):
        result = router.handle_command("/think off", "test:direct:user1")
        assert "off" in result
        assert router._think_levels["test:direct:user1"] == "off"

    def test_think_set_xhigh(self, router):
        result = router.handle_command("/think xhigh", "test:direct:user1")
        assert "xhigh" in result
        assert router._think_levels["test:direct:user1"] == "xhigh"

    def test_think_invalid_level(self, router):
        result = router.handle_command("/think turbo", "test:direct:user1")
        assert "Unknown" in result
        assert "turbo" in result

    def test_think_case_insensitive(self, router):
        result = router.handle_command("/think HIGH", "test:direct:user1")
        assert "high" in result
        assert router._think_levels["test:direct:user1"] == "high"

    def test_think_per_session(self, router):
        router.handle_command("/think high", "session1")
        router.handle_command("/think low", "session2")
        assert router._think_levels["session1"] == "high"
        assert router._think_levels["session2"] == "low"

    def test_think_shows_temperature(self, router):
        result = router.handle_command("/think high", "test:direct:user1")
        assert "0.9" in result

    def test_think_shows_current_after_set(self, router):
        router.handle_command("/think low", "test:direct:user1")
        result = router.handle_command("/think", "test:direct:user1")
        assert "low" in result
        assert "(current)" in result


# =============================================================================
# TestThinkInSkillList
# =============================================================================

class TestThinkInSkillList:
    """Test /think is recognized as built-in command."""

    def test_think_not_skill_invocation(self, router):
        is_skill, name, msg = router.is_skill_invocation("/think high")
        assert is_skill is False

    def test_think_in_help(self, router):
        result = router.handle_command("/help", "test:direct:user1")
        assert "/think" in result


# =============================================================================
# TestThinkTemperatureInjection
# =============================================================================

class TestThinkTemperatureInjection:
    """Test that think level affects LLM calls."""

    @pytest.mark.asyncio
    async def test_default_no_temperature_override(self, router):
        """Without /think set, no temperature kwarg should be passed."""
        await router.handle_message(
            channel="test", user_id="user1", user_message="hello"
        )
        call_args = router.llm.chat.call_args
        # Should not have temperature kwarg (uses provider default)
        assert "temperature" not in (call_args.kwargs if call_args.kwargs else {})

    @pytest.mark.asyncio
    async def test_think_level_passes_temperature(self, router):
        """After /think high, temperature should be passed to llm.chat()."""
        session_key = "test:direct:user1"
        router._think_levels[session_key] = "high"

        await router.handle_message(
            channel="test", user_id="user1", user_message="hello"
        )
        call_args = router.llm.chat.call_args
        assert call_args.kwargs.get("temperature") == 0.9

    @pytest.mark.asyncio
    async def test_think_off_passes_zero(self, router):
        """After /think off, temperature 0.0 should be passed."""
        session_key = "test:direct:user1"
        router._think_levels[session_key] = "off"

        await router.handle_message(
            channel="test", user_id="user1", user_message="hello"
        )
        call_args = router.llm.chat.call_args
        assert call_args.kwargs.get("temperature") == 0.0


# =============================================================================
# TestThinkingModelCodeBlockExtraction
# =============================================================================

class TestThinkingModelCodeBlockExtraction:
    """Test that code blocks are extracted from reasoning field for thinking models."""

    def test_extract_code_block_from_reasoning(self):
        from coco_b.core.llm.openai_compat import _CODE_BLOCK_RE
        reasoning = (
            "Let me think about how to create this todo list...\n"
            "I should emit a todo code block.\n"
            "```todo\nACTION: list\n```\n"
            "That should work."
        )
        blocks = _CODE_BLOCK_RE.findall(reasoning)
        assert len(blocks) == 1
        assert "ACTION: list" in blocks[0]

    def test_extract_multiple_code_blocks(self):
        from coco_b.core.llm.openai_compat import _CODE_BLOCK_RE
        reasoning = (
            "First block:\n```schedule\nACTION: create\nNAME: test\n```\n"
            "Second block:\n```todo\nACTION: add\nTITLE: Buy milk\n```\n"
        )
        blocks = _CODE_BLOCK_RE.findall(reasoning)
        assert len(blocks) == 2

    def test_no_code_blocks_returns_empty(self):
        from coco_b.core.llm.openai_compat import _CODE_BLOCK_RE
        reasoning = "I'm thinking about how to respond to this request..."
        blocks = _CODE_BLOCK_RE.findall(reasoning)
        assert len(blocks) == 0

    def test_chat_extracts_code_blocks_from_reasoning(self):
        """chat() should extract code blocks from reasoning when content is empty."""
        from coco_b.core.llm.openai_compat import OpenAICompatibleProvider
        from unittest.mock import MagicMock

        config = MagicMock()
        config.provider = "ollama"
        config.base_url = "http://localhost:11434/v1"
        config.api_key = None
        config.model = "gemini-flash"
        config.max_response_tokens = 4096
        config.temperature = 0.7
        config.timeout = 30
        config.extra = {}

        provider = OpenAICompatibleProvider(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning": (
                        "Let me create a todo list...\n"
                        "```todo\nACTION: list\n```\n"
                        "Done thinking."
                    ),
                }
            }]
        }

        with patch("requests.post", return_value=mock_response):
            result = provider.chat([{"role": "user", "content": "/todo list"}])
            assert "```todo" in result
            assert "ACTION: list" in result
            # Should NOT contain the reasoning text
            assert "Let me create" not in result
            assert "Done thinking" not in result

    def test_chat_falls_back_to_full_reasoning_when_no_blocks(self):
        """chat() returns full reasoning when no code blocks found."""
        from coco_b.core.llm.openai_compat import OpenAICompatibleProvider
        from unittest.mock import MagicMock

        config = MagicMock()
        config.provider = "ollama"
        config.base_url = "http://localhost:11434/v1"
        config.api_key = None
        config.model = "gemini-flash"
        config.max_response_tokens = 4096
        config.temperature = 0.7
        config.timeout = 30
        config.extra = {}

        provider = OpenAICompatibleProvider(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning": "Just thinking out loud without code blocks",
                }
            }]
        }

        with patch("requests.post", return_value=mock_response):
            result = provider.chat([{"role": "user", "content": "hello"}])
            assert result == "Just thinking out loud without code blocks"

    def test_chat_prefers_content_over_reasoning(self):
        """chat() should use content when it's not empty, ignoring reasoning."""
        from coco_b.core.llm.openai_compat import OpenAICompatibleProvider
        from unittest.mock import MagicMock

        config = MagicMock()
        config.provider = "ollama"
        config.base_url = "http://localhost:11434/v1"
        config.api_key = None
        config.model = "gemini-flash"
        config.max_response_tokens = 4096
        config.temperature = 0.7
        config.timeout = 30
        config.extra = {}

        provider = OpenAICompatibleProvider(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Here is your answer!",
                    "reasoning": "Some internal thinking...",
                }
            }]
        }

        with patch("requests.post", return_value=mock_response):
            result = provider.chat([{"role": "user", "content": "hello"}])
            assert result == "Here is your answer!"
