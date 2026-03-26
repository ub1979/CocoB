"""
Admin dashboard — user management, permission requests, identity linking.

Only accessible to authenticated admin users via the Flet UI.
"""

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors, Spacing
from skillforge.flet.components.widgets import StyledButton, StatusBadge
from skillforge.core.user_permissions import PermissionManager, ALL_PERMISSIONS, DEFAULT_ROLES
from skillforge.core.permission_requests import PermissionRequestManager
from skillforge.core.identity_resolver import IdentityResolver


class AdminView:
    """Admin dashboard with user management, permission requests, and identity linking."""

    def __init__(self, page: ft.Page, permission_manager: PermissionManager,
                 request_manager: PermissionRequestManager,
                 identity_resolver: IdentityResolver):
        self.page = page
        self.perm_mgr = permission_manager
        self.req_mgr = request_manager
        self.id_resolver = identity_resolver

    def build(self) -> ft.Column:
        """Build the admin dashboard."""
        self._users_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=Spacing.SM)
        self._requests_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=Spacing.SM)
        self._identity_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=Spacing.SM)

        # Pending requests badge for tab label
        self._pending_badge = ft.Text("", size=11, color=AppColors.ERROR, weight=ft.FontWeight.BOLD)

        users_content = ft.Container(content=self._build_users_tab(), padding=ft.Padding.only(top=8), expand=True)
        requests_content = ft.Container(content=self._build_requests_tab(), padding=ft.Padding.only(top=8), expand=True)
        identity_content = ft.Container(content=self._build_identity_tab(), padding=ft.Padding.only(top=8), expand=True)

        tab_bar = ft.TabBar(
            tabs=[
                ft.Tab(label="Users & Roles", icon=icons.PEOPLE),
                ft.Tab(label="Permission Requests", icon=icons.APPROVAL),
                ft.Tab(label="Identity Linking", icon=icons.LINK),
            ],
            indicator_color=AppColors.SECONDARY,
            label_color=AppColors.TEXT_PRIMARY,
            unselected_label_color=AppColors.TEXT_SECONDARY,
        )

        tab_bar_view = ft.TabBarView(
            controls=[users_content, requests_content, identity_content],
            expand=True,
        )

        tabs = ft.Tabs(
            length=3,
            selected_index=0,
            content=ft.Column([tab_bar, tab_bar_view], expand=True, spacing=0),
            expand=True,
        )

        # Header with icon, title, and summary stats
        self._stats_row = ft.Row([], spacing=Spacing.SM)

        header = ft.Container(
            content=ft.Row([
                ft.Icon(icons.ADMIN_PANEL_SETTINGS, color=AppColors.ACCENT,
                        size=26),
                ft.Column([
                    ft.Text("Admin Panel", size=22,
                            weight=ft.FontWeight.W_700,
                            color=AppColors.TEXT_PRIMARY),
                    ft.Text("Manage users, permissions, and identity linking",
                            size=12, color=AppColors.TEXT_MUTED),
                ], spacing=1, expand=True),
                self._stats_row,
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=4, right=4, top=8, bottom=16),
        )

        return ft.Column([
            header,
            tabs,
        ], expand=True, spacing=0)

    # -----------------------------------------------------------------
    # Header stats
    # -----------------------------------------------------------------

    def _update_stats(self):
        """Update the header summary stats."""
        user_count = len(self.perm_mgr.get_all_users())
        pending_count = len(self.req_mgr.get_pending())
        link_count = sum(len(a) for a in self.id_resolver.get_all_users().values())

        self._stats_row.controls = [
            StatusBadge(f"{user_count} users", "info"),
            StatusBadge(
                f"{pending_count} pending",
                "warning" if pending_count > 0 else "success",
            ),
            StatusBadge(f"{link_count} links", "info"),
        ]

    # -----------------------------------------------------------------
    # Users & Roles tab
    # -----------------------------------------------------------------

    def _build_users_tab(self) -> ft.Container:
        self._new_user_id = ft.TextField(
            label="User ID", width=200, dense=True,
            prefix_icon=icons.PERSON_ADD,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        self._new_user_role = ft.Dropdown(
            label="Role", width=160, dense=True,
            border_color=AppColors.BORDER,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            options=[ft.dropdown.Option(r) for r in DEFAULT_ROLES],
        )
        add_btn = StyledButton("Add User", icon=icons.PERSON_ADD,
                               on_click=self._add_user)

        return ft.Container(
            content=ft.Column([
                ft.Text("Manage user roles and permissions. Users without a role get full access by default.",
                         size=13, color=AppColors.TEXT_SECONDARY),
                ft.Container(
                    content=ft.Row([self._new_user_id, self._new_user_role, add_btn],
                                   spacing=Spacing.SM,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.only(top=Spacing.XS, bottom=Spacing.XS),
                ),
                ft.Divider(color=AppColors.BORDER),
                self._users_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_users(self):
        self._users_list.controls.clear()
        users = self.perm_mgr.get_all_users()
        if not users:
            self._users_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(icons.GROUP_OFF, size=40, color=AppColors.TEXT_MUTED),
                        ft.Text("No users configured",
                                size=14, weight=ft.FontWeight.W_500, color=AppColors.TEXT_SECONDARY),
                        ft.Text("All users have full access. Add users to enable role-based permissions.",
                                size=12, color=AppColors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    padding=Spacing.XL, width=400,
                ))
            return

        for uid, info in users.items():
            role = info.get("role", "unknown")
            perms = self.perm_mgr.get_user_permissions(uid)
            perm_str = ", ".join(sorted(perms)) if "*" not in perms else "All permissions (admin)"
            aliases = self.id_resolver.get_aliases(uid)
            alias_str = " | ".join(aliases) if aliases else "No linked platforms"

            # Role color indicator
            role_colors = {
                "admin": AppColors.SECONDARY,
                "power_user": AppColors.INFO,
                "user": AppColors.SUCCESS,
                "restricted": AppColors.TEXT_MUTED,
            }
            role_color = role_colors.get(role, AppColors.TEXT_SECONDARY)

            role_dropdown = ft.Dropdown(
                value=role, width=140, dense=True,
                border_color=AppColors.BORDER,
                text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
                options=[ft.dropdown.Option(r) for r in DEFAULT_ROLES],
                on_select=lambda e, u=uid: self._change_role(u, e.control.value),
            )

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(icons.PERSON, color="white", size=16),
                            width=28, height=28,
                            bgcolor=role_color,
                            border_radius=ft.BorderRadius.all(14),
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(uid, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_PRIMARY, size=14,
                                expand=True),
                        role_dropdown,
                        ft.IconButton(icons.DELETE_OUTLINE, icon_color=AppColors.ERROR, icon_size=18,
                                      tooltip="Remove user",
                                      on_click=lambda e, u=uid: self._remove_user(u)),
                    ], alignment=ft.MainAxisAlignment.START, spacing=Spacing.SM,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([
                        ft.Icon(icons.DEVICES, size=12, color=AppColors.TEXT_MUTED),
                        ft.Text(alias_str, size=12, color=AppColors.TEXT_SECONDARY),
                    ], spacing=4),
                    ft.Row([
                        ft.Icon(icons.SECURITY, size=12, color=AppColors.TEXT_MUTED),
                        ft.Text(perm_str, size=11, color=AppColors.TEXT_SECONDARY, expand=True),
                    ], spacing=4),
                ], spacing=6),
                padding=ft.Padding.all(Spacing.SM + 4),
                border=ft.Border.all(1, AppColors.BORDER),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=AppColors.SURFACE,
            )
            self._users_list.controls.append(card)

    def _add_user(self, e):
        uid = (self._new_user_id.value or "").strip()
        role = self._new_user_role.value or "user"
        if not uid:
            return
        self.perm_mgr.set_user_role(uid, role, assigned_by="admin_panel")
        self._new_user_id.value = ""
        self.refresh()

    def _change_role(self, user_id: str, new_role: str):
        self.perm_mgr.set_user_role(user_id, new_role, assigned_by="admin_panel")
        self.refresh()

    def _remove_user(self, user_id: str):
        self.perm_mgr.remove_user(user_id)
        self.refresh()

    # -----------------------------------------------------------------
    # Permission Requests tab
    # -----------------------------------------------------------------

    def _build_requests_tab(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text("Review and approve or deny permission requests from users across all channels.",
                         size=13, color=AppColors.TEXT_SECONDARY),
                ft.Divider(color=AppColors.BORDER),
                self._requests_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_requests(self):
        self._requests_list.controls.clear()
        pending = self.req_mgr.get_pending()
        if not pending:
            self._requests_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(icons.VERIFIED, size=40, color=AppColors.SUCCESS),
                        ft.Text("No pending requests",
                                size=14, weight=ft.FontWeight.W_500, color=AppColors.TEXT_SECONDARY),
                        ft.Text("All permission requests have been handled.",
                                size=12, color=AppColors.TEXT_MUTED),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    padding=Spacing.XL, width=400,
                ))
            return

        for req in pending:
            reason_text = req.get("reason", "")

            card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icons.HELP_OUTLINE, color=AppColors.WARNING, size=20),
                        width=36, height=36,
                        bgcolor=AppColors.WARNING_LIGHT,
                        border_radius=ft.BorderRadius.all(18),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(req['user_id'], weight=ft.FontWeight.BOLD,
                                    color=AppColors.TEXT_PRIMARY, size=14),
                            ft.Text("requests", size=13, color=AppColors.TEXT_SECONDARY),
                            ft.Container(
                                content=ft.Text(req['permission'], size=12,
                                                color=AppColors.INFO,
                                                weight=ft.FontWeight.W_500),
                                bgcolor=AppColors.INFO_LIGHT,
                                padding=ft.Padding.only(left=8, right=8, top=2, bottom=2),
                                border_radius=ft.BorderRadius.all(4),
                            ),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Row([
                            ft.Text(req['timestamp'], size=11, color=AppColors.TEXT_MUTED),
                            ft.Text(f"— {reason_text}", size=11, color=AppColors.TEXT_SECONDARY,
                                    italic=True) if reason_text else ft.Container(),
                        ], spacing=4),
                    ], spacing=2, expand=True),
                    ft.IconButton(icons.CHECK_CIRCLE, icon_color=AppColors.SUCCESS, icon_size=28,
                                  tooltip="Approve",
                                  on_click=lambda e, r=req: self._approve_request(r)),
                    ft.IconButton(icons.CANCEL, icon_color=AppColors.ERROR, icon_size=28,
                                  tooltip="Deny",
                                  on_click=lambda e, r=req: self._deny_request(r)),
                ], alignment=ft.MainAxisAlignment.START, spacing=Spacing.SM,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.all(Spacing.SM + 4),
                border=ft.Border.all(1, AppColors.BORDER),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=AppColors.SURFACE,
            )
            self._requests_list.controls.append(card)

    def _approve_request(self, req):
        self.req_mgr.approve(req["id"], "admin")
        self.perm_mgr.grant_permission(req["user_id"], req["permission"])
        self.refresh()

    def _deny_request(self, req):
        self.req_mgr.deny(req["id"], "admin")
        self.refresh()

    # -----------------------------------------------------------------
    # Identity Linking tab
    # -----------------------------------------------------------------

    def _build_identity_tab(self) -> ft.Container:
        self._canonical_id_field = ft.TextField(
            label="Canonical User ID (e.g. admin)", width=200, dense=True,
            prefix_icon=icons.PERSON,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        self._platform_id_field = ft.TextField(
            label="Platform ID (e.g. telegram:12345)", width=260, dense=True,
            prefix_icon=icons.DEVICES,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        link_btn = StyledButton("Link", icon=icons.LINK, on_click=self._link_identity)

        return ft.Container(
            content=ft.Column([
                ft.Text("Link platform accounts to canonical user IDs so "
                         "permissions follow the person across channels.",
                         size=13, color=AppColors.TEXT_SECONDARY),
                ft.Container(
                    content=ft.Row([self._canonical_id_field, self._platform_id_field, link_btn],
                                   spacing=Spacing.SM,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.only(top=Spacing.XS, bottom=Spacing.XS),
                ),
                ft.Divider(color=AppColors.BORDER),
                self._identity_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_identity(self):
        self._identity_list.controls.clear()
        users = self.id_resolver.get_all_users()
        if not users:
            self._identity_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(icons.LINK_OFF, size=40, color=AppColors.TEXT_MUTED),
                        ft.Text("No identity links configured",
                                size=14, weight=ft.FontWeight.W_500, color=AppColors.TEXT_SECONDARY),
                        ft.Text("Link platform accounts above to unify user permissions.",
                                size=12, color=AppColors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    padding=Spacing.XL, width=400,
                ))
            return

        for canonical, aliases in users.items():
            # Platform icon mapping
            def _platform_icon(alias):
                a_lower = alias.lower()
                if "telegram" in a_lower:
                    return icons.TELEGRAM
                elif "whatsapp" in a_lower:
                    return icons.WHATSAPP
                elif "slack" in a_lower:
                    return icons.TAG
                elif "discord" in a_lower:
                    return icons.DISCORD
                return icons.DEVICE_UNKNOWN

            alias_chips = [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(_platform_icon(a), size=14, color=AppColors.TEXT_PRIMARY),
                        ft.Text(a, size=12, color=AppColors.TEXT_PRIMARY),
                        ft.IconButton(icons.CLOSE, icon_size=14,
                                      icon_color=AppColors.TEXT_MUTED,
                                      tooltip="Unlink",
                                      on_click=lambda e, alias=a: self._unlink_identity(alias)),
                    ], spacing=4, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=AppColors.SURFACE_VARIANT,
                    padding=ft.Padding.only(left=8, right=2, top=2, bottom=2),
                    border_radius=ft.BorderRadius.all(16),
                    border=ft.Border.all(1, AppColors.BORDER),
                )
                for a in aliases
            ]

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(icons.PERSON, color="white", size=14),
                            width=24, height=24,
                            bgcolor=AppColors.PRIMARY,
                            border_radius=ft.BorderRadius.all(12),
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(canonical, weight=ft.FontWeight.BOLD,
                                color=AppColors.TEXT_PRIMARY, size=14),
                        ft.Text(f"({len(aliases)} linked)", size=11, color=AppColors.TEXT_MUTED),
                    ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row(alias_chips, wrap=True, spacing=6, run_spacing=6),
                ], spacing=Spacing.SM),
                padding=ft.Padding.all(Spacing.SM + 4),
                border=ft.Border.all(1, AppColors.BORDER),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=AppColors.SURFACE,
            )
            self._identity_list.controls.append(card)

    def _link_identity(self, e):
        canonical = (self._canonical_id_field.value or "").strip()
        platform = (self._platform_id_field.value or "").strip()
        if not canonical or not platform:
            return
        self.id_resolver.link(canonical, platform)
        self._canonical_id_field.value = ""
        self._platform_id_field.value = ""
        self.refresh()

    def _unlink_identity(self, platform_id: str):
        self.id_resolver.unlink(platform_id)
        self.refresh()

    # -----------------------------------------------------------------
    # Refresh all tabs
    # -----------------------------------------------------------------

    def refresh(self):
        """Refresh all admin panel data."""
        self._refresh_users()
        self._refresh_requests()
        self._refresh_identity()
        self._update_stats()
        self.page.update()
