"""
Reusable Flet widgets — CollapsibleSection, StatusBadge, StyledButton.
"""

from typing import Optional

import flet as ft
from flet import Icons as icons

from coco_b.flet.theme import AppColors


class CollapsibleSection(ft.Container):
    """A collapsible section with header and content."""

    def __init__(self, title: str, content: ft.Control, icon: Optional[str] = None, expanded: bool = True, **kwargs):
        self.is_expanded = expanded
        self.expand_icon = ft.Icon(icons.EXPAND_LESS if expanded else icons.EXPAND_MORE, color=AppColors.TEXT_SECONDARY, size=20)

        header_content = [
            ft.Icon(icon, color=AppColors.PRIMARY, size=20) if icon else ft.Container(),
            ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY, expand=True),
            self.expand_icon,
        ]

        self.header = ft.Container(
            content=ft.Row(header_content, spacing=12),
            padding=ft.padding.only(left=16, right=16, top=12, bottom=12),
            border_radius=ft.border_radius.all(8),
            bgcolor=AppColors.SURFACE_VARIANT,
            on_click=self._toggle_expand,
        )

        self.content_container = ft.Container(content=content, padding=ft.padding.all(16), visible=expanded)

        super().__init__(
            content=ft.Column([self.header, self.content_container], spacing=0),
            border=ft.border.all(1, AppColors.BORDER),
            border_radius=ft.border_radius.all(12),
            bgcolor=AppColors.SURFACE,
            **kwargs
        )

    def _toggle_expand(self, e):
        self.is_expanded = not self.is_expanded
        self.content_container.visible = self.is_expanded
        self.expand_icon.name = icons.EXPAND_LESS if self.is_expanded else icons.EXPAND_MORE
        self.update()


class StatusBadge(ft.Container):
    """A status badge with icon and text."""

    def __init__(self, text: str, status: str = "info"):
        colors = {
            "success": (AppColors.SUCCESS, AppColors.SUCCESS_LIGHT),
            "warning": (AppColors.WARNING, AppColors.WARNING_LIGHT),
            "error": (AppColors.ERROR, AppColors.ERROR_LIGHT),
            "info": (AppColors.INFO, AppColors.INFO_LIGHT),
        }
        color, bg = colors.get(status, colors["info"])
        status_icons = {"success": icons.CHECK_CIRCLE, "warning": icons.WARNING, "error": icons.ERROR, "info": icons.INFO}

        super().__init__(
            content=ft.Row([ft.Icon(status_icons.get(status, icons.INFO), color=color, size=16), ft.Text(text, size=12, color=color)], spacing=6),
            padding=ft.padding.only(left=12, right=12, top=6, bottom=6), bgcolor=bg, border_radius=ft.border_radius.all(20)
        )


class StyledButton(ft.Button):
    """Styled button with consistent theming."""

    def __init__(self, text: str, on_click=None, icon=None, variant="primary", expand=False, **kwargs):
        colors = {
            "primary": (AppColors.PRIMARY, AppColors.TEXT_ON_PRIMARY, 2),
            "secondary": (AppColors.SECONDARY, AppColors.TEXT_PRIMARY, 2),
            "outline": (AppColors.SURFACE, AppColors.PRIMARY, 0),
            "text": (None, AppColors.PRIMARY, 0),
        }
        bgcolor, color, elevation = colors.get(variant, colors["primary"])

        if icon:
            content = ft.Row([
                ft.Icon(icon, color=color, size=18),
                ft.Text(text, color=color, weight=ft.FontWeight.W_500)
            ], spacing=8, tight=True)
        else:
            content = ft.Text(text, color=color, weight=ft.FontWeight.W_500)

        super().__init__(
            content=content,
            on_click=on_click, bgcolor=bgcolor, color=color, elevation=elevation,
            style=ft.ButtonStyle(padding=ft.padding.only(left=20, right=20, top=10, bottom=10),
                               shape=ft.RoundedRectangleBorder(radius=8),
                               side=ft.BorderSide(1, AppColors.PRIMARY) if variant == "outline" else None),
            expand=expand, **kwargs
        )
