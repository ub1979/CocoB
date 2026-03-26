# =============================================================================
'''
    File Name : gemini_provider.py
    
    Description : Google Gemini LLM provider implementation
    
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

from typing import List, Dict, Generator, Any, Optional, TYPE_CHECKING

from .base import LLMProvider, LLMConfig

if TYPE_CHECKING:
    from skillforge.core.image_handler import Attachment


# =============================================================================
'''
    GeminiProvider : Provider for Google Gemini API
    
    Supports three modes:
    1. API key mode: Uses google-generativeai package with GOOGLE_API_KEY
    2. CLI mode: Uses Vertex AI with Application Default Credentials (gcloud auth)
    3. OAuth mode: Uses direct OAuth tokens (for Google One AI Premium subscribers)
    
    For CLI mode, run:
        gcloud auth application-default login
    
    For OAuth mode (subscription users), run:
        npm install -g @google/gemini-cli
        python -m core.llm.auth login gemini
    
    Configuration:
        auth_method="api_key": Uses GOOGLE_API_KEY environment variable
        auth_method="cli": Uses gcloud Application Default Credentials
        auth_method="oauth": Uses stored OAuth tokens from login flow
    
    For Vertex AI, set extra["gcp_project"] to your Google Cloud project ID.
'''
# =============================================================================
class GeminiProvider(LLMProvider):

    # =========================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =========================================================================
    def __init__(self, config: LLMConfig):
        self._client = None
        self._use_vertex = False
        super().__init__(config)

    # =========================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =========================================================================
    def _validate_config(self) -> None:
        """Validate provider-specific configuration"""
        # ==================================
        if self.config.auth_method == "api_key" and not self.config.api_key:
            raise ValueError(
                "API key required for Gemini. "
                "Set GOOGLE_API_KEY environment variable or use auth_method='cli' for gcloud auth "
                "or auth_method='oauth' for subscription users."
            )

        # ==================================
        if self.config.auth_method == "cli":
            # For Vertex AI, project is recommended but we can try to detect it
            # ==================================
            if not self.config.extra.get("gcp_project"):
                # Try to get project from environment or gcloud config
                import os
                project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
                # ==================================
                if project:
                    self.config.extra["gcp_project"] = project

        # ==================================
        if self.config.auth_method == "oauth":
            # OAuth mode uses stored tokens - validate they exist
            from .auth import is_logged_in
            # ==================================
            if not is_logged_in("gemini"):
                raise ValueError(
                    "Not logged in to Gemini. Run: python -m core.llm.auth login gemini"
                )

    # =========================================================================
    # =========================================================================
    # Function _get_client -> None to Any
    # =========================================================================
    # =========================================================================
    def _get_client(self):
        """Get or create the Gemini client"""
        # ==================================
        if self.config.auth_method == "oauth":
            # For OAuth, always refresh the client to ensure token is valid
            # The get_valid_token() call will auto-refresh if needed
            self._client = self._create_oauth_client()
            self._use_vertex = False
        # ==================================
        elif self._client is not None:
            return self._client
        # ==================================
        elif self.config.auth_method == "cli":
            # Use Application Default Credentials with Vertex AI
            self._client = self._create_vertex_client()
            self._use_vertex = True
        else:
            # Use API key with google-generativeai
            self._client = self._create_genai_client()
            self._use_vertex = False

        return self._client

    # =========================================================================
    # =========================================================================
    # Function _create_oauth_client -> None to Any
    # =========================================================================
    # =========================================================================
    def _create_oauth_client(self):
        """Create client using OAuth tokens (for subscription users)"""
        try:
            import google.generativeai as genai
            from google.oauth2.credentials import Credentials

            from .auth import get_valid_token

            # Get valid access token (auto-refreshes if expired)
            access_token = get_valid_token("gemini")

            # Create credentials object
            credentials = Credentials(token=access_token)

            # Configure genai with credentials
            genai.configure(credentials=credentials)

            return genai.GenerativeModel(self.config.model)

        except ImportError as e:
            raise ImportError(
                "google-generativeai and google-auth packages not installed. Run: "
                "pip install google-generativeai google-auth"
            ) from e

    # =========================================================================
    # =========================================================================
    # Function _create_vertex_client -> None to Any
    # =========================================================================
    # =========================================================================
    def _create_vertex_client(self):
        """Create Vertex AI client with Application Default Credentials"""
        try:
            from google.auth import default
            from google.auth.transport.requests import Request
            import vertexai
            from vertexai.generative_models import GenerativeModel

            # Get credentials from ADC
            credentials, project = default()

            # Refresh if needed
            # ==================================
            if hasattr(credentials, 'refresh'):
                credentials.refresh(Request())

            # Use project from config or detected from credentials
            gcp_project = self.config.extra.get("gcp_project") or project

            # ==================================
            if not gcp_project:
                raise ValueError(
                    "GCP project required for Vertex AI. "
                    "Set GCP_PROJECT environment variable or extra['gcp_project'] in config."
                )

            # Get location, default to us-central1
            location = self.config.extra.get("gcp_location", "us-central1")

            # Initialize Vertex AI
            vertexai.init(
                project=gcp_project,
                location=location,
                credentials=credentials
            )

            return GenerativeModel(self.config.model)

        except ImportError as e:
            raise ImportError(
                "Vertex AI packages not installed. Run: "
                "pip install google-cloud-aiplatform google-auth"
            ) from e

    # =========================================================================
    # =========================================================================
    # Function _create_genai_client -> None to Any
    # =========================================================================
    # =========================================================================
    def _create_genai_client(self):
        """Create google-generativeai client with API key"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.config.api_key)
            return genai.GenerativeModel(self.config.model)

        except ImportError as e:
            raise ImportError(
                "google-generativeai package not installed. Run: "
                "pip install google-generativeai"
            ) from e

    # =========================================================================
    # =========================================================================
    # Function _convert_messages -> List[Dict[str, str]] to tuple
    # =========================================================================
    # =========================================================================
    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple:
        """Convert OpenAI-style messages to Gemini format

        Returns:
            Tuple of (history, current_message, system_instruction)
        """
        system_instruction = None
        history = []
        current_message = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # ==================================
            if role == "system":
                # Gemini handles system prompts differently
                system_instruction = content
            # ==================================
            elif role == "assistant":
                # content can be a string or a list of parts (vision)
                if isinstance(content, list):
                    history.append({"role": "model", "parts": content})
                else:
                    history.append({"role": "model", "parts": [content]})
            # ==================================
            elif role == "user":
                # Keep track of the last user message
                # ==================================
                if current_message is not None:
                    history.append(current_message)
                # content can be a string or a list of parts (vision)
                if isinstance(content, list):
                    current_message = {"role": "user", "parts": content}
                else:
                    current_message = {"role": "user", "parts": [content]}

        return history, current_message, system_instruction

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
        model = self._get_client()
        history, current_message, system_instruction = self._convert_messages(messages)

        try:
            # ==================================
            if self._use_vertex:
                return self._chat_vertex(model, history, current_message, system_instruction, **kwargs)
            else:
                return self._chat_genai(model, history, current_message, system_instruction, **kwargs)
        except Exception as e:
            raise ConnectionError(f"Error communicating with Gemini: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function _chat_genai -> Any to str
    # =========================================================================
    # =========================================================================
    def _chat_genai(self, model, history, current_message, system_instruction, **kwargs) -> str:
        """Chat using google-generativeai SDK"""
        import google.generativeai as genai

        # Create generation config
        generation_config = genai.GenerationConfig(
            temperature=kwargs.get("temperature", self.config.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
        )

        # If we have a system instruction, create a new model with it
        # ==================================
        if system_instruction:
            model = genai.GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )

        # Start chat with history
        chat = model.start_chat(history=history)

        # Send current message
        # ==================================
        if current_message:
            parts = current_message["parts"]
            # Single text string: send directly; multi-part (vision): send list
            content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
            response = chat.send_message(
                content_to_send,
                generation_config=generation_config
            )
            return response.text

        return "No message provided."

    # =========================================================================
    # =========================================================================
    # Function _chat_vertex -> Any to str
    # =========================================================================
    # =========================================================================
    def _chat_vertex(self, model, history, current_message, system_instruction, **kwargs) -> str:
        """Chat using Vertex AI SDK"""
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        # Create generation config
        generation_config = GenerationConfig(
            temperature=kwargs.get("temperature", self.config.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
        )

        # If we have a system instruction, create a new model with it
        # ==================================
        if system_instruction:
            model = GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )

        # Start chat with history
        chat = model.start_chat(history=history)

        # Send current message
        # ==================================
        if current_message:
            parts = current_message["parts"]
            # Single text string: send directly; multi-part (vision): send list
            content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
            response = chat.send_message(
                content_to_send,
                generation_config=generation_config
            )
            return response.text

        return "No message provided."

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
        model = self._get_client()
        history, current_message, system_instruction = self._convert_messages(messages)

        try:
            # ==================================
            if self._use_vertex:
                yield from self._stream_vertex(model, history, current_message, system_instruction, **kwargs)
            else:
                yield from self._stream_genai(model, history, current_message, system_instruction, **kwargs)
        except Exception as e:
            raise ConnectionError(f"Error streaming from Gemini: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function _stream_genai -> Any to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def _stream_genai(self, model, history, current_message, system_instruction, **kwargs) -> Generator[str, None, None]:
        """Stream using google-generativeai SDK"""
        import google.generativeai as genai

        # Create generation config
        generation_config = genai.GenerationConfig(
            temperature=kwargs.get("temperature", self.config.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
        )

        # If we have a system instruction, create a new model with it
        # ==================================
        if system_instruction:
            model = genai.GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )

        # Start chat with history
        chat = model.start_chat(history=history)

        # Send current message with streaming
        # ==================================
        if current_message:
            parts = current_message["parts"]
            # Single text string: send directly; multi-part (vision): send list
            content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
            response = chat.send_message(
                content_to_send,
                generation_config=generation_config,
                stream=True
            )

            for chunk in response:
                # ==================================
                if chunk.text:
                    yield chunk.text

    # =========================================================================
    # =========================================================================
    # Function _stream_vertex -> Any to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def _stream_vertex(self, model, history, current_message, system_instruction, **kwargs) -> Generator[str, None, None]:
        """Stream using Vertex AI SDK"""
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        # Create generation config
        generation_config = GenerationConfig(
            temperature=kwargs.get("temperature", self.config.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.config.max_response_tokens),
        )

        # If we have a system instruction, create a new model with it
        # ==================================
        if system_instruction:
            model = GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )

        # Start chat with history
        chat = model.start_chat(history=history)

        # Send current message with streaming
        # ==================================
        if current_message:
            parts = current_message["parts"]
            # Single text string: send directly; multi-part (vision): send list
            content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
            response = chat.send_message(
                content_to_send,
                generation_config=generation_config,
                stream=True
            )

            for chunk in response:
                # ==================================
                if chunk.text:
                    yield chunk.text

    # =========================================================================
    # =========================================================================
    # Function supports_vision -> None to bool (property getter)
    # =========================================================================
    # =========================================================================
    @property
    def supports_vision(self) -> bool:
        """Whether this provider supports vision input.

        All Gemini models support vision (multimodal).
        """
        return True

    # =========================================================================
    # =========================================================================
    # Function format_vision_messages -> List, List to List
    # =========================================================================
    # =========================================================================
    def format_vision_messages(
        self,
        messages: List[Dict[str, Any]],
        attachments: List[Attachment],
    ) -> List[Dict[str, Any]]:
        """Format with Gemini inline_data parts.

        Gemini uses parts arrays. The _convert_messages method reads
        msg["content"]. We convert the last user message's content to
        a list of parts dicts that _convert_messages will pass through.

        After this transform, content becomes:
            [
                {"inline_data": {"mime_type": "image/jpeg", "data": "base64..."}},
                "describe this"
            ]

        Args:
            messages: Standard message list (role/content dicts).
            attachments: List of Attachment objects.

        Returns:
            Modified messages with the last user message's content as a
            list of Gemini-format parts.
        """
        if not attachments:
            return messages

        from skillforge.core.image_handler import ImageHandler
        handler = ImageHandler()

        # Find last user message index
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_idx = i
                break

        if last_user_idx is None:
            return messages

        result = [m.copy() for m in messages]
        user_msg = result[last_user_idx]
        text = user_msg.get("content", "")

        parts: List[Any] = []
        for att in attachments:
            b64 = handler.encode_base64(att.file_path)
            parts.append({
                "inline_data": {
                    "mime_type": att.mime_type,
                    "data": b64,
                }
            })
        parts.append(text)

        result[last_user_idx] = {"role": "user", "content": parts}
        return result

    # =========================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =========================================================================
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Gemini uses a different tokenizer than OpenAI.
        This provides a rough estimate.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Gemini tokenization is roughly similar to other models
        # ~4 characters per token on average
        return len(text) // 4


# =============================================================================
'''
    End of File : gemini_provider.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================
