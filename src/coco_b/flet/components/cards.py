"""
Status cards — ServerStatusCard, CliStatusCard.
"""

import flet as ft
from flet import Icons as icons

from coco_b.flet.theme import AppColors, LOCAL_SERVER_PROVIDERS, CLI_PROVIDERS


class ServerStatusCard(ft.Container):
    """Card showing local server status."""

    def __init__(self, name: str, is_running: bool, status_text: str):
        cmd = LOCAL_SERVER_PROVIDERS[name]["start_cmd"]
        desc = LOCAL_SERVER_PROVIDERS[name]["desc"]

        status_color = AppColors.SUCCESS if is_running else AppColors.ERROR
        status_icon = icons.CHECK_CIRCLE if is_running else icons.ERROR

        content = ft.Column([
            ft.Row([
                ft.Icon(icons.STORAGE, color=AppColors.PRIMARY, size=24),
                ft.Column([
                    ft.Text(name.upper(), size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                    ft.Text(desc, size=11, color=AppColors.TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Icon(status_icon, color=status_color, size=20),
                ft.Text(status_text, size=12, color=status_color, weight=ft.FontWeight.W_500),
            ], spacing=8),
            ft.Container(
                content=ft.Column([
                    ft.Text("To start:", size=11, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(cmd, size=11, selectable=True, font_family="monospace", color=AppColors.TEXT_PRIMARY),
                        padding=ft.padding.all(8), bgcolor=AppColors.SURFACE_VARIANT, border_radius=ft.border_radius.all(6)
                    ),
                ], spacing=4),
                visible=not is_running, padding=ft.padding.only(top=8)
            ),
        ], spacing=0)

        super().__init__(content=content, padding=ft.padding.all(12), bgcolor=AppColors.SURFACE,
                        border=ft.border.all(1, AppColors.BORDER), border_radius=ft.border_radius.all(8))


class CliStatusCard(ft.Container):
    """Card showing CLI provider status - clickable to switch provider."""

    def __init__(self, name: str, is_installed: bool, status_text: str, on_click=None):
        self.provider_name = name
        self.is_installed = is_installed
        info = CLI_PROVIDERS[name]

        status_color = AppColors.SUCCESS if is_installed else AppColors.WARNING
        status_icon = icons.CHECK_CIRCLE if is_installed else icons.WARNING

        action_button = ft.Container(
            content=ft.Text("Use", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
            padding=ft.padding.only(left=12, right=12, top=6, bottom=6),
            bgcolor=AppColors.PRIMARY,
            border_radius=ft.border_radius.all(6),
            visible=is_installed,
        ) if is_installed else ft.Container()

        content = ft.Column([
            ft.Row([
                ft.Icon(icons.TERMINAL, color=AppColors.PRIMARY, size=24),
                ft.Column([
                    ft.Text(name.upper(), size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                    ft.Text(info["desc"], size=11, color=AppColors.TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Icon(status_icon, color=status_color, size=20),
                ft.Text(status_text, size=12, color=status_color, weight=ft.FontWeight.W_500),
                action_button,
            ], spacing=8),
            ft.Container(
                content=ft.Column([
                    ft.Text("Install with:", size=11, color=AppColors.TEXT_SECONDARY),
                    ft.Container(
                        content=ft.Text(info["install"], size=11, selectable=True, font_family="monospace", color=AppColors.TEXT_PRIMARY),
                        padding=ft.padding.all(8), bgcolor=AppColors.SURFACE_VARIANT, border_radius=ft.border_radius.all(6)
                    ),
                ], spacing=4),
                visible=not is_installed, padding=ft.padding.only(top=8)
            ),
        ], spacing=0)

        super().__init__(
            content=content, padding=ft.padding.all(12), bgcolor=AppColors.SURFACE,
            border=ft.border.all(1, AppColors.BORDER), border_radius=ft.border_radius.all(8),
            on_click=on_click if is_installed else None,
            ink=is_installed,
        )
