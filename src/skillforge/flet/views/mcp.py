"""
MCPPanel — MCP server management view.
"""

import json
import threading

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors
from skillforge.flet.components.widgets import StyledButton


class MCPPanel:
    """MCP server management panel."""

    def __init__(self, page: ft.Page, app_state, mcp_manager, router):
        self.page = page
        self.app_state = app_state
        self.mcp_manager = mcp_manager
        self.router = router
        self._executor = None

    def set_executor(self, executor):
        self._executor = executor

    def build(self) -> ft.Column:
        header = ft.Container(
            content=ft.Row([
                ft.Text("MCP Servers", size=24, weight=ft.FontWeight.W_700, color=AppColors.PRIMARY),
                ft.Container(expand=True),
                StyledButton("Import", icon=icons.DOWNLOAD, on_click=self._import_claude_config, variant="outline"),
                ft.Container(width=8),
                StyledButton("Refresh", icon=icons.REFRESH, on_click=self._refresh_mcp_servers, variant="outline"),
                ft.Container(width=8),
                StyledButton("+ Add", icon=icons.ADD, on_click=self._add_mcp_server_dialog),
            ]),
            padding=ft.Padding.only(bottom=16),
            border=ft.Border.only(bottom=ft.BorderSide(1, AppColors.BORDER))
        )

        self.mcp_servers_list = ft.ListView(expand=True, spacing=8, padding=ft.Padding.all(8))
        self._populate_mcp_servers()

        return ft.Column([
            header,
            ft.Text("MCP (Model Context Protocol) servers provide tools the AI can use.",
                    size=12, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=8),
            self.mcp_servers_list,
        ], expand=True, spacing=0)

    def _populate_mcp_servers(self):
        self.mcp_servers_list.controls.clear()

        MCPManager = None
        try:
            from skillforge.core.mcp_client import MCPManager as _MCPManager
            MCPManager = _MCPManager
        except ImportError:
            pass

        if not self.mcp_manager or MCPManager is None:
            self.mcp_servers_list.controls.append(ft.Text("MCP manager not available", color=AppColors.TEXT_SECONDARY))
            return

        server_states = self.mcp_manager.get_server_states()
        if not server_states:
            self.mcp_servers_list.controls.append(ft.Text("No MCP servers configured", color=AppColors.TEXT_SECONDARY))
            self.mcp_servers_list.controls.append(ft.Container(height=8))
            self.mcp_servers_list.controls.append(
                ft.Text("Click 'Import' to import from Claude Desktop,\nor '+ Add' to configure a new server.",
                        size=12, color=AppColors.TEXT_MUTED))
            return

        for name, state in server_states.items():
            self.mcp_servers_list.controls.append(self._create_mcp_server_card(name, state))

        self.mcp_servers_list.controls.append(ft.Container(height=16))
        self.mcp_servers_list.controls.append(
            ft.Text("Available Tools", size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY))
        self.mcp_servers_list.controls.append(ft.Container(height=8))

        all_tools = self.mcp_manager.get_all_tools()
        if all_tools:
            for server_name, tools in all_tools.items():
                if tools:
                    self.mcp_servers_list.controls.append(
                        ft.Text(f"{server_name.upper()}", size=12, weight=ft.FontWeight.W_600, color=AppColors.PRIMARY))
                    for tool in tools:
                        self.mcp_servers_list.controls.append(ft.Container(
                            content=ft.Column([
                                ft.Text(tool.get('name', 'Unknown'), size=13, weight=ft.FontWeight.W_500, color=AppColors.TEXT_PRIMARY),
                                ft.Text(tool.get('description', 'No description')[:100], size=11, color=AppColors.TEXT_SECONDARY,
                                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2),
                            padding=ft.Padding.all(8), bgcolor=AppColors.SURFACE_VARIANT, border_radius=ft.BorderRadius.all(6),
                        ))
                    self.mcp_servers_list.controls.append(ft.Container(height=8))
        else:
            self.mcp_servers_list.controls.append(
                ft.Text("No tools available. Connect to a server to see its tools.", color=AppColors.TEXT_MUTED, size=12))

    def _create_mcp_server_card(self, name, state):
        status = state.status if hasattr(state, 'status') else None
        status_value = status.value if status else "disconnected"

        if status_value == "connected":
            status_color, status_icon, status_text, is_connected = AppColors.SUCCESS, icons.CHECK_CIRCLE, "Connected", True
        elif status_value == "connecting":
            status_color, status_icon, status_text, is_connected = AppColors.WARNING, icons.SYNC, "Connecting...", False
        elif status_value == "error":
            status_color, status_icon, status_text, is_connected = AppColors.ERROR, icons.ERROR, "Error", False
        else:
            status_color, status_icon, status_text, is_connected = AppColors.TEXT_MUTED, icons.CIRCLE_OUTLINED, "Disconnected", False

        config_obj = state.config if hasattr(state, 'config') else None
        server_type = config_obj.type.value if config_obj and hasattr(config_obj, 'type') else "stdio"
        tools_count = len(state.tools) if hasattr(state, 'tools') else 0

        connect_btn = ft.IconButton(
            icon=icons.POWER_SETTINGS_NEW if not is_connected else icons.STOP_CIRCLE,
            icon_color=AppColors.SUCCESS if not is_connected else AppColors.ERROR,
            icon_size=20, tooltip="Connect" if not is_connected else "Disconnect",
            on_click=lambda e, n=name, c=is_connected: self._toggle_mcp_connection(n, c),
        )
        delete_btn = ft.IconButton(
            icon=icons.DELETE, icon_color=AppColors.ERROR, icon_size=18,
            tooltip="Remove server", on_click=lambda e, n=name: self._delete_mcp_server(n),
        )

        card_content = ft.Column([
            ft.Row([
                ft.Icon(icons.DEVICE_HUB, color=AppColors.PRIMARY, size=24),
                ft.Container(
                    content=ft.Text(name, size=14, weight=ft.FontWeight.W_600, color=AppColors.TEXT_PRIMARY,
                                   overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, no_wrap=True),
                    expand=True, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                ),
                ft.Container(
                    content=ft.Row([ft.Icon(status_icon, color=status_color, size=14),
                                    ft.Text(status_text, size=11, color=status_color, no_wrap=True)], spacing=4, tight=True),
                    bgcolor=ft.Colors.with_opacity(0.13, status_color), padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(12),
                ),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                content=ft.Row([
                    ft.Text(f"Type: {server_type.upper()}", size=11, color=AppColors.TEXT_SECONDARY, no_wrap=True),
                    ft.Text("•", size=11, color=AppColors.TEXT_MUTED),
                    ft.Text(f"{tools_count} tools" if is_connected else "Not connected", size=11, color=AppColors.TEXT_SECONDARY, no_wrap=True),
                ], spacing=6),
                padding=ft.Padding.only(top=4, left=32),
            ),
            ft.Container(
                content=ft.Row([ft.Container(expand=True), connect_btn, delete_btn], spacing=0),
                padding=ft.Padding.only(top=4),
            ),
            ft.Container(
                content=ft.Text(state.error_message or "", size=11, color=AppColors.ERROR, overflow=ft.TextOverflow.ELLIPSIS, max_lines=2),
                visible=status_value == "error" and bool(state.error_message),
                padding=ft.Padding.only(top=4, left=32),
            ),
        ], spacing=0)

        return ft.Container(
            content=card_content, padding=ft.Padding.all(12), bgcolor=AppColors.SURFACE,
            border=ft.Border.all(1, AppColors.BORDER), border_radius=ft.BorderRadius.all(8),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

    def _toggle_mcp_connection(self, server_name, is_connected):
        if not self.mcp_manager:
            return

        def do_connect():
            try:
                if is_connected:
                    success, msg = self.mcp_manager.disconnect_server_sync(server_name)
                else:
                    success, msg = self.mcp_manager.connect_server_sync(server_name)
                if success and self.router:
                    connected_count = len([s for s in self.mcp_manager.servers.values() if s.connected])
                    self.router.set_mcp_manager(self.mcp_manager if connected_count > 0 else None)
                if success:
                    self._show_snackbar(msg)
                else:
                    self._show_snackbar(msg, error=True)
                self._populate_mcp_servers()
                try:
                    self.page.update()
                except Exception:
                    pass
            except Exception as ex:
                self._show_snackbar(f"Error: {str(ex)}", error=True)

        if self._executor:
            self._executor.submit(do_connect)
        else:
            threading.Thread(target=do_connect, daemon=True).start()
        self._show_snackbar("Connecting..." if not is_connected else "Disconnecting...")

    def _refresh_mcp_servers(self, e=None):
        if self.mcp_manager:
            self.mcp_manager.load_config()
            self._populate_mcp_servers()
            self._show_snackbar("MCP servers refreshed")
        self.page.update()

    def _import_claude_config(self, e):
        if not self.mcp_manager:
            self._show_snackbar("MCP manager not available", error=True)
            return
        imported, msg = self.mcp_manager.import_claude_desktop_config()
        self._show_snackbar(msg)
        self._populate_mcp_servers()
        self.page.update()

    def _add_mcp_server_dialog(self, e):
        name_field = ft.TextField(label="Server Name", hint_text="my-server",
                                  border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        type_dropdown = ft.Dropdown(label="Type", options=[
            ft.dropdown.Option("stdio", "STDIO (subprocess)"),
            ft.dropdown.Option("sse", "SSE (Server-Sent Events)"),
            ft.dropdown.Option("http", "HTTP (Streamable)"),
        ], value="stdio", border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        command_field = ft.TextField(label="Command", hint_text="npx -y @modelcontextprotocol/server-filesystem",
                                    border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        args_field = ft.TextField(label="Arguments (JSON array)", hint_text='["/path/to/dir"]',
                                  border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE)
        url_field = ft.TextField(label="URL (for SSE/HTTP)", hint_text="http://localhost:8080/mcp",
                                 border_color=AppColors.BORDER, color=AppColors.TEXT_PRIMARY, bgcolor=AppColors.SURFACE, visible=False)

        def on_type_change(e):
            is_remote = type_dropdown.value in ("sse", "http")
            command_field.visible = not is_remote
            args_field.visible = not is_remote
            url_field.visible = is_remote
            self.page.update()

        type_dropdown.on_change = on_type_change

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def add_server(e):
            name = name_field.value.strip() if name_field.value else ""
            if not name:
                self._show_snackbar("Please enter a server name", error=True)
                return
            server_type = type_dropdown.value or "stdio"
            config_dict = {"type": server_type}
            if server_type == "stdio":
                if not command_field.value:
                    self._show_snackbar("Please enter a command", error=True)
                    return
                config_dict["command"] = command_field.value.strip()
                if args_field.value:
                    try:
                        config_dict["args"] = json.loads(args_field.value)
                    except json.JSONDecodeError:
                        self._show_snackbar("Invalid JSON for arguments", error=True)
                        return
            else:
                if not url_field.value:
                    self._show_snackbar("Please enter a URL", error=True)
                    return
                config_dict["url"] = url_field.value.strip()
            try:
                from skillforge.ui.settings.mcp_models import MCPServerConfig
                server_config = MCPServerConfig.from_dict(name, config_dict)
                if self.mcp_manager.add_server(server_config):
                    self._show_snackbar(f"Added server: {name}")
                    self._populate_mcp_servers()
                    dialog.open = False
                else:
                    self._show_snackbar("Failed to add server", error=True)
            except Exception as ex:
                self._show_snackbar(f"Error: {str(ex)}", error=True)
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Add MCP Server", color=AppColors.TEXT_PRIMARY),
            content=ft.Column([name_field, type_dropdown, command_field, args_field, url_field],
                             tight=True, spacing=16, width=500),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), StyledButton("Add Server", on_click=add_server)],
            actions_alignment=ft.MainAxisAlignment.END, bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _delete_mcp_server(self, server_name):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            if self.mcp_manager.remove_server(server_name):
                self._show_snackbar(f"Removed server: {server_name}")
                self._populate_mcp_servers()
            else:
                self._show_snackbar("Failed to remove server", error=True)
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text(f"Remove {server_name}?", color=AppColors.TEXT_PRIMARY),
            content=ft.Text("This will remove the server configuration.", color=AppColors.TEXT_SECONDARY),
            actions=[ft.TextButton("Cancel", on_click=close_dialog),
                     ft.TextButton("Remove", style=ft.ButtonStyle(color=AppColors.ERROR), on_click=confirm_delete)],
            actions_alignment=ft.MainAxisAlignment.END, bgcolor=AppColors.SURFACE,
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _show_snackbar(self, message, error=False):
        snackbar = ft.SnackBar(
            content=ft.Text(message, color=AppColors.TEXT_ON_PRIMARY),
            bgcolor=AppColors.ERROR if error else AppColors.SUCCESS, open=True,
        )
        self.page.overlay.append(snackbar)
        self.page.update()
