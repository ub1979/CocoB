# =============================================================================
'''
    File Name : scheduler.py

    Description : Task Scheduler module using APScheduler for cron-based task
                  execution. Supports scheduled message sending and skill
                  execution across all configured channels.

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError

if TYPE_CHECKING:
    from coco_b.core.router import MessageRouter

# =============================================================================
# Setup logging
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")


# =============================================================================
'''
    ScheduledTask : Configuration dataclass for scheduled tasks
                    Stores all task parameters including schedule, action,
                    and target channel/user information
'''
# =============================================================================
@dataclass
class ScheduledTask:
    """Configuration for a scheduled task"""
    id: str = ""
    name: str = ""
    description: str = ""
    enabled: bool = True
    schedule: str = "0 9 * * *"  # Cron expression (default: 9 AM daily)
    timezone: str = "UTC"
    action: str = "send_message"  # "send_message" or "execute_skill"
    target_channel: str = "telegram"  # telegram, discord, slack, etc.
    target_user: str = ""  # User ID to send message to
    target_chat: Optional[str] = None  # Optional chat/channel ID
    message: Optional[str] = None  # Message to send (for send_message action)
    skill_name: Optional[str] = None  # Skill to execute (for execute_skill action)
    skill_params: Optional[str] = None  # Parameters for skill
    created_at: str = ""
    updated_at: str = ""

    # New fields for multi-trigger, retry, concurrency
    schedule_kind: str = "cron"       # "cron", "every", or "at"
    interval_seconds: int = 0         # For kind="every" (e.g., 1800 = 30 min)
    run_at: str = ""                  # For kind="at" — ISO 8601 datetime
    delete_after_run: bool = False    # Auto-delete one-shot tasks after success
    max_retries: int = 5             # Max retry attempts on failure
    retry_count: int = 0             # Current consecutive failure count
    max_concurrent: int = 1          # Max concurrent executions
    last_error: str = ""             # Last error message for display

    # =========================================================================
    # Function __post_init__ -> None to None
    # =========================================================================
    def __post_init__(self):
        """Initialize id and timestamps if not set"""
        if not self.id:
            self.id = f"task-{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now(tz=timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    # =========================================================================
    # Function get_human_schedule -> None to str
    # =========================================================================
    def get_human_schedule(self) -> str:
        """Convert schedule to human-readable English."""
        if self.schedule_kind == "every":
            secs = self.interval_seconds
            if secs >= 3600 and secs % 3600 == 0:
                n = secs // 3600
                return f"Every {n} hour{'s' if n != 1 else ''}"
            elif secs >= 60 and secs % 60 == 0:
                n = secs // 60
                return f"Every {n} minute{'s' if n != 1 else ''}"
            else:
                return f"Every {secs} second{'s' if secs != 1 else ''}"

        if self.schedule_kind == "at":
            if self.run_at:
                try:
                    dt = datetime.fromisoformat(self.run_at)
                    return f"Once at {dt.strftime('%Y-%m-%d %H:%M')}"
                except (ValueError, TypeError):
                    return f"Once at {self.run_at}"
            return "One-shot (no time set)"

        # Cron — map common patterns to English
        parts = self.schedule.split()
        if len(parts) == 5:
            minute, hour, dom, month, dow = parts

            # Every N minutes: */15 * * * *
            if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
                n = minute[2:]
                return f"Every {n} minutes"

            # Every N hours: 0 */2 * * *
            if minute == "0" and hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
                n = hour[2:]
                return f"Every {n} hours"

            # Daily at HH:MM
            if dom == "*" and month == "*" and dow == "*" and not hour.startswith("*/") and not minute.startswith("*/"):
                try:
                    h, m = int(hour), int(minute)
                    time_str = f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}"
                    if h > 12:
                        time_str = f"{h - 12}:{m:02d} PM"
                    elif h == 0:
                        time_str = f"12:{m:02d} AM"
                    return f"Daily at {time_str}"
                except (ValueError, TypeError):
                    pass

            # Weekdays at HH:MM: M H * * 1-5
            if dom == "*" and month == "*" and dow == "1-5":
                try:
                    h, m = int(hour), int(minute)
                    time_str = f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}"
                    if h > 12:
                        time_str = f"{h - 12}:{m:02d} PM"
                    elif h == 0:
                        time_str = f"12:{m:02d} AM"
                    return f"Weekdays at {time_str}"
                except (ValueError, TypeError):
                    pass

            # Specific weekday: M H * * N
            day_names = {"0": "Sundays", "1": "Mondays", "2": "Tuesdays",
                         "3": "Wednesdays", "4": "Thursdays", "5": "Fridays", "6": "Saturdays"}
            if dom == "*" and month == "*" and dow in day_names:
                try:
                    h, m = int(hour), int(minute)
                    time_str = f"{h}:{m:02d} {'AM' if h < 12 else 'PM'}"
                    if h > 12:
                        time_str = f"{h - 12}:{m:02d} PM"
                    elif h == 0:
                        time_str = f"12:{m:02d} AM"
                    return f"{day_names[dow]} at {time_str}"
                except (ValueError, TypeError):
                    pass

            # Monthly: 0 0 1 * *
            if month == "*" and dow == "*":
                try:
                    d = int(dom)
                    suffix = "th"
                    if d in (1, 21, 31):
                        suffix = "st"
                    elif d in (2, 22):
                        suffix = "nd"
                    elif d in (3, 23):
                        suffix = "rd"
                    return f"Monthly on the {d}{suffix}"
                except (ValueError, TypeError):
                    pass

        return self.schedule

    # =========================================================================
    # Function to_dict -> None to Dict[str, Any]
    # =========================================================================
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    # =========================================================================
    # Function from_dict -> Dict[str, Any] to ScheduledTask
    # =========================================================================
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        """Create ScheduledTask from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
'''
    ExecutionLog : Record of a task execution
'''
# =============================================================================
@dataclass
class ExecutionLog:
    """Record of a task execution"""
    task_id: str
    task_name: str
    timestamp: str
    success: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    # =========================================================================
    # Function to_dict -> None to Dict[str, Any]
    # =========================================================================
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


# =============================================================================
'''
    SchedulerManager : Main scheduler class that manages task scheduling,
                       execution, and persistence using APScheduler
'''
# =============================================================================
class SchedulerManager:
    """
    Manages scheduled tasks using APScheduler.

    Features:
    - Cron-based task scheduling
    - Persistent task storage (JSON)
    - Execution logging (JSONL)
    - Send messages or execute skills
    - Multi-channel support
    """

    # =========================================================================
    # Function __init__ -> MessageRouter, Path to None
    # =========================================================================
    def __init__(
        self,
        router: "MessageRouter",
        data_dir: Path,
        channel_handlers: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialize scheduler manager.

        Args:
            router: Message router for executing tasks
            data_dir: Directory for storing task data
            channel_handlers: Dict mapping channel names to send functions
        """
        self.router = router
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.tasks_file = self.data_dir / "tasks.json"
        self.log_file = self.data_dir / "execution_log.jsonl"

        self.channel_handlers: Dict[str, Callable] = channel_handlers or {}
        self.tasks: Dict[str, ScheduledTask] = {}

        # Initialize APScheduler
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False
        self._running_tasks: set = set()  # Track currently executing task IDs

        # Retry backoff delays in seconds: 30s, 1m, 5m, 15m, 60m
        self.RETRY_BACKOFF = [30, 60, 300, 900, 3600]

        # Load existing tasks
        self._load_tasks()

        logger.info(f"SchedulerManager initialized with {len(self.tasks)} tasks")

    # =========================================================================
    # Function register_channel_handler -> str, Callable to None
    # =========================================================================
    def register_channel_handler(self, channel: str, handler: Callable):
        """
        Register a send message handler for a channel.

        Args:
            channel: Channel name (telegram, discord, slack)
            handler: Async function(user_id, message, chat_id=None) -> bool
        """
        self.channel_handlers[channel] = handler
        logger.info(f"Registered handler for channel: {channel}")

    # =========================================================================
    # Function start -> None to None
    # =========================================================================
    async def start(self):
        """Start the scheduler"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        # Schedule all enabled tasks
        for task in self.tasks.values():
            if task.enabled:
                self._schedule_task(task)

        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    # =========================================================================
    # Function stop -> None to None
    # =========================================================================
    async def stop(self):
        """Stop the scheduler gracefully"""
        if not self._running:
            return

        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Scheduler stopped")

    # =========================================================================
    # Function add_task -> ScheduledTask to str
    # =========================================================================
    async def add_task(self, task: ScheduledTask) -> str:
        """
        Add a new scheduled task.

        Args:
            task: Task configuration

        Returns:
            Task ID
        """
        # Validate trigger based on schedule_kind
        if task.schedule_kind == "cron":
            try:
                CronTrigger.from_crontab(task.schedule, timezone=task.timezone)
            except ValueError as e:
                raise ValueError(f"Invalid cron expression: {e}")
        elif task.schedule_kind == "every":
            if task.interval_seconds <= 0:
                raise ValueError("Interval must be a positive number of seconds")
        elif task.schedule_kind == "at":
            if not task.run_at:
                raise ValueError("run_at datetime is required for one-shot tasks")
            try:
                datetime.fromisoformat(task.run_at)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid run_at datetime: {e}")
        else:
            raise ValueError(f"Unknown schedule_kind: {task.schedule_kind}")

        # Ensure unique ID
        if task.id in self.tasks:
            task.id = f"task-{uuid.uuid4().hex[:8]}"

        task.updated_at = datetime.now(tz=timezone.utc).isoformat()
        self.tasks[task.id] = task

        # Schedule if enabled
        if task.enabled and self._running:
            self._schedule_task(task)

        self._save_tasks()
        logger.info(f"Added task: {task.name} ({task.id})")

        return task.id

    # =========================================================================
    # Function remove_task -> str to bool
    # =========================================================================
    async def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task ID to remove

        Returns:
            True if removed
        """
        if task_id not in self.tasks:
            return False

        # Remove from scheduler
        try:
            self.scheduler.remove_job(task_id)
        except JobLookupError:
            pass  # Job might not be scheduled

        # Remove from tasks
        task = self.tasks.pop(task_id)
        self._save_tasks()

        logger.info(f"Removed task: {task.name} ({task_id})")
        return True

    # =========================================================================
    # Function update_task -> str, dict to bool
    # =========================================================================
    async def update_task(self, task_id: str, updates: dict) -> bool:
        """
        Update a scheduled task.

        Args:
            task_id: Task ID to update
            updates: Dictionary of fields to update

        Returns:
            True if updated
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        # Validate schedule if updating
        kind = updates.get("schedule_kind", task.schedule_kind)
        if "schedule" in updates and kind == "cron":
            try:
                tz = updates.get("timezone", task.timezone)
                CronTrigger.from_crontab(updates["schedule"], timezone=tz)
            except ValueError as e:
                raise ValueError(f"Invalid cron expression: {e}")
        if "interval_seconds" in updates and kind == "every":
            if updates["interval_seconds"] <= 0:
                raise ValueError("Interval must be a positive number of seconds")

        # Apply updates
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now(tz=timezone.utc).isoformat()

        # Reschedule if running
        if self._running:
            try:
                self.scheduler.remove_job(task_id)
            except JobLookupError:
                pass

            if task.enabled:
                self._schedule_task(task)

        self._save_tasks()
        logger.info(f"Updated task: {task.name} ({task_id})")

        return True

    # =========================================================================
    # Function pause_task -> str to bool
    # =========================================================================
    async def pause_task(self, task_id: str) -> bool:
        """
        Pause a scheduled task.

        Args:
            task_id: Task ID to pause

        Returns:
            True if paused
        """
        return await self.update_task(task_id, {"enabled": False})

    # =========================================================================
    # Function resume_task -> str to bool
    # =========================================================================
    async def resume_task(self, task_id: str) -> bool:
        """
        Resume a paused task.

        Args:
            task_id: Task ID to resume

        Returns:
            True if resumed
        """
        return await self.update_task(task_id, {"enabled": True})

    # =========================================================================
    # Function list_tasks -> None to List[Dict[str, Any]]
    # =========================================================================
    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        List all tasks with their next run time.

        Returns:
            List of task dictionaries with status info
        """
        result = []

        for task in self.tasks.values():
            task_dict = task.to_dict()

            # Get next run time from scheduler
            job = self.scheduler.get_job(task.id)
            if job and getattr(job, 'next_run_time', None):
                task_dict["next_run"] = job.next_run_time.isoformat()
            else:
                task_dict["next_run"] = None

            task_dict["status"] = "active" if task.enabled else "paused"
            task_dict["human_schedule"] = task.get_human_schedule()
            result.append(task_dict)

        return result

    # =========================================================================
    # Function get_task -> str to Optional[ScheduledTask]
    # =========================================================================
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID"""
        return self.tasks.get(task_id)

    # =========================================================================
    # Function get_execution_log -> int to List[Dict[str, Any]]
    # =========================================================================
    def get_execution_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent execution log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of execution log entries (most recent first)
        """
        if not self.log_file.exists():
            return []

        logs = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading execution log: {e}")
            return []

        # Return most recent first
        return list(reversed(logs[-limit:]))

    # =========================================================================
    # Function _schedule_task -> ScheduledTask to None
    # =========================================================================
    def _schedule_task(self, task: ScheduledTask):
        """
        Schedule a task with APScheduler using the appropriate trigger.

        Args:
            task: Task to schedule
        """
        try:
            if task.schedule_kind == "every":
                trigger = IntervalTrigger(seconds=task.interval_seconds)
            elif task.schedule_kind == "at":
                # Skip expired one-shot tasks instead of firing them late
                try:
                    run_dt = datetime.fromisoformat(task.run_at)
                    if run_dt.tzinfo is None:
                        run_dt = run_dt.replace(tzinfo=timezone.utc)
                    if run_dt < datetime.now(tz=timezone.utc):
                        logger.info(
                            f"Skipping expired one-shot task '{task.name}' "
                            f"(was scheduled for {task.run_at})"
                        )
                        if task.delete_after_run:
                            task.enabled = False
                            self._save_tasks()
                        return
                except (ValueError, TypeError):
                    pass
                trigger = DateTrigger(
                    run_date=datetime.fromisoformat(task.run_at),
                    timezone=task.timezone,
                )
            else:  # "cron" (default)
                trigger = CronTrigger.from_crontab(task.schedule, timezone=task.timezone)

            self.scheduler.add_job(
                func=self._execute_task,
                trigger=trigger,
                id=task.id,
                name=task.name,
                args=[task],
                replace_existing=True,
            )

            job = self.scheduler.get_job(task.id)
            if job and getattr(job, 'next_run_time', None):
                logger.info(f"Scheduled task '{task.name}' ({task.schedule_kind}) - next run: {job.next_run_time}")

        except Exception as e:
            logger.error(f"Failed to schedule task '{task.name}': {e}")

    # =========================================================================
    # Function _execute_task -> ScheduledTask to None
    # =========================================================================
    async def _execute_task(self, task: ScheduledTask, is_retry: bool = False):
        """
        Execute a scheduled task with concurrency control and retry backoff.

        Args:
            task: Task to execute
            is_retry: Whether this is a retry attempt
        """
        # Concurrency control — skip if max concurrent reached
        running_count = sum(1 for t in self._running_tasks if t == task.id)
        if running_count >= task.max_concurrent:
            logger.warning(f"Skipping task '{task.name}' — max concurrent ({task.max_concurrent}) reached")
            return

        self._running_tasks.add(task.id)
        logger.info(f"Executing task: {task.name} ({task.id}){' [retry]' if is_retry else ''}")

        success = False
        error = None
        details = {}

        try:
            if task.action == "send_message":
                success = await self._execute_send_message(task)
                details["action"] = "send_message"
                details["channel"] = task.target_channel
                details["user"] = task.target_user

            elif task.action == "execute_skill":
                success = await self._execute_skill(task)
                details["action"] = "execute_skill"
                details["skill"] = task.skill_name
                details["channel"] = task.target_channel

            else:
                error = f"Unknown action: {task.action}"

        except Exception as e:
            error = str(e)
            logger.error(f"Task execution error: {e}", exc_info=True)

        finally:
            self._running_tasks.discard(task.id)

        # Log execution
        self._log_execution(task.id, task.name, success, error, details)

        # Handle success
        if success:
            task.retry_count = 0
            task.last_error = ""

            # Auto-delete one-shot tasks after success
            if task.delete_after_run and task.schedule_kind == "at":
                logger.info(f"Auto-deleting one-shot task '{task.name}' after success")
                await self.remove_task(task.id)
                return

            self._save_tasks()
            return

        # Handle failure — retry logic (not for one-shot tasks)
        task.last_error = error or "Unknown error"
        if task.schedule_kind != "at" and task.retry_count < task.max_retries:
            task.retry_count += 1
            backoff_idx = min(task.retry_count - 1, len(self.RETRY_BACKOFF) - 1)
            delay_seconds = self.RETRY_BACKOFF[backoff_idx]

            retry_time = datetime.now(tz=timezone.utc).timestamp() + delay_seconds
            retry_dt = datetime.fromtimestamp(retry_time, tz=timezone.utc)
            retry_job_id = f"{task.id}-retry-{task.retry_count}"

            logger.info(f"Scheduling retry {task.retry_count}/{task.max_retries} "
                        f"for '{task.name}' in {delay_seconds}s")

            try:
                self.scheduler.add_job(
                    func=self._execute_task,
                    trigger=DateTrigger(run_date=retry_dt),
                    id=retry_job_id,
                    name=f"{task.name} (retry {task.retry_count})",
                    args=[task, True],
                    replace_existing=True,
                )
            except Exception as e:
                logger.error(f"Failed to schedule retry for '{task.name}': {e}")
        elif task.retry_count >= task.max_retries:
            logger.warning(f"Task '{task.name}' exceeded max retries ({task.max_retries})")

        self._save_tasks()

    # =========================================================================
    # Function _execute_send_message -> ScheduledTask to bool
    # =========================================================================
    async def _execute_send_message(self, task: ScheduledTask) -> bool:
        """
        Execute send_message action.

        Args:
            task: Task with message details

        Returns:
            True if successful
        """
        if not task.message:
            raise ValueError("No message specified for send_message action")

        if not task.target_user:
            raise ValueError("No target user specified")

        handler = self.channel_handlers.get(task.target_channel)
        if not handler:
            raise ValueError(f"No handler registered for channel: {task.target_channel}")

        # Call the channel handler
        return await handler(
            user_id=task.target_user,
            message=task.message,
            chat_id=task.target_chat,
        )

    # =========================================================================
    # Function _execute_skill -> ScheduledTask to bool
    # =========================================================================
    async def _execute_skill(self, task: ScheduledTask) -> bool:
        """
        Execute skill action via the router.

        Args:
            task: Task with skill details

        Returns:
            True if successful
        """
        if not task.skill_name:
            raise ValueError("No skill name specified for execute_skill action")

        if not task.target_user:
            raise ValueError("No target user specified")

        # Build the skill invocation message
        skill_message = f"/{task.skill_name}"
        if task.skill_params:
            skill_message += f" {task.skill_params}"

        # Execute via router
        response = await self.router.handle_message(
            channel=task.target_channel,
            user_id=task.target_user,
            user_message=skill_message,
            chat_id=task.target_chat,
            user_name="Scheduler",
        )

        # Send response to user if we have a handler
        if response and task.target_channel in self.channel_handlers:
            handler = self.channel_handlers[task.target_channel]
            await handler(
                user_id=task.target_user,
                message=response,
                chat_id=task.target_chat,
            )

        return True

    # =========================================================================
    # Function _log_execution -> str, str, bool, Optional[str], Optional[Dict] to None
    # =========================================================================
    def _log_execution(
        self,
        task_id: str,
        task_name: str,
        success: bool,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log task execution to JSONL file.

        Args:
            task_id: Task ID
            task_name: Task name
            success: Whether execution succeeded
            error: Error message if failed
            details: Additional execution details
        """
        log_entry = ExecutionLog(
            task_id=task_id,
            task_name=task_name,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            success=success,
            error=error,
            details=details,
        )

        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to write execution log: {e}")

        if success:
            logger.info(f"Task '{task_name}' executed successfully")
        else:
            logger.warning(f"Task '{task_name}' failed: {error}")

    # =========================================================================
    # Function _load_tasks -> None to None
    # =========================================================================
    def _load_tasks(self):
        """Load tasks from JSON file"""
        if not self.tasks_file.exists():
            self.tasks = {}
            return

        try:
            with open(self.tasks_file, 'r') as f:
                data = json.load(f)

            self.tasks = {
                task_data["id"]: ScheduledTask.from_dict(task_data)
                for task_data in data.get("tasks", [])
            }

            logger.info(f"Loaded {len(self.tasks)} tasks from {self.tasks_file}")

        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
            self.tasks = {}

    # =========================================================================
    # Function _save_tasks -> None to None
    # =========================================================================
    def _save_tasks(self):
        """Save tasks to JSON file"""
        try:
            data = {
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            }

            with open(self.tasks_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self.tasks)} tasks to {self.tasks_file}")

        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")

    # =========================================================================
    # Function get_status -> None to Dict[str, Any]
    # =========================================================================
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status.

        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "task_count": len(self.tasks),
            "active_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "paused_tasks": sum(1 for t in self.tasks.values() if not t.enabled),
            "registered_channels": list(self.channel_handlers.keys()),
        }


# =============================================================================
# Factory Function
# =============================================================================

# =========================================================================
# Function create_scheduler_manager -> MessageRouter, str to SchedulerManager
# =========================================================================
def create_scheduler_manager(
    router: "MessageRouter",
    data_dir: str = "data/scheduler",
) -> SchedulerManager:
    """
    Create a configured SchedulerManager instance.

    Args:
        router: Message router for executing tasks
        data_dir: Directory for storing task data

    Returns:
        Configured SchedulerManager
    """
    return SchedulerManager(
        router=router,
        data_dir=Path(data_dir),
    )


# =============================================================================
# Standalone Test Section
# =============================================================================
if __name__ == "__main__":
    import asyncio

    async def main():
        """Test scheduler functionality"""
        print("Scheduler Test")
        print("=" * 40)

        # Create a mock router
        class MockRouter:
            async def handle_message(self, **kwargs):
                print(f"Mock message: {kwargs}")
                return "Mock response"

        # Create scheduler
        scheduler = create_scheduler_manager(
            router=MockRouter(),
            data_dir="data/scheduler_test",
        )

        # Register a test handler
        async def test_handler(user_id, message, chat_id=None):
            print(f"Sending to {user_id}: {message}")
            return True

        scheduler.register_channel_handler("test", test_handler)

        # Add a test task
        task = ScheduledTask(
            name="Test Task",
            description="A test scheduled task",
            schedule="* * * * *",  # Every minute
            action="send_message",
            target_channel="test",
            target_user="user-123",
            message="Hello from scheduler!",
        )

        await scheduler.add_task(task)

        # Start scheduler
        await scheduler.start()

        print("\nScheduler status:", scheduler.get_status())
        print("\nTasks:", scheduler.list_tasks())

        # Run for a bit
        print("\nWaiting for task execution (press Ctrl+C to stop)...")
        try:
            while True:
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            print("\nStopping...")

        await scheduler.stop()

    asyncio.run(main())


# =============================================================================
'''
    End of File : scheduler.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
