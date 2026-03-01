# =============================================================================
'''
    File Name : __init__.py
    
    Description : UI Module initialization file. Provides Gradio-based user 
                  interface components for mr_bot. Exports main UI components
                  including settings and chat handlers.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - UI Module Exports
# =============================================================================

from .settings import AppState, create_provider_tab
from .chat import chat_with_bot

# =============================================================================
# Module Public API - Exposed Components
# =============================================================================

__all__ = [
    "AppState",
    "create_provider_tab",
    "chat_with_bot",
]

# =============================================================================
# End of File - mr_bot UI Module
# =============================================================================
# Project   : mr_bot - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
