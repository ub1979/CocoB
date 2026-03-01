# =============================================================================
'''
    File Name : anthropic_provider.py
    
    Description : Anthropic Claude LLM provider implementation
    
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
from typing import List, Dict, Generator, Any, Optional

import requests

from .base import LLMProvider, LLMConfig


# =============================================================================
'''
    AnthropicProvider : Provider for Anthropic Claude API
    
    Supports two modes:
    1. API key mode: Uses ANTHROPIC_API_KEY environment variable
    2. OAuth mode: Uses stored OAuth tokens (for Claude Pro/Max subscribers)
    
    Claude handles system prompts differently from OpenAI-compatible APIs.
    The system prompt must be passed as a top-level 'system' parameter,
    not as a message with role='system'.
    
    Configuration:
        auth_method="api_key": Uses ANTHROPIC_API_KEY environment variable (default)
        auth_method="oauth": Uses stored OAuth tokens from login flow
'''
# =============================================================================
class AnthropicProvider(LLMProvider):

    BASE_URL = "https://api.anthropic.com"
    API_VERSION = "2023-06-01"

    # =========================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =========================================================================
    def _validate_config(self) -> None:
        """Validate Anthropic-specific configuration"""
        # ==================================
        if self.config.auth_method == "oauth":
            # OAuth mode uses stored tokens - validate they exist
            from .auth import is_logged_in
            # ==================================
            if not is_logged_in("anthropic"):
                raise ValueError(
                    "Not logged in to Anthropic. Run: python -m core.llm.auth login anthropic"
                )
        # ==================================
        elif not self.config.api_key:
            raise ValueError(
                "API key is required for Anthropic. "
                "Set it via the 'api_key' config option or ANTHROPIC_API_KEY environment variable. "
                "Or use auth_method='oauth' for subscription users."
            )

        # Set default base_url if not provided
        # ==================================
        if self.config.base_url is None:
            self.config.base_url = self.BASE_URL

    # =========================================================================
    # =========================================================================
    # Function _get_headers -> None to Dict[str, str]
    # =========================================================================
    # =========================================================================
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers for Anthropic API"""
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": self.API_VERSION,
        }

        # ==================================
        if self.config.auth_method == "oauth":
            # Use OAuth token
            from .auth import get_valid_token
            access_token = get_valid_token("anthropic")
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            # Use API key
            headers["x-api-key"] = self.config.api_key or ""

        return headers

    # =========================================================================
    # =========================================================================
    # Function _prepare_request -> List[Dict[str, str]], bool, **kwargs to Dict[str, Any]
    # =========================================================================
    # =========================================================================
    def _prepare_request(self, messages: List[Dict[str, str]], stream: bool = False, **kwargs) -> Dict[str, Any]:
        """Extract system prompt and format for Claude API

        Claude requires system prompts as a separate top-level parameter,
        not in the messages array like OpenAI.

        Args:
            messages: List of message dicts (may include system messages)
            stream: Whether to stream the response
            **kwargs: Additional options

        Returns:
            Request payload formatted for Anthropic API
        """
        system_content: Optional[str] = None
        chat_messages: List[Dict[str, str]] = []

        # ==================================
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # ==================================
            if role == "system":
                # Anthropic: system prompt is top-level, not in messages
                # If multiple system messages, concatenate them
                # ==================================
                if system_content is None:
                    system_content = content
                else:
                    system_content = f"{system_content}\n\n{content}"
            else:
                # Map roles: Anthropic uses 'user' and 'assistant'
                anthropic_role = role if role in ["user", "assistant"] else "user"
                chat_messages.append({
                    "role": anthropic_role,
                    "content": content
                })

        # Build payload
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_response_tokens),
            "messages": chat_messages,
            "stream": stream,
        }

        # Add system prompt if present
        # ==================================
        if system_content:
            payload["system"] = system_content

        # Add temperature if specified
        temperature = kwargs.get("temperature", self.config.temperature)
        # ==================================
        if temperature is not None:
            payload["temperature"] = temperature

        # Add any extra parameters from config
        # ==================================
        if self.config.extra:
            for key, value in self.config.extra.items():
                # ==================================
                if key not in payload:
                    payload[key] = value

        return payload

    # =========================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]], **kwargs to str
    # =========================================================================
    # =========================================================================
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request to Claude and return response text

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Returns:
            AI response text
        """
        url = f"{self.config.base_url}/v1/messages"
        headers = self._get_headers()
        payload = self._prepare_request(messages, stream=False, **kwargs)

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()

            # Extract response text from Claude's response format
            # Claude returns: {"content": [{"type": "text", "text": "..."}], ...}
            # ==================================
            if "content" in data and len(data["content"]) > 0:
                # Find the text content block
                # ==================================
                for block in data["content"]:
                    # ==================================
                    if block.get("type") == "text":
                        return block.get("text", "")

            return "I apologize, but I couldn't generate a response."

        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.config.timeout} seconds")
        except requests.exceptions.HTTPError as e:
            # Parse Anthropic error response
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
                raise ConnectionError(f"Anthropic API error: {error_msg}")
            except (json.JSONDecodeError, AttributeError):
                raise ConnectionError(f"Error communicating with Anthropic: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error communicating with Anthropic: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]], **kwargs to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response from Claude

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options (temperature, max_tokens, etc.)

        Yields:
            Response text chunks as they arrive
        """
        url = f"{self.config.base_url}/v1/messages"
        headers = self._get_headers()
        payload = self._prepare_request(messages, stream=True, **kwargs)

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
            # Anthropic streaming format differs from OpenAI
            # ==================================
            for line in response.iter_lines():
                # ==================================
                if line:
                    line = line.decode("utf-8")

                    # Skip SSE comments and empty lines
                    # ==================================
                    if line.startswith(":") or not line.strip():
                        continue

                    # Parse event type
                    # ==================================
                    if line.startswith("event: "):
                        event_type = line[7:]
                        continue

                    # Parse data lines
                    # ==================================
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        try:
                            data = json.loads(data_str)

                            # Handle different event types
                            event_type_from_data = data.get("type", "")

                            # ==================================
                            if event_type_from_data == "content_block_delta":
                                # Extract text delta
                                delta = data.get("delta", {})
                                # ==================================
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    # ==================================
                                    if text:
                                        yield text

                            # ==================================
                            elif event_type_from_data == "message_stop":
                                # Stream complete
                                break

                            # ==================================
                            elif event_type_from_data == "error":
                                # Handle streaming error
                                error_msg = data.get("error", {}).get("message", "Unknown error")
                                raise ConnectionError(f"Anthropic streaming error: {error_msg}")

                        except json.JSONDecodeError:
                            continue

        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.config.timeout} seconds")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error communicating with Anthropic: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =========================================================================
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Claude uses a different tokenizer than OpenAI, but for estimation
        purposes, the character-based approximation works reasonably well.

        For production use, consider using the anthropic package's
        count_tokens method if available.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        try:
            # Try to use anthropic package's tokenizer if available
            import anthropic

            # anthropic.Anthropic().count_tokens() requires API call
            # For now, use the rough estimate
            pass
        except ImportError:
            pass

        # Fall back to rough estimate: 1 token ≈ 4 characters
        # Claude's tokenizer is similar to OpenAI's cl100k_base
        return len(text) // 4


# =============================================================================
'''
    End of File : anthropic_provider.py
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================
