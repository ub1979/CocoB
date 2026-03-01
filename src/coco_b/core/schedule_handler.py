# =============================================================================
'''
    File Name : schedule_handler.py

    Description : Handler for parsing and executing schedule commands from
                  LLM responses. Integrates with the SchedulerManager to
                  create, list, pause, resume, and delete scheduled tasks.

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
import re
import logging
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.core.scheduler import SchedulerManager

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("schedule_handler")


# =============================================================================
'''
    ScheduleCommandHandler : Parses and executes schedule commands from
                             LLM responses in ```schedule``` code blocks.
'''
# =============================================================================
class ScheduleCommandHandler:
    """
    Handles schedule commands embedded in LLM responses.

    Parses code blocks like:
    ```schedule
    ACTION: create
    NAME: Daily Reminder
    SCHEDULE: 0 9 * * *
    MESSAGE: Good morning!
    ```
    """

    # Pattern to find schedule code blocks
    SCHEDULE_BLOCK_PATTERN = re.compile(
        r'```schedule\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> Optional[SchedulerManager] to None
    # =========================================================================
    def __init__(self, scheduler_manager: Optional["SchedulerManager"] = None):
        """
        Initialize the schedule command handler.

        Args:
            scheduler_manager: The scheduler manager to execute commands
        """
        self.scheduler_manager = scheduler_manager

    # =========================================================================
    # Function set_scheduler_manager -> SchedulerManager to None
    # =========================================================================
    def set_scheduler_manager(self, scheduler_manager: "SchedulerManager"):
        """Set or update the scheduler manager"""
        self.scheduler_manager = scheduler_manager

    # =========================================================================
    # Function has_schedule_commands -> str to bool
    # =========================================================================
    def has_schedule_commands(self, response: str) -> bool:
        """
        Check if response contains schedule commands.

        Args:
            response: LLM response text

        Returns:
            True if schedule commands found
        """
        return bool(self.SCHEDULE_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_schedule_block -> str to Dict[str, str]
    # =========================================================================
    def parse_schedule_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse a schedule block into key-value pairs.

        Args:
            block_content: Content inside ```schedule``` block

        Returns:
            Dictionary of parsed values
        """
        result = {}
        current_key = None
        current_value = []

        for line in block_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Check for KEY: VALUE pattern
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().upper()
                value = parts[1].strip() if len(parts) > 1 else ""

                # Common keys we expect
                if key in ['ACTION', 'NAME', 'SCHEDULE', 'MESSAGE', 'TASK_ID',
                          'SKILL', 'PARAMS', 'CHANNEL', 'TIMEZONE',
                          'KIND', 'INTERVAL', 'RUN_AT', 'DELETE_AFTER']:
                    # Save previous key if exists
                    if current_key:
                        result[current_key] = '\n'.join(current_value).strip()

                    current_key = key
                    current_value = [value] if value else []
                else:
                    # Continuation of previous value
                    if current_key:
                        current_value.append(line)
            else:
                # Continuation of previous value
                if current_key:
                    current_value.append(line)

        # Save last key
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()

        return result

    # =========================================================================
    # Function extract_commands -> str to list
    # =========================================================================
    def extract_commands(self, response: str) -> list:
        """
        Extract all schedule commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.SCHEDULE_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_schedule_block(match)
            if parsed.get('ACTION'):
                commands.append(parsed)

        return commands

    # =========================================================================
    # Function execute_commands -> str, str, str, Optional[str] to Tuple[str, list]
    # =========================================================================
    async def execute_commands(
        self,
        response: str,
        channel: str,
        user_id: str,
        chat_id: Optional[str] = None,
    ) -> Tuple[str, list]:
        """
        Execute all schedule commands in response.

        Args:
            response: LLM response text
            channel: Channel name for task targeting
            user_id: User ID for task targeting
            chat_id: Optional chat ID

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        if not self.scheduler_manager:
            logger.warning("No scheduler manager available")
            return response, []

        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            # Normalize action — take only the first word (LLMs sometimes add extra text)
            raw_action = cmd.get('ACTION', '').strip()
            action = raw_action.split()[0].lower() if raw_action else ''
            result = None

            try:
                if action == 'create':
                    result = await self._handle_create(cmd, channel, user_id, chat_id)
                elif action == 'list':
                    result = await self._handle_list(user_id)
                elif action == 'pause':
                    result = await self._handle_pause(cmd)
                elif action == 'resume':
                    result = await self._handle_resume(cmd)
                elif action in ('delete', 'stop', 'cancel', 'remove'):
                    # Check for "delete all" / "stop all"
                    name = cmd.get('NAME', '').strip().lower()
                    rest = ' '.join(raw_action.split()[1:]).lower()
                    if name == 'all' or rest == 'all':
                        result = await self._handle_delete_all(user_id)
                    else:
                        result = await self._handle_delete(cmd)
                elif action in ('delete_all', 'stop_all', 'clear'):
                    result = await self._handle_delete_all(user_id)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Schedule command error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean schedule blocks from response for display
        cleaned = self.SCHEDULE_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_create -> Dict, str, str, Optional[str] to Dict
    # =========================================================================
    @staticmethod
    def _parse_interval(text: str) -> int:
        """
        Parse an interval string to seconds.

        Args:
            text: Interval like "30m", "2h", "60s", or bare number (seconds)

        Returns:
            Number of seconds
        """
        text = text.strip().lower()
        if text.endswith('h'):
            return int(text[:-1]) * 3600
        elif text.endswith('m'):
            return int(text[:-1]) * 60
        elif text.endswith('s'):
            return int(text[:-1])
        else:
            return int(text)

    async def _handle_create(
        self,
        cmd: Dict[str, str],
        channel: str,
        user_id: str,
        chat_id: Optional[str],
    ) -> Dict[str, Any]:
        """Handle create action"""
        from coco_b.core.scheduler import ScheduledTask

        name = cmd.get('NAME', 'Scheduled Task')
        schedule = cmd.get('SCHEDULE', '')
        message = cmd.get('MESSAGE', '')
        skill = cmd.get('SKILL', '')
        params = cmd.get('PARAMS', '')
        timezone_str = cmd.get('TIMEZONE', 'UTC')
        target_channel = cmd.get('CHANNEL', channel)
        kind = cmd.get('KIND', 'cron').lower()

        # Build trigger-specific fields
        interval_seconds = 0
        run_at = ""
        delete_after_run = False

        if kind == "every":
            interval_text = cmd.get('INTERVAL', '')
            if not interval_text:
                return {"success": False, "error": "No INTERVAL specified for 'every' task"}
            try:
                interval_seconds = self._parse_interval(interval_text)
            except (ValueError, TypeError):
                return {"success": False, "error": f"Invalid interval: {interval_text}"}
        elif kind == "at":
            run_at = cmd.get('RUN_AT', '')
            if not run_at:
                return {"success": False, "error": "No RUN_AT specified for one-shot task"}
            delete_after_str = cmd.get('DELETE_AFTER', 'true').lower()
            delete_after_run = delete_after_str not in ('false', '0', 'no')
        else:
            # cron — need SCHEDULE
            if not schedule:
                return {"success": False, "error": "No schedule specified"}

        if not message and not skill:
            return {"success": False, "error": "No message or skill specified"}

        # Determine action type
        action_type = "execute_skill" if skill else "send_message"

        task = ScheduledTask(
            name=name,
            description=f"Created via chat by user {user_id}",
            schedule=schedule,
            timezone=timezone_str,
            action=action_type,
            target_channel=target_channel,
            target_user=user_id,
            target_chat=chat_id,
            message=message if action_type == "send_message" else None,
            skill_name=skill if action_type == "execute_skill" else None,
            skill_params=params if action_type == "execute_skill" else None,
            schedule_kind=kind,
            interval_seconds=interval_seconds,
            run_at=run_at,
            delete_after_run=delete_after_run,
        )

        try:
            task_id = await self.scheduler_manager.add_task(task)
            # Build human-readable schedule info
            human = task.get_human_schedule()
            return {
                "success": True,
                "action": "create",
                "task_id": task_id,
                "name": name,
                "schedule": human,
                "schedule_kind": kind,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Function _handle_list -> str to Dict
    # =========================================================================
    async def _handle_list(self, user_id: str) -> Dict[str, Any]:
        """Handle list action"""
        tasks = self.scheduler_manager.list_tasks()

        # Filter to user's tasks, fall back to all enabled tasks
        user_tasks = [t for t in tasks if t.get('target_user') == user_id]
        if not user_tasks:
            user_tasks = [t for t in tasks if t.get('enabled', True)]

        return {
            "success": True,
            "action": "list",
            "tasks": user_tasks,
            "total": len(user_tasks),
        }

    # =========================================================================
    # Function _handle_pause -> Dict to Dict
    # =========================================================================
    async def _handle_pause(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle pause action"""
        task_id = cmd.get('TASK_ID', '')
        if not task_id:
            return {"success": False, "error": "No task ID specified"}

        success = await self.scheduler_manager.pause_task(task_id)
        return {
            "success": success,
            "action": "pause",
            "task_id": task_id,
            "error": None if success else "Task not found",
        }

    # =========================================================================
    # Function _handle_resume -> Dict to Dict
    # =========================================================================
    async def _handle_resume(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle resume action"""
        task_id = cmd.get('TASK_ID', '')
        if not task_id:
            return {"success": False, "error": "No task ID specified"}

        success = await self.scheduler_manager.resume_task(task_id)
        return {
            "success": success,
            "action": "resume",
            "task_id": task_id,
            "error": None if success else "Task not found",
        }

    # =========================================================================
    # Function _handle_delete -> Dict to Dict
    # =========================================================================
    async def _handle_delete(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle delete action — supports TASK_ID or NAME lookup.
        Deletes ALL tasks matching the name (not just the first)."""
        task_id = cmd.get('TASK_ID', '')

        # If explicit task ID, delete just that one
        if task_id:
            success = await self.scheduler_manager.remove_task(task_id)
            return {
                "success": success,
                "action": "delete",
                "task_id": task_id,
                "error": None if success else "Task not found",
            }

        # Search by name — delete ALL matching tasks
        name = cmd.get('NAME', '')
        if not name:
            return {"success": False, "error": "No task found. Provide TASK_ID or NAME."}

        matching_ids = [
            tid for tid, task in self.scheduler_manager.tasks.items()
            if name.lower() in task.name.lower()
        ]

        if not matching_ids:
            return {"success": False, "error": f"No task matching '{name}' found."}

        deleted = []
        for tid in matching_ids:
            if await self.scheduler_manager.remove_task(tid):
                deleted.append(tid)

        return {
            "success": len(deleted) > 0,
            "action": "delete",
            "task_id": ", ".join(deleted),
            "error": None if deleted else "Failed to delete tasks",
        }

    # =========================================================================
    # Function _handle_delete_all -> str to Dict
    # =========================================================================
    async def _handle_delete_all(self, user_id: str) -> Dict[str, Any]:
        """Delete all tasks for a user (or all tasks if no user match)."""
        deleted = []
        # Collect task IDs first to avoid modifying dict during iteration
        task_ids = list(self.scheduler_manager.tasks.keys())

        for tid in task_ids:
            task = self.scheduler_manager.tasks.get(tid)
            if not task:
                continue
            # Delete tasks belonging to this user, or all if no user filter
            if task.target_user == user_id or not user_id:
                success = await self.scheduler_manager.remove_task(tid)
                if success:
                    deleted.append(tid)

        # If no user-specific tasks found, delete all enabled tasks
        if not deleted:
            task_ids = list(self.scheduler_manager.tasks.keys())
            for tid in task_ids:
                success = await self.scheduler_manager.remove_task(tid)
                if success:
                    deleted.append(tid)

        return {
            "success": len(deleted) > 0,
            "action": "delete_all",
            "deleted_count": len(deleted),
            "error": None if deleted else "No tasks found to delete",
        }

    # =========================================================================
    # Function _format_results -> list to str
    # =========================================================================
    def _format_results(self, results: list) -> str:
        """Format execution results for display"""
        lines = []

        for result in results:
            action = result.get('action', 'unknown')
            success = result.get('success', False)

            if not success:
                error = result.get('error', 'Unknown error')
                lines.append(f"**Error**: {error}")
                continue

            if action == 'create':
                task_id = result.get('task_id', '')
                name = result.get('name', '')
                schedule = result.get('schedule', '')
                kind = result.get('schedule_kind', 'cron')
                lines.append(f"**Task Created**: {name}")
                lines.append(f"- ID: `{task_id}`")
                lines.append(f"- Schedule: {schedule}")
                if kind != "cron":
                    lines.append(f"- Type: {kind}")

            elif action == 'list':
                tasks = result.get('tasks', [])
                if not tasks:
                    lines.append("**No scheduled tasks found.**")
                else:
                    lines.append(f"**Your Scheduled Tasks** ({len(tasks)} total):")
                    for t in tasks:
                        status = "Active" if t.get('enabled', True) else "Paused"
                        next_run = t.get('next_run', 'N/A')
                        human = t.get('human_schedule', t.get('schedule', ''))
                        lines.append(f"- **{t.get('name')}** (`{t.get('id')}`)")
                        lines.append(f"  Schedule: {human} | Status: {status}")
                        if next_run and next_run != 'N/A':
                            lines.append(f"  Next run: {next_run}")

            elif action == 'pause':
                task_id = result.get('task_id', '')
                lines.append(f"**Task Paused**: `{task_id}`")

            elif action == 'resume':
                task_id = result.get('task_id', '')
                lines.append(f"**Task Resumed**: `{task_id}`")

            elif action == 'delete':
                task_id = result.get('task_id', '')
                lines.append(f"**Task Deleted**: `{task_id}`")

            elif action == 'delete_all':
                count = result.get('deleted_count', 0)
                lines.append(f"**All reminders stopped** ({count} tasks deleted)")

        return '\n'.join(lines)


# =============================================================================
# Convenience function
# =============================================================================

def create_schedule_handler(
    scheduler_manager: Optional["SchedulerManager"] = None,
) -> ScheduleCommandHandler:
    """Create a schedule command handler"""
    return ScheduleCommandHandler(scheduler_manager)


# =============================================================================
'''
    End of File : schedule_handler.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
