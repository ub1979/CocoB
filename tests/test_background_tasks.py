# =============================================================================
# test_background_tasks.py — Tests for background task runner
# =============================================================================

import pytest
import tempfile
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_status_values(self):
        """All statuses should have correct values."""
        from skillforge.core.background_tasks import TaskStatus
        
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.PAUSED.value == "paused"


class TestTaskType:
    """Test TaskType constants."""

    def test_task_types_defined(self):
        """All task types should be defined."""
        from skillforge.core.background_tasks import TaskType
        
        assert TaskType.HEALTH_MONITOR == "health_monitor"
        assert TaskType.DATA_SYNC == "data_sync"
        assert TaskType.PERIODIC_CHECK == "periodic_check"
        assert TaskType.SCHEDULED_JOB == "scheduled_job"

    def test_all_types_list(self):
        """ALL_TYPES should contain all types."""
        from skillforge.core.background_tasks import TaskType
        
        assert len(TaskType.ALL_TYPES) == 4


class TestBackgroundTask:
    """Test BackgroundTask dataclass."""

    def test_task_creation(self):
        """Should create task with defaults."""
        from skillforge.core.background_tasks import BackgroundTask
        
        task = BackgroundTask(
            task_id="test123",
            task_type="health_monitor",
            name="Test Task",
            description="A test task"
        )
        
        assert task.task_id == "test123"
        assert task.status == "pending"
        assert task.run_count == 0
        assert task.required_auth_level == "YELLOW"

    def test_is_active(self):
        """Should correctly determine if task is active."""
        from skillforge.core.background_tasks import BackgroundTask, TaskStatus
        
        task = BackgroundTask(
            task_id="test",
            task_type="health_monitor",
            name="Test",
            description="Test"
        )
        assert task.is_active is True
        
        task.status = TaskStatus.PAUSED.value
        assert task.is_active is False
        
        task.status = TaskStatus.COMPLETED.value
        assert task.is_active is False

    def test_is_due_interval(self):
        """Should correctly determine if interval task is due."""
        from skillforge.core.background_tasks import BackgroundTask
        
        task = BackgroundTask(
            task_id="test",
            task_type="periodic_check",
            name="Test",
            description="Test",
            interval_minutes=60
        )
        
        # Never run - should be due
        assert task.is_due is True
        
        # Just ran - should not be due
        task.last_run = datetime.now().isoformat()
        assert task.is_due is False

    def test_is_due_scheduled(self):
        """Should correctly determine if scheduled task is due."""
        from skillforge.core.background_tasks import BackgroundTask
        
        current_time = datetime.now().strftime("%H:%M")
        task = BackgroundTask(
            task_id="test",
            task_type="scheduled_job",
            name="Test",
            description="Test",
            schedule_time=current_time
        )
        
        # Should be due at scheduled time
        assert task.is_due is True

    def test_to_dict(self):
        """Should convert to dictionary."""
        from skillforge.core.background_tasks import BackgroundTask
        
        task = BackgroundTask(
            task_id="test",
            task_type="health_monitor",
            name="Test",
            description="Test"
        )
        
        data = task.to_dict()
        assert data["task_id"] == "test"
        assert data["task_type"] == "health_monitor"

    def test_from_dict(self):
        """Should create from dictionary."""
        from skillforge.core.background_tasks import BackgroundTask
        
        data = {
            "task_id": "test",
            "task_type": "health_monitor",
            "name": "Test",
            "description": "Test description",
            "status": "running",
            "run_count": 5
        }
        
        task = BackgroundTask.from_dict(data)
        assert task.task_id == "test"
        assert task.status == "running"
        assert task.run_count == 5


class TestTaskResult:
    """Test TaskResult dataclass."""

    def test_result_creation(self):
        """Should create result."""
        from skillforge.core.background_tasks import TaskResult
        
        result = TaskResult(
            task_id="test",
            success=True,
            output="Test output"
        )
        
        assert result.task_id == "test"
        assert result.success is True
        assert result.output == "Test output"


class TestBackgroundTaskRunnerInitialization:
    """Test BackgroundTaskRunner initialization."""

    def test_initialization(self):
        """Should initialize with empty state."""
        from skillforge.core.background_tasks import BackgroundTaskRunner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            assert runner._running is False
            assert len(runner._tasks) == 0
            assert runner._semaphore._value == 5  # MAX_CONCURRENT

    def test_creates_data_directory(self):
        """Should create data directory."""
        from skillforge.core.background_tasks import BackgroundTaskRunner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "tasks"
            runner = BackgroundTaskRunner(data_dir=data_dir)
            
            assert data_dir.exists()


class TestTaskManagement:
    """Test task management methods."""

    def test_create_task(self):
        """Should create a new task."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Health Check",
                description="Check system health",
                interval_minutes=60
            )
            
            assert task is not None
            assert task.name == "Health Check"
            assert task.interval_minutes == 60
            assert task.task_id in runner._tasks

    def test_create_task_invalid_type(self):
        """Should reject invalid task type."""
        from skillforge.core.background_tasks import BackgroundTaskRunner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type="invalid_type",
                name="Test",
                description="Test"
            )
            
            assert task is None

    def test_get_task(self):
        """Should retrieve task by ID."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            retrieved = runner.get_task(task.task_id)
            assert retrieved is not None
            assert retrieved.task_id == task.task_id

    def test_get_all_tasks(self):
        """Should return all tasks."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            runner.create_task(user_id="user1", task_type=TaskType.HEALTH_MONITOR,
                             name="Task 1", description="Test")
            runner.create_task(user_id="user1", task_type=TaskType.DATA_SYNC,
                             name="Task 2", description="Test")
            
            tasks = runner.get_all_tasks()
            assert len(tasks) == 2

    def test_get_active_tasks(self):
        """Should return only active tasks."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType, TaskStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task1 = runner.create_task(user_id="user1", task_type=TaskType.HEALTH_MONITOR,
                                      name="Active", description="Test")
            task2 = runner.create_task(user_id="user1", task_type=TaskType.DATA_SYNC,
                                      name="Paused", description="Test")
            
            # Pause second task
            runner._tasks[task2.task_id].status = TaskStatus.PAUSED.value
            
            active = runner.get_active_tasks()
            assert len(active) == 1
            assert active[0].task_id == task1.task_id

    def test_update_task(self):
        """Should update task fields."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Original",
                description="Original desc"
            )
            
            updated = runner.update_task(
                user_id="user1",
                task_id=task.task_id,
                name="Updated",
                description="Updated desc"
            )
            
            assert updated is not None
            assert updated.name == "Updated"
            assert updated.description == "Updated desc"

    def test_delete_task(self):
        """Should delete task."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            result = runner.delete_task("user1", task.task_id)
            assert result is True
            assert task.task_id not in runner._tasks

    def test_pause_resume_task(self):
        """Should pause and resume tasks."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType, TaskStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            # Pause
            result = runner.pause_task("user1", task.task_id)
            assert result is True
            assert runner._tasks[task.task_id].status == TaskStatus.PAUSED.value
            
            # Resume
            result = runner.resume_task("user1", task.task_id)
            assert result is True
            assert runner._tasks[task.task_id].status == TaskStatus.PENDING.value


class TestTaskExecution:
    """Test task execution."""

    @pytest.mark.asyncio
    async def test_register_task_handler(self):
        """Should register task handler."""
        from skillforge.core.background_tasks import BackgroundTaskRunner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            handler = AsyncMock(return_value="success")
            runner.register_task_handler("test_type", handler)
            
            assert "test_type" in runner._task_handlers

    @pytest.mark.asyncio
    async def test_execute_task_with_handler(self):
        """Should execute task using registered handler."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType, BackgroundTask
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            handler = AsyncMock(return_value="Task completed")
            runner.register_task_handler(TaskType.HEALTH_MONITOR, handler)
            
            task = BackgroundTask(
                task_id="test",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            await runner._execute_task(task)
            
            handler.assert_called_once()
            assert task.status == "completed"
            assert task.run_count == 1

    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        """Should handle task execution failure."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType, BackgroundTask
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            handler = AsyncMock(side_effect=Exception("Task failed"))
            runner.register_task_handler(TaskType.HEALTH_MONITOR, handler)
            
            task = BackgroundTask(
                task_id="test",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            await runner._execute_task(task)
            
            assert task.status == "failed"
            assert task.last_error is not None

    @pytest.mark.asyncio
    async def test_run_task_now(self):
        """Should manually trigger task execution."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            # Mock execution to avoid actual run
            with patch.object(runner, '_execute_task') as mock_exec:
                result = await runner.run_task_now("user1", task.task_id)
                assert result is True
                mock_exec.assert_called_once()


class TestTaskScheduler:
    """Test task scheduler."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Should start and stop scheduler."""
        from skillforge.core.background_tasks import BackgroundTaskRunner
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            assert runner._running is False
            
            await runner.start()
            assert runner._running is True
            
            await runner.stop()
            assert runner._running is False


class TestTaskResults:
    """Test task results tracking."""

    def test_get_task_results(self):
        """Should return task results."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            # Add some mock results
            runner._results[task.task_id] = [
                {"success": True, "timestamp": "2026-01-01T00:00:00"},
                {"success": False, "timestamp": "2026-01-01T01:00:00"},
            ]
            
            results = runner.get_task_results(task.task_id)
            assert len(results) == 2

    def test_get_task_results_with_limit(self):
        """Should respect result limit."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            # Add many results
            runner._results[task.task_id] = [
                {"success": True, "timestamp": f"2026-01-01T{i:02d}:00:00"}
                for i in range(20)
            ]
            
            results = runner.get_task_results(task.task_id, limit=5)
            assert len(results) == 5


class TestTaskPersistence:
    """Test task persistence."""

    def test_save_and_load_tasks(self):
        """Should persist tasks across instances."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance - create task
            runner1 = BackgroundTaskRunner(data_dir=tmpdir)
            task = runner1.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test",
                interval_minutes=60
            )
            
            # Second instance - should load task
            runner2 = BackgroundTaskRunner(data_dir=tmpdir)
            
            loaded = runner2.get_task(task.task_id)
            assert loaded is not None
            assert loaded.name == "Test"
            assert loaded.interval_minutes == 60


class TestTaskStatus:
    """Test task status methods."""

    def test_get_status(self):
        """Should return correct status."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = BackgroundTaskRunner(data_dir=tmpdir)
            
            runner.create_task(user_id="user1", task_type=TaskType.HEALTH_MONITOR,
                             name="Task 1", description="Test")
            runner.create_task(user_id="user1", task_type=TaskType.DATA_SYNC,
                             name="Task 2", description="Test")
            
            status = runner.get_status()
            
            assert status["running"] is False
            assert status["total_tasks"] == 2
            assert status["active_tasks"] == 2
            assert status["task_types"][TaskType.HEALTH_MONITOR] == 1


class TestTaskAuthorization:
    """Test task authorization with AuthManager."""

    def test_create_task_requires_auth(self):
        """Should check auth when creating tasks."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        from skillforge.core.auth_manager import AuthManager, SecurityLevel
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            task_dir = Path(tmpdir) / "tasks"
            
            auth_manager = AuthManager(data_dir=auth_dir)
            auth_manager.setup_password("password123")
            
            runner = BackgroundTaskRunner(data_dir=task_dir, auth_manager=auth_manager)
            
            # Without auth - should fail
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            assert task is None
            
            # With auth - should succeed
            auth_manager.authenticate_password("user1", "password123")
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            assert task is not None

    def test_delete_task_requires_auth(self):
        """Should check auth when deleting tasks."""
        from skillforge.core.background_tasks import BackgroundTaskRunner, TaskType
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            task_dir = Path(tmpdir) / "tasks"
            
            auth_manager = AuthManager(data_dir=auth_dir)
            auth_manager.setup_password("password123")
            auth_manager.authenticate_password("user1", "password123")
            
            runner = BackgroundTaskRunner(data_dir=task_dir, auth_manager=auth_manager)
            
            task = runner.create_task(
                user_id="user1",
                task_type=TaskType.HEALTH_MONITOR,
                name="Test",
                description="Test"
            )
            
            # Clear auth
            auth_manager._sessions.clear()
            
            # Without auth - should fail
            result = runner.delete_task("user1", task.task_id)
            assert result is False
