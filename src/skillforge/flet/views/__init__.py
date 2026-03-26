"""Flet UI views."""

from skillforge.flet.views.chat import ChatView
from skillforge.flet.views.settings import SettingsView
from skillforge.flet.views.tools import ToolsView
from skillforge.flet.views.mcp import MCPPanel
from skillforge.flet.views.skills import SkillsPanel
from skillforge.flet.views.clawhub import ClawHubPanel
from skillforge.flet.views.history import HistoryView

__all__ = [
    "ChatView",
    "SettingsView",
    "ToolsView",
    "MCPPanel",
    "SkillsPanel",
    "ClawHubPanel",
    "HistoryView",
]
