"""
HistoryView — conversation history browser and export.
"""

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors, Spacing
from skillforge.flet.components.widgets import StyledButton


class HistoryView:
    """Conversation history view."""

    def __init__(self, page: ft.Page, app_state, session_manager):
        self.page = page
        self.app_state = app_state
        self.session_manager = session_manager
        self.current_user_id = "user-001"

    def build(self) -> ft.Column:
        header = ft.Container(
            content=ft.Row([
                ft.Icon(icons.HISTORY, color=AppColors.PRIMARY, size=24),
                ft.Text("History", size=22, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                ft.Container(expand=True),
                StyledButton("Refresh", icon=icons.REFRESH, on_click=lambda e: self.refresh(),
                             variant="outline"),
                ft.Container(width=8),
                StyledButton("Export", icon=icons.DOWNLOAD, variant="outline"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(bottom=Spacing.MD),
            border=ft.Border.only(bottom=ft.BorderSide(1, AppColors.BORDER))
        )
        self.history_list = ft.ListView(expand=True, spacing=Spacing.SM,
                                         padding=ft.Padding.only(top=Spacing.SM))
        return ft.Column([header, self.history_list], expand=True, spacing=0)

    def refresh(self):
        """Refresh history list."""
        self.history_list.controls.clear()
        if self.session_manager:
            history = self.session_manager.get_conversation_history(
                self.session_manager.get_session_key("flet", self.current_user_id))
            if not history:
                self.history_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(icons.CHAT_BUBBLE_OUTLINE, size=48, color=AppColors.TEXT_MUTED),
                            ft.Text("No conversation history",
                                    size=14, weight=ft.FontWeight.W_500,
                                    color=AppColors.TEXT_SECONDARY),
                            ft.Text("Start chatting to see your conversation history here.",
                                    size=12, color=AppColors.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                        padding=ft.padding.only(top=60),
                    ))
                self.page.update()
                return

            for msg in history:
                is_user = msg['role'] == 'user'
                role_icon = icons.PERSON if is_user else icons.SMART_TOY
                role_color = AppColors.PRIMARY if is_user else AppColors.SECONDARY
                role_label = "You" if is_user else "SkillForge"
                content_preview = msg['content'][:300]
                if len(msg['content']) > 300:
                    content_preview += "..."

                self.history_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(role_icon, color="white", size=14),
                                width=26, height=26,
                                bgcolor=role_color,
                                border_radius=ft.BorderRadius.all(13),
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Column([
                                ft.Text(role_label, size=12, weight=ft.FontWeight.W_600,
                                        color=AppColors.TEXT_PRIMARY),
                                ft.Text(content_preview, size=12,
                                        color=AppColors.TEXT_SECONDARY,
                                        max_lines=3,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2, expand=True),
                        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                        padding=ft.Padding.all(Spacing.SM + 2),
                        bgcolor=AppColors.SURFACE,
                        border=ft.Border.all(1, AppColors.BORDER),
                        border_radius=ft.BorderRadius.all(8),
                    )
                )
        self.page.update()
