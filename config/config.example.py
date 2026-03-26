# =============================================================================
'''
    File Name : config.example.py
    
    Description : Configuration file template for the SkillForge chatbot.
                  Copy this file to config.py and fill in your credentials.
                  Contains settings for MS Teams, AI provider, server,
                  session storage, and context management.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# MS Teams Bot Configuration Section
# =============================================================================

# ==================================
# Microsoft Teams App Registration Credentials
# Get these from Azure Portal -> App Registrations
MSTEAMS_APP_ID = "YOUR_APP_ID_HERE"
MSTEAMS_APP_PASSWORD = "YOUR_APP_PASSWORD_HERE"


# =============================================================================
# AI Configuration Section
# =============================================================================

# ==================================
# Ollama Local AI Server Settings
# Default endpoint for local Ollama installation
AI_BASE_URL = "http://localhost:11434/v1"  # Ollama endpoint

# ==================================
# AI Model Selection
# Default model to use for responses
AI_MODEL = "gemma3:1b"


# =============================================================================
# Server Configuration Section
# =============================================================================

# ==================================
# Network Binding Settings
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 3978       # Default bot service port


# =============================================================================
# Session Configuration Section
# =============================================================================

# ==================================
# Session Data Storage Paths
# Directory for conversation session files
SESSION_DATA_DIR = "data/sessions"

# ==================================
# Memory Data Storage Paths
# Directory for persistent memory storage
MEMORY_DATA_DIR = "data/memory"


# =============================================================================
# Context Management Section
# =============================================================================

# ==================================
# Token Limits for Context Window
# Maximum tokens to maintain in conversation context
MAX_CONTEXT_TOKENS = 100000  # Leave room for response

# ==================================
# Compaction Threshold
# Compact conversation history when reaching this percentage
COMPACTION_THRESHOLD = 0.8  # Compact at 80% full


# =============================================================================
'''
    End of File : config.example.py
    
    Setup Instructions:
    1. Copy this file to config.py
    2. Fill in your MS Teams credentials
    3. Adjust AI settings as needed
    4. Run the bot
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
