# =============================================================================
'''
    File Name : todo_handler.py

    Description : Handler for parsing and executing todo commands from
                  LLM responses. Manages a persistent JSON-based todo list
                  with priorities, due dates, tags, and reminders.

    Created on 2026-02-20

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
import json
import uuid
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.core.scheduler import SchedulerManager

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("todo_handler")


# =============================================================================
'''
    TodoCommandHandler : Parses and executes todo commands from
                         LLM responses in ```todo``` code blocks.
'''
# =============================================================================
class TodoCommandHandler:
    """
    Handles todo commands embedded in LLM responses.

    Parses code blocks like:
    ```todo
    ACTION: add
    TITLE: Buy groceries
    PRIORITY: medium
    ```
    """

    # Pattern to find todo code blocks
    TODO_BLOCK_PATTERN = re.compile(
        r'```todo\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> Optional[SchedulerManager] to None
    # =========================================================================
    def __init__(self, scheduler_manager: Optional["SchedulerManager"] = None):
        """
        Initialize the todo command handler.

        Args:
            scheduler_manager: The scheduler manager for reminders
        """
        self.scheduler_manager = scheduler_manager
        from coco_b import PROJECT_ROOT
        self._data_file = PROJECT_ROOT / "data" / "todos.json"
        self._lock = threading.Lock()
        self._ensure_data_file()

    # =========================================================================
    # Function set_scheduler_manager -> SchedulerManager to None
    # =========================================================================
    def set_scheduler_manager(self, scheduler_manager: "SchedulerManager"):
        """Set or update the scheduler manager"""
        self.scheduler_manager = scheduler_manager

    # =========================================================================
    # Function _ensure_data_file -> None to None
    # =========================================================================
    def _ensure_data_file(self):
        """Ensure the data directory and file exist"""
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            self._save_data({})

    # =========================================================================
    # Function _load_data -> None to Dict
    # =========================================================================
    def _load_data(self) -> Dict[str, List[Dict]]:
        """Load todos from JSON file (thread-safe)"""
        with self._lock:
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}

    # =========================================================================
    # Function _save_data -> Dict to None
    # =========================================================================
    def _save_data(self, data: Dict[str, List[Dict]]):
        """Save todos to JSON file (thread-safe)"""
        with self._lock:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

    # =========================================================================
    # Function has_todo_commands -> str to bool
    # =========================================================================
    def has_todo_commands(self, response: str) -> bool:
        """
        Check if response contains todo commands.

        Args:
            response: LLM response text

        Returns:
            True if todo commands found
        """
        return bool(self.TODO_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_todo_block -> str to Dict[str, str]
    # =========================================================================
    def parse_todo_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse a todo block into key-value pairs.

        Args:
            block_content: Content inside ```todo``` block

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
                if key in ['ACTION', 'TITLE', 'PRIORITY', 'DUE', 'TAGS',
                          'TODO_ID', 'REMIND_AT']:
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
        Extract all todo commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.TODO_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_todo_block(match)
            if parsed.get('ACTION'):
                commands.append(parsed)

        return commands

    # =========================================================================
    # Function execute_commands -> str, str, Optional[str] to Tuple[str, list]
    # =========================================================================
    async def execute_commands(
        self,
        response: str,
        user_id: str,
        channel: str = "",
        chat_id: Optional[str] = None,
    ) -> Tuple[str, list]:
        """
        Execute all todo commands in response.

        Args:
            response: LLM response text
            user_id: User ID for scoping todos
            channel: Channel name (for reminders)
            chat_id: Optional chat ID (for reminders)

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            action = cmd.get('ACTION', '').lower()
            result = None

            try:
                if action == 'add':
                    result = self._handle_add(cmd, user_id)
                elif action == 'list':
                    result = self._handle_list(cmd, user_id)
                elif action == 'done':
                    result = self._handle_done(cmd, user_id)
                elif action == 'delete':
                    result = self._handle_delete(cmd, user_id)
                elif action == 'edit':
                    result = self._handle_edit(cmd, user_id)
                elif action == 'remind':
                    result = await self._handle_remind(cmd, user_id, channel, chat_id)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Todo command error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean todo blocks from response for display
        cleaned = self.TODO_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_add -> Dict, str to Dict
    # =========================================================================
    def _handle_add(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle add action"""
        title = cmd.get('TITLE', '').strip()
        if not title:
            return {"success": False, "error": "No title specified"}

        priority = cmd.get('PRIORITY', 'medium').lower()
        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        due = cmd.get('DUE', '').strip() or None
        tags_str = cmd.get('TAGS', '').strip()
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

        todo_id = uuid.uuid4().hex[:8]
        now = datetime.now(tz=timezone.utc).isoformat()

        todo_item = {
            "id": todo_id,
            "title": title,
            "priority": priority,
            "due": due,
            "tags": tags,
            "status": "pending",
            "created_at": now,
            "completed_at": None,
        }

        data = self._load_data()
        if user_id not in data:
            data[user_id] = []
        data[user_id].append(todo_item)
        self._save_data(data)

        return {
            "success": True,
            "action": "add",
            "todo_id": todo_id,
            "title": title,
            "priority": priority,
            "due": due,
        }

    # =========================================================================
    # Function _handle_list -> Dict, str to Dict
    # =========================================================================
    def _handle_list(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle list action"""
        data = self._load_data()
        todos = data.get(user_id, [])

        # Filter to non-deleted pending items by default
        active_todos = [t for t in todos if t.get('status') != 'deleted']

        # Apply optional filters
        filter_tags = cmd.get('TAGS', '').strip()
        if filter_tags:
            tag_list = [t.strip().lower() for t in filter_tags.split(',') if t.strip()]
            active_todos = [
                t for t in active_todos
                if any(tag.lower() in [x.lower() for x in t.get('tags', [])] for tag in tag_list)
            ]

        filter_priority = cmd.get('PRIORITY', '').strip().lower()
        if filter_priority:
            active_todos = [t for t in active_todos if t.get('priority') == filter_priority]

        return {
            "success": True,
            "action": "list",
            "todos": active_todos,
            "total": len(active_todos),
        }

    # =========================================================================
    # Function _handle_done -> Dict, str to Dict
    # =========================================================================
    def _handle_done(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle done action"""
        todo_id = cmd.get('TODO_ID', '').strip()
        if not todo_id:
            return {"success": False, "error": "No todo ID specified"}

        data = self._load_data()
        todos = data.get(user_id, [])

        for todo in todos:
            if todo['id'] == todo_id:
                todo['status'] = 'done'
                todo['completed_at'] = datetime.now(tz=timezone.utc).isoformat()
                self._save_data(data)
                return {
                    "success": True,
                    "action": "done",
                    "todo_id": todo_id,
                    "title": todo['title'],
                }

        return {"success": False, "error": f"Todo '{todo_id}' not found"}

    # =========================================================================
    # Function _handle_delete -> Dict, str to Dict
    # =========================================================================
    def _handle_delete(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle delete action"""
        todo_id = cmd.get('TODO_ID', '').strip()
        if not todo_id:
            return {"success": False, "error": "No todo ID specified"}

        data = self._load_data()
        todos = data.get(user_id, [])

        for todo in todos:
            if todo['id'] == todo_id:
                todo['status'] = 'deleted'
                self._save_data(data)
                return {
                    "success": True,
                    "action": "delete",
                    "todo_id": todo_id,
                    "title": todo['title'],
                }

        return {"success": False, "error": f"Todo '{todo_id}' not found"}

    # =========================================================================
    # Function _handle_edit -> Dict, str to Dict
    # =========================================================================
    def _handle_edit(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle edit action"""
        todo_id = cmd.get('TODO_ID', '').strip()
        if not todo_id:
            return {"success": False, "error": "No todo ID specified"}

        data = self._load_data()
        todos = data.get(user_id, [])

        for todo in todos:
            if todo['id'] == todo_id:
                updated_fields = []

                if cmd.get('TITLE'):
                    todo['title'] = cmd['TITLE'].strip()
                    updated_fields.append('title')
                if cmd.get('PRIORITY'):
                    priority = cmd['PRIORITY'].strip().lower()
                    if priority in ('low', 'medium', 'high'):
                        todo['priority'] = priority
                        updated_fields.append('priority')
                if cmd.get('DUE'):
                    todo['due'] = cmd['DUE'].strip()
                    updated_fields.append('due')
                if cmd.get('TAGS'):
                    tags_str = cmd['TAGS'].strip()
                    todo['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
                    updated_fields.append('tags')

                if not updated_fields:
                    return {"success": False, "error": "No fields to update"}

                self._save_data(data)
                return {
                    "success": True,
                    "action": "edit",
                    "todo_id": todo_id,
                    "title": todo['title'],
                    "updated_fields": updated_fields,
                }

        return {"success": False, "error": f"Todo '{todo_id}' not found"}

    # =========================================================================
    # Function _handle_remind -> Dict, str, str, Optional[str] to Dict
    # =========================================================================
    async def _handle_remind(
        self,
        cmd: Dict[str, str],
        user_id: str,
        channel: str,
        chat_id: Optional[str],
    ) -> Dict[str, Any]:
        """Handle remind action — creates a scheduled reminder via SchedulerManager"""
        todo_id = cmd.get('TODO_ID', '').strip()
        remind_at = cmd.get('REMIND_AT', '').strip()

        if not todo_id:
            return {"success": False, "error": "No todo ID specified"}
        if not remind_at:
            return {"success": False, "error": "No reminder time specified"}
        if not self.scheduler_manager:
            return {"success": False, "error": "Scheduler not available for reminders"}

        # Find the todo to get its title
        data = self._load_data()
        todos = data.get(user_id, [])
        todo_item = None
        for todo in todos:
            if todo['id'] == todo_id:
                todo_item = todo
                break

        if not todo_item:
            return {"success": False, "error": f"Todo '{todo_id}' not found"}

        # Create a scheduled task for the reminder
        from coco_b.core.scheduler import ScheduledTask

        task = ScheduledTask(
            name=f"Todo reminder: {todo_item['title']}",
            description=f"Reminder for todo {todo_id}",
            schedule=remind_at,
            timezone="UTC",
            action="send_message",
            target_channel=channel,
            target_user=user_id,
            target_chat=chat_id,
            message=f"Reminder: **{todo_item['title']}** (todo `{todo_id}`)",
        )

        try:
            task_id = await self.scheduler_manager.add_task(task)
            return {
                "success": True,
                "action": "remind",
                "todo_id": todo_id,
                "title": todo_item['title'],
                "schedule_task_id": task_id,
                "remind_at": remind_at,
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

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

            if action == 'add':
                title = result.get('title', '')
                todo_id = result.get('todo_id', '')
                priority = result.get('priority', 'medium')
                due = result.get('due')
                lines.append(f"**Todo Added**: {title}")
                lines.append(f"- ID: `{todo_id}`")
                lines.append(f"- Priority: {priority}")
                if due:
                    lines.append(f"- Due: {due}")

            elif action == 'list':
                todos = result.get('todos', [])
                if not todos:
                    lines.append("**No todos found.**")
                else:
                    lines.append(f"**Your Todos** ({len(todos)} items):")
                    for t in todos:
                        status_icon = "✅" if t.get('status') == 'done' else "⬜"
                        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                            t.get('priority', 'medium'), "🟡"
                        )
                        due_str = f" | Due: {t['due']}" if t.get('due') else ""
                        tags_str = f" | Tags: {', '.join(t['tags'])}" if t.get('tags') else ""
                        lines.append(
                            f"- {status_icon} {priority_icon} **{t['title']}** (`{t['id']}`)"
                            f"{due_str}{tags_str}"
                        )

            elif action == 'done':
                title = result.get('title', '')
                lines.append(f"**Completed**: ✅ {title}")

            elif action == 'delete':
                title = result.get('title', '')
                lines.append(f"**Deleted**: {title}")

            elif action == 'edit':
                title = result.get('title', '')
                fields = result.get('updated_fields', [])
                lines.append(f"**Updated**: {title}")
                lines.append(f"- Changed: {', '.join(fields)}")

            elif action == 'remind':
                title = result.get('title', '')
                remind_at = result.get('remind_at', '')
                lines.append(f"**Reminder Set**: {title}")
                lines.append(f"- Schedule: `{remind_at}`")

        return '\n'.join(lines)


# =============================================================================
# Convenience function
# =============================================================================

def create_todo_handler(
    scheduler_manager: Optional["SchedulerManager"] = None,
) -> TodoCommandHandler:
    """Create a todo command handler"""
    return TodoCommandHandler(scheduler_manager)


# =============================================================================
'''
    End of File : todo_handler.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
