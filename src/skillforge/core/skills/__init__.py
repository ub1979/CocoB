# =============================================================================
'''
    File Name : __init__.py
    
    Description : Skills Framework module initialization. Provides the ability 
                  to load, manage, and use skills - reusable prompt templates 
                  that teach the AI how to perform specific tasks.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Skills Framework Components
# =============================================================================

from .loader import Skill, parse_skill_file, parse_skill_content, skill_to_markdown
from .manager import SkillsManager

# =============================================================================
# Public API - Exported Symbols
# =============================================================================

__all__ = [
    "Skill",
    "SkillsManager",
    "parse_skill_file",
    "parse_skill_content",
    "skill_to_markdown",
]

# =============================================================================
'''
    End of File : __init__.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    License : Open Source - Safe Open Community Project
'''
# =============================================================================
