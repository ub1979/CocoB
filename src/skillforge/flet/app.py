"""
SkillForge Flet app — entry point and top-level layout.

Thin orchestrator: creates view instances, wires 5-tab navigation,
handles login gate, admin panel, auto-start bots, and cleanup on shutdown.
"""

import asyncio
import os
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import flet as ft
from flet import Icons as icons

from skillforge import PROJECT_ROOT
from skillforge.flet.theme import AppColors, API_KEY_ENV_MAP
from skillforge.flet.storage import secure_storage
from skillforge.flet.views.chat import ChatView
from skillforge.flet.views.settings import SettingsView
from skillforge.flet.views.tools import ToolsView
from skillforge.flet.views.mcp import MCPPanel
from skillforge.flet.views.skills import SkillsPanel
from skillforge.flet.views.clawhub import ClawHubPanel
from skillforge.flet.views.history import HistoryView
from skillforge.flet.views.login import LoginView
from skillforge.flet.views.admin import AdminView
from skillforge.core.identity_resolver import IdentityResolver
from skillforge.core.permission_requests import PermissionRequestManager

# ---------------------------------------------------------------------------
# Lazy imports — bot-related components
# ---------------------------------------------------------------------------

BOT_AVAILABLE = False
MCPManager = None
SCHEDULER_AVAILABLE = False
TELEGRAM_AVAILABLE = False
TelegramChannel = None
TelegramConfig = None
WHATSAPP_AVAILABLE = False
WhatsAppChannel = None
WhatsAppConfig = None
SLACK_AVAILABLE = False
SlackChannel = None
SlackConfig = None

try:
    from skillforge.core.sessions import SessionManager
    from skillforge.core.llm import LLMProviderFactory
    from skillforge.core.llm.base import LLMConfig
    from skillforge.core.router import MessageRouter
    from skillforge.core.skills import SkillsManager
    from skillforge.ui.settings.state import AppState
    import config
    BOT_AVAILABLE = True

    try:
        from skillforge.core.scheduler import SchedulerManager, ScheduledTask, create_scheduler_manager
        SCHEDULER_AVAILABLE = True
    except ImportError as sched_err:
        print(f"Note: Scheduler not available: {sched_err}")

    try:
        from skillforge.core.mcp_client import MCPManager
    except ImportError as mcp_err:
        print(f"Note: MCP components not available: {mcp_err}")

    try:
        from skillforge.channels.telegram import TelegramChannel, TelegramConfig
        TELEGRAM_AVAILABLE = True
    except ImportError:
        pass

    try:
        from skillforge.channels.whatsapp import WhatsAppChannel, WhatsAppConfig
        WHATSAPP_AVAILABLE = True
    except ImportError:
        pass

    try:
        from skillforge.channels.slack_channel import SlackChannel, SlackConfig
        SLACK_AVAILABLE = True
    except ImportError:
        pass

except ImportError as e:
    print(f"Warning: Could not import some skillforge components: {e}")
    if 'TELEGRAM_AVAILABLE' not in dir():
        TELEGRAM_AVAILABLE = False
    if 'WHATSAPP_AVAILABLE' not in dir():
        WHATSAPP_AVAILABLE = False
    if 'SLACK_AVAILABLE' not in dir():
        SLACK_AVAILABLE = False


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class SkillForgeApp:
    """Main SkillForge Flet application — thin orchestrator."""

    def __init__(self, page: ft.Page, admin_username: str = "admin"):
        self.page = page
        self.page.title = "SkillForge - Intelligent AI Assistant"
        self.page.theme_mode = ft.ThemeMode.DARK

        # Ensure dark mode colours are applied before building UI
        if not AppColors.is_dark_mode():
            AppColors.set_dark_mode(True)

        self.page.bgcolor = AppColors.BACKGROUND
        self.page.padding = 0
        self.page.window_width = 1200
        self.page.window_height = 800

        # Set app icon
        icon_path = PROJECT_ROOT / "icon" / "icon.png"
        if icon_path.exists():
            self.page.window.icon = str(icon_path)

        self.admin_username = admin_username
        self.current_user_id = admin_username
        self._executor = ThreadPoolExecutor(max_workers=4)
        self.scheduler_manager = None
        self._scheduler_loop = None

        # Admin subsystems
        self.identity_resolver = IdentityResolver()
        self.request_manager = PermissionRequestManager()

        self._init_bot_components()
        self._init_views()
        self._init_nav()
        self._layout()

    # -----------------------------------------------------------------
    # Bot component init (router, skills, MCP, scheduler)
    # -----------------------------------------------------------------

    def _init_bot_components(self):
        """Initialize backend: router, skills, MCP, scheduler."""
        self.session_manager = None
        self.router = None
        self.app_state = None
        self.skills_manager = None
        self.mcp_manager = None

        # Load saved API keys from secure storage BEFORE initializing providers
        self._load_saved_api_keys()

        if not BOT_AVAILABLE:
            return

        try:
            self.session_manager = SessionManager(config.SESSION_DATA_DIR)

            # Use saved provider or config default
            saved_provider = secure_storage.get_setting('current_provider')
            active_provider = (saved_provider
                               if saved_provider and saved_provider in config.LLM_PROVIDERS
                               else config.LLM_PROVIDER)
            print(f"[Startup] Using provider: {active_provider}"
                  + (" (saved)" if saved_provider else " (default)"))

            llm_config = config.LLM_PROVIDERS[active_provider]
            llm_provider = LLMProviderFactory.from_dict(llm_config)
            self.router = MessageRouter(self.session_manager, llm_provider)

            # Skills
            self.skills_manager = SkillsManager(
                bundled_dir=Path(config.SKILLS_DIR),
                project_dir=Path(config.SKILLS_DIR),
                user_dir=Path(config.USER_SKILLS_DIR),
            )
            loaded_skills = self.skills_manager.load_all_skills()
            print(f"[Skills] Loaded {len(loaded_skills)} skills")

            if hasattr(self.router, 'personality'):
                self.router.personality.skills_manager = self.skills_manager

            # MCP
            if MCPManager is not None:
                try:
                    mcp_config_path = Path(PROJECT_ROOT) / "config" / "mcp_config.json"
                    self.mcp_manager = MCPManager(config_file=mcp_config_path)
                    self.mcp_manager.load_config()
                    self.router.set_mcp_manager(self.mcp_manager)

                    def _auto_connect_mcp():
                        try:
                            self.mcp_manager.connect_all_sync(timeout=120.0)
                            connected = [n for n, c in self.mcp_manager.get_server_configs().items() if c.enabled]
                            if connected:
                                print(f"[MCP] Auto-connected: {', '.join(connected)}")
                        except Exception as e:
                            print(f"[MCP] Auto-connect error: {e}")
                    threading.Thread(target=_auto_connect_mcp, daemon=True).start()
                except Exception as mcp_err:
                    print(f"MCP initialization skipped: {mcp_err}")

            # App state
            self.app_state = AppState(
                session_manager=self.session_manager,
                router=self.router,
                current_provider=active_provider,
                skills_manager=self.skills_manager,
                mcp_manager=self.mcp_manager,
            )

            print(f"Bot initialized: {active_provider} | {len(self.skills_manager.get_skills())} skills")

            # Scheduler
            if SCHEDULER_AVAILABLE:
                try:
                    self.scheduler_manager = create_scheduler_manager(
                        router=self.router, data_dir="data/scheduler",
                    )
                    self.app_state.scheduler_manager = self.scheduler_manager
                    self.router.set_scheduler_manager(self.scheduler_manager)

                    # Register flet channel handler so scheduler can deliver messages
                    async def _flet_send_message(user_id, message, chat_id=None):
                        try:
                            if hasattr(self, 'chat_view'):
                                self.chat_view.inject_scheduled_message(message)
                            return True
                        except Exception as e:
                            print(f"[Scheduler] Flet delivery failed: {e}")
                            return False

                    self.scheduler_manager.register_channel_handler("flet", _flet_send_message)

                    print(f"Scheduler initialized: {len(self.scheduler_manager.tasks)} tasks loaded")
                except Exception as sched_err:
                    print(f"Scheduler initialization skipped: {sched_err}")
                    self.scheduler_manager = None

        except Exception as e:
            import traceback
            print(f"Error initializing bot: {e}")
            traceback.print_exc()

    def _load_saved_api_keys(self):
        """Load all saved API keys from secure storage on startup."""
        for provider, env_var in API_KEY_ENV_MAP.items():
            storage_key = 'api_key_groq' if provider == 'groq-large' else f'api_key_{provider}'
            saved_key = secure_storage.get_token(storage_key)
            if saved_key:
                os.environ[env_var] = saved_key
                if BOT_AVAILABLE and provider in config.LLM_PROVIDERS:
                    config.LLM_PROVIDERS[provider]["api_key"] = saved_key
                print(f"[Startup] Loaded API key for {provider}")

    # -----------------------------------------------------------------
    # View creation
    # -----------------------------------------------------------------

    def _init_views(self):
        """Create all view instances."""
        # Chat view
        self.chat_view = ChatView(
            page=self.page,
            app_state=self.app_state,
            skills_manager=self.skills_manager,
            mcp_manager=self.mcp_manager,
            session_manager=self.session_manager,
            router=self.router,
            secure_storage=secure_storage,
        )
        self._chat_content = self.chat_view.build()

        # Sub-panels for Tools tab
        mcp_panel = MCPPanel(
            page=self.page,
            app_state=self.app_state,
            mcp_manager=self.mcp_manager,
            router=self.router,
        )
        mcp_panel.set_executor(self._executor)

        skills_panel = SkillsPanel(
            page=self.page,
            app_state=self.app_state,
            skills_manager=self.skills_manager,
        )

        clawhub_panel = ClawHubPanel(
            page=self.page,
            app_state=self.app_state,
            router=self.router,
        )

        # Tools view (tabbed: MCP / Skills / ClawHub)
        self.tools_view = ToolsView(
            page=self.page,
            mcp_panel=mcp_panel,
            skills_panel=skills_panel,
            clawhub_panel=clawhub_panel,
        )
        self._tools_content = self.tools_view.build()

        # Settings view
        self.settings_view = SettingsView(
            page=self.page,
            app_state=self.app_state,
            router=self.router,
            session_manager=self.session_manager,
            skills_manager=self.skills_manager,
            secure_storage=secure_storage,
            scheduler_manager=self.scheduler_manager,
        )
        # Cross-view callbacks
        self.settings_view.rebuild_callback = self._rebuild_ui
        self.settings_view._refresh_model_info_callback = (
            lambda: self.chat_view._refresh_model_info()
        )
        self.settings_view.load_saved_api_keys()
        self._settings_content = self.settings_view.build()

        # History view
        self.history_view = HistoryView(
            page=self.page,
            app_state=self.app_state,
            session_manager=self.session_manager,
        )
        self._history_content = self.history_view.build()

        # Admin view
        from skillforge.core.user_permissions import PermissionManager
        perm_mgr = self.router._permission_manager if self.router else PermissionManager()
        self.admin_view = AdminView(
            page=self.page,
            permission_manager=perm_mgr,
            request_manager=self.request_manager,
            identity_resolver=self.identity_resolver,
        )
        self._admin_content = self.admin_view.build()
        self.admin_view.refresh()

    # -----------------------------------------------------------------
    # Navigation — 5 tabs: Chat, Tools, Settings, History, Admin
    # -----------------------------------------------------------------

    def _init_nav(self):
        """Create 5-tab navigation rail."""
        self.nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=80,
            min_extended_width=200,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=icons.CHAT_OUTLINED, selected_icon=icons.CHAT, label="Chat"),
                ft.NavigationRailDestination(
                    icon=icons.BUILD_OUTLINED, selected_icon=icons.BUILD, label="Tools"),
                ft.NavigationRailDestination(
                    icon=icons.SETTINGS_OUTLINED, selected_icon=icons.SETTINGS, label="Settings"),
                ft.NavigationRailDestination(
                    icon=icons.HISTORY_OUTLINED, selected_icon=icons.HISTORY, label="History"),
                ft.NavigationRailDestination(
                    icon=icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                    selected_icon=icons.ADMIN_PANEL_SETTINGS, label="Admin"),
            ],
            on_change=self._on_nav_change,
            bgcolor=AppColors.SURFACE,
            indicator_color=ft.Colors.with_opacity(0.13, AppColors.ACCENT),
            indicator_shape=ft.RoundedRectangleBorder(radius=8),
        )

    def _on_nav_change(self, e):
        """Handle navigation tab change."""
        views = [
            self._chat_content,
            self._tools_content,
            self._settings_content,
            self._history_content,
            self._admin_content,
        ]
        idx = e.control.selected_index
        self.content_area.content = views[idx]
        if idx == 3:  # History tab
            self.history_view.refresh()
        if idx == 4:  # Admin tab
            self.admin_view.refresh()
        self.page.update()

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------

    def _layout(self):
        """Compose page layout."""
        self.content_area = ft.Container(
            content=self._chat_content, expand=True, padding=20,
        )
        self.page.add(
            ft.Row([
                self.nav_rail,
                ft.VerticalDivider(width=1),
                self.content_area,
            ], expand=True)
        )

    def _rebuild_ui(self):
        """Rebuild the full UI (e.g., after theme change)."""
        self.page.controls.clear()
        self._init_views()
        self._init_nav()
        self._layout()
        self.page.update()

    # -----------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------

    def cleanup(self):
        """Clean up resources on shutdown."""
        # Chat view executor
        if hasattr(self, 'chat_view'):
            self.chat_view.cleanup()

        # App executor
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)

        # MCP servers
        if self.mcp_manager:
            try:
                self.mcp_manager.disconnect_all_sync(timeout=5.0)
            except Exception:
                pass

        # WhatsApp webhook / process
        if hasattr(self, 'whatsapp_webhook_server') and self.whatsapp_webhook_server:
            try:
                self.whatsapp_webhook_server.shutdown()
            except Exception:
                pass
        if hasattr(self, 'whatsapp_process') and self.whatsapp_process:
            try:
                self.whatsapp_process.terminate()
                self.whatsapp_process.wait(timeout=3)
            except Exception:
                try:
                    self.whatsapp_process.kill()
                except Exception:
                    pass

        # Scheduler
        if self.scheduler_manager:
            try:
                loop = self._scheduler_loop
                if loop and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        self.scheduler_manager.stop(), loop)
                    future.result(timeout=5)
                    loop.call_soon_threadsafe(loop.stop)
                else:
                    self.scheduler_manager.scheduler.shutdown(wait=False)
            except Exception:
                pass


# =============================================================================
# ENTRY POINT
# =============================================================================

def _auto_start_bots(app):
    """Auto-start configured bots and scheduler."""
    if secure_storage._data.get('telegram_auto_start', False):
        saved_token = secure_storage.get_token('telegram_bot_token')
        if saved_token and TELEGRAM_AVAILABLE:
            print("[Auto-start] Starting Telegram bot...")
            def delayed_start_telegram():
                time.sleep(2)
                try:
                    app.settings_view._start_telegram_bot()
                except Exception as e:
                    print(f"[Auto-start] Telegram failed: {e}")
            threading.Thread(target=delayed_start_telegram, daemon=True).start()

    if secure_storage._data.get('slack_auto_start', False):
        saved_bot_token = secure_storage.get_token('slack_bot_token')
        saved_app_token = secure_storage.get_token('slack_app_token')
        if saved_bot_token and saved_app_token and SLACK_AVAILABLE:
            print("[Auto-start] Starting Slack bot...")
            def delayed_start_slack():
                time.sleep(3)
                try:
                    app.settings_view._start_slack_bot()
                except Exception as e:
                    print(f"[Auto-start] Slack failed: {e}")
            threading.Thread(target=delayed_start_slack, daemon=True).start()

    if secure_storage._data.get('whatsapp_auto_start', False):
        print("[Auto-start] Starting WhatsApp bot...")
        def delayed_start_whatsapp():
            time.sleep(4)
            try:
                app.settings_view._start_whatsapp_service()
                time.sleep(3)
                app.settings_view._start_whatsapp_bot()
            except Exception as e:
                print(f"[Auto-start] WhatsApp failed: {e}")
        threading.Thread(target=delayed_start_whatsapp, daemon=True).start()

    if app.scheduler_manager:
        def run_scheduler_loop():
            time.sleep(5)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                app._scheduler_loop = loop
                if hasattr(app, 'settings_view'):
                    app.settings_view._scheduler_loop = loop
                loop.run_until_complete(app.scheduler_manager.start())
                print("[Auto-start] Scheduler started")
                loop.run_forever()
            except Exception as e:
                print(f"[Auto-start] Scheduler failed: {e}")
        threading.Thread(target=run_scheduler_loop, daemon=True).start()


def main(page: ft.Page):
    """Main entry point for Flet app."""
    # Wire secure storage → AppColors for theme persistence
    AppColors.set_secure_storage(secure_storage)
    AppColors.load_saved_mode()

    page.title = "SkillForge"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = AppColors.BACKGROUND

    def on_authenticated(username):
        """Called after successful login — show the main app."""
        page.controls.clear()
        app = SkillForgeApp(page, admin_username=username)

        def on_window_event(e):
            if e.data == "close":
                app.cleanup()
                page.window_destroy()

        page.window_prevent_close = True
        page.on_window_event = on_window_event
        _auto_start_bots(app)

    # Show login gate
    login_view = LoginView(page, secure_storage, on_authenticated)
    page.add(login_view.build())


if __name__ == "__main__":
    print("Starting SkillForge Flet UI...")
    ft.app(target=main)
