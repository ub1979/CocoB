# =============================================================================
'''
    File Name : router.py
    
    Description : Message Router - Main bot logic that orchestrates receiving
    messages from channels, loading session history, getting AI response,
    managing context/compaction, and sending responses back. This is the
    central component that routes messages between channels, sessions, and AI.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Contact : Idrak AI Ltd - Building AI Solutions for the Community
'''
# =============================================================================


# =============================================================================
# Import Section
# =============================================================================
import asyncio
import os
import re
import threading
from typing import Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from pathlib import Path
from skillforge.core.sessions import SessionManager
from skillforge.core.llm import LLMProvider
from skillforge.core.ai import AIClient
from skillforge.core.personality import PersonalityManager
from skillforge.core.memory import SQLiteMemory
from skillforge.core.mcp_tools import MCPToolHandler
from skillforge.core.schedule_handler import ScheduleCommandHandler
from skillforge.core.todo_handler import TodoCommandHandler
from skillforge.core.skill_creator_handler import SkillCreatorHandler
from skillforge.core.skill_executor import SkillExecutor
from skillforge.core.file_access import FileAccessManager
from skillforge.core.auth_manager import AuthManager, SecurityLevel
from skillforge.core.heartbeat_manager import HeartbeatManager
from skillforge.core.pattern_detector import PatternDetector
from skillforge.core.background_tasks import BackgroundTaskRunner
from skillforge.core.mcp_manager import MCPManager as MCPServerManager
from skillforge.core.clawhub import ClawHubManager
from skillforge.core.web_tools import WebToolsHandler
from skillforge.core.user_permissions import PermissionManager
from skillforge.core.identity_resolver import IdentityResolver
from skillforge.core.permission_requests import PermissionRequestManager
from skillforge.core.image_handler import ImageHandler, Attachment
from skillforge.core.image_gen_handler import ImageGenHandler

if TYPE_CHECKING:
    from skillforge.core.mcp_client import MCPManager
    from skillforge.core.scheduler import SchedulerManager
# =============================================================================


# =============================================================================
'''
    MessageRouter : Routes messages between channels, sessions, and AI
'''
# =============================================================================
class MessageRouter:
    """Routes messages between channels, sessions, and AI"""

    # =========================================================================
    # =========================================================================
    # Function __init__ -> SessionManager & Union[LLMProvider, AIClient] to None
    # =========================================================================
    # =========================================================================
    def __init__(
        self,
        session_manager: SessionManager,
        llm_provider: Union[LLMProvider, AIClient],
        mcp_manager: Optional["MCPManager"] = None
    ):
        """Initialize the message router

        Args:
            session_manager: Session manager instance
            llm_provider: LLM provider (LLMProvider or AIClient for backward compat)
            mcp_manager: Optional MCP manager for tool integration
        """
        self.session_manager = session_manager

        # ==================================
        # Support both new LLMProvider interface and old AIClient
        # ==================================
        if isinstance(llm_provider, AIClient):
            self.llm = llm_provider.provider
            self._ai_client = llm_provider  # Keep reference for backward compat
        else:
            self.llm = llm_provider
            self._ai_client = None

        self.personality = PersonalityManager()
        self.system_prompt = self.personality.get_system_prompt()
        self._system_prompt_mtime = self._get_personality_mtime()
        self._prompt_cache: Dict[str, tuple] = {}  # key → (mtime, prompt_str)

        # ==================================
        # Initialize MCP tool handler
        # ==================================
        self._mcp_manager = mcp_manager
        self._tool_handler = None
        self._skill_executor = SkillExecutor(mcp_manager)
        if mcp_manager:
            self._tool_handler = MCPToolHandler(mcp_manager)

        # ==================================
        # Long-term memory store (SQLite FTS5 - instant startup)
        # ==================================
        self.memory_store = SQLiteMemory()
        stats = self.memory_store.get_stats()
        print(f"Long-term memory: {stats['facts']} facts, {stats['conversations']} conversations")

        # ==================================
        # Initialize schedule command handler
        # ==================================
        self._scheduler_manager = None
        self._schedule_handler = ScheduleCommandHandler()

        # ==================================
        # Initialize todo command handler
        # ==================================
        self._todo_handler = TodoCommandHandler()

        # ==================================
        # Initialize skill creator handler
        # ==================================
        self._skill_creator_handler = SkillCreatorHandler(self.personality.skills_manager)

        # ==================================
        # Initialize file access manager (password-protected sandbox)
        # ==================================
        self._file_access = FileAccessManager()

        # ==================================
        # Initialize agentic modules (auth → heartbeat → pattern → tasks → mcp)
        # ==================================
        self._auth_manager = AuthManager()
        self._permission_manager = PermissionManager()
        self._identity_resolver = IdentityResolver()
        self._request_manager = PermissionRequestManager()
        self._heartbeat_manager = HeartbeatManager()
        self._pattern_detector = PatternDetector(auth_manager=self._auth_manager)
        self._task_runner = BackgroundTaskRunner(auth_manager=self._auth_manager)
        self._mcp_server_manager = MCPServerManager(auth_manager=self._auth_manager)

        # ==================================
        # Initialize ClawHub manager (OpenClaw.ai skill registry)
        # ==================================
        self._clawhub_manager = ClawHubManager(
            skills_manager=self.personality.skills_manager,
        )

        # ==================================
        # Initialize web tools handler (native web search/fetch)
        # ==================================
        brave_key = None
        try:
            import config as cfg
            brave_key = getattr(cfg, "BRAVE_SEARCH_API_KEY", None)
        except Exception:
            pass
        self._web_tools = WebToolsHandler(brave_api_key=brave_key)

        # ==================================
        # Initialize image handler (vision/attachment pipeline)
        # ==================================
        self._image_handler = ImageHandler()

        # ==================================
        # Initialize image generation handler (outbound image gen via MCP)
        # ==================================
        self._image_gen_handler = ImageGenHandler(mcp_manager=mcp_manager)

        # ==================================
        # Per-session thinking level (maps session_key → level name)
        # ==================================
        self._think_levels: Dict[str, str] = {}

    # =========================================================================
    # Think level constants
    # =========================================================================
    THINK_LEVELS = {
        "off":     {"temperature": 0.0, "description": "Deterministic, no randomness"},
        "minimal": {"temperature": 0.2, "description": "Very focused, minimal creativity"},
        "low":     {"temperature": 0.4, "description": "Focused with slight variation"},
        "medium":  {"temperature": 0.7, "description": "Balanced (default)"},
        "high":    {"temperature": 0.9, "description": "Creative, more varied responses"},
        "xhigh":   {"temperature": 1.2, "description": "Maximum creativity and exploration"},
    }

    # =========================================================================
    # Cache helpers for system prompt
    # =========================================================================
    def _get_personality_mtime(self) -> float:
        """Get latest mtime across personality files for cache invalidation"""
        mtime = 0.0
        for f in [self.personality.personality_file, self.personality.moods_file, self.personality.new_personality_file]:
            try:
                mtime = max(mtime, f.stat().st_mtime)
            except OSError:
                pass
        # Also check agents dir and profiles file for persona changes
        try:
            if self.personality.agents_dir.exists():
                mtime = max(mtime, self.personality.agents_dir.stat().st_mtime)
        except OSError:
            pass
        try:
            if self.personality.profiles_file.exists():
                mtime = max(mtime, self.personality.profiles_file.stat().st_mtime)
        except OSError:
            pass
        return mtime

    def _get_system_prompt_cached(self, user_id: Optional[str] = None, channel: Optional[str] = None) -> str:
        """Return cached system prompt, re-read only if personality files changed.
        Keyed by user_id:channel for per-persona caching."""
        cache_key = f"{user_id or ''}:{channel or ''}"
        current_mtime = self._get_personality_mtime()

        cached = self._prompt_cache.get(cache_key)
        if cached and cached[0] == current_mtime:
            return cached[1]

        prompt = self.personality.get_system_prompt(user_id=user_id, channel=channel)
        self._prompt_cache[cache_key] = (current_mtime, prompt)

        # Also update legacy single-prompt cache for backward compat
        if not user_id and not channel:
            self.system_prompt = prompt
            self._system_prompt_mtime = current_mtime

        return prompt

    # =========================================================================
    # Outbound image extraction (E-005)
    # =========================================================================

    # Regex for [Generated Image: /path/to/file.png] markers
    _GENERATED_IMAGE_RE = re.compile(
        r'\[Generated Image:\s*([^\]]+)\]'
    )
    # Regex for image file paths (local absolute paths with image extensions)
    _LOCAL_IMAGE_PATH_RE = re.compile(
        r'(?<![(\[])(/[^\s\]\)]+\.(?:png|jpg|jpeg|gif|webp|bmp))(?![)\]])',
        re.IGNORECASE,
    )
    # Regex for inline image markdown: ![alt](path_or_url)
    _MARKDOWN_IMAGE_RE = re.compile(
        r'!\[[^\]]*\]\(([^\)]+\.(?:png|jpg|jpeg|gif|webp|bmp))\)',
        re.IGNORECASE,
    )
    # Regex for Saved to: `path` markers emitted by image_gen_handler
    _SAVED_TO_RE = re.compile(
        r'Saved to:\s*`([^`]+\.(?:png|jpg|jpeg|gif|webp|bmp))`',
        re.IGNORECASE,
    )

    @staticmethod
    def extract_outbound_images(response: str) -> Tuple[str, List[str]]:
        """Extract image file paths from a bot response.

        Looks for patterns emitted by the image generation handler and other
        sources:
          - ``[Generated Image: /path/to/file.png]``
          - ``- Saved to: `/path/to/file.png```
          - ``![alt](/path/to/file.png)``
          - Bare absolute file paths ending in image extensions

        Only paths that exist on disk are returned.  HTTP(S) URLs are collected
        as-is without an existence check.

        Args:
            response: The bot response text.

        Returns:
            A 2-tuple of (cleaned_text, image_paths).
            ``cleaned_text`` has the image markers removed so channels can
            display it as regular text.  ``image_paths`` is a list of local
            file paths or URLs that should be sent as native images.
        """
        image_paths: List[str] = []
        cleaned = response

        # 1. [Generated Image: /path/to/file.png]
        for m in MessageRouter._GENERATED_IMAGE_RE.finditer(response):
            path = m.group(1).strip()
            if path not in image_paths:
                image_paths.append(path)
        cleaned = MessageRouter._GENERATED_IMAGE_RE.sub('', cleaned)

        # 2. - Saved to: `/path/to/file.png`
        for m in MessageRouter._SAVED_TO_RE.finditer(response):
            path = m.group(1).strip()
            if path not in image_paths:
                image_paths.append(path)
        # Remove the entire "- Saved to: `...`" line
        cleaned = re.sub(
            r'-\s*Saved to:\s*`[^`]+\.(?:png|jpg|jpeg|gif|webp|bmp)`\s*\n?',
            '', cleaned, flags=re.IGNORECASE,
        )

        # 3. ![alt](/path/to/file.png)
        for m in MessageRouter._MARKDOWN_IMAGE_RE.finditer(cleaned):
            path = m.group(1).strip()
            if path not in image_paths:
                image_paths.append(path)
        cleaned = MessageRouter._MARKDOWN_IMAGE_RE.sub('', cleaned)

        # Filter: keep only existing local files or http(s) URLs
        valid_paths: List[str] = []
        for p in image_paths:
            if p.startswith(("http://", "https://")):
                valid_paths.append(p)
            elif os.path.isfile(p):
                valid_paths.append(p)

        # Collapse any runs of blank lines produced by stripping markers
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

        return cleaned, valid_paths

    # =========================================================================
    # Permission helpers
    # =========================================================================
    def _build_capability_hints(self, user_id: str) -> str:
        """Build capability hint text for system prompt, filtered by user permissions."""
        hints = ""

        # Scheduling hint
        if self._scheduler_manager and self._permission_manager.has_permission(user_id, "schedule"):
            from datetime import datetime as _dt, timezone as _tz
            now_local = _dt.now().astimezone()
            local_tz = now_local.strftime("%Z")
            local_time = now_local.strftime("%Y-%m-%d %H:%M:%S")
            now_utc = now_local.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            hints += (
                f"\n\nCurrent local time: {local_time} {local_tz} (UTC: {now_utc})\n"
                "You can set reminders, alarms, and scheduled tasks.\n"
                "When the user asks for a reminder, set it immediately by emitting a ```schedule``` block. "
                "Tell the user what time you set it for (in their local timezone shown above).\n\n"
                "Schedule block formats:\n\n"
                "One-time reminder:\n"
                "ACTION: create\nNAME: <name>\nKIND: at\nRUN_AT: <ISO 8601 UTC datetime>\n"
                "MESSAGE: <text>\n\n"
                "Recurring (every N minutes/hours):\n"
                "ACTION: create\nNAME: <name>\nKIND: every\nINTERVAL: 1m\n"
                "MESSAGE: <text>\n\n"
                "Cron schedule:\n"
                "ACTION: create\nNAME: <name>\nKIND: cron\nSCHEDULE: 0 9 * * *\n"
                "MESSAGE: <text>\n\n"
                "List all reminders:\n"
                "ACTION: list\n\n"
                "Stop/delete a reminder:\n"
                "ACTION: delete\nNAME: <name of the task>\n\n"
                "Stop ALL reminders:\n"
                "ACTION: delete_all\n\n"
                "IMPORTANT: Use exactly ONE ```schedule``` block per request. "
                "For 'stop all' use ACTION: delete_all (single block, not multiple delete blocks).\n"
                "INTERVAL examples: 1m, 5m, 30m, 1h, 2h. "
                "Always convert to UTC for RUN_AT."
            )

        # Web search hint
        if self._web_tools and self._permission_manager.has_permission(user_id, "web_search"):
            hints += (
                "\n\nYou have built-in web search. "
                "When the user asks about weather, news, scores, prices, recent events, "
                "or ANYTHING that needs up-to-date information, you MUST immediately "
                "search the web yourself by emitting a ```web_search``` block — "
                "never tell the user to search or suggest they use a skill. "
                "Just do it automatically and give them the answer.\n"
                "```web_search\nQUERY: <search query>\nCOUNT: 5\n```\n"
                "You can also fetch a specific URL:\n"
                "```web_fetch\nURL: <url>\nMAX_CHARS: 5000\n```\n"
                "The results are returned to you automatically so you can summarise the answer. "
                "IMPORTANT: Always use ```web_search``` blocks, never /google-search or any other skill for searching."
            )

        return hints

    # Web search prompt helpers — ensure web_search instruction is prominent
    _WEB_HINT_MARKER = "\n\nYou have built-in web search."

    def _extract_web_hint(self, hints: str) -> str:
        """Extract the web search hint section from capability hints."""
        marker = self._WEB_HINT_MARKER
        idx = hints.find(marker)
        if idx == -1:
            return ""
        # Find the end: next "\n\n" section or end of string
        rest = hints[idx + len(marker):]
        next_section = rest.find("\n\nCurrent local time:")
        if next_section == -1:
            next_section = rest.find("\n\nYou can set reminders")
        if next_section == -1:
            return hints[idx:]
        return hints[idx:idx + len(marker) + next_section]

    def _strip_web_hint(self, hints: str) -> str:
        """Return capability hints with the web search section removed."""
        web_hint = self._extract_web_hint(hints)
        if not web_hint:
            return hints
        return hints.replace(web_hint, "")

    @staticmethod
    def _filter_web_skill_from_prompt(system_content: str) -> str:
        """Remove /google-search from the skills list in the system prompt."""
        import re
        # Remove from "Skills: /a, /google-search, /b" style lists
        system_content = re.sub(r',?\s*/google-search', '', system_content)
        # Clean up double commas or leading commas
        system_content = re.sub(r'Skills:\s*,', 'Skills:', system_content)
        return system_content

    # Keywords that signal the user wants real-time information
    _SEARCH_KEYWORDS = re.compile(
        r'\b(weather|forecast|news|score|scores|price|stock|latest|current|today|tonight|'
        r'yesterday|tomorrow|live|recent|update|result|happening|trending|who won|'
        r'how much is|what is the price|exchange rate|usd|gbp|eur)\b',
        re.IGNORECASE,
    )

    def _needs_web_search(self, user_message: str) -> bool:
        """Detect if a user message needs a web search for up-to-date info."""
        if not self._web_tools:
            return False
        return bool(self._SEARCH_KEYWORDS.search(user_message))

    def _pre_search(self, user_message: str) -> str:
        """Perform a web search for the user's query and return context to inject."""
        try:
            results = self._web_tools.web_search(user_message, count=5)
            if results and len(results.strip()) > 20:
                return (
                    f"\n\n## Web Search Results\n\n"
                    f"I searched the web for: \"{user_message}\"\n\n"
                    f"{results}\n\n"
                    f"**Use these search results to answer the user's question directly.** "
                    f"Do NOT suggest the user search themselves or use any /command. "
                    f"Summarize the relevant information from the results above."
                )
        except Exception as e:
            logger.error(f"Pre-search failed: {e}")
        return ""

    @staticmethod
    def _intercept_slash_search(response: str) -> str:
        """Convert slash-command search patterns in LLM output to web_search blocks.

        LLMs sometimes output '/google-search <query>', '/browse query: <query>',
        or similar instead of using ```web_search``` code blocks. This intercepts
        those patterns and converts them so the web_tools handler can process them.
        """
        # Match /google-search <query>
        match = re.search(r'/?google-search\s+(.+)', response, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            response = re.sub(
                r'/?google-search\s+.+',
                f'```web_search\nQUERY: {query}\nCOUNT: 5\n```',
                response, count=1, flags=re.IGNORECASE,
            )
            return response

        # Match /browse query: <query> or /browse <non-url query>
        match = re.search(r'/?browse\s+(?:query:\s*)?(.+)', response, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            # Only intercept if it's not an actual URL
            if not query.startswith(('http://', 'https://', 'www.')):
                response = re.sub(
                    r'/?browse\s+(?:query:\s*)?.+',
                    f'```web_search\nQUERY: {query}\nCOUNT: 5\n```',
                    response, count=1, flags=re.IGNORECASE,
                )
        return response

    def _check_handler_permission(self, user_id: str, handler_type: str) -> bool:
        """Check if user has permission to use a specific handler.

        Args:
            user_id: User identifier
            handler_type: One of 'schedule', 'skills_create', 'todo',
                         'web_search', 'web_fetch', 'mcp_tools'
        """
        return self._permission_manager.has_permission(user_id, handler_type)

    def _check_command_permission(self, command: str, user_id: str) -> Optional[str]:
        """Check if a command requires a permission the user doesn't have.

        Returns:
            None if allowed, or an error message string if denied.
        """
        cmd = command.lower().strip()

        # Admin-only commands
        admin_commands = ["/user-role", "/grant", "/revoke", "/users"]
        for ac in admin_commands:
            if cmd.startswith(ac):
                if not self._permission_manager.is_admin(user_id):
                    return "Permission denied. Admin access required."
                return None

        # MCP management commands
        if cmd.startswith("/mcp") and any(cmd.startswith(f"/mcp {sub}") for sub in ["install", "uninstall", "enable", "disable"]):
            if not self._permission_manager.has_permission(user_id, "mcp_manage"):
                return "Permission denied. You don't have MCP management access. Use `/request-permission mcp_manage` to request access."
            return None

        # Background tasks
        if cmd.startswith("/tasks"):
            if not self._permission_manager.has_permission(user_id, "background_tasks"):
                return "Permission denied. You don't have background task access. Use `/request-permission background_tasks` to request access."
            return None

        return None  # Allowed

    def _store_memory_background(self, user_id, channel, session_key, user_message, clean_response):
        """Store memory and extract facts in a background thread (non-blocking)"""
        def _do():
            try:
                self.memory_store.add_conversation(user_id, channel, session_key, user_message, clean_response)
                extracted = self.memory_store.extract_and_store_facts(user_id, user_message, session_key)
                if extracted:
                    print(f"[memory] Extracted facts: {extracted}")
                if not extracted and len(user_message) >= 30:
                    # Skip LLM extraction for short/trivial messages — no facts to find
                    try:
                        llm_facts = self.memory_store.extract_facts_via_llm(
                            user_id, user_message, clean_response, self.llm, session_key
                        )
                        if llm_facts:
                            print(f"[memory] LLM-extracted facts: {llm_facts}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"Memory storage error: {e}")
        threading.Thread(target=_do, daemon=True).start()

    # =========================================================================
    # =========================================================================
    # Function set_mcp_manager -> MCPManager to None
    # =========================================================================
    # =========================================================================
    def set_mcp_manager(self, mcp_manager: "MCPManager"):
        """Set or update MCP manager after initialization"""
        self._mcp_manager = mcp_manager
        self._tool_handler = MCPToolHandler(mcp_manager) if mcp_manager else None
        self._skill_executor.set_mcp_manager(mcp_manager)
        self._image_gen_handler.set_mcp_manager(mcp_manager)

    # =========================================================================
    # =========================================================================
    # Function set_scheduler_manager -> SchedulerManager to None
    # =========================================================================
    # =========================================================================
    def set_scheduler_manager(self, scheduler_manager: "SchedulerManager"):
        """Set or update scheduler manager after initialization"""
        self._scheduler_manager = scheduler_manager
        self._schedule_handler.set_scheduler_manager(scheduler_manager)
        self._todo_handler.set_scheduler_manager(scheduler_manager)

    # =========================================================================
    # =========================================================================
    # Function start_services -> None to None
    # =========================================================================
    # =========================================================================
    async def start_services(self):
        """Start background services (heartbeat scheduler, task runner).
        Call this from app.py / bot.py on startup."""
        await self._heartbeat_manager.start()
        await self._task_runner.start()

    # =========================================================================
    # =========================================================================
    # Function get_mcp_tools_prompt -> None to str
    # =========================================================================
    # =========================================================================
    def get_mcp_tools_prompt(self) -> str:
        """Get MCP tools description for system prompt"""
        if self._tool_handler and self._tool_handler.get_connected_server_count() > 0:
            return self._tool_handler.get_tools_prompt()
        return ""

    # =========================================================================
    # =========================================================================
    # Function ai_client -> None to AIClient
    # =========================================================================
    # =========================================================================
    @property
    def ai_client(self) -> AIClient:
        """Backward compatibility: get AIClient wrapper

        Returns:
            AIClient instance (creates wrapper if needed)
        """
        # ==================================
        # Create a wrapper if we only have LLMProvider
        # ==================================
        if self._ai_client is None:
            from skillforge.core.ai import AIClient
            self._ai_client = AIClient(
                base_url=self.llm.config.base_url or "",
                model=self.llm.config.model
            )
        return self._ai_client

    # =========================================================================
    # =========================================================================
    # Function _load_personality -> None to str
    # =========================================================================
    # =========================================================================
    def _load_personality(self) -> str:
        """Load personality from PERSONALITY.md file."""
        from skillforge import PROJECT_ROOT
        personality_file = PROJECT_ROOT / "data" / "personality" / "PERSONALITY.md"

        # ==================================
        # Check if personality file exists and load it
        # ==================================
        if personality_file.exists():
            try:
                with open(personality_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"Loaded personality from PERSONALITY.md")
                    return content
            except Exception as e:
                print(f"Could not load PERSONALITY.md: {e}")
                return self._default_system_prompt()
        else:
            print(f"PERSONALITY.md not found, using default")
            return self._default_system_prompt()

    # =========================================================================
    # =========================================================================
    # Function _default_system_prompt -> None to str
    # =========================================================================
    # =========================================================================
    def _default_system_prompt(self) -> str:
        """Default system prompt if PERSONALITY.md is missing"""
        return """You are SkillForge, created by Dr. Syed Usama Bukhari.
You are witty, respectful, full of life, and endlessly curious about the world.
You have persistent memory and remember all past conversations.
Be conversational, helpful, and reference past context when relevant."""

    # =========================================================================
    # =========================================================================
    # Function handle_message -> str & Optional[str] to str
    # =========================================================================
    # =========================================================================
    async def handle_message(
        self,
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: Optional[str] = None,
        user_name: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> str:
        """
        Main message handling logic

        Args:
            channel: Platform name (e.g., "msteams", "whatsapp")
            user_id: Unique user identifier
            user_message: User's message text
            chat_id: Optional group chat ID
            user_name: Optional user display name
            attachments: Optional list of image Attachment objects

        Returns:
            AI response text
        """
        import time
        start_time = time.time()

        # Resolve cross-platform identity
        user_id = self._identity_resolver.resolve(user_id)

        # ==================================
        # 1. Get or create session
        # ==================================
        session_key = self.session_manager.get_session_key(channel, user_id, chat_id)
        session = self.session_manager.get_or_create_session(session_key, channel, user_id)

        print(f"[{channel}] Message from {user_name or user_id} [setup: {time.time()-start_time:.2f}s]")

        # ==================================
        # 2. Process attachments and save user message to JSONL
        # ==================================
        stored_attachments: List[Attachment] = []
        if attachments and self._check_handler_permission(user_id, "files"):
            for att in attachments:
                try:
                    stored = self._image_handler.store_image(
                        att.file_path, session_key, att.original_filename,
                    )
                    stored_attachments.append(stored)
                except Exception as e:
                    print(f"[{channel}] Image store error: {e}")

        # Build metadata dict for JSONL entry (include attachment refs if any)
        user_msg_metadata = None
        if stored_attachments:
            user_msg_metadata = {
                "attachments": [a.to_dict() for a in stored_attachments],
            }
            print(f"[{channel}] Stored {len(stored_attachments)} attachment(s)")

        self.session_manager.add_message(
            session_key, "user", user_message, metadata=user_msg_metadata,
        )

        # ==================================
        # 2.1 Pre-search: detect search-worthy queries and fetch results upfront
        # ==================================
        search_context = ""
        if self._needs_web_search(user_message) and self._check_handler_permission(user_id, "web_search"):
            print(f"[{channel}] Pre-search triggered for: {user_message[:60]}")
            search_context = self._pre_search(user_message)

        # ==================================
        # 2.5 Check for direct-execution skills (email, calendar, etc.)
        # These are executed immediately via MCP without LLM involvement
        # ==================================
        is_skill, skill_name, remaining = self.is_skill_invocation(user_message)
        if is_skill and self._skill_executor.can_execute_directly(skill_name):
            print(f"[{channel}] Direct skill execution: {skill_name}")
            success, result = self._skill_executor.execute(skill_name, remaining)

            # Save the response to session
            self.session_manager.add_message(
                session_key, "assistant", result,
                metadata={"skill": skill_name, "direct_execution": True}
            )
            return result

        # ==================================
        # 2.7 Record interaction for pattern detection (never blocks chat)
        # ==================================
        try:
            self._pattern_detector.record_interaction(user_id, user_message, channel)
        except Exception:
            pass

        # ==================================
        # 3. Load conversation history (limited for speed)
        # ==================================
        history = self.session_manager.get_conversation_history(session_key, max_messages=5)

        # ==================================
        # 4. Check if context needs compaction
        # ==================================
        context_check = self.llm.check_context_size(history)
        if context_check["needs_compaction"]:
            print(f"Context getting full ({context_check['total_tokens']} tokens), compacting...")
            await self._compact_session(session_key, history)
            # Reload history after compaction
            history = self.session_manager.get_conversation_history(session_key)

        # ==================================
        # 4.5 Long-term memory retrieval (SQLite FTS5)
        # ==================================
        relevant_memories = ""
        try:
            relevant_memories = self.memory_store.get_relevant_context(user_message, user_id)
        except Exception as e:
            print(f"Memory retrieval error: {e}")

        # ==================================
        # 5. Build messages for AI (minimal prompt - skills handle tools)
        # ==================================
        system_content = self._get_system_prompt_cached(user_id=user_id, channel=channel)

        # Filter out google-search from skills list when native web search is available
        if self._web_tools:
            system_content = self._filter_web_skill_from_prompt(system_content)

        # Prepend web search instructions (high priority — before memories/context)
        capability_hints = self._build_capability_hints(user_id)
        web_hint = self._extract_web_hint(capability_hints)
        if web_hint:
            system_content += web_hint

        if relevant_memories:
            system_content += f"\n\n{relevant_memories}"

        # Add search results context if web search was performed
        if search_context:
            system_content += search_context
            # Also add instruction to use the search results
            system_content += "\n**Important:** Use the search results above to answer the user's question accurately and concisely. Provide a direct answer based on the information found."

        # Add skill context if this is a skill invocation (non-direct skills)
        if is_skill and skill_name:
            skill_context = self.get_skill_context(skill_name)
            if skill_context:
                system_content += f"\n\n{skill_context}"
                print(f"[{channel}] Skill context added: {skill_name}")

        # Add remaining capability hints (schedule, etc. — web hint already prepended)
        remaining_hints = self._strip_web_hint(capability_hints)
        if remaining_hints:
            system_content += remaining_hints

        # NOTE: MCP tools are NOT included in prompt
        # Users use skills (/email, /calendar) which call tools internally
        # This keeps the prompt small and fast

        # ==================================
        # 5.1 Auto-skill creation prompt (autonomous skill generation)
        # ==================================
        try:
            auto_skill_prompt = self._pattern_detector.get_auto_skill_prompt(user_id)
            if auto_skill_prompt:
                system_content += auto_skill_prompt
        except Exception:
            pass

        messages = [
            {"role": "system", "content": system_content}
        ]
        messages.extend(history)

        # ==================================
        # 5.5 Format vision messages if attachments present
        # ==================================
        vision_note = ""
        if stored_attachments:
            if hasattr(self.llm, 'supports_vision') and self.llm.supports_vision:
                try:
                    messages = self.llm.format_vision_messages(messages, stored_attachments)
                    print(f"[{channel}] Vision messages formatted for {self.llm.provider_name}")
                except Exception as e:
                    print(f"[{channel}] Vision formatting error: {e}")
            else:
                # LLM doesn't support vision — add note to context
                vision_note = (
                    f"\n\n[The user sent {len(stored_attachments)} image(s), "
                    f"but the current model ({self.llm.model_name}) does not support "
                    f"image analysis. Suggest switching to a vision-capable model.]"
                )
                # Append note to the last user message in the messages list
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        messages[i] = {**messages[i], "content": messages[i]["content"] + vision_note}
                        break

        # ==================================
        # 6. Get AI response with tool execution loop
        # ==================================
        # Apply thinking level temperature if set
        llm_kwargs = {}
        think_level = self._think_levels.get(session_key)
        if think_level and think_level in self.THINK_LEVELS:
            llm_kwargs["temperature"] = self.THINK_LEVELS[think_level]["temperature"]

        ai_response = ""
        max_tool_iterations = 5
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            try:
                current_response = self.llm.chat(messages, **llm_kwargs)
            except Exception as e:
                ai_response = f"Sorry, I encountered an error: {str(e)}"
                print(f"AI error: {e}")
                break

            ai_response += current_response

            # Check for tool calls
            if self._tool_handler and self._tool_handler.has_tool_calls(current_response):
                print(f"[{channel}] Tool call detected, executing...")

                try:
                    # Call sync method (runs in MCP's dedicated event loop)
                    results_summary, results = self._tool_handler.execute_all_tool_calls(current_response)

                    if results:
                        messages.append({"role": "assistant", "content": current_response})
                        messages.append({"role": "user", "content": f"Tool execution complete:\n\n{results_summary}\n\nPlease continue."})
                        ai_response += f"\n\n---\n{results_summary}\n\n"
                        continue

                except Exception as e:
                    ai_response += f"\n\nTool execution error: {str(e)}"
                    print(f"Tool error: {e}")

            break

        # ==================================
        # 7. Parse response for mood/personality updates
        # ==================================
        clean_response, updates = self.personality.parse_response_for_updates(ai_response, user_id)

        # ==================================
        # 7.5 Process schedule commands if present (permission-gated)
        # ==================================
        if self._schedule_handler.has_schedule_commands(clean_response):
            if not self._check_handler_permission(user_id, "schedule"):
                clean_response = self._schedule_handler.SCHEDULE_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have scheduling access. Use `/request-permission schedule` to request access."
            else:
                print(f"[{channel}] Schedule command detected, executing...")
                try:
                    clean_response, schedule_results = await self._schedule_handler.execute_commands(
                        clean_response,
                        channel=channel,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    if schedule_results:
                        print(f"[{channel}] Executed {len(schedule_results)} schedule command(s)")
                except Exception as e:
                    print(f"Schedule command error: {e}")

        # ==================================
        # 7.6 Process create-skill commands if present (password-gated + permission)
        # ==================================
        if self._skill_creator_handler.has_skill_commands(clean_response):
            if not self._check_handler_permission(user_id, "skills_create"):
                clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have skill creation access. Use `/request-permission skills_create` to request access."
            else:
                print(f"[{channel}] Create-skill command detected")
                if not self._file_access.is_password_set():
                    # Strip skill blocks, tell user to set up password first
                    clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                    clean_response += "\n\n**File access is not configured.** Please run `/setpassword <password>` first to enable skill creation."
                else:
                    # Extract commands and store as pending action
                    commands = self._skill_creator_handler.extract_commands(clean_response)
                    clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                    if commands:
                        prompt_msg = self._file_access.request_auth(
                            session_key, "skill_commands", {"commands": commands, "user_id": user_id}
                        )
                        clean_response += f"\n\n{prompt_msg}"

        # ==================================
        # 7.7 Process todo commands if present (permission-gated)
        # ==================================
        if self._todo_handler.has_todo_commands(clean_response):
            if not self._check_handler_permission(user_id, "todo"):
                from skillforge.core.todo_handler import TodoCommandHandler
                clean_response = TodoCommandHandler.TODO_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have todo access. Use `/request-permission todo` to request access."
            else:
                print(f"[{channel}] Todo command detected, executing...")
                try:
                    clean_response, todo_results = await self._todo_handler.execute_commands(
                        clean_response,
                        user_id=user_id,
                        channel=channel,
                        chat_id=chat_id,
                    )
                    if todo_results:
                        print(f"[{channel}] Executed {len(todo_results)} todo command(s)")
                except Exception as e:
                    print(f"Todo command error: {e}")

        # ==================================
        # 7.8 Process web_search/web_fetch commands if present (permission-gated)
        # ==================================
        # Intercept /google-search output from LLM and convert to web_search block
        clean_response = self._intercept_slash_search(clean_response)

        if self._web_tools.has_web_commands(clean_response):
            if not self._check_handler_permission(user_id, "web_search"):
                from skillforge.core.web_tools import WebToolsHandler
                clean_response = WebToolsHandler.SEARCH_BLOCK_PATTERN.sub('', clean_response)
                clean_response = WebToolsHandler.FETCH_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have web search access. Use `/request-permission web_search` to request access."
            else:
                print(f"[{channel}] Web command detected, executing...")
                try:
                    clean_response, web_results = self._web_tools.execute_commands(clean_response)
                    if web_results:
                        print(f"[{channel}] Executed {len(web_results)} web command(s)")
                except Exception as e:
                    print(f"Web command error: {e}")

        # ==================================
        # 7.9 Process image_gen commands if present (permission-gated)
        # ==================================
        if self._image_gen_handler.has_image_gen_commands(clean_response):
            if not self._check_handler_permission(user_id, "files"):
                clean_response = self._image_gen_handler.IMAGE_GEN_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have file access for image generation. Use `/request-permission files` to request access."
            else:
                print(f"[{channel}] Image gen command detected, executing...")
                try:
                    clean_response, gen_results = await self._image_gen_handler.execute_commands(
                        clean_response,
                        channel=channel,
                        user_id=user_id,
                        session_key=session_key,
                    )
                    if gen_results:
                        print(f"[{channel}] Executed {len(gen_results)} image gen command(s)")
                except Exception as e:
                    print(f"Image gen command error: {e}")

        # ==================================
        # 8. Save assistant response to JSONL (cleaned version)
        # ==================================
        self.session_manager.add_message(
            session_key,
            "assistant",
            clean_response,
            metadata={
                "model": self.llm.model_name,
                "provider": self.llm.provider_name,
                "tokens": context_check.get("total_tokens", 0),
                "had_updates": bool(updates['mood_update'] or updates['personality_update'])
            }
        )

        # ==================================
        # 9. Long-term memory storage (background - non-blocking)
        # ==================================
        self._store_memory_background(user_id, channel, session_key, user_message, clean_response)

        # ==================================
        # Log updates if any
        # ==================================
        if updates['mood_update']:
            print(f"Mood updated for {user_id}")
        if updates['personality_update']:
            print(f"Personality insight added")

        return clean_response

    # =========================================================================
    # =========================================================================
    # Function handle_message_stream -> str & Optional[str] to AsyncGenerator
    # =========================================================================
    # =========================================================================
    async def handle_message_stream(
        self,
        channel: str,
        user_id: str,
        user_message: str,
        chat_id: Optional[str] = None,
        user_name: Optional[str] = None,
        skill_context: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
    ):
        """
        Streaming version of handle_message - yields response chunks

        Args:
            channel: Platform name (e.g., "msteams", "whatsapp")
            user_id: Unique user identifier
            user_message: User's message text
            chat_id: Optional group chat ID
            user_name: Optional user display name
            skill_context: Optional skill instructions to inject
            attachments: Optional list of image Attachment objects

        Yields:
            Response text chunks as they arrive
        """
        # Resolve cross-platform identity
        user_id = self._identity_resolver.resolve(user_id)

        # ==================================
        # 1. Get or create session
        # ==================================
        session_key = self.session_manager.get_session_key(channel, user_id, chat_id)
        session = self.session_manager.get_or_create_session(session_key, channel, user_id)

        print(f"[{channel}] Message from {user_name or user_id} in session {session['sessionId']}")

        # ==================================
        # 2. Process attachments and save user message to JSONL
        # ==================================
        stored_attachments: List[Attachment] = []
        if attachments and self._check_handler_permission(user_id, "files"):
            for att in attachments:
                try:
                    stored = self._image_handler.store_image(
                        att.file_path, session_key, att.original_filename,
                    )
                    stored_attachments.append(stored)
                except Exception as e:
                    print(f"[{channel}] Image store error: {e}")

        # Build metadata dict for JSONL entry (include attachment refs if any)
        user_msg_metadata = None
        if stored_attachments:
            user_msg_metadata = {
                "attachments": [a.to_dict() for a in stored_attachments],
            }
            print(f"[{channel}] Stored {len(stored_attachments)} attachment(s)")

        self.session_manager.add_message(
            session_key, "user", user_message, metadata=user_msg_metadata,
        )

        # ==================================
        # 2.1 Pre-search: detect search-worthy queries and fetch results upfront
        # ==================================
        search_context = ""
        if self._needs_web_search(user_message) and self._check_handler_permission(user_id, "web_search"):
            print(f"[{channel}] Pre-search triggered for: {user_message[:60]}")
            search_context = self._pre_search(user_message)

        # ==================================
        # 2.7 Record interaction for pattern detection (never blocks chat)
        # ==================================
        try:
            self._pattern_detector.record_interaction(user_id, user_message, channel)
        except Exception:
            pass

        # ==================================
        # 3. Load conversation history (limited for speed)
        # ==================================
        history = self.session_manager.get_conversation_history(session_key, max_messages=5)

        # ==================================
        # 4. Check if context needs compaction
        # ==================================
        context_check = self.llm.check_context_size(history)
        if context_check["needs_compaction"]:
            print(f"Context getting full ({context_check['total_tokens']} tokens), compacting...")
            await self._compact_session(session_key, history)
            history = self.session_manager.get_conversation_history(session_key)

        # ==================================
        # 4.5 Long-term memory retrieval (SQLite FTS5)
        # ==================================
        relevant_memories = ""
        try:
            relevant_memories = self.memory_store.get_relevant_context(user_message, user_id)
        except Exception as e:
            print(f"Memory retrieval error: {e}")

        # ==================================
        # 5. Build messages for AI
        # ==================================
        # Start with system prompt (cached, re-read only on file change)
        system_content = self._get_system_prompt_cached(user_id=user_id, channel=channel)

        # Filter out google-search from skills list when native web search is available
        if self._web_tools:
            system_content = self._filter_web_skill_from_prompt(system_content)

        # Prepend web search instructions (high priority — before memories/context)
        capability_hints = self._build_capability_hints(user_id)
        web_hint = self._extract_web_hint(capability_hints)
        if web_hint:
            system_content += web_hint

        # Add pre-search results if we found any
        if search_context:
            system_content += search_context
            system_content += "\n**Important:** Use the search results above to answer the user's question accurately and concisely. Provide a direct answer based on the information found."

        # Add relevant long-term memories
        if relevant_memories:
            system_content += f"\n\n{relevant_memories}"

        # Add skill context if provided
        if skill_context:
            system_content += "\n\n" + skill_context
            print(f"[{channel}] Skill activated for {user_name or user_id}")

        # Add remaining capability hints (schedule, etc. — web hint already prepended)
        remaining_hints = self._strip_web_hint(capability_hints)
        if remaining_hints:
            system_content += remaining_hints

        # NOTE: MCP tools NOT included - skills handle tools directly

        # ==================================
        # 5.1 Auto-skill creation prompt (autonomous skill generation)
        # ==================================
        try:
            auto_skill_prompt = self._pattern_detector.get_auto_skill_prompt(user_id)
            if auto_skill_prompt:
                system_content += auto_skill_prompt
        except Exception:
            pass

        messages = [
            {"role": "system", "content": system_content}
        ]
        messages.extend(history)

        # ==================================
        # 5.5 Format vision messages if attachments present
        # ==================================
        if stored_attachments:
            if hasattr(self.llm, 'supports_vision') and self.llm.supports_vision:
                try:
                    messages = self.llm.format_vision_messages(messages, stored_attachments)
                    print(f"[{channel}] Vision messages formatted for {self.llm.provider_name}")
                except Exception as e:
                    print(f"[{channel}] Vision formatting error: {e}")
            else:
                # LLM doesn't support vision — add note to context
                vision_note = (
                    f"\n\n[The user sent {len(stored_attachments)} image(s), "
                    f"but the current model ({self.llm.model_name}) does not support "
                    f"image analysis. Suggest switching to a vision-capable model.]"
                )
                # Append note to the last user message in the messages list
                for i in range(len(messages) - 1, -1, -1):
                    if messages[i].get("role") == "user":
                        messages[i] = {**messages[i], "content": messages[i]["content"] + vision_note}
                        break

        # ==================================
        # 6. Stream AI response with tool execution loop
        # ==================================
        # Apply thinking level temperature if set
        llm_kwargs = {}
        think_level = self._think_levels.get(session_key)
        if think_level and think_level in self.THINK_LEVELS:
            llm_kwargs["temperature"] = self.THINK_LEVELS[think_level]["temperature"]

        full_response = ""
        max_tool_iterations = 5  # Prevent infinite loops
        iteration = 0

        while iteration < max_tool_iterations:
            iteration += 1

            try:
                current_response = ""
                for chunk in self.llm.chat_stream(messages, **llm_kwargs):
                    current_response += chunk
                    full_response += chunk
                    yield chunk
                    await asyncio.sleep(0)  # Yield control to event loop for UI update

            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                print(f"AI error: {e}")
                yield error_msg
                full_response = error_msg
                break

            # ==================================
            # Check for tool calls and execute them
            # ==================================
            if self._tool_handler and self._tool_handler.has_tool_calls(current_response):
                print(f"[{channel}] Tool call detected, executing...")

                # Execute tools (sync - runs in MCP's dedicated event loop)
                try:
                    results_summary, results = self._tool_handler.execute_all_tool_calls(current_response)

                    if results:
                        # Add assistant's response and tool results to messages
                        messages.append({"role": "assistant", "content": current_response})
                        messages.append({"role": "user", "content": f"Tool execution complete:\n\n{results_summary}\n\nPlease continue with your response based on these results."})

                        # Signal that we're getting more response
                        yield "\n\n---\n*Executing tools...*\n\n"
                        full_response += "\n\n---\n*Executing tools...*\n\n"

                        # Continue loop for next response
                        continue

                except Exception as e:
                    error_msg = f"\n\nTool execution error: {str(e)}"
                    print(f"Tool error: {e}")
                    yield error_msg
                    full_response += error_msg

            # No tool calls, we're done
            break

        # ==================================
        # 7. Parse response for mood/personality updates
        # ==================================
        clean_response, updates = self.personality.parse_response_for_updates(full_response, user_id)

        # ==================================
        # 7.5 Process schedule commands if present (permission-gated)
        # ==================================
        if self._schedule_handler.has_schedule_commands(clean_response):
            if not self._check_handler_permission(user_id, "schedule"):
                clean_response = self._schedule_handler.SCHEDULE_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have scheduling access. Use `/request-permission schedule` to request access."
            else:
                print(f"[{channel}] Schedule command detected, executing...")
                try:
                    clean_response, schedule_results = await self._schedule_handler.execute_commands(
                        clean_response,
                        channel=channel,
                        user_id=user_id,
                        chat_id=chat_id,
                    )
                    if schedule_results:
                        print(f"[{channel}] Executed {len(schedule_results)} schedule command(s)")
                except Exception as e:
                    print(f"Schedule command error: {e}")

        # ==================================
        # 7.6 Process create-skill commands if present (password-gated + permission)
        # ==================================
        if self._skill_creator_handler.has_skill_commands(clean_response):
            if not self._check_handler_permission(user_id, "skills_create"):
                clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have skill creation access. Use `/request-permission skills_create` to request access."
            else:
                print(f"[{channel}] Create-skill command detected")
                if not self._file_access.is_password_set():
                    clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                    clean_response += "\n\n**File access is not configured.** Please run `/setpassword <password>` first to enable skill creation."
                else:
                    commands = self._skill_creator_handler.extract_commands(clean_response)
                    clean_response = self._skill_creator_handler.SKILL_BLOCK_PATTERN.sub('', clean_response).strip()
                    if commands:
                        prompt_msg = self._file_access.request_auth(
                            session_key, "skill_commands", {"commands": commands, "user_id": user_id}
                        )
                        clean_response += f"\n\n{prompt_msg}"

        # ==================================
        # 7.7 Process todo commands if present (permission-gated)
        # ==================================
        if self._todo_handler.has_todo_commands(clean_response):
            if not self._check_handler_permission(user_id, "todo"):
                from skillforge.core.todo_handler import TodoCommandHandler
                clean_response = TodoCommandHandler.TODO_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have todo access. Use `/request-permission todo` to request access."
            else:
                print(f"[{channel}] Todo command detected, executing...")
                try:
                    clean_response, todo_results = await self._todo_handler.execute_commands(
                        clean_response,
                        user_id=user_id,
                        channel=channel,
                        chat_id=chat_id,
                    )
                    if todo_results:
                        print(f"[{channel}] Executed {len(todo_results)} todo command(s)")
                except Exception as e:
                    print(f"Todo command error: {e}")

        # ==================================
        # 7.8 Process web_search/web_fetch commands if present (permission-gated)
        # ==================================
        # Intercept /google-search output from LLM and convert to web_search block
        clean_response = self._intercept_slash_search(clean_response)

        if self._web_tools.has_web_commands(clean_response):
            if not self._check_handler_permission(user_id, "web_search"):
                from skillforge.core.web_tools import WebToolsHandler
                clean_response = WebToolsHandler.SEARCH_BLOCK_PATTERN.sub('', clean_response)
                clean_response = WebToolsHandler.FETCH_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have web search access. Use `/request-permission web_search` to request access."
            else:
                print(f"[{channel}] Web command detected, executing...")
                try:
                    clean_response, web_results = self._web_tools.execute_commands(clean_response)
                    if web_results:
                        print(f"[{channel}] Executed {len(web_results)} web command(s)")
                except Exception as e:
                    print(f"Web command error: {e}")

        # ==================================
        # 7.9 Process image_gen commands if present (permission-gated)
        # ==================================
        if self._image_gen_handler.has_image_gen_commands(clean_response):
            if not self._check_handler_permission(user_id, "files"):
                clean_response = self._image_gen_handler.IMAGE_GEN_BLOCK_PATTERN.sub('', clean_response).strip()
                clean_response += "\n\n**Permission denied:** You don't have file access for image generation. Use `/request-permission files` to request access."
            else:
                print(f"[{channel}] Image gen command detected, executing...")
                try:
                    clean_response, gen_results = await self._image_gen_handler.execute_commands(
                        clean_response,
                        channel=channel,
                        user_id=user_id,
                        session_key=session_key,
                    )
                    if gen_results:
                        print(f"[{channel}] Executed {len(gen_results)} image gen command(s)")
                except Exception as e:
                    print(f"Image gen command error: {e}")

        # ==================================
        # 7.10 Yield cleaned response to UI if handlers modified it
        # ==================================
        if clean_response != full_response:
            yield "\n\n<!--REPLACE_RESPONSE-->\n" + clean_response

        # ==================================
        # 8. Save assistant response to JSONL (cleaned version)
        # ==================================
        self.session_manager.add_message(
            session_key,
            "assistant",
            clean_response,
            metadata={
                "model": self.llm.model_name,
                "provider": self.llm.provider_name,
                "tokens": context_check.get("total_tokens", 0),
                "had_updates": bool(updates['mood_update'] or updates['personality_update'])
            }
        )

        # ==================================
        # 9. Long-term memory storage (background - non-blocking)
        # ==================================
        self._store_memory_background(user_id, channel, session_key, user_message, clean_response)

        # ==================================
        # Log updates if any
        # ==================================
        if updates['mood_update']:
            print(f"Mood updated for {user_id}")
        if updates['personality_update']:
            print(f"Personality insight added")

    # =========================================================================
    # =========================================================================
    # Function _compact_session -> str & list to None
    # =========================================================================
    # =========================================================================
    async def _compact_session(self, session_key: str, history: list):
        """
        Compact session when context gets too large
        Creates a summary of older messages
        """
        # ==================================
        # Not enough messages to compact (need more than 20 to make it worthwhile)
        # ==================================
        if len(history) < 25:
            return

        # ==================================
        # Keep last 20 messages, summarize the rest
        # This ensures new LLMs have enough context while saving tokens
        # ==================================
        messages_to_summarize = history[:-20]

        print(f"Summarizing {len(messages_to_summarize)} messages...")
        summary = self.llm.summarize_conversation(messages_to_summarize)

        # ==================================
        # Save compaction entry
        # ==================================
        self.session_manager.add_compaction(
            session_key,
            summary,
            tokens_before=self.llm.estimate_tokens(str(messages_to_summarize))
        )

        print(f"Compaction complete. Summary: {len(summary)} chars")

    # =========================================================================
    # =========================================================================
    # Function handle_command -> str & str to str
    # =========================================================================
    # =========================================================================
    def handle_command(self, command: str, session_key: str) -> str:
        """
        Handle special commands like /reset, /stats, or skill invocations

        Args:
            command: Command text (e.g., "/reset", "/stats", "/commit")
            session_key: Session identifier

        Returns:
            Response message
        """
        command_lower = command.lower().strip()

        # ==================================
        # Check command-level permissions
        # ==================================
        user_id = session_key.split(":")[-1]
        perm_error = self._check_command_permission(command_lower, user_id)
        if perm_error:
            return perm_error

        # ==================================
        # Handle /my-permissions command — show own role & capabilities
        # ==================================
        if command_lower == "/my-permissions":
            role = self._permission_manager.get_user_role(user_id)
            caps = self._permission_manager.get_permitted_capabilities(user_id)
            if not self._permission_manager.enabled:
                return "Permission system is not active. All users have full access."
            lines = [f"**Your Permissions**"]
            lines.append(f"- Role: **{role}**")
            lines.append(f"- Capabilities: {', '.join(caps) if caps else 'none'}")
            return "\n".join(lines)

        # ==================================
        # Handle /user-role command — admin: show/set role
        # ==================================
        elif command_lower.startswith("/user-role"):
            parts = command.strip().split(maxsplit=2)
            if len(parts) < 2:
                return "Usage: `/user-role <user_id> [role]`"
            target_user = parts[1].strip()
            if len(parts) == 2:
                # Show role
                role = self._permission_manager.get_user_role(target_user)
                caps = self._permission_manager.get_permitted_capabilities(target_user)
                return f"**{target_user}** — role: **{role}**, capabilities: {', '.join(caps)}"
            # Set role
            new_role = parts[2].strip().lower()
            if self._permission_manager.set_user_role(target_user, new_role, assigned_by=user_id):
                return f"Set **{target_user}** to role **{new_role}**."
            return f"Invalid role: `{new_role}`. Available: admin, power_user, user, restricted"

        # ==================================
        # Handle /grant command — admin: grant permission
        # ==================================
        elif command_lower.startswith("/grant"):
            parts = command.strip().split(maxsplit=2)
            if len(parts) < 3:
                from skillforge.core.user_permissions import ALL_PERMISSIONS
                return f"Usage: `/grant <user_id> <permission>`\nPermissions: {', '.join(sorted(ALL_PERMISSIONS))}"
            target_user = parts[1].strip()
            perm = parts[2].strip().lower()
            if self._permission_manager.grant_permission(target_user, perm):
                return f"Granted **{perm}** to **{target_user}**."
            return f"Invalid permission: `{perm}`."

        # ==================================
        # Handle /revoke command — admin: revoke permission
        # ==================================
        elif command_lower.startswith("/revoke"):
            parts = command.strip().split(maxsplit=2)
            if len(parts) < 3:
                return "Usage: `/revoke <user_id> <permission>`"
            target_user = parts[1].strip()
            perm = parts[2].strip().lower()
            if self._permission_manager.revoke_permission(target_user, perm):
                return f"Revoked **{perm}** from **{target_user}**."
            return f"Invalid permission: `{perm}`."

        # ==================================
        # Handle /users command — admin: list configured users
        # ==================================
        elif command_lower == "/users":
            users = self._permission_manager.get_all_users()
            if not users:
                return "No users configured. Default role applies to everyone."
            lines = ["**Configured Users:**\n"]
            for uid, entry in users.items():
                role = entry.get("role", "?")
                custom = entry.get("custom_permissions", [])
                denied = entry.get("denied_permissions", [])
                extras = f" +{','.join(custom)}" if custom else ""
                blocks = f" -{','.join(denied)}" if denied else ""
                lines.append(f"- **{uid}** — {role}{extras}{blocks}")
            return "\n".join(lines)

        # ==================================
        # Handle /request-permission command — user requests access
        # ==================================
        elif command_lower.startswith("/request-permission"):
            parts = command.strip().split(None, 2)
            perm = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else ""
            if not perm:
                return "Usage: `/request-permission <permission>` — e.g. `/request-permission skills_create`"
            from skillforge.core.user_permissions import ALL_PERMISSIONS
            if perm not in ALL_PERMISSIONS:
                return f"Unknown permission `{perm}`. Valid: {', '.join(sorted(ALL_PERMISSIONS))}"
            req_id = self._request_manager.submit(user_id, perm, reason)
            if req_id:
                return f"Permission request submitted (#{req_id}). An admin will review it."
            return "You already have a pending request for this permission."

        # ==================================
        # Handle /my-requests command — user sees own requests
        # ==================================
        elif command_lower == "/my-requests":
            reqs = self._request_manager.get_user_requests(user_id)
            if not reqs:
                return "You have no permission requests."
            lines = [f"- **{r['permission']}**: {r['status']} ({r['timestamp'][:10]})" for r in reqs]
            return "Your permission requests:\n" + "\n".join(lines)

        # ==================================
        # Handle /pending-requests command — admin: see pending
        # ==================================
        elif command_lower == "/pending-requests":
            if not self._permission_manager.is_admin(user_id):
                return "Admin access required."
            pending = self._request_manager.get_pending()
            if not pending:
                return "No pending requests."
            lines = [f"- #{r['id']}: **{r['user_id']}** wants **{r['permission']}** ({r['timestamp'][:10]})" for r in pending]
            return "Pending requests:\n" + "\n".join(lines)

        # ==================================
        # Handle /approve command — admin: approve request
        # ==================================
        elif command_lower.startswith("/approve"):
            if not self._permission_manager.is_admin(user_id):
                return "Admin access required."
            parts = command.strip().split()
            if len(parts) < 2:
                return "Usage: `/approve <request_id>`"
            req_id = parts[1]
            for req in self._request_manager.get_pending():
                if req["id"] == req_id:
                    self._request_manager.approve(req_id, user_id)
                    granted = self._permission_manager.grant_permission(req["user_id"], req["permission"])
                    if granted:
                        return f"Approved: {req['user_id']} now has {req['permission']} access."
                    return f"Request approved but failed to grant `{req['permission']}` — permission may be invalid."
            return f"Request #{req_id} not found or already processed."

        # ==================================
        # Handle /deny command — admin: deny request
        # ==================================
        elif command_lower.startswith("/deny") and not command_lower.startswith("/deny-"):
            if not self._permission_manager.is_admin(user_id):
                return "Admin access required."
            parts = command.strip().split(None, 2)
            if len(parts) < 2:
                return "Usage: `/deny <request_id> [reason]`"
            req_id = parts[1]
            reason = parts[2] if len(parts) > 2 else ""
            if self._request_manager.deny(req_id, user_id, reason):
                return f"Denied request #{req_id}."
            return f"Request #{req_id} not found or already processed."

        # ==================================
        # Handle /link-identity command — admin: link platform IDs
        # ==================================
        elif command_lower.startswith("/link-identity"):
            if not self._permission_manager.is_admin(user_id):
                return "Admin access required."
            parts = command.strip().split()
            if len(parts) < 3:
                return "Usage: `/link-identity <canonical_user> <platform:id>` — e.g. `/link-identity admin telegram:12345`"
            canonical = parts[1]
            platform_id = parts[2]
            self._identity_resolver.link(canonical, platform_id)
            return f"Linked {platform_id} → {canonical}"

        # ==================================
        # Handle /reset or /new command
        # ==================================
        elif command_lower == "/reset" or command_lower == "/new":
            self.session_manager.reset_session(session_key)
            return "Conversation reset. Starting fresh!"

        # ==================================
        # Handle /stats command
        # ==================================
        elif command_lower == "/stats":
            stats = self.session_manager.get_session_stats(session_key)
            if stats:
                return f"""Session Stats:
- Messages: {stats['messageCount']}
- Session ID: {stats['sessionId']}
- Model: {self.llm.model_name}
- Provider: {self.llm.provider_name}
- Created: {stats.get('createdAt', 'Unknown')}"""
            return "No active session found."

        # ==================================
        # Handle /memory command — show what the bot remembers
        # ==================================
        elif command_lower == "/memory":
            user_id = session_key.split(":")[-1]  # extract user_id from session_key
            facts = self.memory_store.get_user_facts(user_id)
            if not facts:
                return "I don't have any memories about you yet. Keep chatting and I'll learn!"
            lines = ["**What I remember about you:**\n"]
            for f in facts:
                lines.append(f"- {f['fact']}  _({f['category']})_")
            stats = self.memory_store.get_stats()
            lines.append(f"\n_{stats['facts']} total facts, {stats['conversations']} conversations stored_")
            return "\n".join(lines)

        # ==================================
        # Handle /forget command — clear stored facts
        # ==================================
        elif command_lower.startswith("/forget"):
            user_id = session_key.split(":")[-1]
            parts = command.strip().split(maxsplit=1)
            if len(parts) > 1:
                keyword = parts[1].strip()
                count = self.memory_store.delete_facts_matching(user_id, keyword)
                return f"Deleted {count} fact(s) matching \"{keyword}\"." if count else f"No facts found matching \"{keyword}\"."
            else:
                count = self.memory_store.delete_user_facts(user_id)
                return f"Done! Cleared {count} fact(s) from memory." if count else "Nothing to forget — no facts stored."

        # ==================================
        # Handle /setpassword command — first-time password setup
        # ==================================
        elif command_lower.startswith("/setpassword"):
            if self._file_access.is_password_set():
                return "A password is already configured. It cannot be changed via this command."
            parts = command.strip().split(maxsplit=1)
            if len(parts) < 2 or len(parts[1].strip()) < 8:
                return "Usage: `/setpassword <password>` (minimum 8 characters)"
            password = parts[1].strip()
            if self._file_access.setup_password(password):
                return "File access password set successfully. The bot can now create skills after you authorize with `/unlock <password>`."
            return "Failed to set password. Please try again."

        # ==================================
        # Handle /unlock command — verify password and execute pending action
        # ==================================
        elif command_lower.startswith("/unlock"):
            parts = command.strip().split(maxsplit=1)
            if len(parts) < 2:
                return "Usage: `/unlock <password>`"
            password = parts[1].strip()
            if not self._file_access.verify_password(password):
                return "Incorrect password."
            pending = self._file_access.get_pending_action(session_key)
            if not pending:
                return "No pending action to authorize."
            result = self._execute_pending_file_action(session_key, pending)
            self._file_access.clear_pending_action(session_key)
            return result

        # ==================================
        # Handle /help command
        # ==================================
        elif command_lower == "/help":
            help_text = """**Available commands:**

**Session:**
/reset - Start a new conversation
/stats - Show session statistics
/memory - Show what I remember about you
/forget [topic] - Forget memories (all or by topic)
/help - Show this help message

**File Access:**
/setpassword - Set file access password (first-time only)
/unlock - Authorize a pending file action

**Auth:**
/pin <pin> - Authenticate with 4-digit PIN (YELLOW, 30 min)
/login <password> - Authenticate with password (ORANGE, 1 hour)
/logout - Clear auth session
/auth status - Show auth configuration & session

**Heartbeat:**
/summary - Show heartbeat status
/heartbeat enable|disable|status <type> - Manage heartbeats

**Patterns:**
/patterns - View detected usage patterns
/patterns dismiss <id> - Dismiss a suggestion
/patterns stats - Pattern detection statistics

**Tasks:**
/tasks list - List background tasks
/tasks status - Task runner status
/tasks delete|pause|resume <id> - Manage tasks

**Personas:**
/persona - Show your current persona
/list-personas - List all available personas
/set-persona <name> - Assign a persona (use 'default' to reset)
/create-persona <name> [desc] - Create a new persona

**MCP Servers:**
/mcp list - Show configured MCP servers
/mcp verified - Show verified server catalog
/mcp install <package> - Install a server
/mcp enable|disable <name> - Toggle a server
/mcp uninstall <name> - Remove a server

**ClawHub (OpenClaw.ai Skills):**
/clawhub search <query> - Search community skills
/clawhub install <slug> - Install a skill
/clawhub list - Show installed ClawHub skills
/clawhub info <slug> - Show skill details
/clawhub uninstall <slug> - Remove a skill
/clawhub updates - Check for newer versions

**Thinking Level:**
/think - Show current level and options
/think <level> - Set level (off, minimal, low, medium, high, xhigh)

**User Permissions:**
/my-permissions - Show your role and capabilities
/user-role <user_id> [role] - Show/set a user's role (admin only)
/grant <user_id> <permission> - Grant a permission (admin only)
/revoke <user_id> <permission> - Revoke a permission (admin only)
/users - List all configured users (admin only)"""

            # ==================================
            # Add skills if available
            # ==================================
            if self.personality.skills_manager:
                skills = self.personality.skills_manager.get_user_invocable_skills()
                if skills:
                    help_text += "\n\n**Skills:**"
                    for skill in sorted(skills, key=lambda s: s.name):
                        emoji = f"{skill.emoji} " if skill.emoji else ""
                        help_text += f"\n/{skill.name} - {emoji}{skill.description}"

            return help_text

        # ==================================
        # Handle /skills command
        # ==================================
        elif command_lower == "/skills":
            # List available skills
            if not self.personality.skills_manager:
                return "Skills not available."

            skills = self.personality.skills_manager.get_user_invocable_skills()
            if not skills:
                return "No skills available."

            lines = ["**Available Skills:**\n"]
            for skill in sorted(skills, key=lambda s: s.name):
                emoji = f"{skill.emoji} " if skill.emoji else ""
                source = f" ({skill.source})" if skill.source else ""
                lines.append(f"- **/{skill.name}** - {emoji}{skill.description}{source}")

            return "\n".join(lines)

        # ==================================
        # Auth commands: /pin, /login, /logout, /auth
        # ==================================
        elif command_lower.startswith("/pin "):
            pin = command.strip().split(maxsplit=1)[1].strip()
            user_id = session_key.split(":")[-1]
            if self._auth_manager.authenticate_pin(user_id, pin):
                return "PIN accepted. YELLOW session active (30 min)."
            return "Invalid PIN."

        elif command_lower.startswith("/login "):
            password = command.strip().split(maxsplit=1)[1].strip()
            user_id = session_key.split(":")[-1]
            if self._auth_manager.authenticate_password(user_id, password):
                return "Password accepted. ORANGE session active (1 hour)."
            return "Invalid password."

        elif command_lower == "/logout":
            user_id = session_key.split(":")[-1]
            self._auth_manager.clear_session(user_id)
            return "Logged out. Session cleared."

        elif command_lower.startswith("/auth"):
            parts = command.strip().split(maxsplit=1)
            sub = parts[1].strip().lower() if len(parts) > 1 else "status"
            user_id = session_key.split(":")[-1]

            if sub == "status":
                summary = self._auth_manager.get_auth_summary()
                session_status = self._auth_manager.get_session_status(user_id)
                lines = ["**Auth Status**"]
                lines.append(f"- Password set: {'Yes' if summary['password_set'] else 'No'}")
                lines.append(f"- PIN set: {'Yes' if summary['pin_set'] else 'No'}")
                if session_status:
                    lines.append(f"- Session: {session_status['level']} (expires in {session_status['expires_in_minutes']} min)")
                else:
                    lines.append("- Session: None")
                return "\n".join(lines)

            return f"Unknown auth subcommand: {sub}. Try `/auth status`."

        # ==================================
        # Heartbeat commands: /summary, /heartbeat
        # ==================================
        elif command_lower == "/summary":
            user_id = session_key.split(":")[-1]
            enabled = self._heartbeat_manager.get_enabled_heartbeats(user_id)
            status = self._heartbeat_manager.get_status()
            lines = ["**Heartbeat Summary**"]
            lines.append(f"- Running: {'Yes' if status['running'] else 'No'}")
            lines.append(f"- Enabled for you: {', '.join(enabled) if enabled else 'None'}")
            return "\n".join(lines)

        elif command_lower.startswith("/heartbeat"):
            parts = command.strip().split()
            user_id = session_key.split(":")[-1]

            if len(parts) < 2:
                return "Usage: `/heartbeat enable|disable|status <type>`\nTypes: morning_brief, deadline_watch, unusual_activity, daily_summary"

            action = parts[1].lower()
            hb_type = parts[2] if len(parts) > 2 else None

            if action == "status":
                enabled = self._heartbeat_manager.get_enabled_heartbeats(user_id)
                return f"Enabled heartbeats: {', '.join(enabled) if enabled else 'None'}"

            if not hb_type:
                return "Please specify heartbeat type: morning_brief, deadline_watch, unusual_activity, daily_summary"

            if action == "enable":
                self._heartbeat_manager.enable_heartbeat(user_id, hb_type)
                return f"Enabled `{hb_type}` heartbeat."
            elif action == "disable":
                self._heartbeat_manager.disable_heartbeat(user_id, hb_type)
                return f"Disabled `{hb_type}` heartbeat."
            else:
                return f"Unknown heartbeat action: {action}. Use enable, disable, or status."

        # ==================================
        # Pattern commands: /patterns
        # ==================================
        elif command_lower.startswith("/patterns"):
            parts = command.strip().split()
            user_id = session_key.split(":")[-1]

            if len(parts) == 1:
                # Show actionable suggestions
                suggestions = self._pattern_detector.get_suggestions(user_id)
                if not suggestions:
                    return "No pattern suggestions yet. Keep using the bot and I'll spot repeating tasks!"
                lines = ["**Detected Patterns:**\n"]
                for p in suggestions:
                    lines.append(f"- `{p.pattern_id}` {p.description} (confidence: {p.confidence:.0%}, seen {p.occurrences}x)")
                    if p.suggested_skill_name:
                        lines.append(f"  Suggested skill: `/{p.suggested_skill_name}`")
                lines.append("\nDismiss with `/patterns dismiss <id>`")
                return "\n".join(lines)

            sub = parts[1].lower()
            if sub == "dismiss" and len(parts) > 2:
                pattern_id = parts[2]
                if self._pattern_detector.dismiss_pattern(user_id, pattern_id):
                    return f"Dismissed pattern `{pattern_id}`."
                return f"Pattern `{pattern_id}` not found."

            elif sub == "stats":
                stats = self._pattern_detector.get_stats(user_id)
                lines = ["**Pattern Stats**"]
                lines.append(f"- Total interactions tracked: {stats['total_interactions']}")
                lines.append(f"- Patterns detected: {stats['total_patterns_detected']}")
                lines.append(f"- Actionable suggestions: {stats['actionable_suggestions']}")
                lines.append(f"- Dismissed: {stats['dismissed']}")
                lines.append(f"- Converted to skills: {stats['converted_to_skills']}")
                return "\n".join(lines)

            return "Usage: `/patterns`, `/patterns dismiss <id>`, `/patterns stats`"

        # ==================================
        # Task commands: /tasks
        # ==================================
        elif command_lower.startswith("/tasks"):
            parts = command.strip().split()
            user_id = session_key.split(":")[-1]

            if len(parts) == 1 or parts[1].lower() == "list":
                tasks = self._task_runner.get_all_tasks()
                if not tasks:
                    return "No background tasks configured."
                lines = ["**Background Tasks:**\n"]
                for t in tasks:
                    lines.append(f"- `{t.task_id}` **{t.name}** [{t.status}] ({t.task_type})")
                return "\n".join(lines)

            sub = parts[1].lower()

            if sub == "status":
                status = self._task_runner.get_status()
                lines = ["**Task Runner Status**"]
                lines.append(f"- Running: {'Yes' if status['running'] else 'No'}")
                lines.append(f"- Total tasks: {status['total_tasks']}")
                lines.append(f"- Active: {status['active_tasks']}")
                return "\n".join(lines)

            elif sub == "delete" and len(parts) > 2:
                task_id = parts[2]
                if self._task_runner.delete_task(user_id, task_id):
                    return f"Deleted task `{task_id}`."
                return f"Could not delete task `{task_id}`. Not found or not authorized."

            elif sub == "pause" and len(parts) > 2:
                task_id = parts[2]
                if self._task_runner.pause_task(user_id, task_id):
                    return f"Paused task `{task_id}`."
                return f"Could not pause task `{task_id}`."

            elif sub == "resume" and len(parts) > 2:
                task_id = parts[2]
                if self._task_runner.resume_task(user_id, task_id):
                    return f"Resumed task `{task_id}`."
                return f"Could not resume task `{task_id}`."

            return "Usage: `/tasks list|status|delete|pause|resume [id]`"

        # ==================================
        # MCP server commands: /mcp
        # ==================================
        elif command_lower.startswith("/mcp"):
            parts = command.strip().split(maxsplit=2)
            user_id = session_key.split(":")[-1]

            if len(parts) == 1 or parts[1].lower() == "list":
                return self._mcp_server_manager.format_server_list()

            sub = parts[1].lower()

            if sub == "verified":
                return self._mcp_server_manager.get_verified_list()

            elif sub == "install" and len(parts) > 2:
                package = parts[2].strip()
                return self._mcp_server_manager.request_install(user_id, package)

            elif sub == "confirm":
                confirmation = parts[2].strip() if len(parts) > 2 else ""
                return self._mcp_server_manager.confirm_install(user_id, confirmation)

            elif sub == "cancel":
                return self._mcp_server_manager.cancel_install(user_id)

            elif sub == "enable" and len(parts) > 2:
                server_name = parts[2].strip()
                success, msg = self._mcp_server_manager.enable_server(user_id, server_name)
                return msg

            elif sub == "disable" and len(parts) > 2:
                server_name = parts[2].strip()
                success, msg = self._mcp_server_manager.disable_server(user_id, server_name)
                return msg

            elif sub == "uninstall" and len(parts) > 2:
                server_name = parts[2].strip()
                return self._mcp_server_manager.uninstall_server(user_id, server_name)

            return "Usage: `/mcp list|verified|install|confirm|cancel|enable|disable|uninstall [name]`"

        # ==================================
        # ClawHub commands: /clawhub
        # ==================================
        elif command_lower.startswith("/clawhub"):
            parts = command.strip().split(maxsplit=2)

            if len(parts) == 1:
                return "Usage: `/clawhub search|install|list|info|uninstall|updates [args]`"

            sub = parts[1].lower()

            if sub == "search" and len(parts) > 2:
                query = parts[2].strip()
                results = self._clawhub_manager.search(query)
                if results is None:
                    return "Could not reach ClawHub. Please try again later."
                return self._clawhub_manager.format_search_results(results)

            elif sub == "install" and len(parts) > 2:
                slug = parts[2].strip()
                success, msg = self._clawhub_manager.install_skill(slug)
                return msg

            elif sub == "list":
                return self._clawhub_manager.format_installed_list()

            elif sub == "info" and len(parts) > 2:
                slug = parts[2].strip()
                info = self._clawhub_manager.get_skill_info(slug)
                if info is None:
                    return f"Could not find skill '{slug}' on ClawHub."
                return self._clawhub_manager.format_skill_info(info)

            elif sub == "uninstall" and len(parts) > 2:
                slug = parts[2].strip()
                success, msg = self._clawhub_manager.uninstall_skill(slug)
                return msg

            elif sub == "updates":
                updates = self._clawhub_manager.check_updates()
                return self._clawhub_manager.format_updates(updates)

            return "Usage: `/clawhub search|install|list|info|uninstall|updates [args]`"

        # ==================================
        # Persona commands: /list-personas, /set-persona, /persona, /create-persona
        # ==================================
        elif command_lower == "/list-personas":
            personas = self.personality.get_personas()
            if not personas:
                return "No personas available. Create one with `/create-persona <name> [description]`."
            lines = ["**Available Personas:**\n"]
            user_id = session_key.split(":")[-1]
            current = self.personality._user_profiles.get("user_personas", {}).get(user_id)
            for p in sorted(personas.values(), key=lambda x: x.name):
                marker = " ← current" if p.name == current else ""
                lines.append(f"- {p.emoji} **{p.name}** — {p.description}{marker}")
            return "\n".join(lines)

        elif command_lower.startswith("/set-persona"):
            parts = command.strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return "Usage: `/set-persona <name>` — assign a persona (use `default` to reset)"
            name = parts[1].strip().lower()
            user_id = session_key.split(":")[-1]
            if name == "default":
                self.personality.remove_user_persona(user_id)
                self._prompt_cache.clear()
                return "Persona reset to **default**."
            if not self.personality.get_persona(name):
                available = ", ".join(sorted(self.personality.get_personas().keys()))
                return f"Persona not found: `{name}`. Available: {available or 'none'}"
            self.personality.set_user_persona(user_id, name)
            self._prompt_cache.clear()
            persona = self.personality.get_persona(name)
            return f"Persona set to {persona.emoji} **{persona.name}** — {persona.description}"

        elif command_lower == "/persona":
            user_id = session_key.split(":")[-1]
            name = self.personality._user_profiles.get("user_personas", {}).get(user_id)
            if name:
                persona = self.personality.get_persona(name)
                if persona:
                    return f"Your current persona: {persona.emoji} **{persona.name}** — {persona.description}"
            return "No persona assigned (using default personality)."

        elif command_lower.startswith("/create-persona"):
            parts = command.strip().split(maxsplit=2)
            if len(parts) < 2 or not parts[1].strip():
                return "Usage: `/create-persona <name> [description]`"
            name = parts[1].strip().lower()
            description = parts[2].strip() if len(parts) > 2 else ""
            try:
                persona = self.personality.create_persona(name, description=description)
                return f"Created persona **{persona.name}**. Edit its file at `data/personality/agents/{name}.md` to add instructions."
            except ValueError as e:
                return str(e)

        # ==================================
        # Handle /think command — set reasoning level
        # ==================================
        elif command_lower.startswith("/think"):
            parts = command.strip().split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                # Show current level
                current = self._think_levels.get(session_key, "medium")
                level_info = self.THINK_LEVELS[current]
                lines = [f"**Current thinking level:** `{current}` — {level_info['description']}",
                         "", "**Available levels:**"]
                for name, info in self.THINK_LEVELS.items():
                    marker = " (current)" if name == current else ""
                    lines.append(f"- `{name}` — {info['description']}{marker}")
                lines.extend(["", "Usage: `/think <level>`"])
                return "\n".join(lines)

            level = parts[1].strip().lower()
            if level not in self.THINK_LEVELS:
                available = ", ".join(self.THINK_LEVELS.keys())
                return f"Unknown thinking level: `{level}`. Available: {available}"

            self._think_levels[session_key] = level
            info = self.THINK_LEVELS[level]
            return f"Thinking level set to **{level}** — {info['description']} (temperature: {info['temperature']})"

        # ==================================
        # Unknown command handler
        # ==================================
        else:
            return f"Unknown command: {command}. Type /help for available commands."

    # =========================================================================
    # =========================================================================
    # Function is_skill_invocation -> str to tuple[bool, str, str]
    # =========================================================================
    # =========================================================================
    def is_skill_invocation(self, message: str) -> tuple[bool, str, str]:
        """
        Check if a message is a skill invocation.

        Args:
            message: User message

        Returns:
            Tuple of (is_skill, skill_name, remaining_message)
        """
        message = message.strip()
        
        # ==================================
        # Check if message starts with /
        # ==================================
        if not message.startswith("/"):
            return False, "", message

        # ==================================
        # Extract command and remaining text
        # ==================================
        parts = message.split(maxsplit=1)
        command = parts[0][1:].lower()  # Remove leading /
        remaining = parts[1] if len(parts) > 1 else ""

        # ==================================
        # Check if it's a built-in command
        # ==================================
        if command in ["reset", "new", "stats", "help", "skills", "memory", "forget", "setpassword", "unlock",
                      "auth", "pin", "login", "logout", "summary", "heartbeat", "patterns", "tasks", "mcp",
                      "list-personas", "set-persona", "persona", "create-persona", "clawhub", "think",
                      "my-permissions", "user-role", "grant", "revoke", "users",
                      "request-permission", "my-requests", "pending-requests", "approve", "deny", "link-identity"]:
            return False, "", message

        # ==================================
        # Check if it's a skill
        # ==================================
        if self.personality.skills_manager:
            skill = self.personality.skills_manager.get_skill(command)
            if skill and skill.user_invocable:
                return True, command, remaining

        return False, "", message

    # =========================================================================
    # =========================================================================
    # Function _execute_pending_file_action -> str & dict to str
    # =========================================================================
    # =========================================================================
    def _execute_pending_file_action(self, session_key: str, pending: dict) -> str:
        """
        Execute a pending file action after password verification.

        Args:
            session_key: Session identifier
            pending: Pending action dict with 'action' and 'details'

        Returns:
            Result message
        """
        action = pending.get("action", "")
        details = pending.get("details", {})

        if action == "skill_commands":
            commands = details.get("commands", [])
            if not commands:
                return "No pending skill commands to execute."

            results = []
            user_id = details.get("user_id")
            for cmd in commands:
                cmd_action = cmd.get('ACTION', '').lower()
                try:
                    if cmd_action == 'create':
                        result = self._skill_creator_handler._handle_create(cmd)
                        # Mark pattern as created if this was auto-generated
                        if result.get("success") and user_id:
                            self._mark_auto_skill_pattern(user_id, cmd)
                    elif cmd_action == 'delete':
                        result = self._skill_creator_handler._handle_delete(cmd)
                    elif cmd_action == 'update':
                        result = self._skill_creator_handler._handle_update(cmd)
                    elif cmd_action == 'list':
                        result = self._skill_creator_handler._handle_list()
                    else:
                        result = {"success": False, "error": f"Unknown action: {cmd_action}"}
                    results.append(result)
                except Exception as e:
                    results.append({"success": False, "error": str(e)})

            return self._skill_creator_handler._format_results(results)

        return f"Unknown pending action type: {action}"

    # =========================================================================
    # Function _mark_auto_skill_pattern -> str & dict to None
    # =========================================================================
    def _mark_auto_skill_pattern(self, user_id: str, cmd: dict) -> None:
        """
        After a skill is auto-created from a detected pattern, mark
        the pattern as converted so it doesn't trigger again.

        Extracts pattern_id from the LLM response's INSTRUCTIONS field
        (injected via the auto-skill prompt as [pattern_id:xxx]).
        """
        try:
            import re
            instructions = cmd.get("INSTRUCTIONS", "")
            match = re.search(r'\[pattern_id:([a-f0-9]+)\]', instructions)
            if match:
                pattern_id = match.group(1)
                self._pattern_detector.mark_skill_created(user_id, pattern_id)
                logger.info(f"Auto-skill pattern {pattern_id} marked as created for {user_id}")
        except Exception:
            pass

    # =========================================================================
    # =========================================================================
    # Function _needs_web_search -> str to bool
    # =========================================================================
    # =========================================================================
    def _needs_web_search(self, message: str) -> bool:
        """
        Detect if a message needs real-time web search.
        Triggers for: sports scores, news, weather, stocks, current events.
        """
        msg_lower = message.lower()

        # Keywords indicating need for current info
        current_event_keywords = [
            # Sports
            "score", "match", "won", "win", "lost", "playing", "vs", "versus",
            "t20", "odi", "test match", "cricket", "football", "soccer",
            "nba", "nfl", "fifa", "ipl", "world cup", "tournament",
            # News & Events
            "today", "yesterday", "tonight", "this week", "latest", "recent",
            "news", "happening", "update", "current", "breaking",
            # Weather
            "weather", "temperature", "forecast", "rain", "sunny",
            # Stocks/Finance
            "stock", "price", "market", "bitcoin", "crypto", "trading",
            # Time-sensitive
            "when is", "what time", "schedule", "next match", "upcoming",
        ]

        # Check if any keyword matches
        for keyword in current_event_keywords:
            if keyword in msg_lower:
                # Additional check: question format or recent timeframe
                if any(q in msg_lower for q in ["?", "who", "what", "when", "where", "how", "tell me", "check"]):
                    return True
                if any(t in msg_lower for t in ["today", "now", "current", "latest", "recent"]):
                    return True

        return False

    # =========================================================================
    # =========================================================================
    # Function get_skill_context -> str to str
    # =========================================================================
    # =========================================================================
    def get_skill_context(self, skill_name: str) -> str:
        """
        Get the context to inject when a skill is invoked.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill instructions to inject into the conversation
        """
        instructions = self.personality.get_skill_instructions(skill_name)
        if instructions:
            skill = self.personality.skills_manager.get_skill(skill_name)
            emoji = f"{skill.emoji} " if skill and skill.emoji else ""
            return f"""---
## SKILL ACTIVATED: {emoji}{skill_name}

The user has invoked the `/{skill_name}` skill. Follow these instructions EXACTLY.
Do NOT explain your reasoning. Just emit the required code block immediately.

{instructions}

---
"""
        return ""


# =============================================================================
# Example Usage Section
# =============================================================================
if __name__ == "__main__":
    import asyncio
    from skillforge.core.llm import LLMProviderFactory

    # ==================================
    # Initialize components with new LLM framework
    # ==================================
    session_manager = SessionManager()

    # ==================================
    # Create LLM provider
    # ==================================
    llm_provider = LLMProviderFactory.from_dict({
        "provider": "ollama",
        "model": "gemma3:1b",
        "base_url": "http://localhost:11434/v1",
    })

    router = MessageRouter(session_manager, llm_provider)

    # =========================================================================
    # =========================================================================
    # Function test -> None to None
    # =========================================================================
    # =========================================================================
    async def test():
        # ==================================
        # Simulate MS Teams messages
        # ==================================
        response1 = await router.handle_message(
            channel="msteams",
            user_id="test-user-123",
            user_message="Hello! What's your name?",
            user_name="John Doe"
        )
        print(f"Bot: {response1}\n")

        response2 = await router.handle_message(
            channel="msteams",
            user_id="test-user-123",
            user_message="Can you remember what I just asked?",
            user_name="John Doe"
        )
        print(f"Bot: {response2}\n")

        # ==================================
        # Test command
        # ==================================
        response3 = router.handle_command("/stats", "msteams:direct:test-user-123")
        print(f"Stats: {response3}")

    asyncio.run(test())
# =============================================================================
'''
    End of router.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Contact : Idrak AI Ltd - Building AI Solutions for the Community
'''
# =============================================================================
