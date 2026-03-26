"""
Status cards — ServerStatusCard, CliStatusCard.
Refined design with subtle shadows and left accent indicators.
"""

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors, LOCAL_SERVER_PROVIDERS, CLI_PROVIDERS


class ServerStatusCard(ft.Container):
    """Card showing local server status with accent indicator."""

    def __init__(self, name: str, is_running: bool, status_text: str):
        cmd = LOCAL_SERVER_PROVIDERS[name]["start_cmd"]
        desc = LOCAL_SERVER_PROVIDERS[name]["desc"]

        status_color = AppColors.SUCCESS if is_running else AppColors.TEXT_MUTED
        status_icon = icons.CHECK_CIRCLE if is_running else icons.CIRCLE_OUTLINED

        # Left accent bar — green when running, muted when not
        accent = ft.Container(
            width=3, height=40,
            bgcolor=AppColors.SUCCESS if is_running else AppColors.BORDER,
            border_radius=ft.BorderRadius.all(2),
        )

        content = ft.Column([
            ft.Row([
                accent,
                ft.Icon(icons.STORAGE, color=AppColors.PRIMARY, size=22),
                ft.Column([
                    ft.Text(name.upper(), size=13, weight=ft.FontWeight.W_600,
                            color=AppColors.TEXT_PRIMARY),
                    ft.Text(desc, size=11, color=AppColors.TEXT_SECONDARY),
                ], spacing=1, expand=True),
                ft.Icon(status_icon, color=status_color, size=18),
                ft.Text(status_text, size=11, color=status_color,
                        weight=ft.FontWeight.W_500),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                content=ft.Column([
                    ft.Text("To start:", size=11, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(cmd, size=11, selectable=True,
                                        font_family="monospace",
                                        color=AppColors.TEXT_PRIMARY),
                        padding=ft.Padding.all(8),
                        bgcolor=AppColors.SURFACE_VARIANT,
                        border_radius=ft.BorderRadius.all(6),
                    ),
                ], spacing=4),
                visible=not is_running,
                padding=ft.Padding.only(top=8, left=16),
            ),
        ], spacing=0)

        super().__init__(
            content=content,
            padding=ft.Padding.only(left=4, right=14, top=12, bottom=12),
            bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(10),
        )


class CliStatusCard(ft.Container):
    """Card showing CLI provider status - clickable to switch provider."""

    def __init__(self, name: str, is_installed: bool, status_text: str,
                 on_click=None):
        self.provider_name = name
        self.is_installed = is_installed
        info = CLI_PROVIDERS[name]

        status_color = AppColors.SUCCESS if is_installed else AppColors.TEXT_MUTED
        status_icon = icons.CHECK_CIRCLE if is_installed else icons.CIRCLE_OUTLINED

        accent = ft.Container(
            width=3, height=40,
            bgcolor=AppColors.SUCCESS if is_installed else AppColors.BORDER,
            border_radius=ft.BorderRadius.all(2),
        )

        action_button = ft.Container(
            content=ft.Text("Use", size=11, color=ft.Colors.WHITE,
                            weight=ft.FontWeight.W_600),
            padding=ft.Padding.only(left=12, right=12, top=5, bottom=5),
            bgcolor=AppColors.PRIMARY,
            border_radius=ft.BorderRadius.all(6),
            visible=is_installed,
        ) if is_installed else ft.Container()

        content = ft.Column([
            ft.Row([
                accent,
                ft.Icon(icons.TERMINAL, color=AppColors.PRIMARY, size=22),
                ft.Column([
                    ft.Text(name.upper(), size=13, weight=ft.FontWeight.W_600,
                            color=AppColors.TEXT_PRIMARY),
                    ft.Text(info["desc"], size=11, color=AppColors.TEXT_SECONDARY),
                ], spacing=1, expand=True),
                ft.Icon(status_icon, color=status_color, size=18),
                ft.Text(status_text, size=11, color=status_color,
                        weight=ft.FontWeight.W_500),
                action_button,
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                content=ft.Column([
                    ft.Text("Install with:", size=11, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(info["install"], size=11, selectable=True,
                                        font_family="monospace",
                                        color=AppColors.TEXT_PRIMARY),
                        padding=ft.Padding.all(8),
                        bgcolor=AppColors.SURFACE_VARIANT,
                        border_radius=ft.BorderRadius.all(6),
                    ),
                ], spacing=4),
                visible=not is_installed,
                padding=ft.Padding.only(top=8, left=16),
            ),
        ], spacing=0)

        super().__init__(
            content=content,
            padding=ft.Padding.only(left=4, right=14, top=12, bottom=12),
            bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(10),
            on_click=on_click if is_installed else None,
            ink=is_installed,
        )
