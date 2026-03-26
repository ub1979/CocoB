# =============================================================================
'''
    File Name : __init__.py
    
    Description : Settings Module initialization file. Provides configuration
                  UI components for LLM provider selection, connection testing,
                  model discovery for local providers, and future MCP tools,
                  Skills, and Memory settings.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Settings Submodules
# =============================================================================

from .state import AppState
from .provider_tab import create_provider_tab
from .mcp_tab import create_mcp_tab
from .scheduler_tab import create_scheduler_tab
from .connection import test_provider_connection
from .models import fetch_models_for_provider, fetch_ollama_models

# =============================================================================
# Module Public API - Exposed Components
# =============================================================================

__all__ = [
    "AppState",
    "create_provider_tab",
    "create_mcp_tab",
    "create_scheduler_tab",
    "test_provider_connection",
    "fetch_models_for_provider",
    "fetch_ollama_models",
]

# =============================================================================
# End of File - SkillForge Settings Module
# =============================================================================
# Project   : SkillForge - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
