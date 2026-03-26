# =============================================================================
'''
    File Name : mcp_tab.py

    Description : MCP Server Management Tab - Allows users to configure,
                  connect, and manage Model Context Protocol servers. Supports
                  STDIO, Docker, SSE, and HTTP transport types.

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Imports
# =============================================================================

import gradio as gr
import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from .mcp_models import (
    MCPServerType,
    MCPConnectionStatus,
    MCPServerConfig,
    MCPServerState,
    validate_config,
)
from skillforge.core.mcp_client import MCPManager

if TYPE_CHECKING:
    from .state import AppState


# =============================================================================
'''
    create_mcp_tab : Main UI creation function for MCP management tab
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function create_mcp_tab -> AppState to None
# =========================================================================
# =============================================================================

def create_mcp_tab(app_state: "AppState"):
    """
    Create the MCP Server Management tab.

    Args:
        app_state: Shared application state

    Returns:
        None (creates Gradio components in current context)
    """
    # ==================================
    # Initialize MCP manager
    # ==================================
    from skillforge import PROJECT_ROOT
    mcp_manager = MCPManager(config_file=PROJECT_ROOT / "config" / "mcp_config.json")
    mcp_manager.load_config()

    # ==================================
    # Store manager in app_state
    # ==================================
    app_state.mcp_manager = mcp_manager

    # ==================================
    # Wire MCP manager to router for tool integration
    # ==================================
    if hasattr(app_state, 'router') and app_state.router:
        app_state.router.set_mcp_manager(mcp_manager)
        print("[MCP] Wired MCP manager to message router")

    with gr.Tab("MCP Tools"):
        gr.Markdown("## MCP Server Management")
        gr.Markdown("Configure MCP servers that provide tools to your AI assistant.")

        with gr.Row():
            # ==================================
            # Left Column: Server List
            # ==================================
            with gr.Column(scale=1):
                gr.Markdown("### Configured Servers")

                # Server list with status
                server_list = gr.Radio(
                    choices=_get_server_choices(mcp_manager),
                    label="Select a server to view/configure",
                    value=None,
                )

                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", size="sm", scale=1)
                    connect_all_btn = gr.Button("Connect All", size="sm", scale=1)
                    disconnect_all_btn = gr.Button("Disconnect All", size="sm", scale=1)

                gr.Markdown("---")
                gr.Markdown("### Add New Server")

                # Server type selector
                server_type = gr.Dropdown(
                    choices=[
                        ("STDIO (local)", "stdio"),
                        ("Docker", "docker"),
                        ("SSE (remote)", "sse"),
                        ("HTTP (remote)", "http"),
                    ],
                    value="stdio",
                    label="Server Type",
                    info="Transport type for MCP communication"
                )

                # Server name
                server_name = gr.Textbox(
                    label="Server Name",
                    placeholder="my-mcp-server",
                    info="Unique identifier for this server"
                )

                # Description
                server_description = gr.Textbox(
                    label="Description (optional)",
                    placeholder="What this server provides..."
                )

                # STDIO/Docker fields
                with gr.Group() as stdio_fields:
                    command_input = gr.Textbox(
                        label="Command",
                        placeholder="npx",
                        info="Executable to run (e.g., npx, python, docker)"
                    )
                    args_input = gr.Textbox(
                        label="Arguments",
                        placeholder="-y @playwright/mcp-server",
                        info="Space-separated arguments"
                    )
                    env_input = gr.Textbox(
                        label="Environment Variables (optional)",
                        placeholder="KEY=value KEY2=value2",
                        info="Space-separated KEY=value pairs"
                    )

                # SSE/HTTP fields
                with gr.Group(visible=False) as http_fields:
                    url_input = gr.Textbox(
                        label="URL",
                        placeholder="https://api.example.com/mcp",
                        info="MCP server endpoint URL"
                    )
                    headers_input = gr.Textbox(
                        label="Headers (optional)",
                        placeholder="Authorization: Bearer xxx",
                        info="HTTP headers (one per line)"
                    )

                with gr.Row():
                    add_server_btn = gr.Button("➕ Add Server", variant="primary", scale=2)
                    import_claude_btn = gr.Button("📥 Import Claude Desktop", size="sm", scale=2)

                add_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    visible=False
                )

            # ==================================
            # Right Column: Server Details
            # ==================================
            with gr.Column(scale=2):
                gr.Markdown("### Server Details")

                # Server info display
                detail_name = gr.Textbox(label="Name", interactive=False)
                detail_type = gr.Textbox(label="Type", interactive=False)
                detail_status = gr.Textbox(label="Status", interactive=False)
                detail_config = gr.Textbox(label="Configuration", interactive=False, lines=3)

                # Action buttons
                with gr.Row():
                    connect_btn = gr.Button("🔌 Connect", variant="primary", scale=1)
                    disconnect_btn = gr.Button("Disconnect", scale=1)
                    delete_btn = gr.Button("🗑️ Delete", variant="stop", scale=1)

                action_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    visible=False
                )

                gr.Markdown("---")
                gr.Markdown("### Available Tools")

                # Tools display as accordions
                tools_container = gr.Markdown(
                    value="_Select a connected server to view its tools_"
                )

        # ==================================
        # Hidden state
        # ==================================
        current_server = gr.State(value=None)

        # =============================================================================
        # Event Handlers
        # =============================================================================

        # =============================================================================
        # =========================================================================
        # Function on_type_change -> str to tuple
        # =========================================================================
        # =============================================================================

        def on_type_change(server_type: str):
            """Toggle form fields based on server type"""
            is_stdio_docker = server_type in ("stdio", "docker")
            return (
                gr.update(visible=is_stdio_docker),  # stdio_fields
                gr.update(visible=not is_stdio_docker),  # http_fields
            )

        # =============================================================================
        # =========================================================================
        # Function on_refresh -> None to gr.update
        # =========================================================================
        # =============================================================================

        def on_refresh():
            """Refresh server list"""
            mcp_manager.load_config()
            choices = _get_server_choices(mcp_manager)
            return gr.update(choices=choices, value=None)

        # =============================================================================
        # =========================================================================
        # Function on_server_select -> str to tuple
        # =========================================================================
        # =============================================================================

        def on_server_select(choice: str):
            """Load selected server details"""
            if not choice:
                return (
                    "",  # detail_name
                    "",  # detail_type
                    "",  # detail_status
                    "",  # detail_config
                    "_Select a connected server to view its tools_",  # tools_container
                    None,  # current_server
                    gr.update(visible=False),  # action_status
                )

            # ==================================
            # Extract server name from choice
            server_name = _extract_server_name(choice)
            states = mcp_manager.get_server_states()

            if server_name not in states:
                return (
                    server_name,
                    "",
                    "Not found",
                    "",
                    "_Server not found_",
                    None,
                    gr.update(visible=False),
                )

            state = states[server_name]
            config = state.config

            # ==================================
            # Build config display
            config_lines = []
            if config.command:
                config_lines.append(f"Command: {config.command}")
            if config.args:
                config_lines.append(f"Args: {' '.join(config.args)}")
            if config.url:
                config_lines.append(f"URL: {config.url}")
            if config.env:
                config_lines.append(f"Env: {len(config.env)} variables")
            config_display = "\n".join(config_lines) if config_lines else "No configuration"

            # ==================================
            # Build tools display
            tools_md = _format_tools_display(state.tools)

            return (
                config.name,
                config.type.value.upper(),
                f"{state.get_status_emoji()} {state.get_status_display()}",
                config_display,
                tools_md,
                server_name,
                gr.update(visible=False),
            )

        # =============================================================================
        # =========================================================================
        # Function on_connect -> str to tuple
        # =========================================================================
        # =============================================================================

        def on_connect(server_name: str):
            """Connect to selected server"""
            if not server_name:
                return (
                    gr.update(value="No server selected", visible=True),
                    gr.update(),  # server_list
                    gr.update(),  # detail_status
                    gr.update(),  # tools_container
                )

            # Use sync wrapper that runs in dedicated MCP event loop
            success, msg = mcp_manager.connect_server_sync(server_name)

            # ==================================
            # Refresh router's MCP awareness
            if hasattr(app_state, 'router') and app_state.router:
                app_state.router.set_mcp_manager(mcp_manager)

            # ==================================
            # Update displays
            choices = _get_server_choices(mcp_manager)
            states = mcp_manager.get_server_states()

            status_display = ""
            tools_md = "_Not connected_"
            if server_name in states:
                state = states[server_name]
                status_display = f"{state.get_status_emoji()} {state.get_status_display()}"
                tools_md = _format_tools_display(state.tools)

            # Log tool availability
            if success and server_name in states:
                tool_count = len(states[server_name].tools)
                print(f"[MCP] {server_name} connected with {tool_count} tools available for chat")

            return (
                gr.update(value=msg, visible=True),
                gr.update(choices=choices),
                gr.update(value=status_display),
                gr.update(value=tools_md),
            )

        # =============================================================================
        # =========================================================================
        # Function on_disconnect -> str to tuple
        # =========================================================================
        # =============================================================================

        def on_disconnect(server_name: str):
            """Disconnect from selected server"""
            if not server_name:
                return (
                    gr.update(value="No server selected", visible=True),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                )

            # Use sync wrapper that runs in dedicated MCP event loop
            success, msg = mcp_manager.disconnect_server_sync(server_name)

            choices = _get_server_choices(mcp_manager)

            return (
                gr.update(value=msg, visible=True),
                gr.update(choices=choices),
                gr.update(value="⚪ Disconnected"),
                gr.update(value="_Not connected_"),
            )

        # =============================================================================
        # =========================================================================
        # Function on_delete -> str to tuple
        # =========================================================================
        # =============================================================================

        def on_delete(server_name: str):
            """Delete selected server"""
            if not server_name:
                return (
                    gr.update(value="No server selected", visible=True),
                    gr.update(),
                    "",
                    "",
                    "",
                    "",
                    "_Select a server_",
                    None,
                )

            success = mcp_manager.remove_server(server_name)
            choices = _get_server_choices(mcp_manager)

            if success:
                return (
                    gr.update(value=f"Deleted server: {server_name}", visible=True),
                    gr.update(choices=choices, value=None),
                    "",
                    "",
                    "",
                    "",
                    "_Select a server_",
                    None,
                )
            else:
                return (
                    gr.update(value=f"Failed to delete: {server_name}", visible=True),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    server_name,
                )

        # =============================================================================
        # =========================================================================
        # Function on_connect_all -> None to tuple
        # =========================================================================
        # =============================================================================

        def on_connect_all():
            """Connect to all enabled servers"""
            # Use sync wrapper that runs in dedicated MCP event loop
            mcp_manager.connect_all_sync()

            # Refresh router's MCP awareness
            if hasattr(app_state, 'router') and app_state.router:
                app_state.router.set_mcp_manager(mcp_manager)

            choices = _get_server_choices(mcp_manager)
            total_tools = sum(len(s.tools) for s in mcp_manager.get_server_states().values())
            print(f"[MCP] All servers connected, {total_tools} total tools available")

            return (
                gr.update(value=f"Connected to all enabled servers ({total_tools} tools available)", visible=True),
                gr.update(choices=choices),
            )

        # =============================================================================
        # =========================================================================
        # Function on_disconnect_all -> None to tuple
        # =========================================================================
        # =============================================================================

        def on_disconnect_all():
            """Disconnect from all servers"""
            # Use sync wrapper that runs in dedicated MCP event loop
            mcp_manager.disconnect_all_sync()
            choices = _get_server_choices(mcp_manager)
            return (
                gr.update(value="Disconnected from all servers", visible=True),
                gr.update(choices=choices),
            )

        # =============================================================================
        # =========================================================================
        # Function on_add_server -> str, str, str, str, str, str, str, str to tuple
        # =========================================================================
        # =============================================================================

        def on_add_server(
            s_type: str,
            s_name: str,
            s_desc: str,
            s_cmd: str,
            s_args: str,
            s_env: str,
            s_url: str,
            s_headers: str
        ):
            """Add a new server"""
            # ==================================
            # Validate name
            if not s_name or not s_name.strip():
                return (
                    gr.update(value="Please enter a server name", visible=True),
                    gr.update(),
                )

            clean_name = s_name.strip().lower().replace(" ", "-")

            # ==================================
            # Check if exists
            if clean_name in mcp_manager.get_server_configs():
                return (
                    gr.update(value=f"Server already exists: {clean_name}", visible=True),
                    gr.update(),
                )

            # ==================================
            # Parse type
            try:
                server_type = MCPServerType(s_type)
            except ValueError:
                server_type = MCPServerType.STDIO

            # ==================================
            # Build config based on type
            config = MCPServerConfig(
                name=clean_name,
                type=server_type,
                enabled=True,
                description=s_desc.strip() if s_desc else "",
            )

            if server_type in (MCPServerType.STDIO, MCPServerType.DOCKER):
                if not s_cmd or not s_cmd.strip():
                    return (
                        gr.update(value="Command is required for STDIO/Docker servers", visible=True),
                        gr.update(),
                    )
                config.command = s_cmd.strip()
                config.args = s_args.split() if s_args else []
                config.env = _parse_env_string(s_env) if s_env else {}
            else:
                if not s_url or not s_url.strip():
                    return (
                        gr.update(value="URL is required for SSE/HTTP servers", visible=True),
                        gr.update(),
                    )
                config.url = s_url.strip()
                config.headers = _parse_headers_string(s_headers) if s_headers else {}

            # ==================================
            # Validate config
            is_valid, error_msg = validate_config(config)
            if not is_valid:
                return (
                    gr.update(value=f"Invalid config: {error_msg}", visible=True),
                    gr.update(),
                )

            # ==================================
            # Add server
            if mcp_manager.add_server(config):
                choices = _get_server_choices(mcp_manager)
                return (
                    gr.update(value=f"Added server: {clean_name}", visible=True),
                    gr.update(choices=choices),
                )
            else:
                return (
                    gr.update(value="Failed to add server", visible=True),
                    gr.update(),
                )

        # =============================================================================
        # =========================================================================
        # Function on_import_claude -> None to tuple
        # =========================================================================
        # =============================================================================

        def on_import_claude():
            """Import servers from Claude Desktop"""
            count, msg = mcp_manager.import_claude_desktop_config()
            choices = _get_server_choices(mcp_manager)
            return (
                gr.update(value=msg, visible=True),
                gr.update(choices=choices),
            )

        # =============================================================================
        # Wire Up Events
        # =============================================================================

        # Server type change
        server_type.change(
            fn=on_type_change,
            inputs=[server_type],
            outputs=[stdio_fields, http_fields]
        )

        # Refresh button
        refresh_btn.click(
            fn=on_refresh,
            inputs=[],
            outputs=[server_list]
        )

        # Server selection
        server_list.change(
            fn=on_server_select,
            inputs=[server_list],
            outputs=[
                detail_name,
                detail_type,
                detail_status,
                detail_config,
                tools_container,
                current_server,
                action_status,
            ]
        )

        # Connect button
        connect_btn.click(
            fn=on_connect,
            inputs=[current_server],
            outputs=[action_status, server_list, detail_status, tools_container]
        )

        # Disconnect button
        disconnect_btn.click(
            fn=on_disconnect,
            inputs=[current_server],
            outputs=[action_status, server_list, detail_status, tools_container]
        )

        # Delete button
        delete_btn.click(
            fn=on_delete,
            inputs=[current_server],
            outputs=[
                action_status,
                server_list,
                detail_name,
                detail_type,
                detail_status,
                detail_config,
                tools_container,
                current_server,
            ]
        )

        # Connect All button
        connect_all_btn.click(
            fn=on_connect_all,
            inputs=[],
            outputs=[add_status, server_list]
        )

        # Disconnect All button
        disconnect_all_btn.click(
            fn=on_disconnect_all,
            inputs=[],
            outputs=[add_status, server_list]
        )

        # Add Server button
        add_server_btn.click(
            fn=on_add_server,
            inputs=[
                server_type,
                server_name,
                server_description,
                command_input,
                args_input,
                env_input,
                url_input,
                headers_input,
            ],
            outputs=[add_status, server_list]
        )

        # Import Claude Desktop button
        import_claude_btn.click(
            fn=on_import_claude,
            inputs=[],
            outputs=[add_status, server_list]
        )

        gr.Markdown("---")
        gr.Markdown("""
**Server Types:**
- **STDIO**: Local tools (npx, python scripts)
- **Docker**: Containerized MCP servers
- **SSE**: Server-Sent Events (legacy remote)
- **HTTP**: Streamable HTTP (modern remote)

**Tips:**
- Click "Connect" to start a server and discover its tools
- Use "Import Claude Desktop" to import existing configs
- Tools from connected servers are available to the AI
        """)


# =============================================================================
'''
    Helper Functions : Utility functions for MCP tab
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function _get_server_choices -> MCPManager to List[str]
# =========================================================================
# =============================================================================

def _get_server_choices(manager: MCPManager) -> List[str]:
    """Build choices list for server radio buttons"""
    states = manager.get_server_states()
    choices = []

    for name, state in sorted(states.items()):
        emoji = state.get_status_emoji()
        tool_count = len(state.tools)

        if state.status == MCPConnectionStatus.CONNECTED:
            display = f"{emoji} {name} ({tool_count} tools)"
        else:
            display = f"{emoji} {name}"

        choices.append(display)

    return choices


# =============================================================================
# =========================================================================
# Function _extract_server_name -> str to str
# =========================================================================
# =============================================================================

def _extract_server_name(choice: str) -> str:
    """Extract server name from choice string"""
    # Format: "emoji name (X tools)" or "emoji name"
    # Remove emoji (first 2 chars including space)
    text = choice[2:] if len(choice) > 2 else choice

    # Remove tool count if present
    if " (" in text:
        text = text.split(" (")[0]

    return text.strip()


# =============================================================================
# =========================================================================
# Function _format_tools_display -> List[Dict] to str
# =========================================================================
# =============================================================================

def _format_tools_display(tools: List[Dict]) -> str:
    """Format tools as markdown for display"""
    if not tools:
        return "_No tools available. Connect to the server to discover tools._"

    output = []
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")

        output.append(f"**🔧 {name}**")
        output.append(f"> {description}")

        # ==================================
        # Show input schema if available
        if "inputSchema" in tool:
            schema = tool["inputSchema"]
            props = schema.get("properties", {})
            required = schema.get("required", [])

            if props:
                output.append("")
                output.append("| Parameter | Type | Required |")
                output.append("|-----------|------|----------|")

                for prop_name, prop_info in props.items():
                    prop_type = prop_info.get("type", "any")
                    is_required = "Yes" if prop_name in required else "No"
                    output.append(f"| `{prop_name}` | {prop_type} | {is_required} |")

        output.append("")
        output.append("---")
        output.append("")

    return "\n".join(output)


# =============================================================================
# =========================================================================
# Function _parse_env_string -> str to Dict[str, str]
# =========================================================================
# =============================================================================

def _parse_env_string(env_str: str) -> Dict[str, str]:
    """Parse environment variables from space-separated KEY=value string"""
    env = {}
    for pair in env_str.split():
        if "=" in pair:
            key, value = pair.split("=", 1)
            env[key] = value
    return env


# =============================================================================
# =========================================================================
# Function _parse_headers_string -> str to Dict[str, str]
# =========================================================================
# =============================================================================

def _parse_headers_string(headers_str: str) -> Dict[str, str]:
    """Parse HTTP headers from newline-separated Header: value string"""
    headers = {}
    for line in headers_str.strip().split("\n"):
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key.strip()] = value.strip()
    return headers


# =============================================================================
# End of File
# =============================================================================
# Project : SkillForge - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
