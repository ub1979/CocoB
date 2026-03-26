# =============================================================================
'''
    File Name : gemini_cli_provider.py
    
    Description : Gemini CLI Provider for SkillForge. Uses the official 
    Gemini CLI as backend, allowing users with Google One AI Premium 
    subscriptions to use their subscription without extra API costs.
    
    Prerequisites:
        npm install -g @google/gemini-cli
        gemini auth login  (one-time setup)
    
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

import subprocess
import shutil
from typing import List, Dict, Generator, Optional

from .base import LLMProvider, LLMConfig


# =============================================================================
'''
    GeminiCLIProvider : Provider that wraps the Gemini CLI
    
    Uses the official Gemini CLI which has OAuth access to Gemini
    with Google One AI Premium subscriptions. No API key needed.
    
    Configuration:
        model: Model to use (default: gemini-2.0-flash)
        timeout: Request timeout in seconds (default: 120)
'''
# =============================================================================

class GeminiCLIProvider(LLMProvider):

    # =========================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =========================================================================
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._session_id: Optional[str] = None

    # =========================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =========================================================================
    def _validate_config(self) -> None:
        """Validate that Gemini CLI is installed"""
        # ==================================
        if not shutil.which("gemini"):
            raise ValueError(
                "Gemini CLI not found. Install it with:\n"
                "  npm install -g @google/gemini-cli\n"
                "Then login with:\n"
                "  gemini auth login"
            )

    # =========================================================================
    # =========================================================================
    # Function _build_command -> str to List[str]
    # =========================================================================
    # =========================================================================
    def _build_command(self, prompt: str) -> List[str]:
        """Build the gemini CLI command

        Gemini CLI flags:
        -p, --prompt  Prompt string
        -m, --model   Model to use (optional, uses default if not set)
        """
        cmd = ["gemini"]

        # ==================================
        # Only pass model if explicitly set and not empty
        # Let CLI use its default (gemini-2.5-pro) otherwise
        # ==================================
        if self.config.model and self.config.model not in ("", "default"):
            cmd.extend(["-m", self.config.model])

        # ==================================
        # Add the prompt
        # ==================================
        cmd.extend(["-p", prompt])

        return cmd

    # =========================================================================
    # =========================================================================
    # Function _format_messages -> List[Dict[str, str]] to str
    # =========================================================================
    # =========================================================================
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a single prompt for CLI

        Keep it simple - just extract the last user message with
        system prompt prepended if present.
        """
        system_prompt = ""
        last_user_message = ""

        # ==================================
        # Extract system prompt and last user message
        # ==================================
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # ==================================
            if role == "system":
                system_prompt = content
            elif role == "user":
                last_user_message = content

        # ==================================
        # Combine system and user message
        # ==================================
        if system_prompt:
            return f"{system_prompt}\n\n{last_user_message}"
        return last_user_message

    # =========================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]], **kwargs to str
    # =========================================================================
    # =========================================================================
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request via Gemini CLI

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options

        Returns:
            AI response text
        """
        prompt = self._format_messages(messages)
        cmd = self._build_command(prompt)

        # ==================================
        # Debug: show command being run
        # ==================================
        print(f"[Gemini CLI] Running: {' '.join(cmd[:3])}... (prompt length: {len(prompt)})")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=None,
                input=''  # Gemini CLI expects stdin even with -p flag
            )

            # ==================================
            # Check for command execution errors
            # ==================================
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise ConnectionError(f"Gemini CLI error: {error_msg}")

            # ==================================
            # Gemini CLI outputs plain text
            # ==================================
            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Gemini CLI timed out after {self.config.timeout} seconds")
        except FileNotFoundError:
            raise ConnectionError("Gemini CLI not found. Install with: npm install -g @google/gemini-cli")
        except Exception as e:
            raise ConnectionError(f"Error running Gemini CLI: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]], **kwargs to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response from Gemini CLI

        Note: Gemini CLI doesn't support streaming output, so we run it
        synchronously and yield the output line by line.

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options

        Yields:
            Response text chunks
        """
        prompt = self._format_messages(messages)
        cmd = self._build_command(prompt)

        # ==================================
        # Debug: show command being run
        # ==================================
        print(f"[Gemini CLI] Running: {' '.join(cmd[:3])}... (prompt length: {len(prompt)})")

        try:
            # ==================================
            # Run process and stream stdout line by line
            # ==================================
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # ==================================
            # Yield output as it comes
            # ==================================
            for line in process.stdout:
                if line:
                    yield line

            process.wait(timeout=self.config.timeout)

            # ==================================
            # Check for process errors
            # ==================================
            if process.returncode != 0:
                stderr = process.stderr.read()
                if stderr:
                    raise ConnectionError(f"Gemini CLI error: {stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError(f"Gemini CLI timed out after {self.config.timeout} seconds")
        except FileNotFoundError:
            raise ConnectionError("Gemini CLI not found. Install with: npm install -g @google/gemini-cli")
        except Exception as e:
            raise ConnectionError(f"Error streaming from Gemini CLI: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function supports_vision -> None to bool (property getter)
    # =========================================================================
    # =========================================================================
    @property
    def supports_vision(self) -> bool:
        """Whether this provider supports vision input.

        CLI providers cannot accept image input directly.
        """
        return False

    # =========================================================================
    # =========================================================================
    # Function estimate_tokens -> str to int
    # =========================================================================
    # =========================================================================
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # ==================================
        # Rough estimate: 1 token ≈ 4 characters
        # ==================================
        return len(text) // 4

    # =========================================================================
    # =========================================================================
    # Function reset_session -> None to None
    # =========================================================================
    # =========================================================================
    def reset_session(self) -> None:
        """Reset the conversation session"""
        self._session_id = None

    # =========================================================================
    # =========================================================================
    # Function session_id -> property to Optional[str]
    # =========================================================================
    # =========================================================================
    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID"""
        return self._session_id


# =============================================================================
# End of File
# =============================================================================
# 
# Project : SkillForge - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# 
# Done by : Syed Usama Bukhari & Idrak AI Ltd Team
# =============================================================================
