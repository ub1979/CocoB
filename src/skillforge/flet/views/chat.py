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

from skillforge import PROJECT_ROOT
from skillforge.core.image_handler import Attachment
from skillforge.flet.theme import AppColors, format_timestamp
from skillforge.flet.components.chat_message import ChatMessage
from skillforge.flet.components.widgets import StatusBadge


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
        # Use the logged-in admin username so permissions match
        stored_name = ""
        if secure_storage:
            try:
                stored_name = secure_storage.get_admin_username()
            except Exception:
                pass
        self.current_user_id = stored_name or "user-001"
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._is_processing = False
        self._typing_row: Optional[ft.Row] = None
        self._pending_attachments: list = []  # List of Attachment objects
        self._suggestions: list = []  # Current popup suggestions
        self._selected_index: int = 0  # Highlighted index in popup
        self._focus_lock_until: float = 0.0

    def build(self) -> ft.Column:
        """Build and return the chat view."""
        icon_path = PROJECT_ROOT / "icon" / "icon.png"

        # Header with logo, title, and status
        logo = (ft.Image(src=str(icon_path), width=36, height=36)
                if icon_path.exists()
                else ft.Icon(icons.SMART_TOY, size=28, color=AppColors.SECONDARY))
        header = ft.Container(
            content=ft.Row([
                logo,
                ft.Column([
                    ft.Text("SkillForge Chat", size=18, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                    ft.Text(self._get_current_model_info(), size=11, color=AppColors.TEXT_MUTED),
                ], spacing=0, tight=True),
                ft.Container(expand=True),
                StatusBadge("Online", "success"),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=4, right=4, top=8, bottom=8),
        )

        self.model_info_text = ft.Text(self._get_current_model_info(), size=13, color=AppColors.TEXT_PRIMARY)

        # Compact user/model bar
        user_bar = ft.Container(
            content=ft.Row([
                ft.Icon(icons.PERSON, size=14, color=AppColors.TEXT_MUTED),
                ft.TextField(
                    value=self.current_user_id,
                    on_change=lambda e: setattr(self, 'current_user_id', e.control.value),
                    width=140, height=32, text_size=12, dense=True,
                    border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY,
                    content_padding=ft.Padding.only(left=8, right=8, top=4, bottom=4),
                ),
                ft.Container(expand=True),
                ft.Icon(icons.MEMORY, size=14, color=AppColors.TEXT_MUTED),
                self.model_info_text,
                ft.IconButton(icon=icons.REFRESH, on_click=self._refresh_model_info,
                              icon_size=14, icon_color=AppColors.TEXT_MUTED,
                              tooltip="Refresh model info"),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=AppColors.SURFACE_VARIANT,
            padding=ft.Padding.only(left=10, right=6, top=4, bottom=4),
            border_radius=ft.BorderRadius.all(8),
        )

        self.messages_list = ft.ListView(expand=True, spacing=8, auto_scroll=True,
                                          padding=ft.Padding.only(top=8, bottom=8))

        # Welcome message
        welcome_text = "Hello! I'm SkillForge.\n\n**Commands:**\n- /help - Show commands\n- /reset - Reset chat\n- /stats - Statistics\n- /skills - List skills"
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
            hint_text="Type a message or / for commands...",
            expand=True, multiline=True, min_lines=1, max_lines=3,
            on_submit=self._send_message,
            on_change=self._on_input_change,
            on_blur=self._on_input_blur,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.SECONDARY,
            color=AppColors.TEXT_PRIMARY,
            bgcolor=AppColors.SURFACE, shift_enter=True,
        )

        send_button = ft.IconButton(
            icon=icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
            bgcolor=AppColors.PRIMARY, on_click=self._send_message,
            tooltip="Send message",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        )

        # File picker for image attachments
        self._file_picker = ft.FilePicker()

        attach_button = ft.IconButton(
            icon=icons.ATTACH_FILE,
            icon_color=AppColors.TEXT_SECONDARY,
            tooltip="Attach image",
            on_click=self._on_attach_clicked,
        )

        # Attachment preview bar (hidden by default)
        self._attachment_preview = ft.Row(controls=[], spacing=8, visible=False)
        self._attachment_preview_container = ft.Container(
            content=self._attachment_preview,
            bgcolor=AppColors.SURFACE_VARIANT,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(8),
            padding=ft.Padding.only(left=8, right=8, top=4, bottom=4),
            visible=False,
        )

        # Register keyboard handler for Tab/Arrow navigation in skill popup
        self.page.on_keyboard_event = self._on_keyboard

        self.skills_popup = ft.Column(controls=[], spacing=2, visible=False)
        self.skills_popup_container = ft.Container(
            content=self.skills_popup, bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(8),
            padding=ft.Padding.all(8), visible=False,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.Colors.with_opacity(0.1, "black"),
                offset=ft.Offset(0, -2),
            ),
        )

        # Input area container
        input_area = ft.Container(
            content=ft.Column([
                self.skills_popup_container,
                self._attachment_preview_container,
                ft.Row([attach_button, self.message_input, send_button],
                       spacing=8, vertical_alignment=ft.CrossAxisAlignment.END),
            ], spacing=6),
            padding=ft.Padding.only(top=8),
            border=ft.Border.only(top=ft.BorderSide(1, AppColors.BORDER)),
        )

        return ft.Column([
            header,
            ft.Divider(height=1, color=AppColors.BORDER),
            user_bar,
            self.messages_list,
            input_area,
        ], expand=True, spacing=6)

    # ── Typing indicator ─────────────────────────────────────────────────

    def _show_typing_indicator(self):
        """Show animated typing indicator."""
        self._typing_row = ft.Row([
            ft.ProgressRing(width=16, height=16, stroke_width=2),
            ft.Text("SkillForge is thinking...", color=AppColors.TEXT_MUTED, italic=True, size=13),
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

    # ── Attachment handling ────────────────────────────────────────────────

    def _on_attach_clicked(self, e):
        """Open file picker and handle selected file."""
        try:
            files = self._file_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
                dialog_title="Choose an image to attach",
            )
            if not files:
                return

            picked = files[0]
            file_path = picked.path
            if not file_path:
                return

            from pathlib import Path as _Path
            p = _Path(file_path)
            if not p.exists():
                return

            # Determine MIME type from extension
            from skillforge.core.image_handler import EXTENSION_TO_MIME
            ext = p.suffix.lower()
            mime = EXTENSION_TO_MIME.get(ext, "image/png")

            attachment = Attachment(
                file_path=file_path,
                original_filename=p.name,
                mime_type=mime,
                size_bytes=p.stat().st_size,
            )
            self._pending_attachments = [attachment]

            # Show preview
            self._attachment_preview.controls.clear()
            self._attachment_preview.controls.extend([
                ft.Image(src=file_path, width=48, height=48, fit=ft.BoxFit.CONTAIN,
                         border_radius=ft.BorderRadius.all(4)),
                ft.Text(p.name, size=12, color=AppColors.TEXT_SECONDARY,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                ft.IconButton(
                    icon=icons.CLOSE, icon_size=16,
                    icon_color=AppColors.TEXT_MUTED,
                    tooltip="Remove attachment",
                    on_click=lambda _: self._clear_pending_attachments(),
                ),
            ])
            self._attachment_preview.visible = True
            self._attachment_preview_container.visible = True
            self.page.update()
        except Exception as ex:
            self.logger.error(f"File picker error: {ex}") if hasattr(self, 'logger') else None

    def _clear_pending_attachments(self):
        """Clear all pending attachments and hide preview."""
        self._pending_attachments.clear()
        self._attachment_preview.controls.clear()
        self._attachment_preview.visible = False
        self._attachment_preview_container.visible = False
        self.page.update()

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
        text = e.control.value or ""
        show_popup = False
        popup_changed = False
        previous_visible = self.skills_popup.visible
        previous_suggestions = list(self._suggestions)

        if text.startswith("/") and " " not in text:
            cmd = text[1:].lower()
            suggestions = []
            builtins = [
                ("help", "Show available commands"),
                ("reset", "Reset conversation"),
                ("stats", "Show session statistics"),
                ("skills", "List all skills"),
            ]

            has_exact = False
            for name, desc in builtins:
                if cmd and name == cmd:
                    has_exact = True
                elif cmd == "" or name.startswith(cmd):
                    suggestions.append((name, desc, False))
            if self.skills_manager:
                for skill in self.skills_manager.get_user_invocable_skills():
                    if cmd and skill.name.lower() == cmd:
                        has_exact = True
                    elif cmd == "" or skill.name.lower().startswith(cmd):
                        emoji = f"{skill.emoji} " if skill.emoji else ""
                        suggestions.append((skill.name, f"{emoji}{skill.description}", True))

            if suggestions and not has_exact:
                self._suggestions = suggestions[:8]
                self._selected_index = 0
                self._rebuild_popup_items()
                show_popup = True
            else:
                self._suggestions = []
                self._selected_index = 0

        popup_changed = (
            previous_visible != show_popup or
            previous_suggestions != self._suggestions
        )
        self.skills_popup.visible = show_popup
        self.skills_popup_container.visible = show_popup

        if popup_changed:
            self._update_popup_controls()
            self._lock_input_focus()

    def _on_input_blur(self, e):
        """Keep slash-command typing active even if popup updates steal focus."""
        if self._should_keep_input_focus():
            self._schedule_input_focus()

    def _rebuild_popup_items(self):
        """Rebuild popup items as plain non-focusable containers."""
        self.skills_popup.controls.clear()
        for idx, (name, desc, _is_skill) in enumerate(self._suggestions):
            row = ft.Container(
                content=ft.Row([
                    ft.Text(f"/{name}", weight=ft.FontWeight.BOLD,
                            size=13, color=AppColors.PRIMARY),
                    ft.Text(f" - {desc}", size=12,
                            color=AppColors.TEXT_SECONDARY),
                ], spacing=4),
                on_click=lambda _e, n=name: self._select_skill(n),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=AppColors.SURFACE_VARIANT if idx == self._selected_index else None,
            )
            self.skills_popup.controls.append(row)

    def _on_keyboard(self, e: ft.KeyboardEvent):
        """Handle Tab/Arrow keys for skill popup selection."""
        if not self.skills_popup.visible or not self._suggestions:
            return

        if e.key == "Tab":
            name = self._suggestions[self._selected_index][0]
            self._select_skill(name)
        elif e.key == "Arrow Down":
            self._selected_index = (self._selected_index + 1) % len(self._suggestions)
            self._update_highlight()
        elif e.key == "Arrow Up":
            self._selected_index = (self._selected_index - 1) % len(self._suggestions)
            self._update_highlight()
        elif e.key == "Escape":
            self.skills_popup.visible = False
            self.skills_popup_container.visible = False
            self._suggestions = []
            self._update_popup_controls()
            self._schedule_input_focus()

    def _update_highlight(self):
        """Update visual highlight on the selected suggestion."""
        for i, ctrl in enumerate(self.skills_popup.controls):
            ctrl.bgcolor = AppColors.SURFACE_VARIANT if i == self._selected_index else None
        self._update_popup_controls()
        self._schedule_input_focus()

    def _select_skill(self, skill_name: str):
        """Insert selected skill into input and close popup."""
        self.message_input.value = f"/{skill_name} "
        self.skills_popup.visible = False
        self.skills_popup_container.visible = False
        self._suggestions = []
        self._update_input_and_popup()
        self._lock_input_focus()

    def _update_popup_controls(self):
        """Refresh only popup-related controls to avoid full-page focus churn."""
        try:
            self.page.update(self.skills_popup_container)
        except Exception:
            try:
                self.page.update()
            except Exception:
                pass

    def _update_input_and_popup(self):
        """Refresh the chat input and popup without forcing a full page redraw."""
        try:
            self.page.update(self.message_input, self.skills_popup_container)
        except Exception:
            try:
                self.page.update()
            except Exception:
                pass

    def _should_keep_input_focus(self) -> bool:
        """Return True while slash-command interactions should own keyboard focus."""
        text = self.message_input.value or ""
        if self.skills_popup.visible:
            return True
        if time.monotonic() < self._focus_lock_until:
            return True
        return text.startswith("/") and " " not in text

    def _lock_input_focus(self, duration: float = 0.4):
        """Keep focus on the input for a short window to beat Tab traversal."""
        self._focus_lock_until = time.monotonic() + duration
        self._schedule_input_focus()

    def _schedule_input_focus(self):
        """Restore chat input focus after popup updates that steal the caret."""
        async def _restore_focus():
            for delay in (0.01, 0.05, 0.15):
                await asyncio.sleep(delay)
                try:
                    await self.message_input.focus()
                except TypeError:
                    # Some Flet versions return non-awaitable from focus()
                    pass
                except Exception:
                    pass

        try:
            self.page.run_task(_restore_focus)
        except Exception:
            pass

    # ── Send & Process ───────────────────────────────────────────────────

    def _send_message(self, e):
        """Send message — handles commands and regular messages."""
        text = self.message_input.value.strip()
        has_attachments = bool(self._pending_attachments)

        # Allow sending with just an attachment (no text required)
        if not text and not has_attachments:
            return
        if self._is_processing:
            return

        # Capture attachments before clearing
        attachments = list(self._pending_attachments) if has_attachments else None

        self.message_input.value = ""
        self._clear_pending_attachments()
        # Close any open popup and refocus input
        self.skills_popup.visible = False
        self.skills_popup_container.visible = False
        self._suggestions = []
        self.page.update()
        self._schedule_input_focus()

        if text and text.startswith("/") and self.router and not has_attachments:
            is_skill, skill_name, remaining = self.router.is_skill_invocation(text)
            print(f"[chat] _send_message: text='{text}', is_skill={is_skill}, skill_name='{skill_name}'")
            if not is_skill:
                self._handle_command(text)
                return

        display_text = text or "[Image]"

        self.messages_list.controls.append(
            ChatMessage(
                text=display_text, is_user=True,
                timestamp=datetime.now().strftime("%H:%M"),
                attachments=attachments,
            )
        )
        self.page.update()
        self.page.run_task(self._process_bot_response, display_text, attachments)

    async def _process_bot_response(self, user_message: str, attachments=None):
        """Process bot response using streaming on Flet's event loop."""
        if self._is_processing:
            print(f"[chat] _process_bot_response SKIPPED (already processing): '{user_message[:50]}'")
            return
        self._is_processing = True
        self._show_typing_indicator()
        self._last_ui_update = 0.0

        try:
            if self.router:
                is_skill, skill_name, remaining = self.router.is_skill_invocation(user_message)
                skill_context = ""
                effective_message = user_message

                # Auto-detect skill intent from natural language (no slash prefix)
                if not is_skill:
                    msg_lower = user_message.lower()
                    _email_kw = (
                        "email", "inbox", "mail", "unread", "sent me",
                        "message from", "latest email", "check my mail",
                        "any new email", "send an email", "write an email",
                    )
                    _cal_kw = (
                        "calendar", "calander", "calender", "calandar",
                        "schedule", "meeting", "appointment", "event",
                        "what's on today", "what's on tomorrow",
                        "do i have any", "am i free", "any plans",
                        "book a meeting", "google cal",
                    )
                    _notion_kw = (
                        "notion", "my list", "my_list", "my:list",
                        "todo list", "todolist", "to-do",
                        "add to list", "put in list", "shopping list",
                    )
                    if any(k in msg_lower for k in _email_kw):
                        is_skill, skill_name, remaining = True, "email", user_message
                    elif any(k in msg_lower for k in _cal_kw):
                        is_skill, skill_name, remaining = True, "calendar", user_message
                    elif any(k in msg_lower for k in _notion_kw):
                        is_skill, skill_name, remaining = True, "notion", user_message

                print(f"[chat] _process_bot_response: msg='{user_message}', is_skill={is_skill}, skill='{skill_name}', remaining='{remaining}'")

                if is_skill:
                    # Direct-execution skills: email, calendar, notion, etc.
                    # ALWAYS execute directly — no LLM guessing.
                    if self.router._skill_executor.can_execute_directly(skill_name):
                        print(f"[chat] DIRECT EXEC: skill={skill_name}, args='{remaining}'")
                        try:
                            success, result = await asyncio.to_thread(
                                self.router._skill_executor.execute, skill_name, remaining
                            )
                            print(f"[chat] DIRECT EXEC result: success={success}, len={len(result)}")
                            self._update_bot_message(result, is_partial=False)
                            return
                        except Exception as exc:
                            print(f"[chat] DIRECT EXEC error: {exc}")
                            self._update_bot_message(f"**Error:** {exc}", is_partial=False)
                            return

                    elif skill_name == "google-search":
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

                    else:
                        # Other skills — just inject skill context for LLM
                        skill_context = self.router.get_skill_context(skill_name)
                        effective_message = remaining if remaining else user_message

                print(f"[chat] Sending to router stream: effective_message='{effective_message[:80]}', has_skill_context={bool(skill_context)}")
                full_text = ""
                replace_marker = "\n\n<!--REPLACE_RESPONSE-->\n"
                stream_kwargs = dict(
                    channel="flet", user_id=self.current_user_id,
                    user_message=effective_message, chat_id=None,
                    user_name="Flet User",
                    skill_context=skill_context if skill_context else None,
                )
                if attachments:
                    stream_kwargs["attachments"] = attachments
                async for chunk in self.router.handle_message_stream(**stream_kwargs):
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

        # Intercept: if the LLM output contains a slash command, execute it
        # instead of showing it to the user as text.
        # _is_auto_executing prevents recursion when the executor's result
        # is displayed via this same method.
        if (not is_partial and self.router
                and not getattr(self, '_is_auto_executing', False)):
            import re as _re
            m = _re.search(r'`?(/(email|calendar|notion|browse)\s*[^`]*)`?', text)
            if m:
                cmd_text = m.group(1).strip().rstrip('`')
                is_skill, skill_name, remaining = self.router.is_skill_invocation(cmd_text)
                if is_skill and self.router._skill_executor.can_execute_directly(skill_name):
                    print(f"[chat] AUTO-EXEC intercepted LLM command: {cmd_text}")
                    self.page.run_task(self._auto_execute_skill, skill_name, remaining)
                    return

        # Also remove any previous partial bot response
        if self.messages_list.controls:
            last_msg = self.messages_list.controls[-1]
            if hasattr(last_msg, '_is_bot_response') and last_msg._is_bot_response:
                self.messages_list.controls.pop()

        # E-005: Extract outbound images from bot response (only for final)
        outbound_attachments = None
        display_text = text
        if not is_partial:
            try:
                from skillforge.core.router import MessageRouter
                cleaned, image_paths = MessageRouter.extract_outbound_images(text)
                if image_paths:
                    display_text = cleaned
                    outbound_attachments = []
                    for img_path in image_paths:
                        outbound_attachments.append(Attachment(
                            file_path=img_path,
                            original_filename=img_path.rsplit("/", 1)[-1] if "/" in img_path else img_path,
                            mime_type="image/png",  # Approximate — display works regardless
                            size_bytes=0,
                        ))
            except Exception:
                pass

        new_msg = ChatMessage(
            text=display_text, is_user=False,
            timestamp=datetime.now().strftime("%H:%M"),
            attachments=outbound_attachments,
        )
        new_msg._is_bot_response = True
        self.messages_list.controls.append(new_msg)
        try:
            self.page.update()
            # Refocus input after final bot message so user can keep typing
            if not is_partial:
                self._schedule_input_focus()
        except Exception:
            pass

    async def _auto_execute_skill(self, skill_name: str, args: str):
        """Auto-execute a slash command the LLM suggested instead of showing it."""
        self._is_auto_executing = True
        try:
            success, result = await asyncio.to_thread(
                self.router._skill_executor.execute, skill_name, args
            )
            self._update_bot_message(result, is_partial=False)
        except Exception as ex:
            self._update_bot_message(f"**Error:** {ex}", is_partial=False)
        finally:
            self._is_auto_executing = False

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
                self._schedule_input_focus()
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
            self._schedule_input_focus()

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
