# =============================================================================
# test_imports.py — Verify all core modules import without errors
# =============================================================================

import pytest


class TestCoreImports:
    """Every core module should import cleanly."""

    def test_import_sessions(self):
        from coco_b.core.sessions import SessionManager

    def test_import_llm(self):
        from coco_b.core.llm import LLMProviderFactory

    def test_import_router(self):
        from coco_b.core.router import MessageRouter

    def test_import_personality(self):
        from coco_b.core.personality import PersonalityManager

    def test_import_schedule_handler(self):
        from coco_b.core.schedule_handler import ScheduleCommandHandler

    def test_import_todo_handler(self):
        from coco_b.core.todo_handler import TodoCommandHandler

    def test_import_skill_creator_handler(self):
        from coco_b.core.skill_creator_handler import SkillCreatorHandler

    def test_import_skills_manager(self):
        from coco_b.core.skills.manager import SkillsManager

    def test_import_skills_loader(self):
        from coco_b.core.skills.loader import Skill, parse_skill_file

    def test_import_memory(self):
        from coco_b.core.memory import SQLiteMemory

    def test_import_mcp_tools(self):
        from coco_b.core.mcp_tools import MCPToolHandler

    def test_import_skill_executor(self):
        from coco_b.core.skill_executor import SkillExecutor

    def test_import_file_access(self):
        from coco_b.core.file_access import FileAccessManager

    def test_import_scheduler(self):
        from coco_b.core.scheduler import SchedulerManager

    def test_import_auth_manager(self):
        from coco_b.core.auth_manager import AuthManager

    def test_import_background_tasks(self):
        from coco_b.core.background_tasks import BackgroundTaskRunner

    def test_import_heartbeat_manager(self):
        from coco_b.core.heartbeat_manager import HeartbeatManager

    def test_import_pattern_detector(self):
        from coco_b.core.pattern_detector import PatternDetector

    def test_import_webhook_security(self):
        from coco_b.core.webhook_security import WebhookSecurityError

    def test_import_mcp_manager(self):
        from coco_b.core.mcp_manager import MCPManager

    def test_import_clawhub(self):
        from coco_b.core.clawhub import ClawHubManager


class TestFletImports:
    """Flet UI package modules should import cleanly."""

    def test_import_flet_theme(self):
        from coco_b.flet.theme import AppColors, Spacing

    def test_import_flet_storage(self):
        from coco_b.flet.storage import SecureStorage, secure_storage

    def test_import_flet_chat_message(self):
        from coco_b.flet.components.chat_message import ChatMessage

    def test_import_flet_widgets(self):
        from coco_b.flet.components.widgets import CollapsibleSection, StatusBadge, StyledButton

    def test_import_flet_cards(self):
        from coco_b.flet.components.cards import ServerStatusCard, CliStatusCard

    def test_import_flet_chat_view(self):
        from coco_b.flet.views.chat import ChatView

    def test_import_flet_settings_view(self):
        from coco_b.flet.views.settings import SettingsView

    def test_import_flet_tools_view(self):
        from coco_b.flet.views.tools import ToolsView

    def test_import_flet_mcp_panel(self):
        from coco_b.flet.views.mcp import MCPPanel

    def test_import_flet_skills_panel(self):
        from coco_b.flet.views.skills import SkillsPanel

    def test_import_flet_clawhub_panel(self):
        from coco_b.flet.views.clawhub import ClawHubPanel

    def test_import_flet_history_view(self):
        from coco_b.flet.views.history import HistoryView

    def test_import_flet_app(self):
        from coco_b.flet.app import main, CocoBApp

    def test_import_flet_package(self):
        from coco_b.flet import main
