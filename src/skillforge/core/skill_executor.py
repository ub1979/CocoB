# =============================================================================
'''
    File Name : skill_executor.py

    Description : Unified Skill Executor - Handles direct skill execution via MCP
    for all channels (Telegram, Flet, WhatsApp, Slack, Discord, etc.)

    This module provides channel-agnostic skill execution so that skills like
    /email and /calendar work the same way regardless of which channel the
    user is using.

    Created on 2026-02-10

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

import re
import logging
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.mcp_client import MCPManager

logger = logging.getLogger("skillforge.skill_executor")


class SkillExecutor:
    """
    Unified skill executor for all channels.

    Handles direct MCP tool execution for skills like /email and /calendar,
    providing consistent behavior across Telegram, Flet, WhatsApp, etc.
    """

    def __init__(self, mcp_manager: Optional["MCPManager"] = None):
        """Initialize the skill executor.

        Args:
            mcp_manager: Optional MCP manager for tool execution
        """
        self._mcp_manager = mcp_manager

    def set_mcp_manager(self, mcp_manager: "MCPManager"):
        """Set or update the MCP manager."""
        self._mcp_manager = mcp_manager

    @property
    def mcp_manager(self) -> Optional["MCPManager"]:
        """Get the MCP manager."""
        return self._mcp_manager

    # Maps skill names to MCP servers they can use (first connected wins)
    _SKILL_SERVERS = {
        "email": ["google-workspace", "outlook", "ms365", "composio"],
        "calendar": ["google-workspace", "outlook", "ms365", "composio"],
        "notion": ["notion"],
        "google-search": ["playwright"],
        "browse": ["playwright"],
    }

    def _find_server(self, skill_name: str) -> str | None:
        """Find the first connected MCP server for a skill."""
        if not self._mcp_manager:
            return None
        for server in self._SKILL_SERVERS.get(skill_name, []):
            if self._mcp_manager.is_connected(server):
                return server
        return None

    def _diagnose_server(self, skill_name: str) -> str:
        """Diagnose why no server is connected for a skill and return a helpful message."""
        import os
        from pathlib import Path

        servers = self._SKILL_SERVERS.get(skill_name, [])
        if not self._mcp_manager:
            return "MCP is not configured."

        # Check which servers are configured (enabled) but failed to connect
        hints = []
        for server in servers:
            configs = self._mcp_manager.get_server_configs()
            cfg = configs.get(server)
            if cfg and cfg.enabled and not self._mcp_manager.is_connected(server):
                if server == "google-workspace":
                    gauth = Path.home() / ".mcp" / "google-workspace" / ".gauth.json"
                    if not gauth.exists():
                        hints.append(f"**{server}**: OAuth credentials file missing (~/.mcp/google-workspace/.gauth.json). See docs/EMAIL_CALENDAR_SETUP.md")
                    else:
                        # Credentials exist but probably no token — OAuth flow not completed
                        hints.append(f"**{server}**: OAuth not authorized. Restart the app and complete the Google sign-in in your browser when prompted.")
                elif server == "outlook":
                    hints.append(f"**{server}**: Check Azure Client ID/Secret in Settings > Accounts.")
                elif server == "notion":
                    hints.append(f"**{server}**: Set your Notion API key in config/mcp_config.json. Get it from https://www.notion.so/my-integrations")
                else:
                    hints.append(f"**{server}**: Failed to connect — check the MCP Tools tab for details.")
            elif cfg and not cfg.enabled:
                hints.append(f"**{server}**: Disabled in config. Enable it in MCP Tools settings.")

        if hints:
            return "\n".join(hints)
        return "No compatible MCP server is configured. Set one up in **MCP Tools** settings."

    def can_execute_directly(self, skill_name: str) -> bool:
        """Check if a skill can be executed directly via MCP.

        Args:
            skill_name: Name of the skill (without leading /)

        Returns:
            True if the skill has direct MCP execution support
        """
        return skill_name in self._SKILL_SERVERS

    def execute(self, skill_name: str, args: str) -> Tuple[bool, str]:
        """Execute a skill directly via MCP.

        Args:
            skill_name: Name of the skill (without leading /)
            args: Arguments/command for the skill

        Returns:
            Tuple of (success, result_message)
        """
        if not self._mcp_manager:
            return False, (
                f"❌ Cannot execute /{skill_name} — MCP is not configured.\n\n"
                "Go to **MCP Tools** in settings to connect the required server.\n"
                "See docs/EMAIL_CALENDAR_SETUP.md for setup instructions."
            )

        print(f"[executor] execute: skill={skill_name}, args={repr(args)}")
        if skill_name == "email":
            return self._execute_email(args)
        elif skill_name == "calendar":
            return self._execute_calendar(args)
        elif skill_name == "notion":
            return self._execute_notion(args)
        elif skill_name == "google-search":
            return self._execute_google_search(args)
        elif skill_name == "browse":
            return self._execute_browse(args)
        else:
            return False, f"Skill '{skill_name}' does not support direct execution."

    def _extract_mcp_result(self, result) -> str:
        """Extract text content from MCP tool result.

        Args:
            result: MCP tool result (dict, list, or other)

        Returns:
            Extracted text content as string
        """
        if isinstance(result, dict):
            if "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict):
                            texts.append(item.get("text", str(item)))
                        else:
                            texts.append(str(item))
                    return "\n".join(texts)
                else:
                    return str(content)
            elif "text" in result:
                return result["text"]
            elif "result" in result:
                return str(result["result"])
            else:
                return str(result)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        else:
            return str(result) if result else ""

    def _format_email_list(self, raw_text: str) -> str:
        """Format raw MCP email JSON into a readable list."""
        import json as _json
        try:
            data = _json.loads(raw_text)
        except (ValueError, TypeError):
            return raw_text  # Not JSON, return as-is

        messages = data.get("messages", []) if isinstance(data, dict) else []
        if not messages:
            return "No emails found."

        lines = []
        for i, msg in enumerate(messages, 1):
            sender = msg.get("from", "Unknown")
            subject = msg.get("subject", "(no subject)")
            date = msg.get("date", "")
            unread = "🔵 " if msg.get("isUnread") else ""
            starred = "⭐ " if msg.get("isStarred") else ""
            # Clean up date — show just day and time
            short_date = date.split("+")[0].split("-0")[0].strip() if date else ""
            lines.append(f"{unread}{starred}**{i}. {subject}**")
            lines.append(f"   From: {sender}")
            if short_date:
                lines.append(f"   Date: {short_date}")
            lines.append("")

        total = data.get("resultSizeEstimate", len(messages))
        if total > len(messages):
            lines.append(f"_Showing {len(messages)} of ~{total} emails_")

        return "\n".join(lines)

    def _execute_email(self, command: str) -> Tuple[bool, str]:
        """Execute email commands directly via MCP.

        Args:
            command: Email command (e.g., "inbox", "unread", "search query")

        Returns:
            Tuple of (success, result_message)
        """
        try:
            server = self._find_server("email")
            if not server:
                diagnosis = self._diagnose_server("email")
                return False, (
                    f"No email MCP server connected.\n\n{diagnosis}"
                )

            cmd = command.lower().strip()

            # Parse common email commands
            if cmd.startswith("check") or cmd.startswith("inbox") or cmd == "":
                result = self._mcp_manager.call_tool_sync(
                    server, "list-emails", {"maxResults": 5}
                )
                emails = self._format_email_list(self._extract_mcp_result(result))
                return True, f"**Recent Emails:**\n\n{emails}"

            elif cmd.startswith("unread"):
                result = self._mcp_manager.call_tool_sync(
                    server, "list-emails", {"query": "is:unread", "maxResults": 10}
                )
                emails = self._format_email_list(self._extract_mcp_result(result))
                return True, f"**Unread Emails:**\n\n{emails}"

            elif cmd.startswith("search "):
                query = command[7:].strip()
                result = self._mcp_manager.call_tool_sync(
                    server, "search-emails", {"query": query, "maxResults": 10}
                )
                emails = self._format_email_list(self._extract_mcp_result(result))
                return True, f"**Search Results for '{query}':**\n\n{emails}"

            elif cmd.startswith("send "):
                to_match = re.search(r'to\s+(\S+)', command, re.IGNORECASE)
                subject_match = re.search(r'subject\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
                body_match = re.search(r'body\s+["\']([^"\']+)["\']', command, re.IGNORECASE)

                if to_match:
                    to_email = to_match.group(1)
                    subject = subject_match.group(1) if subject_match else "No Subject"
                    body = body_match.group(1) if body_match else ""
                    self._mcp_manager.call_tool_sync(
                        server, "send-email",
                        {"to": to_email, "subject": subject, "body": body}
                    )
                    return True, f"Email sent to {to_email}"
                else:
                    return False, "Could not parse email. Use: /email send to email@example.com subject \"Subject\" body \"Message\""

            else:
                # Default: list recent emails for any unrecognized command
                result = self._mcp_manager.call_tool_sync(
                    server, "list-emails", {"maxResults": 5}
                )
                emails = self._format_email_list(self._extract_mcp_result(result))
                return True, f"**Recent Emails:**\n\n{emails}"

        except Exception as e:
            logger.error(f"Email execution error: {e}", exc_info=True)
            return False, f"Email error: {str(e)}"

    @staticmethod
    def _detect_system_tz() -> str:
        """Detect IANA timezone from the system. Falls back to UTC."""
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime, timezone
            import time
            # Try tzname first (works on most systems)
            local_tz = datetime.now(timezone.utc).astimezone().tzinfo
            tz_name = str(local_tz)
            # If it's a proper IANA name, use it
            if "/" in tz_name:
                ZoneInfo(tz_name)  # validate
                return tz_name
            # macOS: read /etc/localtime symlink
            import os
            link = os.readlink("/etc/localtime")
            if "zoneinfo/" in link:
                iana = link.split("zoneinfo/", 1)[1]
                ZoneInfo(iana)  # validate
                return iana
        except Exception:
            pass
        return "UTC"

    _CALENDAR_TZ = _detect_system_tz.__func__()

    @staticmethod
    def _calendar_time_range(offset_days: int = 0, span_days: int = 1):
        """Return (timeMin, timeMax) as ISO-8601 strings in the user's local timezone."""
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(SkillExecutor._CALENDAR_TZ)
        now = datetime.now(tz)
        start = (now + timedelta(days=offset_days)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=span_days)
        return start.isoformat(), end.isoformat()

    def _execute_calendar(self, command: str) -> Tuple[bool, str]:
        """Execute calendar commands directly via MCP.

        Args:
            command: Calendar command (e.g., "today", "tomorrow", "week")

        Returns:
            Tuple of (success, result_message)
        """
        try:
            server = self._find_server("calendar")
            if not server:
                diagnosis = self._diagnose_server("calendar")
                return False, (
                    f"No calendar MCP server connected.\n\n{diagnosis}"
                )

            cmd = command.lower().strip()

            # Detect create/schedule intent
            _create_kw = ("schedule", "create", "add", "make",
                          "book", "set up", "new event", "new meeting")
            if any(k in cmd for k in _create_kw):
                return self._create_calendar_event(server, command)

            if "tomorrow" in cmd:
                t_min, t_max = self._calendar_time_range(offset_days=1, span_days=1)
                label = "Tomorrow's"
            elif "week" in cmd:
                t_min, t_max = self._calendar_time_range(offset_days=0, span_days=7)
                label = "This Week's"
            else:
                # Default: today
                t_min, t_max = self._calendar_time_range(offset_days=0, span_days=1)
                label = "Today's"

            result = self._mcp_manager.call_tool_sync(
                server, "list-events",
                {"calendarId": "primary", "timeMin": t_min, "timeMax": t_max},
            )
            events = self._extract_mcp_result(result)
            if not events or events.strip() == "" or "no events" in events.lower():
                clean_label = label.rstrip("'s").lower()
                return True, f"No events scheduled for {clean_label}."
            return True, f"**{label} Events:**\n\n{events}"

        except Exception as e:
            logger.error(f"Calendar execution error: {e}", exc_info=True)
            return False, f"Calendar error: {str(e)}"

    def _create_calendar_event(self, server: str, command: str) -> Tuple[bool, str]:
        """Parse natural language and create a calendar event via MCP.

        Handles formats like:
            schedule meeting with Asad at 18:30
            create "Team Sync" tomorrow at 3pm
            add meeting for 14:00
            book appointment at 10am tomorrow
        """
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(self._CALENDAR_TZ)
        cmd = command.strip()
        cmd_lower = cmd.lower()

        # --- Extract time (HH:MM or HH:MMam/pm) ---
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', cmd_lower)
        if not time_match:
            time_match = re.search(r'(\d{1,2})\s*(am|pm)', cmd_lower)

        now = datetime.now(tz)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.lastindex >= 2 and time_match.group(2).isdigit() else 0
            ampm = time_match.group(time_match.lastindex) if time_match.group(time_match.lastindex) in ("am", "pm") else None
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
        else:
            hour, minute = 9, 0  # Default 9am

        # --- Determine day ---
        if "tomorrow" in cmd_lower:
            day_offset = 1
        else:
            day_offset = 0  # Default today

        start = (now + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        end = start + timedelta(hours=1)

        # --- Extract title ---
        # Try quoted title first
        title_match = re.search(r'["\']([^"\']+)["\']', cmd)
        if title_match:
            title = title_match.group(1)
        else:
            # Build title from context: strip command keywords, keep meaningful words
            _strip_words = {
                "ok", "schedule", "create", "add", "book", "set", "up", "new", "make",
                "one", "for", "at", "a", "an", "the", "my", "in", "on", "with",
                "event", "google", "calendar", "calander", "calender", "calandar",
                "please", "can", "you", "do", "it", "tomorrow", "today",
                "am", "pm",
            }
            # Remove the time pattern from the string
            cleaned = re.sub(r'\d{1,2}:\d{2}\s*(am|pm)?|\d{1,2}\s*(am|pm)', '', cmd_lower).strip()
            words = [w for w in cleaned.split() if w not in _strip_words and not w.isdigit()]
            title = " ".join(words).strip().title() if words else "Meeting"

        result = self._mcp_manager.call_tool_sync(
            server, "create-event",
            {
                "calendarId": "primary",
                "summary": title,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "timeZone": self._CALENDAR_TZ,
            },
        )
        time_str = start.strftime("%H:%M")
        day_str = "tomorrow" if day_offset else "today"
        return True, f"**Event created:** {title} at {time_str} {day_str}"

    # =========================================================================
    # Notion
    # =========================================================================

    def _execute_notion(self, command: str) -> Tuple[bool, str]:
        """Execute Notion commands via MCP.

        Tool names: API-post-search, API-post-page, API-patch-block-children,
                    API-query-data-source, API-retrieve-a-database.
        """
        try:
            server = self._find_server("notion")
            if not server:
                diagnosis = self._diagnose_server("notion")
                return False, f"No Notion MCP server connected.\n\n{diagnosis}"

            cmd = command.lower().strip()

            # --- Search ---
            if cmd == "" or cmd.startswith("search"):
                query = command[6:].strip() if cmd.startswith("search") else ""
                result = self._mcp_manager.call_tool_sync(
                    server, "API-post-search",
                    {"query": query, "page_size": 10},
                )
                text = self._extract_mcp_result(result)
                return True, f"**Notion Search Results:**\n\n{text}" if text else (True, "No results found.")

            # --- List databases ---
            elif "database" in cmd or cmd == "list":
                result = self._mcp_manager.call_tool_sync(
                    server, "API-post-search",
                    {"query": "", "filter": {"property": "object", "value": "database"}, "page_size": 20},
                )
                text = self._extract_mcp_result(result)
                return True, f"**Notion Databases:**\n\n{text}" if text else (True, "No databases found.")

            # --- Write-intent: add/create/make/put/todo/note, or "<X> in/to <db>" ---
            elif (any(k in cmd for k in ("create", "make", "add", "new", "todo", "note", "put"))
                  or (" in " in cmd or " to " in cmd)):
                return self._notion_write(server, command)

            else:
                # Default: search
                result = self._mcp_manager.call_tool_sync(
                    server, "API-post-search",
                    {"query": command, "page_size": 10},
                )
                text = self._extract_mcp_result(result)
                return True, f"**Notion Results:**\n\n{text}" if text else (True, "No results found.")

        except Exception as e:
            logger.error(f"Notion execution error: {e}", exc_info=True)
            return False, f"Notion error: {str(e)}"

    def _notion_write(self, server: str, command: str) -> Tuple[bool, str]:
        """Parse NL write commands and add items to a Notion database.

        Strategy: split on the LAST occurrence of ' in ' or ' to ' to separate
        the item from the database name.  This handles any characters in database
        names (colons, spaces, unicode, etc.) without fragile regex.

        Examples:
          "add buy the apple in my:list"     → db=my:list,   item=buy apple
          "add buy apple in my_list"         → db=my_list,   item=buy apple
          "add buy apple to shopping"        → db=shopping,  item=buy apple
          "add to todo buy apple"            → db=todo,      item=buy apple
          "add to my:list buy some bananas"  → db=my:list,   item=buy some bananas
          "make a todo to buy apple"         → db=todo,      item=buy apple
        """
        import re as _re

        cmd = command.lower().strip()

        # Filler words to strip from the item portion
        _filler = {"a", "the", "page", "note", "item", "entry", "notion", "please", "my"}

        # --- Special: "add to <db> <item>" (db right after "to", item is the rest) ---
        m = _re.match(r'(?:add|put)\s+to\s+(\S+)\s+(.+)', cmd)
        if m:
            db_hint = m.group(1).strip()
            item_title = m.group(2).strip()
            return self._notion_add_to_db(server, item_title, db_hint)

        # --- Special: "make/create a todo to <item>" → db=todo ---
        m = _re.match(r'(?:make|create|new)\s+(?:a\s+)?todo\b[:\s]*(?:to\s+)?(.+)', cmd)
        if m:
            item_title = m.group(1).strip()
            return self._notion_add_to_db(server, item_title, "todo")

        # --- General: split on LAST " in " or " to " ---
        # Try " in " first (stronger signal for a container), then " to "
        db_hint = ""
        item_raw = ""
        for prep in (" in ", " to "):
            pos = cmd.rfind(prep)
            if pos > 0:
                before = cmd[:pos].strip()
                after = cmd[pos + len(prep):].strip()
                if after:
                    db_hint = after
                    item_raw = before
                    break

        if db_hint and item_raw:
            # Strip leading verb (add/put/create/make/new)
            item_raw = _re.sub(r'^(?:add|put|create|make|new)\s+', '', item_raw)
            # Strip trailing noise like "put it", "put", "and put"
            item_raw = _re.sub(r'\s+(?:and\s+)?put\s*(?:it|them|this)?\s*$', '', item_raw)
            # Strip filler words and quotes
            words = [w for w in item_raw.split() if w.lower() not in _filler]
            item_title = " ".join(words).strip().strip('"\'')
            if item_title:
                return self._notion_add_to_db(server, item_title, db_hint)

        # --- Keyword "todo" anywhere → treat as todo db ---
        if "todo" in cmd:
            _strip = _filler | {"create", "make", "add", "new", "todo", "to", "for", "in"}
            words = [w for w in command.split() if w.lower() not in _strip]
            item_title = " ".join(words).strip() or "Untitled"
            return self._notion_add_to_db(server, item_title, "todo")

        # --- Fallback: strip verb/filler, search for db matching first word ---
        item_raw = _re.sub(r'^(?:add|put|create|make|new)\s+', '', cmd)
        words = [w for w in item_raw.split() if w.lower() not in _filler]
        if len(words) >= 2:
            # Guess: first word is db, rest is item
            return self._notion_add_to_db(server, " ".join(words[1:]), words[0])
        elif words:
            # Single word — use it as both search query and item title
            return self._notion_add_to_db(server, words[0], words[0])

        return False, "Could not parse your request. Try: `/notion add <item> in <database>`"

    def _notion_add_to_db(self, server: str, item_title: str, db_hint: str) -> Tuple[bool, str]:
        """Find a Notion database by name and add an item to it."""
        import json as _json
        logger.info(f"Notion add-to-db: db_hint={db_hint!r}, item={item_title!r}")

        # Search for the database
        search_result = self._mcp_manager.call_tool_sync(
            server, "API-post-search",
            {"query": db_hint, "filter": {"property": "object", "value": "database"}, "page_size": 3},
        )
        text = self._extract_mcp_result(search_result)
        try:
            data = _json.loads(text)
            results = data.get("results", [])
        except (ValueError, TypeError):
            results = []

        if not results:
            # Check if the integration has access to ANYTHING
            try:
                any_result = self._mcp_manager.call_tool_sync(
                    server, "API-post-search", {"query": "", "page_size": 1},
                )
                any_text = self._extract_mcp_result(any_result)
                any_data = _json.loads(any_text)
                has_any = bool(any_data.get("results"))
            except Exception:
                has_any = False

            if not has_any:
                return False, (
                    f"**Database '{db_hint}' not found** — your Notion integration "
                    "has no access to any pages or databases.\n\n"
                    "**How to fix:**\n"
                    "1. Open your Notion workspace in a browser\n"
                    "2. Go to the page/database you want to share\n"
                    "3. Click **...** (top-right) → **Connections** → add your integration\n"
                    "4. Try again\n\n"
                    "If you haven't created a database yet, create one in Notion first, "
                    "then share it with the integration."
                )

            return False, (
                f"**Database '{db_hint}' not found** in Notion.\n\n"
                "The integration can see some content but not this database.\n"
                "Make sure:\n"
                "1. A database named **{db_hint}** exists\n"
                "2. It's shared with your integration (click **...** → **Connections**)\n"
                "3. Try `/notion list` to see available databases"
            )

        db = results[0]
        db_id = db.get("id", "")

        # Detect the title property name from the database schema
        title_prop = "Name"  # default
        props = db.get("properties", {})
        for prop_name, prop_def in props.items():
            if prop_def.get("type") == "title":
                title_prop = prop_name
                break

        # Create a page in the database
        add_result = self._mcp_manager.call_tool_sync(
            server, "API-post-page",
            {
                "parent": {"type": "database_id", "database_id": db_id},
                "properties": {
                    title_prop: {"title": [{"text": {"content": item_title}}]},
                },
            },
        )
        add_text = self._extract_mcp_result(add_result)
        if "error" in str(add_text).lower():
            return False, f"Failed to add item: {add_text}"

        db_title = ""
        for t in db.get("title", []):
            db_title += t.get("plain_text", "")
        db_label = db_title or db_hint

        return True, f"**Added to {db_label}:** {item_title}"

    def _parse_search_results(self, raw_snapshot: str) -> str:
        """Parse browser snapshot to extract clean search results.

        Args:
            raw_snapshot: Raw accessibility tree from Playwright

        Returns:
            Cleaned and formatted search results
        """
        results = []
        lines = raw_snapshot.split('\n')

        current_result = {"title": "", "url": "", "snippet": ""}
        in_result = False

        for line in lines:
            line = line.strip()

            # Skip navigation, ads, and UI elements
            if any(skip in line.lower() for skip in [
                'button', 'combobox', 'navigation', 'search by',
                'settings', 'sign in', 'accessibility', 'skip to',
                'google apps', 'cursor=pointer', '[ref=', 'img [ref',
                'filters and topics', 'all types'
            ]):
                continue

            # Look for links with URLs (search results)
            if 'link "' in line and '/url:' in line:
                # Extract title from link
                title_match = re.search(r'link "([^"]+)"', line)
                if title_match:
                    title = title_match.group(1)
                    # Skip if it's a navigation link
                    if title.lower() in ['all', 'news', 'images', 'videos', 'maps', 'shopping', 'more']:
                        continue
                    current_result["title"] = title
                    in_result = True

            elif '/url: http' in line and in_result:
                # Extract URL
                url_match = re.search(r'/url:\s*(https?://[^\s]+)', line)
                if url_match:
                    url = url_match.group(1)
                    # Skip Google internal URLs
                    if 'google.com/search' not in url and 'accounts.google' not in url:
                        current_result["url"] = url

            elif in_result and current_result["title"] and not current_result["snippet"]:
                # Look for snippet text (generic text after the link)
                if 'generic' in line.lower() or 'statictext' in line.lower():
                    text_match = re.search(r':\s*(.+)$', line)
                    if text_match:
                        snippet = text_match.group(1).strip()
                        if len(snippet) > 20 and not snippet.startswith('['):
                            current_result["snippet"] = snippet

            # If we have a complete result, save it
            if current_result["title"] and current_result["url"]:
                if current_result not in results:
                    results.append(current_result.copy())
                current_result = {"title": "", "url": "", "snippet": ""}
                in_result = False

            # Limit to top 5 results
            if len(results) >= 5:
                break

        # Format results
        if not results:
            # Fallback: try to extract any meaningful text
            clean_text = []
            for line in lines:
                # Look for text content
                if 'statictext' in line.lower() or ('generic' in line.lower() and ':' in line):
                    text_match = re.search(r':\s*([^[\]]+)$', line)
                    if text_match:
                        text = text_match.group(1).strip()
                        if len(text) > 30 and text not in clean_text:
                            clean_text.append(text)
                            if len(clean_text) >= 5:
                                break

            if clean_text:
                return "\n\n".join(clean_text[:5])
            return "Could not parse search results. Please try a different search."

        formatted = []
        for i, r in enumerate(results[:5], 1):
            entry = f"**{i}. {r['title']}**"
            if r['url']:
                entry += f"\n   {r['url']}"
            if r['snippet']:
                entry += f"\n   {r['snippet'][:200]}"
            formatted.append(entry)

        return "\n\n".join(formatted)

    def _execute_google_search(self, query: str) -> Tuple[bool, str]:
        """Execute Google search via Playwright MCP.

        Args:
            query: Search query

        Returns:
            Tuple of (success, result_message)
        """
        try:
            server = self._find_server("google-search")
            if not server:
                diagnosis = self._diagnose_server("google-search")
                return False, f"❌ No browser MCP server connected.\n\n{diagnosis}"

            if not query.strip():
                return False, "Please provide a search query. Example: /google-search AI news"

            # Navigate to Google
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            logger.info(f"[google-search] Navigating to: {search_url}")

            self._mcp_manager.call_tool_sync(
                server, "browser_navigate", {"url": search_url}
            )

            # Get page snapshot
            result = self._mcp_manager.call_tool_sync(
                server, "browser_snapshot", {}
            )
            raw_snapshot = self._extract_mcp_result(result)

            # Close browser
            try:
                self._mcp_manager.call_tool_sync(server, "browser_close", {})
            except Exception:
                pass

            if len(raw_snapshot.strip()) < 50:
                return False, "Search executed but could not extract results."

            # Parse and clean the results
            clean_results = self._parse_search_results(raw_snapshot)

            return True, f"🔍 **Search Results for '{query}':**\n\n{clean_results}"

        except Exception as e:
            logger.error(f"Google search error: {e}", exc_info=True)
            try:
                self._mcp_manager.call_tool_sync(server, "browser_close", {})
            except Exception:
                pass
            return False, f"❌ Search error: {str(e)}"

    def _parse_page_content(self, raw_snapshot: str) -> str:
        """Parse browser snapshot to extract clean page content.

        Args:
            raw_snapshot: Raw accessibility tree from Playwright

        Returns:
            Cleaned page content
        """
        clean_text = []
        lines = raw_snapshot.split('\n')

        for line in lines:
            line = line.strip()

            # Skip UI elements and navigation
            if any(skip in line.lower() for skip in [
                'button', 'combobox', 'cursor=pointer', '[ref=',
                'img [ref', 'navigation', 'banner', 'contentinfo',
                'menu', 'menuitem', 'toolbar', 'tablist'
            ]):
                continue

            # Extract text content from headings, paragraphs, etc.
            if any(content_type in line.lower() for content_type in [
                'heading', 'paragraph', 'statictext', 'text',
                'article', 'main', 'section'
            ]):
                # Try to extract the text content
                text_match = re.search(r':\s*([^[\]]{20,})$', line)
                if text_match:
                    text = text_match.group(1).strip()
                    if text and text not in clean_text:
                        clean_text.append(text)

            # Also look for generic text blocks
            elif 'generic' in line.lower() and ':' in line:
                text_match = re.search(r':\s*([^[\]]{30,})$', line)
                if text_match:
                    text = text_match.group(1).strip()
                    if text and text not in clean_text:
                        clean_text.append(text)

            # Limit content
            if len(clean_text) >= 20:
                break

        if clean_text:
            return "\n\n".join(clean_text)

        # Fallback: return truncated raw content with basic cleanup
        # Remove obvious UI elements
        cleaned = re.sub(r'\[ref=\w+\]', '', raw_snapshot)
        cleaned = re.sub(r'\[cursor=pointer\]', '', cleaned)
        cleaned = re.sub(r'button|combobox|navigation', '', cleaned, flags=re.IGNORECASE)
        return cleaned[:3000]

    def _execute_browse(self, url: str) -> Tuple[bool, str]:
        """Browse a URL via Playwright MCP.

        Args:
            url: URL to browse

        Returns:
            Tuple of (success, result_message)
        """
        try:
            server = self._find_server("browse")
            if not server:
                diagnosis = self._diagnose_server("browse")
                return False, f"❌ No browser MCP server connected.\n\n{diagnosis}"

            url = url.strip()
            if not url:
                return False, "Please provide a URL. Example: /browse https://example.com"

            if not url.startswith("http"):
                url = "https://" + url

            logger.info(f"[browse] Opening URL: {url}")

            self._mcp_manager.call_tool_sync(
                server, "browser_navigate", {"url": url}
            )

            result = self._mcp_manager.call_tool_sync(
                server, "browser_snapshot", {}
            )
            raw_snapshot = self._extract_mcp_result(result)

            try:
                self._mcp_manager.call_tool_sync(server, "browser_close", {})
            except Exception:
                pass

            if len(raw_snapshot.strip()) < 50:
                return False, f"Opened {url} but could not extract content."

            # Parse and clean the content
            clean_content = self._parse_page_content(raw_snapshot)

            return True, f"🌐 **Content from {url}:**\n\n{clean_content}"

        except Exception as e:
            logger.error(f"Browse error: {e}", exc_info=True)
            try:
                self._mcp_manager.call_tool_sync(server, "browser_close", {})
            except Exception:
                pass
            return False, f"❌ Browse error: {str(e)}"


# =============================================================================
# Singleton instance for easy access
# =============================================================================
_skill_executor: Optional[SkillExecutor] = None


def get_skill_executor() -> SkillExecutor:
    """Get the global skill executor instance."""
    global _skill_executor
    if _skill_executor is None:
        _skill_executor = SkillExecutor()
    return _skill_executor


def set_skill_executor_mcp(mcp_manager: "MCPManager"):
    """Set the MCP manager for the global skill executor."""
    get_skill_executor().set_mcp_manager(mcp_manager)


# =============================================================================
'''
    End of skill_executor.py
'''
# =============================================================================
