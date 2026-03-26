"""
ChatMessage — chat bubble with Markdown rendering for assistant messages
and optional image attachment display.
"""

from typing import Optional, List

import flet as ft
from flet import Icons as icons

from skillforge import PROJECT_ROOT
from skillforge.flet.theme import AppColors


class ChatMessage(ft.Row):
    """A chat message bubble with Markdown rendering for assistant responses
    and optional image attachment rendering."""

    def __init__(
        self,
        text: str,
        is_user: bool = False,
        timestamp: Optional[str] = None,
        attachments: Optional[List] = None,
    ):
        # Avatar
        if is_user:
            avatar = ft.CircleAvatar(
                content=ft.Icon(icons.PERSON, size=18),
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                radius=18,
            )
        else:
            icon_path = PROJECT_ROOT / "icon" / "chat_icon.png"
            if icon_path.exists():
                avatar = ft.Container(
                    content=ft.Image(src=str(icon_path), width=32, height=32),
                    width=36, height=36,
                    alignment=ft.Alignment(0, 0),
                )
            else:
                avatar = ft.CircleAvatar(
                    content=ft.Icon(icons.SMART_TOY, size=18),
                    color=ft.Colors.WHITE,
                    bgcolor=AppColors.SECONDARY,
                    radius=18,
                )

        # Build list of controls for the message column
        column_controls = []

        # Name label
        if is_user:
            label_color = AppColors.PRIMARY
        else:
            label_color = AppColors.SECONDARY
        column_controls.append(
            ft.Text("You" if is_user else "SkillForge",
                     weight=ft.FontWeight.W_600, size=12, color=label_color),
        )

        # Render image attachments above the text body (if any)
        if attachments:
            for att in attachments:
                file_path = att.file_path if hasattr(att, "file_path") else str(att)
                column_controls.append(
                    ft.Container(
                        content=ft.Image(
                            src=file_path,
                            width=300,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=ft.BorderRadius.all(8),
                        ),
                        padding=ft.Padding.only(top=4, bottom=4),
                    )
                )

        # Message body — user gets plain Text, assistant gets Markdown
        if is_user:
            body = ft.Text(text, selectable=True, size=14,
                           color=AppColors.TEXT_PRIMARY, no_wrap=False)
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

        column_controls.append(body)

        if timestamp:
            column_controls.append(
                ft.Text(timestamp, size=10, color=AppColors.TEXT_MUTED, italic=True)
            )

        # Wrap message in a bubble container
        if is_user:
            bubble_bg = ft.Colors.with_opacity(0.09, AppColors.PRIMARY_LIGHT)
            bubble_border = ft.Colors.with_opacity(0.25, AppColors.PRIMARY_LIGHT)
        else:
            bubble_bg = AppColors.SURFACE
            bubble_border = AppColors.BORDER

        message_bubble = ft.Container(
            content=ft.Column(column_controls, tight=True, spacing=4),
            bgcolor=bubble_bg,
            border=ft.Border.all(1, bubble_border),
            border_radius=ft.BorderRadius.all(12),
            padding=ft.Padding.only(left=14, right=14, top=10, bottom=10),
            expand=True,
        )

        super().__init__(
            controls=[avatar, message_bubble],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=10,
        )
