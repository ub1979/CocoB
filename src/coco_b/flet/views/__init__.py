"""Flet UI views."""

from coco_b.flet.views.chat import ChatView
from coco_b.flet.views.settings import SettingsView
from coco_b.flet.views.tools import ToolsView
from coco_b.flet.views.mcp import MCPPanel
from coco_b.flet.views.skills import SkillsPanel
from coco_b.flet.views.clawhub import ClawHubPanel
from coco_b.flet.views.history import HistoryView

__all__ = [
    "ChatView",
    "SettingsView",
    "ToolsView",
    "MCPPanel",
    "SkillsPanel",
    "ClawHubPanel",
    "HistoryView",
]
