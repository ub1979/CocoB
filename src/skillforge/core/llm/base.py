# =============================================================================
'''
    File Name : base.py
    
    Description : Base classes for LLM providers (ABC and Config)
    
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
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Generator, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.image_handler import Attachment
# =============================================================================


# =============================================================================
'''
    LLMConfig : Configuration dataclass for LLM providers
'''
# =============================================================================
@dataclass
class LLMConfig:
    """Configuration for an LLM provider"""
    provider: str                          # "openai", "ollama", "anthropic", "gemini", etc.
    model: str                             # Model name/identifier
    base_url: Optional[str] = None         # API endpoint
    api_key: Optional[str] = None          # API key (if required)
    auth_method: str = "api_key"           # "api_key", "cli", or "env"
    context_window: int = 4096             # Max context tokens
    max_response_tokens: int = 4096        # Max response tokens
    temperature: float = 0.7               # Sampling temperature
    timeout: int = 60                      # Request timeout seconds
    extra: Dict[str, Any] = field(default_factory=dict)  # Provider-specific options


# =============================================================================
'''
    LLMProvider : Abstract base class defining the provider interface
'''
# =============================================================================
class LLMProvider(ABC):
    """Abstract base class for LLM providers

    All LLM providers must implement this interface to be used
    with the LLMProviderFactory and the rest of the bot framework.
    """

    # =============================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =============================================================================
    def __init__(self, config: LLMConfig):
        self.config = config
        self._validate_config()

    # =============================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =============================================================================
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    # =============================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]] to str
    # =========================================================================
    # =============================================================================
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request and return response text

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional provider-specific options

        Returns:
            AI response text
        """
        pass

    # =============================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]] to Generator[str, None, None]
    # =========================================================================
    # =============================================================================
    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional provider-specific options

        Yields:
            Response text chunks as they arrive
        """
        pass

    # =============================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =============================================================================
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        pass

    # =============================================================================
    # =========================================================================
    # Function check_context_size -> List[Dict[str, str]] to Dict[str, Any]
    # =========================================================================
    # =============================================================================
    def check_context_size(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Check if messages fit in context window

        Args:
            messages: List of messages to check

        Returns:
            Dict with keys:
                - total_tokens: Estimated total tokens
                - available_tokens: Tokens available for context
                - within_limit: Whether messages fit
                - needs_compaction: Whether context should be compacted
        """
        total = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        reserve = 8000  # Reserve for system prompt and response
        available = self.config.context_window - reserve

        # ==================================
        return {
            "total_tokens": total,
            "available_tokens": available,
            "within_limit": total < available,
            "needs_compaction": total > (available * 0.8)
        }

    # =============================================================================
    # =========================================================================
    # Function summarize_conversation -> List[Dict[str, str]] to str
    # =========================================================================
    # =============================================================================
    def summarize_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Summarize conversation for compaction

        Default implementation uses self.chat() to generate summary.
        Override in subclasses for provider-specific implementations.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary text
        """
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])

        summarize_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversations concisely. "
                          "Capture key points, topics discussed, and important information."
            },
            {
                "role": "user",
                "content": f"Please summarize this conversation:\n\n{conversation_text}\n\n"
                          "Provide a concise summary that captures the main topics and important details."
            }
        ]

        return self.chat(summarize_messages)

    # =============================================================================
    # =========================================================================
    # Function model_name -> None to str (property getter)
    # =========================================================================
    # =============================================================================
    @property
    def model_name(self) -> str:
        """Get the model name"""
        return self.config.model

    # =============================================================================
    # =========================================================================
    # Function provider_name -> None to str (property getter)
    # =========================================================================
    # =============================================================================
    @property
    def provider_name(self) -> str:
        """Get the provider name"""
        return self.config.provider

    # =============================================================================
    # =========================================================================
    # Function supports_vision -> None to bool (property getter)
    # =========================================================================
    # =============================================================================
    @property
    def supports_vision(self) -> bool:
        """Whether this provider supports image/vision input.

        Override in subclasses that support vision.

        Returns:
            False by default — subclasses override to True.
        """
        return False

    # =============================================================================
    # =========================================================================
    # Function format_vision_messages -> List, List to List
    # =========================================================================
    # =============================================================================
    def format_vision_messages(
        self,
        messages: List[Dict[str, Any]],
        attachments: List[Attachment],
    ) -> List[Dict[str, Any]]:
        """Format messages with image attachments for this provider's API.

        Default implementation: no-op (returns messages unchanged).
        Vision-capable providers MUST override this.

        Args:
            messages: Standard message list (role/content dicts).
            attachments: List of Attachment objects to include with the
                         latest user message.

        Returns:
            Modified messages list with provider-specific image format.
        """
        return messages


# =============================================================================
# End of File
# =============================================================================
# Project : SkillForge - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
