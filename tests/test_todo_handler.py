# =============================================================================
# test_todo_handler.py — Unit tests for TodoCommandHandler
# =============================================================================

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from skillforge.core.todo_handler import TodoCommandHandler


@pytest.fixture
def handler(tmp_path):
    """Create a TodoCommandHandler with a temp data directory."""
    h = TodoCommandHandler()
    h._data_file = tmp_path / "todos.json"
    h._save_data({})
    return h


class TestDetection:
    """Test todo block detection in LLM responses."""

    def test_detects_todo_block(self, handler):
        response = "Sure!\n\n```todo\nACTION: add\nTITLE: Buy milk\n```"
        assert handler.has_todo_commands(response) is True

    def test_no_false_positive(self, handler):
        response = "Here's a regular message with no code blocks."
        assert handler.has_todo_commands(response) is False

    def test_case_insensitive(self, handler):
        response = "```Todo\nACTION: list\n```"
        assert handler.has_todo_commands(response) is True

    def test_ignores_other_blocks(self, handler):
        response = "```python\nprint('hello')\n```"
        assert handler.has_todo_commands(response) is False


class TestParsing:
    """Test parsing of todo block content."""

    def test_parse_basic_block(self, handler):
        block = "ACTION: add\nTITLE: Buy milk\nPRIORITY: high"
        result = handler.parse_todo_block(block)
        assert result["ACTION"] == "add"
        assert result["TITLE"] == "Buy milk"
        assert result["PRIORITY"] == "high"

    def test_parse_with_tags(self, handler):
        block = "ACTION: add\nTITLE: Fix bug\nTAGS: work, urgent"
        result = handler.parse_todo_block(block)
        assert result["TAGS"] == "work, urgent"

    def test_extract_multiple_commands(self, handler):
        response = (
            "```todo\nACTION: add\nTITLE: Task 1\n```\n"
            "```todo\nACTION: add\nTITLE: Task 2\n```"
        )
        commands = handler.extract_commands(response)
        assert len(commands) == 2
        assert commands[0]["TITLE"] == "Task 1"
        assert commands[1]["TITLE"] == "Task 2"

    def test_extract_ignores_empty_action(self, handler):
        response = "```todo\nTITLE: No action\n```"
        commands = handler.extract_commands(response)
        assert len(commands) == 0


class TestAdd:
    """Test adding todos."""

    @pytest.mark.asyncio
    async def test_add_basic(self, handler):
        response = "```todo\nACTION: add\nTITLE: Buy groceries\n```"
        cleaned, results = await handler.execute_commands(response, user_id="u1")
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["action"] == "add"
        assert results[0]["title"] == "Buy groceries"
        assert results[0]["todo_id"]

    @pytest.mark.asyncio
    async def test_add_with_priority_and_due(self, handler):
        response = "```todo\nACTION: add\nTITLE: Deploy\nPRIORITY: high\nDUE: 2026-03-01\n```"
        _, results = await handler.execute_commands(response, user_id="u1")
        assert results[0]["priority"] == "high"
        assert results[0]["due"] == "2026-03-01"

    @pytest.mark.asyncio
    async def test_add_persists_to_json(self, handler):
        response = "```todo\nACTION: add\nTITLE: Persistent task\n```"
        await handler.execute_commands(response, user_id="u1")
        data = handler._load_data()
        assert "u1" in data
        assert len(data["u1"]) == 1
        assert data["u1"][0]["title"] == "Persistent task"
        assert data["u1"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_add_no_title_fails(self, handler):
        response = "```todo\nACTION: add\n```"
        _, results = await handler.execute_commands(response, user_id="u1")
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_add_invalid_priority_defaults_medium(self, handler):
        response = "```todo\nACTION: add\nTITLE: Test\nPRIORITY: extreme\n```"
        _, results = await handler.execute_commands(response, user_id="u1")
        assert results[0]["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_add_with_tags(self, handler):
        response = "```todo\nACTION: add\nTITLE: Tagged task\nTAGS: work, urgent\n```"
        await handler.execute_commands(response, user_id="u1")
        data = handler._load_data()
        assert data["u1"][0]["tags"] == ["work", "urgent"]


class TestList:
    """Test listing todos."""

    @pytest.mark.asyncio
    async def test_list_empty(self, handler):
        response = "```todo\nACTION: list\n```"
        _, results = await handler.execute_commands(response, user_id="u1")
        assert results[0]["success"] is True
        assert results[0]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_after_add(self, handler):
        await handler.execute_commands("```todo\nACTION: add\nTITLE: A\n```", user_id="u1")
        await handler.execute_commands("```todo\nACTION: add\nTITLE: B\n```", user_id="u1")
        _, results = await handler.execute_commands("```todo\nACTION: list\n```", user_id="u1")
        assert results[0]["total"] == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_priority(self, handler):
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Low\nPRIORITY: low\n```", user_id="u1")
        await handler.execute_commands("```todo\nACTION: add\nTITLE: High\nPRIORITY: high\n```", user_id="u1")
        _, results = await handler.execute_commands("```todo\nACTION: list\nPRIORITY: high\n```", user_id="u1")
        assert results[0]["total"] == 1
        assert results[0]["todos"][0]["title"] == "High"

    @pytest.mark.asyncio
    async def test_list_filter_by_tag(self, handler):
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Work task\nTAGS: work\n```", user_id="u1")
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Home task\nTAGS: home\n```", user_id="u1")
        _, results = await handler.execute_commands("```todo\nACTION: list\nTAGS: work\n```", user_id="u1")
        assert results[0]["total"] == 1

    @pytest.mark.asyncio
    async def test_list_excludes_deleted(self, handler):
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Keep\n```", user_id="u1")
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Remove\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        await handler.execute_commands(f"```todo\nACTION: delete\nTODO_ID: {tid}\n```", user_id="u1")
        _, results = await handler.execute_commands("```todo\nACTION: list\n```", user_id="u1")
        assert results[0]["total"] == 1

    @pytest.mark.asyncio
    async def test_user_isolation(self, handler):
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Alice task\n```", user_id="alice")
        await handler.execute_commands("```todo\nACTION: add\nTITLE: Bob task\n```", user_id="bob")
        _, results = await handler.execute_commands("```todo\nACTION: list\n```", user_id="alice")
        assert results[0]["total"] == 1
        assert results[0]["todos"][0]["title"] == "Alice task"


class TestDone:
    """Test marking todos as done."""

    @pytest.mark.asyncio
    async def test_mark_done(self, handler):
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Finish\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        _, results = await handler.execute_commands(f"```todo\nACTION: done\nTODO_ID: {tid}\n```", user_id="u1")
        assert results[0]["success"] is True
        data = handler._load_data()
        assert data["u1"][0]["status"] == "done"
        assert data["u1"][0]["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_done_not_found(self, handler):
        _, results = await handler.execute_commands("```todo\nACTION: done\nTODO_ID: nonexistent\n```", user_id="u1")
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_done_no_id(self, handler):
        _, results = await handler.execute_commands("```todo\nACTION: done\n```", user_id="u1")
        assert results[0]["success"] is False


class TestDelete:
    """Test deleting todos."""

    @pytest.mark.asyncio
    async def test_delete(self, handler):
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Trash\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        _, results = await handler.execute_commands(f"```todo\nACTION: delete\nTODO_ID: {tid}\n```", user_id="u1")
        assert results[0]["success"] is True
        data = handler._load_data()
        assert data["u1"][0]["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, handler):
        _, results = await handler.execute_commands("```todo\nACTION: delete\nTODO_ID: nope\n```", user_id="u1")
        assert results[0]["success"] is False


class TestEdit:
    """Test editing todos."""

    @pytest.mark.asyncio
    async def test_edit_title(self, handler):
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Old\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        _, results = await handler.execute_commands(
            f"```todo\nACTION: edit\nTODO_ID: {tid}\nTITLE: New\n```", user_id="u1"
        )
        assert results[0]["success"] is True
        assert "title" in results[0]["updated_fields"]
        data = handler._load_data()
        assert data["u1"][0]["title"] == "New"

    @pytest.mark.asyncio
    async def test_edit_priority(self, handler):
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Test\nPRIORITY: low\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        _, results = await handler.execute_commands(
            f"```todo\nACTION: edit\nTODO_ID: {tid}\nPRIORITY: high\n```", user_id="u1"
        )
        assert results[0]["success"] is True
        data = handler._load_data()
        assert data["u1"][0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_edit_no_fields_fails(self, handler):
        _, add_results = await handler.execute_commands("```todo\nACTION: add\nTITLE: Test\n```", user_id="u1")
        tid = add_results[0]["todo_id"]
        _, results = await handler.execute_commands(
            f"```todo\nACTION: edit\nTODO_ID: {tid}\n```", user_id="u1"
        )
        assert results[0]["success"] is False

    @pytest.mark.asyncio
    async def test_edit_not_found(self, handler):
        _, results = await handler.execute_commands(
            "```todo\nACTION: edit\nTODO_ID: nope\nTITLE: X\n```", user_id="u1"
        )
        assert results[0]["success"] is False


class TestFormatResults:
    """Test result formatting for display."""

    def test_format_add(self, handler):
        results = [{"success": True, "action": "add", "title": "Buy milk", "todo_id": "abc123", "priority": "high", "due": "tomorrow"}]
        text = handler._format_results(results)
        assert "Buy milk" in text
        assert "abc123" in text
        assert "high" in text

    def test_format_error(self, handler):
        results = [{"success": False, "error": "Something broke"}]
        text = handler._format_results(results)
        assert "Something broke" in text

    def test_format_empty_list(self, handler):
        results = [{"success": True, "action": "list", "todos": [], "total": 0}]
        text = handler._format_results(results)
        assert "No todos" in text


class TestCleanedResponse:
    """Test that todo blocks are stripped from the displayed response."""

    @pytest.mark.asyncio
    async def test_blocks_removed(self, handler):
        response = "I'll add that for you!\n\n```todo\nACTION: add\nTITLE: Test\n```\n\nDone!"
        cleaned, _ = await handler.execute_commands(response, user_id="u1")
        assert "```todo" not in cleaned
        assert "I'll add that for you!" in cleaned
        assert "Done!" in cleaned
