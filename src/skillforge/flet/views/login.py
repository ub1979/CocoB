"""
Login gate for SkillForge Flet UI.

First run: admin account setup form.
Subsequent runs: login form.
On success, calls on_authenticated callback to show the main app.
"""

import flet as ft
from flet import Icons as icons
from skillforge import PROJECT_ROOT
from skillforge.flet.theme import AppColors, Spacing
from skillforge.flet.storage import SecureStorage


class LoginView:
    """Login screen that gates access to the main application."""

    def __init__(self, page: ft.Page, storage: SecureStorage, on_authenticated):
        self.page = page
        self.storage = storage
        self.on_authenticated = on_authenticated
        self._is_setup = not storage.has_admin()

    def build(self) -> ft.Container:
        """Build the login/setup view."""
        icon_path = PROJECT_ROOT / "icon" / "icon.png"

        self.username_field = ft.TextField(
            label="Username",
            width=320,
            prefix_icon=icons.PERSON,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.SECONDARY,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            on_submit=lambda e: self._handle_submit(e),
        )
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            width=320,
            prefix_icon=icons.LOCK,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.SECONDARY,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            on_submit=lambda e: self._handle_submit(e),
        )
        self.confirm_field = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True,
            width=320,
            prefix_icon=icons.LOCK_OUTLINE,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.SECONDARY,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            visible=self._is_setup,
            on_submit=lambda e: self._handle_submit(e),
        )
        self.error_text = ft.Text(
            "", color=AppColors.ERROR, size=13, visible=False,
            text_align=ft.TextAlign.CENTER, width=320,
        )
        self.submit_btn = ft.Button(
            content=ft.Row([
                ft.Icon(
                    icons.ADMIN_PANEL_SETTINGS if self._is_setup else icons.LOGIN,
                    color=AppColors.TEXT_ON_PRIMARY, size=18,
                ),
                ft.Text(
                    "Create Admin Account" if self._is_setup else "Login",
                    color=AppColors.TEXT_ON_PRIMARY,
                    weight=ft.FontWeight.W_600,
                ),
            ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
            on_click=self._handle_submit,
            width=320,
            bgcolor=AppColors.SECONDARY,
            style=ft.ButtonStyle(
                padding=ft.Padding.only(top=14, bottom=14),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        title = "Create Admin Account" if self._is_setup else "Welcome Back"
        subtitle = ("Set up your admin credentials to get started."
                     if self._is_setup
                     else "Sign in to continue to SkillForge.")

        logo = (ft.Image(src=str(icon_path), width=100, height=100)
                if icon_path.exists()
                else ft.Icon(icons.SMART_TOY, size=80, color=AppColors.SECONDARY))

        # Decorative line under the logo
        accent_line = ft.Container(
            width=60, height=3,
            bgcolor=AppColors.SECONDARY,
            border_radius=ft.BorderRadius.all(2),
        )

        form_card = ft.Container(
            content=ft.Column(
                controls=[
                    logo,
                    accent_line,
                    ft.Container(height=4),
                    ft.Text(title, size=22, weight=ft.FontWeight.BOLD,
                            color=AppColors.TEXT_PRIMARY, text_align=ft.TextAlign.CENTER),
                    ft.Text(subtitle, size=13, color=AppColors.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.MD),
                    self.username_field,
                    self.password_field,
                    self.confirm_field,
                    self.error_text,
                    ft.Container(height=Spacing.XS),
                    self.submit_btn,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            width=400,
            padding=ft.Padding.all(Spacing.XL),
            bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(16),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=24,
                color=ft.Colors.with_opacity(0.08, "black"),
                offset=ft.Offset(0, 8),
            ),
        )

        # Footer with version
        footer = ft.Text(
            "SkillForge — Intelligent AI Assistant",
            size=11, color=AppColors.TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(expand=True),
                    form_card,
                    ft.Container(height=Spacing.LG),
                    footer,
                    ft.Container(height=Spacing.XL),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
            bgcolor=AppColors.BACKGROUND,
        )

    def _handle_submit(self, e):
        """Handle login or setup submission."""
        username = self.username_field.value or ""
        password = self.password_field.value or ""

        if not username or not password:
            self._show_error("Username and password are required.")
            return

        if self._is_setup:
            confirm = self.confirm_field.value or ""
            if password != confirm:
                self._show_error("Passwords do not match.")
                return
            if len(password) < 6:
                self._show_error("Password must be at least 6 characters.")
                return
            self.storage.set_admin_credentials(username, password)
            self.on_authenticated(username)
        else:
            if self.storage.verify_admin(username, password):
                self.on_authenticated(username)
            else:
                self._show_error("Invalid username or password.")

    def _show_error(self, msg: str):
        self.error_text.value = msg
        self.error_text.visible = True
        self.page.update()
