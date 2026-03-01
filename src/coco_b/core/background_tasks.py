# =============================================================================
'''
    File Name : background_tasks.py
    
    Description : Background task runner for periodic operations.
                  Runs tasks like health monitors, data sync, and checks
                  with YELLOW level authentication (PIN required).
    
    Security Levels:
        - YELLOW: Creating/modifying tasks requires PIN (30min session)
        - GREEN: Viewing task status requires no auth
    
    Task Types:
        - health_monitor: Check service health
        - data_sync: Sync data with external services
        - periodic_check: Run periodic checks
        - scheduled_job: Run at scheduled times
    
    Created on 2026-02-21
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : coco B - Persistent Memory AI Chatbot
    
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
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from coco_b.core.auth_manager import AuthManager, SecurityLevel

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("background_tasks")


# =============================================================================
'''
    TaskStatus : Status of a background task
'''
# =============================================================================
class TaskStatus(Enum):
    """Status of a background task"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# =============================================================================
'''
    TaskType : Types of background tasks
'''
# =============================================================================
class TaskType:
    """Types of background tasks"""
    
    HEALTH_MONITOR = "health_monitor"
    DATA_SYNC = "data_sync"
    PERIODIC_CHECK = "periodic_check"
    SCHEDULED_JOB = "scheduled_job"
    
    ALL_TYPES = [HEALTH_MONITOR, DATA_SYNC, PERIODIC_CHECK, SCHEDULED_JOB]


# =============================================================================
'''
    BackgroundTask : Definition of a background task
'''
# =============================================================================
@dataclass
class BackgroundTask:
    """Definition of a background task"""
    task_id: str
    task_type: str
    name: str
    description: str
    
    # Scheduling
    interval_minutes: Optional[int] = None  # For periodic tasks
    schedule_time: Optional[str] = None  # HH:MM for scheduled jobs
    
    # Task configuration
    command: Optional[str] = None  # Command to execute
    function_name: Optional[str] = None  # Function to call
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Status tracking
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    last_error: Optional[str] = None
    
    # Security
    required_auth_level: str = "YELLOW"  # GREEN, YELLOW, ORANGE, RED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackgroundTask":
        """Create from dictionary"""
        known_fields = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)
    
    @property
    def is_active(self) -> bool:
        """Whether task is active and should run"""
        return self.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]
    
    @property
    def is_due(self) -> bool:
        """Whether task is due to run"""
        if not self.is_active:
            return False
        
        now = datetime.now()
        
        # Check interval-based
        if self.interval_minutes:
            if not self.last_run:
                return True
            last = datetime.fromisoformat(self.last_run)
            minutes_since = (now - last).total_seconds() / 60
            return minutes_since >= self.interval_minutes
        
        # Check schedule-based
        if self.schedule_time:
            current_time = now.strftime("%H:%M")
            if current_time == self.schedule_time:
                # Check if already ran today
                if self.last_run:
                    last = datetime.fromisoformat(self.last_run)
                    if last.date() == now.date():
                        return False
                return True
        
        return False


# =============================================================================
'''
    TaskResult : Result of a task execution
'''
# =============================================================================
@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


# =============================================================================
'''
    BackgroundTaskRunner : Manages and executes background tasks
    
    Features:
        - Schedule tasks by interval or time
        - Track task execution and results
        - YELLOW auth level for task management
        - Concurrent task execution with limits
'''
# =============================================================================
class BackgroundTaskRunner:
    """
    Manages and executes background tasks.
    Task management requires YELLOW level (PIN).
    """
    
    # Maximum concurrent tasks
    MAX_CONCURRENT = 5
    
    def __init__(self, data_dir: Optional[Path] = None,
                 auth_manager: Optional["AuthManager"] = None):
        """
        Initialize background task runner.
        
        Args:
            data_dir: Directory to store task definitions
            auth_manager: AuthManager for security checks
        """
        # ==================================
        # Setup data directory
        # ==================================
        if data_dir is None:
            from coco_b import PROJECT_ROOT
            self._data_dir = Path(PROJECT_ROOT) / "data" / "tasks"
        else:
            self._data_dir = Path(data_dir)
        
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # ==================================
        # Auth manager for security
        # ==================================
        self._auth_manager = auth_manager
        
        # ==================================
        # Task storage
        # ==================================
        self._tasks: Dict[str, BackgroundTask] = {}
        self._results: Dict[str, List[TaskResult]] = {}
        
        # ==================================
        # Execution state
        # ==================================
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._task_handlers: Dict[str, Callable] = {}
        
        # ==================================
        # Load existing tasks
        # ==================================
        self._load_tasks()
    
    # =========================================================================
    # Data Persistence
    # =========================================================================
    
    def _get_tasks_file(self) -> Path:
        """Get tasks storage file"""
        return self._data_dir / "tasks.json"
    
    def _get_results_file(self) -> Path:
        """Get results storage file"""
        return self._data_dir / "results.json"
    
    def _load_tasks(self):
        """Load tasks from disk"""
        tasks_file = self._get_tasks_file()
        if tasks_file.exists():
            try:
                with open(tasks_file, 'r') as f:
                    data = json.load(f)
                
                for task_id, task_data in data.items():
                    self._tasks[task_id] = BackgroundTask.from_dict(task_data)
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load tasks: {e}")
        
        # Load results
        results_file = self._get_results_file()
        if results_file.exists():
            try:
                with open(results_file, 'r') as f:
                    self._results = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load results: {e}")
    
    def _save_tasks(self):
        """Save tasks to disk"""
        tasks_file = self._get_tasks_file()
        try:
            data = {tid: task.to_dict() for tid, task in self._tasks.items()}
            with open(tasks_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save tasks: {e}")
    
    def _save_results(self):
        """Save results to disk"""
        results_file = self._get_results_file()
        try:
            # Limit results per task to prevent file bloat
            limited_results = {
                tid: results[-50:] if len(results) > 50 else results
                for tid, results in self._results.items()
            }
            with open(results_file, 'w') as f:
                json.dump(limited_results, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save results: {e}")
    
    # =========================================================================
    # Task Registration
    # =========================================================================
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """
        Register a handler function for a task type.
        
        Args:
            task_type: Type of task this handler handles
            handler: Async function to execute task
        """
        self._task_handlers[task_type] = handler
        logger.info(f"Registered handler for {task_type}")
    
    # =========================================================================
    # Task Management (YELLOW level)
    # =========================================================================
    
    def create_task(self, user_id: str, task_type: str, name: str,
                   description: str,
                   interval_minutes: Optional[int] = None,
                   schedule_time: Optional[str] = None,
                   command: Optional[str] = None,
                   parameters: Optional[Dict[str, Any]] = None,
                   required_auth_level: str = "YELLOW") -> Optional[BackgroundTask]:
        """
        Create a new background task.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User creating the task
            task_type: Type of task
            name: Task name
            description: Task description
            interval_minutes: Run interval for periodic tasks
            schedule_time: HH:MM for scheduled tasks
            command: Command to execute
            parameters: Task parameters
            required_auth_level: Minimum auth level required
            
        Returns:
            Created task or None if not authorized
        """
        # Check authorization
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                logger.warning(f"User {user_id} not authorized to create tasks")
                return None
        
        # Validate task type
        if task_type not in TaskType.ALL_TYPES:
            logger.error(f"Invalid task type: {task_type}")
            return None
        
        # Create task
        task = BackgroundTask(
            task_id=str(uuid.uuid4())[:8],
            task_type=task_type,
            name=name,
            description=description,
            interval_minutes=interval_minutes,
            schedule_time=schedule_time,
            command=command,
            parameters=parameters or {},
            required_auth_level=required_auth_level,
            status=TaskStatus.PENDING.value
        )
        
        self._tasks[task.task_id] = task
        self._save_tasks()
        
        logger.info(f"Created task {task.task_id}: {name}")
        return task
    
    def update_task(self, user_id: str, task_id: str, 
                   **updates) -> Optional[BackgroundTask]:
        """
        Update an existing task.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User updating the task
            task_id: Task to update
            **updates: Fields to update
            
        Returns:
            Updated task or None
        """
        # Check authorization
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return None
        
        if task_id not in self._tasks:
            return None
        
        task = self._tasks[task_id]
        
        # Update allowed fields
        allowed_fields = ['name', 'description', 'interval_minutes', 
                         'schedule_time', 'command', 'parameters']
        for field, value in updates.items():
            if field in allowed_fields and hasattr(task, field):
                setattr(task, field, value)
        
        self._save_tasks()
        logger.info(f"Updated task {task_id}")
        return task
    
    def delete_task(self, user_id: str, task_id: str) -> bool:
        """
        Delete a task.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User deleting the task
            task_id: Task to delete
            
        Returns:
            True if deleted
        """
        # Check authorization
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False
        
        if task_id not in self._tasks:
            return False
        
        del self._tasks[task_id]
        if task_id in self._results:
            del self._results[task_id]
        
        self._save_tasks()
        self._save_results()
        
        logger.info(f"Deleted task {task_id}")
        return True
    
    def pause_task(self, user_id: str, task_id: str) -> bool:
        """
        Pause a task.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User pausing the task
            task_id: Task to pause
            
        Returns:
            True if paused
        """
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False
        
        if task_id not in self._tasks:
            return False
        
        self._tasks[task_id].status = TaskStatus.PAUSED.value
        self._save_tasks()
        
        logger.info(f"Paused task {task_id}")
        return True
    
    def resume_task(self, user_id: str, task_id: str) -> bool:
        """
        Resume a paused task.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User resuming the task
            task_id: Task to resume
            
        Returns:
            True if resumed
        """
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False
        
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        if task.status == TaskStatus.PAUSED.value:
            task.status = TaskStatus.PENDING.value
            self._save_tasks()
            logger.info(f"Resumed task {task_id}")
            return True
        return False
    
    # =========================================================================
    # Task Queries (GREEN level - no auth required)
    # =========================================================================
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """
        Get a task by ID.
        GREEN level - no authentication required.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None
        """
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[BackgroundTask]:
        """
        Get all tasks.
        GREEN level - no authentication required.
        
        Returns:
            List of all tasks
        """
        return list(self._tasks.values())
    
    def get_active_tasks(self) -> List[BackgroundTask]:
        """
        Get all active tasks.
        GREEN level - no authentication required.
        
        Returns:
            List of active tasks
        """
        return [t for t in self._tasks.values() if t.is_active]
    
    def get_task_results(self, task_id: str, limit: int = 10) -> List[Dict]:
        """
        Get execution results for a task.
        GREEN level - no authentication required.
        
        Args:
            task_id: Task ID
            limit: Maximum results to return
            
        Returns:
            List of task results
        """
        results = self._results.get(task_id, [])
        return results[-limit:] if results else []
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get runner status.
        GREEN level - no authentication required.
        
        Returns:
            Status information
        """
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "active_tasks": len(self.get_active_tasks()),
            "task_types": {
                ttype: len([t for t in self._tasks.values() if t.task_type == ttype])
                for ttype in TaskType.ALL_TYPES
            }
        }
    
    # =========================================================================
    # Task Execution
    # =========================================================================
    
    async def start(self):
        """Start the task scheduler"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Background task runner started")
    
    async def stop(self):
        """Stop the task scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Background task runner stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                await self._check_and_run_tasks()
                # Check every 30 seconds
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(30)
    
    async def _check_and_run_tasks(self):
        """Check for due tasks and run them"""
        for task in self._tasks.values():
            if task.is_due:
                # Run task concurrently with semaphore limit
                asyncio.create_task(self._execute_task(task))
    
    async def _execute_task(self, task: BackgroundTask):
        """Execute a single task"""
        async with self._semaphore:
            start_time = datetime.now()
            task.status = TaskStatus.RUNNING.value
            task.last_run = start_time.isoformat()
            
            logger.info(f"Executing task {task.task_id}: {task.name}")
            
            try:
                # Execute task based on type
                if task.task_type in self._task_handlers:
                    handler = self._task_handlers[task.task_type]
                    result = await handler(task)
                    success = result is not False
                    output = str(result) if result else None
                elif task.command:
                    # Execute shell command
                    import subprocess
                    proc = await asyncio.create_subprocess_shell(
                        task.command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await proc.communicate()
                    success = proc.returncode == 0
                    output = stdout.decode() if stdout else None
                    error = stderr.decode() if stderr else None
                else:
                    success = False
                    output = None
                
                # Calculate duration
                duration = (datetime.now() - start_time).total_seconds()
                
                # Update task status
                task.status = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value
                task.run_count += 1
                if not success:
                    task.last_error = error if 'error' in dir() else "Task failed"
                
                # Record result
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=success,
                    output=output,
                    error=error if 'error' in dir() else None,
                    duration_seconds=duration
                )
                
                if task.task_id not in self._results:
                    self._results[task.task_id] = []
                self._results[task.task_id].append(task_result.__dict__)
                
                logger.info(f"Task {task.task_id} completed: success={success}")
                
            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {e}")
                task.status = TaskStatus.FAILED.value
                task.last_error = str(e)
                
                # Record failure
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(e)
                )
                if task.task_id not in self._results:
                    self._results[task.task_id] = []
                self._results[task.task_id].append(task_result.__dict__)
            
            finally:
                # Reset status for next run if periodic
                if task.interval_minutes and task.status != TaskStatus.PAUSED.value:
                    task.status = TaskStatus.PENDING.value
                
                self._save_tasks()
                self._save_results()
    
    async def run_task_now(self, user_id: str, task_id: str) -> bool:
        """
        Manually trigger a task to run now.
        Requires YELLOW level authentication.
        
        Args:
            user_id: User triggering the task
            task_id: Task to run
            
        Returns:
            True if task was triggered
        """
        # Check authorization
        if self._auth_manager:
            from coco_b.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False
        
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        asyncio.create_task(self._execute_task(task))
        return True


# =============================================================================
'''
    End of File : background_tasks.py
    
    Project : coco B - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
