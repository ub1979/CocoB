# =============================================================================
# test_claude_cli.py — Tests for Claude CLI provider optimizations:
# _format_messages with/without session, session persistence save/load.
# =============================================================================

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """Minimal LLMConfig mock."""
    config = MagicMock()
    config.timeout = 120
    config.model = "claude-sonnet-4-20250514"
    config.extra = {}
    return config


@pytest.fixture
def provider(mock_config, tmp_path):
    """Create a ClaudeCLIProvider with session file pointed at tmp_path."""
    import skillforge.core.llm.claude_cli_provider as mod
    original = mod._SESSION_FILE
    mod._SESSION_FILE = tmp_path / "claude_session.json"
    try:
        with patch("shutil.which", return_value="/usr/bin/claude"):
            from skillforge.core.llm.claude_cli_provider import ClaudeCLIProvider
            p = ClaudeCLIProvider(mock_config)
            yield p
    finally:
        mod._SESSION_FILE = original


# ---------------------------------------------------------------------------
# _format_messages tests
# ---------------------------------------------------------------------------

class TestFormatMessages:
    """_format_messages should send full history on first message, only latest user on resume."""

    def test_no_session_sends_full_history(self, provider):
        """Without a session, all messages are formatted."""
        provider._session_id = None
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = provider._format_messages(messages)
        assert "[System Instructions]" in result
        assert "You are helpful." in result
        assert "[User]\nHello" in result
        assert "[Previous Assistant Response]" in result
        assert "How are you?" in result

    def test_with_session_sends_only_latest_user(self, provider):
        """With an active session, only the last user message is sent."""
        provider._session_id = "abc-123"
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        result = provider._format_messages(messages)
        assert result == "How are you?"
        assert "[System Instructions]" not in result
        assert "[Previous Assistant Response]" not in result

    def test_with_session_no_user_messages(self, provider):
        """Edge case: session active but no user messages returns empty string."""
        provider._session_id = "abc-123"
        messages = [
            {"role": "system", "content": "You are helpful."},
        ]
        result = provider._format_messages(messages)
        assert result == ""

    def test_no_session_system_goes_first(self, provider):
        """System message should appear at the beginning regardless of order."""
        provider._session_id = None
        messages = [
            {"role": "user", "content": "First"},
            {"role": "system", "content": "System prompt"},
        ]
        result = provider._format_messages(messages)
        assert result.startswith("[System Instructions]")


# ---------------------------------------------------------------------------
# Session persistence tests
# ---------------------------------------------------------------------------

class TestSessionPersistence:
    """Session ID should survive save/load round-trip."""

    def test_save_and_load_session(self, provider, tmp_path):
        """Save session ID then load it back."""
        import skillforge.core.llm.claude_cli_provider as mod
        provider._session_id = "test-session-abc"
        provider._save_session_id()

        assert mod._SESSION_FILE.exists()
        data = json.loads(mod._SESSION_FILE.read_text())
        assert data["session_id"] == "test-session-abc"

        # Load it back
        loaded = provider._load_session_id()
        assert loaded == "test-session-abc"

    def test_load_returns_none_when_no_file(self, provider, tmp_path):
        """Loading when no file exists returns None."""
        import skillforge.core.llm.claude_cli_provider as mod
        if mod._SESSION_FILE.exists():
            mod._SESSION_FILE.unlink()
        result = provider._load_session_id()
        assert result is None

    def test_load_handles_corrupt_file(self, provider, tmp_path):
        """Corrupt JSON should return None, not crash."""
        import skillforge.core.llm.claude_cli_provider as mod
        mod._SESSION_FILE.write_text("not valid json{{{")
        result = provider._load_session_id()
        assert result is None

    def test_reset_session_clears_file(self, provider, tmp_path):
        """reset_session should remove the persisted file."""
        import skillforge.core.llm.claude_cli_provider as mod
        provider._session_id = "test-session"
        provider._save_session_id()
        assert mod._SESSION_FILE.exists()

        provider.reset_session()
        assert provider._session_id is None
        assert not mod._SESSION_FILE.exists()

    def test_init_loads_persisted_session(self, mock_config, tmp_path):
        """New provider instance should load session from disk."""
        import skillforge.core.llm.claude_cli_provider as mod
        original = mod._SESSION_FILE
        mod._SESSION_FILE = tmp_path / "claude_session.json"
        try:
            mod._SESSION_FILE.write_text(json.dumps({"session_id": "persisted-123"}))
            with patch("shutil.which", return_value="/usr/bin/claude"):
                from skillforge.core.llm.claude_cli_provider import ClaudeCLIProvider
                p = ClaudeCLIProvider(mock_config)
                assert p._session_id == "persisted-123"
        finally:
            mod._SESSION_FILE = original


# ---------------------------------------------------------------------------
# Build command tests
# ---------------------------------------------------------------------------

class TestBuildCommand:
    """_build_command should include --resume when session exists."""

    def test_no_session_no_resume(self, provider):
        provider._session_id = None
        cmd = provider._build_command("hello")
        assert "--resume" not in cmd

    def test_with_session_includes_resume(self, provider):
        provider._session_id = "sess-456"
        cmd = provider._build_command("hello")
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "sess-456"
