# =============================================================================
'''
    File Name : __init__.py
    
    Description : LLM Provider Framework package initialization
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# LLM Provider Framework
#
# A modular framework for integrating multiple LLM providers.
#
# Supported providers:
# - OpenAI (and compatible APIs: Ollama, vLLM, Groq, Together AI, Azure, Kimi)
# - Anthropic Claude
# - Google Gemini (API key + Vertex AI/gcloud auth)
#
# Usage:
#     from coco_b.core.llm import LLMProviderFactory, LLMConfig
#
#     # Quick setup from dict
#     provider = LLMProviderFactory.from_dict({
#         "provider": "ollama",
#         "model": "gemma3:1b",
#     })
#
#     # Send chat request
#     response = provider.chat([
#         {"role": "user", "content": "Hello!"}
#     ])
#
#     # Stream response
#     for chunk in provider.chat_stream([
#         {"role": "user", "content": "Tell me a story"}
#     ]):
#         print(chunk, end="", flush=True)
#
#     # Use Gemini with gcloud auth
#     provider = LLMProviderFactory.from_dict({
#         "provider": "gemini",
#         "model": "gemini-1.5-pro",
#         "auth_method": "cli",  # Uses gcloud auth
#         "extra": {"gcp_project": "my-project"},
#     })
# =============================================================================

# =============================================================================
# Import Section - Core LLM Provider Components
# =============================================================================

# Import base classes for LLM provider abstraction
from .base import LLMProvider, LLMConfig

# Import OpenAI-compatible provider (supports Ollama, vLLM, Groq, Together AI, Azure, Kimi)
from .openai_compat import OpenAICompatibleProvider

# Import Anthropic Claude provider
from .anthropic_provider import AnthropicProvider

# Import Google Gemini provider (supports API key and gcloud auth)
from .gemini_provider import GeminiProvider

# Import factory for creating provider instances
from .factory import LLMProviderFactory

# =============================================================================
# Public API - Exposed symbols for external use
# =============================================================================

__all__ = [
    "LLMProvider",
    "LLMConfig",
    "OpenAICompatibleProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "LLMProviderFactory",
]

# =============================================================================
# End of File
# =============================================================================
# Project: mr_bot - Persistent Memory AI Chatbot
# License: Open Source - Safe Open Community Project
# Mission: Making AI Useful for Everyone
# =============================================================================
