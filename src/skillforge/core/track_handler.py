# =============================================================================
'''
    File Name : track_handler.py

    Description : Handler for parsing and executing personal data tracking
                  commands from LLM responses. Manages a persistent JSON-based
                  tracker for fuel logs, gym routines, meter readings, expenses,
                  weight, and any user-defined category.

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
import uuid
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("track_handler")


# =============================================================================
'''
    TrackCommandHandler : Parses and executes personal data tracking commands
                          from LLM responses in ```track``` code blocks.
'''
# =============================================================================
class TrackCommandHandler:
    """
    Handles track commands embedded in LLM responses.

    Parses code blocks like:
    ```track
    ACTION: log
    CATEGORY: petrol
    VALUE: 40
    UNIT: litres
    NOTE: meter:45230
    ```
    """

    # Pattern to find track code blocks
    TRACK_BLOCK_PATTERN = re.compile(
        r'```track\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> None to None
    # =========================================================================
    def __init__(self):
        """
        Initialize the track command handler.
        """
        from skillforge import PROJECT_ROOT
        self._data_file = PROJECT_ROOT / "data" / "tracker.json"
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
    def _load_data(self) -> Dict[str, List[Dict]]:
        """Load tracker data from JSON file (thread-safe)"""
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
        """Save tracker data to JSON file (thread-safe)"""
        with self._lock:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

    # =========================================================================
    # Function has_track_commands -> str to bool
    # =========================================================================
    def has_track_commands(self, response: str) -> bool:
        """
        Check if response contains track commands.

        Args:
            response: LLM response text

        Returns:
            True if track commands found
        """
        return bool(self.TRACK_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_track_block -> str to Dict[str, str]
    # =========================================================================
    def parse_track_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse a track block into key-value pairs.

        Args:
            block_content: Content inside ```track``` block

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
                if key in ['ACTION', 'CATEGORY', 'VALUE', 'UNIT', 'NOTE',
                           'ENTRY_ID', 'COUNT', 'DATE_FROM', 'DATE_TO']:
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
        Extract all track commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.TRACK_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_track_block(match)
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
        Execute all track commands in response.

        Args:
            response: LLM response text
            user_id: User ID for scoping tracked data

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            action = cmd.get('ACTION', '').lower()
            result = None

            try:
                if action == 'log':
                    result = self._handle_log(cmd, user_id)
                elif action == 'list':
                    result = self._handle_list(cmd, user_id)
                elif action == 'categories':
                    result = self._handle_categories(cmd, user_id)
                elif action == 'stats':
                    result = self._handle_stats(cmd, user_id)
                elif action == 'delete':
                    result = self._handle_delete(cmd, user_id)
                elif action == 'export':
                    result = self._handle_export(cmd, user_id)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Track command error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean track blocks from response for display
        cleaned = self.TRACK_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_log -> Dict, str to Dict
    # =========================================================================
    def _handle_log(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle log action"""
        category = cmd.get('CATEGORY', '').strip().lower()
        if not category:
            return {"success": False, "error": "No category specified"}

        value_str = cmd.get('VALUE', '').strip()
        if not value_str:
            return {"success": False, "error": "No value specified"}

        try:
            value = float(value_str)
        except ValueError:
            return {"success": False, "error": f"Invalid numeric value: {value_str}"}

        unit = cmd.get('UNIT', '').strip() or None
        note = cmd.get('NOTE', '').strip() or None

        entry_id = uuid.uuid4().hex[:8]
        now = datetime.now(tz=timezone.utc).isoformat()

        entry = {
            "id": entry_id,
            "category": category,
            "value": value,
            "unit": unit,
            "note": note,
            "timestamp": now,
        }

        data = self._load_data()
        if user_id not in data:
            data[user_id] = []
        data[user_id].append(entry)
        self._save_data(data)

        return {
            "success": True,
            "action": "log",
            "entry_id": entry_id,
            "category": category,
            "value": value,
            "unit": unit,
            "note": note,
        }

    # =========================================================================
    # Function _handle_list -> Dict, str to Dict
    # =========================================================================
    def _handle_list(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle list action"""
        category = cmd.get('CATEGORY', '').strip().lower()
        if not category:
            return {"success": False, "error": "No category specified"}

        data = self._load_data()
        entries = data.get(user_id, [])

        # Filter by category
        filtered = [e for e in entries if e.get('category') == category]

        # Apply date filters
        date_from = cmd.get('DATE_FROM', '').strip()
        date_to = cmd.get('DATE_TO', '').strip()

        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if dt_from.tzinfo is None:
                    dt_from = dt_from.replace(tzinfo=timezone.utc)
                filtered = [
                    e for e in filtered
                    if datetime.fromisoformat(e['timestamp']) >= dt_from
                ]
            except ValueError:
                logger.warning(f"Invalid DATE_FROM: {date_from}")

        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
                if dt_to.tzinfo is None:
                    # Set to end of day
                    dt_to = dt_to.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                filtered = [
                    e for e in filtered
                    if datetime.fromisoformat(e['timestamp']) <= dt_to
                ]
            except ValueError:
                logger.warning(f"Invalid DATE_TO: {date_to}")

        # Sort by timestamp descending (most recent first)
        filtered.sort(key=lambda e: e.get('timestamp', ''), reverse=True)

        # Apply count limit
        count_str = cmd.get('COUNT', '10').strip()
        try:
            count = int(count_str)
        except ValueError:
            count = 10
        filtered = filtered[:count]

        return {
            "success": True,
            "action": "list",
            "category": category,
            "entries": filtered,
            "total": len(filtered),
        }

    # =========================================================================
    # Function _handle_categories -> Dict, str to Dict
    # =========================================================================
    def _handle_categories(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle categories action"""
        data = self._load_data()
        entries = data.get(user_id, [])

        # Collect unique categories with counts
        category_counts: Dict[str, int] = {}
        for entry in entries:
            cat = entry.get('category', 'unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1

        categories = [
            {"name": name, "count": count}
            for name, count in sorted(category_counts.items())
        ]

        return {
            "success": True,
            "action": "categories",
            "categories": categories,
            "total": len(categories),
        }

    # =========================================================================
    # Function _handle_stats -> Dict, str to Dict
    # =========================================================================
    def _handle_stats(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle stats action — calculate analytics for a category"""
        category = cmd.get('CATEGORY', '').strip().lower()
        if not category:
            return {"success": False, "error": "No category specified"}

        data = self._load_data()
        entries = data.get(user_id, [])

        # Filter by category
        filtered = [e for e in entries if e.get('category') == category]

        # Apply date filters
        date_from = cmd.get('DATE_FROM', '').strip()
        date_to = cmd.get('DATE_TO', '').strip()

        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from)
                if dt_from.tzinfo is None:
                    dt_from = dt_from.replace(tzinfo=timezone.utc)
                filtered = [
                    e for e in filtered
                    if datetime.fromisoformat(e['timestamp']) >= dt_from
                ]
            except ValueError:
                logger.warning(f"Invalid DATE_FROM: {date_from}")

        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to)
                if dt_to.tzinfo is None:
                    dt_to = dt_to.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                filtered = [
                    e for e in filtered
                    if datetime.fromisoformat(e['timestamp']) <= dt_to
                ]
            except ValueError:
                logger.warning(f"Invalid DATE_TO: {date_to}")

        if not filtered:
            return {
                "success": True,
                "action": "stats",
                "category": category,
                "count": 0,
                "message": f"No entries found for '{category}'",
            }

        # Sort by timestamp ascending for trend calculation
        filtered.sort(key=lambda e: e.get('timestamp', ''))

        values = [e['value'] for e in filtered]
        count = len(values)
        total = sum(values)
        average = total / count
        min_val = min(values)
        max_val = max(values)
        first_date = filtered[0].get('timestamp', '')
        last_date = filtered[-1].get('timestamp', '')

        # Determine the most common unit
        units = [e.get('unit') for e in filtered if e.get('unit')]
        unit = max(set(units), key=units.count) if units else None

        # Simple trend: compare average of last 3 entries vs previous 3
        trend = "stable"
        if count >= 6:
            prev_avg = sum(values[-6:-3]) / 3
            recent_avg = sum(values[-3:]) / 3
            if recent_avg > prev_avg * 1.05:
                trend = "increasing"
            elif recent_avg < prev_avg * 0.95:
                trend = "decreasing"
            else:
                trend = "stable"
        elif count >= 2:
            # With fewer entries, compare last vs first
            if values[-1] > values[0] * 1.05:
                trend = "increasing"
            elif values[-1] < values[0] * 0.95:
                trend = "decreasing"
            else:
                trend = "stable"

        return {
            "success": True,
            "action": "stats",
            "category": category,
            "count": count,
            "total": round(total, 2),
            "average": round(average, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "unit": unit,
            "first_date": first_date,
            "last_date": last_date,
            "trend": trend,
        }

    # =========================================================================
    # Function _handle_delete -> Dict, str to Dict
    # =========================================================================
    def _handle_delete(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle delete action"""
        entry_id = cmd.get('ENTRY_ID', '').strip()
        if not entry_id:
            return {"success": False, "error": "No entry ID specified"}

        data = self._load_data()
        entries = data.get(user_id, [])

        for i, entry in enumerate(entries):
            if entry['id'] == entry_id:
                removed = entries.pop(i)
                data[user_id] = entries
                self._save_data(data)
                return {
                    "success": True,
                    "action": "delete",
                    "entry_id": entry_id,
                    "category": removed.get('category', ''),
                    "value": removed.get('value'),
                    "note": removed.get('note'),
                }

        return {"success": False, "error": f"Entry '{entry_id}' not found"}

    # =========================================================================
    # Function _handle_export -> Dict, str to Dict
    # =========================================================================
    def _handle_export(self, cmd: Dict[str, str], user_id: str) -> Dict[str, Any]:
        """Handle export action — return all data for a category"""
        category = cmd.get('CATEGORY', '').strip().lower()
        if not category:
            return {"success": False, "error": "No category specified"}

        data = self._load_data()
        entries = data.get(user_id, [])

        # Filter by category and sort by timestamp ascending
        filtered = [e for e in entries if e.get('category') == category]
        filtered.sort(key=lambda e: e.get('timestamp', ''))

        return {
            "success": True,
            "action": "export",
            "category": category,
            "entries": filtered,
            "total": len(filtered),
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

            if action == 'log':
                category = result.get('category', '')
                value = result.get('value', '')
                unit = result.get('unit', '')
                note = result.get('note', '')
                entry_id = result.get('entry_id', '')
                unit_str = f" {unit}" if unit else ""
                note_str = f" ({note})" if note else ""
                lines.append(f"**Logged**: {value}{unit_str} in *{category}*{note_str}")
                lines.append(f"- Entry ID: `{entry_id}`")

            elif action == 'list':
                category = result.get('category', '')
                entries = result.get('entries', [])
                if not entries:
                    lines.append(f"**No entries found for *{category}*.**")
                else:
                    lines.append(f"**{category.title()} Log** ({len(entries)} entries):")
                    for e in entries:
                        ts = e.get('timestamp', '')
                        # Format timestamp for display
                        try:
                            dt = datetime.fromisoformat(ts)
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, TypeError):
                            date_str = ts
                        value = e.get('value', '')
                        unit = e.get('unit', '')
                        note = e.get('note', '')
                        unit_str = f" {unit}" if unit else ""
                        note_str = f" — {note}" if note else ""
                        lines.append(
                            f"- `{e['id']}` | {date_str} | **{value}{unit_str}**{note_str}"
                        )

            elif action == 'categories':
                categories = result.get('categories', [])
                if not categories:
                    lines.append("**No categories tracked yet.**")
                else:
                    lines.append(f"**Your Tracked Categories** ({len(categories)}):")
                    for cat in categories:
                        lines.append(f"- **{cat['name']}** — {cat['count']} entries")

            elif action == 'stats':
                category = result.get('category', '')
                count = result.get('count', 0)
                if count == 0:
                    lines.append(f"**No data found for *{category}*.**")
                else:
                    unit = result.get('unit', '')
                    unit_str = f" {unit}" if unit else ""
                    trend = result.get('trend', 'stable')
                    trend_icon = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}.get(
                        trend, "➡️"
                    )
                    lines.append(f"**Stats for *{category}***:")
                    lines.append(f"- Entries: {count}")
                    lines.append(f"- Total: {result.get('total', 0)}{unit_str}")
                    lines.append(f"- Average: {result.get('average', 0)}{unit_str}")
                    lines.append(f"- Min: {result.get('min', 0)}{unit_str}")
                    lines.append(f"- Max: {result.get('max', 0)}{unit_str}")
                    lines.append(f"- First entry: {result.get('first_date', 'N/A')}")
                    lines.append(f"- Last entry: {result.get('last_date', 'N/A')}")
                    lines.append(f"- Trend: {trend_icon} {trend}")

            elif action == 'delete':
                entry_id = result.get('entry_id', '')
                category = result.get('category', '')
                value = result.get('value', '')
                lines.append(f"**Deleted**: entry `{entry_id}` from *{category}* (value: {value})")

            elif action == 'export':
                category = result.get('category', '')
                entries = result.get('entries', [])
                if not entries:
                    lines.append(f"**No data to export for *{category}*.**")
                else:
                    lines.append(f"**Export: *{category}*** ({len(entries)} entries):")
                    for e in entries:
                        ts = e.get('timestamp', '')
                        try:
                            dt = datetime.fromisoformat(ts)
                            date_str = dt.strftime("%Y-%m-%d %H:%M")
                        except (ValueError, TypeError):
                            date_str = ts
                        value = e.get('value', '')
                        unit = e.get('unit', '')
                        note = e.get('note', '')
                        unit_str = f" {unit}" if unit else ""
                        note_str = f" — {note}" if note else ""
                        lines.append(
                            f"- `{e['id']}` | {date_str} | {value}{unit_str}{note_str}"
                        )

        return '\n'.join(lines)


# =============================================================================
# Convenience function
# =============================================================================

def create_track_handler() -> TrackCommandHandler:
    """Create a track command handler"""
    return TrackCommandHandler()


# =============================================================================
'''
    End of File : track_handler.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
