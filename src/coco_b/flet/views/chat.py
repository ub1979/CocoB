"""
ChatView — chat UI with message handling, skill suggestions, and typing indicator.
"""

import asyncio
import time
import threading
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import flet as ft
from flet import Icons as icons

from coco_b import PROJECT_ROOT
from coco_b.flet.theme import AppColors, format_timestamp
from coco_b.flet.components.chat_message import ChatMessage
from coco_b.flet.components.widgets import StatusBadge


class ChatView:
    """Chat view — message list, input, skill popup, and typing indicator."""

    def __init__(self, page: ft.Page, app_state, skills_manager, mcp_manager,
                 session_manager, router, secure_storage):
        self.page = page
        self.app_state = app_state
        self.skills_manager = skills_manager
        self.mcp_manager = mcp_manager
        self.session_manager = session_manager
        self.router = router
        self.secure_storage = secure_storage
        self.current_user_id = "user-001"
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._is_processing = False
        self._typing_row: Optional[ft.Row] = None

    def build(self) -> ft.Column:
        """Build and return the chat view."""
        icon_path = PROJECT_ROOT / "icon" / "coco_b_icon.png"
        header = ft.Row([
            ft.Image(src=str(icon_path), width=40, height=40) if icon_path.exists() else ft.Container(),
            ft.Text("coco B Chat", size=20, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
            ft.Container(expand=True),
            StatusBadge("Online", "success"),
        ])

        self.model_info_text = ft.Text(self._get_current_model_info(), size=13, color=AppColors.TEXT_PRIMARY)

        user_bar = ft.Row([
            ft.Text("User:", size=12, color=AppColors.TEXT_SECONDARY),
            ft.TextField(
                value=self.current_user_id,
                on_change=lambda e: setattr(self, 'current_user_id', e.control.value),
                width=150, height=35, text_size=12,
                border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY,
            ),
            ft.Container(width=20),
            ft.Text("Model:", size=12, color=AppColors.TEXT_SECONDARY),
            self.model_info_text,
            ft.IconButton(icon=icons.REFRESH, on_click=self._refresh_model_info, icon_size=16, icon_color=AppColors.TEXT_SECONDARY),
        ])

        self.messages_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)

        # Welcome message
        welcome_text = "Hello! I'm coco B.\n\n**Commands:**\n- /help - Show commands\n- /reset - Reset chat\n- /stats - Statistics\n- /skills - List skills"
        if self.skills_manager:
            skills = self.skills_manager.get_user_invocable_skills()
            if skills:
                welcome_text += "\n\n**Skills:** "
                welcome_text += ", ".join([f"/{s.name}" for s in skills[:5]])
                if len(skills) > 5:
                    welcome_text += f" (+{len(skills) - 5} more)"

        self.messages_list.controls.append(ChatMessage(
            text=welcome_text, is_user=False, timestamp=datetime.now().strftime("%H:%M")
        ))

        self.message_input = ft.TextField(
            hint_text="Type / for commands...",
            expand=True, multiline=True, min_lines=1, max_lines=3,
            on_submit=self._send_message, on_change=self._on_input_change,
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY,
            bgcolor=AppColors.SURFACE, shift_enter=True,
        )

        send_button = ft.IconButton(
            icon=icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
            bgcolor=AppColors.PRIMARY, on_click=self._send_message,
        )

        self.skills_popup = ft.Column(controls=[], spacing=2, visible=False)
        self.skills_popup_container = ft.Container(
            content=self.skills_popup, bgcolor=AppColors.SURFACE,
            border=ft.border.all(1, AppColors.BORDER),
            border_radius=ft.border_radius.all(8),
            padding=ft.padding.all(8), visible=False,
        )

        input_row = ft.Row([self.message_input, send_button], spacing=10)

        return ft.Column([
            header, ft.Divider(height=1), user_bar, ft.Divider(height=1),
            self.messages_list, ft.Divider(height=1),
            self.skills_popup_container, input_row,
        ], expand=True, spacing=10)

    # ── Typing indicator ─────────────────────────────────────────────────

    def _show_typing_indicator(self):
        """Show animated typing indicator."""
        self._typing_row = ft.Row([
            ft.ProgressRing(width=16, height=16, stroke_width=2),
            ft.Text("coco B is thinking...", color=AppColors.TEXT_MUTED, italic=True, size=13),
        ], spacing=8)
        self.messages_list.controls.append(self._typing_row)
        try:
            self.page.update()
        except Exception:
            pass

    def _hide_typing_indicator(self):
        """Remove typing indicator."""
        if self._typing_row and self._typing_row in self.messages_list.controls:
            self.messages_list.controls.remove(self._typing_row)
        self._typing_row = None

    # ── Model info ───────────────────────────────────────────────────────

    def _get_current_model_info(self):
        if self.app_state:
            info = self.app_state.get_current_provider_info()
            return f"{info['provider_name']}: {info['model_name']}"
        return "Not connected"

    def _refresh_model_info(self, e=None):
        if hasattr(self, 'model_info_text'):
            self.model_info_text.value = self._get_current_model_info()
        self.page.update()

    # ── Input handling ───────────────────────────────────────────────────

    def _on_input_change(self, e):
        """Show skill suggestions when typing /."""
        text = e.control.value
        if text.startswith("/"):
            cmd = text[1:].lower()
            suggestions = []
            builtins = [
                ("help", "Show available commands"),
                ("reset", "Reset conversation"),
                ("stats", "Show session statistics"),
                ("skills", "List all skills"),
            ]
            for name, desc in builtins:
                if cmd == "" or name.startswith(cmd):
                    suggestions.append((name, desc, False))
            if self.skills_manager:
                for skill in self.skills_manager.get_user_invocable_skills():
                    if cmd == "" or skill.name.lower().startswith(cmd):
                        emoji = f"{skill.emoji} " if skill.emoji else ""
                        suggestions.append((skill.name, f"{emoji}{skill.description}", True))
            if suggestions:
                self.skills_popup.controls.clear()
                for name, desc, is_skill in suggestions[:8]:
                    btn = ft.TextButton(
                        content=ft.Row([
                            ft.Text(f"/{name}", weight=ft.FontWeight.BOLD, size=13, color=AppColors.PRIMARY),
                            ft.Text(f" - {desc}", size=12, color=AppColors.TEXT_SECONDARY),
                        ]),
                        on_click=lambda e, n=name: self._select_skill(n),
                    )
                    self.skills_popup.controls.append(btn)
                self.skills_popup.visible = True
                self.skills_popup_container.visible = True
            else:
                self.skills_popup.visible = False
                self.skills_popup_container.visible = False
        else:
            self.skills_popup.visible = False
            self.skills_popup_container.visible = False
        self.page.update()

    def _select_skill(self, skill_name: str):
        self.message_input.value = f"/{skill_name} "
        self.message_input.focus()
        self.skills_popup.visible = False
        self.skills_popup_container.visible = False
        self.page.update()

    # ── Send & Process ───────────────────────────────────────────────────

    def _send_message(self, e):
        """Send message — handles commands and regular messages."""
        text = self.message_input.value.strip()
        if not text or self._is_processing:
            return

        self.message_input.value = ""
        self.page.update()

        if text.startswith("/") and self.router:
            is_skill, skill_name, remaining = self.router.is_skill_invocation(text)
            if not is_skill:
                self._handle_command(text)
                return

        self.messages_list.controls.append(
            ChatMessage(text=text, is_user=True, timestamp=datetime.now().strftime("%H:%M"))
        )
        self.page.update()
        self.page.run_task(self._process_bot_response, text)

    async def _process_bot_response(self, user_message: str):
        """Process bot response using streaming on Flet's event loop."""
        if self._is_processing:
            return
        self._is_processing = True
        self._show_typing_indicator()
        self._last_ui_update = 0.0

        try:
            if self.router:
                is_skill, skill_name, remaining = self.router.is_skill_invocation(user_message)
                skill_context = ""
                effective_message = user_message

                if is_skill:
                    skill_context = self.router.get_skill_context(skill_name)
                    effective_message = remaining if remaining else f"Execute the {skill_name} skill"

                    if skill_name == "google-search":
                        if self.mcp_manager and self.mcp_manager.is_connected('playwright'):
                            query = remaining if remaining else "google search test"
                            search_results = await asyncio.to_thread(self._execute_google_search, query)
                            if search_results and len(search_results) > 50:
                                skill_context += f"\n\n## Live Search Results\n\nI executed a Google search for '{query}'. Here are the results:\n\n{search_results}\n\nPlease summarize these search results for the user. DO NOT say you cannot access the web - the results are provided above."
                                effective_message = f"Summarize the search results for: {query}"
                        elif self.mcp_manager and not self.mcp_manager.is_connected('playwright'):
                            skill_context += "\n\n**ERROR**: Playwright MCP is not connected. Please go to MCP Tools tab and connect Playwright first."

                    elif skill_name == "browse":
                        if self.mcp_manager and self.mcp_manager.is_connected('playwright'):
                            url = remaining.strip() if remaining else "https://google.com"
                            if not url.startswith("http"):
                                url = "https://" + url
                            browse_results = await asyncio.to_thread(self._execute_browse, url)
                            if browse_results:
                                skill_context += f"\n\n## Page Content\n\nI opened {url} in the browser. Here's the page content:\n\n{browse_results}\n\nDescribe what you see on this page."
                                effective_message = f"Describe the content from {url}"
                        elif self.mcp_manager and not self.mcp_manager.is_connected('playwright'):
                            skill_context += "\n\n**ERROR**: Playwright MCP is not connected. Please go to MCP Tools tab and connect Playwright first."

                    elif skill_name == "email":
                        if self.mcp_manager and self.mcp_manager.is_connected('google-workspace'):
                            result = await asyncio.to_thread(self._execute_email, remaining)
                            if result:
                                self._update_bot_message(result, is_partial=False)
                                return

                    elif skill_name == "calendar":
                        if self.mcp_manager and self.mcp_manager.is_connected('google-workspace'):
                            result = await asyncio.to_thread(self._execute_calendar, remaining)
                            if result:
                                self._update_bot_message(result, is_partial=False)
                                return

                full_text = ""
                replace_marker = "\n\n<!--REPLACE_RESPONSE-->\n"
                async for chunk in self.router.handle_message_stream(
                    channel="flet", user_id=self.current_user_id,
                    user_message=effective_message, chat_id=None,
                    user_name="Flet User",
                    skill_context=skill_context if skill_context else None,
                ):
                    full_text += chunk
                    if replace_marker in full_text:
                        full_text = full_text.split(replace_marker, 1)[1]
                    now = time.monotonic()
                    if now - self._last_ui_update >= 0.1:
                        self._update_bot_message(full_text, is_partial=True)
                        self._last_ui_update = now
                if replace_marker in full_text:
                    full_text = full_text.split(replace_marker, 1)[1]
                self._update_bot_message(full_text, is_partial=False)

            else:
                await asyncio.sleep(1)
                self._update_bot_message(
                    f"**Demo Mode**\n\nReceived: '{user_message[:50]}...'\n\n(Connect to bot backend for real responses)",
                    is_partial=False,
                )

        except Exception as ex:
            import traceback
            error_msg = f"**Error:** {str(ex)}"
            traceback.print_exc()

            error_str = str(ex)
            if "Connection refused" in error_str or "ConnectionError" in error_str:
                provider_info = self.app_state.get_current_provider_info() if self.app_state else {}
                base_url = provider_info.get("base_url", "")
                if "8080" in base_url:
                    error_msg = "**MLX server not running!**\n\nStart it in a terminal:\n```\nmlx_lm.server --model <model> --port 8080\n```"
                elif "11434" in base_url:
                    error_msg = "**Ollama not running!**\n\nStart it in a terminal:\n```\nollama serve\n```"
                elif "1234" in base_url:
                    error_msg = "**LM Studio server not running!**\n\nOpen LM Studio and start the server."

            self._update_bot_message(error_msg, is_partial=False)

        finally:
            self._is_processing = False

    def _update_bot_message(self, text: str, is_partial: bool = False):
        """Replace typing indicator (or last partial) with the response."""
        self._hide_typing_indicator()

        # Also remove any previous partial bot response
        if self.messages_list.controls:
            last_msg = self.messages_list.controls[-1]
            if hasattr(last_msg, '_is_bot_response') and last_msg._is_bot_response:
                self.messages_list.controls.pop()

        new_msg = ChatMessage(text=text, is_user=False, timestamp=datetime.now().strftime("%H:%M"))
        new_msg._is_bot_response = True
        self.messages_list.controls.append(new_msg)
        try:
            self.page.update()
        except Exception:
            pass

    # ── Commands ─────────────────────────────────────────────────────────

    def _handle_command(self, cmd):
        cmd_lower = cmd.lower().strip()
        if self.router and self.session_manager:
            session_key = self.session_manager.get_session_key("flet", self.current_user_id)
            if cmd_lower in ["/reset", "/new"]:
                response = self.router.handle_command(cmd, session_key)
                self.messages_list.controls.clear()
                self.messages_list.controls.append(
                    ChatMessage(text=response, is_user=False, timestamp=datetime.now().strftime("%H:%M"))
                )
                self.page.update()
                return
            response = self.router.handle_command(cmd, session_key)
        else:
            responses = {
                "/help": "**Commands:**\n- /help - Show help\n- /reset - Reset chat\n- /stats - Statistics\n- /skills - List skills",
                "/reset": "Cannot reset: Router not available",
                "/stats": self._get_stats_text(),
            }
            response = responses.get(cmd_lower, f"Unknown command: {cmd}")

        if response:
            self.messages_list.controls.append(
                ChatMessage(text=response, is_user=False, timestamp=datetime.now().strftime("%H:%M"))
            )
            self.page.update()

    def _get_stats_text(self):
        if not self.session_manager:
            return "No session manager"
        stats = self.session_manager.get_session_stats(self.session_manager.get_session_key("flet", self.current_user_id))
        if not stats:
            return "No active session"
        return f"**Session Stats**\nMessages: {stats['messageCount']}\nCreated: {format_timestamp(stats['createdAt'])}"

    # ── MCP skill helpers ────────────────────────────────────────────────

    def _extract_mcp_result(self, result) -> str:
        if isinstance(result, dict):
            if "content" in result:
                content = result["content"]
                if isinstance(content, list):
                    return "\n".join(item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in content)
                return str(content)
            elif "text" in result:
                return result["text"]
            return str(result)
        return str(result)

    def _execute_browse(self, url: str) -> str:
        if not self.mcp_manager or not self.mcp_manager.is_connected("playwright"):
            return ""
        try:
            self.mcp_manager.call_tool_sync("playwright", "browser_navigate", {"url": url})
            time.sleep(3)
            snapshot_result = self.mcp_manager.call_tool_sync("playwright", "browser_snapshot", {})
            result_text = self._extract_mcp_result(snapshot_result)
            if len(result_text.strip()) < 100:
                try:
                    eval_result = self.mcp_manager.call_tool_sync("playwright", "browser_evaluate", {"function": "() => document.body.innerText"})
                    result_text = self._extract_mcp_result(eval_result)
                except Exception:
                    pass
            return result_text[:8000]
        except Exception as e:
            return f"Error browsing: {str(e)}"

    def _execute_google_search(self, query: str) -> str:
        if not self.mcp_manager or not self.mcp_manager.is_connected("playwright"):
            return ""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            self.mcp_manager.call_tool_sync("playwright", "browser_navigate", {"url": search_url})
            time.sleep(3)
            snapshot_result = self.mcp_manager.call_tool_sync("playwright", "browser_snapshot", {})
            result_text = self._extract_mcp_result(snapshot_result)
            if len(result_text.strip()) < 200:
                try:
                    eval_result = self.mcp_manager.call_tool_sync("playwright", "browser_evaluate", {"function": "() => document.body.innerText"})
                    eval_text = self._extract_mcp_result(eval_result)
                    if len(eval_text) > len(result_text):
                        result_text = eval_text
                except Exception:
                    pass
            try:
                self.mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except Exception:
                pass
            return result_text[:8000] if len(result_text.strip()) >= 50 else "Search executed but could not extract results."
        except Exception as e:
            try:
                self.mcp_manager.call_tool_sync("playwright", "browser_close", {})
            except Exception:
                pass
            return f"Error executing search: {str(e)}"

    def _execute_email(self, command: str) -> str:
        try:
            import re
            cmd = command.lower().strip()
            if cmd.startswith("check") or cmd.startswith("inbox") or cmd == "":
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-emails", {"maxResults": 5})
                return f"**Recent Emails:**\n\n{self._extract_mcp_result(result)}"
            elif cmd.startswith("unread"):
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-emails", {"query": "is:unread", "maxResults": 10})
                return f"**Unread Emails:**\n\n{self._extract_mcp_result(result)}"
            elif cmd.startswith("search "):
                query = command[7:].strip()
                result = self.mcp_manager.call_tool_sync("google-workspace", "search-emails", {"query": query, "maxResults": 10})
                return f"**Search Results for '{query}':**\n\n{self._extract_mcp_result(result)}"
            elif cmd.startswith("send "):
                to_match = re.search(r'to\s+(\S+)', command, re.IGNORECASE)
                subject_match = re.search(r'subject\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
                body_match = re.search(r'body\s+["\']([^"\']+)["\']', command, re.IGNORECASE)
                if to_match:
                    to_email = to_match.group(1)
                    subject = subject_match.group(1) if subject_match else "No Subject"
                    body = body_match.group(1) if body_match else ""
                    self.mcp_manager.call_tool_sync("google-workspace", "send-email", {"to": to_email, "subject": subject, "body": body})
                    return f"Email sent to {to_email}"
                return "Could not parse email. Use: /email send to email@example.com subject \"Subject\" body \"Message\""
            return "**Email Commands:**\n- `/email` or `/email inbox` - Check inbox\n- `/email unread` - Show unread\n- `/email search <query>` - Search emails\n- `/email send to <email> subject \"...\" body \"...\"`"
        except Exception as e:
            return f"Email error: {str(e)}"

    def _execute_calendar(self, command: str) -> str:
        try:
            cmd = command.lower().strip()
            import re
            if cmd == "" or cmd == "today" or "today" in cmd:
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-events", {"timeMin": "today", "maxResults": 10})
                events = self._extract_mcp_result(result)
                return "No events scheduled for today." if not events or "no events" in events.lower() else f"**Today's Events:**\n\n{events}"
            elif "tomorrow" in cmd:
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-events", {"timeMin": "tomorrow", "maxResults": 10})
                events = self._extract_mcp_result(result)
                return "No events scheduled for tomorrow." if not events or "no events" in events.lower() else f"**Tomorrow's Events:**\n\n{events}"
            elif "week" in cmd:
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-events", {"timeMin": "today", "timeMax": "+7d", "maxResults": 20})
                events = self._extract_mcp_result(result)
                return "No events scheduled this week." if not events or "no events" in events.lower() else f"**This Week's Events:**\n\n{events}"
            elif cmd.startswith("create "):
                title_match = re.search(r'["\']([^"\']+)["\']', command)
                if title_match:
                    title = title_match.group(1)
                    time_part = command[command.find(title_match.group(0)) + len(title_match.group(0)):].strip()
                    self.mcp_manager.call_tool_sync("google-workspace", "create-event", {"title": title, "when": time_part if time_part else "tomorrow"})
                    return f"Created: {title}"
                return "Use: /calendar create \"Event Name\" tomorrow at 3pm"
            else:
                result = self.mcp_manager.call_tool_sync("google-workspace", "list-events", {"timeMin": "today", "maxResults": 10})
                events = self._extract_mcp_result(result)
                return "No events scheduled for today." if not events or "no events" in events.lower() else f"**Today's Events:**\n\n{events}"
        except Exception as e:
            return f"Calendar error: {str(e)}"

    def inject_scheduled_message(self, message: str):
        """Inject a message from the scheduler into the chat UI (thread-safe)."""
        def _do_inject():
            self.messages_list.controls.append(
                ChatMessage(
                    text=f"\u23f0 **Reminder:** {message}",
                    is_user=False,
                    timestamp=datetime.now().strftime("%H:%M"),
                )
            )
            try:
                self.page.update()
            except Exception:
                pass

        # Schedule on Flet's event loop — safe from any thread
        try:
            self.page.run_thread(_do_inject)
        except Exception:
            # Fallback: direct call (works if already on Flet thread)
            _do_inject()

    def cleanup(self):
        """Shutdown executor."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
