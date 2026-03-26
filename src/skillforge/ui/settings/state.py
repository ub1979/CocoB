# =============================================================================
'''
    File Name : state.py
    
    Description : UI State Management module. Handles runtime configuration
                  and provider switching for the SkillForge application. Manages
                  the shared application state including session management,
                  message routing, and LLM provider configuration.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Core Dependencies
# =============================================================================

from dataclasses import dataclass, field
from typing import Optional, Callable, Tuple, TYPE_CHECKING
from skillforge.core.llm import LLMProviderFactory, LLMProvider
from skillforge.core.router import MessageRouter
from skillforge.core.sessions import SessionManager
import config

# =============================================================================
# TYPE_CHECKING Imports - Avoid Circular Dependencies
# =============================================================================

if TYPE_CHECKING:
    from skillforge.core.skills import SkillsManager
    from skillforge.core.mcp_client import MCPManager
    from skillforge.core.scheduler import SchedulerManager


# =============================================================================
'''
    AppState : Shared application state dataclass for UI components.
               Manages session manager, message router, current provider,
               and skills manager integration.
'''
# =============================================================================

@dataclass
class AppState:
    """Shared application state for UI components"""

    # ==================================
    # Core Application Components
    # ==================================
    session_manager: SessionManager
    router: MessageRouter
    current_provider: str = "ollama"

    # ==================================
    # Callbacks for UI Updates
    # ==================================
    on_provider_change: Optional[Callable[[str, LLMProvider], None]] = None

    # ==================================
    # Skills Manager Integration
    # ==================================
    skills_manager: Optional["SkillsManager"] = None

    # ==================================
    # MCP Manager Integration
    # ==================================
    mcp_manager: Optional["MCPManager"] = None

    # ==================================
    # Scheduler Manager Integration
    # ==================================
    scheduler_manager: Optional["SchedulerManager"] = None

    # =============================================================================
    # =========================================================================
    # Function __post_init -> None to None (Post-initialization hook)
    # =========================================================================
    # =============================================================================

    def __post_init__(self):
        # ==================================
        # Ensure router's personality manager has access to skills
        # ==================================
        if self.skills_manager and hasattr(self.router, 'personality'):
            self.router.personality.skills_manager = self.skills_manager

    # =============================================================================
    # =========================================================================
    # Function switch_provider -> str, Optional[dict] to Tuple[bool, str]
    # =========================================================================
    # =============================================================================

    def switch_provider(
        self,
        provider_name: str,
        custom_config: Optional[dict] = None
    ) -> Tuple[bool, str]:
        """
        Switch to a different LLM provider at runtime.

        Args:
            provider_name: Name of the provider to switch to
            custom_config: Optional custom configuration dict

        Returns:
            Tuple of (success, message)
        """
        try:
            # ==================================
            # Get config (custom or from LLM_PROVIDERS)
            # ==================================
            if custom_config:
                llm_config = custom_config
            elif provider_name in config.LLM_PROVIDERS:
                llm_config = config.LLM_PROVIDERS[provider_name]
            else:
                return False, f"Unknown provider: {provider_name}"

            # ==================================
            # Create new provider instance
            # ==================================
            new_provider = LLMProviderFactory.from_dict(llm_config)

            # ==================================
            # Update router's LLM and current provider
            # ==================================
            self.router.llm = new_provider
            self.current_provider = provider_name

            # ==================================
            # Save provider to secure storage (for Telegram sync)
            # ==================================
            try:
                from skillforge import secure_storage
                secure_storage.set_setting('current_provider', provider_name)
            except:
                pass  # Non-critical

            # ==================================
            # Trigger UI callback if set
            # ==================================
            if self.on_provider_change:
                self.on_provider_change(provider_name, new_provider)

            return True, f"Switched to {new_provider.provider_name}: {new_provider.model_name}"

        except Exception as e:
            return False, f"Failed to switch: {str(e)}"

    # =============================================================================
    # =========================================================================
    # Function get_current_provider_info -> None to dict
    # =========================================================================
    # =============================================================================

    def get_current_provider_info(self) -> dict:
        """Get information about the current provider"""
        return {
            "provider_name": self.router.llm.provider_name,
            "model_name": self.router.llm.model_name,
            "base_url": getattr(self.router.llm.config, 'base_url', None),
        }

    # =============================================================================
    # =========================================================================
    # Function save_as_default -> str to bool
    # =========================================================================
    # =============================================================================

    def save_as_default(self, provider_name: str) -> bool:
        """
        Save current provider as default in config.

        Note: This updates runtime config only.
        For persistence, would need to write to config file.

        Args:
            provider_name: Provider name to set as default

        Returns:
            True if successful
        """
        # ==================================
        # Update runtime config
        # ==================================
        config.LLM_PROVIDER = provider_name
        return True

    # =============================================================================
    # =========================================================================
    # Function get_available_providers -> None to list
    # =========================================================================
    # =============================================================================

    def get_available_providers(self) -> list:
        """Get list of configured provider names"""
        return list(config.LLM_PROVIDERS.keys())


# =============================================================================
# End of File - SkillForge UI State Management
# =============================================================================
# Project   : SkillForge - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
