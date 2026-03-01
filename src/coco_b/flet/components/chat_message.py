"""
ChatMessage — chat bubble with Markdown rendering for assistant messages.
"""

from typing import Optional

import flet as ft
from flet import Icons as icons

from coco_b import PROJECT_ROOT
from coco_b.flet.theme import AppColors


class ChatMessage(ft.Row):
    """A chat message bubble with Markdown rendering for assistant responses."""

    def __init__(self, text: str, is_user: bool = False, timestamp: Optional[str] = None):
        bubble_bg = AppColors.PRIMARY if is_user else AppColors.SURFACE
        text_color = AppColors.TEXT_ON_PRIMARY if is_user else AppColors.TEXT_PRIMARY

        # Avatar
        if is_user:
            avatar = ft.CircleAvatar(
                content=ft.Icon(icons.PERSON, size=20),
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                radius=18,
            )
        else:
            icon_path = PROJECT_ROOT / "icon" / "inner_chat.png"
            avatar = ft.Image(src=str(icon_path), width=36, height=36)

        # Message body — user gets plain Text, assistant gets Markdown
        if is_user:
            body = ft.Text(text, selectable=True, size=14, color=text_color, no_wrap=False)
        else:
            body = ft.Markdown(
                text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                code_theme="atom-one-dark",
                code_style_sheet=ft.MarkdownStyleSheet(
                    code_text_style=ft.TextStyle(size=13, font_family="monospace"),
                ),
            )

        message_column = ft.Column(
            [
                ft.Text("You" if is_user else "coco B", weight=ft.FontWeight.BOLD, size=12, color=text_color),
                body,
            ],
            tight=True,
            spacing=4,
            expand=True,
        )

        if timestamp:
            message_column.controls.append(
                ft.Text(timestamp, size=10, color=AppColors.TEXT_MUTED, italic=True)
            )

        super().__init__(
            controls=[avatar, message_column],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=12,
        )
