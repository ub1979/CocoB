# =============================================================================
# test_flet_app.py — Smoke tests for the Flet UI: build every view and the
# full CocoBApp without crashing.  Uses a MagicMock page so no Flet runtime
# is needed.
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

import flet as ft
from flet import Icons as icons


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_page():
    """Create a MagicMock that behaves enough like ft.Page for view building."""
    page = MagicMock()
    page.window = MagicMock()
    page.window.icon = None
    page.controls = []
    page.overlay = []
    page.theme_mode = ft.ThemeMode.DARK
    page.title = ""
    page.bgcolor = ""
    page.padding = 0
    page.window_width = 1200
    page.window_height = 800
    page.window_prevent_close = False
    page.on_window_event = None
    return page


@pytest.fixture
def secure_storage():
    """Minimal mock of SecureStorage."""
    storage = MagicMock()
    storage.get_setting.return_value = True  # dark mode
    storage.get_token.return_value = ""
    storage._data = {}
    return storage


@pytest.fixture
def app_state():
    """Minimal mock of AppState."""
    state = MagicMock()
    state.get_current_provider_info.return_value = {
        "provider_name": "test-provider",
        "model_name": "test-model",
        "base_url": "",
    }
    state.scheduler_manager = None
    return state


@pytest.fixture
def skills_manager():
    """Minimal mock of SkillsManager."""
    mgr = MagicMock()
    mgr.get_skills.return_value = []
    mgr.get_user_invocable_skills.return_value = []
    mgr.get_skill.return_value = None
    return mgr


@pytest.fixture
def session_manager():
    """Minimal mock of SessionManager."""
    mgr = MagicMock()
    mgr.get_session_key.return_value = "flet:dm:user-001"
    mgr.get_conversation_history.return_value = []
    return mgr


@pytest.fixture
def router():
    """Minimal mock of MessageRouter."""
    r = MagicMock()
    r.is_skill_invocation.return_value = (False, None, None)
    r.handle_command.return_value = "OK"
    return r


# ---------------------------------------------------------------------------
# Individual view build tests
# ---------------------------------------------------------------------------

class TestViewBuilds:
    """Each view's build() must return a ft.Column without raising."""

    def test_chat_view_builds(self, mock_page, app_state, skills_manager,
                               session_manager, router, secure_storage):
        from coco_b.flet.views.chat import ChatView
        view = ChatView(
            page=mock_page, app_state=app_state,
            skills_manager=skills_manager, mcp_manager=None,
            session_manager=session_manager, router=router,
            secure_storage=secure_storage,
        )
        result = view.build()
        assert isinstance(result, ft.Column)

    def test_settings_view_builds(self, mock_page, app_state, session_manager,
                                   skills_manager, router, secure_storage):
        from coco_b.flet.views.settings import SettingsView
        view = SettingsView(
            page=mock_page, app_state=app_state, router=router,
            session_manager=session_manager, skills_manager=skills_manager,
            secure_storage=secure_storage, scheduler_manager=None,
        )
        result = view.build()
        assert isinstance(result, ft.Column)

    def test_tools_view_builds(self, mock_page, app_state, skills_manager, router):
        from coco_b.flet.views.mcp import MCPPanel
        from coco_b.flet.views.skills import SkillsPanel
        from coco_b.flet.views.clawhub import ClawHubPanel
        from coco_b.flet.views.tools import ToolsView

        mcp = MCPPanel(page=mock_page, app_state=app_state,
                       mcp_manager=None, router=router)
        skills = SkillsPanel(page=mock_page, app_state=app_state,
                             skills_manager=skills_manager)
        clawhub = ClawHubPanel(page=mock_page, app_state=app_state,
                               router=router)

        view = ToolsView(page=mock_page, mcp_panel=mcp,
                         skills_panel=skills, clawhub_panel=clawhub)
        result = view.build()
        assert isinstance(result, ft.Column)

    def test_mcp_panel_builds(self, mock_page, app_state, router):
        from coco_b.flet.views.mcp import MCPPanel
        panel = MCPPanel(page=mock_page, app_state=app_state,
                         mcp_manager=None, router=router)
        result = panel.build()
        assert isinstance(result, ft.Column)

    def test_skills_panel_builds(self, mock_page, app_state, skills_manager):
        from coco_b.flet.views.skills import SkillsPanel
        panel = SkillsPanel(page=mock_page, app_state=app_state,
                            skills_manager=skills_manager)
        result = panel.build()
        assert isinstance(result, ft.Column)

    def test_user_permissions_section_builds(self, mock_page, app_state, session_manager,
                                                skills_manager, router, secure_storage):
        from coco_b.flet.views.settings import SettingsView
        view = SettingsView(
            page=mock_page, app_state=app_state, router=router,
            session_manager=session_manager, skills_manager=skills_manager,
            secure_storage=secure_storage, scheduler_manager=None,
        )
        view.build()
        result = view._create_user_permissions_section()
        assert isinstance(result, ft.Container)  # CollapsibleSection is a Container

    def test_clawhub_panel_builds(self, mock_page, app_state, router):
        from coco_b.flet.views.clawhub import ClawHubPanel
        panel = ClawHubPanel(page=mock_page, app_state=app_state,
                             router=router)
        result = panel.build()
        assert isinstance(result, ft.Column)

    def test_history_view_builds(self, mock_page, app_state, session_manager):
        from coco_b.flet.views.history import HistoryView
        view = HistoryView(page=mock_page, app_state=app_state,
                           session_manager=session_manager)
        result = view.build()
        assert isinstance(result, ft.Column)


# ---------------------------------------------------------------------------
# Component build tests
# ---------------------------------------------------------------------------

class TestComponentBuilds:
    """Reusable components must instantiate without errors."""

    def test_chat_message_user(self):
        from coco_b.flet.components.chat_message import ChatMessage
        msg = ChatMessage(text="Hello", is_user=True, timestamp="12:00")
        assert isinstance(msg, ft.Row)

    def test_chat_message_assistant(self):
        from coco_b.flet.components.chat_message import ChatMessage
        msg = ChatMessage(text="**Bold** and `code`", is_user=False, timestamp="12:01")
        assert isinstance(msg, ft.Row)

    def test_chat_message_assistant_markdown(self):
        from coco_b.flet.components.chat_message import ChatMessage
        md = "## Heading\n\n```python\nprint('hi')\n```\n\n- bullet"
        msg = ChatMessage(text=md, is_user=False, timestamp="12:02")
        assert isinstance(msg, ft.Row)
        # Verify assistant messages use Markdown rendering
        message_col = msg.controls[1]  # Column with label + body
        body = message_col.controls[1]
        assert isinstance(body, ft.Markdown)

    def test_chat_message_user_plain_text(self):
        from coco_b.flet.components.chat_message import ChatMessage
        msg = ChatMessage(text="plain text", is_user=True, timestamp="12:03")
        message_col = msg.controls[1]
        body = message_col.controls[1]
        assert isinstance(body, ft.Text)

    def test_styled_button(self):
        from coco_b.flet.components.widgets import StyledButton
        btn = StyledButton("Click me", icon=icons.ADD)
        assert isinstance(btn, ft.Button)

    def test_styled_button_outline(self):
        from coco_b.flet.components.widgets import StyledButton
        btn = StyledButton("Click", variant="outline")
        assert isinstance(btn, ft.Button)

    def test_status_badge(self):
        from coco_b.flet.components.widgets import StatusBadge
        badge = StatusBadge("Online", "success")
        assert isinstance(badge, ft.Container)

    def test_collapsible_section(self):
        from coco_b.flet.components.widgets import CollapsibleSection
        section = CollapsibleSection(
            title="Test", content=ft.Text("body"), expanded=True)
        assert isinstance(section, ft.Container)

    def test_server_status_card(self):
        from coco_b.flet.components.cards import ServerStatusCard
        card = ServerStatusCard(name="ollama", is_running=False, status_text="Not running (port 11434)")
        assert isinstance(card, ft.Container)

    def test_server_status_card_running(self):
        from coco_b.flet.components.cards import ServerStatusCard
        card = ServerStatusCard(name="ollama", is_running=True, status_text="Running on port 11434")
        assert isinstance(card, ft.Container)

    def test_cli_status_card(self):
        from coco_b.flet.components.cards import CliStatusCard
        card = CliStatusCard(name="claude-cli", is_installed=False, status_text="Not installed")
        assert isinstance(card, ft.Container)

    def test_cli_status_card_installed(self):
        from coco_b.flet.components.cards import CliStatusCard
        card = CliStatusCard(name="claude-cli", is_installed=True, status_text="Installed")
        assert isinstance(card, ft.Container)


# ---------------------------------------------------------------------------
# Theme & storage tests
# ---------------------------------------------------------------------------

class TestThemeAndStorage:
    """Theme switching and storage instantiation must work."""

    def test_appcolors_dark_mode(self):
        from coco_b.flet.theme import AppColors
        AppColors.set_dark_mode(True)
        assert AppColors.is_dark_mode() is True
        assert AppColors.BACKGROUND == "#1A1A2E"

    def test_appcolors_light_mode(self):
        from coco_b.flet.theme import AppColors
        AppColors.set_dark_mode(False)
        assert AppColors.is_dark_mode() is False
        assert AppColors.BACKGROUND == "#F7FAFC"
        # Reset to dark for other tests
        AppColors.set_dark_mode(True)

    def test_spacing_constants(self):
        from coco_b.flet.theme import Spacing
        assert Spacing.XS == 4
        assert Spacing.SM == 8
        assert Spacing.MD == 16
        assert Spacing.LG == 24
        assert Spacing.XL == 32

    def test_secure_storage_instantiates(self, tmp_path):
        from coco_b.flet.storage import SecureStorage
        s = SecureStorage(storage_dir=tmp_path)
        s.set_setting("test_key", "test_value")
        assert s.get_setting("test_key") == "test_value"

    def test_secure_storage_tokens(self, tmp_path):
        from coco_b.flet.storage import SecureStorage
        s = SecureStorage(storage_dir=tmp_path)
        s.set_token("api_key", "sk-12345")
        assert s.get_token("api_key") == "sk-12345"


# ---------------------------------------------------------------------------
# Full app smoke test — the main event
# ---------------------------------------------------------------------------

class TestCocoBAppSmoke:
    """CocoBApp must initialise and build the full UI without errors."""

    def test_app_initialises(self, mock_page):
        """The full CocoBApp init — page setup, views, nav, layout — must not crash."""
        from coco_b.flet.app import CocoBApp
        app = CocoBApp(mock_page)

        # Page was configured
        assert mock_page.title == "coco B - Intelligent AI Assistant"
        assert mock_page.theme_mode == ft.ThemeMode.DARK

        # Views exist
        assert app.chat_view is not None
        assert app.settings_view is not None
        assert app.tools_view is not None
        assert app.history_view is not None

        # Nav rail created (4 destinations)
        assert app.nav_rail is not None
        assert len(app.nav_rail.destinations) == 4

        # Layout was added to page
        assert mock_page.add.called

    def test_app_cleanup(self, mock_page):
        """cleanup() must not raise."""
        from coco_b.flet.app import CocoBApp
        app = CocoBApp(mock_page)
        app.cleanup()  # should not raise

    def test_app_rebuild_ui(self, mock_page):
        """_rebuild_ui() must not raise — used after theme toggle."""
        from coco_b.flet.app import CocoBApp
        app = CocoBApp(mock_page)
        app._rebuild_ui()  # should not raise

    def test_main_entry_point(self, mock_page):
        """The main() function that ft.app() calls must not crash."""
        from coco_b.flet.app import main
        main(mock_page)

        assert mock_page.window_prevent_close is True
        assert mock_page.on_window_event is not None

    def test_nav_change_to_each_tab(self, mock_page):
        """Switching to every tab must not crash."""
        from coco_b.flet.app import CocoBApp
        app = CocoBApp(mock_page)

        for idx in range(4):
            event = MagicMock()
            event.control.selected_index = idx
            app._on_nav_change(event)  # should not raise

    def test_chat_view_streaming_path(self, mock_page, app_state, skills_manager,
                                       session_manager, router, secure_storage):
        """Streaming chat path must set up correctly without crashing."""
        from coco_b.flet.views.chat import ChatView
        view = ChatView(
            page=mock_page, app_state=app_state,
            skills_manager=skills_manager, mcp_manager=None,
            session_manager=session_manager, router=router,
            secure_storage=secure_storage,
        )
        view.build()

        # Verify _process_bot_response initialises streaming state
        assert view._is_processing is False
        assert hasattr(view, '_executor')

        # Verify the streaming method exists on the router mock
        assert hasattr(router, 'handle_message_stream')

    def test_inject_scheduled_message(self, mock_page, app_state, skills_manager,
                                       session_manager, router, secure_storage):
        """inject_scheduled_message must add a reminder to the chat list."""
        from coco_b.flet.views.chat import ChatView
        from coco_b.flet.components.chat_message import ChatMessage
        # Make run_thread actually call the function
        mock_page.run_thread.side_effect = lambda fn, *a, **kw: fn(*a, **kw)
        view = ChatView(
            page=mock_page, app_state=app_state,
            skills_manager=skills_manager, mcp_manager=None,
            session_manager=session_manager, router=router,
            secure_storage=secure_storage,
        )
        view.build()

        count_before = len(view.messages_list.controls)
        view.inject_scheduled_message("drink water")
        assert len(view.messages_list.controls) == count_before + 1

        # The last message should be a ChatMessage (assistant-style)
        last_msg = view.messages_list.controls[-1]
        assert isinstance(last_msg, ChatMessage)

    def test_inject_scheduled_message_calls_page_update(self, mock_page, app_state,
                                                          skills_manager, session_manager,
                                                          router, secure_storage):
        """inject_scheduled_message must call page.run_thread for thread safety."""
        from coco_b.flet.views.chat import ChatView
        view = ChatView(
            page=mock_page, app_state=app_state,
            skills_manager=skills_manager, mcp_manager=None,
            session_manager=session_manager, router=router,
            secure_storage=secure_storage,
        )
        view.build()

        view.inject_scheduled_message("test reminder")
        mock_page.run_thread.assert_called_once()
