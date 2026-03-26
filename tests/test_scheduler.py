# =============================================================================
# test_scheduler.py — Unit tests for SchedulerManager and ScheduledTask
# =============================================================================

import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from skillforge.core.scheduler import ScheduledTask, SchedulerManager, ExecutionLog


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_router():
    router = MagicMock()
    router.handle_message = AsyncMock(return_value="Mock response")
    return router


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "scheduler_data"


@pytest.fixture
def manager(mock_router, data_dir):
    return SchedulerManager(router=mock_router, data_dir=data_dir)


# =============================================================================
# TestScheduledTask — Dataclass fields and serialization
# =============================================================================

class TestScheduledTask:
    """Test ScheduledTask dataclass defaults and serialization."""

    def test_default_fields(self):
        task = ScheduledTask(name="Test")
        assert task.schedule_kind == "cron"
        assert task.interval_seconds == 0
        assert task.run_at == ""
        assert task.delete_after_run is False
        assert task.max_retries == 5
        assert task.retry_count == 0
        assert task.max_concurrent == 1
        assert task.last_error == ""

    def test_id_auto_generated(self):
        task = ScheduledTask(name="Test")
        assert task.id.startswith("task-")

    def test_created_at_uses_utc(self):
        task = ScheduledTask(name="Test")
        assert task.created_at != ""
        # Should be a valid ISO timestamp with timezone info
        dt = datetime.fromisoformat(task.created_at)
        assert dt.tzinfo is not None

    def test_custom_fields(self):
        task = ScheduledTask(
            name="Interval",
            schedule_kind="every",
            interval_seconds=1800,
            max_retries=3,
            max_concurrent=2,
        )
        assert task.schedule_kind == "every"
        assert task.interval_seconds == 1800
        assert task.max_retries == 3
        assert task.max_concurrent == 2

    def test_to_dict_includes_new_fields(self):
        task = ScheduledTask(name="Test", schedule_kind="every", interval_seconds=600)
        d = task.to_dict()
        assert d["schedule_kind"] == "every"
        assert d["interval_seconds"] == 600
        assert d["delete_after_run"] is False
        assert d["max_retries"] == 5
        assert d["retry_count"] == 0
        assert d["max_concurrent"] == 1
        assert d["last_error"] == ""

    def test_from_dict_round_trip(self):
        task = ScheduledTask(
            name="Roundtrip",
            schedule_kind="at",
            run_at="2026-03-01T10:00:00",
            delete_after_run=True,
            max_retries=3,
        )
        d = task.to_dict()
        restored = ScheduledTask.from_dict(d)
        assert restored.name == "Roundtrip"
        assert restored.schedule_kind == "at"
        assert restored.run_at == "2026-03-01T10:00:00"
        assert restored.delete_after_run is True
        assert restored.max_retries == 3

    def test_from_dict_backward_compat(self):
        """Old tasks without new fields should load fine with defaults."""
        old_data = {
            "id": "task-old",
            "name": "Legacy",
            "schedule": "0 9 * * *",
            "action": "send_message",
            "target_channel": "telegram",
            "target_user": "u1",
        }
        task = ScheduledTask.from_dict(old_data)
        assert task.schedule_kind == "cron"
        assert task.interval_seconds == 0
        assert task.max_retries == 5


# =============================================================================
# TestHumanReadable — get_human_schedule()
# =============================================================================

class TestHumanReadable:
    """Test human-readable schedule display."""

    def test_cron_daily_9am(self):
        task = ScheduledTask(name="T", schedule="0 9 * * *")
        assert task.get_human_schedule() == "Daily at 9:00 AM"

    def test_cron_daily_2pm(self):
        task = ScheduledTask(name="T", schedule="0 14 * * *")
        assert task.get_human_schedule() == "Daily at 2:00 PM"

    def test_cron_daily_midnight(self):
        task = ScheduledTask(name="T", schedule="0 0 * * *")
        assert task.get_human_schedule() == "Daily at 12:00 AM"

    def test_cron_weekdays(self):
        task = ScheduledTask(name="T", schedule="0 9 * * 1-5")
        assert task.get_human_schedule() == "Weekdays at 9:00 AM"

    def test_cron_every_15_minutes(self):
        task = ScheduledTask(name="T", schedule="*/15 * * * *")
        assert task.get_human_schedule() == "Every 15 minutes"

    def test_cron_every_2_hours(self):
        task = ScheduledTask(name="T", schedule="0 */2 * * *")
        assert task.get_human_schedule() == "Every 2 hours"

    def test_cron_mondays(self):
        task = ScheduledTask(name="T", schedule="30 8 * * 1")
        assert task.get_human_schedule() == "Mondays at 8:30 AM"

    def test_cron_monthly_1st(self):
        task = ScheduledTask(name="T", schedule="0 0 1 * *")
        assert task.get_human_schedule() == "Monthly on the 1st"

    def test_cron_monthly_3rd(self):
        task = ScheduledTask(name="T", schedule="0 0 3 * *")
        assert task.get_human_schedule() == "Monthly on the 3rd"

    def test_cron_monthly_22nd(self):
        task = ScheduledTask(name="T", schedule="0 0 22 * *")
        assert task.get_human_schedule() == "Monthly on the 22nd"

    def test_cron_fallback_raw(self):
        task = ScheduledTask(name="T", schedule="5 4 * * 0,6")
        # Not a common pattern — returns raw cron
        assert task.get_human_schedule() == "5 4 * * 0,6"

    def test_interval_minutes(self):
        task = ScheduledTask(name="T", schedule_kind="every", interval_seconds=1800)
        assert task.get_human_schedule() == "Every 30 minutes"

    def test_interval_hours(self):
        task = ScheduledTask(name="T", schedule_kind="every", interval_seconds=7200)
        assert task.get_human_schedule() == "Every 2 hours"

    def test_interval_seconds(self):
        task = ScheduledTask(name="T", schedule_kind="every", interval_seconds=45)
        assert task.get_human_schedule() == "Every 45 seconds"

    def test_interval_1_hour(self):
        task = ScheduledTask(name="T", schedule_kind="every", interval_seconds=3600)
        assert task.get_human_schedule() == "Every 1 hour"

    def test_one_shot(self):
        task = ScheduledTask(name="T", schedule_kind="at", run_at="2026-03-01T14:00:00")
        assert task.get_human_schedule() == "Once at 2026-03-01 14:00"

    def test_one_shot_no_time(self):
        task = ScheduledTask(name="T", schedule_kind="at", run_at="")
        assert task.get_human_schedule() == "One-shot (no time set)"


# =============================================================================
# TestMultiTrigger — Trigger creation validation in add_task
# =============================================================================

class TestMultiTrigger:
    """Test multi-trigger validation in add_task."""

    @pytest.mark.asyncio
    async def test_add_cron_task(self, manager):
        task = ScheduledTask(name="Cron", schedule="0 9 * * *",
                             action="send_message", target_user="u1", message="hi")
        task_id = await manager.add_task(task)
        assert task_id in manager.tasks

    @pytest.mark.asyncio
    async def test_add_interval_task(self, manager):
        task = ScheduledTask(name="Interval", schedule_kind="every",
                             interval_seconds=1800,
                             action="send_message", target_user="u1", message="hi")
        task_id = await manager.add_task(task)
        assert task_id in manager.tasks
        assert manager.tasks[task_id].schedule_kind == "every"

    @pytest.mark.asyncio
    async def test_add_oneshot_task(self, manager):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        task = ScheduledTask(name="OneShot", schedule_kind="at", run_at=future,
                             action="send_message", target_user="u1", message="hi")
        task_id = await manager.add_task(task)
        assert task_id in manager.tasks
        assert manager.tasks[task_id].schedule_kind == "at"

    @pytest.mark.asyncio
    async def test_invalid_cron_raises(self, manager):
        task = ScheduledTask(name="Bad", schedule="not-a-cron",
                             action="send_message", target_user="u1", message="hi")
        with pytest.raises(ValueError, match="Invalid cron"):
            await manager.add_task(task)

    @pytest.mark.asyncio
    async def test_invalid_interval_raises(self, manager):
        task = ScheduledTask(name="Bad", schedule_kind="every", interval_seconds=0,
                             action="send_message", target_user="u1", message="hi")
        with pytest.raises(ValueError, match="positive"):
            await manager.add_task(task)

    @pytest.mark.asyncio
    async def test_invalid_oneshot_no_run_at(self, manager):
        task = ScheduledTask(name="Bad", schedule_kind="at", run_at="",
                             action="send_message", target_user="u1", message="hi")
        with pytest.raises(ValueError, match="run_at"):
            await manager.add_task(task)

    @pytest.mark.asyncio
    async def test_invalid_oneshot_bad_datetime(self, manager):
        task = ScheduledTask(name="Bad", schedule_kind="at", run_at="not-a-date",
                             action="send_message", target_user="u1", message="hi")
        with pytest.raises(ValueError, match="Invalid run_at"):
            await manager.add_task(task)

    @pytest.mark.asyncio
    async def test_unknown_kind_raises(self, manager):
        task = ScheduledTask(name="Bad", schedule_kind="unknown",
                             action="send_message", target_user="u1", message="hi")
        with pytest.raises(ValueError, match="Unknown schedule_kind"):
            await manager.add_task(task)


# =============================================================================
# TestRetryBackoff — Retry logic
# =============================================================================

class TestRetryBackoff:
    """Test retry backoff delays and behavior."""

    def test_backoff_delays(self, manager):
        assert manager.RETRY_BACKOFF == [30, 60, 300, 900, 3600]

    @pytest.mark.asyncio
    async def test_retry_increments_count(self, manager):
        task = ScheduledTask(
            name="Fail", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="test",
        )
        await manager.add_task(task)
        await manager.start()

        # Simulate failure — no handler registered for "test" channel
        await manager._execute_task(task)
        assert task.retry_count == 1
        assert task.last_error != ""

        await manager.stop()

    @pytest.mark.asyncio
    async def test_success_resets_retry_count(self, manager):
        async def mock_handler(user_id, message, chat_id=None):
            return True

        manager.register_channel_handler("test", mock_handler)
        task = ScheduledTask(
            name="Succeed", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="test", retry_count=3,
        )
        await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        assert task.retry_count == 0
        assert task.last_error == ""

        await manager.stop()

    @pytest.mark.asyncio
    async def test_no_retry_for_oneshot(self, manager):
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        task = ScheduledTask(
            name="OneShot Fail", schedule_kind="at", run_at=future,
            action="send_message", target_user="u1", message="hi",
            target_channel="test",
        )
        await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        # One-shot tasks don't retry — count stays at 0
        assert task.retry_count == 0

        await manager.stop()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, manager):
        task = ScheduledTask(
            name="Max Retry", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="test", retry_count=5, max_retries=5,
        )
        await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        # Should not increment beyond max
        assert task.retry_count == 5

        await manager.stop()


# =============================================================================
# TestConcurrency — Max concurrent execution
# =============================================================================

class TestConcurrency:
    """Test concurrency control."""

    @pytest.mark.asyncio
    async def test_skip_when_max_concurrent_reached(self, manager):
        task = ScheduledTask(
            name="Concurrent", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="test", max_concurrent=1,
        )
        await manager.add_task(task)
        await manager.start()

        # Simulate task already running
        manager._running_tasks.add(task.id)

        # This should be skipped due to max_concurrent
        await manager._execute_task(task)

        # Clean up — only one entry should be in running (the one we added)
        assert task.id in manager._running_tasks
        manager._running_tasks.discard(task.id)

        await manager.stop()

    @pytest.mark.asyncio
    async def test_allow_after_completion(self, manager):
        async def mock_handler(user_id, message, chat_id=None):
            return True

        manager.register_channel_handler("test", mock_handler)
        task = ScheduledTask(
            name="Sequential", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="test", max_concurrent=1,
        )
        await manager.add_task(task)
        await manager.start()

        # Run once — should complete and remove from running
        await manager._execute_task(task)
        assert task.id not in manager._running_tasks

        # Run again — should be allowed
        await manager._execute_task(task)
        assert task.id not in manager._running_tasks

        await manager.stop()


# =============================================================================
# TestOneShot — Auto-delete behavior
# =============================================================================

class TestOneShot:
    """Test one-shot task auto-deletion."""

    @pytest.mark.asyncio
    async def test_auto_delete_after_success(self, manager):
        async def mock_handler(user_id, message, chat_id=None):
            return True

        manager.register_channel_handler("test", mock_handler)
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        task = ScheduledTask(
            name="AutoDelete", schedule_kind="at", run_at=future,
            action="send_message", target_user="u1", message="hi",
            target_channel="test", delete_after_run=True,
        )
        task_id = await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        assert task_id not in manager.tasks

        await manager.stop()

    @pytest.mark.asyncio
    async def test_no_delete_when_flag_false(self, manager):
        async def mock_handler(user_id, message, chat_id=None):
            return True

        manager.register_channel_handler("test", mock_handler)
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        task = ScheduledTask(
            name="KeepAfter", schedule_kind="at", run_at=future,
            action="send_message", target_user="u1", message="hi",
            target_channel="test", delete_after_run=False,
        )
        task_id = await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        # Task should still exist
        assert task_id in manager.tasks

        await manager.stop()


# =============================================================================
# TestPersistence — Save/load with new fields
# =============================================================================

class TestPersistence:
    """Test task persistence with new fields."""

    @pytest.mark.asyncio
    async def test_save_and_load_interval_task(self, mock_router, data_dir):
        manager1 = SchedulerManager(router=mock_router, data_dir=data_dir)
        task = ScheduledTask(
            name="Persist Interval",
            schedule_kind="every",
            interval_seconds=3600,
            action="send_message",
            target_user="u1",
            message="hi",
        )
        await manager1.add_task(task)

        # Create new manager — should load the task
        manager2 = SchedulerManager(router=mock_router, data_dir=data_dir)
        assert len(manager2.tasks) == 1
        loaded = list(manager2.tasks.values())[0]
        assert loaded.schedule_kind == "every"
        assert loaded.interval_seconds == 3600

    @pytest.mark.asyncio
    async def test_save_and_load_oneshot_task(self, mock_router, data_dir):
        manager1 = SchedulerManager(router=mock_router, data_dir=data_dir)
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat()
        task = ScheduledTask(
            name="Persist OneShot",
            schedule_kind="at",
            run_at=future,
            delete_after_run=True,
            action="send_message",
            target_user="u1",
            message="hi",
        )
        await manager1.add_task(task)

        manager2 = SchedulerManager(router=mock_router, data_dir=data_dir)
        loaded = list(manager2.tasks.values())[0]
        assert loaded.schedule_kind == "at"
        assert loaded.delete_after_run is True


# =============================================================================
# TestExecutionLog
# =============================================================================

class TestExecutionLog:
    """Test execution log dataclass."""

    def test_log_to_dict(self):
        log = ExecutionLog(
            task_id="t1", task_name="Test",
            timestamp="2026-01-01T00:00:00", success=True,
        )
        d = log.to_dict()
        assert d["task_id"] == "t1"
        assert d["success"] is True

    def test_log_with_error(self):
        log = ExecutionLog(
            task_id="t1", task_name="Test",
            timestamp="2026-01-01T00:00:00", success=False,
            error="Connection refused",
        )
        d = log.to_dict()
        assert d["error"] == "Connection refused"


# =============================================================================
# TestSchedulerStatus
# =============================================================================

class TestSchedulerStatus:
    """Test scheduler status reporting."""

    def test_status_initial(self, manager):
        status = manager.get_status()
        assert status["running"] is False
        assert status["task_count"] == 0

    @pytest.mark.asyncio
    async def test_status_with_tasks(self, manager):
        task = ScheduledTask(
            name="Status Test", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
        )
        await manager.add_task(task)
        status = manager.get_status()
        assert status["task_count"] == 1
        assert status["active_tasks"] == 1

    @pytest.mark.asyncio
    async def test_list_tasks_includes_human_schedule(self, manager):
        task = ScheduledTask(
            name="List Test", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
        )
        await manager.add_task(task)
        tasks = manager.list_tasks()
        assert len(tasks) == 1
        assert tasks[0]["human_schedule"] == "Daily at 9:00 AM"


# =============================================================================
# TestFletChannelHandler — Flet channel handler registration
# =============================================================================

class TestFletChannelHandler:
    """Test that a registered flet handler is called when a task fires."""

    @pytest.mark.asyncio
    async def test_register_flet_handler(self, manager):
        """Registering a flet handler should store it in channel_handlers."""
        async def flet_handler(user_id, message, chat_id=None):
            return True

        manager.register_channel_handler("flet", flet_handler)
        assert "flet" in manager.channel_handlers

    @pytest.mark.asyncio
    async def test_flet_handler_called_on_task_execute(self, manager):
        """When a task targets 'flet', the registered handler should be called."""
        call_log = []

        async def flet_handler(user_id, message, chat_id=None):
            call_log.append({"user_id": user_id, "message": message})
            return True

        manager.register_channel_handler("flet", flet_handler)
        task = ScheduledTask(
            name="Flet Reminder", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="drink water",
            target_channel="flet",
        )
        await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        assert len(call_log) == 1
        assert call_log[0]["message"] == "drink water"
        assert call_log[0]["user_id"] == "u1"

        await manager.stop()

    @pytest.mark.asyncio
    async def test_flet_handler_failure_increments_retry(self, manager):
        """A failing flet handler should trigger retry logic."""
        async def failing_handler(user_id, message, chat_id=None):
            return False

        manager.register_channel_handler("flet", failing_handler)
        task = ScheduledTask(
            name="Fail Flet", schedule="0 9 * * *",
            action="send_message", target_user="u1", message="hi",
            target_channel="flet",
        )
        await manager.add_task(task)
        await manager.start()

        await manager._execute_task(task)
        assert task.retry_count == 1

        await manager.stop()
