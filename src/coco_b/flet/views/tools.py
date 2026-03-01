"""
ToolsView — tabbed container wrapping MCP, Skills, and ClawHub panels.

Uses Flet 0.80+ Tabs/TabBar/TabBarView API.
"""

import flet as ft
from flet import Icons as icons

from coco_b.flet.theme import AppColors


class ToolsView:
    """Tabbed container combining MCP, Skills, and ClawHub into a single nav item."""

    def __init__(self, page: ft.Page, mcp_panel, skills_panel, clawhub_panel):
        self.page = page
        self.mcp_panel = mcp_panel
        self.skills_panel = skills_panel
        self.clawhub_panel = clawhub_panel

    def build(self) -> ft.Column:
        header = ft.Text("Tools", size=24, weight=ft.FontWeight.W_700, color=AppColors.PRIMARY)

        # Build panel contents
        mcp_content = ft.Container(content=self.mcp_panel.build(), padding=ft.padding.only(top=8), expand=True)
        skills_content = ft.Container(content=self.skills_panel.build(), padding=ft.padding.only(top=8), expand=True)
        clawhub_content = ft.Container(content=self.clawhub_panel.build(), padding=ft.padding.only(top=8), expand=True)

        tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label="MCP Servers", icon=icons.DEVICE_HUB),
                ft.Tab(label="Skills", icon=icons.EXTENSION),
                ft.Tab(label="ClawHub", icon=icons.STORE),
            ],
            indicator_color=AppColors.SECONDARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SECONDARY,
        )

        tab_bar_view = ft.TabBarView(
            controls=[mcp_content, skills_content, clawhub_content],
            expand=True,
        )

        tabs = ft.Tabs(
            length=3,
            selected_index=0,
            content=ft.Column([tab_bar, tab_bar_view], expand=True, spacing=0),
            expand=True,
        )

        return ft.Column([header, tabs], expand=True, spacing=0)
