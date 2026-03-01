"""
HistoryView — conversation history browser and export.
"""

import flet as ft
from flet import Icons as icons

from coco_b.flet.theme import AppColors
from coco_b.flet.components.widgets import StyledButton


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
                ft.Text("History", size=24, weight=ft.FontWeight.W_700, color=AppColors.PRIMARY),
                ft.Container(expand=True),
                StyledButton("Export", icon=icons.DOWNLOAD),
            ]),
            padding=ft.padding.only(bottom=16),
            border=ft.border.only(bottom=ft.BorderSide(1, AppColors.BORDER))
        )
        self.history_list = ft.ListView(expand=True)
        return ft.Column([header, self.history_list], expand=True, spacing=0)

    def refresh(self):
        """Refresh history list."""
        self.history_list.controls.clear()
        if self.session_manager:
            history = self.session_manager.get_conversation_history(
                self.session_manager.get_session_key("flet", self.current_user_id))
            for msg in history or []:
                role_icon = "\U0001f464" if msg['role'] == 'user' else "\U0001f916"
                self.history_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{role_icon} {msg['role'].title()}", size=12, weight=ft.FontWeight.W_600),
                            ft.Text(msg['content'][:200] + ("..." if len(msg['content']) > 200 else ""),
                                   size=12, color=AppColors.TEXT_SECONDARY),
                        ], spacing=2),
                        padding=ft.padding.all(8), bgcolor=AppColors.SURFACE,
                        border=ft.border.all(1, AppColors.BORDER), border_radius=ft.border_radius.all(6),
                    )
                )
