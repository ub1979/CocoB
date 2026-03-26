"""
SettingsView — appearance, personas, messaging bots, scheduler, LLM providers, memory.

This is the largest view, extracted from the old monolithic app.py.
"""

import asyncio
import base64
import json
import os
import sys
import threading
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import flet as ft
from flet import Icons as icons

from skillforge import PROJECT_ROOT as project_root
from skillforge.flet.theme import (
    AppColors, Spacing, LOCAL_SERVER_PROVIDERS, CLI_PROVIDERS,
    CLOUD_API_PROVIDERS, API_KEY_ENV_MAP,
    check_local_server_status, check_cli_installed,
)
from skillforge.flet.storage import secure_storage as _default_storage
from skillforge.flet.components.widgets import (
    CollapsibleSection, StyledButton, SectionHeader, SubItemAccordion,
    SettingsPanel, SettingRow,
)
from skillforge.flet.components.cards import ServerStatusCard, CliStatusCard
from skillforge.core.user_permissions import Permission, UserRole, ALL_PERMISSIONS

# Conditional imports
BOT_AVAILABLE = False
TELEGRAM_AVAILABLE = False
WHATSAPP_AVAILABLE = False
SLACK_AVAILABLE = False
SCHEDULER_AVAILABLE = False
TelegramChannel = TelegramConfig = None
WhatsAppChannel = WhatsAppConfig = None
SlackChannel = SlackConfig = None

try:
    import config
    BOT_AVAILABLE = True
except ImportError:
    config = None

try:
    from skillforge.channels.telegram import TelegramChannel, TelegramConfig
    TELEGRAM_AVAILABLE = True
except ImportError:
    pass

try:
    from skillforge.channels.whatsapp import WhatsAppChannel, WhatsAppConfig
    WHATSAPP_AVAILABLE = True
except ImportError:
    pass

try:
    from skillforge.channels.slack_channel import SlackChannel, SlackConfig
    SLACK_AVAILABLE = True
except ImportError:
    pass

try:
    from skillforge.core.scheduler import SchedulerManager, ScheduledTask
    SCHEDULER_AVAILABLE = True
except ImportError:
    pass


class SettingsView:
    """Settings view with grouped sections."""

    def __init__(self, page: ft.Page, app_state, router, session_manager,
                 skills_manager, secure_storage, scheduler_manager=None):
        self.page = page
        self.app_state = app_state
        self.router = router
        self.session_manager = session_manager
        self.skills_manager = skills_manager
        self.secure_storage = secure_storage or _default_storage
        self.scheduler_manager = scheduler_manager
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.rebuild_callback = None  # Set by app.py for full UI rebuild
        self._refresh_model_info_callback = None  # Set by app.py

    def build(self) -> ft.Column:
        # Build all section contents (lazy — built once)
        self._section_contents = {
            "appearance": self._create_appearance_section(),
            "personas": self._create_personas_section(),
            "permissions": self._create_user_permissions_section(),
            "bots": self._create_messaging_bots_group(),
            "scheduler": self._create_proactive_tasks_group(),
            "providers": self._create_llm_providers_group(),
            "memory": self._create_memory_section(),
        }

        self._active_section_key = None

        # Category card grid — the "home" page of settings
        self._categories = [
            ("appearance", icons.PALETTE, "Appearance", "Theme & colors"),
            ("personas", icons.PEOPLE, "Personas", "Agents & defaults"),
            ("permissions", icons.SECURITY, "Permissions", "Roles & access"),
            ("bots", icons.FORUM, "Channels", "Telegram, WhatsApp, Slack"),
            ("scheduler", icons.SCHEDULE, "Scheduler", "Proactive tasks"),
            ("providers", icons.PSYCHOLOGY, "LLM Providers", "Local, CLI, Cloud"),
            ("memory", icons.MEMORY, "Memory", "Context & storage"),
        ]

        grid_controls = []
        for key, icon, title, subtitle in self._categories:
            card = self._build_category_card(key, icon, title, subtitle)
            grid_controls.append(card)

        self._grid_header = ft.Container(
            content=ft.Row([
                ft.Icon(icons.TUNE, color=AppColors.TEXT_PRIMARY, size=24),
                ft.Column([
                    ft.Text("Settings", size=20, weight=ft.FontWeight.W_700,
                            color=AppColors.TEXT_PRIMARY),
                    ft.Text("Configure your assistant, channels, and providers",
                            size=12, color=AppColors.TEXT_MUTED),
                ], spacing=1, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=4, right=4, top=8, bottom=12),
        )

        self._grid_view = ft.Column([
            self._grid_header,
            ft.Row(controls=grid_controls, wrap=True, spacing=12, run_spacing=12),
        ], spacing=4)

        # Section detail view — hidden until a card is clicked
        self._detail_header_icon = ft.Icon(icons.SETTINGS, color=AppColors.TEXT_PRIMARY, size=22)
        self._detail_header_title = ft.Text("", size=18, weight=ft.FontWeight.W_700,
                                            color=AppColors.TEXT_PRIMARY)
        self._detail_header_subtitle = ft.Text("", size=12, color=AppColors.TEXT_MUTED)

        self._detail_header = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icons.ARROW_BACK, color=AppColors.TEXT_PRIMARY, size=20),
                    on_click=lambda e: self._go_back(),
                    ink=True, border_radius=ft.BorderRadius.all(20),
                    padding=ft.Padding.all(8),
                ),
                self._detail_header_icon,
                ft.Column([
                    self._detail_header_title,
                    self._detail_header_subtitle,
                ], spacing=1, expand=True),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=0, right=4, top=8, bottom=8),
        )

        self._detail_body = ft.Container()
        self._detail_view = ft.Column([
            self._detail_header,
            ft.ListView(controls=[self._detail_body], expand=True,
                        spacing=0, padding=ft.Padding.only(right=4)),
        ], spacing=0, expand=True, visible=False)

        # Stack both views — only one visible at a time
        self._grid_view.visible = True
        return ft.Column([self._grid_view, self._detail_view],
                         expand=True, spacing=0)

    def _build_category_card(self, key: str, icon: str,
                             title: str, subtitle: str) -> ft.Container:
        """Build a clickable category card for the settings grid."""
        card = ft.Container(
            content=ft.Column([
                ft.Icon(icon, color=AppColors.TEXT_PRIMARY, size=30),
                ft.Text(title, size=13, weight=ft.FontWeight.W_600,
                        color=AppColors.TEXT_PRIMARY),
                ft.Text(subtitle, size=10, color=AppColors.TEXT_MUTED),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=130, height=120,
            padding=ft.Padding.only(top=18, bottom=12, left=8, right=8),
            bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(12),
            alignment=ft.Alignment(0, -0.2),
            on_click=lambda e, k=key: self._open_section(k),
            ink=True,
        )
        return card

    def _open_section(self, key: str):
        """Navigate into a settings section — hides grid, shows section page."""
        self._active_section_key = key

        # Find category info for header
        for cat_key, cat_icon, cat_title, cat_subtitle in self._categories:
            if cat_key == key:
                self._detail_header_icon.name = cat_icon
                self._detail_header_title.value = cat_title
                self._detail_header_subtitle.value = cat_subtitle
                break

        # Rebuild live sections from scratch each time they're opened
        if key == "permissions":
            self._section_contents["permissions"] = self._create_user_permissions_section()
        elif key == "personas":
            self._refresh_persona_list()
            self._refresh_channel_dropdowns()

        self._detail_body.content = self._section_contents[key]
        self._grid_view.visible = False
        self._detail_view.visible = True
        self.page.update()

    def _go_back(self):
        """Return to the settings grid from a section page."""
        self._active_section_key = None
        self._detail_view.visible = False
        self._grid_view.visible = True
        self.page.update()

    # =====================================================================
    # APPEARANCE
    # =====================================================================

    def _create_appearance_section(self):
        self.dark_mode_switch = ft.Switch(
            value=AppColors.is_dark_mode(), active_color=AppColors.ACCENT,
            on_change=self._toggle_dark_mode,
        )
        content = ft.Column([
            SettingRow("Dark Mode", icon=icons.DARK_MODE,
                       subtitle="Reduce eye strain with a darker palette",
                       control=self.dark_mode_switch),
        ], spacing=0)
        return SettingsPanel(title="Appearance", icon=icons.PALETTE,
                             subtitle="Theme & visual preferences",
                             content=content)

    def _toggle_dark_mode(self, e):
        is_dark = e.control.value
        AppColors.set_dark_mode(is_dark)
        self.page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        self.page.bgcolor = AppColors.BACKGROUND
        if self.rebuild_callback:
            self.rebuild_callback()
        self.page.update()

    # =====================================================================
    # PERSONAS
    # =====================================================================

    def _create_personas_section(self):
        self._persona_list = ft.Column(spacing=4)
        self._persona_create_name = ft.TextField(label="Name", width=140, text_size=13, dense=True)
        self._persona_create_emoji = ft.TextField(label="Emoji", width=60, text_size=13, dense=True, value="\U0001f916")
        self._persona_create_desc = ft.TextField(label="Description", expand=True, text_size=13, dense=True)
        self._persona_create_instructions = ft.TextField(
            label="Instructions (persona behavior)", multiline=True, min_lines=2, max_lines=4,
            text_size=13, expand=True,
        )

        channels = ["telegram", "whatsapp", "slack", "discord", "msteams", "gradio"]
        self._channel_dropdowns = {}
        persona_names = ["(none)"] + sorted(self.router.personality.get_personas().keys()) if self.router else ["(none)"]

        channel_row_items = []
        for ch in channels:
            dd = ft.Dropdown(
                label=ch.capitalize(), width=140, text_size=12, dense=True,
                options=[ft.dropdown.Option(n) for n in persona_names],
                value=self.router.personality._user_profiles.get("channel_defaults", {}).get(ch, "(none)") if self.router else "(none)",
                on_select=lambda e, channel=ch: self._on_channel_persona_change(channel, e),
            )
            self._channel_dropdowns[ch] = dd
            channel_row_items.append(dd)

        self._refresh_persona_list()

        content = ft.Column([
            SectionHeader("Loaded Personas", icon=icons.PEOPLE),
            self._persona_list,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Channel Defaults",
                          subtitle="Set a default persona per channel"),
            ft.Row(channel_row_items, wrap=True, spacing=8, run_spacing=8),
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Create New Persona", icon=icons.ADD_CIRCLE_OUTLINE),
            ft.Row([self._persona_create_name, self._persona_create_emoji,
                    self._persona_create_desc], spacing=8),
            self._persona_create_instructions,
            StyledButton("Create Persona", icon=icons.ADD,
                         on_click=self._on_create_persona),
        ], spacing=12)

        return SettingsPanel(title="Personas & Agents", icon=icons.PEOPLE,
                             subtitle="Configure AI personality and per-channel defaults",
                             content=content)

    def _refresh_persona_list(self):
        self._persona_list.controls.clear()
        if not self.router:
            return
        personas = self.router.personality.get_personas()
        if not personas:
            self._persona_list.controls.append(
                ft.Text("No personas loaded. Create one below.", size=12, color=AppColors.TEXT_SECONDARY, italic=True))
            return
        for p in sorted(personas.values(), key=lambda x: x.name):
            delete_btn = ft.IconButton(
                icon=icons.DELETE_OUTLINE, icon_size=16, icon_color=AppColors.ERROR,
                tooltip="Delete persona", on_click=lambda e, name=p.name: self._on_delete_persona(name),
                visible=(p.name != "default"),
            )
            row = ft.Row([
                ft.Text(p.emoji, size=16),
                ft.Text(p.name, size=13, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY, width=100),
                ft.Text(p.description, size=12, color=AppColors.TEXT_SECONDARY, expand=True),
                delete_btn,
            ], spacing=8)
            self._persona_list.controls.append(row)

    def _on_channel_persona_change(self, channel, e):
        if not self.router:
            return
        value = e.control.value
        if value == "(none)":
            self.router.personality.set_channel_default(channel, "default")
        else:
            try:
                self.router.personality.set_channel_default(channel, value)
            except ValueError:
                pass
        self.router._prompt_cache.clear()

    def _on_create_persona(self, e):
        if not self.router:
            return
        name = self._persona_create_name.value.strip().lower() if self._persona_create_name.value else ""
        if not name:
            return
        emoji = self._persona_create_emoji.value.strip() if self._persona_create_emoji.value else "\U0001f916"
        desc = self._persona_create_desc.value.strip() if self._persona_create_desc.value else ""
        instructions = self._persona_create_instructions.value.strip() if self._persona_create_instructions.value else ""
        try:
            self.router.personality.create_persona(name, description=desc, emoji=emoji, instructions=instructions)
            self._persona_create_name.value = ""
            self._persona_create_desc.value = ""
            self._persona_create_instructions.value = ""
            self._persona_create_emoji.value = "\U0001f916"
            self._refresh_persona_list()
            self._refresh_channel_dropdowns()
            self.page.update()
        except ValueError:
            pass

    def _on_delete_persona(self, name):
        if not self.router:
            return
        try:
            self.router.personality.delete_persona(name)
            self.router._prompt_cache.clear()
            self._refresh_persona_list()
            self._refresh_channel_dropdowns()
            self.page.update()
        except ValueError:
            pass

    def _refresh_channel_dropdowns(self):
        persona_names = ["(none)"] + sorted(self.router.personality.get_personas().keys()) if self.router else ["(none)"]
        for ch, dd in self._channel_dropdowns.items():
            dd.options = [ft.dropdown.Option(n) for n in persona_names]
            current = self.router.personality._user_profiles.get("channel_defaults", {}).get(ch) if self.router else None
            dd.value = current if current in persona_names else "(none)"

    # =====================================================================
    # USER PERMISSIONS
    # =====================================================================

    def _create_user_permissions_section(self):
        pm = getattr(self.router, '_permission_manager', None) if self.router else None

        self._perm_user_list = ft.Column(spacing=4)
        self._perm_status = ft.Text("", size=12, color=AppColors.ACCENT, visible=False)
        self._perm_user_id_field = ft.TextField(
            label="User ID", width=200, text_size=13, dense=True,
        )
        self._perm_role_dropdown = ft.Dropdown(
            label="Role", width=160, text_size=12, dense=True,
            options=[ft.dropdown.Option(r.value) for r in UserRole],
            value=UserRole.USER.value,
        )
        self._refresh_perm_user_list()

        if pm and not pm.enabled:
            inactive_msg = ft.Text(
                "Permission system is inactive (no data/user_roles.json). "
                "Set a user role below to activate it.",
                size=12, color=AppColors.TEXT_SECONDARY, italic=True,
            )
        else:
            inactive_msg = ft.Container()

        content = ft.Column([
            inactive_msg,
            SectionHeader("Configured Users", icon=icons.PEOPLE,
                          subtitle="Click permissions to toggle"),
            self._perm_user_list,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Add User", icon=icons.PERSON_ADD),
            ft.Row([
                self._perm_user_id_field,
                self._perm_role_dropdown,
                StyledButton("Set Role", icon=icons.PERSON_ADD,
                             on_click=self._on_perm_set_role),
            ], spacing=8),
            self._perm_status,
        ], spacing=12)

        return SettingsPanel(
            title="User Permissions", icon=icons.SECURITY,
            subtitle="Manage roles and access control",
            content=content,
        )

    def _refresh_perm_user_list(self):
        self._perm_user_list.controls.clear()
        pm = getattr(self.router, '_permission_manager', None) if self.router else None
        if not pm:
            self._perm_user_list.controls.append(
                ft.Text("No router available.", size=12, color=AppColors.TEXT_SECONDARY, italic=True))
            return

        users = pm.get_all_users()
        if not users:
            self._perm_user_list.controls.append(
                ft.Text("No users configured yet.", size=12, color=AppColors.TEXT_SECONDARY, italic=True))
            return

        from skillforge.core.user_permissions import DEFAULT_ROLES
        all_perm_names = sorted([p.value for p in Permission])
        role_colors = {
            "admin": AppColors.ACCENT,
            "power_user": AppColors.PRIMARY_LIGHT,
            "user": AppColors.TEXT_PRIMARY,
            "restricted": AppColors.TEXT_MUTED,
        }

        for uid, entry in sorted(users.items()):
            role = entry.get("role", "user")
            custom = set(entry.get("custom_permissions", []))
            denied = set(entry.get("denied_permissions", []))
            rc = role_colors.get(role, AppColors.TEXT_SECONDARY)

            # Calculate effective permissions for this user
            role_def = DEFAULT_ROLES.get(role, {})
            role_perms = role_def.get("permissions", [])
            if role_perms == ["*"]:
                base_granted = set(all_perm_names)
            else:
                base_granted = set(role_perms)
            effective = (base_granted | custom) - denied

            # Build clickable permission chips
            chips = []
            for p in all_perm_names:
                is_enabled = p in effective
                if is_enabled:
                    chip = ft.Container(
                        content=ft.Text(p, size=8, color=AppColors.ACCENT,
                                        weight=ft.FontWeight.W_600),
                        padding=ft.Padding.only(left=6, right=6, top=3, bottom=3),
                        bgcolor=ft.Colors.with_opacity(0.09, AppColors.ACCENT),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.19, AppColors.ACCENT)),
                        border_radius=ft.BorderRadius.all(4),
                        on_click=lambda e, u=uid, perm=p: self._toggle_permission(u, perm, revoke=True),
                        tooltip=f"Click to revoke '{p}'",
                        ink=True,
                    )
                else:
                    chip = ft.Container(
                        content=ft.Text(p, size=8, color=AppColors.TEXT_MUTED),
                        padding=ft.Padding.only(left=6, right=6, top=3, bottom=3),
                        bgcolor=AppColors.SURFACE,
                        border=ft.Border.all(1, AppColors.BORDER),
                        border_radius=ft.BorderRadius.all(4),
                        on_click=lambda e, u=uid, perm=p: self._toggle_permission(u, perm, revoke=False),
                        tooltip=f"Click to grant '{p}'",
                        ink=True,
                    )
                chips.append(chip)

            # Role badge
            role_badge = ft.Container(
                content=ft.Text(role.replace("_", " ").title(), size=10,
                                color=rc, weight=ft.FontWeight.W_600),
                padding=ft.Padding.only(left=8, right=8, top=2, bottom=2),
                bgcolor=ft.Colors.with_opacity(0.08, rc),
                border_radius=ft.BorderRadius.all(4),
            )

            delete_btn = ft.IconButton(
                icon=icons.DELETE_OUTLINE, icon_size=16, icon_color=AppColors.ERROR,
                tooltip="Remove user", on_click=lambda e, u=uid: self._on_perm_remove_user(u),
            )

            user_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icons.PERSON, size=16, color=rc),
                        ft.Text(uid, size=13, weight=ft.FontWeight.W_600,
                                color=AppColors.TEXT_PRIMARY),
                        role_badge,
                        ft.Container(expand=True),
                        delete_btn,
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row(chips, wrap=True, spacing=4, run_spacing=4),
                ], spacing=6),
                padding=ft.Padding.all(10),
                bgcolor=AppColors.SURFACE_VARIANT,
                border_radius=ft.BorderRadius.all(8),
            )
            self._perm_user_list.controls.append(user_card)

    def _toggle_permission(self, user_id: str, permission: str, revoke: bool = False):
        """Toggle a permission for a user — called by clickable chips."""
        pm = getattr(self.router, '_permission_manager', None) if self.router else None
        if not pm:
            return
        if revoke:
            ok = pm.revoke_permission(user_id, permission)
            if ok:
                self._perm_show_status(f"Revoked '{permission}' from {user_id}")
        else:
            ok = pm.grant_permission(user_id, permission)
            if ok:
                self._perm_show_status(f"Granted '{permission}' to {user_id}")
        self._refresh_perm_user_list()
        self.page.update()

    def _perm_show_status(self, msg, is_error=False):
        self._perm_status.value = msg
        self._perm_status.color = AppColors.ERROR if is_error else AppColors.ACCENT
        self._perm_status.visible = True
        self.page.update()

    def _on_perm_set_role(self, e):
        pm = getattr(self.router, '_permission_manager', None) if self.router else None
        if not pm:
            return
        uid = self._perm_user_id_field.value.strip() if self._perm_user_id_field.value else ""
        if not uid:
            self._perm_show_status("Enter a user ID.", is_error=True)
            return
        role = self._perm_role_dropdown.value
        ok = pm.set_user_role(uid, role, assigned_by="ui")
        if ok:
            self._perm_show_status(f"Set {uid} → {role}")
            self._refresh_perm_user_list()
            self.page.update()
        else:
            self._perm_show_status(f"Invalid role: {role}", is_error=True)

    def _on_perm_remove_user(self, user_id):
        pm = getattr(self.router, '_permission_manager', None) if self.router else None
        if not pm:
            return
        ok = pm.remove_user(user_id)
        if ok:
            self._perm_show_status(f"Removed {user_id}")
            self._refresh_perm_user_list()
            self.page.update()
        else:
            self._perm_show_status(f"User {user_id} not found.", is_error=True)

    # =====================================================================
    # MESSAGING BOTS GROUP
    # =====================================================================

    def _create_messaging_bots_group(self):
        self._create_telegram_section()
        self._create_whatsapp_section()
        self._create_slack_section()

        telegram_content = self._create_telegram_content()
        whatsapp_content = self._create_whatsapp_content()
        slack_content = self._create_slack_content()
        discord_content = self._create_discord_content()

        group_content = ft.Column([
            SubItemAccordion(
                "Telegram", "\U0001f4f1",
                status_text="Ready", status_color=AppColors.SUCCESS,
                content=telegram_content),
            SubItemAccordion(
                "WhatsApp", "\U0001f4ac",
                status_text="Ready", status_color=AppColors.SUCCESS,
                content=whatsapp_content),
            SubItemAccordion(
                "Slack", "\U0001f4bc",
                status_text="Ready", status_color=AppColors.SUCCESS,
                content=slack_content),
            SubItemAccordion(
                "Discord", "\U0001f3ae",
                status_text="Coming Soon", status_color=AppColors.WARNING,
                content=discord_content),
        ], spacing=4)

        return SettingsPanel(title="Messaging Channels", icon=icons.FORUM,
                             subtitle="Configure and manage your bot connections",
                             content=group_content)

    # ── Telegram ─────────────────────────────────────────────────────────

    def _create_telegram_section(self):
        if not hasattr(self, 'telegram_bot'):
            self.telegram_bot = None
        if not hasattr(self, 'telegram_running'):
            self.telegram_running = False
        if not hasattr(self, 'telegram_loop'):
            self.telegram_loop = None

        saved_token = self.secure_storage.get_token('telegram_bot_token')
        self._has_saved_token = bool(saved_token)
        current_token = saved_token or (config.TELEGRAM_BOT_TOKEN if BOT_AVAILABLE and hasattr(config, 'TELEGRAM_BOT_TOKEN') else "")

        self.telegram_token_input = ft.TextField(
            label="Bot Token", value=current_token if not saved_token else "",
            password=True, can_reveal_password=False,
            hint_text="Enter token or use saved" if saved_token else "Get from @BotFather",
            border_color=AppColors.BORDER, focused_border_color=AppColors.PRIMARY,
            color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            expand=True, on_change=self._on_telegram_token_change,
        )
        self.telegram_reveal_btn = ft.IconButton(
            icon=icons.VISIBILITY_OFF, icon_color=AppColors.TEXT_SECONDARY,
            tooltip="Reveal token (requires password)", on_click=self._reveal_telegram_token,
        )
        self.telegram_status_icon = ft.Icon(icons.CIRCLE, color=AppColors.SUCCESS if self.telegram_running else AppColors.TEXT_MUTED, size=16)
        self.telegram_status_text = ft.Text("Running" if self.telegram_running else "Stopped", size=12,
                                           color=AppColors.SUCCESS if self.telegram_running else AppColors.TEXT_MUTED)
        self.telegram_bot_info = ft.Text("Token saved \u2713" if saved_token else "", size=12, color=AppColors.TEXT_SECONDARY)

        auto_start = self.secure_storage._data.get('telegram_auto_start', False)
        self.telegram_auto_start = ft.Checkbox(
            label="Auto-start on launch", value=auto_start, on_change=self._toggle_auto_start,
            label_style=ft.TextStyle(size=12, color=AppColors.TEXT_SECONDARY),
        )
        self.telegram_start_btn = StyledButton(
            "Stop Bot" if self.telegram_running else "Start Bot",
            icon=icons.STOP if self.telegram_running else icons.PLAY_ARROW,
            on_click=self._toggle_telegram_bot,
            variant="primary" if not self.telegram_running else "secondary",
        )
        self.telegram_set_password_btn = ft.TextButton(
            "Set Password" if not self.secure_storage.has_password() else "Change Password",
            on_click=self._set_view_password, style=ft.ButtonStyle(color=AppColors.TEXT_SECONDARY),
        )

    def _create_telegram_content(self):
        if not hasattr(self, 'telegram_token_input'):
            self._create_telegram_section()

        # Status bar
        status_bar = ft.Container(
            content=ft.Row([
                self.telegram_status_icon, self.telegram_status_text,
                ft.Container(expand=True), self.telegram_bot_info,
            ], spacing=8),
            padding=ft.Padding.all(10),
            bgcolor=AppColors.SURFACE_VARIANT,
            border_radius=ft.BorderRadius.all(8),
        )

        return ft.Column([
            ft.Text("Token is encrypted locally. Set a password to protect viewing it.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            status_bar,
            ft.Container(height=10),
            SectionHeader("Bot Token", icon=icons.KEY),
            ft.Row([self.telegram_token_input, self.telegram_reveal_btn], spacing=8),
            ft.Container(height=10),
            ft.Row([self.telegram_start_btn, ft.Container(expand=True),
                    self.telegram_auto_start], spacing=8),
            self.telegram_set_password_btn,
        ], spacing=4)

    def _on_telegram_token_change(self, e):
        if "saved" in self.telegram_bot_info.value.lower():
            self.telegram_bot_info.value = "Modified (not saved)"
            self.page.update()

    def _reveal_telegram_token(self, e):
        saved_token = self.secure_storage.get_token('telegram_bot_token')
        if not saved_token:
            self._show_snackbar("No token saved", error=True)
            return
        if self.secure_storage.has_password():
            self._show_password_dialog("Enter Password", "Enter password to view token:",
                                       on_success=lambda: self._do_reveal_token(saved_token))
        else:
            self._do_reveal_token(saved_token)

    def _do_reveal_token(self, token):
        self.telegram_token_input.value = token
        self.telegram_reveal_btn.icon = icons.VISIBILITY
        self.page.update()
        self._show_snackbar("Token revealed (hidden in 10s)")
        def hide_token():
            time.sleep(10)
            if hasattr(self, 'telegram_token_input'):
                self.telegram_token_input.value = ""
                self.telegram_reveal_btn.icon = icons.VISIBILITY_OFF
                try:
                    self.page.update()
                except Exception:
                    pass
        threading.Thread(target=hide_token, daemon=True).start()

    def _toggle_auto_start(self, e):
        self.secure_storage._data['telegram_auto_start'] = e.control.value
        self.secure_storage._save()
        self._show_snackbar("Telegram auto-start " + ("enabled" if e.control.value else "disabled"))

    def _set_view_password(self, e):
        def on_password_set(password):
            self.secure_storage.set_password_hash(password)
            self.telegram_set_password_btn.text = "Change Password"
            self.page.update()
            self._show_snackbar("Password set successfully")
        self._show_set_password_dialog(on_success=on_password_set)

    def _show_password_dialog(self, title, message, on_success):
        password_field = ft.TextField(password=True, can_reveal_password=True, hint_text="Enter password", autofocus=True)
        def on_submit(e):
            if self.secure_storage.verify_password(password_field.value):
                self.page.close(dlg)
                on_success()
            else:
                self._show_snackbar("Wrong password", error=True)
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column([ft.Text(message, size=12), password_field], tight=True, spacing=10),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)), ft.Button(content=ft.Text("OK"), on_click=on_submit, bgcolor=AppColors.PRIMARY, color=AppColors.TEXT_ON_PRIMARY)],
        )
        self.page.open(dlg)

    def _show_set_password_dialog(self, on_success):
        password_field = ft.TextField(password=True, can_reveal_password=True, hint_text="New password", autofocus=True)
        confirm_field = ft.TextField(password=True, can_reveal_password=True, hint_text="Confirm password")
        def on_submit(e):
            if password_field.value != confirm_field.value:
                self._show_snackbar("Passwords don't match", error=True)
                return
            if len(password_field.value) < 4:
                self._show_snackbar("Password too short (min 4 chars)", error=True)
                return
            self.page.close(dlg)
            on_success(password_field.value)
        dlg = ft.AlertDialog(
            title=ft.Text("Set Password"),
            content=ft.Column([
                ft.Text("This password protects viewing your saved tokens.", size=12),
                password_field, confirm_field,
            ], tight=True, spacing=10),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dlg)), ft.Button(content=ft.Text("Set Password"), on_click=on_submit, bgcolor=AppColors.PRIMARY, color=AppColors.TEXT_ON_PRIMARY)],
        )
        self.page.open(dlg)

    def _toggle_telegram_bot(self, e):
        if self.telegram_running:
            self._stop_telegram_bot()
        else:
            self._start_telegram_bot()

    def _start_telegram_bot(self):
        if not TELEGRAM_AVAILABLE or TelegramChannel is None:
            self._show_snackbar("Telegram not available. Install python-telegram-bot.", error=True)
            return
        if getattr(self, 'telegram_running', False):
            self._show_snackbar("Telegram bot is already running")
            return
        token = self.telegram_token_input.value.strip()
        if not token:
            token = self.secure_storage.get_token('telegram_bot_token')
        if not token:
            self._show_snackbar("Please enter a bot token", error=True)
            return

        self.secure_storage.set_token('telegram_bot_token', token)
        self.telegram_bot_info.value = "Token saved \u2713"
        self._has_saved_token = True
        if BOT_AVAILABLE:
            config.TELEGRAM_BOT_TOKEN = token

        def run_telegram():
            self.telegram_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.telegram_loop)
            async def telegram_main():
                try:
                    async def handle_message(channel, user_id, user_message, **kwargs):
                        try:
                            if self.app_state and self.app_state.router:
                                return await self.app_state.router.handle_message(
                                    channel=channel, user_id=user_id, user_message=user_message,
                                    chat_id=kwargs.get('chat_id'), user_name=kwargs.get('user_name', 'User'),
                                )
                            return "Bot not fully initialized. Please try again."
                        except Exception as e:
                            return f"Error: {str(e)[:100]}"

                    tg_config = TelegramConfig(
                        bot_token=token,
                        allowed_users=config.TELEGRAM_ALLOWED_USERS if BOT_AVAILABLE and hasattr(config, 'TELEGRAM_ALLOWED_USERS') else [],
                    )
                    self.telegram_bot = TelegramChannel(config=tg_config, message_handler=handle_message)
                    await self.telegram_bot.initialize()
                    bot_info = await self.telegram_bot.get_bot_info()
                    if bot_info:
                        self.telegram_bot_info.value = f"@{bot_info['username']} - {bot_info['first_name']}"
                        self.page.update()
                    await self.telegram_bot.start_polling()
                    while self.telegram_running:
                        await asyncio.sleep(1)
                except Exception as ex:
                    err_msg = str(ex)
                    if "already running" in err_msg.lower() or "conflict" in err_msg.lower():
                        self.telegram_bot_info.value = "Error: Another bot instance is already running"
                    else:
                        self.telegram_bot_info.value = f"Error: {err_msg[:80]}"
                    self.telegram_running = False
                    self._update_telegram_ui()
                    self.page.update()
            try:
                self.telegram_loop.run_until_complete(telegram_main())
            finally:
                self.telegram_loop.close()

        self.telegram_running = True
        self._update_telegram_ui()
        self.page.update()
        self.telegram_thread = threading.Thread(target=run_telegram, daemon=True)
        self.telegram_thread.start()
        self._show_snackbar("Telegram bot starting...")

    def _stop_telegram_bot(self):
        self.telegram_running = False
        if self.telegram_bot and self.telegram_loop:
            async def stop_bot():
                if self.telegram_bot:
                    await self.telegram_bot.stop()
            if self.telegram_loop.is_running():
                asyncio.run_coroutine_threadsafe(stop_bot(), self.telegram_loop)
        self.telegram_bot = None
        self.telegram_bot_info.value = ""
        self._update_telegram_ui()
        self.page.update()
        self._show_snackbar("Telegram bot stopped")

    def _update_telegram_ui(self):
        self.telegram_status_icon.color = AppColors.SUCCESS if self.telegram_running else AppColors.TEXT_MUTED
        self.telegram_status_text.value = "Running" if self.telegram_running else "Stopped"
        self.telegram_status_text.color = AppColors.SUCCESS if self.telegram_running else AppColors.TEXT_MUTED

    # ── WhatsApp (simplified — key methods) ──────────────────────────────

    def _create_whatsapp_section(self):
        if not hasattr(self, 'whatsapp_channel'):
            self.whatsapp_channel = None
        if not hasattr(self, 'whatsapp_connected'):
            self.whatsapp_connected = False
        if not hasattr(self, 'whatsapp_service_running'):
            self.whatsapp_service_running = False
        if not hasattr(self, 'whatsapp_webhook_running'):
            self.whatsapp_webhook_running = False
        if not hasattr(self, 'whatsapp_webhook_server'):
            self.whatsapp_webhook_server = None
        if not hasattr(self, 'whatsapp_lid_cache'):
            self.whatsapp_lid_cache = {}

        self.whatsapp_service_url = ft.TextField(
            label="Baileys Service URL",
            value=self.secure_storage.get_setting('whatsapp_service_url') or "http://localhost:3979",
            hint_text="http://localhost:3979", border_color=AppColors.BORDER,
            focused_border_color=AppColors.PRIMARY, color=AppColors.TEXT_PRIMARY,
            bgcolor=AppColors.SURFACE, label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY), expand=True,
        )
        self.whatsapp_service_status = ft.Row([
            ft.Icon(icons.CIRCLE, color=AppColors.TEXT_MUTED, size=14),
            ft.Text("Service: Unknown", size=12, color=AppColors.TEXT_MUTED),
        ], spacing=4)
        self.whatsapp_connection_status = ft.Row([
            ft.Icon(icons.CIRCLE, color=AppColors.TEXT_MUTED, size=14),
            ft.Text("WhatsApp: Not connected", size=12, color=AppColors.TEXT_MUTED),
        ], spacing=4)
        self.whatsapp_qr_container = ft.Container(
            content=ft.Column([ft.Text("QR Code will appear here when ready", size=12, color=AppColors.TEXT_MUTED, text_align=ft.TextAlign.CENTER)],
                             horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=AppColors.SURFACE_VARIANT, border_radius=ft.BorderRadius.all(8), padding=ft.Padding.all(20), visible=False,
        )
        self.whatsapp_start_service_btn = StyledButton("Start Service", icon=icons.PLAY_ARROW, on_click=self._start_whatsapp_service)
        self.whatsapp_stop_service_btn = StyledButton("Stop Service", icon=icons.STOP, on_click=self._stop_whatsapp_service, variant="secondary")
        self.whatsapp_check_btn = StyledButton("Check Status", icon=icons.REFRESH, on_click=self._check_whatsapp_status, variant="outline")
        self.whatsapp_show_qr_btn = StyledButton("Connect & Show QR", icon=icons.QR_CODE, on_click=self._show_whatsapp_qr)
        self.whatsapp_disconnect_btn = StyledButton("Disconnect", icon=icons.LINK_OFF, on_click=self._disconnect_whatsapp, variant="outline")
        self.whatsapp_logout_btn = StyledButton("Logout & Unlink", icon=icons.DELETE_FOREVER, on_click=self._logout_whatsapp, variant="outline")
        self.whatsapp_bot_status = ft.Row([
            ft.Icon(icons.CIRCLE, color=AppColors.TEXT_MUTED, size=14),
            ft.Text("Bot: Stopped", size=12, color=AppColors.TEXT_MUTED),
        ], spacing=4)
        self.whatsapp_start_bot_btn = StyledButton("Start Bot", icon=icons.SMART_TOY, on_click=self._start_whatsapp_bot)
        self.whatsapp_stop_bot_btn = StyledButton("Stop Bot", icon=icons.STOP, on_click=self._stop_whatsapp_bot, variant="secondary")

        saved_dm_policy = self.secure_storage.get_setting('whatsapp_dm_policy') or 'self_only'
        self.whatsapp_dm_policy = ft.Dropdown(
            label="DM Policy", value=saved_dm_policy, options=[
                ft.dropdown.Option("self_only", "Self Only (chat with yourself)"),
                ft.dropdown.Option("allowlist", "Allowlist (specific numbers)"),
                ft.dropdown.Option("open", "Open (respond to everyone)"),
                ft.dropdown.Option("disabled", "Disabled (no auto-replies)"),
            ], on_select=self._save_whatsapp_settings,
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, width=280,
        )
        saved_allowlist = self.secure_storage.get_setting('whatsapp_allowlist') or ''
        self.whatsapp_allowlist = ft.TextField(
            label="Allowed Numbers (comma separated)", value=saved_allowlist, hint_text="+1234567890, +0987654321",
            on_change=self._save_whatsapp_settings, border_color=AppColors.BORDER,
            color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, expand=True,
        )
        saved_group_policy = self.secure_storage.get_setting('whatsapp_group_policy') or 'mention'
        self.whatsapp_group_policy = ft.Dropdown(
            label="Group Policy", value=saved_group_policy, options=[
                ft.dropdown.Option("mention", "Require @mention"),
                ft.dropdown.Option("allowlist", "Allowlist groups only"),
                ft.dropdown.Option("open", "Respond to all groups"),
                ft.dropdown.Option("disabled", "Ignore all groups"),
            ], on_select=self._save_whatsapp_settings,
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, width=280,
        )
        self.whatsapp_ack_reaction = ft.Checkbox(
            label="Send reaction on message received",
            value=self.secure_storage.get_setting('whatsapp_ack_reaction') or True,
            on_change=self._save_whatsapp_settings,
            label_style=ft.TextStyle(size=12, color=AppColors.TEXT_SECONDARY),
        )
        self.whatsapp_auto_start = ft.Checkbox(
            label="Auto-start on launch", value=self.secure_storage._data.get('whatsapp_auto_start', False),
            on_change=self._toggle_whatsapp_auto_start,
            label_style=ft.TextStyle(size=12, color=AppColors.TEXT_SECONDARY),
        )
        self.whatsapp_persona_list = ft.Column([], spacing=4)
        self.whatsapp_persona_phone_input = ft.TextField(
            label="Phone number", hint_text="447771234567", border_color=AppColors.BORDER,
            color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, expand=True, text_size=12,
        )
        persona_options = []
        if self.router and hasattr(self.router, 'personality'):
            for name in self.router.personality.get_personas():
                persona_options.append(ft.dropdown.Option(name, name))
        self.whatsapp_persona_dropdown = ft.Dropdown(
            label="Persona", options=persona_options, border_color=AppColors.BORDER,
            color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, width=160, text_size=12,
        )
        self.whatsapp_persona_add_btn = StyledButton("Add", icon=icons.ADD, on_click=self._on_add_whatsapp_persona, variant="outline")
        self._refresh_whatsapp_contact_personas()

    def _create_whatsapp_content(self):
        if not hasattr(self, 'whatsapp_service_url'):
            self._create_whatsapp_section()

        # Status indicators
        status_section = ft.Container(
            content=ft.Column([
                self.whatsapp_service_status,
                self.whatsapp_connection_status,
                self.whatsapp_bot_status,
            ], spacing=6),
            padding=ft.Padding.all(12),
            bgcolor=AppColors.SURFACE_VARIANT,
            border_radius=ft.BorderRadius.all(8),
        )

        return ft.Column([
            ft.Text("Connect to WhatsApp via Baileys Node.js service.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            status_section,
            ft.Container(height=12),
            SectionHeader("Service Control", icon=icons.DNS),
            ft.Row([self.whatsapp_start_service_btn,
                    self.whatsapp_stop_service_btn,
                    self.whatsapp_check_btn], spacing=8, wrap=True),
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Connect WhatsApp", icon=icons.QR_CODE),
            ft.Row([self.whatsapp_show_qr_btn,
                    self.whatsapp_disconnect_btn,
                    self.whatsapp_logout_btn], spacing=8, wrap=True),
            self.whatsapp_qr_container,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Bot Control", icon=icons.SMART_TOY),
            ft.Row([self.whatsapp_start_bot_btn,
                    self.whatsapp_stop_bot_btn], spacing=8),
            self.whatsapp_auto_start,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Access Control", icon=icons.SHIELD),
            self.whatsapp_dm_policy,
            ft.Container(height=6),
            self.whatsapp_allowlist,
            ft.Container(height=6),
            self.whatsapp_group_policy,
            ft.Container(height=6),
            self.whatsapp_ack_reaction,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Contact Personas", icon=icons.CONTACTS),
            self.whatsapp_persona_list,
            ft.Row([self.whatsapp_persona_phone_input,
                    self.whatsapp_persona_dropdown,
                    self.whatsapp_persona_add_btn], spacing=8),
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Service URL", icon=icons.LINK),
            self.whatsapp_service_url,
        ], spacing=8)

    def _toggle_whatsapp_auto_start(self, e):
        self.secure_storage._data['whatsapp_auto_start'] = e.control.value
        self.secure_storage._save()

    def _check_whatsapp_status(self, e=None):
        service_url = self.whatsapp_service_url.value.strip() or "http://localhost:3979"
        self.secure_storage.set_setting('whatsapp_service_url', service_url)
        def check():
            try:
                response = requests.get(f"{service_url}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    self.whatsapp_service_running = True
                    self.whatsapp_connected = data.get("connected", False)
                    self.whatsapp_service_status.controls[0].color = AppColors.SUCCESS
                    self.whatsapp_service_status.controls[1].value = "Service: Running"
                    self.whatsapp_service_status.controls[1].color = AppColors.SUCCESS
                    if self.whatsapp_connected:
                        user_info = data.get("user") or {}
                        phone = user_info.get("phone", "")
                        name = user_info.get("name", "")
                        label = "WhatsApp: Connected"
                        if phone:
                            label += f" \u2014 +{phone}"
                        if name:
                            label += f" ({name})"
                        self.whatsapp_connection_status.controls[0].color = AppColors.SUCCESS
                        self.whatsapp_connection_status.controls[1].value = label
                        self.whatsapp_connection_status.controls[1].color = AppColors.SUCCESS
                        self.whatsapp_qr_container.visible = False
                    self._show_snackbar("WhatsApp status checked")
                else:
                    raise Exception(f"HTTP {response.status_code}")
            except requests.exceptions.ConnectionError:
                self.whatsapp_service_running = False
                self.whatsapp_connected = False
                self.whatsapp_service_status.controls[0].color = AppColors.ERROR
                self.whatsapp_service_status.controls[1].value = "Service: Not running"
                self.whatsapp_service_status.controls[1].color = AppColors.ERROR
                self._show_snackbar("WhatsApp service not running", error=True)
            except Exception as ex:
                self._show_snackbar(f"Error: {str(ex)[:50]}", error=True)
            self.page.update()
        threading.Thread(target=check, daemon=True).start()

    def _show_whatsapp_qr(self, e=None):
        service_url = self.whatsapp_service_url.value.strip() or "http://localhost:3979"
        def fetch_qr():
            try:
                response = requests.get(f"{service_url}/qr", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("connected"):
                        self.whatsapp_qr_container.content = ft.Column([
                            ft.Icon(icons.CHECK_CIRCLE, color=AppColors.SUCCESS, size=48),
                            ft.Text("Already connected!", size=14, color=AppColors.SUCCESS, weight=ft.FontWeight.W_600),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                    elif data.get("qr"):
                        self.whatsapp_qr_container.content = ft.Column([
                            ft.Text("Scan with WhatsApp", size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                            ft.Text("QR code ready - check terminal for scannable QR", size=12, color=AppColors.PRIMARY),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
                    self.whatsapp_qr_container.visible = True
            except Exception as ex:
                self._show_snackbar(f"Error: {str(ex)[:50]}", error=True)
            self.page.update()
        threading.Thread(target=fetch_qr, daemon=True).start()

    def _disconnect_whatsapp(self, e=None):
        service_url = self.whatsapp_service_url.value.strip()
        def disconnect():
            try:
                response = requests.post(f"{service_url}/disconnect", timeout=10)
                if response.status_code == 200:
                    self.whatsapp_connected = False
                    self.whatsapp_connection_status.controls[0].color = AppColors.TEXT_MUTED
                    self.whatsapp_connection_status.controls[1].value = "WhatsApp: Disconnected"
                    self.whatsapp_connection_status.controls[1].color = AppColors.TEXT_MUTED
                    self.whatsapp_qr_container.visible = False
                    self._show_snackbar("Disconnected from WhatsApp")
            except Exception as ex:
                self._show_snackbar(f"Error: {str(ex)[:50]}", error=True)
            self.page.update()
        threading.Thread(target=disconnect, daemon=True).start()

    def _logout_whatsapp(self, e=None):
        service_url = self.whatsapp_service_url.value.strip()
        def do_logout():
            try:
                response = requests.post(f"{service_url}/disconnect", json={"logout": True}, timeout=15)
                if response.status_code == 200:
                    self.whatsapp_connected = False
                    self.whatsapp_connection_status.controls[0].color = AppColors.TEXT_MUTED
                    self.whatsapp_connection_status.controls[1].value = "WhatsApp: Logged out"
                    self.whatsapp_connection_status.controls[1].color = AppColors.TEXT_MUTED
                    self._show_snackbar("Logged out & session cleared.")
            except Exception:
                self._show_snackbar("Service not running", error=True)
            self.page.update()
        threading.Thread(target=do_logout, daemon=True).start()

    def _start_whatsapp_service(self, e=None):
        service_dir = project_root / "whatsapp_service"
        if not service_dir.exists():
            self._show_snackbar("whatsapp_service directory not found", error=True)
            return
        self._do_start_whatsapp_service(service_dir)

    def _do_start_whatsapp_service(self, service_dir):
        try:
            service_url = self.whatsapp_service_url.value.strip()
            try:
                response = requests.get(f"{service_url}/status", timeout=2)
                if response.status_code == 200:
                    self._show_snackbar("WhatsApp service is already running")
                    self._check_whatsapp_status()
                    return
            except Exception:
                pass
            if sys.platform == "win32":
                self.whatsapp_process = subprocess.Popen(["npm", "start"], cwd=str(service_dir), creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                self.whatsapp_process = subprocess.Popen(["npm", "start"], cwd=str(service_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            self.whatsapp_service_status.controls[0].color = AppColors.WARNING
            self.whatsapp_service_status.controls[1].value = "Service: Starting..."
            self.whatsapp_service_status.controls[1].color = AppColors.WARNING
            self.page.update()
            self._show_snackbar("Starting WhatsApp service...")
            def check_after():
                time.sleep(3)
                self._check_whatsapp_status()
            threading.Thread(target=check_after, daemon=True).start()
        except FileNotFoundError:
            self._show_snackbar("npm not found", error=True)
        except Exception as ex:
            self._show_snackbar(f"Error: {str(ex)[:50]}", error=True)

    def _stop_whatsapp_service(self, e=None):
        service_url = self.whatsapp_service_url.value.strip()
        def stop():
            try:
                requests.post(f"{service_url}/disconnect", timeout=5)
            except Exception:
                pass
            if hasattr(self, 'whatsapp_process') and self.whatsapp_process:
                try:
                    self.whatsapp_process.terminate()
                    self.whatsapp_process.wait(timeout=5)
                    self.whatsapp_process = None
                except Exception:
                    try:
                        self.whatsapp_process.kill()
                        self.whatsapp_process = None
                    except Exception:
                        pass
            self.whatsapp_service_running = False
            self.whatsapp_connected = False
            self.whatsapp_service_status.controls[0].color = AppColors.TEXT_MUTED
            self.whatsapp_service_status.controls[1].value = "Service: Stopped"
            self.whatsapp_service_status.controls[1].color = AppColors.TEXT_MUTED
            self._show_snackbar("WhatsApp service stopped")
            self.page.update()
        threading.Thread(target=stop, daemon=True).start()

    def _save_whatsapp_settings(self, e=None):
        if hasattr(self, 'whatsapp_dm_policy'):
            self.secure_storage.set_setting('whatsapp_dm_policy', self.whatsapp_dm_policy.value)
        if hasattr(self, 'whatsapp_allowlist'):
            self.secure_storage.set_setting('whatsapp_allowlist', self.whatsapp_allowlist.value)
        if hasattr(self, 'whatsapp_group_policy'):
            self.secure_storage.set_setting('whatsapp_group_policy', self.whatsapp_group_policy.value)
        if hasattr(self, 'whatsapp_ack_reaction'):
            self.secure_storage.set_setting('whatsapp_ack_reaction', self.whatsapp_ack_reaction.value)

    def _refresh_whatsapp_contact_personas(self):
        if not hasattr(self, 'whatsapp_persona_list'):
            return
        self.whatsapp_persona_list.controls.clear()
        if not self.router or not hasattr(self.router, 'personality'):
            return
        user_personas = self.router.personality._user_profiles.get("user_personas", {})
        if not user_personas:
            self.whatsapp_persona_list.controls.append(
                ft.Text("No contact personas assigned", size=11, color=AppColors.TEXT_MUTED, italic=True))

    def _on_add_whatsapp_persona(self, e=None):
        phone = self.whatsapp_persona_phone_input.value.strip()
        persona = self.whatsapp_persona_dropdown.value
        if not phone or not persona:
            self._show_snackbar("Enter a phone number and select a persona", error=True)
            return
        phone_normalized = ''.join(c for c in phone if c.isdigit())
        if not phone_normalized:
            self._show_snackbar("Invalid phone number", error=True)
            return
        try:
            self.router.personality.set_user_persona(phone_normalized, persona)
            self.whatsapp_persona_phone_input.value = ""
            self._refresh_whatsapp_contact_personas()
            self._show_snackbar(f"Persona '{persona}' assigned to {phone_normalized}")
            self.page.update()
        except ValueError as ex:
            self._show_snackbar(str(ex), error=True)

    def _start_whatsapp_bot(self, e=None):
        if self.whatsapp_webhook_running:
            self._show_snackbar("WhatsApp bot is already running")
            return
        service_url = self.whatsapp_service_url.value.strip() or "http://localhost:3979"
        webhook_port = 3978

        def run_webhook_server():
            from http.server import HTTPServer, BaseHTTPRequestHandler
            app_ref = self

            class WhatsAppWebhookHandler(BaseHTTPRequestHandler):
                def log_message(self, format, *args):
                    pass

                def do_POST(self_handler):
                    if self_handler.path == '/whatsapp/incoming':
                        content_length = int(self_handler.headers['Content-Length'])
                        post_data = self_handler.rfile.read(content_length)
                        try:
                            data = json.loads(post_data.decode('utf-8'))
                            threading.Thread(target=app_ref._handle_whatsapp_message, args=(data,), daemon=True).start()
                            self_handler.send_response(200)
                            self_handler.send_header('Content-Type', 'application/json')
                            self_handler.end_headers()
                            self_handler.wfile.write(b'{"status": "ok"}')
                        except Exception:
                            self_handler.send_response(500)
                            self_handler.end_headers()
                    else:
                        self_handler.send_response(404)
                        self_handler.end_headers()

                def do_GET(self_handler):
                    if self_handler.path == '/health':
                        self_handler.send_response(200)
                        self_handler.send_header('Content-Type', 'application/json')
                        self_handler.end_headers()
                        self_handler.wfile.write(b'{"status": "healthy"}')
                    else:
                        self_handler.send_response(404)
                        self_handler.end_headers()

            try:
                self.whatsapp_webhook_server = HTTPServer(('0.0.0.0', webhook_port), WhatsAppWebhookHandler)
                try:
                    webhook_url = f"http://localhost:{webhook_port}/whatsapp/incoming"
                    requests.post(f"{service_url}/webhook", json={"url": webhook_url}, timeout=5)
                except Exception:
                    pass
                self.whatsapp_webhook_running = True
                self.whatsapp_bot_status.controls[0].color = AppColors.SUCCESS
                self.whatsapp_bot_status.controls[1].value = "Bot: Running"
                self.whatsapp_bot_status.controls[1].color = AppColors.SUCCESS

                # Register WhatsApp channel handler for scheduler delivery
                if self.scheduler_manager:
                    wa_service_url = service_url
                    async def _whatsapp_send_message(user_id, message, chat_id=None):
                        try:
                            target = chat_id or user_id
                            if target:
                                requests.post(
                                    f"{wa_service_url}/send",
                                    json={"chatId": target, "message": message},
                                    timeout=10,
                                )
                            return True
                        except Exception as e:
                            print(f"[Scheduler] WhatsApp delivery failed: {e}")
                            return False
                    self.scheduler_manager.register_channel_handler("whatsapp", _whatsapp_send_message)

                self.page.update()
                self._show_snackbar("WhatsApp bot started!")
                self.whatsapp_webhook_server.serve_forever()
            except OSError as ex:
                self._show_snackbar(f"Port {webhook_port} already in use", error=True)
                self.whatsapp_webhook_running = False
            except Exception:
                self.whatsapp_webhook_running = False
            self.page.update()

        threading.Thread(target=run_webhook_server, daemon=True).start()

    def _stop_whatsapp_bot(self, e=None):
        def do_stop():
            if self.whatsapp_webhook_server:
                try:
                    self.whatsapp_webhook_server.shutdown()
                except Exception:
                    pass
                self.whatsapp_webhook_server = None
            self.whatsapp_webhook_running = False
            self.whatsapp_bot_status.controls[0].color = AppColors.TEXT_MUTED
            self.whatsapp_bot_status.controls[1].value = "Bot: Stopped"
            self.whatsapp_bot_status.controls[1].color = AppColors.TEXT_MUTED
            self._show_snackbar("WhatsApp bot stopped")
            self.page.update()
        threading.Thread(target=do_stop, daemon=True).start()

    def _handle_whatsapp_message(self, data):
        try:
            sender_id = data.get("senderId", "")
            chat_id = data.get("chatId", "")
            content = data.get("content", "")
            sender_name = data.get("senderName", "User")
            if not content or not chat_id:
                return
            service_url = self.whatsapp_service_url.value.strip()
            if self.app_state and self.app_state.router:
                async def process():
                    return await self.app_state.router.handle_message(
                        channel="whatsapp", user_id=sender_id, user_message=content,
                        chat_id=chat_id, user_name=sender_name,
                    )
                response = asyncio.run(process())
                if response:
                    try:
                        requests.post(f"{service_url}/send", json={"chatId": chat_id, "message": response}, timeout=10)
                    except Exception:
                        pass
        except Exception as ex:
            import traceback
            traceback.print_exc()

    # ── Slack ────────────────────────────────────────────────────────────

    def _create_slack_section(self):
        if not hasattr(self, 'slack_bot'):
            self.slack_bot = None
        if not hasattr(self, 'slack_running'):
            self.slack_running = False
        if not hasattr(self, 'slack_loop'):
            self.slack_loop = None

        saved_bot_token = self.secure_storage.get_token('slack_bot_token')
        saved_app_token = self.secure_storage.get_token('slack_app_token')
        self._has_saved_slack_token = bool(saved_bot_token)

        self.slack_bot_token_input = ft.TextField(
            label="Bot Token (xoxb-...)", value="" if saved_bot_token else "",
            password=True, can_reveal_password=False,
            hint_text="Enter token or use saved" if saved_bot_token else "Get from Slack API",
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY), expand=True,
        )
        self.slack_app_token_input = ft.TextField(
            label="App Token (xapp-...)", value="" if saved_app_token else "",
            password=True, can_reveal_password=False,
            hint_text="Enter token or use saved" if saved_app_token else "Enable Socket Mode in Slack",
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY), expand=True,
        )
        self.slack_reveal_btn = ft.IconButton(icon=icons.VISIBILITY_OFF, icon_color=AppColors.TEXT_SECONDARY, tooltip="Reveal tokens")
        self.slack_status_icon = ft.Icon(icons.CIRCLE, color=AppColors.TEXT_MUTED, size=16)
        self.slack_status_text = ft.Text("Stopped", size=12, color=AppColors.TEXT_MUTED)
        self.slack_bot_info = ft.Text("Tokens saved \u2713" if saved_bot_token else "", size=12, color=AppColors.TEXT_SECONDARY)
        self.slack_auto_start = ft.Checkbox(
            label="Auto-start on launch", value=self.secure_storage._data.get('slack_auto_start', False),
            on_change=self._toggle_slack_auto_start,
            label_style=ft.TextStyle(size=12, color=AppColors.TEXT_SECONDARY),
        )
        self.slack_start_btn = StyledButton("Start Bot", icon=icons.PLAY_ARROW, on_click=self._toggle_slack_bot)

    def _create_slack_content(self):
        if not hasattr(self, 'slack_bot_token_input'):
            self._create_slack_section()

        status_bar = ft.Container(
            content=ft.Row([
                self.slack_status_icon, self.slack_status_text,
                ft.Container(expand=True), self.slack_bot_info,
            ], spacing=8),
            padding=ft.Padding.all(10),
            bgcolor=AppColors.SURFACE_VARIANT,
            border_radius=ft.BorderRadius.all(8),
        )

        return ft.Column([
            ft.Text("Connect via Socket Mode. Get tokens from api.slack.com/apps",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            status_bar,
            ft.Container(height=10),
            SectionHeader("Tokens", icon=icons.KEY),
            ft.Row([self.slack_bot_token_input, self.slack_reveal_btn], spacing=8),
            ft.Container(height=6),
            self.slack_app_token_input,
            ft.Container(height=10),
            ft.Row([self.slack_start_btn, ft.Container(expand=True),
                    self.slack_auto_start], spacing=8),
        ], spacing=4)

    def _toggle_slack_auto_start(self, e):
        self.secure_storage._data['slack_auto_start'] = e.control.value
        self.secure_storage._save()

    def _toggle_slack_bot(self, e):
        if self.slack_running:
            self._stop_slack_bot()
        else:
            self._start_slack_bot()

    def _start_slack_bot(self):
        if not SLACK_AVAILABLE or SlackChannel is None:
            self._show_snackbar("Slack not available", error=True)
            return
        if getattr(self, 'slack_running', False):
            self._show_snackbar("Slack bot is already running")
            return
        bot_token = self.slack_bot_token_input.value.strip() or self.secure_storage.get_token('slack_bot_token')
        app_token = self.slack_app_token_input.value.strip() or self.secure_storage.get_token('slack_app_token')
        if not bot_token or not app_token:
            self._show_snackbar("Please enter both tokens", error=True)
            return
        self.secure_storage.set_token('slack_bot_token', bot_token)
        self.secure_storage.set_token('slack_app_token', app_token)
        self.slack_bot_info.value = "Tokens saved \u2713"

        def run_slack():
            self.slack_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.slack_loop)
            async def slack_main():
                try:
                    async def handle_message(channel, user_id, user_message, **kwargs):
                        if self.app_state and self.app_state.router:
                            return await self.app_state.router.handle_message(
                                channel=channel, user_id=user_id, user_message=user_message,
                                chat_id=kwargs.get('chat_id'), user_name=kwargs.get('user_name', 'User'),
                            )
                        return "Bot not initialized."
                    slack_config = SlackConfig(
                        bot_token=bot_token, app_token=app_token,
                        allowed_users=config.SLACK_ALLOWED_USERS if BOT_AVAILABLE and hasattr(config, 'SLACK_ALLOWED_USERS') else [],
                        allowed_channels=config.SLACK_ALLOWED_CHANNELS if BOT_AVAILABLE and hasattr(config, 'SLACK_ALLOWED_CHANNELS') else [],
                    )
                    self.slack_bot = SlackChannel(config=slack_config, message_handler=handle_message)
                    await self.slack_bot.start()
                except Exception as ex:
                    self.slack_bot_info.value = f"Error: {str(ex)[:50]}"
                    self.slack_running = False
                    self.page.update()
            try:
                self.slack_loop.run_until_complete(slack_main())
            finally:
                self.slack_loop.close()

        self.slack_running = True
        self.slack_status_icon.color = AppColors.SUCCESS
        self.slack_status_text.value = "Running"
        self.slack_status_text.color = AppColors.SUCCESS
        self.page.update()
        threading.Thread(target=run_slack, daemon=True).start()
        self._show_snackbar("Slack bot starting...")

    def _stop_slack_bot(self):
        self.slack_running = False
        if self.slack_bot and self.slack_loop:
            if self.slack_loop.is_running():
                asyncio.run_coroutine_threadsafe(self.slack_bot.stop(), self.slack_loop)
        self.slack_bot = None
        self.slack_status_icon.color = AppColors.TEXT_MUTED
        self.slack_status_text.value = "Stopped"
        self.slack_status_text.color = AppColors.TEXT_MUTED
        self.page.update()
        self._show_snackbar("Slack bot stopped")

    # ── Discord ──────────────────────────────────────────────────────────

    def _create_discord_content(self):
        return ft.Column([
            ft.TextField(label="Bot Token", hint_text="Enter your Discord bot token...", password=True,
                        border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, disabled=True, expand=True),
            ft.Container(height=8),
            ft.Text("Discord integration will be available in a future update.", size=11, color=AppColors.TEXT_MUTED, italic=True),
        ], spacing=0)

    # =====================================================================
    # LLM PROVIDERS GROUP
    # =====================================================================

    def _create_llm_providers_group(self):
        local_content = self._create_local_servers_content()
        cli_content = self._create_cli_providers_content()
        cloud_content = self._create_cloud_api_content()

        group_content = ft.Column([
            SubItemAccordion(
                "Local LLM Servers", "\U0001f5a5\ufe0f",
                description="Ollama, LM Studio, MLX, vLLM",
                content=local_content),
            SubItemAccordion(
                "CLI Providers", "\u2328\ufe0f",
                description="Claude CLI, Gemini CLI (subscription)",
                content=cli_content),
            SubItemAccordion(
                "Cloud API", "\u2601\ufe0f",
                description="OpenAI, Anthropic, Groq, etc.",
                content=cloud_content),
        ], spacing=4)

        return SettingsPanel(title="LLM Providers", icon=icons.PSYCHOLOGY,
                             subtitle="Local servers, CLI tools, and cloud APIs",
                             content=group_content)

    # ── Local Servers ────────────────────────────────────────────────────

    def _create_local_servers_content(self):
        if not hasattr(self, '_local_server_list'):
            self._create_local_servers_section()
        return ft.Column([
            ft.Text("Local LLM servers that run on your machine.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            self._local_server_list,
            ft.Container(height=8),
            ft.Row([StyledButton("Refresh Status", icon=icons.REFRESH,
                                 on_click=self._refresh_local_servers,
                                 variant="outline")]),
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("Select Provider", icon=icons.PLAY_CIRCLE),
            self._local_provider_btn_row,
            ft.Container(height=8),
            self.model_status_text,
            ft.Container(height=6),
            self.local_model_dropdown,
            ft.Container(height=10),
            ft.Row([
                StyledButton("Refresh Models", icon=icons.REFRESH,
                             on_click=self._refresh_local_models,
                             variant="outline"),
                StyledButton("Use Local Server", icon=icons.PLAY_ARROW,
                             on_click=self._use_local_server),
            ], spacing=8),
        ], spacing=4)

    def _create_local_servers_section(self):
        self.local_server_cards = {}
        self._local_server_list = ft.Column(spacing=8)
        for name in LOCAL_SERVER_PROVIDERS.keys():
            is_running, status = check_local_server_status(name)
            card = ServerStatusCard(name, is_running, status)
            self.local_server_cards[name] = card
            self._local_server_list.controls.append(card)

        self.selected_local_provider = None
        provider_icons = {"ollama": "\U0001f999", "lmstudio": "\U0001f3af", "mlx": "\U0001f34e", "vllm": "\u26a1"}
        self.provider_buttons = {}
        self._local_provider_btn_row = ft.Row(wrap=True, spacing=12)
        for name in LOCAL_SERVER_PROVIDERS.keys():
            icon_text = provider_icons.get(name, "\U0001f4e6")
            btn = ft.Button(
                content=ft.Row([ft.Text(icon_text, size=18), ft.Text(name.upper(), weight=ft.FontWeight.W_600, size=13)], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=AppColors.SURFACE_VARIANT, color=AppColors.TEXT_PRIMARY,
                elevation=0,
                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=20, vertical=14), shape=ft.RoundedRectangleBorder(radius=10), side=ft.BorderSide(1, AppColors.BORDER)),
                on_click=lambda e, n=name: self._select_local_provider(n),
            )
            self.provider_buttons[name] = btn
            self._local_provider_btn_row.controls.append(btn)

        self.local_model_dropdown = ft.Dropdown(
            label="Available Models", hint_text="Select a provider first", options=[],
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, disabled=True,
        )
        self.model_status_text = ft.Text("Click a provider button to load available models", size=12, color=AppColors.TEXT_SECONDARY)

    def _select_local_provider(self, provider_name):
        self.selected_local_provider = provider_name
        for name, btn in self.provider_buttons.items():
            if name == provider_name:
                btn.bgcolor = AppColors.PRIMARY
                btn.color = AppColors.TEXT_ON_PRIMARY
            else:
                btn.bgcolor = AppColors.SURFACE_VARIANT
                btn.color = AppColors.TEXT_PRIMARY
        is_running, status = check_local_server_status(provider_name)
        if not is_running:
            self.model_status_text.value = f"{provider_name.upper()} is not running. Start it first."
            self.model_status_text.color = AppColors.WARNING
            self.local_model_dropdown.options = []
            self.local_model_dropdown.disabled = True
            self.page.update()
            return
        self.model_status_text.value = f"Loading models from {provider_name.upper()}..."
        self.page.update()
        self._load_models_for_provider(provider_name)

    def _load_models_for_provider(self, provider_name):
        try:
            models = []
            port = LOCAL_SERVER_PROVIDERS.get(provider_name, {}).get("port", 11434)
            if provider_name == "ollama":
                response = requests.get(f"http://localhost:{port}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = [m["name"] for m in response.json().get("models", [])]
            else:
                response = requests.get(f"http://localhost:{port}/v1/models", timeout=5)
                if response.status_code == 200:
                    models = [m["id"] for m in response.json().get("data", [])]
            if models:
                self.local_model_dropdown.options = [ft.dropdown.Option(m) for m in models]
                self.local_model_dropdown.value = models[0]
                self.local_model_dropdown.disabled = False
                self.model_status_text.value = f"Found {len(models)} models"
                self.model_status_text.color = AppColors.SUCCESS
            else:
                self.local_model_dropdown.options = []
                self.local_model_dropdown.disabled = True
                self.model_status_text.value = "No models found."
                self.model_status_text.color = AppColors.WARNING
        except Exception as ex:
            self.model_status_text.value = f"Error: {str(ex)[:50]}"
            self.model_status_text.color = AppColors.ERROR
            self.local_model_dropdown.options = []
            self.local_model_dropdown.disabled = True
        self.page.update()

    def _refresh_local_models(self, e=None):
        if self.selected_local_provider:
            self._load_models_for_provider(self.selected_local_provider)
        else:
            self._show_snackbar("Select a provider first", error=True)

    def _refresh_local_servers(self, e=None):
        self.page.update()

    def _use_local_server(self, e):
        provider = self.selected_local_provider
        model = self.local_model_dropdown.value
        if not provider:
            self._show_snackbar("Select a provider first", error=True)
            return
        if not model:
            self._show_snackbar("Select a model", error=True)
            return
        if not BOT_AVAILABLE or not self.app_state:
            self._show_snackbar("Bot not initialized", error=True)
            return
        is_running, status = check_local_server_status(provider)
        if not is_running:
            self._show_snackbar(f"{provider} not running", error=True)
            return
        try:
            custom_config = config.LLM_PROVIDERS.get(provider, {}).copy()
            custom_config["model"] = model
            success, msg = self.app_state.switch_provider(provider, custom_config=custom_config)
            if success:
                self._show_snackbar(f"Switched to {provider.upper()}: {model}")
                if self._refresh_model_info_callback:
                    self._refresh_model_info_callback()
            else:
                self._show_snackbar(f"Failed: {msg}", error=True)
        except Exception as ex:
            self._show_snackbar(f"Error: {str(ex)}", error=True)
        self.page.update()

    # ── CLI Providers ────────────────────────────────────────────────────

    def _create_cli_providers_content(self):
        if not hasattr(self, '_cli_list'):
            self._create_cli_providers_section()
        return ft.Column([
            ft.Text("CLI providers use your subscription (no API key needed).",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            self._cli_list,
            ft.Container(height=8),
            ft.Row([StyledButton("Refresh Status", icon=icons.REFRESH,
                                 on_click=self._refresh_cli_status,
                                 variant="outline")]),
            self.cli_status_text,
        ], spacing=4)

    def _create_cli_providers_section(self):
        self.cli_cards = {}
        self._cli_list = ft.Column(spacing=8)
        for name in CLI_PROVIDERS.keys():
            is_installed, status = check_cli_installed(name)
            card = CliStatusCard(name, is_installed, status, on_click=lambda e, n=name: self._use_cli_provider_direct(n))
            self.cli_cards[name] = card
            self._cli_list.controls.append(card)
        self.cli_status_text = ft.Text("", size=12)

    def _refresh_cli_status(self, e=None):
        self.page.update()

    def _use_cli_provider_direct(self, provider):
        if not BOT_AVAILABLE or not self.app_state:
            self.cli_status_text.value = "Bot not initialized"
            self.cli_status_text.color = AppColors.ERROR
            self.page.update()
            return
        try:
            success, msg = self.app_state.switch_provider(provider)
            if success:
                self.cli_status_text.value = f"Switched to {provider.upper()}"
                self.cli_status_text.color = AppColors.SUCCESS
                if self._refresh_model_info_callback:
                    self._refresh_model_info_callback()
            else:
                self.cli_status_text.value = f"{msg}"
                self.cli_status_text.color = AppColors.ERROR
        except Exception as ex:
            self.cli_status_text.value = f"Error: {str(ex)}"
            self.cli_status_text.color = AppColors.ERROR
        self.page.update()

    # ── Cloud API ────────────────────────────────────────────────────────

    def _create_cloud_api_content(self):
        if not hasattr(self, 'cloud_provider_dropdown'):
            self._create_cloud_api_section()
        return ft.Column([
            ft.Text("Cloud API providers require an API key.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            self.cloud_provider_dropdown,
            ft.Container(height=8),
            ft.Row([StyledButton("Switch Provider", icon=icons.CLOUD,
                                 on_click=self._use_cloud_provider)]),
            self.cloud_status_text,
            ft.Divider(height=1, color=AppColors.BORDER),
            SectionHeader("API Key Management", icon=icons.VPN_KEY),
            ft.Row([self.api_key_provider, self.api_key_input], spacing=8),
            ft.Container(height=8),
            ft.Row([
                StyledButton("Check Key", icon=icons.SEARCH,
                             on_click=self._check_api_key_status,
                             variant="outline"),
                StyledButton("Save Key", icon=icons.SAVE,
                             on_click=self._save_api_key),
            ], spacing=8),
            self.api_key_status,
        ], spacing=4)

    def _create_cloud_api_section(self):
        cloud_providers = [p for p in (config.LLM_PROVIDERS.keys() if BOT_AVAILABLE else CLOUD_API_PROVIDERS)
                          if p in CLOUD_API_PROVIDERS]
        self.cloud_provider_dropdown = ft.Dropdown(
            label="Select Cloud Provider", options=[ft.dropdown.Option(p, p.upper()) for p in cloud_providers],
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
        )
        self.cloud_status_text = ft.Text("", size=12, color=AppColors.TEXT_PRIMARY)
        self.api_key_provider = ft.Dropdown(
            label="Provider", options=[ft.dropdown.Option(p, p.upper()) for p in cloud_providers],
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
        )
        self.api_key_input = ft.TextField(
            label="API Key", password=True, can_reveal_password=True,
            border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE,
            hint_text="Enter new key or leave empty to keep existing",
        )
        self.api_key_status = ft.Text("", size=12)

    def _use_cloud_provider(self, e):
        provider = self.cloud_provider_dropdown.value
        if not provider or not BOT_AVAILABLE or not self.app_state:
            self.cloud_status_text.value = "Select a provider" if not provider else "Bot not initialized"
            self.cloud_status_text.color = AppColors.ERROR
            self.page.update()
            return
        try:
            success, msg = self.app_state.switch_provider(provider)
            if success:
                self.cloud_status_text.value = f"Switched to {provider}"
                self.cloud_status_text.color = AppColors.SUCCESS
                if self._refresh_model_info_callback:
                    self._refresh_model_info_callback()
            else:
                self.cloud_status_text.value = f"{msg}"
                self.cloud_status_text.color = AppColors.ERROR
        except Exception as ex:
            self.cloud_status_text.value = f"Error: {str(ex)}"
            self.cloud_status_text.color = AppColors.ERROR
        self.page.update()

    def _check_api_key_status(self, e):
        provider = self.api_key_provider.value
        if not provider:
            self.api_key_status.value = "Select a provider first"
            self.api_key_status.color = AppColors.ERROR
            self.page.update()
            return
        storage_key = 'api_key_groq' if provider == 'groq-large' else f'api_key_{provider}'
        saved_key = self.secure_storage.get_token(storage_key)
        if saved_key:
            self.api_key_status.value = f"Key saved for {provider.upper()} ({saved_key[:8]}...)"
            self.api_key_status.color = AppColors.SUCCESS
        else:
            self.api_key_status.value = f"No key saved for {provider.upper()}"
            self.api_key_status.color = AppColors.WARNING
        self.page.update()

    def _save_api_key(self, e):
        provider = self.api_key_provider.value
        key = self.api_key_input.value
        if not key:
            self.api_key_status.value = "Enter an API key"
            self.api_key_status.color = AppColors.ERROR
            self.page.update()
            return
        env_var = API_KEY_ENV_MAP.get(provider)
        if env_var:
            storage_key = 'api_key_groq' if provider == 'groq-large' else f'api_key_{provider}'
            self.secure_storage.set_token(storage_key, key.strip())
            os.environ[env_var] = key.strip()
            if BOT_AVAILABLE and provider in config.LLM_PROVIDERS:
                config.LLM_PROVIDERS[provider]["api_key"] = key.strip()
            self.api_key_status.value = f"Saved for {provider}"
            self.api_key_status.color = AppColors.SUCCESS
            self.api_key_input.value = ""
            self._show_snackbar(f"API key saved for {provider}")
        else:
            self.api_key_status.value = "Unknown provider"
            self.api_key_status.color = AppColors.ERROR
        self.page.update()

    def load_saved_api_keys(self):
        """Load all saved API keys from secure storage on startup."""
        for provider, env_var in API_KEY_ENV_MAP.items():
            storage_key = 'api_key_groq' if provider == 'groq-large' else f'api_key_{provider}'
            saved_key = self.secure_storage.get_token(storage_key)
            if saved_key:
                os.environ[env_var] = saved_key
                if BOT_AVAILABLE and config and provider in config.LLM_PROVIDERS:
                    config.LLM_PROVIDERS[provider]["api_key"] = saved_key

    # =====================================================================
    # MEMORY
    # =====================================================================

    def _create_memory_section(self):
        self._memory_switch = ft.Switch(value=True, active_color=AppColors.ACCENT)
        self._memory_context_slider = ft.Slider(
            min=5, max=50, divisions=45, value=20,
            active_color=AppColors.ACCENT, width=200,
        )
        self._memory_threshold_slider = ft.Slider(
            min=0, max=1, divisions=10, value=0.5,
            active_color=AppColors.ACCENT, width=200,
        )
        content = ft.Column([
            SettingRow("Persistent Memory", icon=icons.SAVE,
                       subtitle="Remember facts and preferences across sessions",
                       control=self._memory_switch),
            ft.Divider(height=1, color=AppColors.BORDER),
            SettingRow("Context Window", icon=icons.HISTORY,
                       subtitle="Max messages to include (5–50)",
                       control=self._memory_context_slider),
            ft.Divider(height=1, color=AppColors.BORDER),
            SettingRow("Importance Threshold", icon=icons.TUNE,
                       subtitle="Min relevance score for recall (0–1)",
                       control=self._memory_threshold_slider),
            ft.Divider(height=1, color=AppColors.BORDER),
            ft.Container(
                content=StyledButton("Clear All Memory", icon=icons.DELETE_SWEEP,
                                     variant="outline"),
                padding=ft.Padding.only(top=8),
            ),
        ], spacing=0)
        return SettingsPanel(title="Memory", icon=icons.MEMORY,
                             subtitle="Context retention and long-term recall",
                             content=content)

    # =====================================================================
    # PROACTIVE TASKS (SCHEDULER)
    # =====================================================================

    def _create_proactive_tasks_group(self):
        CRON_PRESETS = {
            "Every minute": "* * * * *", "Every 5 minutes": "*/5 * * * *",
            "Every 15 minutes": "*/15 * * * *", "Every hour": "0 * * * *",
            "Every day at 9 AM": "0 9 * * *", "Every day at 6 PM": "0 18 * * *",
            "Every Monday at 9 AM": "0 9 * * 1", "Every weekday at 9 AM": "0 9 * * 1-5",
            "First of month at 9 AM": "0 9 1 * *", "Custom": "",
        }
        TIMEZONES = ["UTC", "US/Eastern", "US/Pacific", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Asia/Karachi"]
        CHANNELS = ["telegram", "discord", "slack", "whatsapp", "gradio"]

        self._scheduler_task_list = ft.ListView(spacing=4, height=200)
        self._scheduler_refresh_tasks()

        self._sched_editing_task_id = None
        self._sched_name = ft.TextField(label="Task Name", hint_text="Daily Summary", dense=True, text_size=13)
        self._sched_action = ft.Dropdown(
            label="Action Type", width=200, dense=True, text_size=13,
            options=[ft.dropdown.Option("send_message", "Send Message"), ft.dropdown.Option("execute_skill", "Execute Skill")],
            value="send_message",
        )
        self._sched_action.on_change = self._sched_on_action_change
        self._sched_preset = ft.Dropdown(
            label="Schedule Preset", width=220, dense=True, text_size=13,
            options=[ft.dropdown.Option(k) for k in CRON_PRESETS], value="Every day at 9 AM",
        )
        self._sched_preset.on_change = lambda e: self._sched_on_preset_change(e, CRON_PRESETS)
        self._sched_cron = ft.TextField(label="Cron Expression", value="0 9 * * *", dense=True, text_size=13, width=200)
        self._sched_timezone = ft.Dropdown(label="Timezone", width=180, dense=True, text_size=13,
                                          options=[ft.dropdown.Option(tz) for tz in TIMEZONES], value="UTC")
        self._sched_channel = ft.Dropdown(label="Target Channel", width=180, dense=True, text_size=13,
                                         options=[ft.dropdown.Option(ch) for ch in CHANNELS], value="telegram")
        self._sched_user = ft.TextField(label="Target User ID", hint_text="user-123", dense=True, text_size=13)
        self._sched_message = ft.TextField(label="Message Content", multiline=True, min_lines=2, max_lines=4, dense=True, text_size=13)
        self._sched_skill_name = ft.TextField(label="Skill Name", dense=True, text_size=13, visible=False)
        self._sched_skill_params = ft.TextField(label="Skill Parameters", dense=True, text_size=13, visible=False)
        self._sched_save_btn = StyledButton("Create Task", icon=icons.ADD, on_click=self._scheduler_create_task)
        self._sched_cancel_btn = StyledButton("Cancel Edit", icon=icons.CANCEL, variant="outline", on_click=self._scheduler_cancel_edit, visible=False)
        self._sched_form_status = ft.Text("", size=11, color=AppColors.TEXT_SECONDARY)

        form_content = ft.Column([
            ft.Row([self._sched_name, self._sched_action], spacing=8),
            ft.Row([self._sched_preset, self._sched_cron, self._sched_timezone], spacing=8, wrap=True),
            ft.Row([self._sched_channel, self._sched_user], spacing=8),
            self._sched_message, self._sched_skill_name, self._sched_skill_params,
            ft.Row([self._sched_save_btn, self._sched_cancel_btn, self._sched_form_status], spacing=8),
        ], spacing=8)

        self._scheduler_log_list = ft.ListView(spacing=2, height=150)
        self._scheduler_refresh_log()

        task_count = len(self.scheduler_manager.tasks) if self.scheduler_manager else 0
        group_content = ft.Column([
            SubItemAccordion(
                "Task List", "\U0001f4cb",
                description=f"{task_count} tasks configured",
                content=ft.Column([
                    self._scheduler_task_list,
                    ft.Row([StyledButton("Refresh", icon=icons.REFRESH,
                                         variant="outline",
                                         on_click=lambda e: self._scheduler_refresh_tasks())],
                           spacing=8),
                ], spacing=8),
                expanded=True),
            SubItemAccordion(
                "Create / Edit Task", "\u2795",
                description="Add a new scheduled task",
                content=form_content),
            SubItemAccordion(
                "Execution Log", "\U0001f4ca",
                description="Recent task execution history",
                content=ft.Column([
                    self._scheduler_log_list,
                    ft.Row([StyledButton("Refresh Log", icon=icons.REFRESH,
                                         variant="outline",
                                         on_click=lambda e: self._scheduler_refresh_log())],
                           spacing=8),
                ], spacing=8)),
        ], spacing=4)

        return SettingsPanel(title="Proactive Tasks", icon=icons.SCHEDULE,
                             subtitle="Scheduled actions and automated workflows",
                             content=group_content)

    def _sched_on_action_change(self, e):
        is_message = (e.control.value == "send_message")
        self._sched_message.visible = is_message
        self._sched_skill_name.visible = not is_message
        self._sched_skill_params.visible = not is_message
        self.page.update()

    def _sched_on_preset_change(self, e, presets):
        cron = presets.get(e.control.value, "")
        if cron:
            self._sched_cron.value = cron
            self.page.update()

    def _run_async_scheduler(self, coro):
        loop = getattr(self, '_scheduler_loop', None)
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=10)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _scheduler_create_task(self, e=None):
        sm = self.scheduler_manager
        if not sm:
            self._sched_form_status.value = "Scheduler not initialized"
            self._sched_form_status.color = AppColors.ERROR
            self.page.update()
            return
        name = self._sched_name.value.strip()
        if not name:
            self._sched_form_status.value = "Task name is required"
            self._sched_form_status.color = AppColors.ERROR
            self.page.update()
            return
        user = self._sched_user.value.strip()
        cron = self._sched_cron.value.strip()
        action = self._sched_action.value or "send_message"
        try:
            if self._sched_editing_task_id:
                updates = {
                    "name": name, "schedule": cron, "timezone": self._sched_timezone.value or "UTC",
                    "action": action, "target_channel": self._sched_channel.value or "telegram", "target_user": user,
                    "message": self._sched_message.value.strip() if action == "send_message" else None,
                    "skill_name": self._sched_skill_name.value.strip() if action == "execute_skill" else None,
                }
                self._run_async_scheduler(sm.update_task(self._sched_editing_task_id, updates))
                self._sched_form_status.value = f"Task updated"
                self._sched_form_status.color = AppColors.SUCCESS
                self._scheduler_cancel_edit()
            else:
                task = ScheduledTask(
                    name=name, schedule=cron, timezone=self._sched_timezone.value or "UTC",
                    action=action, target_channel=self._sched_channel.value or "telegram", target_user=user,
                    message=self._sched_message.value.strip() if action == "send_message" else None,
                    skill_name=self._sched_skill_name.value.strip() if action == "execute_skill" else None,
                )
                task_id = self._run_async_scheduler(sm.add_task(task))
                self._sched_form_status.value = f"Task created: {task_id}"
                self._sched_form_status.color = AppColors.SUCCESS
            self._scheduler_refresh_tasks()
            self._sched_clear_form()
        except Exception as ex:
            self._sched_form_status.value = f"Error: {ex}"
            self._sched_form_status.color = AppColors.ERROR
        self.page.update()

    def _sched_clear_form(self):
        self._sched_name.value = ""
        self._sched_cron.value = "0 9 * * *"
        self._sched_preset.value = "Every day at 9 AM"
        self._sched_timezone.value = "UTC"
        self._sched_action.value = "send_message"
        self._sched_channel.value = "telegram"
        self._sched_user.value = ""
        self._sched_message.value = ""
        self._sched_message.visible = True
        self._sched_skill_name.value = ""
        self._sched_skill_name.visible = False
        self._sched_skill_params.value = ""
        self._sched_skill_params.visible = False

    def _scheduler_cancel_edit(self, e=None):
        self._sched_editing_task_id = None
        self._sched_cancel_btn.visible = False
        self._sched_clear_form()
        self.page.update()

    def _scheduler_edit_task(self, task_id):
        sm = self.scheduler_manager
        if not sm:
            return
        task = sm.get_task(task_id)
        if not task:
            return
        self._sched_editing_task_id = task_id
        self._sched_name.value = task.name
        self._sched_cron.value = task.schedule
        self._sched_preset.value = "Custom"
        self._sched_timezone.value = task.timezone
        self._sched_action.value = task.action
        self._sched_channel.value = task.target_channel
        self._sched_user.value = task.target_user or ""
        is_message = task.action == "send_message"
        self._sched_message.value = task.message or ""
        self._sched_message.visible = is_message
        self._sched_skill_name.value = task.skill_name or ""
        self._sched_skill_name.visible = not is_message
        self._sched_cancel_btn.visible = True
        self._sched_form_status.value = f"Editing: {task.name}"
        self._sched_form_status.color = AppColors.INFO
        self.page.update()

    def _scheduler_delete_task(self, task_id):
        sm = self.scheduler_manager
        if not sm:
            return
        try:
            self._run_async_scheduler(sm.remove_task(task_id))
            self._scheduler_refresh_tasks()
            self._show_snackbar(f"Task {task_id} deleted")
        except Exception as ex:
            self._show_snackbar(f"Error: {ex}", error=True)

    def _scheduler_toggle_task(self, task_id, enabled):
        sm = self.scheduler_manager
        if not sm:
            return
        try:
            if enabled:
                self._run_async_scheduler(sm.resume_task(task_id))
            else:
                self._run_async_scheduler(sm.pause_task(task_id))
            self._scheduler_refresh_tasks()
        except Exception as ex:
            self._show_snackbar(f"Error: {ex}", error=True)

    def _scheduler_refresh_tasks(self, e=None):
        if not hasattr(self, '_scheduler_task_list'):
            return
        self._scheduler_task_list.controls.clear()
        sm = self.scheduler_manager
        if not sm:
            self._scheduler_task_list.controls.append(ft.Text("Scheduler not initialized", size=12, color=AppColors.TEXT_MUTED, italic=True))
            try:
                self.page.update()
            except Exception:
                pass
            return
        tasks = sm.list_tasks()
        if not tasks:
            self._scheduler_task_list.controls.append(ft.Text("No tasks configured yet", size=12, color=AppColors.TEXT_MUTED, italic=True))
            try:
                self.page.update()
            except Exception:
                pass
            return
        for t in tasks:
            tid = t["id"]
            is_enabled = t.get("enabled", True)
            status = t.get("status", "active")
            status_color = AppColors.SUCCESS if status == "active" else AppColors.WARNING
            next_run = t.get("next_run", "")
            if next_run:
                try:
                    dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
                    next_run = dt.strftime("%m/%d %H:%M")
                except Exception:
                    pass
            card = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(t["name"], size=13, weight=ft.FontWeight.W_500, color=AppColors.TEXT_PRIMARY),
                        ft.Row([ft.Text(t["schedule"], size=10, color=AppColors.TEXT_SECONDARY),
                                ft.Text(f"| {t['action']}", size=10, color=AppColors.TEXT_SECONDARY),
                                ft.Text(f"| {t['target_channel']}", size=10, color=AppColors.TEXT_SECONDARY),
                                ft.Text(f"| Next: {next_run}" if next_run else "", size=10, color=AppColors.TEXT_SECONDARY)], spacing=4),
                    ], spacing=2, expand=True),
                    ft.Container(content=ft.Text(status.upper(), size=9, color="white", weight=ft.FontWeight.W_600),
                                bgcolor=status_color, padding=ft.Padding.symmetric(horizontal=6, vertical=2), border_radius=ft.BorderRadius.all(8)),
                    ft.Switch(value=is_enabled, on_change=lambda e, _tid=tid: self._scheduler_toggle_task(_tid, e.control.value), scale=0.7),
                    ft.IconButton(icon=icons.EDIT, icon_size=16, on_click=lambda e, _tid=tid: self._scheduler_edit_task(_tid)),
                    ft.IconButton(icon=icons.DELETE, icon_size=16, icon_color=AppColors.ERROR, on_click=lambda e, _tid=tid: self._scheduler_delete_task(_tid)),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                bgcolor=AppColors.SURFACE_VARIANT, border_radius=ft.BorderRadius.all(8),
            )
            self._scheduler_task_list.controls.append(card)
        try:
            self.page.update()
        except Exception:
            pass

    def _scheduler_refresh_log(self, e=None):
        if not hasattr(self, '_scheduler_log_list'):
            return
        self._scheduler_log_list.controls.clear()
        sm = self.scheduler_manager
        if not sm:
            self._scheduler_log_list.controls.append(ft.Text("Scheduler not initialized", size=12, color=AppColors.TEXT_MUTED, italic=True))
            return
        logs = sm.get_execution_log(limit=20)
        if not logs:
            self._scheduler_log_list.controls.append(ft.Text("No executions yet", size=12, color=AppColors.TEXT_MUTED, italic=True))
            return
        for log in logs:
            ts = log.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    ts = dt.strftime("%m/%d %H:%M:%S")
                except Exception:
                    pass
            success = log.get("success", False)
            error = log.get("error", "")
            row = ft.Container(
                content=ft.Row([
                    ft.Text(ts, size=10, color=AppColors.TEXT_SECONDARY, width=100),
                    ft.Text(log.get("task_name", "?"), size=11, color=AppColors.TEXT_PRIMARY, expand=True),
                    ft.Icon(icons.CHECK_CIRCLE if success else icons.ERROR, color=AppColors.SUCCESS if success else AppColors.ERROR, size=14),
                    ft.Text(error[:50] if error else "", size=10, color=AppColors.ERROR, expand=True) if error else ft.Container(),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            )
            self._scheduler_log_list.controls.append(row)

    # =====================================================================
    # HELPERS
    # =====================================================================

    def _show_snackbar(self, message, error=False):
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=AppColors.TEXT_ON_PRIMARY),
            bgcolor=AppColors.ERROR if error else AppColors.SUCCESS, open=True,
        )
        self.page.overlay.append(snackbar)
        try:
            self.page.update()
        except Exception:
            pass

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
        if hasattr(self, 'whatsapp_webhook_server') and self.whatsapp_webhook_server:
            try:
                self.whatsapp_webhook_server.shutdown()
            except Exception:
                pass
        if hasattr(self, 'whatsapp_process') and self.whatsapp_process:
            try:
                self.whatsapp_process.terminate()
                self.whatsapp_process.wait(timeout=3)
            except Exception:
                try:
                    self.whatsapp_process.kill()
                except Exception:
                    pass
