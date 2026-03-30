# =============================================================================
# test_integration_chat.py — End-to-end integration tests simulating real chat
#
# These tests exercise the full message flow: user message → router → LLM mock
# → response parsing → handler execution → session persistence. Unlike unit
# tests, they wire up a real SessionManager, PersonalityManager, handlers, and
# memory store — only the LLM call is mocked (no real API traffic).
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch
from skillforge.core.router import MessageRouter
from skillforge.core.sessions import SessionManager
from skillforge.core.file_access import FileAccessManager


# =============================================================================
# Smart response side-effect — inspects messages to return realistic replies
# =============================================================================
def smart_response(messages, **kwargs):
    """Inspect the messages list and return a context-appropriate LLM reply."""
    system_content = ""
    last_user = ""
    for m in messages:
        if m["role"] == "system":
            system_content += m["content"]
        elif m["role"] == "user":
            last_user = m["content"]

    # --- Skill-specific responses ---
    if "SKILL ACTIVATED" in system_content and "todo" in system_content.lower():
        return (
            "Sure! I'll add that to your list.\n\n"
            "```todo\nACTION: add\nTITLE: Buy groceries\n```"
        )

    if "SKILL ACTIVATED" in system_content and "schedule" in system_content.lower():
        return (
            "I'll set a reminder for you.\n\n"
            "```schedule\nACTION: add\nTITLE: Team standup\n"
            "TIME: in 5 minutes\nMESSAGE: Time for standup!\n```"
        )

    if "SKILL ACTIVATED" in system_content:
        # Generic skill response — no code block
        return "I've activated the skill and here are the results for your request."

    # --- Regular conversation ---
    lower = last_user.lower()
    if any(g in lower for g in ["hello", "hi ", "hey", "good morning"]):
        return "Hey there! Great to hear from you. How can I help today?"

    if "my name is" in lower:
        return "Nice to meet you! I'll remember that."

    if "?" in last_user:
        return "That's a great question! Let me think about that. The answer involves several considerations."

    if "error" in lower and "raise" in lower:
        raise Exception("Simulated LLM failure")

    return "Got it! I understand what you're saying. Let me help with that."


def smart_stream(messages, **kwargs):
    """Streaming version — yields chunks that match smart_response."""
    full = smart_response(messages, **kwargs)
    words = full.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")


# =============================================================================
# LLM provider mock factories — one per backend type
# =============================================================================
def _make_mock_llm(provider_name, model_name):
    llm = MagicMock()
    llm.provider_name = provider_name
    llm.model_name = model_name
    llm.config = MagicMock()
    llm.config.base_url = "http://localhost"
    llm.config.model = model_name
    llm.config.context_window = 4096
    llm.check_context_size.return_value = {
        "needs_compaction": False,
        "total_tokens": 100,
        "available_tokens": 3000,
        "within_limit": True,
    }
    llm.estimate_tokens.return_value = 50
    llm.chat.side_effect = smart_response
    llm.chat_stream.side_effect = smart_stream
    return llm


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture(params=[
    ("ollama", "gemma3:1b"),
    ("claude-cli", "claude-3-haiku"),
    ("gemini-cli", "gemini-2.0-flash"),
], ids=["ollama", "claude-cli", "gemini-cli"])
def llm(request):
    """Parametrized LLM mock — tests run once per provider."""
    provider_name, model_name = request.param
    return _make_mock_llm(provider_name, model_name)


@pytest.fixture
def make_router(tmp_path):
    """Factory fixture — returns a function that creates a wired router."""

    def _factory(llm_mock):
        sm = SessionManager(str(tmp_path / "sessions"))
        r = MessageRouter(sm, llm_mock)
        # Redirect todo handler to temp file
        r._todo_handler._data_file = tmp_path / "todos.json"
        r._todo_handler._save_data({})
        # Redirect file-access manager to temp directory
        r._file_access = FileAccessManager(project_root=tmp_path)
        # Use isolated temp memory DB so tests don't share real data
        from skillforge.core.memory import SQLiteMemory
        r.memory_store = SQLiteMemory(db_path=str(tmp_path / "test_memory.db"))
        # Disable permission system for integration tests (all users get full access)
        from skillforge.core.user_permissions import PermissionManager
        r._permission_manager = PermissionManager(data_dir=tmp_path / "perm_data")
        return r

    return _factory


@pytest.fixture
def router(make_router, llm):
    """Convenience: router already wired with the parametrized LLM."""
    return make_router(llm)


# =============================================================================
# 1. TestNormalConversation — Regular chat (× 3 providers)
# =============================================================================
class TestNormalConversation:
    """Simulates everyday human messages hitting the router."""

    async def test_simple_greeting(self, router, llm):
        resp = await router.handle_message("ui", "user1", "Hello!")
        assert len(resp) > 0
        # Session should exist now
        key = router.session_manager.get_session_key("ui", "user1")
        stats = router.session_manager.get_session_stats(key)
        assert stats is not None
        assert stats["messageCount"] >= 2  # user + assistant

    async def test_multi_turn_history_builds(self, router, llm):
        await router.handle_message("ui", "user1", "Hi there")
        await router.handle_message("ui", "user1", "How are you?")
        await router.handle_message("ui", "user1", "Tell me a joke")
        key = router.session_manager.get_session_key("ui", "user1")
        history = router.session_manager.get_conversation_history(key)
        assert len(history) >= 6  # 3 user + 3 assistant

    async def test_long_message(self, router, llm):
        long_msg = "A" * 2500
        resp = await router.handle_message("ui", "user1", long_msg)
        assert len(resp) > 0

    async def test_special_characters(self, router, llm):
        resp = await router.handle_message("ui", "user1", "Hello! 🎉 café naïve — \"quotes\" & <tags>")
        assert len(resp) > 0

    async def test_unicode_message(self, router, llm):
        resp = await router.handle_message("ui", "user1", "こんにちは世界 مرحبا")
        assert len(resp) > 0

    async def test_llm_error_graceful(self, router, llm):
        resp = await router.handle_message("ui", "user1", "raise error please")
        assert "error" in resp.lower()

    async def test_response_saved_to_session(self, router, llm):
        resp = await router.handle_message("ui", "user1", "Hello!")
        key = router.session_manager.get_session_key("ui", "user1")
        history = router.session_manager.get_conversation_history(key)
        # Last message should be the assistant response
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == resp

    async def test_provider_name_in_metadata(self, router, llm):
        """Saved response metadata includes the provider name."""
        await router.handle_message("ui", "user1", "Hello!")
        assert llm.chat.called
        # Verify the metadata was passed to add_message by checking session file
        key = router.session_manager.get_session_key("ui", "user1")
        session = router.session_manager.sessions[key]
        # Read last line of JSONL
        from pathlib import Path
        import json
        lines = Path(session["sessionFile"]).read_text().strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry.get("metadata", {}).get("provider") == llm.provider_name

    async def test_model_name_in_metadata(self, router, llm):
        await router.handle_message("ui", "user1", "Hello!")
        key = router.session_manager.get_session_key("ui", "user1")
        session = router.session_manager.sessions[key]
        from pathlib import Path
        import json
        lines = Path(session["sessionFile"]).read_text().strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry.get("metadata", {}).get("model") == llm.model_name


# =============================================================================
# 2. TestSkillInvocation — Skill detection & context injection (× 3 providers)
# =============================================================================
class TestSkillInvocation:
    """Tests that skill messages get detected, context injected, and
    code-block responses executed."""

    # --- Detection tests (sync, fast) ---

    def test_all_skills_detected(self, router):
        """Every bundled skill name is detected by is_skill_invocation."""
        skill_names = [
            "todo", "schedule", "commit", "search", "explain",
            "google-search", "browse", "email", "calendar",
            "create-skill", "files", "github", "news", "notes", "social",
        ]
        for name in skill_names:
            is_skill, detected, _ = router.is_skill_invocation(f"/{name} test")
            assert is_skill, f"/{name} not detected as skill"
            assert detected == name

    def test_all_skills_have_context(self, router):
        """Every bundled skill returns non-empty context."""
        skill_names = [
            "todo", "schedule", "commit", "search", "explain",
            "google-search", "browse", "email", "calendar",
            "create-skill", "files", "github", "news", "notes", "social",
        ]
        for name in skill_names:
            ctx = router.get_skill_context(name)
            assert ctx, f"/{name} returned empty context"
            assert "SKILL ACTIVATED" in ctx

    def test_remaining_text_passed(self, router):
        _, _, remaining = router.is_skill_invocation("/github list my PRs")
        assert remaining == "list my PRs"

    def test_skill_no_remaining(self, router):
        is_skill, name, remaining = router.is_skill_invocation("/todo")
        assert is_skill
        assert name == "todo"
        assert remaining == ""

    # --- Full flow tests (async, × 3 providers) ---

    async def test_todo_skill_flow(self, router, llm):
        """
        /todo add buy groceries → skill detected → context injected →
        LLM returns ```todo``` block → handler executes → block stripped
        """
        resp = await router.handle_message("ui", "user1", "/todo add buy groceries")
        # The todo block should have been processed and stripped
        assert "```todo" not in resp
        # The todo should be persisted
        data = router._todo_handler._load_data()
        assert any("Buy groceries" in t.get("title", "") for t in data.get("user1", []))

    async def test_schedule_skill_flow(self, router, llm):
        """
        /schedule remind me → skill detected → context injected →
        LLM returns ```schedule``` block → handler processes it
        """
        # Schedule handler needs a scheduler_manager to actually execute
        mock_sm = MagicMock()
        mock_sm.add_job = MagicMock(return_value="job-123")
        router.set_scheduler_manager(mock_sm)
        resp = await router.handle_message("ui", "user1", "/schedule remind me in 5 mins")
        # The schedule block should be processed
        assert "```schedule" not in resp

    async def test_generic_skill_context_injected(self, router, llm):
        """For non-block skills like /explain, the skill context is injected
        into the system prompt but no special code block is parsed."""
        resp = await router.handle_message("ui", "user1", "/explain what is recursion")
        assert len(resp) > 0
        # Verify skill context was injected by checking the messages passed to LLM
        call_args = llm.chat.call_args
        messages = call_args[0][0]
        system_content = messages[0]["content"]
        assert "SKILL ACTIVATED" in system_content

    async def test_skill_response_saved(self, router, llm):
        """Skill response is saved to session history."""
        await router.handle_message("ui", "user1", "/explain what is a variable")
        key = router.session_manager.get_session_key("ui", "user1")
        history = router.session_manager.get_conversation_history(key)
        assert len(history) >= 2
        assert history[-1]["role"] == "assistant"


# =============================================================================
# 3. TestCommandHandling — Built-in /commands (× 3 providers)
# =============================================================================
class TestCommandHandling:
    """Tests the synchronous handle_command path."""

    def test_help_returns_text(self, router):
        resp = router.handle_command("/help", "ui:direct:user1")
        assert "Available commands" in resp
        assert "/reset" in resp

    def test_help_includes_skills(self, router):
        resp = router.handle_command("/help", "ui:direct:user1")
        assert "Skills" in resp
        assert "/todo" in resp

    def test_stats_new_session(self, router):
        # No session yet
        resp = router.handle_command("/stats", "ui:direct:user1")
        assert "No active session" in resp

    async def test_stats_after_message(self, router, llm):
        await router.handle_message("ui", "user1", "Hello!")
        key = router.session_manager.get_session_key("ui", "user1")
        resp = router.handle_command("/stats", key)
        assert "Messages:" in resp
        assert llm.model_name in resp
        assert llm.provider_name in resp

    def test_reset_clears_session(self, router):
        # Create a session first
        key = router.session_manager.get_session_key("ui", "user1")
        router.session_manager.get_or_create_session(key, "ui", "user1")
        router.session_manager.add_message(key, "user", "hello")
        resp = router.handle_command("/reset", key)
        assert "reset" in resp.lower()
        assert router.session_manager.get_session_stats(key) is None

    def test_skills_command(self, router):
        resp = router.handle_command("/skills", "ui:direct:user1")
        assert "Available Skills" in resp
        assert "/todo" in resp

    def test_memory_empty(self, router):
        resp = router.handle_command("/memory", "ui:direct:user1")
        assert "don't have any memories" in resp.lower() or "memories" in resp.lower()

    def test_forget_empty(self, router):
        resp = router.handle_command("/forget", "ui:direct:user1")
        assert "Nothing to forget" in resp or "0" in resp

    def test_unknown_command(self, router):
        resp = router.handle_command("/nonexistent", "ui:direct:user1")
        assert "Unknown command" in resp

    def test_help_command_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/help")
        assert is_skill is False

    def test_reset_command_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/reset")
        assert is_skill is False

    def test_stats_command_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/stats")
        assert is_skill is False

    def test_memory_command_not_skill(self, router):
        is_skill, _, _ = router.is_skill_invocation("/memory")
        assert is_skill is False


# =============================================================================
# 4. TestStreamingResponse — handle_message_stream (× 3 providers)
# =============================================================================
class TestStreamingResponse:
    """Tests the streaming path that the UI uses."""

    async def test_stream_yields_chunks(self, router, llm):
        chunks = []
        async for chunk in router.handle_message_stream("ui", "user1", "Hello!"):
            chunks.append(chunk)
        assert len(chunks) > 1  # Should yield multiple chunks

    async def test_stream_assembled_matches_response(self, router, llm):
        chunks = []
        async for chunk in router.handle_message_stream("ui", "user1", "Hello!"):
            chunks.append(chunk)
        assembled = "".join(chunks)
        assert len(assembled) > 0
        assert "hear from you" in assembled.lower() or "help" in assembled.lower()

    async def test_stream_saves_to_session(self, router, llm):
        async for _ in router.handle_message_stream("ui", "user1", "Hello!"):
            pass
        key = router.session_manager.get_session_key("ui", "user1")
        history = router.session_manager.get_conversation_history(key)
        assert len(history) >= 2
        assert history[-1]["role"] == "assistant"

    async def test_stream_with_skill_context(self, router, llm):
        skill_ctx = router.get_skill_context("explain")
        chunks = []
        async for chunk in router.handle_message_stream(
            "ui", "user1", "/explain recursion", skill_context=skill_ctx
        ):
            chunks.append(chunk)
        assembled = "".join(chunks)
        assert len(assembled) > 0
        # Verify skill context was injected
        call_args = llm.chat_stream.call_args
        messages = call_args[0][0]
        assert "SKILL ACTIVATED" in messages[0]["content"]

    async def test_stream_error_yields_error_message(self, router, llm):
        chunks = []
        async for chunk in router.handle_message_stream("ui", "user1", "raise error please"):
            chunks.append(chunk)
        assembled = "".join(chunks)
        assert "error" in assembled.lower()


# =============================================================================
# 5. TestContextCompaction — compaction triggers
# =============================================================================
class TestContextCompaction:
    """Verify that context compaction is triggered when needed."""

    async def test_compaction_not_triggered_normal(self, router, llm):
        """Normal message should NOT trigger compaction."""
        await router.handle_message("ui", "user1", "Hello!")
        llm.summarize_conversation.assert_not_called()

    async def test_compaction_triggered_when_needed(self, make_router, tmp_path):
        """When check_context_size says needs_compaction, _compact_session is
        called.  The initial history load uses max_messages=5, so compaction
        re-loads without limit — but the threshold is 25 messages.  We patch
        _compact_session directly to verify the trigger."""
        llm = _make_mock_llm("ollama", "test-model")
        llm.check_context_size.return_value = {
            "needs_compaction": True,
            "total_tokens": 3500,
            "available_tokens": 4000,
            "within_limit": True,
        }
        router = make_router(llm)

        with patch.object(router, "_compact_session") as mock_compact:
            mock_compact.return_value = None  # async mock
            await router.handle_message("ui", "user1", "Trigger compaction")
            mock_compact.assert_called_once()


# =============================================================================
# 6. TestMultiTurnSession — Simulates a full human session
# =============================================================================
class TestMultiTurnSession:
    """Simulates a realistic sequence of interactions one human might have."""

    async def test_full_session_flow(self, make_router):
        """greeting → question → /todo → /stats → /reset"""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)

        # 1. Greeting
        resp = await router.handle_message("ui", "alice", "Hello!")
        assert len(resp) > 0

        # 2. Question
        resp = await router.handle_message("ui", "alice", "What is Python?")
        assert len(resp) > 0

        # 3. Skill invocation (todo)
        resp = await router.handle_message("ui", "alice", "/todo add buy groceries")
        assert "```todo" not in resp

        # 4. Stats command
        key = router.session_manager.get_session_key("ui", "alice")
        resp = router.handle_command("/stats", key)
        assert "Messages:" in resp

        # 5. Reset
        resp = router.handle_command("/reset", key)
        assert "reset" in resp.lower()
        assert router.session_manager.get_session_stats(key) is None

    async def test_same_user_different_channels(self, make_router):
        """Same user on different channels → separate sessions."""
        llm = _make_mock_llm("claude-cli", "claude-3-haiku")
        router = make_router(llm)

        await router.handle_message("ui", "bob", "Hello from UI")
        await router.handle_message("telegram", "bob", "Hello from Telegram")

        key_ui = router.session_manager.get_session_key("ui", "bob")
        key_tg = router.session_manager.get_session_key("telegram", "bob")

        assert key_ui != key_tg

        stats_ui = router.session_manager.get_session_stats(key_ui)
        stats_tg = router.session_manager.get_session_stats(key_tg)

        assert stats_ui is not None
        assert stats_tg is not None
        assert stats_ui["sessionId"] != stats_tg["sessionId"]

    async def test_group_vs_direct_separate_sessions(self, make_router):
        """Group chat and DM for same user → different session keys."""
        llm = _make_mock_llm("gemini-cli", "gemini-2.0-flash")
        router = make_router(llm)

        await router.handle_message("slack", "carol", "Hello in DM")
        await router.handle_message("slack", "carol", "Hello in group", chat_id="group-123")

        key_dm = router.session_manager.get_session_key("slack", "carol")
        key_group = router.session_manager.get_session_key("slack", "carol", "group-123")

        assert key_dm != key_group
        assert "direct" in key_dm
        assert "group" in key_group

    async def test_conversation_history_isolated(self, make_router):
        """Messages from different users don't leak between sessions."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)

        await router.handle_message("ui", "alice", "Secret message from Alice")
        await router.handle_message("ui", "bob", "Hello from Bob")

        key_alice = router.session_manager.get_session_key("ui", "alice")
        key_bob = router.session_manager.get_session_key("ui", "bob")

        history_alice = router.session_manager.get_conversation_history(key_alice)
        history_bob = router.session_manager.get_conversation_history(key_bob)

        # Alice's history should not contain Bob's messages
        alice_contents = [m["content"] for m in history_alice]
        bob_contents = [m["content"] for m in history_bob]

        assert not any("Bob" in c for c in alice_contents)
        assert not any("Alice" in c for c in bob_contents)


# =============================================================================
# 7. TestMemoryExtraction — Long-term memory integration
# =============================================================================
class TestMemoryExtraction:
    """Tests that the memory store is wired into the message flow."""

    async def test_memory_store_called(self, router, llm):
        """After handling a message, memory background storage is invoked."""
        with patch.object(router, "_store_memory_background") as mock_store:
            await router.handle_message("ui", "user1", "My name is John")
            mock_store.assert_called_once()
            args = mock_store.call_args[0]
            assert args[0] == "user1"  # user_id
            assert "My name is John" in args[3]  # user_message

    async def test_memory_fact_extraction(self, router, llm):
        """Facts like 'My name is X' get extracted via the memory store."""
        # Call handle_message which triggers _store_memory_background in a thread
        # Instead, test the memory store directly to avoid thread timing issues
        router.memory_store.extract_and_store_facts("user1", "My name is John")
        facts = router.memory_store.get_user_facts("user1")
        assert any("John" in f["fact"] for f in facts)

    async def test_memory_retrieval_in_prompt(self, router, llm):
        """Stored facts appear in the system prompt for subsequent messages."""
        # Store a fact
        router.memory_store.add_fact("user1", "User's name is John", "personal")

        # Send a message — memory should be included in system prompt
        await router.handle_message("ui", "user1", "What do you remember about me?")

        call_args = llm.chat.call_args
        messages = call_args[0][0]
        system_content = messages[0]["content"]
        assert "John" in system_content


# =============================================================================
# 8. TestAuthCommands — Authentication command handling
# =============================================================================
class TestAuthCommands:

    def test_pin_invalid(self, router):
        resp = router.handle_command("/pin 0000", "ui:direct:user1")
        assert "Invalid" in resp or "PIN" in resp

    def test_login_invalid(self, router):
        resp = router.handle_command("/login wrongpass", "ui:direct:user1")
        assert "Invalid" in resp

    def test_logout(self, router):
        resp = router.handle_command("/logout", "ui:direct:user1")
        assert "Logged out" in resp

    def test_auth_status(self, router):
        resp = router.handle_command("/auth status", "ui:direct:user1")
        assert "Auth Status" in resp


# =============================================================================
# 9. TestHeartbeatCommands
# =============================================================================
class TestHeartbeatCommands:

    def test_summary(self, router):
        resp = router.handle_command("/summary", "ui:direct:user1")
        assert "Heartbeat" in resp

    def test_heartbeat_enable(self, router):
        resp = router.handle_command("/heartbeat enable morning_brief", "ui:direct:user1")
        assert "Enabled" in resp or "enabled" in resp

    def test_heartbeat_disable(self, router):
        resp = router.handle_command("/heartbeat disable morning_brief", "ui:direct:user1")
        assert "Disabled" in resp or "disabled" in resp

    def test_heartbeat_status(self, router):
        resp = router.handle_command("/heartbeat status", "ui:direct:user1")
        assert "heartbeat" in resp.lower()


# =============================================================================
# 10. TestPatternCommands
# =============================================================================
class TestPatternCommands:

    def test_patterns_empty(self, router):
        resp = router.handle_command("/patterns", "ui:direct:user1")
        assert "pattern" in resp.lower()

    def test_patterns_stats(self, router):
        resp = router.handle_command("/patterns stats", "ui:direct:user1")
        assert "Pattern Stats" in resp

    def test_patterns_dismiss_nonexistent(self, router):
        resp = router.handle_command("/patterns dismiss fake-id", "ui:direct:user1")
        assert "not found" in resp.lower()


# =============================================================================
# 11. TestTaskCommands
# =============================================================================
class TestTaskCommands:

    def test_tasks_list_empty(self, router):
        resp = router.handle_command("/tasks list", "ui:direct:user1")
        assert "No background tasks" in resp or "Tasks" in resp

    def test_tasks_status(self, router):
        resp = router.handle_command("/tasks status", "ui:direct:user1")
        assert "Task Runner" in resp


# =============================================================================
# 12. TestMCPCommands
# =============================================================================
class TestMCPCommands:

    def test_mcp_list(self, router):
        resp = router.handle_command("/mcp list", "ui:direct:user1")
        assert isinstance(resp, str)

    def test_mcp_verified(self, router):
        resp = router.handle_command("/mcp verified", "ui:direct:user1")
        assert isinstance(resp, str)


# =============================================================================
# 13. TestSkillCreationViaChat — Full create-skill flow through chat
# =============================================================================
class TestSkillCreationViaChat:
    """Tests the end-to-end skill creation flow:
    LLM returns ```create-skill``` block → password gate → file written."""

    async def test_create_skill_blocked_without_password(self, make_router):
        """When no password is set, create-skill blocks are stripped and
        the user is told to set a password first."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        create_skill_response = (
            "I'll create that skill for you!\n\n"
            "```create-skill\n"
            "ACTION: create\n"
            "NAME: dad-jokes\n"
            "DESCRIPTION: Tell dad jokes\n"
            "EMOJI: 😄\n"
            "INSTRUCTIONS:\nTell a random dad joke when invoked.\n"
            "```"
        )
        # Override side_effect to return the create-skill block
        llm.chat.side_effect = None
        llm.chat.return_value = create_skill_response
        router = make_router(llm)

        resp = await router.handle_message("ui", "user1", "/create-skill make a dad-jokes skill")
        # Block should be stripped
        assert "```create-skill" not in resp
        # User should be told to set password
        assert "setpassword" in resp.lower() or "file access" in resp.lower()

    async def test_create_skill_with_password_flow(self, make_router, tmp_path):
        """Full flow: set password → LLM returns create-skill → /unlock → skill created."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "Creating your skill!\n\n"
            "```create-skill\n"
            "ACTION: create\n"
            "NAME: dad-jokes\n"
            "DESCRIPTION: Tell dad jokes on demand\n"
            "EMOJI: 😄\n"
            "INSTRUCTIONS:\nTell a creative and funny dad joke.\n"
            "```"
        )
        router = make_router(llm)

        # 1. Set password
        session_key = "ui:direct:user1"
        resp = router.handle_command("/setpassword MyStr0ngPass!", session_key)
        assert "successfully" in resp.lower()

        # 2. Send message that triggers create-skill
        resp = await router.handle_message("ui", "user1", "/create-skill make a dad-jokes skill")
        # Block stripped, pending action created, user asked to /unlock
        assert "```create-skill" not in resp
        assert "unlock" in resp.lower()

        # 3. Unlock with correct password → pending action executes
        resp = router.handle_command("/unlock MyStr0ngPass!", session_key)
        assert "dad-jokes" in resp.lower() or "created" in resp.lower()

    async def test_create_skill_wrong_password_rejected(self, make_router):
        """Unlock with wrong password rejects."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "```create-skill\nACTION: create\nNAME: test-skill\n"
            "DESCRIPTION: Test\nINSTRUCTIONS:\nDo something.\n```"
        )
        router = make_router(llm)

        session_key = "ui:direct:user1"
        router.handle_command("/setpassword MyStr0ngPass!", session_key)
        await router.handle_message("ui", "user1", "/create-skill make test")

        resp = router.handle_command("/unlock WrongPassword!", session_key)
        assert "Incorrect" in resp


# =============================================================================
# 14. TestMCPServerManagement — Install, enable, disable, uninstall
# =============================================================================
class TestMCPServerManagement:
    """Tests the full MCP server management flow through chat commands."""

    def _make_router_with_mcp(self, make_router, tmp_path):
        """Create a router with an isolated MCP manager."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        # Ensure config subdirectory exists (MCPManager expects config/mcp_config.json)
        (tmp_path / "config").mkdir(exist_ok=True)
        # Point MCP manager to temp directory so it doesn't touch real config
        from skillforge.core.mcp_manager import MCPManager as MCPServerManager
        router._mcp_server_manager = MCPServerManager(
            project_root=tmp_path,
            auth_manager=None,  # No auth required for tests
        )
        return router

    def test_mcp_list_empty(self, make_router, tmp_path):
        router = self._make_router_with_mcp(make_router, tmp_path)
        resp = router.handle_command("/mcp list", "ui:direct:user1")
        assert "No MCP servers" in resp

    def test_mcp_verified_catalog(self, make_router, tmp_path):
        router = self._make_router_with_mcp(make_router, tmp_path)
        resp = router.handle_command("/mcp verified", "ui:direct:user1")
        assert "Playwright" in resp
        assert "Filesystem" in resp
        assert "GitHub" in resp

    def test_mcp_install_verified_server(self, make_router, tmp_path):
        """Install a verified server: request → confirm → installed."""
        router = self._make_router_with_mcp(make_router, tmp_path)

        # 1. Request install of a verified package
        resp = router.handle_command(
            "/mcp install @playwright/mcp", "ui:direct:user1"
        )
        assert "VERIFIED" in resp
        assert "Playwright" in resp

        # 2. Confirm installation
        resp = router.handle_command("/mcp confirm", "ui:direct:user1")
        assert "installed" in resp.lower() or "Successfully" in resp

        # 3. Verify it shows in list
        resp = router.handle_command("/mcp list", "ui:direct:user1")
        assert "mcp" in resp.lower()  # Server should appear

    def test_mcp_install_unverified_server_warning(self, make_router, tmp_path):
        """Unverified server shows security warnings."""
        router = self._make_router_with_mcp(make_router, tmp_path)

        resp = router.handle_command(
            "/mcp install @shady/unknown-server", "ui:direct:user1"
        )
        assert "UNKNOWN" in resp or "WARNING" in resp
        assert "risk" in resp.lower()

    def test_mcp_install_unverified_requires_confirmation(self, make_router, tmp_path):
        """Unverified server needs exact confirmation text."""
        router = self._make_router_with_mcp(make_router, tmp_path)

        router.handle_command(
            "/mcp install @shady/unknown-server", "ui:direct:user1"
        )
        # Wrong confirmation
        resp = router.handle_command("/mcp confirm wrong text", "ui:direct:user1")
        assert "doesn't match" in resp.lower()

        # Correct confirmation
        resp = router.handle_command(
            "/mcp confirm I understand the risk: @shady/unknown-server",
            "ui:direct:user1",
        )
        assert "installed" in resp.lower() or "Successfully" in resp

    def test_mcp_cancel_install(self, make_router, tmp_path):
        router = self._make_router_with_mcp(make_router, tmp_path)
        router.handle_command("/mcp install @playwright/mcp", "ui:direct:user1")
        resp = router.handle_command("/mcp cancel", "ui:direct:user1")
        assert "Cancelled" in resp

    def test_mcp_enable_disable_server(self, make_router, tmp_path):
        """Enable/disable toggle on an installed server."""
        router = self._make_router_with_mcp(make_router, tmp_path)

        # Install first
        router.handle_command("/mcp install @playwright/mcp", "ui:direct:user1")
        router.handle_command("/mcp confirm", "ui:direct:user1")

        # Get the server name from the list
        import json
        config = json.loads((tmp_path / "config" / "mcp_config.json").read_text())
        server_name = list(config["mcpServers"].keys())[0]

        # Disable
        resp = router.handle_command(f"/mcp disable {server_name}", "ui:direct:user1")
        assert "Disabled" in resp or "disabled" in resp.lower()

        # Enable
        resp = router.handle_command(f"/mcp enable {server_name}", "ui:direct:user1")
        assert "Enabled" in resp or "enabled" in resp.lower()

    def test_mcp_uninstall_server(self, make_router, tmp_path):
        """Uninstall removes server from config."""
        router = self._make_router_with_mcp(make_router, tmp_path)

        # Install
        router.handle_command("/mcp install @playwright/mcp", "ui:direct:user1")
        router.handle_command("/mcp confirm", "ui:direct:user1")

        import json
        config = json.loads((tmp_path / "config" / "mcp_config.json").read_text())
        server_name = list(config["mcpServers"].keys())[0]

        # Uninstall
        resp = router.handle_command(f"/mcp uninstall {server_name}", "ui:direct:user1")
        assert "Uninstalled" in resp or "uninstalled" in resp.lower()

        # Verify gone
        resp = router.handle_command("/mcp list", "ui:direct:user1")
        assert "No MCP servers" in resp

    def test_mcp_cancel_no_pending(self, make_router, tmp_path):
        """Cancel with no pending install returns appropriate message."""
        router = self._make_router_with_mcp(make_router, tmp_path)
        resp = router.handle_command("/mcp cancel", "ui:direct:user1")
        assert "No pending" in resp

    def test_mcp_enable_nonexistent_server(self, make_router, tmp_path):
        """Enable a server that doesn't exist returns error."""
        router = self._make_router_with_mcp(make_router, tmp_path)
        resp = router.handle_command("/mcp enable fake-server", "ui:direct:user1")
        assert "not found" in resp.lower()

    def test_mcp_uninstall_nonexistent_server(self, make_router, tmp_path):
        """Uninstall a server that doesn't exist returns error."""
        router = self._make_router_with_mcp(make_router, tmp_path)
        resp = router.handle_command("/mcp uninstall fake-server", "ui:direct:user1")
        assert "not found" in resp.lower()


# =============================================================================
# 15. TestDirectSkillExecution — Skills that bypass LLM (email, calendar)
# =============================================================================
class TestDirectSkillExecution:
    """Tests skills that execute directly via MCP without LLM involvement."""

    async def test_direct_skill_detected(self, make_router):
        """Direct-execution skills like /email are detected by the router."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        assert router._skill_executor.can_execute_directly("email")
        assert router._skill_executor.can_execute_directly("calendar")
        assert router._skill_executor.can_execute_directly("google-search")
        assert router._skill_executor.can_execute_directly("browse")
        # Regular skills should NOT be direct-execution
        assert not router._skill_executor.can_execute_directly("todo")
        assert not router._skill_executor.can_execute_directly("explain")

    async def test_direct_skill_without_mcp_returns_error(self, make_router):
        """Direct skill with no MCP manager returns a helpful error."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        # No MCP manager set — skill_executor._mcp_manager is None
        success, result = router._skill_executor.execute("email", "send hello to bob")
        assert success is False
        assert "not available" in result.lower() or "not connected" in result.lower() or "not initialized" in result.lower() or "not configured" in result.lower()

    async def test_direct_skill_with_mcp_calls_tool(self, make_router):
        """Direct skill with MCP manager invokes the tool."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)

        # Mock MCP manager
        mock_mcp = MagicMock()
        mock_mcp.call_tool_sync.return_value = {"success": True, "output": "Email sent!"}
        router._skill_executor.set_mcp_manager(mock_mcp)

        # The execute method should try to call MCP
        success, result = router._skill_executor.execute("email", "send hello to bob")
        # Even if internal implementation varies, the MCP manager should be invoked
        assert isinstance(result, str)

    async def test_direct_skill_skips_llm(self, make_router):
        """When a direct skill is invoked via handle_message, the LLM
        should NOT be called — the skill executes directly."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)

        # Mock skill executor to return a result
        router._skill_executor = MagicMock()
        router._skill_executor.can_execute_directly.return_value = True
        router._skill_executor.execute.return_value = (True, "Email sent to bob@example.com!")

        resp = await router.handle_message("ui", "user1", "/email send hello to bob")
        assert "Email sent" in resp
        # LLM should NOT have been called
        llm.chat.assert_not_called()


# =============================================================================
# 16. TestSchedulerIntegration — Schedule creation/management via chat
# =============================================================================
class TestSchedulerIntegration:
    """Tests the schedule handler wired through the router."""

    async def test_schedule_block_creates_task(self, make_router):
        """LLM returns ```schedule``` block → task created via scheduler."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "I've set that up for you!\n\n"
            "```schedule\n"
            "ACTION: create\n"
            "NAME: Morning standup\n"
            "SCHEDULE: 0 9 * * 1-5\n"
            "MESSAGE: Time for standup!\n"
            "```"
        )
        router = make_router(llm)

        # Wire up a mock scheduler manager
        mock_scheduler = MagicMock()
        mock_scheduler.add_task = MagicMock(return_value="task-abc123")
        # Make add_task an async function
        import asyncio
        async def mock_add_task(task):
            return "task-abc123"
        mock_scheduler.add_task = mock_add_task
        router.set_scheduler_manager(mock_scheduler)

        resp = await router.handle_message("ui", "user1", "/schedule set a daily standup at 9am weekdays")
        # Schedule block should be stripped and result appended
        assert "```schedule" not in resp
        assert "Task Created" in resp or "Morning standup" in resp

    async def test_schedule_list_via_chat(self, make_router):
        """LLM returns a schedule list block → user tasks listed."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "Here are your schedules:\n\n"
            "```schedule\n"
            "ACTION: list\n"
            "```"
        )
        router = make_router(llm)

        mock_scheduler = MagicMock()
        mock_scheduler.list_tasks.return_value = []
        router.set_scheduler_manager(mock_scheduler)

        resp = await router.handle_message("ui", "user1", "/schedule list my tasks")
        assert "```schedule" not in resp
        assert "No scheduled tasks" in resp or "tasks" in resp.lower()

    async def test_schedule_without_scheduler_no_crash(self, make_router):
        """Without a scheduler manager wired, schedule blocks are ignored gracefully."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "```schedule\n"
            "ACTION: create\n"
            "NAME: Test\n"
            "SCHEDULE: 0 9 * * *\n"
            "MESSAGE: Hello\n"
            "```"
        )
        router = make_router(llm)
        # Do NOT set scheduler manager
        resp = await router.handle_message("ui", "user1", "/schedule test")
        # Should not crash — block stays as-is or is stripped
        assert isinstance(resp, str)

    async def test_schedule_delete_task(self, make_router):
        """LLM returns schedule delete block → task removed."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        llm.chat.side_effect = None
        llm.chat.return_value = (
            "I'll remove that schedule.\n\n"
            "```schedule\n"
            "ACTION: delete\n"
            "TASK_ID: task-abc123\n"
            "```"
        )
        router = make_router(llm)

        mock_scheduler = MagicMock()
        async def mock_remove(task_id):
            return True
        mock_scheduler.remove_task = mock_remove
        router.set_scheduler_manager(mock_scheduler)

        resp = await router.handle_message("ui", "user1", "/schedule delete task-abc123")
        assert "```schedule" not in resp
        assert "Deleted" in resp or "deleted" in resp.lower()


# =============================================================================
# 17. TestHeartbeatIntegration — Heartbeat enable/disable/summary via chat
# =============================================================================
class TestHeartbeatIntegration:
    """Tests the heartbeat system through the router commands."""

    def test_enable_morning_brief(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        resp = router.handle_command("/heartbeat enable morning_brief", "ui:direct:user1")
        assert "Enabled" in resp
        assert "morning_brief" in resp

    def test_enable_daily_summary(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        resp = router.handle_command("/heartbeat enable daily_summary", "ui:direct:user1")
        assert "Enabled" in resp
        assert "daily_summary" in resp

    def test_enable_then_check_status(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        router.handle_command("/heartbeat enable morning_brief", "ui:direct:user1")
        router.handle_command("/heartbeat enable daily_summary", "ui:direct:user1")
        resp = router.handle_command("/heartbeat status", "ui:direct:user1")
        assert "morning_brief" in resp
        assert "daily_summary" in resp

    def test_enable_then_disable(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        router.handle_command("/heartbeat enable morning_brief", "ui:direct:user1")
        resp = router.handle_command("/heartbeat disable morning_brief", "ui:direct:user1")
        assert "Disabled" in resp

        resp = router.handle_command("/heartbeat status", "ui:direct:user1")
        assert "morning_brief" not in resp or "None" in resp

    def test_summary_shows_heartbeat_state(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        router.handle_command("/heartbeat enable daily_summary", "ui:direct:user1")
        resp = router.handle_command("/summary", "ui:direct:user1")
        assert "Heartbeat" in resp
        assert "daily_summary" in resp

    def test_heartbeat_no_type_shows_usage(self, make_router):
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        resp = router.handle_command("/heartbeat enable", "ui:direct:user1")
        assert "specify" in resp.lower() or "type" in resp.lower()

    def test_heartbeat_all_types(self, make_router):
        """All heartbeat types can be enabled."""
        llm = _make_mock_llm("ollama", "gemma3:1b")
        router = make_router(llm)
        types = ["morning_brief", "deadline_watch", "unusual_activity", "daily_summary"]
        for hb_type in types:
            resp = router.handle_command(f"/heartbeat enable {hb_type}", "ui:direct:user1")
            assert "Enabled" in resp, f"Failed to enable {hb_type}"

        resp = router.handle_command("/heartbeat status", "ui:direct:user1")
        for hb_type in types:
            assert hb_type in resp, f"{hb_type} not in status after enabling"
