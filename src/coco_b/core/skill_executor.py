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

    Project : coco B - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

import re
import logging
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.core.mcp_client import MCPManager

logger = logging.getLogger("coco_b.skill_executor")


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

    def can_execute_directly(self, skill_name: str) -> bool:
        """Check if a skill can be executed directly via MCP.

        Args:
            skill_name: Name of the skill (without leading /)

        Returns:
            True if the skill has direct MCP execution support
        """
        return skill_name in ["email", "calendar", "google-search", "browse"]

    def execute(self, skill_name: str, args: str) -> Tuple[bool, str]:
        """Execute a skill directly via MCP.

        Args:
            skill_name: Name of the skill (without leading /)
            args: Arguments/command for the skill

        Returns:
            Tuple of (success, result_message)
        """
        if not self._mcp_manager:
            return False, "MCP manager not initialized. Please configure MCP tools first."

        if skill_name == "email":
            return self._execute_email(args)
        elif skill_name == "calendar":
            return self._execute_calendar(args)
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

    def _execute_email(self, command: str) -> Tuple[bool, str]:
        """Execute email commands directly via MCP.

        Args:
            command: Email command (e.g., "inbox", "unread", "search query")

        Returns:
            Tuple of (success, result_message)
        """
        try:
            # Check if google-workspace is connected
            if not self._mcp_manager.is_connected('google-workspace'):
                return False, "Google Workspace MCP not connected. Go to MCP Tools and connect google-workspace first."

            cmd = command.lower().strip()

            # Parse common email commands
            if cmd.startswith("check") or cmd.startswith("inbox") or cmd == "":
                # List recent emails
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-emails", {"maxResults": 5}
                )
                emails = self._extract_mcp_result(result)
                return True, f"📧 **Recent Emails:**\n\n{emails}"

            elif cmd.startswith("unread"):
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-emails", {"query": "is:unread", "maxResults": 10}
                )
                emails = self._extract_mcp_result(result)
                return True, f"📧 **Unread Emails:**\n\n{emails}"

            elif cmd.startswith("search "):
                query = command[7:].strip()
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "search-emails", {"query": query, "maxResults": 10}
                )
                emails = self._extract_mcp_result(result)
                return True, f"🔍 **Search Results for '{query}':**\n\n{emails}"

            elif cmd.startswith("send "):
                # Parse: send to email@example.com subject "Subject" body "Body"
                to_match = re.search(r'to\s+(\S+)', command, re.IGNORECASE)
                subject_match = re.search(r'subject\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
                body_match = re.search(r'body\s+["\']([^"\']+)["\']', command, re.IGNORECASE)

                if to_match:
                    to_email = to_match.group(1)
                    subject = subject_match.group(1) if subject_match else "No Subject"
                    body = body_match.group(1) if body_match else ""

                    result = self._mcp_manager.call_tool_sync(
                        "google-workspace", "send-email",
                        {"to": to_email, "subject": subject, "body": body}
                    )
                    return True, f"✅ Email sent to {to_email}"
                else:
                    return False, "❌ Could not parse email. Use: /email send to email@example.com subject \"Subject\" body \"Message\""

            else:
                return True, ("📧 **Email Commands:**\n"
                             "• `/email` or `/email inbox` - Check inbox\n"
                             "• `/email unread` - Show unread\n"
                             "• `/email search <query>` - Search emails\n"
                             "• `/email send to <email> subject \"...\" body \"...\"`")

        except Exception as e:
            logger.error(f"Email execution error: {e}", exc_info=True)
            return False, f"❌ Email error: {str(e)}"

    def _execute_calendar(self, command: str) -> Tuple[bool, str]:
        """Execute calendar commands directly via MCP.

        Args:
            command: Calendar command (e.g., "today", "tomorrow", "week")

        Returns:
            Tuple of (success, result_message)
        """
        try:
            # Check if google-workspace is connected
            if not self._mcp_manager.is_connected('google-workspace'):
                return False, "Google Workspace MCP not connected. Go to MCP Tools and connect google-workspace first."

            cmd = command.lower().strip()

            # Check for "today" related queries
            if cmd == "" or cmd == "today" or "today" in cmd:
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-events", {"timeMin": "today", "maxResults": 10}
                )
                events = self._extract_mcp_result(result)
                if not events or events.strip() == "" or "no events" in events.lower():
                    return True, "📅 No events scheduled for today."
                return True, f"📅 **Today's Events:**\n\n{events}"

            # Check for "tomorrow" related queries
            elif "tomorrow" in cmd:
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-events", {"timeMin": "tomorrow", "maxResults": 10}
                )
                events = self._extract_mcp_result(result)
                if not events or events.strip() == "" or "no events" in events.lower():
                    return True, "📅 No events scheduled for tomorrow."
                return True, f"📅 **Tomorrow's Events:**\n\n{events}"

            # Check for "week" related queries
            elif "week" in cmd:
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-events", {"timeMin": "today", "timeMax": "+7d", "maxResults": 20}
                )
                events = self._extract_mcp_result(result)
                if not events or events.strip() == "" or "no events" in events.lower():
                    return True, "📅 No events scheduled this week."
                return True, f"📅 **This Week's Events:**\n\n{events}"

            elif cmd.startswith("create "):
                # Parse: create "Event Name" tomorrow at 3pm
                title_match = re.search(r'["\']([^"\']+)["\']', command)

                if title_match:
                    title = title_match.group(1)
                    # Extract time info after the title
                    time_part = command[command.find(title_match.group(0)) + len(title_match.group(0)):].strip()

                    result = self._mcp_manager.call_tool_sync(
                        "google-workspace", "create-event",
                        {"title": title, "when": time_part if time_part else "tomorrow"}
                    )
                    return True, f"✅ Created: {title}"
                else:
                    return False, "❌ Use: /calendar create \"Event Name\" tomorrow at 3pm"

            else:
                # Default: show today's events for any other query
                result = self._mcp_manager.call_tool_sync(
                    "google-workspace", "list-events", {"timeMin": "today", "maxResults": 10}
                )
                events = self._extract_mcp_result(result)
                if not events or events.strip() == "" or "no events" in events.lower():
                    return True, "📅 No events scheduled for today."
                return True, f"📅 **Today's Events:**\n\n{events}"

        except Exception as e:
            logger.error(f"Calendar execution error: {e}", exc_info=True)
            return False, f"❌ Calendar error: {str(e)}"

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
            if not self._mcp_manager.is_connected('playwright'):
                return False, "Playwright MCP not connected. Go to MCP Tools and connect playwright first."

            if not query.strip():
                return False, "Please provide a search query. Example: /google-search AI news"

            # Navigate to Google
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            logger.info(f"[google-search] Navigating to: {search_url}")

            self._mcp_manager.call_tool_sync(
                "playwright", "browser_navigate", {"url": search_url}
            )

            # Get page snapshot
            result = self._mcp_manager.call_tool_sync(
                "playwright", "browser_snapshot", {}
            )
            raw_snapshot = self._extract_mcp_result(result)

            # Close browser
            try:
                self._mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except:
                pass

            if len(raw_snapshot.strip()) < 50:
                return False, "Search executed but could not extract results."

            # Parse and clean the results
            clean_results = self._parse_search_results(raw_snapshot)

            return True, f"🔍 **Search Results for '{query}':**\n\n{clean_results}"

        except Exception as e:
            logger.error(f"Google search error: {e}", exc_info=True)
            try:
                self._mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except:
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
            if not self._mcp_manager.is_connected('playwright'):
                return False, "Playwright MCP not connected. Go to MCP Tools and connect playwright first."

            url = url.strip()
            if not url:
                return False, "Please provide a URL. Example: /browse https://example.com"

            if not url.startswith("http"):
                url = "https://" + url

            logger.info(f"[browse] Opening URL: {url}")

            self._mcp_manager.call_tool_sync(
                "playwright", "browser_navigate", {"url": url}
            )

            result = self._mcp_manager.call_tool_sync(
                "playwright", "browser_snapshot", {}
            )
            raw_snapshot = self._extract_mcp_result(result)

            try:
                self._mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except:
                pass

            if len(raw_snapshot.strip()) < 50:
                return False, f"Opened {url} but could not extract content."

            # Parse and clean the content
            clean_content = self._parse_page_content(raw_snapshot)

            return True, f"🌐 **Content from {url}:**\n\n{clean_content}"

        except Exception as e:
            logger.error(f"Browse error: {e}", exc_info=True)
            try:
                self._mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except:
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
