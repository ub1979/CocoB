# =============================================================================
'''
    File Name : provider_tab.py
    
    Description : LLM Provider Settings Tab - Allows users to select from 
                  configured providers, see and select available models (for 
                  local providers), login to OAuth providers (Anthropic, Gemini),
                  configure custom provider (endpoint, API key), test connection,
                  and switch providers without restart.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Imports
# =============================================================================

import gradio as gr
import threading
import requests
from typing import TYPE_CHECKING, Optional, Dict, Tuple

from .connection import test_provider_connection
from .models import fetch_models_for_provider
import config

if TYPE_CHECKING:
    from .state import AppState

# =============================================================================
# Constants
# =============================================================================

# OAuth providers that need login buttons
OAUTH_PROVIDERS = {"anthropic-oauth", "gemini-oauth"}

# Providers that support model listing
LOCAL_PROVIDERS = {"ollama", "lmstudio", "vllm", "mlx"}

# Local server configurations for health checks
LOCAL_SERVER_CONFIG = {
    "ollama": {"port": 11434, "health_url": "http://localhost:11434/api/tags"},
    "mlx": {"port": 8080, "health_url": "http://localhost:8080/v1/models"},
    "lmstudio": {"port": 1234, "health_url": "http://localhost:1234/v1/models"},
    "vllm": {"port": 8000, "health_url": "http://localhost:8000/v1/models"},
}

# =============================================================================
'''
    Utility Functions : Helper functions for provider configuration and OAuth
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function check_local_server_status -> str to tuple[bool, str]
# =========================================================================
# =============================================================================
def check_local_server_status(provider_name: str) -> tuple[bool, str]:
    """
    Check if a local LLM server is running
    
    Args:
        provider_name: Name of the provider (ollama, mlx, lmstudio, vllm)
        
    Returns:
        Tuple of (is_running, status_message)
    """
    # ==================================
    # Check if this is a local provider
    # ==================================
    if provider_name not in LOCAL_SERVER_CONFIG:
        return True, "API-based provider (cloud)"
    
    server_info = LOCAL_SERVER_CONFIG[provider_name]
    
    try:
        response = requests.get(server_info["health_url"], timeout=2)
        if response.status_code == 200:
            return True, f"🟢 Running on port {server_info['port']}"
        else:
            return False, f"🔴 HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"🔴 Not running (port {server_info['port']})"
    except Exception as e:
        return False, f"🔴 Error: {str(e)[:50]}"

# =============================================================================
# =========================================================================
# Function get_server_start_command -> str to str
# =========================================================================
# =============================================================================
def get_server_start_command(provider_name: str) -> str:
    """
    Get the command to start a local server
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        Command string to start the server
    """
    commands = {
        "ollama": "ollama serve",
        "mlx": "python -m mlx_lm.server --model mlx-community/Llama-3.2-1B-Instruct-4bit --port 8080",
        "lmstudio": "Start LM Studio app and enable server",
        "vllm": "python -m vllm.entrypoints.openai.api_server --model <model-name>",
    }
    return commands.get(provider_name, "See documentation for startup instructions")

# =============================================================================
# =========================================================================
# Function _get_safe_config -> str to dict
# =========================================================================
# =============================================================================
def _get_safe_config(provider_name: str) -> dict:
    """Get provider config with sensitive data masked"""
    # ==================================
    if provider_name not in config.LLM_PROVIDERS:
        return {}

    cfg = config.LLM_PROVIDERS[provider_name].copy()

    # Mask sensitive fields
    # ==================================
    if cfg.get("api_key"):
        cfg["api_key"] = "***hidden***"

    return cfg

# =============================================================================
# =========================================================================
# Function _get_oauth_status -> str to tuple[bool, str]
# =========================================================================
# =============================================================================
def _get_oauth_status(provider_name: str) -> tuple[bool, str]:
    """
    Check OAuth login status for a provider.

    Returns:
        Tuple of (is_logged_in, status_message)
    """
    from coco_b.core.llm.auth import is_logged_in, get_token_info

    # Map config names to auth provider names
    auth_provider = provider_name.replace("-oauth", "")

    # ==================================
    if is_logged_in(auth_provider):
        info = get_token_info(auth_provider)
        # ==================================
        if info and info.get("expired") and not info.get("has_refresh_token"):
            return False, "Token expired - re-login required"
        return True, "Logged in"
    return False, "Not logged in"

# =============================================================================
# =========================================================================
# Function _run_oauth_login -> str to tuple[bool, str]
# =========================================================================
# =============================================================================
def _run_oauth_login(provider_name: str) -> tuple[bool, str]:
    """
    Run OAuth login flow for a provider.

    Returns:
        Tuple of (success, message)
    """
    from coco_b.core.llm.auth import gemini, anthropic, save_credentials

    # Map config names to auth provider names
    auth_provider = provider_name.replace("-oauth", "")

    try:
        # ==================================
        if auth_provider == "gemini":
            tokens = gemini.login()
        elif auth_provider == "anthropic":
            tokens = anthropic.login()
        else:
            return False, f"Unknown OAuth provider: {auth_provider}"

        save_credentials(auth_provider, tokens)
        return True, "Login successful!"
    except Exception as e:
        return False, f"Login failed: {str(e)}"

# =============================================================================
# =========================================================================
# Function _run_oauth_logout -> str to tuple[bool, str]
# =========================================================================
# =============================================================================
def _run_oauth_logout(provider_name: str) -> tuple[bool, str]:
    """
    Logout from an OAuth provider.

    Returns:
        Tuple of (success, message)
    """
    from coco_b.core.llm.auth import delete_credentials

    auth_provider = provider_name.replace("-oauth", "")

    # ==================================
    if delete_credentials(auth_provider):
        return True, "Logged out successfully"
    return False, "Not logged in"

# =============================================================================
'''
    create_provider_tab : Main UI creation function for provider settings tab
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function create_provider_tab -> AppState, Optional to None
# =========================================================================
# =============================================================================
def create_provider_tab(app_state: "AppState", model_info_component=None):
    """
    Create the LLM Provider settings tab.

    Args:
        app_state: Shared application state
        model_info_component: Optional Gradio component to update with model info
                              (e.g., the model display in Chat tab)

    Returns:
        None (creates Gradio components in current context)
    """
    with gr.Tab("Settings"):
        gr.Markdown("# Settings", elem_classes=["settings-title"])

        # Current provider display
        current_info = gr.Markdown(
            f"**Current Provider:** {app_state.router.llm.provider_name} - {app_state.router.llm.model_name}"
        )

        # =============================================================================
        # Appearance Section
        # =============================================================================
        with gr.Accordion("🎨  Appearance", open=False):
            gr.Markdown("Customize the look and feel of the application.")
            with gr.Row():
                dark_mode_toggle = gr.Checkbox(
                    label="🌙 Dark Mode",
                    value=True,
                    info="Switch to dark theme for reduced eye strain",
                    interactive=True
                )

        # =============================================================================
        # Bot Integrations Section
        # =============================================================================
        with gr.Accordion("📱  Messaging Bot Integrations", open=True):
            gr.Markdown("Connect coco B to your favorite messaging platforms.")

            # Telegram Bot
            with gr.Group():
                gr.Markdown("""
                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; margin-bottom: 8px;">
                    <div style="width: 44px; height: 44px; background: linear-gradient(135deg, #0088cc 0%, #229ED9 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">📱</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #f1f5f9; font-size: 1.1rem;">Telegram Bot</div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Connect to Telegram for mobile messaging</div>
                    </div>
                    <div style="padding: 4px 12px; background: #22c55e; border-radius: 20px; font-size: 0.75rem; color: white; font-weight: 600;">Configured</div>
                </div>
                """)
                with gr.Row():
                    telegram_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        placeholder="Enter your Telegram bot token...",
                        scale=3
                    )
                    telegram_save_btn = gr.Button("💾 Save", scale=1, size="sm")

            # WhatsApp Bot
            with gr.Group():
                gr.Markdown("""
                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; margin-bottom: 8px;">
                    <div style="width: 44px; height: 44px; background: linear-gradient(135deg, #25D366 0%, #128C7E 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">💬</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #f1f5f9; font-size: 1.1rem;">WhatsApp Bot</div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Connect via WhatsApp Business API</div>
                    </div>
                    <div style="padding: 4px 12px; background: #eab308; border-radius: 20px; font-size: 0.75rem; color: white; font-weight: 600;">Coming Soon</div>
                </div>
                """)
                with gr.Row():
                    whatsapp_phone = gr.Textbox(
                        label="Phone Number ID",
                        placeholder="Enter your WhatsApp Business phone ID...",
                        scale=2,
                        interactive=False
                    )
                    whatsapp_token = gr.Textbox(
                        label="Access Token",
                        type="password",
                        placeholder="Enter your access token...",
                        scale=2,
                        interactive=False
                    )
                    whatsapp_save_btn = gr.Button("💾 Save", scale=1, size="sm", interactive=False)

            # Slack Bot
            with gr.Group():
                gr.Markdown("""
                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; margin-bottom: 8px;">
                    <div style="width: 44px; height: 44px; background: linear-gradient(135deg, #4A154B 0%, #611f69 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">💼</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #f1f5f9; font-size: 1.1rem;">Slack Bot</div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Connect to Slack workspaces</div>
                    </div>
                    <div style="padding: 4px 12px; background: #eab308; border-radius: 20px; font-size: 0.75rem; color: white; font-weight: 600;">Coming Soon</div>
                </div>
                """)
                with gr.Row():
                    slack_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        placeholder="xoxb-your-token...",
                        scale=2,
                        interactive=False
                    )
                    slack_signing = gr.Textbox(
                        label="Signing Secret",
                        type="password",
                        placeholder="Enter signing secret...",
                        scale=2,
                        interactive=False
                    )
                    slack_save_btn = gr.Button("💾 Save", scale=1, size="sm", interactive=False)

            # Discord Bot
            with gr.Group():
                gr.Markdown("""
                <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; margin-bottom: 8px;">
                    <div style="width: 44px; height: 44px; background: linear-gradient(135deg, #5865F2 0%, #7289DA 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">🎮</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #f1f5f9; font-size: 1.1rem;">Discord Bot</div>
                        <div style="color: #94a3b8; font-size: 0.85rem;">Connect to Discord servers</div>
                    </div>
                    <div style="padding: 4px 12px; background: #eab308; border-radius: 20px; font-size: 0.75rem; color: white; font-weight: 600;">Coming Soon</div>
                </div>
                """)
                with gr.Row():
                    discord_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        placeholder="Enter your Discord bot token...",
                        scale=3,
                        interactive=False
                    )
                    discord_save_btn = gr.Button("💾 Save", scale=1, size="sm", interactive=False)

        # =============================================================================
        # Local LLM Servers Section
        # =============================================================================
        with gr.Accordion("🖥️  Local LLM Servers", open=True):
            gr.Markdown("Local LLM servers that run on your machine. Start the server before using.")
        
            # Create server status cards for local providers
            server_status_displays = {}
            server_configs = {
                "ollama": {
                    "name": "OLLAMA",
                    "desc": "Local LLM server",
                    "icon": "🦙",
                    "cmd": "ollama serve"
                },
                "vllm": {
                    "name": "VLLM",
                    "desc": "High-throughput inference",
                    "icon": "⚡",
                    "cmd": "python -m vllm.entrypoints.openai.api_server --model <model>"
                },
                "lmstudio": {
                    "name": "LMSTUDIO",
                    "desc": "LM Studio local server",
                    "icon": "🎯",
                    "cmd": "Start LM Studio and enable server"
                },
                "mlx": {
                    "name": "MLX",
                    "desc": "Apple Silicon optimized",
                    "icon": "🍎",
                    "cmd": "python -m mlx_lm.server --model <model> --port 8080"
                },
            }

            for provider, cfg in server_configs.items():
                is_running, status = check_local_server_status(provider)
                port = LOCAL_SERVER_CONFIG.get(provider, {}).get("port", "N/A")
                status_color = "#22c55e" if is_running else "#ef4444"
                status_text = f"Running on port {port}" if is_running else f"Not running (port {port})"

                gr.Markdown(f"""
                <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div style="width: 40px; height: 40px; background: #3b82f6; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem;">{cfg['icon']}</div>
                            <div>
                                <div style="font-weight: 600; color: #f1f5f9;">{cfg['name']}</div>
                                <div style="color: #94a3b8; font-size: 0.85rem;">{cfg['desc']}</div>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 8px; height: 8px; background: {status_color}; border-radius: 50%;"></div>
                            <span style="color: {status_color}; font-size: 0.85rem; font-weight: 500;">{status_text}</span>
                        </div>
                    </div>
                    <div style="margin-top: 12px; padding: 8px 12px; background: #0f172a; border-radius: 6px; font-family: monospace; font-size: 0.8rem; color: #94a3b8;">
                        To start: <code style="color: #60a5fa;">{cfg['cmd']}</code>
                    </div>
                </div>
                """)
                # Hidden status for dynamic updates
                with gr.Row(visible=False):
                    status_display = gr.Markdown(status)
                    server_status_displays[provider] = status_display

            # Refresh server status button
            refresh_server_btn = gr.Button("🔄 Refresh Status", variant="secondary", size="sm")

            # Server start instructions (dynamic)
            server_instructions = gr.Markdown(
                "",
                visible=False
            )

            gr.Markdown("---")
            gr.Markdown("### Select Local Provider")
            gr.Markdown("Click on a provider below to select it, then choose a model.")

            # Model selection as clickable buttons
            selected_local_provider = gr.State(value=None)
            selected_local_model = gr.State(value=None)

            gr.Markdown("""
            <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
            """)

            with gr.Row():
                ollama_btn = gr.Button(
                    "🦙 Ollama",
                    variant="secondary",
                    size="lg",
                    elem_classes=["model-select-btn"]
                )
                lmstudio_btn = gr.Button(
                    "🎯 LM Studio",
                    variant="secondary",
                    size="lg",
                    elem_classes=["model-select-btn"]
                )
                mlx_btn = gr.Button(
                    "🍎 MLX",
                    variant="secondary",
                    size="lg",
                    elem_classes=["model-select-btn"]
                )
                vllm_btn = gr.Button(
                    "⚡ vLLM",
                    variant="secondary",
                    size="lg",
                    elem_classes=["model-select-btn"]
                )

            # Model list display (shown after selecting a provider)
            models_container = gr.Markdown(
                "Select a provider above to see available models",
                elem_classes=["models-info"]
            )

            # Model dropdown (populated dynamically)
            model_dropdown_local = gr.Dropdown(
                choices=[],
                value=None,
                label="📦 Available Models",
                info="Select a model to use (click Refresh to reload)",
                allow_custom_value=True,
                visible=True
            )

            with gr.Row():
                refresh_models_local_btn = gr.Button("🔄 Refresh Models", size="sm")
                use_local_btn = gr.Button("▶️ Use Local Server", variant="primary")
        
            def update_server_status():
                """Update all server status displays"""
                return [check_local_server_status(p)[1] for p in ["ollama", "mlx", "lmstudio", "vllm"]]

            def on_local_provider_click(provider_name):
                """Handle local provider button click"""
                success, models, message = fetch_models_for_provider(
                    provider_name,
                    config.LLM_PROVIDERS.get(provider_name, {"base_url": LOCAL_SERVER_CONFIG.get(provider_name, {}).get("health_url", "").replace("/api/tags", "/v1").replace("/v1/models", "/v1")})
                )
                if success and models:
                    return (
                        provider_name,
                        gr.update(choices=models, value=models[0] if models else None, visible=True),
                        f"Found {len(models)} models for {provider_name.upper()}"
                    )
                else:
                    return (
                        provider_name,
                        gr.update(choices=[], visible=True),
                        message
                    )

            def on_use_local_server(provider_name, model_name):
                """Switch to the selected local provider and model"""
                if not provider_name:
                    return gr.update(value="Please select a provider first")
                if not model_name:
                    return gr.update(value="Please select a model first")

                custom_config = config.LLM_PROVIDERS.get(provider_name, {}).copy()
                if custom_config:
                    custom_config["model"] = model_name
                else:
                    # Build config for unknown provider
                    port = LOCAL_SERVER_CONFIG.get(provider_name, {}).get("port", 11434)
                    custom_config = {
                        "provider": "openai",
                        "model": model_name,
                        "base_url": f"http://localhost:{port}/v1",
                        "api_key": None,
                        "context_window": 8192,
                        "max_response_tokens": 4096,
                    }

                success, msg = app_state.switch_provider(provider_name, custom_config)
                return msg

            # Wire up local provider buttons
            ollama_btn.click(
                fn=lambda: on_local_provider_click("ollama"),
                inputs=[],
                outputs=[selected_local_provider, model_dropdown_local, models_container]
            )
            lmstudio_btn.click(
                fn=lambda: on_local_provider_click("lmstudio"),
                inputs=[],
                outputs=[selected_local_provider, model_dropdown_local, models_container]
            )
            mlx_btn.click(
                fn=lambda: on_local_provider_click("mlx"),
                inputs=[],
                outputs=[selected_local_provider, model_dropdown_local, models_container]
            )
            vllm_btn.click(
                fn=lambda: on_local_provider_click("vllm"),
                inputs=[],
                outputs=[selected_local_provider, model_dropdown_local, models_container]
            )

            refresh_models_local_btn.click(
                fn=lambda p: on_local_provider_click(p) if p else (None, gr.update(), "Select a provider first"),
                inputs=[selected_local_provider],
                outputs=[selected_local_provider, model_dropdown_local, models_container]
            )

            use_local_btn.click(
                fn=on_use_local_server,
                inputs=[selected_local_provider, model_dropdown_local],
                outputs=[models_container]
            )

        # =============================================================================
        # CLI Providers (Subscription-based) Section
        # =============================================================================
        with gr.Accordion("💳  CLI Providers (Subscription-based)", open=False):
            gr.Markdown("Providers that require a subscription (Claude, ChatGPT, etc.)")

            with gr.Row():
                # Provider dropdown
                provider_list = list(config.LLM_PROVIDERS.keys())
                provider_dropdown = gr.Dropdown(
                    choices=provider_list,
                    value=config.LLM_PROVIDER,
                    label="Provider",
                    info="Select a pre-configured provider",
                    scale=2
                )

                # Model dropdown (populated dynamically)
                model_dropdown = gr.Dropdown(
                    choices=[],
                    value=None,
                    label="Model",
                    info="Available models (click Refresh to load)",
                    scale=2,
                    allow_custom_value=True
                )

                # Refresh models button
                refresh_models_btn = gr.Button("🔄 Refresh", scale=1)

            # Model status message
            model_status = gr.Textbox(
                label="Model Status",
                interactive=False,
                visible=False
            )

            with gr.Row():
                # Switch button
                switch_btn = gr.Button("Switch Provider", variant="primary", scale=2)

            # Status message
            status_msg = gr.Textbox(
                label="Status",
                interactive=False,
                visible=False
            )

            def on_provider_select(provider_name):
                """Show startup instructions for selected provider"""
                is_running, _ = check_local_server_status(provider_name)
                if not is_running and provider_name in LOCAL_SERVER_CONFIG:
                    cmd = get_server_start_command(provider_name)
                    return f"""
                    ⚠️ **{provider_name.upper()} is not running!**

                    To start it, run this command in a terminal:
                    ```bash
                    {cmd}
                    ```

                    Then click "🔄 Refresh Server Status" above.
                    """
                return "💡 **Tip:** Select a provider above to see startup instructions if it's not running."

            # OAuth section (visible only for OAuth providers)
            with gr.Group(visible=False) as oauth_section:
                gr.Markdown("### OAuth Authentication")
                oauth_status = gr.Markdown("Checking login status...")

                with gr.Row():
                    login_btn = gr.Button("🔑 Login", variant="primary", scale=1)
                    logout_btn = gr.Button("Logout", variant="secondary", scale=1)

                oauth_msg = gr.Textbox(
                    label="OAuth Status",
                    interactive=False,
                    visible=False
                )

                gr.Markdown("*Or run from terminal:* `python -m core.llm.auth login anthropic`")

            # Provider details (read-only)
            with gr.Accordion("Provider Details", open=False):
                provider_details = gr.JSON(
                    label="Configuration",
                    value=_get_safe_config(config.LLM_PROVIDER)
                )

        # =============================================================================
        # Cloud API Providers Section
        # =============================================================================
        with gr.Accordion("☁️  Cloud API Providers", open=False):
            gr.Markdown("Configure API keys for cloud-based LLM providers.")

            gr.Markdown("### 🔑 API Keys")
            gr.Markdown("""*Paste your API keys here (saved to environment for this session)*

**Note:** Anthropic has blocked OAuth tokens for third-party tools (Jan 2026).
Use an API key from [console.anthropic.com](https://console.anthropic.com) instead.""")

            with gr.Row():
                api_key_provider = gr.Dropdown(
                    choices=["anthropic", "openai", "groq", "together", "gemini"],
                    value="anthropic",
                    label="Provider",
                    scale=1
                )
                api_key_input = gr.Textbox(
                    label="API Key",
                    type="password",
                    placeholder="sk-ant-... or sk-...",
                    scale=3
                )
                save_key_btn = gr.Button("💾 Save Key", scale=1)

            api_key_status = gr.Textbox(
                label="Status",
                interactive=False,
                visible=False
            )

            gr.Markdown("---")
            gr.Markdown("### Custom Provider")
            gr.Markdown("*Configure a custom OpenAI-compatible endpoint*")

            with gr.Row():
                custom_url = gr.Textbox(
                    label="API Endpoint",
                    placeholder="http://localhost:11434/v1",
                    scale=2
                )
                custom_model = gr.Textbox(
                    label="Model Name",
                    placeholder="llama3",
                    scale=1
                )

            with gr.Row():
                custom_key = gr.Textbox(
                    label="API Key (optional)",
                    type="password",
                    placeholder="sk-...",
                    scale=2
                )
                test_btn = gr.Button("Test Connection", scale=1)

            custom_status = gr.Textbox(
                label="Connection Status",
                interactive=False,
                visible=False
            )

            use_custom_btn = gr.Button("Use Custom Provider", variant="secondary")

        # =============================================================================
        # Memory Settings Section
        # =============================================================================
        with gr.Accordion("🧠  Memory Settings", open=False):
            gr.Markdown("Configure how coco B remembers conversations.")

            memory_enabled = gr.Checkbox(
                label="Enable Persistent Memory",
                value=True,
                info="Remember conversations across sessions"
            )
            memory_context = gr.Slider(
                label="Context Window Size",
                minimum=5,
                maximum=50,
                value=20,
                step=1,
                info="Number of recent messages to include in context"
            )
            with gr.Row():
                clear_memory_btn = gr.Button("🗑️ Clear All Memory", variant="secondary")
                export_memory_btn = gr.Button("📤 Export Memory", variant="secondary")

        # =============================================================================
        # Event Handlers Section
        # =============================================================================

        # =============================================================================
        # =========================================================================
        # Function on_provider_change -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_provider_change(provider_name):
            """Handle provider dropdown change"""
            # Check if OAuth provider
            is_oauth = provider_name in OAUTH_PROVIDERS

            # Get OAuth status if applicable
            oauth_status_text = ""
            # ==================================
            if is_oauth:
                logged_in, status_text = _get_oauth_status(provider_name)
                oauth_status_text = f"**Status:** {status_text}"

            # Get config details
            details = _get_safe_config(provider_name)

            # Get current model from config
            current_model = details.get("model", "")

            return (
                gr.update(visible=is_oauth),  # oauth_section
                gr.update(value=oauth_status_text),  # oauth_status
                gr.update(value=details),  # provider_details
                gr.update(value=current_model),  # model_dropdown value
            )

        # =============================================================================
        # =========================================================================
        # Function on_refresh_models -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_refresh_models(provider_name):
            """Fetch available models for the selected provider"""
            # ==================================
            if provider_name not in config.LLM_PROVIDERS:
                return gr.update(choices=[]), gr.update(value="Unknown provider", visible=True)

            provider_config = config.LLM_PROVIDERS[provider_name]
            success, models, message = fetch_models_for_provider(provider_name, provider_config)

            # ==================================
            if success and models:
                # Set the first model as default if current model not in list
                current_model = provider_config.get("model", "")
                selected = current_model if current_model in models else models[0]
                return (
                    gr.update(choices=models, value=selected),
                    gr.update(value=message, visible=True)
                )
            else:
                # Keep existing value, show message
                return (
                    gr.update(choices=models if models else []),
                    gr.update(value=message, visible=True)
                )

        # =============================================================================
        # =========================================================================
        # Function on_switch -> str, str to tuple
        # =========================================================================
        # =============================================================================
        def on_switch(provider_name, model_name):
            """Switch to selected provider and model"""
            # If model specified, override the config
            custom_config = None
            # ==================================
            if model_name and provider_name in config.LLM_PROVIDERS:
                custom_config = config.LLM_PROVIDERS[provider_name].copy()
                custom_config["model"] = model_name

            success, msg = app_state.switch_provider(
                provider_name,
                custom_config=custom_config
            )

            new_info = f"**Current Provider:** {app_state.router.llm.provider_name} - {app_state.router.llm.model_name}"
            chat_model_info = f"{app_state.router.llm.provider_name}: {app_state.router.llm.model_name}"
            details = _get_safe_config(provider_name)

            # Log the switch for visibility
            # ==================================
            if success:
                print(f"[Settings] Switched to {app_state.router.llm.provider_name}: {app_state.router.llm.model_name}")

            results = [
                gr.update(value=new_info),
                gr.update(value=msg, visible=True),
                gr.update(value=details),
            ]

            # Update external model_info component if provided
            # ==================================
            if model_info_component is not None:
                results.append(gr.update(value=chat_model_info))

            return tuple(results)

        # =============================================================================
        # =========================================================================
        # Function on_login -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_login(provider_name):
            """Handle OAuth login button click"""
            success, msg = _run_oauth_login(provider_name)

            # ==================================
            if success:
                logged_in, status_text = _get_oauth_status(provider_name)
                return (
                    gr.update(value=f"**Status:** {status_text}"),
                    gr.update(value=msg, visible=True)
                )
            else:
                return (
                    gr.update(),
                    gr.update(value=msg, visible=True)
                )

        # =============================================================================
        # =========================================================================
        # Function on_logout -> str to tuple
        # =========================================================================
        # =============================================================================
        def on_logout(provider_name):
            """Handle OAuth logout button click"""
            success, msg = _run_oauth_logout(provider_name)
            logged_in, status_text = _get_oauth_status(provider_name)

            return (
                gr.update(value=f"**Status:** {status_text}"),
                gr.update(value=msg, visible=True)
            )

        # =============================================================================
        # =========================================================================
        # Function on_save_api_key -> str, str to gr.update
        # =========================================================================
        # =============================================================================
        def on_save_api_key(provider_name, api_key):
            """Save API key to environment and config"""
            import os

            # ==================================
            if not api_key or not api_key.strip():
                return gr.update(value="Please enter an API key", visible=True)

            # Map provider to environment variable name
            env_var_map = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "groq": "GROQ_API_KEY",
                "together": "TOGETHER_API_KEY",
                "gemini": "GOOGLE_API_KEY",
            }

            env_var = env_var_map.get(provider_name)
            # ==================================
            if not env_var:
                return gr.update(value=f"Unknown provider: {provider_name}", visible=True)

            # Save to environment (current session)
            os.environ[env_var] = api_key.strip()

            # Also update the config in memory
            # ==================================
            if provider_name in config.LLM_PROVIDERS:
                config.LLM_PROVIDERS[provider_name]["api_key"] = api_key.strip()

            print(f"[Settings] Saved API key for {provider_name}")
            return gr.update(value=f"API key saved for {provider_name}! You can now switch to this provider.", visible=True)

        # =============================================================================
        # =========================================================================
        # Function on_test -> str, str, str to gr.update
        # =========================================================================
        # =============================================================================
        def on_test(url, model, api_key):
            """Test custom provider connection"""
            # ==================================
            if not url or not model:
                return gr.update(value="Please provide URL and model name", visible=True)
            success, msg = test_provider_connection(url, model, api_key)
            return gr.update(value=msg, visible=True)

        # =============================================================================
        # =========================================================================
        # Function on_use_custom -> str, str, str to tuple
        # =========================================================================
        # =============================================================================
        def on_use_custom(url, model, api_key):
            """Switch to custom provider"""
            # ==================================
            if not url or not model:
                results = [
                    gr.update(),
                    gr.update(value="Please provide URL and model name", visible=True)
                ]
                # ==================================
                if model_info_component is not None:
                    results.append(gr.update())
                return tuple(results)

            custom_config = {
                "provider": "openai",  # OpenAI-compatible
                "model": model,
                "base_url": url,
                "api_key": api_key if api_key else None,
                "context_window": 8192,
                "max_response_tokens": 4096,
            }
            success, msg = app_state.switch_provider("custom", custom_config)
            new_info = f"**Current Provider:** {app_state.router.llm.provider_name} - {app_state.router.llm.model_name}"
            chat_model_info = f"{app_state.router.llm.provider_name}: {app_state.router.llm.model_name}"

            # ==================================
            if success:
                print(f"[Settings] Switched to custom: {app_state.router.llm.provider_name}: {app_state.router.llm.model_name}")

            results = [
                gr.update(value=new_info),
                gr.update(value=msg, visible=True)
            ]
            # ==================================
            if model_info_component is not None:
                results.append(gr.update(value=chat_model_info))

            return tuple(results)

        # =============================================================================
        # Wire Up Events Section
        # =============================================================================

        # Provider dropdown change
        provider_dropdown.change(
            fn=on_provider_change,
            inputs=[provider_dropdown],
            outputs=[oauth_section, oauth_status, provider_details, model_dropdown]
        )
        
        # =============================================================================
        # Server status events
        # =============================================================================
        # Refresh server status button
        refresh_server_btn.click(
            fn=update_server_status,
            inputs=[],
            outputs=list(server_status_displays.values())
        )
        
        # Update instructions when provider changes
        provider_dropdown.change(
            fn=on_provider_select,
            inputs=[provider_dropdown],
            outputs=[server_instructions]
        )

        # Refresh models button
        refresh_models_btn.click(
            fn=on_refresh_models,
            inputs=[provider_dropdown],
            outputs=[model_dropdown, model_status]
        )

        # Switch provider button - outputs depend on whether external component is passed
        switch_outputs = [current_info, status_msg, provider_details]
        # ==================================
        if model_info_component is not None:
            switch_outputs.append(model_info_component)

        switch_btn.click(
            fn=on_switch,
            inputs=[provider_dropdown, model_dropdown],
            outputs=switch_outputs
        )

        # OAuth login button
        login_btn.click(
            fn=on_login,
            inputs=[provider_dropdown],
            outputs=[oauth_status, oauth_msg]
        )

        # OAuth logout button
        logout_btn.click(
            fn=on_logout,
            inputs=[provider_dropdown],
            outputs=[oauth_status, oauth_msg]
        )

        # Save API key button
        save_key_btn.click(
            fn=on_save_api_key,
            inputs=[api_key_provider, api_key_input],
            outputs=[api_key_status]
        )

        # Test connection button
        test_btn.click(
            fn=on_test,
            inputs=[custom_url, custom_model, custom_key],
            outputs=[custom_status]
        )

        # Use custom provider button
        custom_outputs = [current_info, status_msg]
        # ==================================
        if model_info_component is not None:
            custom_outputs.append(model_info_component)

        use_custom_btn.click(
            fn=on_use_custom,
            inputs=[custom_url, custom_model, custom_key],
            outputs=custom_outputs
        )

        gr.Markdown("---")
        gr.Markdown("*Settings are applied immediately. No restart needed!*")

# =============================================================================
# End of File
# =============================================================================
# Project : mr_bot - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
