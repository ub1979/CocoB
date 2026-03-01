# =============================================================================
'''
    File Name : llamacpp_provider.py
    
    Description : llama.cpp LLM provider implementation
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
from typing import List, Dict, Generator, Any, Optional

from .base import LLMProvider, LLMConfig
# =============================================================================


# =============================================================================
'''
    LlamaCppProvider : Provider for llama-cpp-python local inference
'''
# =============================================================================
class LlamaCppProvider(LLMProvider):
    """Provider for llama-cpp-python local inference

    This provider loads GGUF models directly without needing a server.
    Useful for fully local, offline inference.

    Config options:
        model: Model name (for display, not used for loading)
        extra:
            model_path: Path to .gguf model file (required)
            n_gpu_layers: Number of layers to offload to GPU (default: 0)
            n_ctx: Context window size (overrides context_window)
            n_batch: Batch size for prompt processing (default: 512)
            verbose: Show llama.cpp output (default: False)
    """

    # =========================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =========================================================================
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._llm = None  # Lazy load

    # =========================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =========================================================================
    def _validate_config(self) -> None:
        """Validate llama-cpp-python specific configuration"""
        model_path = self.config.extra.get("model_path")
        # ==================================
        if not model_path:
            raise ValueError(
                "LlamaCpp requires 'model_path' in extra config. "
                "Set it to the path of your .gguf model file."
            )

    # =========================================================================
    # =========================================================================
    # Function _get_llm -> None to Llama
    # =========================================================================
    # =========================================================================
    def _get_llm(self):
        """Lazy load the Llama model"""
        # ==================================
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError:
                raise ImportError(
                    "llama-cpp-python is not installed. "
                    "Install with: pip install llama-cpp-python"
                )

            extra = self.config.extra
            self._llm = Llama(
                model_path=extra.get("model_path"),
                n_ctx=extra.get("n_ctx", self.config.context_window),
                n_gpu_layers=extra.get("n_gpu_layers", 0),
                n_batch=extra.get("n_batch", 512),
                verbose=extra.get("verbose", False),
            )
        return self._llm

    # =========================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]] to str
    # =========================================================================
    # =========================================================================
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request and return response text

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Returns:
            AI response text
        """
        llm = self._get_llm()

        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=False,
        )

        return response["choices"][0]["message"]["content"]

    # =========================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]] to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Yields:
            Response text chunks as they arrive
        """
        llm = self._get_llm()

        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True,
        )

        for chunk in response:
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            # ==================================
            if content:
                yield content

    # =========================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =========================================================================
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Uses llama.cpp's tokenizer if model is loaded,
        otherwise falls back to rough estimate.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # ==================================
        if self._llm is not None:
            # Use the actual tokenizer
            tokens = self._llm.tokenize(text.encode("utf-8"))
            return len(tokens)
        else:
            # Rough estimate: 1 token ≈ 4 characters
            return len(text) // 4

    # =========================================================================
    # =========================================================================
    # Function unload -> None to None
    # =========================================================================
    # =========================================================================
    def unload(self) -> None:
        """Unload the model to free memory"""
        # ==================================
        if self._llm is not None:
            del self._llm
            self._llm = None


# =============================================================================
# End of File
# =============================================================================
# Project : mr_bot - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
