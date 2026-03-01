"""
ClawHubPanel — marketplace search/install for OpenClaw.ai community skills.
"""

import flet as ft
from flet import Icons as icons

from coco_b.flet.theme import AppColors
from coco_b.flet.components.widgets import StyledButton


class ClawHubPanel:
    """ClawHub marketplace panel."""

    def __init__(self, page: ft.Page, app_state, router):
        self.page = page
        self.app_state = app_state
        self.router = router

    def _get_clawhub(self):
        """Get ClawHub manager from router."""
        if self.router:
            return getattr(self.router, '_clawhub_manager', None)
        return None

    def build(self) -> ft.Column:
        header = ft.Container(
            content=ft.Row([
                ft.Text("ClawHub", size=24, weight=ft.FontWeight.W_700, color=AppColors.PRIMARY),
                ft.Text("  OpenClaw.ai Community Skills", size=13, color=AppColors.TEXT_SECONDARY),
                ft.Container(expand=True),
                StyledButton("Installed", icon=icons.DOWNLOAD_DONE, on_click=self._show_installed, variant="outline"),
                ft.Container(width=8),
                StyledButton("Check Updates", icon=icons.UPDATE, on_click=self._check_updates, variant="outline"),
            ]),
            padding=ft.padding.only(bottom=16),
            border=ft.border.only(bottom=ft.BorderSide(1, AppColors.BORDER))
        )

        self.search_field = ft.TextField(
            hint_text="Search 5,700+ community skills...", expand=True,
            border_color=AppColors.BORDER, focused_border_color=AppColors.SECONDARY,
            color=AppColors.TEXT_PRIMARY, on_submit=self._search,
        )
        search_row = ft.Row([self.search_field, ft.Container(width=8),
                             StyledButton("Search", icon=icons.SEARCH, on_click=self._search)])

        self.results_list = ft.ListView(expand=True, spacing=8, padding=ft.padding.all(8))
        self.results_list.controls.append(
            ft.Text("Search ClawHub to discover community skills.", size=13, color=AppColors.TEXT_SECONDARY))

        return ft.Column([header, ft.Container(height=8), search_row, ft.Container(height=8),
                         self.results_list], expand=True, spacing=0)

    def _search(self, e=None):
        query = self.search_field.value
        if not query or not query.strip():
            return

        self.results_list.controls.clear()
        self.results_list.controls.append(ft.Text("Searching...", size=13, color=AppColors.TEXT_SECONDARY, italic=True))
        self.page.update()

        clawhub = self._get_clawhub()
        if clawhub is None:
            self.results_list.controls.clear()
            self.results_list.controls.append(ft.Text("ClawHub manager not available.", color=AppColors.ERROR))
            self.page.update()
            return

        results = clawhub.search(query.strip())
        self.results_list.controls.clear()

        if results is None:
            self.results_list.controls.append(ft.Text("Could not reach ClawHub. Please try again later.", color=AppColors.ERROR))
        elif not results:
            self.results_list.controls.append(ft.Text(f'No skills found for "{query}".', color=AppColors.TEXT_SECONDARY))
        else:
            self.results_list.controls.append(ft.Text(f"{len(results)} skills found", size=12, color=AppColors.TEXT_SECONDARY))
            for r in results:
                self.results_list.controls.append(self._create_skill_card(r))
        self.page.update()

    def _create_skill_card(self, skill_data):
        emoji = skill_data.get("emoji", "\U0001f4e6")
        name = skill_data.get("name", skill_data.get("slug", "unknown"))
        desc = skill_data.get("description", "")
        author = skill_data.get("author", "")
        downloads = skill_data.get("downloads", 0)
        slug = skill_data.get("slug", name)

        info_parts = []
        if author:
            info_parts.append(f"by {author}")
        if downloads:
            info_parts.append(f"{downloads:,} installs")
        info_text = " \u00b7 ".join(info_parts) if info_parts else ""

        return ft.Container(
            content=ft.Row([
                ft.Text(emoji, size=24), ft.Container(width=8),
                ft.Column([
                    ft.Text(name, size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                    ft.Text(desc, size=12, color=AppColors.TEXT_SECONDARY, max_lines=2),
                    ft.Text(info_text, size=11, color=AppColors.TEXT_SECONDARY, italic=True) if info_text else ft.Container(),
                ], spacing=2, expand=True),
                StyledButton("Install", icon=icons.DOWNLOAD, on_click=lambda e, s=slug: self._install(s), variant="outline"),
            ], alignment=ft.MainAxisAlignment.START),
            padding=ft.padding.all(12), border_radius=ft.border_radius.all(8),
            border=ft.border.all(1, AppColors.BORDER), bgcolor=AppColors.SURFACE,
        )

    def _install(self, slug):
        clawhub = self._get_clawhub()
        if clawhub is None:
            return
        success, msg = clawhub.install_skill(slug)
        dialog = ft.AlertDialog(
            title=ft.Text("Install Result"), content=ft.Text(msg, color=AppColors.TEXT_PRIMARY),
            actions=[ft.TextButton("OK", on_click=lambda e: self._close_dialog(dialog))],
            bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_installed(self, e=None):
        clawhub = self._get_clawhub()
        if clawhub is None:
            return
        installed = clawhub.list_installed()
        self.results_list.controls.clear()

        if not installed:
            self.results_list.controls.append(ft.Text("No ClawHub skills installed yet.", color=AppColors.TEXT_SECONDARY))
        else:
            self.results_list.controls.append(ft.Text(f"{len(installed)} installed ClawHub skills", size=12, color=AppColors.TEXT_SECONDARY))
            for s in installed:
                slug = s["slug"]
                version = s.get("version", "?")
                author = s.get("author", "")
                author_str = f" by {author}" if author else ""
                card = ft.Container(
                    content=ft.Row([
                        ft.Text("\U0001f4e6", size=24), ft.Container(width=8),
                        ft.Column([
                            ft.Text(slug, size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                            ft.Text(f"v{version}{author_str}", size=12, color=AppColors.TEXT_SECONDARY),
                        ], spacing=2, expand=True),
                        StyledButton("Uninstall", icon=icons.DELETE, on_click=lambda e, sl=slug: self._uninstall(sl), variant="outline"),
                    ], alignment=ft.MainAxisAlignment.START),
                    padding=ft.padding.all(12), border_radius=ft.border_radius.all(8),
                    border=ft.border.all(1, AppColors.BORDER), bgcolor=AppColors.SURFACE,
                )
                self.results_list.controls.append(card)
        self.page.update()

    def _uninstall(self, slug):
        clawhub = self._get_clawhub()
        if clawhub is None:
            return
        success, msg = clawhub.uninstall_skill(slug)
        dialog = ft.AlertDialog(
            title=ft.Text("Uninstall Result"), content=ft.Text(msg, color=AppColors.TEXT_PRIMARY),
            actions=[ft.TextButton("OK", on_click=lambda e: self._close_dialog(dialog))],
            bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
        if success:
            self._show_installed()

    def _check_updates(self, e=None):
        clawhub = self._get_clawhub()
        if clawhub is None:
            return
        updates = clawhub.check_updates()
        self.results_list.controls.clear()

        if not updates:
            self.results_list.controls.append(ft.Text("All ClawHub skills are up to date.", color=AppColors.TEXT_SECONDARY))
        else:
            self.results_list.controls.append(ft.Text(f"{len(updates)} updates available", size=12, color=AppColors.TEXT_SECONDARY))
            for u in updates:
                card = ft.Container(
                    content=ft.Row([
                        ft.Text("\U0001f504", size=24), ft.Container(width=8),
                        ft.Column([
                            ft.Text(u["slug"], size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY),
                            ft.Text(f"v{u['installed_version']} \u2192 v{u['latest_version']}", size=12, color=AppColors.SECONDARY),
                        ], spacing=2, expand=True),
                    ], alignment=ft.MainAxisAlignment.START),
                    padding=ft.padding.all(12), border_radius=ft.border_radius.all(8),
                    border=ft.border.all(1, AppColors.BORDER), bgcolor=AppColors.SURFACE,
                )
                self.results_list.controls.append(card)
        self.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        self.page.update()
