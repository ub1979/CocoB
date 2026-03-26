# =============================================================================
'''
    File Name : __init__.py
    
    Description : OAuth authentication module for LLM providers.
                  Supports subscription-based authentication for Google Gemini
                  (Google One AI Premium subscribers) and Anthropic Claude
                  (Claude Pro/Max subscribers).
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

# Provider modules
from . import gemini
from . import anthropic

# Credential management
from .credentials import (
    save_credentials,
    load_credentials,
    delete_credentials,
    get_valid_token,
    is_logged_in,
    get_token_info,
    CREDENTIALS_FILE,
    CREDENTIALS_DIR,
)

# Base utilities (for custom implementations)
from .base import (
    OAuthCallbackHandler,
    generate_pkce,
    run_oauth_flow,
    refresh_access_token,
)

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Provider modules
    "gemini",
    "anthropic",
    # Credential management
    "save_credentials",
    "load_credentials",
    "delete_credentials",
    "get_valid_token",
    "is_logged_in",
    "get_token_info",
    "CREDENTIALS_FILE",
    "CREDENTIALS_DIR",
    # Base utilities
    "OAuthCallbackHandler",
    "generate_pkce",
    "run_oauth_flow",
    "refresh_access_token",
]

# =============================================================================
# End of File - SkillForge OAuth Authentication Module
# =============================================================================
