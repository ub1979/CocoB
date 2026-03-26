"""
Reusable Flet widgets — CollapsibleSection, StatusBadge, StyledButton, SectionHeader.

Refined design system: layered surfaces, generous spacing, subtle shadows,
accent-colored focus elements.
"""

from typing import Optional

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors, Spacing


class CollapsibleSection(ft.Container):
    """A premium collapsible section with accent indicator and shadow depth."""

    def __init__(self, title: str, content: ft.Control,
                 icon: Optional[str] = None, expanded: bool = True, **kwargs):
        self.is_expanded = expanded
        self.expand_icon = ft.Icon(
            icons.KEYBOARD_ARROW_DOWN if expanded else icons.KEYBOARD_ARROW_RIGHT,
            color=AppColors.TEXT_MUTED, size=20,
            rotate=0 if not expanded else 0,
        )

        # Left accent bar for visual hierarchy
        accent_bar = ft.Container(
            width=3, height=24,
            bgcolor=AppColors.ACCENT if expanded else AppColors.BORDER,
            border_radius=ft.BorderRadius.all(2),
        )
        self._accent_bar = accent_bar

        header_content = [
            accent_bar,
            ft.Icon(icon, color=AppColors.PRIMARY, size=20) if icon else ft.Container(),
            ft.Column([
                ft.Text(title, size=15, weight=ft.FontWeight.W_600,
                        color=AppColors.TEXT_PRIMARY),
            ], spacing=0, expand=True),
            self.expand_icon,
        ]

        self.header = ft.Container(
            content=ft.Row(header_content, spacing=12,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=16, right=20, top=14, bottom=14),
            border_radius=ft.BorderRadius.only(
                top_left=12, top_right=12,
                bottom_left=12 if not expanded else 0,
                bottom_right=12 if not expanded else 0,
            ),
            bgcolor=AppColors.SURFACE_ELEVATED,
            on_click=self._toggle_expand,
        )
        self._header_ref = self.header  # for border_radius updates

        self.content_container = ft.Container(
            content=content,
            padding=ft.Padding.only(left=20, right=20, top=16, bottom=20),
            visible=expanded,
        )

        super().__init__(
            content=ft.Column([self.header, self.content_container], spacing=0),
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=AppColors.SURFACE,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.Colors.with_opacity(0.04, "black"),
                offset=ft.Offset(0, 2),
            ),
            **kwargs
        )

    def _toggle_expand(self, e):
        self.is_expanded = not self.is_expanded
        self.content_container.visible = self.is_expanded
        self.expand_icon.name = (
            icons.KEYBOARD_ARROW_DOWN if self.is_expanded
            else icons.KEYBOARD_ARROW_RIGHT
        )
        self._accent_bar.bgcolor = (
            AppColors.ACCENT if self.is_expanded else AppColors.BORDER
        )
        # Adjust header border radius when expanded/collapsed
        self._header_ref.border_radius = ft.BorderRadius.only(
            top_left=12, top_right=12,
            bottom_left=12 if not self.is_expanded else 0,
            bottom_right=12 if not self.is_expanded else 0,
        )
        self.update()


class StatusBadge(ft.Container):
    """A compact status badge with icon and text — pill shape."""

    def __init__(self, text: str, status: str = "info"):
        colors = {
            "success": (AppColors.SUCCESS, AppColors.SUCCESS_LIGHT),
            "warning": (AppColors.WARNING, AppColors.WARNING_LIGHT),
            "error": (AppColors.ERROR, AppColors.ERROR_LIGHT),
            "info": (AppColors.INFO, AppColors.INFO_LIGHT),
        }
        color, bg = colors.get(status, colors["info"])
        status_icons = {
            "success": icons.CHECK_CIRCLE,
            "warning": icons.WARNING_AMBER,
            "error": icons.ERROR_OUTLINE,
            "info": icons.INFO_OUTLINE,
        }

        super().__init__(
            content=ft.Row([
                ft.Icon(status_icons.get(status, icons.INFO_OUTLINE),
                        color=color, size=14),
                ft.Text(text, size=11, color=color, weight=ft.FontWeight.W_500),
            ], spacing=5, tight=True),
            padding=ft.Padding.only(left=10, right=12, top=5, bottom=5),
            bgcolor=bg,
            border_radius=ft.BorderRadius.all(20),
        )


class StyledButton(ft.Button):
    """Styled button with consistent theming and modern feel."""

    def __init__(self, text: str, on_click=None, icon=None,
                 variant="primary", expand=False, **kwargs):
        colors = {
            "primary": (AppColors.PRIMARY, AppColors.TEXT_ON_PRIMARY),
            "secondary": (AppColors.SURFACE_VARIANT, AppColors.TEXT_PRIMARY),
            "accent": (AppColors.ACCENT, AppColors.TEXT_ON_PRIMARY),
            "outline": (None, AppColors.PRIMARY),
            "text": (None, AppColors.PRIMARY),
            "danger": (AppColors.ERROR, AppColors.TEXT_ON_PRIMARY),
        }
        bgcolor, color = colors.get(variant, colors["primary"])

        if icon:
            content = ft.Row([
                ft.Icon(icon, color=color, size=16),
                ft.Text(text, color=color, weight=ft.FontWeight.W_500, size=13)
            ], spacing=6, tight=True)
        else:
            content = ft.Text(text, color=color, weight=ft.FontWeight.W_500, size=13)

        side = None
        if variant == "outline":
            side = ft.BorderSide(1, AppColors.BORDER)
            bgcolor = AppColors.SURFACE

        super().__init__(
            content=content,
            on_click=on_click, bgcolor=bgcolor, color=color,
            elevation=0,
            style=ft.ButtonStyle(
                padding=ft.Padding.only(left=16, right=16, top=10, bottom=10),
                shape=ft.RoundedRectangleBorder(radius=8),
                side=side,
            ),
            expand=expand, **kwargs
        )


class SectionHeader(ft.Container):
    """A styled section header with icon — used inside CollapsibleSections
    to label sub-groups."""

    def __init__(self, title: str, icon: Optional[str] = None,
                 subtitle: Optional[str] = None):
        row_controls = []
        if icon:
            row_controls.append(
                ft.Icon(icon, color=AppColors.ACCENT, size=16))
        row_controls.append(
            ft.Text(title, size=13, weight=ft.FontWeight.W_600,
                    color=AppColors.TEXT_PRIMARY))
        if subtitle:
            row_controls.append(ft.Container(expand=True))
            row_controls.append(
                ft.Text(subtitle, size=11, color=AppColors.TEXT_MUTED))

        super().__init__(
            content=ft.Row(row_controls, spacing=8,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(bottom=8, top=4),
        )


class SettingsPanel(ft.Container):
    """A clean card-like panel for settings sections.
    Used as the content container when a category card is clicked.
    Replaces the redundant CollapsibleSection wrapper."""

    def __init__(self, title: str, icon: Optional[str] = None,
                 subtitle: Optional[str] = None,
                 content: Optional[ft.Control] = None, **kwargs):
        # Header row with icon in tinted circle
        header_controls = []
        if icon:
            header_controls.append(
                ft.Icon(icon, color=AppColors.TEXT_PRIMARY, size=22))
        col_items = [ft.Text(title, size=16, weight=ft.FontWeight.W_700,
                             color=AppColors.TEXT_PRIMARY)]
        if subtitle:
            col_items.append(ft.Text(subtitle, size=11,
                                     color=AppColors.TEXT_MUTED))
        header_controls.append(ft.Column(col_items, spacing=1, expand=True))

        header = ft.Container(
            content=ft.Row(header_controls, spacing=12,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=20, right=20, top=16, bottom=12),
            bgcolor=AppColors.SURFACE_ELEVATED,
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
        )

        body = ft.Container(
            content=content,
            padding=ft.Padding.only(left=20, right=20, top=12, bottom=20),
        )

        super().__init__(
            content=ft.Column([header, body], spacing=0),
            bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER),
            border_radius=ft.BorderRadius.all(12),
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=8,
                color=ft.Colors.with_opacity(0.04, "black"),
                offset=ft.Offset(0, 2),
            ),
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            **kwargs,
        )


class SettingRow(ft.Container):
    """A single settings row — icon + title/subtitle on left, control on right.
    Styled like iOS/Android settings items."""

    def __init__(self, title: str, icon: Optional[str] = None,
                 subtitle: Optional[str] = None,
                 control: Optional[ft.Control] = None,
                 icon_color: Optional[str] = None,
                 on_click=None):
        left = []
        if icon:
            left.append(
                ft.Icon(icon, color=AppColors.TEXT_PRIMARY, size=20))
        col_items = [ft.Text(title, size=13, weight=ft.FontWeight.W_500,
                             color=AppColors.TEXT_PRIMARY)]
        if subtitle:
            col_items.append(ft.Text(subtitle, size=11,
                                     color=AppColors.TEXT_MUTED))
        left.append(ft.Column(col_items, spacing=1, expand=True))
        if control:
            left.append(control)

        super().__init__(
            content=ft.Row(left, spacing=12,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=4, right=4, top=10, bottom=10),
            border_radius=ft.BorderRadius.all(8),
            on_click=on_click,
            ink=bool(on_click),
        )


class SubItemAccordion(ft.Container):
    """A nested expandable sub-item within a CollapsibleSection.
    Used for bot configs, provider groups, etc."""

    def __init__(self, title: str, icon_emoji: str,
                 status_text: Optional[str] = None,
                 status_color: Optional[str] = None,
                 description: Optional[str] = None,
                 content: Optional[ft.Control] = None,
                 expanded: bool = False):
        self._is_expanded = expanded
        self._expand_icon = ft.Icon(
            icons.KEYBOARD_ARROW_DOWN if expanded else icons.KEYBOARD_ARROW_RIGHT,
            color=AppColors.TEXT_MUTED, size=18,
        )

        title_col_controls = [
            ft.Text(title, size=13, weight=ft.FontWeight.W_500,
                    color=AppColors.TEXT_PRIMARY),
        ]
        if description:
            title_col_controls.append(
                ft.Text(description, size=10, color=AppColors.TEXT_MUTED))

        right_controls = []
        if status_text:
            sc = status_color or AppColors.TEXT_MUTED
            right_controls.append(ft.Container(
                content=ft.Text(status_text, size=10, color="white",
                                weight=ft.FontWeight.W_600),
                bgcolor=sc,
                padding=ft.Padding.only(left=8, right=8, top=3, bottom=3),
                border_radius=ft.BorderRadius.all(10),
            ))
        right_controls.append(self._expand_icon)

        header = ft.Container(
            content=ft.Row([
                ft.Text(icon_emoji, size=17),
                ft.Column(title_col_controls, spacing=0, expand=True),
                *right_controls,
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=14, right=14, top=10, bottom=10),
            bgcolor=AppColors.SURFACE_VARIANT,
            border_radius=ft.BorderRadius.all(10),
            on_click=self._toggle,
        )
        self._header_ref = header

        self._content_container = ft.Container(
            content=content,
            visible=expanded,
            padding=ft.Padding.only(left=18, right=4, top=12, bottom=4),
        )

        super().__init__(
            content=ft.Column([header, self._content_container], spacing=0),
            margin=ft.Margin.only(bottom=6),
        )

    def _toggle(self, e):
        self._is_expanded = not self._is_expanded
        self._content_container.visible = self._is_expanded
        self._expand_icon.name = (
            icons.KEYBOARD_ARROW_DOWN if self._is_expanded
            else icons.KEYBOARD_ARROW_RIGHT
        )
        self.update()
