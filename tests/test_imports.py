# =============================================================================
# test_imports.py — Verify all core modules import without errors
# =============================================================================

import pytest


class TestCoreImports:
    """Every core module should import cleanly."""

    def test_import_sessions(self):
        from skillforge.core.sessions import SessionManager

    def test_import_llm(self):
        from skillforge.core.llm import LLMProviderFactory

    def test_import_router(self):
        from skillforge.core.router import MessageRouter

    def test_import_personality(self):
        from skillforge.core.personality import PersonalityManager

    def test_import_schedule_handler(self):
        from skillforge.core.schedule_handler import ScheduleCommandHandler

    def test_import_todo_handler(self):
        from skillforge.core.todo_handler import TodoCommandHandler

    def test_import_skill_creator_handler(self):
        from skillforge.core.skill_creator_handler import SkillCreatorHandler

    def test_import_skills_manager(self):
        from skillforge.core.skills.manager import SkillsManager

    def test_import_skills_loader(self):
        from skillforge.core.skills.loader import Skill, parse_skill_file

    def test_import_memory(self):
        from skillforge.core.memory import SQLiteMemory

    def test_import_mcp_tools(self):
        from skillforge.core.mcp_tools import MCPToolHandler

    def test_import_skill_executor(self):
        from skillforge.core.skill_executor import SkillExecutor

    def test_import_file_access(self):
        from skillforge.core.file_access import FileAccessManager

    def test_import_scheduler(self):
        from skillforge.core.scheduler import SchedulerManager

    def test_import_auth_manager(self):
        from skillforge.core.auth_manager import AuthManager

    def test_import_background_tasks(self):
        from skillforge.core.background_tasks import BackgroundTaskRunner

    def test_import_heartbeat_manager(self):
        from skillforge.core.heartbeat_manager import HeartbeatManager

    def test_import_pattern_detector(self):
        from skillforge.core.pattern_detector import PatternDetector

    def test_import_webhook_security(self):
        from skillforge.core.webhook_security import WebhookSecurityError

    def test_import_mcp_manager(self):
        from skillforge.core.mcp_manager import MCPManager

    def test_import_clawhub(self):
        from skillforge.core.clawhub import ClawHubManager


class TestFletImports:
    """Flet UI package modules should import cleanly."""

    def test_import_flet_theme(self):
        from skillforge.flet.theme import AppColors, Spacing

    def test_import_flet_storage(self):
        from skillforge.flet.storage import SecureStorage, secure_storage

    def test_import_flet_chat_message(self):
        from skillforge.flet.components.chat_message import ChatMessage

    def test_import_flet_widgets(self):
        from skillforge.flet.components.widgets import CollapsibleSection, StatusBadge, StyledButton

    def test_import_flet_cards(self):
        from skillforge.flet.components.cards import ServerStatusCard, CliStatusCard

    def test_import_flet_chat_view(self):
        from skillforge.flet.views.chat import ChatView

    def test_import_flet_settings_view(self):
        from skillforge.flet.views.settings import SettingsView

    def test_import_flet_tools_view(self):
        from skillforge.flet.views.tools import ToolsView

    def test_import_flet_mcp_panel(self):
        from skillforge.flet.views.mcp import MCPPanel

    def test_import_flet_skills_panel(self):
        from skillforge.flet.views.skills import SkillsPanel

    def test_import_flet_clawhub_panel(self):
        from skillforge.flet.views.clawhub import ClawHubPanel

    def test_import_flet_history_view(self):
        from skillforge.flet.views.history import HistoryView

    def test_import_flet_app(self):
        from skillforge.flet.app import main, SkillForgeApp

    def test_import_flet_package(self):
        from skillforge.flet import main
