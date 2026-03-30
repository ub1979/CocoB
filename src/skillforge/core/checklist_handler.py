# =============================================================================
'''
    File Name : checklist_handler.py

    Description : Handler for parsing and executing checklist commands from
                  LLM responses. Manages persistent named checklists with
                  create, show, quiz, edit, and delete functionality.

    Created on 2026-03-29

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import re
import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("checklist_handler")


# =============================================================================
'''
    ChecklistCommandHandler : Parses and executes checklist commands from
                              LLM responses in ```checklist``` code blocks.
'''
# =============================================================================
class ChecklistCommandHandler:
    """
    Handles checklist commands embedded in LLM responses.

    Parses code blocks like:
    ```checklist
    ACTION: create
    NAME: Travel Checklist
    ITEMS:
    passport
    tickets
    charger
    ```
    """

    # Pattern to find checklist code blocks
    CHECKLIST_BLOCK_PATTERN = re.compile(
        r'```checklist\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> None to None
    # =========================================================================
    def __init__(self):
        """
        Initialize the checklist command handler.
        """
        from skillforge import PROJECT_ROOT
        self._data_file = PROJECT_ROOT / "data" / "checklists.json"
        self._lock = threading.Lock()
        self._ensure_data_file()

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
    def _load_data(self) -> Dict[str, Dict[str, Dict]]:
        """Load checklists from JSON file (thread-safe)"""
        with self._lock:
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}

    # =========================================================================
    # Function _save_data -> Dict to None
    # =========================================================================
    def _save_data(self, data: Dict[str, Dict[str, Dict]]):
        """Save checklists to JSON file (thread-safe)"""
        with self._lock:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

    # =========================================================================
    # Function _slugify -> str to str
    # =========================================================================
    def _slugify(self, name: str) -> str:
        """
        Convert a checklist name to a slug for use as a dictionary key.

        Args:
            name: Human-readable checklist name

        Returns:
            Lowercase slug with spaces replaced by underscores
        """
        slug = name.strip().lower()
        slug = re.sub(r'[^a-z0-9\s]', '', slug)
        slug = re.sub(r'\s+', '_', slug)
        return slug

    # =========================================================================
    # Function has_checklist_commands -> str to bool
    # =========================================================================
    def has_checklist_commands(self, response: str) -> bool:
        """
        Check if response contains checklist commands.

        Args:
            response: LLM response text

        Returns:
            True if checklist commands found
        """
        return bool(self.CHECKLIST_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_checklist_block -> str to Dict[str, str]
    # =========================================================================
    def parse_checklist_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse a checklist block into key-value pairs.

        Handles multi-line values for ITEMS, ADD_ITEMS, and REMOVE_ITEMS fields.

        Args:
            block_content: Content inside ```checklist``` block

        Returns:
            Dictionary of parsed values
        """
        result = {}
        current_key = None
        current_value = []

        known_keys = ['ACTION', 'NAME', 'ITEMS', 'ADD_ITEMS', 'REMOVE_ITEMS']

        for line in block_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Check for KEY: VALUE pattern
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().upper()
                value = parts[1].strip() if len(parts) > 1 else ""

                if key in known_keys:
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
                # Continuation of previous value (multi-line items)
                if current_key:
                    current_value.append(line)

        # Save last key
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()

        return result

    # =========================================================================
    # Function _parse_items -> str to List[str]
    # =========================================================================
    def _parse_items(self, items_str: str) -> List[str]:
        """
        Parse an items string into a list, supporting both comma-separated
        and newline-separated formats.

        Args:
            items_str: Raw items string from command block

        Returns:
            List of item strings
        """
        if not items_str:
            return []

        # If there are newlines, treat as newline-separated
        if '\n' in items_str:
            items = [item.strip() for item in items_str.split('\n')]
        else:
            # Otherwise treat as comma-separated
            items = [item.strip() for item in items_str.split(',')]

        # Filter out empty strings
        return [item for item in items if item]

    # =========================================================================
    # Function extract_commands -> str to list
    # =========================================================================
    def extract_commands(self, response: str) -> list:
        """
        Extract all checklist commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.CHECKLIST_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_checklist_block(match)
            if parsed.get('ACTION'):
                commands.append(parsed)

        return commands

    # =========================================================================
    # Function execute_commands -> str, str to Tuple[str, list]
    # =========================================================================
    async def execute_commands(
        self,
        response: str,
        user_id: str,
    ) -> Tuple[str, list]:
        """
        Execute all checklist commands in response.

        Args:
            response: LLM response text
            user_id: User ID for scoping checklists

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            action = cmd.get('ACTION', '').lower()
            result = None

            try:
                if action == 'create':
                    result = self._handle_create(cmd, user_id)
                elif action == 'list':
                    result = self._handle_list(cmd, user_id)
                elif action == 'show':
                    result = self._handle_show(cmd, user_id)
                elif action == 'quiz':
                    result = self._handle_quiz(cmd, user_id)
                elif action == 'delete':
                    result = self._handle_delete(cmd, user_id)
                elif action == 'edit':
                    result = self._handle_edit(cmd, user_id)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Checklist command error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean checklist blocks from response for display
        cleaned = self.CHECKLIST_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_create -> Dict, str to Dict
    # =========================================================================
    def _handle_create(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle create action"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No checklist name specified"}

        items_str = cmd.get('ITEMS', '').strip()
        items = self._parse_items(items_str)
        if not items:
            return {"success": False, "error": "No items specified"}

        slug = self._slugify(name)
        now = datetime.now(tz=timezone.utc).isoformat()

        checklist_entry = {
            "name": name,
            "items": items,
            "created_at": now,
            "updated_at": now,
        }

        data = self._load_data()
        if user_id not in data:
            data[user_id] = {}
        data[user_id][slug] = checklist_entry
        self._save_data(data)

        return {
            "success": True,
            "action": "create",
            "name": name,
            "slug": slug,
            "items": items,
            "item_count": len(items),
        }

    # =========================================================================
    # Function _handle_list -> Dict, str to Dict
    # =========================================================================
    def _handle_list(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle list action"""
        data = self._load_data()
        user_checklists = data.get(user_id, {})

        checklists_summary = []
        for slug, checklist in user_checklists.items():
            checklists_summary.append({
                "slug": slug,
                "name": checklist["name"],
                "item_count": len(checklist["items"]),
                "created_at": checklist.get("created_at", ""),
                "updated_at": checklist.get("updated_at", ""),
            })

        return {
            "success": True,
            "action": "list",
            "checklists": checklists_summary,
            "total": len(checklists_summary),
        }

    # =========================================================================
    # Function _handle_show -> Dict, str to Dict
    # =========================================================================
    def _handle_show(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle show action"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No checklist name specified"}

        slug = self._slugify(name)
        data = self._load_data()
        user_checklists = data.get(user_id, {})

        checklist = user_checklists.get(slug)
        if not checklist:
            return {"success": False, "error": f"Checklist '{name}' not found"}

        return {
            "success": True,
            "action": "show",
            "name": checklist["name"],
            "slug": slug,
            "items": checklist["items"],
            "item_count": len(checklist["items"]),
            "created_at": checklist.get("created_at", ""),
            "updated_at": checklist.get("updated_at", ""),
        }

    # =========================================================================
    # Function _handle_quiz -> Dict, str to Dict
    # =========================================================================
    def _handle_quiz(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """
        Handle quiz action.

        Returns the checklist items so the LLM can interactively quiz the user
        on each item conversationally.
        """
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No checklist name specified"}

        slug = self._slugify(name)
        data = self._load_data()
        user_checklists = data.get(user_id, {})

        checklist = user_checklists.get(slug)
        if not checklist:
            return {"success": False, "error": f"Checklist '{name}' not found"}

        return {
            "success": True,
            "action": "quiz",
            "name": checklist["name"],
            "slug": slug,
            "items": checklist["items"],
            "item_count": len(checklist["items"]),
        }

    # =========================================================================
    # Function _handle_delete -> Dict, str to Dict
    # =========================================================================
    def _handle_delete(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle delete action"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No checklist name specified"}

        slug = self._slugify(name)
        data = self._load_data()
        user_checklists = data.get(user_id, {})

        checklist = user_checklists.get(slug)
        if not checklist:
            return {"success": False, "error": f"Checklist '{name}' not found"}

        deleted_name = checklist["name"]
        del data[user_id][slug]

        # Clean up empty user entry
        if not data[user_id]:
            del data[user_id]

        self._save_data(data)

        return {
            "success": True,
            "action": "delete",
            "name": deleted_name,
            "slug": slug,
        }

    # =========================================================================
    # Function _handle_edit -> Dict, str to Dict
    # =========================================================================
    def _handle_edit(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle edit action — supports ADD_ITEMS and REMOVE_ITEMS"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No checklist name specified"}

        slug = self._slugify(name)
        data = self._load_data()
        user_checklists = data.get(user_id, {})

        checklist = user_checklists.get(slug)
        if not checklist:
            return {"success": False, "error": f"Checklist '{name}' not found"}

        added = []
        removed = []

        # Handle ADD_ITEMS
        add_items_str = cmd.get('ADD_ITEMS', '').strip()
        if add_items_str:
            add_items = self._parse_items(add_items_str)
            for item in add_items:
                if item.lower() not in [i.lower() for i in checklist["items"]]:
                    checklist["items"].append(item)
                    added.append(item)

        # Handle REMOVE_ITEMS
        remove_items_str = cmd.get('REMOVE_ITEMS', '').strip()
        if remove_items_str:
            remove_items = self._parse_items(remove_items_str)
            remove_lower = [r.lower() for r in remove_items]
            original_items = checklist["items"][:]
            checklist["items"] = [
                item for item in checklist["items"]
                if item.lower() not in remove_lower
            ]
            removed = [
                item for item in original_items
                if item.lower() in remove_lower
            ]

        if not added and not removed:
            return {"success": False, "error": "No items to add or remove specified"}

        checklist["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._save_data(data)

        return {
            "success": True,
            "action": "edit",
            "name": checklist["name"],
            "slug": slug,
            "added": added,
            "removed": removed,
            "items": checklist["items"],
            "item_count": len(checklist["items"]),
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
                name = result.get('name', '')
                items = result.get('items', [])
                lines.append(f"**Checklist Created**: {name}")
                lines.append(f"- Items ({len(items)}):")
                for item in items:
                    lines.append(f"  - {item}")

            elif action == 'list':
                checklists = result.get('checklists', [])
                if not checklists:
                    lines.append("**No checklists found.**")
                else:
                    lines.append(f"**Your Checklists** ({len(checklists)}):")
                    for cl in checklists:
                        lines.append(
                            f"- **{cl['name']}** ({cl['item_count']} items)"
                        )

            elif action == 'show':
                name = result.get('name', '')
                items = result.get('items', [])
                lines.append(f"**{name}** ({len(items)} items):")
                for i, item in enumerate(items, 1):
                    lines.append(f"  {i}. {item}")

            elif action == 'quiz':
                name = result.get('name', '')
                items = result.get('items', [])
                lines.append(f"**Quiz: {name}** ({len(items)} items)")
                lines.append("Let me go through each item:")
                for i, item in enumerate(items, 1):
                    lines.append(f"  {i}. {item}")

            elif action == 'delete':
                name = result.get('name', '')
                lines.append(f"**Checklist Deleted**: {name}")

            elif action == 'edit':
                name = result.get('name', '')
                added = result.get('added', [])
                removed = result.get('removed', [])
                lines.append(f"**Checklist Updated**: {name}")
                if added:
                    lines.append(f"- Added: {', '.join(added)}")
                if removed:
                    lines.append(f"- Removed: {', '.join(removed)}")
                lines.append(f"- Total items: {result.get('item_count', 0)}")

        return '\n'.join(lines)


# =============================================================================
# Convenience function
# =============================================================================

def create_checklist_handler() -> ChecklistCommandHandler:
    """Create a checklist command handler"""
    return ChecklistCommandHandler()


# =============================================================================
'''
    End of File : checklist_handler.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
