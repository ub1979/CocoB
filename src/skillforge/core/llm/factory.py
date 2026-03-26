# =============================================================================
'''
    File Name : factory.py
    
    Description : LLM Provider Factory for creating provider instances
    
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
from typing import Dict, Type, Any

from .base import LLMProvider, LLMConfig
from .openai_compat import OpenAICompatibleProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .claude_cli_provider import ClaudeCLIProvider
from .gemini_cli_provider import GeminiCLIProvider
# =============================================================================


# =============================================================================
'''
    LLMProviderFactory : Factory for creating LLM providers
'''
# =============================================================================
class LLMProviderFactory:
    """Factory for creating LLM providers

    Usage:
        # From config object
        config = LLMConfig(provider="ollama", model="gemma3:1b")
        provider = LLMProviderFactory.create(config)

        # From dictionary
        provider = LLMProviderFactory.from_dict({
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-..."
        })

        # Register custom provider
        LLMProviderFactory.register("custom", CustomProvider)
    """

    # Map provider names to their implementation classes
    _providers: Dict[str, Type[LLMProvider]] = {
        # OpenAI-compatible providers
        "openai": OpenAICompatibleProvider,
        "ollama": OpenAICompatibleProvider,
        "vllm": OpenAICompatibleProvider,
        "groq": OpenAICompatibleProvider,
        "together": OpenAICompatibleProvider,
        "azure": OpenAICompatibleProvider,
        "kimi": OpenAICompatibleProvider,
        "lmstudio": OpenAICompatibleProvider,
        "mlx": OpenAICompatibleProvider,
        # Anthropic
        "anthropic": AnthropicProvider,
        # Claude Code CLI (uses subscription)
        "claude-cli": ClaudeCLIProvider,
        # Google Gemini
        "gemini": GeminiProvider,
        # Gemini CLI (uses subscription)
        "gemini-cli": GeminiCLIProvider,
    }

    # =============================================================================
    # =========================================================================
    # Function create -> LLMConfig to LLMProvider
    # =========================================================================
    # =============================================================================
    @classmethod
    def create(cls, config: LLMConfig) -> LLMProvider:
        """Create a provider from an LLMConfig object

        Args:
            config: LLMConfig with provider settings

        Returns:
            Configured LLMProvider instance

        Raises:
            ValueError: If provider is unknown
        """
        provider_class = cls._providers.get(config.provider)

        # ==================================
        if not provider_class:
            available = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unknown provider: '{config.provider}'. "
                f"Available providers: {available}"
            )
        # ==================================

        return provider_class(config)
    # =============================================================================

    # =============================================================================
    # =========================================================================
    # Function from_dict -> Dict to LLMProvider
    # =========================================================================
    # =============================================================================
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> LLMProvider:
        """Create a provider from a dictionary configuration

        Args:
            config_dict: Dictionary with provider settings.
                Required keys: 'provider', 'model'
                Optional keys: 'base_url', 'api_key', 'context_window',
                              'max_response_tokens', 'temperature', 'timeout', 'extra'

        Returns:
            Configured LLMProvider instance

        Raises:
            ValueError: If required keys are missing or provider is unknown
        """
        # ==================================
        # Validate required keys
        if "provider" not in config_dict:
            raise ValueError("Config dict must include 'provider' key")
        # ==================================

        # ==================================
        if "model" not in config_dict:
            raise ValueError("Config dict must include 'model' key")
        # ==================================

        # Create LLMConfig from dict
        config = LLMConfig(
            provider=config_dict["provider"],
            model=config_dict["model"],
            base_url=config_dict.get("base_url"),
            api_key=config_dict.get("api_key"),
            auth_method=config_dict.get("auth_method", "api_key"),
            context_window=config_dict.get("context_window", 4096),
            max_response_tokens=config_dict.get("max_response_tokens", 4096),
            temperature=config_dict.get("temperature", 0.7),
            timeout=config_dict.get("timeout", 60),
            extra=config_dict.get("extra", {}),
        )

        return cls.create(config)
    # =============================================================================

    # =============================================================================
    # =========================================================================
    # Function register -> str and Type to None
    # =========================================================================
    # =============================================================================
    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]) -> None:
        """Register a custom provider class

        Args:
            name: Provider name to register
            provider_class: Provider class implementing LLMProvider

        Example:
            class MyCustomProvider(LLMProvider):
                ...

            LLMProviderFactory.register("custom", MyCustomProvider)
            provider = LLMProviderFactory.from_dict({"provider": "custom", "model": "my-model"})
        """
        # ==================================
        if not issubclass(provider_class, LLMProvider):
            raise TypeError(
                f"Provider class must be a subclass of LLMProvider, "
                f"got {provider_class.__name__}"
            )
        # ==================================

        cls._providers[name] = provider_class
    # =============================================================================

    # =============================================================================
    # =========================================================================
    # Function list_providers -> None to list
    # =========================================================================
    # =============================================================================
    @classmethod
    def list_providers(cls) -> list:
        """List all registered provider names

        Returns:
            Sorted list of provider names
        """
        return sorted(cls._providers.keys())
    # =============================================================================

    # =============================================================================
    # =========================================================================
    # Function get_provider_class -> str to Type
    # =========================================================================
    # =============================================================================
    @classmethod
    def get_provider_class(cls, name: str) -> Type[LLMProvider]:
        """Get the provider class for a given name

        Args:
            name: Provider name

        Returns:
            Provider class

        Raises:
            ValueError: If provider is unknown
        """
        provider_class = cls._providers.get(name)

        # ==================================
        if not provider_class:
            available = ", ".join(sorted(cls._providers.keys()))
            raise ValueError(
                f"Unknown provider: '{name}'. "
                f"Available providers: {available}"
            )
        # ==================================

        return provider_class
    # =============================================================================


# =============================================================================
'''
    End of File : factory.py
    
    Part of : SkillForge - Persistent Memory AI Chatbot
    
    Created by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================
