# =============================================================================
# test_schedule_handler.py — Unit tests for ScheduleCommandHandler
# =============================================================================

import pytest
from skillforge.core.schedule_handler import ScheduleCommandHandler


@pytest.fixture
def handler():
    return ScheduleCommandHandler()


class TestDetection:
    """Test schedule block detection."""

    def test_detects_schedule_block(self, handler):
        response = "```schedule\nACTION: list\n```"
        assert handler.has_schedule_commands(response) is True

    def test_no_false_positive(self, handler):
        assert handler.has_schedule_commands("no blocks here") is False

    def test_case_insensitive(self, handler):
        response = "```Schedule\nACTION: list\n```"
        assert handler.has_schedule_commands(response) is True


class TestParsing:
    """Test schedule block parsing."""

    def test_parse_create(self, handler):
        block = "ACTION: create\nNAME: Test\nSCHEDULE: 0 9 * * *\nMESSAGE: Hello"
        result = handler.parse_schedule_block(block)
        assert result["ACTION"] == "create"
        assert result["NAME"] == "Test"
        assert result["SCHEDULE"] == "0 9 * * *"
        assert result["MESSAGE"] == "Hello"

    def test_parse_with_skill(self, handler):
        block = "ACTION: create\nNAME: Brief\nSCHEDULE: 0 9 * * *\nSKILL: calendar\nPARAMS: today"
        result = handler.parse_schedule_block(block)
        assert result["SKILL"] == "calendar"
        assert result["PARAMS"] == "today"

    def test_extract_multiple(self, handler):
        response = "```schedule\nACTION: list\n```\n```schedule\nACTION: list\n```"
        commands = handler.extract_commands(response)
        assert len(commands) == 2

    def test_extract_ignores_no_action(self, handler):
        response = "```schedule\nNAME: orphan\n```"
        commands = handler.extract_commands(response)
        assert len(commands) == 0


class TestExecuteWithoutManager:
    """Without a scheduler manager, commands should gracefully fail."""

    @pytest.mark.asyncio
    async def test_returns_response_unchanged(self, handler):
        response = "```schedule\nACTION: list\n```"
        cleaned, results = await handler.execute_commands(response, channel="test", user_id="u1")
        assert results == []


class TestFormatResults:
    """Test result formatting."""

    def test_format_create(self, handler):
        results = [{"success": True, "action": "create", "task_id": "abc", "name": "Test", "schedule": "0 9 * * *"}]
        text = handler._format_results(results)
        assert "Test" in text
        assert "abc" in text

    def test_format_empty_list(self, handler):
        results = [{"success": True, "action": "list", "tasks": [], "total": 0}]
        text = handler._format_results(results)
        assert "No scheduled tasks" in text

    def test_format_error(self, handler):
        results = [{"success": False, "error": "Oops"}]
        text = handler._format_results(results)
        assert "Oops" in text

    def test_format_create_with_kind(self, handler):
        results = [{"success": True, "action": "create", "task_id": "abc",
                     "name": "Interval", "schedule": "Every 30 minutes", "schedule_kind": "every"}]
        text = handler._format_results(results)
        assert "Interval" in text
        assert "every" in text

    def test_format_list_with_human_schedule(self, handler):
        tasks = [{"name": "Daily", "id": "t1", "enabled": True,
                  "next_run": None, "human_schedule": "Daily at 9:00 AM"}]
        results = [{"success": True, "action": "list", "tasks": tasks, "total": 1}]
        text = handler._format_results(results)
        assert "Daily at 9:00 AM" in text


# =============================================================================
# TestNewFieldParsing — Parse KIND, INTERVAL, RUN_AT
# =============================================================================

class TestNewFieldParsing:
    """Test parsing of new schedule fields."""

    def test_parse_kind_every(self, handler):
        block = "ACTION: create\nNAME: Check\nKIND: every\nINTERVAL: 30m\nMESSAGE: ping"
        result = handler.parse_schedule_block(block)
        assert result["KIND"] == "every"
        assert result["INTERVAL"] == "30m"

    def test_parse_kind_at(self, handler):
        block = "ACTION: create\nNAME: Reminder\nKIND: at\nRUN_AT: 2026-03-01T14:00:00\nMESSAGE: hi"
        result = handler.parse_schedule_block(block)
        assert result["KIND"] == "at"
        assert result["RUN_AT"] == "2026-03-01T14:00:00"

    def test_parse_delete_after(self, handler):
        block = "ACTION: create\nNAME: One\nKIND: at\nRUN_AT: 2026-03-01T14:00:00\nDELETE_AFTER: false\nMESSAGE: hi"
        result = handler.parse_schedule_block(block)
        assert result["DELETE_AFTER"] == "false"


# =============================================================================
# TestParseInterval — _parse_interval() helper
# =============================================================================

class TestParseInterval:
    """Test interval string parsing."""

    def test_parse_minutes(self, handler):
        assert handler._parse_interval("30m") == 1800

    def test_parse_hours(self, handler):
        assert handler._parse_interval("2h") == 7200

    def test_parse_seconds(self, handler):
        assert handler._parse_interval("60s") == 60

    def test_parse_bare_number(self, handler):
        assert handler._parse_interval("120") == 120

    def test_parse_with_whitespace(self, handler):
        assert handler._parse_interval("  1h  ") == 3600

    def test_parse_invalid_raises(self, handler):
        with pytest.raises(ValueError):
            handler._parse_interval("abc")


# =============================================================================
# TestHandlerCreateNewKinds — Integration with mock scheduler
# =============================================================================

class TestHandlerCreateNewKinds:
    """Test _handle_create with new trigger kinds."""

    @pytest.fixture
    def mock_manager(self):
        from unittest.mock import AsyncMock, MagicMock
        mgr = MagicMock()
        mgr.add_task = AsyncMock(return_value="task-new")
        return mgr

    @pytest.fixture
    def handler_with_mgr(self, mock_manager):
        h = ScheduleCommandHandler(scheduler_manager=mock_manager)
        return h

    @pytest.mark.asyncio
    async def test_create_interval_task(self, handler_with_mgr, mock_manager):
        cmd = {"ACTION": "create", "NAME": "Health", "KIND": "every",
               "INTERVAL": "30m", "MESSAGE": "check"}
        result = await handler_with_mgr._handle_create(cmd, "test", "u1", None)
        assert result["success"] is True
        assert result["schedule_kind"] == "every"
        # Verify the ScheduledTask was created with correct fields
        call_args = mock_manager.add_task.call_args[0][0]
        assert call_args.schedule_kind == "every"
        assert call_args.interval_seconds == 1800

    @pytest.mark.asyncio
    async def test_create_oneshot_task(self, handler_with_mgr, mock_manager):
        cmd = {"ACTION": "create", "NAME": "Remind", "KIND": "at",
               "RUN_AT": "2026-03-01T14:00:00", "MESSAGE": "meeting!"}
        result = await handler_with_mgr._handle_create(cmd, "test", "u1", None)
        assert result["success"] is True
        assert result["schedule_kind"] == "at"
        call_args = mock_manager.add_task.call_args[0][0]
        assert call_args.run_at == "2026-03-01T14:00:00"
        assert call_args.delete_after_run is True  # default for one-shot

    @pytest.mark.asyncio
    async def test_create_oneshot_keep(self, handler_with_mgr, mock_manager):
        cmd = {"ACTION": "create", "NAME": "Keep", "KIND": "at",
               "RUN_AT": "2026-03-01T14:00:00", "DELETE_AFTER": "false", "MESSAGE": "hi"}
        result = await handler_with_mgr._handle_create(cmd, "test", "u1", None)
        assert result["success"] is True
        call_args = mock_manager.add_task.call_args[0][0]
        assert call_args.delete_after_run is False

    @pytest.mark.asyncio
    async def test_create_interval_no_interval_fails(self, handler_with_mgr):
        cmd = {"ACTION": "create", "NAME": "Bad", "KIND": "every", "MESSAGE": "check"}
        result = await handler_with_mgr._handle_create(cmd, "test", "u1", None)
        assert result["success"] is False
        assert "INTERVAL" in result["error"]

    @pytest.mark.asyncio
    async def test_create_oneshot_no_run_at_fails(self, handler_with_mgr):
        cmd = {"ACTION": "create", "NAME": "Bad", "KIND": "at", "MESSAGE": "hi"}
        result = await handler_with_mgr._handle_create(cmd, "test", "u1", None)
        assert result["success"] is False
        assert "RUN_AT" in result["error"]


# =============================================================================
# TestDeleteByName — delete all matching tasks by name
# =============================================================================

class TestDeleteByName:
    """Test that delete by name removes ALL matching tasks, not just the first."""

    @pytest.fixture
    def mock_manager(self):
        from unittest.mock import AsyncMock, MagicMock
        from dataclasses import dataclass

        @dataclass
        class FakeTask:
            name: str
            target_user: str

        mgr = MagicMock()
        mgr.tasks = {
            "t1": FakeTask(name="Drink Water Reminder", target_user="u1"),
            "t2": FakeTask(name="Drink water", target_user="u1"),
            "t3": FakeTask(name="Exercise", target_user="u1"),
        }
        mgr.remove_task = AsyncMock(return_value=True)
        return mgr

    @pytest.fixture
    def handler_with_mgr(self, mock_manager):
        return ScheduleCommandHandler(scheduler_manager=mock_manager)

    @pytest.mark.asyncio
    async def test_delete_by_name_removes_all_matches(self, handler_with_mgr, mock_manager):
        cmd = {"ACTION": "delete", "NAME": "drink water"}
        result = await handler_with_mgr._handle_delete(cmd)
        assert result["success"] is True
        # Should delete both t1 and t2 (both match "drink water")
        calls = mock_manager.remove_task.call_args_list
        deleted_ids = [c[0][0] for c in calls]
        assert "t1" in deleted_ids
        assert "t2" in deleted_ids
        assert "t3" not in deleted_ids

    @pytest.mark.asyncio
    async def test_delete_by_name_no_match(self, handler_with_mgr):
        cmd = {"ACTION": "delete", "NAME": "nonexistent"}
        result = await handler_with_mgr._handle_delete(cmd)
        assert result["success"] is False
        assert "nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_by_task_id_still_works(self, handler_with_mgr, mock_manager):
        cmd = {"ACTION": "delete", "TASK_ID": "t3"}
        result = await handler_with_mgr._handle_delete(cmd)
        assert result["success"] is True
        assert result["task_id"] == "t3"
        mock_manager.remove_task.assert_called_once_with("t3")


# =============================================================================
# TestDeleteAll — delete_all action
# =============================================================================

class TestDeleteAll:
    """Test delete_all action removes all user tasks."""

    @pytest.fixture
    def mock_manager(self):
        from unittest.mock import AsyncMock, MagicMock
        from dataclasses import dataclass

        @dataclass
        class FakeTask:
            name: str
            target_user: str

        mgr = MagicMock()
        mgr.tasks = {
            "t1": FakeTask(name="Drink water", target_user="u1"),
            "t2": FakeTask(name="Exercise", target_user="u1"),
            "t3": FakeTask(name="Other user task", target_user="u2"),
        }
        mgr.remove_task = AsyncMock(return_value=True)
        return mgr

    @pytest.fixture
    def handler_with_mgr(self, mock_manager):
        return ScheduleCommandHandler(scheduler_manager=mock_manager)

    @pytest.mark.asyncio
    async def test_delete_all_for_user(self, handler_with_mgr, mock_manager):
        result = await handler_with_mgr._handle_delete_all("u1")
        assert result["success"] is True
        assert result["action"] == "delete_all"
        assert result["deleted_count"] == 2
        # Should only delete u1's tasks, not u2's
        calls = mock_manager.remove_task.call_args_list
        deleted_ids = [c[0][0] for c in calls]
        assert "t1" in deleted_ids
        assert "t2" in deleted_ids
        assert "t3" not in deleted_ids

    @pytest.mark.asyncio
    async def test_delete_all_via_execute(self, handler_with_mgr):
        response = "Sure!\n```schedule\nACTION: delete_all\n```"
        cleaned, results = await handler_with_mgr.execute_commands(
            response, "test", "u1", None
        )
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_with_name_all(self, handler_with_mgr):
        """ACTION: delete with NAME: all should trigger delete_all."""
        response = "```schedule\nACTION: delete\nNAME: all\n```"
        cleaned, results = await handler_with_mgr.execute_commands(
            response, "test", "u1", None
        )
        assert len(results) == 1
        assert results[0]["action"] == "delete_all"
        assert results[0]["deleted_count"] == 2

    def test_format_delete_all(self, handler_with_mgr):
        results = [{"success": True, "action": "delete_all", "deleted_count": 5}]
        text = handler_with_mgr._format_results(results)
        assert "All reminders stopped" in text
        assert "5" in text
