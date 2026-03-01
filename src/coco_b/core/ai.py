# =============================================================================
'''
    File Name : ai.py
    
    Description : Backward-compatible AI client wrapper
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================


# =============================================================================
# =========================================================================
# Import Section - Type hints and LLM provider framework
# =========================================================================
# =============================================================================
from typing import List, Dict, Generator

from coco_b.core.llm import LLMProviderFactory, LLMConfig, LLMProvider


# =============================================================================
'''
    AIClient : Backward-compatible wrapper around new LLM framework
    
    This class wraps the LLMProvider interface to maintain compatibility
    with existing code that uses AIClient. For new code, use 
    LLMProviderFactory directly.
'''
# =============================================================================
class AIClient:
    """Backward-compatible wrapper around new LLM framework

    This class wraps the new LLMProvider interface to maintain compatibility
    with existing code that uses AIClient.

    For new code, use LLMProviderFactory directly.
    """

    # =========================================================================
    # =========================================================================
    # Function __init__ -> str, str to None
    # =========================================================================
    # =========================================================================
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "gemma3:1b"):
        """Initialize AI client

        Args:
            base_url: API endpoint URL
            model: Model name
        """
        # ==================================
        # Detect provider from base URL
        provider = self._detect_provider(base_url)

        # ==================================
        # Create LLM configuration with detected provider
        config = LLMConfig(
            provider=provider,
            model=model,
            base_url=base_url,
            context_window=131072,  # Default for gemma3:1b
            max_response_tokens=4096,
        )

        # ==================================
        # Initialize the LLM provider instance
        self._provider: LLMProvider = LLMProviderFactory.create(config)

        # ==================================
        # Expose attributes for backward compatibility
        self.base_url = base_url
        self.model = model
        self.context_window = config.context_window
        self.max_response_tokens = config.max_response_tokens

    # =========================================================================
    # =========================================================================
    # Function _detect_provider -> str to str
    # =========================================================================
    # =========================================================================
    def _detect_provider(self, base_url: str) -> str:
        """Detect provider type from base URL

        Args:
            base_url: API endpoint URL

        Returns:
            Provider name
        """
        # ==================================
        # Normalize URL for comparison
        url_lower = base_url.lower()

        # ==================================
        # Check for OpenAI provider
        if "openai.com" in url_lower:
            return "openai"
        
        # ==================================
        # Check for Anthropic provider
        elif "anthropic.com" in url_lower:
            return "anthropic"
        
        # ==================================
        # Check for Groq provider
        elif "groq.com" in url_lower:
            return "groq"
        
        # ==================================
        # Check for Together AI provider
        elif "together.xyz" in url_lower:
            return "together"
        
        # ==================================
        # Check for Kimi/Moonshot provider
        elif "moonshot.cn" in url_lower:
            return "kimi"
        
        # ==================================
        # Check for Azure OpenAI provider
        elif "azure.com" in url_lower or "openai.azure.com" in url_lower:
            return "azure"
        
        # ==================================
        # Check for Ollama local provider
        elif ":11434" in url_lower or "ollama" in url_lower:
            return "ollama"
        
        # ==================================
        # Check for vLLM provider
        elif ":8000" in url_lower:
            return "vllm"
        
        # ==================================
        # Default to Ollama for unknown local endpoints
        else:
            return "ollama"

    # =========================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]], bool to str
    # =========================================================================
    # =========================================================================
    def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send chat request to AI

        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream response (uses chat_stream internally)

        Returns:
            AI response text
        """
        # ==================================
        # Handle streaming request by collecting chunks
        if stream:
            chunks = []
            for chunk in self._provider.chat_stream(messages):
                chunks.append(chunk)
            return "".join(chunks)
        
        # ==================================
        # Handle non-streaming request with error handling
        else:
            try:
                return self._provider.chat(messages)
            except Exception as e:
                print(f"AI request error: {e}")
                return f"Error communicating with AI: {str(e)}"

    # =========================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]] to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def chat_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """Stream chat response

        Args:
            messages: List of message dicts with 'role' and 'content'

        Yields:
            Response text chunks
        """
        # ==================================
        # Stream response chunks with error handling
        try:
            yield from self._provider.chat_stream(messages)
        except Exception as e:
            print(f"AI streaming error: {e}")
            yield f"Error communicating with AI: {str(e)}"

    # =========================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =========================================================================
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # ==================================
        # Delegate to provider's token estimation
        return self._provider.estimate_tokens(text)

    # =========================================================================
    # =========================================================================
    # Function check_context_size -> List[Dict[str, str]] to Dict
    # =========================================================================
    # =========================================================================
    def check_context_size(self, messages: List[Dict[str, str]]) -> Dict:
        """Check if messages fit in context window

        Args:
            messages: List of messages to check

        Returns:
            Dict with total_tokens, available_tokens, within_limit, needs_compaction
        """
        # ==================================
        # Delegate to provider's context size checking
        return self._provider.check_context_size(messages)

    # =========================================================================
    # =========================================================================
    # Function summarize_conversation -> List[Dict[str, str]] to str
    # =========================================================================
    # =========================================================================
    def summarize_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Create a summary of conversation for compaction

        Args:
            messages: List of messages to summarize

        Returns:
            Summary text
        """
        # ==================================
        # Delegate to provider's summarization
        return self._provider.summarize_conversation(messages)

    # =========================================================================
    # =========================================================================
    # Function provider -> property returning LLMProvider
    # =========================================================================
    # =========================================================================
    @property
    def provider(self) -> LLMProvider:
        """Get the underlying LLM provider

        Returns:
            The LLMProvider instance
        """
        # ==================================
        # Return the internal provider instance
        return self._provider


# =============================================================================
# =========================================================================
# Main Execution Block - Example usage and testing
# =========================================================================
# =============================================================================
# ==================================
# Example usage demonstration
if __name__ == "__main__":
    ai = AIClient()

    # ==================================
    # Test simple chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! What's 2+2?"}
    ]

    response = ai.chat(messages)
    print(f"AI Response: {response}")

    # ==================================
    # Test context checking
    long_messages = [
        {"role": "user", "content": "Hello" * 1000},
        {"role": "assistant", "content": "Hi there!"}
    ]

    context_check = ai.check_context_size(long_messages)
    print(f"\nContext check: {context_check}")


# =============================================================================
'''
    End of File : ai.py
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================
