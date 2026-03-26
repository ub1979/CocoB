# =============================================================================
'''
    File Name : claude_cli_provider.py
    
    Description : Claude Code CLI Provider for SkillForge. Uses the official 
    Claude Code CLI as backend, allowing users with Claude Pro/Max 
    subscriptions to use their subscription without extra API costs.
    
    Prerequisites:
        npm install -g @anthropic-ai/claude-code
        claude login  (one-time setup)
    
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

import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Generator, Any, Optional

from .base import LLMProvider, LLMConfig

try:
    from skillforge import PROJECT_ROOT
    _SESSION_FILE = PROJECT_ROOT / "data" / "claude_session.json"
except Exception:
    _SESSION_FILE = Path("data") / "claude_session.json"


# =============================================================================
'''
    ClaudeCLIProvider : Provider that wraps the Claude Code CLI
    
    Uses the official Claude Code CLI which has OAuth access to Claude
    with Pro/Max subscriptions. No API key needed - uses subscription.
    
    Configuration:
        model: Model to use (default: claude-sonnet-4-20250514)
        timeout: Request timeout in seconds (default: 120)
        extra.session_id: Optional session ID to continue conversation
'''
# =============================================================================

class ClaudeCLIProvider(LLMProvider):

    # =========================================================================
    # =========================================================================
    # Function __init__ -> LLMConfig to None
    # =========================================================================
    # =========================================================================
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._session_id: Optional[str] = self._load_session_id()

    def _load_session_id(self) -> Optional[str]:
        """Load persisted session ID from disk."""
        try:
            if _SESSION_FILE.exists():
                data = json.loads(_SESSION_FILE.read_text())
                return data.get("session_id")
        except Exception:
            pass
        return None

    def _save_session_id(self):
        """Persist session ID to disk for restart survival."""
        try:
            _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SESSION_FILE.write_text(json.dumps({"session_id": self._session_id}))
        except Exception:
            pass

    # =========================================================================
    # =========================================================================
    # Function _validate_config -> None to None
    # =========================================================================
    # =========================================================================
    def _validate_config(self) -> None:
        """Validate that Claude CLI is installed"""
        # ==================================
        if not shutil.which("claude"):
            raise ValueError(
                "Claude Code CLI not found. Install it with:\n"
                "  npm install -g @anthropic-ai/claude-code\n"
                "Then login with:\n"
                "  claude login"
            )

    # =========================================================================
    # =========================================================================
    # Function _build_command -> str, bool to List[str]
    # =========================================================================
    # =========================================================================
    def _build_command(self, prompt: str, stream: bool = False) -> List[str]:
        """Build the claude CLI command"""
        cmd = ["claude", "-p", prompt]

        # ==================================
        # Output format
        # ==================================
        if stream:
            cmd.extend(["--output-format", "stream-json"])
            cmd.extend(["--verbose"])
            cmd.extend(["--include-partial-messages"])
        else:
            cmd.extend(["--output-format", "json"])

        # ==================================
        # Continue conversation if we have a session
        # ==================================
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        # ==================================
        # Model selection (if supported)
        # Note: Claude CLI may not support model override
        # ==================================

        return cmd

    # =========================================================================
    # =========================================================================
    # Function _format_messages -> List[Dict[str, str]] to str
    # =========================================================================
    # =========================================================================
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a single prompt for CLI

        When resuming a session (--resume), Claude CLI already has the full
        conversation server-side, so we only send the latest user message.
        On the first message (no session), we send everything.
        """
        # ==================================
        # Resuming — Claude CLI already has context, just send new user message
        # ==================================
        if self._session_id:
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
            return ""

        # ==================================
        # First message in session — send everything
        # ==================================
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.insert(0, f"[System Instructions]\n{content}\n")
            elif role == "assistant":
                parts.append(f"[Previous Assistant Response]\n{content}\n")
            else:  # user
                parts.append(f"[User]\n{content}\n")

        return "\n".join(parts)

    # =========================================================================
    # =========================================================================
    # Function chat -> List[Dict[str, str]], **kwargs to str
    # =========================================================================
    # =========================================================================
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request via Claude CLI

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options

        Returns:
            AI response text
        """
        prompt = self._format_messages(messages)
        cmd = self._build_command(prompt, stream=False)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
                cwd=None,  # Use current directory
                input=''  # Claude CLI expects stdin
            )

            # ==================================
            # Check for command execution errors
            # ==================================
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise ConnectionError(f"Claude CLI error: {error_msg}")

            # ==================================
            # Parse JSON output
            # ==================================
            try:
                data = json.loads(result.stdout)

                # ==================================
                # Save session ID for continuation
                # ==================================
                if "session_id" in data:
                    self._session_id = data["session_id"]
                    self._save_session_id()

                # ==================================
                # Extract result text
                # ==================================
                return data.get("result", "")

            except json.JSONDecodeError:
                # If not JSON, return raw output
                return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude CLI timed out after {self.config.timeout} seconds")
        except FileNotFoundError:
            raise ConnectionError("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        except Exception as e:
            raise ConnectionError(f"Error running Claude CLI: {str(e)}")

    # =========================================================================
    # =========================================================================
    # Function chat_stream -> List[Dict[str, str]], **kwargs to Generator[str, None, None]
    # =========================================================================
    # =========================================================================
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response from Claude CLI

        Args:
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional options

        Yields:
            Response text chunks as they arrive
        """
        prompt = self._format_messages(messages)
        cmd = self._build_command(prompt, stream=True)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # ==================================
            # Process streaming output line by line
            # ==================================
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("type", "")

                    # ==================================
                    # Handle different event types
                    # ==================================
                    if event_type == "stream_event":
                        delta = event.get("event", {}).get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                yield text

                    elif event_type == "result":
                        # Final result - save session ID
                        if "session_id" in event:
                            self._session_id = event["session_id"]
                            self._save_session_id()

                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    continue

            # ==================================
            # Wait for process to complete
            # ==================================
            process.wait(timeout=10)

            if process.returncode != 0:
                stderr = process.stderr.read()
                if stderr:
                    raise ConnectionError(f"Claude CLI error: {stderr}")

        except subprocess.TimeoutExpired:
            process.kill()
            raise TimeoutError(f"Claude CLI timed out after {self.config.timeout} seconds")
        except FileNotFoundError:
            raise ConnectionError("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        except Exception as e:
            raise ConnectionError(f"Error streaming from Claude CLI: {str(e)}")

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

        Uses rough approximation since we don't have direct tokenizer access.

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
        """Reset the conversation session

        Call this to start a fresh conversation without history.
        """
        self._session_id = None
        try:
            if _SESSION_FILE.exists():
                _SESSION_FILE.unlink()
        except Exception:
            pass

    # =========================================================================
    # =========================================================================
    # Function session_id -> property to Optional[str]
    # =========================================================================
    # =========================================================================
    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID for conversation continuation"""
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
