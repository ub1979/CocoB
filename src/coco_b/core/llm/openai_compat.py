# =============================================================================
'''
    File Name : openai_compat.py
    
    Description : OpenAI-compatible LLM provider implementation
    
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
import json
import re
from typing import List, Dict, Generator, Any, Optional

import requests

from .base import LLMProvider, LLMConfig

# Pattern to extract fenced code blocks from reasoning text
_CODE_BLOCK_RE = re.compile(r'```\w+\s*\n.*?```', re.DOTALL)
# =============================================================================


# =============================================================================
'''
    OpenAICompatibleProvider : Provider for OpenAI-compatible APIs
    
    This provider works with any API that follows the OpenAI chat completions
    format, including Ollama, vLLM, Groq, Together AI, Azure OpenAI, and Kimi.
'''
# =============================================================================
class OpenAICompatibleProvider(LLMProvider):

    # Provider-specific defaults
    PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "requires_key": True,
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "requires_key": False,
        },
        "vllm": {
            "base_url": "http://localhost:8000/v1",
            "requires_key": False,
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "requires_key": True,
        },
        "together": {
            "base_url": "https://api.together.xyz/v1",
            "requires_key": True,
        },
        "azure": {
            "base_url": None,  # Must be provided
            "requires_key": True,
        },
        "kimi": {
            "base_url": "https://api.moonshot.cn/v1",
            "requires_key": True,
        },
        "lmstudio": {
            "base_url": "http://localhost:1234/v1",
            "requires_key": False,
        },
        "mlx": {
            "base_url": "http://localhost:8080/v1",
            "requires_key": False,
        },
    }

    # =============================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =============================================================================
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._setup_defaults()

    # =============================================================================
    # =========================================================================
    # Function _setup_defaults -> None to None
    # =========================================================================
    # =============================================================================
    def _setup_defaults(self) -> None:
        """Apply provider-specific defaults if not specified"""
        defaults = self.PROVIDER_DEFAULTS.get(self.config.provider, {})

        # ==================================
        if self.config.base_url is None and defaults.get("base_url"):
            self.config.base_url = defaults["base_url"]

    # =============================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =============================================================================
    def _validate_config(self) -> None:
        """Validate provider-specific configuration"""
        defaults = self.PROVIDER_DEFAULTS.get(self.config.provider, {})

        # ==================================
        if defaults.get("requires_key") and not self.config.api_key:
            # Azure supports CLI auth via az login
            # ==================================
            if self.config.provider == "azure" and self.config.auth_method == "cli":
                pass  # CLI auth doesn't need API key
            else:
                raise ValueError(
                    f"API key is required for provider '{self.config.provider}'. "
                    f"Set it via the 'api_key' config option or environment variable."
                )

        # ==================================
        if self.config.base_url is None:
            # ==================================
            if self.config.provider == "azure":
                raise ValueError(
                    "Azure OpenAI requires a base_url. "
                    "Set it to your Azure endpoint (e.g., 'https://your-resource.openai.azure.com/openai/deployments/your-deployment')"
                )
            # Use a generic default for unknown providers
            self.config.base_url = "http://localhost:8000/v1"

    # =============================================================================
    # =========================================================================
    # Function _get_headers -> None to Dict[str, str]
    # =========================================================================
    # =============================================================================
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers"""
        headers = {
            "Content-Type": "application/json",
        }

        # Handle Azure AD authentication
        # ==================================
        if self.config.provider == "azure" and self.config.auth_method == "cli":
            # Use Azure AD token via DefaultAzureCredential
            try:
                from azure.identity import DefaultAzureCredential

                credential = DefaultAzureCredential()
                token = credential.get_token("https://cognitiveservices.azure.com/.default")
                headers["Authorization"] = f"Bearer {token.token}"
            except ImportError:
                raise ImportError(
                    "azure-identity package not installed. Run: "
                    "pip install azure-identity"
                )
            except Exception as e:
                raise ConnectionError(
                    f"Failed to get Azure AD token. Run 'az login' first. Error: {e}"
                )
        elif self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

            # Provider-specific headers
            # ==================================
            if self.config.provider == "azure":
                headers["api-key"] = self.config.api_key

        return headers

    # =============================================================================
    # =========================================================================
    # Function _build_payload -> List[Dict[str, str]], bool, **kwargs to Dict[str, Any]
    # =========================================================================
    # =============================================================================
    def _build_payload(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Build request payload"""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": kwargs.get("max_tokens", self.config.max_response_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        # Add any extra parameters from config
        # ==================================
        if self.config.extra:
            for key, value in self.config.extra.items():
                # ==================================
                if key not in payload:
                    payload[key] = value

        # Add any kwargs that override
        for key, value in kwargs.items():
            # ==================================
            if key not in ["max_tokens", "temperature"]:
                payload[key] = value

        return payload

    # =============================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]], **kwargs to str
    # =========================================================================
    # =============================================================================
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request and return response text

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Returns:
            AI response text
        """
        url = f"{self.config.base_url}/chat/completions"
        headers = self._get_headers()
        payload = self._build_payload(messages, stream=False, **kwargs)

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()

            # Extract response text
            # ==================================
            if "choices" in data and len(data["choices"]) > 0:
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                # Thinking models (Gemini Flash, etc.) may put the answer
                # in "reasoning" when "content" is empty.
                # Extract code blocks from reasoning so handlers (todo,
                # schedule, web_search, etc.) can still parse them.
                if not content.strip() and msg.get("reasoning"):
                    reasoning = msg["reasoning"]
                    code_blocks = _CODE_BLOCK_RE.findall(reasoning)
                    if code_blocks:
                        # Return extracted code blocks — handlers need these
                        content = "\n\n".join(code_blocks)
                    else:
                        content = reasoning
                return content

            return "I apologize, but I couldn't generate a response."

        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.config.timeout} seconds")
        except requests.exceptions.HTTPError as e:
            # ==================================
            # Provide helpful error messages for common issues
            # ==================================
            if e.response.status_code == 404:
                error_msg = f"Error communicating with {self.config.provider}: Endpoint not found (404)"
                # ==================================
                # Add MLX-specific troubleshooting
                # ==================================
                if self.config.provider == "mlx":
                    error_msg += (
                        "\n\nMLX Troubleshooting:"
                        "\n1. Ensure mlx-lm is installed: pip install mlx-lm"
                        "\n2. Start the server: python -m mlx_lm.server --model <model> --port 8080"
                        "\n3. Check the server is running: curl http://localhost:8080/v1/models"
                    )
                raise ConnectionError(error_msg)
            raise ConnectionError(f"Error communicating with {self.config.provider}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error communicating with {self.config.provider}: {str(e)}")

    # =============================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]], **kwargs to Generator[str, None, None]
    # =========================================================================
    # =============================================================================
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Yields:
            Response text chunks as they arrive
        """
        url = f"{self.config.base_url}/chat/completions"
        headers = self._get_headers()
        payload = self._build_payload(messages, stream=True, **kwargs)

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
                stream=True
            )
            response.raise_for_status()

            # Process Server-Sent Events (SSE)
            got_content = False
            reasoning_buffer = []

            for line in response.iter_lines():
                # ==================================
                if line:
                    line = line.decode("utf-8")

                    # Skip SSE comments
                    # ==================================
                    if line.startswith(":"):
                        continue

                    # Parse data lines
                    # ==================================
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        # Check for stream end
                        # ==================================
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            # ==================================
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    got_content = True
                                    yield content
                                else:
                                    # Buffer reasoning for code block extraction
                                    reasoning = delta.get("reasoning", "")
                                    if reasoning:
                                        reasoning_buffer.append(reasoning)
                        except json.JSONDecodeError:
                            continue

            # If no content was streamed, extract code blocks from reasoning
            if not got_content and reasoning_buffer:
                full_reasoning = "".join(reasoning_buffer)
                code_blocks = _CODE_BLOCK_RE.findall(full_reasoning)
                if code_blocks:
                    yield "\n\n".join(code_blocks)
                else:
                    yield full_reasoning

        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.config.timeout} seconds")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error communicating with {self.config.provider}: {str(e)}")

    # =============================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =============================================================================
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Uses tiktoken if available (for accurate OpenAI token counts),
        otherwise falls back to a rough character-based estimate.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        try:
            import tiktoken

            # Try to get the encoding for the specific model
            try:
                encoding = tiktoken.encoding_for_model(self.config.model)
            except KeyError:
                # Fall back to cl100k_base for newer models
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))

        except ImportError:
            # Fall back to rough estimate: 1 token ≈ 4 characters
            return len(text) // 4


# =============================================================================
# End of File
# =============================================================================
'''
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
