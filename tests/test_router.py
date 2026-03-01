# =============================================================================
# test_router.py — Integration tests for MessageRouter
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from coco_b.core.router import MessageRouter
from coco_b.core.sessions import SessionManager


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = MagicMock()
    llm.model_name = "test-model"
    llm.provider_name = "test-provider"
    llm.config = MagicMock()
    llm.config.base_url = "http://localhost"
    llm.config.model = "test-model"
    llm.check_context_size.return_value = {"needs_compaction": False, "total_tokens": 100}
    llm.chat.return_value = "Hello! I'm coco B."
    llm.estimate_tokens.return_value = 50
    return llm


@pytest.fixture
def router(tmp_path, mock_llm):
    """Create a MessageRouter with temp session storage."""
    sm = SessionManager(str(tmp_path / "sessions"))
    r = MessageRouter(sm, mock_llm)
    # Point todo handler to temp file
    r._todo_handler._data_file = tmp_path / "todos.json"
    r._todo_handler._save_data({})
    # Point file access manager to temp directory
    from coco_b.core.file_access import FileAccessManager
    r._file_access = FileAccessManager(project_root=tmp_path)
    # Disable permission system for unit tests (all users get full access)
    from coco_b.core.user_permissions import PermissionManager
    r._permission_manager = PermissionManager(data_dir=tmp_path / "perm_data")
    return r


class TestRouterInit:
    """Test router initializes all handlers."""

    def test_has_schedule_handler(self, router):
        assert router._schedule_handler is not None

    def test_has_todo_handler(self, router):
        assert router._todo_handler is not None

    def test_has_skill_creator_handler(self, router):
        assert router._skill_creator_handler is not None


class TestSetSchedulerManager:
    """Test scheduler manager wiring."""

    def test_sets_on_schedule_handler(self, router):
        mock_sm = MagicMock()
        router.set_scheduler_manager(mock_sm)
        assert router._schedule_handler.scheduler_manager is mock_sm

    def test_sets_on_todo_handler(self, router):
        mock_sm = MagicMock()
        router.set_scheduler_manager(mock_sm)
        assert router._todo_handler.scheduler_manager is mock_sm

    def test_stores_on_router(self, router):
        mock_sm = MagicMock()
        router.set_scheduler_manager(mock_sm)
        assert router._scheduler_manager is mock_sm

    def test_scheduler_manager_initially_none(self, router):
        assert router._scheduler_manager is None

    @pytest.mark.asyncio
    async def test_system_prompt_includes_schedule_hint(self, router, mock_llm):
        """When scheduler_manager is set, system prompt should mention scheduling."""
        mock_sm = MagicMock()
        router.set_scheduler_manager(mock_sm)

        # Call handle_message and capture the system prompt passed to llm.chat
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="remind me at 5pm to drink water",
        )
        # llm.chat should have been called with messages containing schedule hint
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0]["content"]
        assert "```schedule```" in system_msg or "schedule" in system_msg.lower()
        assert "reminder" in system_msg.lower() or "remind" in system_msg.lower()

    @pytest.mark.asyncio
    async def test_system_prompt_no_schedule_hint_without_manager(self, router, mock_llm):
        """Without scheduler_manager, system prompt should NOT mention scheduling."""
        await router.handle_message(
            channel="test", user_id="u1",
            user_message="hello",
        )
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        system_msg = messages[0]["content"]
        assert "```schedule```" not in system_msg


class TestSkillInvocation:
    """Test skill detection in messages."""

    def test_detects_skill(self, router):
        is_skill, name, remaining = router.is_skill_invocation("/todo add buy milk")
        assert is_skill is True
        assert name == "todo"
        assert remaining == "add buy milk"

    def test_detects_github_skill(self, router):
        is_skill, name, _ = router.is_skill_invocation("/github list issues")
        assert is_skill is True
        assert name == "github"

    def test_detects_notes_skill(self, router):
        is_skill, name, _ = router.is_skill_invocation("/notes create Meeting notes")
        assert is_skill is True
        assert name == "notes"

    def test_detects_files_skill(self, router):
        is_skill, name, _ = router.is_skill_invocation("/files list ~/Documents")
        assert is_skill is True
        assert name == "files"

    def test_detects_news_skill(self, router):
        is_skill, name, _ = router.is_skill_invocation("/news headlines")
        assert is_skill is True
        assert name == "news"

    def test_detects_social_skill(self, router):
        is_skill, name, _ = router.is_skill_invocation("/social post hello world")
        assert is_skill is True
        assert name == "social"

    def test_builtin_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/help")
        assert is_skill is False

    def test_regular_message_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("hello there")
        assert is_skill is False


class TestCommands:
    """Test built-in command handling."""

    def test_help_lists_skills(self, router):
        response = router.handle_command("/help", "test:direct:u1")
        assert "todo" in response.lower()
        assert "github" in response.lower()

    def test_skills_command(self, router):
        response = router.handle_command("/skills", "test:direct:u1")
        assert "todo" in response.lower()
        assert "github" in response.lower()
        assert "notes" in response.lower()
        assert "files" in response.lower()
        assert "news" in response.lower()
        assert "social" in response.lower()

    def test_unknown_command(self, router):
        response = router.handle_command("/bogus", "test:direct:u1")
        assert "Unknown" in response


class TestSetPassword:
    """Test /setpassword command."""

    def test_setpassword_success(self, router):
        response = router.handle_command("/setpassword MyStr0ngPass!", "test:direct:u1")
        assert "successfully" in response.lower()
        assert router._file_access.is_password_set() is True

    def test_setpassword_too_short(self, router):
        response = router.handle_command("/setpassword abc", "test:direct:u1")
        assert "minimum 8" in response.lower()

    def test_setpassword_no_arg(self, router):
        response = router.handle_command("/setpassword", "test:direct:u1")
        assert "Usage" in response

    def test_setpassword_rejects_if_already_set(self, router):
        router.handle_command("/setpassword FirstPass1!", "test:direct:u1")
        response = router.handle_command("/setpassword SecondPass2!", "test:direct:u1")
        assert "already configured" in response.lower()


class TestUnlock:
    """Test /unlock command."""

    def test_unlock_no_password(self, router):
        response = router.handle_command("/unlock test1234", "test:direct:u1")
        assert "Incorrect" in response

    def test_unlock_wrong_password(self, router):
        router.handle_command("/setpassword CorrectPass1!", "test:direct:u1")
        response = router.handle_command("/unlock WrongPass!!", "test:direct:u1")
        assert "Incorrect" in response

    def test_unlock_no_pending(self, router):
        router.handle_command("/setpassword CorrectPass1!", "test:direct:u1")
        response = router.handle_command("/unlock CorrectPass1!", "test:direct:u1")
        assert "No pending action" in response

    def test_unlock_no_arg(self, router):
        response = router.handle_command("/unlock", "test:direct:u1")
        assert "Usage" in response

    def test_setpassword_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/setpassword test1234")
        assert is_skill is False

    def test_unlock_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/unlock test1234")
        assert is_skill is False


class TestHandleMessageTodoIntegration:
    """Test that todo blocks in LLM responses get processed."""

    @pytest.mark.asyncio
    async def test_todo_block_processed(self, router, mock_llm):
        # Simulate LLM returning a todo block
        mock_llm.chat.return_value = "I'll add that!\n\n```todo\nACTION: add\nTITLE: Buy milk\n```"

        response = await router.handle_message(
            channel="test", user_id="u1",
            user_message="add buy milk to my todos",
        )
        # The todo block should be stripped and replaced with results
        assert "```todo" not in response
        assert "Buy milk" in response

    @pytest.mark.asyncio
    async def test_todo_persisted(self, router, mock_llm):
        mock_llm.chat.return_value = "```todo\nACTION: add\nTITLE: Persisted task\n```"
        await router.handle_message(channel="test", user_id="u1", user_message="add task")
        data = router._todo_handler._load_data()
        assert "u1" in data
        assert data["u1"][0]["title"] == "Persisted task"
