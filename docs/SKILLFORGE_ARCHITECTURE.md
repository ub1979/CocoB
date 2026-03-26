# SkillForge Architecture Reference

## Overview

SkillForge is a multi-channel AI assistant with persistent memory, skill-based extensibility, and a tiered security model. It connects to any LLM provider (local or cloud), remembers users across sessions via SQLite FTS5, supports scheduled tasks, MCP tool integration, image handling, and a desktop UI. Messages arrive from channels (Telegram, Discord, Slack, WhatsApp, MS Teams, Flet UI, Gradio), pass through a central router that orchestrates LLM calls, memory retrieval, code-block handler execution, and permission checks, then return to the originating channel.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web server | Flask (MS Teams webhook) |
| Desktop UI | Flet 0.27+ |
| Web UI | Gradio 6+ |
| LLM interface | OpenAI-compatible API, Anthropic SDK, Google GenAI SDK, CLI subprocesses |
| Memory | SQLite FTS5 (primary), ChromaDB (legacy/optional) |
| Scheduling | APScheduler (AsyncIO) |
| MCP tools | JSON-RPC over stdio subprocess |
| Config | Python module (`config.py`) |
| Package | setuptools, `pyproject.toml` |

---

## System Architecture

```
                        +-----------+
                        |  config/  |
                        | config.py |
                        +-----+-----+
                              |
    +-------+  +--------+  +-+--+  +---------+  +-------+  +--------+
    |Telegram|  |Discord |  |Flet|  | Gradio  |  | Slack |  |WhatsApp|
    |Channel |  |Channel |  | UI |  |   UI    |  |Channel|  |Channel |
    +---+----+  +---+----+  +-+--+  +----+----+  +---+---+  +---+----+
        |           |         |          |            |          |
        +-----+-----+---------+----+-----+-----+------+----------+
              |                     |                  |
              v                     v                  v
        +-----+---------------------+------------------+------+
        |                    MessageRouter                     |
        |  (route_message / handle_message / handle_message_stream)
        +---+--------+--------+--------+--------+--------+----+
            |        |        |        |        |        |
            v        v        v        v        v        v
        +------+ +------+ +------+ +------+ +------+ +------+
        | LLM  | |Memory| |Skills| | MCP  | |Sched.| | Auth |
        |Provid.| |Store | |Mgr   | |Tools | |Mgr   | |Mgr   |
        +------+ +------+ +------+ +------+ +------+ +------+
            |        |                  |
            v        v                  v
        +------+ +------+         +----------+
        |Cloud/| |SQLite|         |MCP Server|
        |Local | | .db  |         |Subprocess|
        | LLM  | +------+         +----------+
        +------+
```

---

## Entry Points & CLI

The `skillforge` console script is defined in `pyproject.toml` and dispatches to `src/skillforge/__main__.py`.

| Command | What it launches | Key module |
|---------|-----------------|------------|
| `skillforge ui` | Flet desktop app (5-tab navigation + login gate) | `flet.app.main` via `flet.app()` |
| `skillforge gradio` | Gradio web chat UI | `gradio_ui.py` |
| `skillforge bot` | Flask server with MS Teams webhook | `bot.py` |
| `skillforge telegram` | python-telegram-bot polling loop | `telegram_bot.py` |
| `skillforge discord` | discord.py bot | `run_discord.py` |
| `skillforge slack` | slack-bolt Socket Mode | `run_slack.py` |
| `skillforge doctor` | Config/dependency health check | `__main__._run_doctor()` |

All modes create the same core pipeline: `SessionManager` + `LLMProviderFactory.from_dict(config)` + `MessageRouter(session_manager, llm_provider)`.

**File:** `src/skillforge/__main__.py`

---

## Message Flow

```
1. Channel receives message (text + optional image attachments)
       |
2. channel calls  router.handle_message(channel, user_id, text, ...)
       |
3. IdentityResolver.resolve(platform_id) -> canonical user_id
       |
4. SessionManager.get_or_create_session()
       |
5. ImageHandler.store_image() for each attachment
       |
6. SessionManager.add_message(session_key, "user", text)
       |
7. Pre-search: if message matches _SEARCH_KEYWORDS, WebToolsHandler
   fetches Brave Search results and injects into system prompt
       |
8. Direct skill check: if /email or /calendar, SkillExecutor runs
   MCP tool immediately and returns (short-circuit)
       |
9. PatternDetector.record_interaction()
       |
10. SessionManager.get_conversation_history(max_messages=5)
       |
11. LLMProvider.check_context_size() -> compact if needed
       |
12. SQLiteMemory.get_relevant_context() -> facts + past conversations
       |
13. Build system prompt:
    PersonalityManager.get_system_prompt(user_id, channel)
    + web search hints + memory context + skill context
    + capability hints (schedule, todo, etc.)
       |
14. LLMProvider.chat(messages) with optional temperature override
       |
15. Tool call loop (max 5 iterations):
    MCPToolHandler.has_tool_calls() -> execute_all_tool_calls()
    -> append results -> re-call LLM
       |
16. Parse response for handler code blocks:
    - ```schedule```  -> ScheduleCommandHandler.execute_commands()
    - ```create-skill``` -> SkillCreatorHandler (pending password confirm)
    - ```todo```      -> TodoCommandHandler.execute_commands()
    - ```image_gen``` -> ImageGenHandler.execute_commands()
    - ```web_search```/```web_fetch``` -> WebToolsHandler
    - JSON tool calls -> MCPToolHandler
       |
17. PersonalityManager.parse_response_for_updates()
       |
18. SessionManager.add_message(session_key, "assistant", response)
       |
19. SQLiteMemory.add_conversation() + extract_and_store_facts()
    (runs in background thread)
       |
20. extract_outbound_images(response) -> (clean_text, image_paths)
       |
21. Channel sends clean_text + image files back to user
```

---

## Core Modules

### Router

| | |
|---|---|
| **File** | `src/skillforge/core/router.py` |
| **Class** | `MessageRouter` |
| **Depends on** | SessionManager, LLMProvider, PersonalityManager, SQLiteMemory, MCPToolHandler, ScheduleCommandHandler, TodoCommandHandler, SkillCreatorHandler, SkillExecutor, FileAccessManager, AuthManager, PermissionManager, IdentityResolver, PermissionRequestManager, HeartbeatManager, PatternDetector, BackgroundTaskRunner, MCPManager (mcp_manager.py), ClawHubManager, WebToolsHandler, ImageHandler, ImageGenHandler |

**Constructor:**
```python
MessageRouter(
    session_manager: SessionManager,
    llm_provider: Union[LLMProvider, AIClient],
    mcp_manager: Optional[MCPManager] = None,
)
```

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `handle_message` | `async (channel, user_id, user_message, chat_id?, user_name?, attachments?) -> str` | Full message handling: session, memory, LLM call, handler execution, response |
| `handle_message_stream` | `async (channel, user_id, user_message, chat_id?, user_name?, skill_context?, attachments?) -> AsyncGenerator[str]` | Streaming variant, yields response chunks |
| `extract_outbound_images` | `@staticmethod (response: str) -> Tuple[str, List[str]]` | Extracts image paths from response markers, returns (cleaned_text, paths) |
| `is_skill_invocation` | `(message: str) -> tuple[bool, str, str]` | Checks if message starts with `/skillname`, returns (is_skill, name, remaining) |
| `set_mcp_manager` | `(mcp_manager) -> None` | Late-bind MCP after init |
| `set_scheduler_manager` | `(scheduler_manager) -> None` | Late-bind scheduler after init |
| `start_services` | `async () -> None` | Start heartbeat and background task runner |
| `get_mcp_tools_prompt` | `() -> str` | MCP tools description for system prompt |

**Think levels** (per-session temperature override):

| Level | Temperature |
|-------|------------|
| off | 0.0 |
| minimal | 0.2 |
| low | 0.4 |
| medium | 0.7 (default) |
| high | 0.9 |
| xhigh | 1.2 |

---

### Sessions

| | |
|---|---|
| **File** | `src/skillforge/core/sessions.py` |
| **Class** | `SessionManager` |
| **Storage** | `data/sessions/sessions.json` (index), `data/sessions/sess-*.jsonl` (transcripts) |

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_session_key` | `(channel, user_id, chat_id?) -> str` | Generate key like `telegram:direct:user123` or `telegram:group:user123:chat456` |
| `get_or_create_session` | `(session_key, channel, user_id) -> Dict` | Returns existing or creates new session |
| `add_message` | `(session_key, role, content, metadata?) -> str` | Append to JSONL, returns message ID |
| `get_conversation_history` | `(session_key, max_messages?) -> List[Dict]` | Read messages from JSONL (tail-optimized) |
| `add_compaction` | `(session_key, summary, tokens_before) -> None` | Write compaction entry; replaces history on reload |
| `reset_session` | `(session_key) -> None` | Delete session from index |
| `list_sessions` | `() -> List[Dict]` | All sessions with metadata |
| `flush` | `() -> None` | Force-write pending index changes |

JSONL entry types: `session` (header), `message` (user/assistant/system), `compaction` (summary).

Security: validates all inputs against `MAX_SESSION_KEY_LENGTH` (512), `MAX_CONTENT_LENGTH` (100KB), path traversal, null bytes.

---

### Memory

| | |
|---|---|
| **Files** | `src/skillforge/core/memory/sqlite_memory.py` (primary), `src/skillforge/core/memory/chroma_store.py` (legacy) |
| **Classes** | `SQLiteMemory`, `MemoryStore` |
| **Storage** | `data/memory.db` (SQLite), `data/memory_db/` (ChromaDB) |

#### SQLiteMemory (primary)

Uses SQLite FTS5 for full-text search. Zero external dependencies, instant startup.

Tables: `facts`, `conversations`, `facts_fts` (FTS5), `conversations_fts` (FTS5).

SQLite pragmas: `journal_mode=WAL`, `synchronous=NORMAL`, `timeout=30s`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_fact` | `(user_id, fact, category?, source_session?) -> int` | Store/deduplicate a user fact |
| `add_conversation` | `(user_id, channel, session_key, user_msg, assistant_msg) -> int` | Store conversation turn with auto-summary |
| `search` | `(query, user_id?, limit?) -> List[Dict]` | FTS5 search across facts and conversations |
| `get_user_facts` | `(user_id) -> List[Dict]` | All facts for a user |
| `get_relevant_context` | `(query, user_id, max_chars?) -> str` | Build formatted context string for system prompt (capped ~1500 chars) |
| `extract_and_store_facts` | `(user_id, user_message, session_key?) -> List[str]` | Regex-based fact extraction (12 patterns) |
| `extract_facts_via_llm` | `(user_id, user_message, assistant_message, llm_provider, session_key?) -> List[str]` | LLM-based fact extraction (second pass) |
| `get_stats` | `() -> Dict` | Counts of facts and conversations |

Fact categories: `info`, `preference`, `trait`.

#### MemoryStore (legacy ChromaDB)

Optional (`chromadb` package). Semantic vector search. Used alongside JSONL. Not loaded by default in current router.

---

### LLM Providers

| | |
|---|---|
| **Files** | `src/skillforge/core/llm/base.py`, `factory.py`, `openai_compat.py`, `anthropic_provider.py`, `gemini_provider.py`, `claude_cli_provider.py`, `gemini_cli_provider.py`, `llamacpp_provider.py`, `auth/` |
| **Base classes** | `LLMProvider` (ABC), `LLMConfig` (dataclass) |
| **Factory** | `LLMProviderFactory` |

#### LLMConfig fields

| Field | Type | Default |
|-------|------|---------|
| `provider` | str | required |
| `model` | str | required |
| `base_url` | Optional[str] | None |
| `api_key` | Optional[str] | None |
| `auth_method` | str | `"api_key"` |
| `context_window` | int | 4096 |
| `max_response_tokens` | int | 4096 |
| `temperature` | float | 0.7 |
| `timeout` | int | 60 |
| `extra` | Dict | {} |

#### LLMProvider abstract methods

| Method | Signature |
|--------|-----------|
| `_validate_config` | `() -> None` |
| `chat` | `(messages: List[Dict], **kwargs) -> str` |
| `chat_stream` | `(messages: List[Dict], **kwargs) -> Generator[str]` |
| `estimate_tokens` | `(text: str) -> int` |

Concrete method: `check_context_size(messages) -> Dict` (total_tokens, available_tokens, within_limit, needs_compaction), `summarize_conversation(messages) -> str`.

#### Registered providers (13 entries in factory)

| Provider name | Implementation class | Type |
|---------------|---------------------|------|
| `openai` | OpenAICompatibleProvider | Cloud API |
| `ollama` | OpenAICompatibleProvider | Local server |
| `vllm` | OpenAICompatibleProvider | Local server |
| `groq` | OpenAICompatibleProvider | Cloud API |
| `together` | OpenAICompatibleProvider | Cloud API |
| `azure` | OpenAICompatibleProvider | Cloud API |
| `kimi` | OpenAICompatibleProvider | Cloud API |
| `lmstudio` | OpenAICompatibleProvider | Local server |
| `mlx` | OpenAICompatibleProvider | Local server |
| `anthropic` | AnthropicProvider | Cloud API |
| `claude-cli` | ClaudeCLIProvider | CLI subprocess |
| `gemini` | GeminiProvider | Cloud API |
| `gemini-cli` | GeminiCLIProvider | CLI subprocess |

Not registered in factory but exists: `LlamaCppProvider` (loads GGUF models directly via `llama-cpp-python`).

#### Auth subpackage

`src/skillforge/core/llm/auth/` - OAuth/CLI authentication helpers for Anthropic and Gemini providers.

---

### Skills

| | |
|---|---|
| **Files** | `src/skillforge/core/skills/loader.py`, `src/skillforge/core/skills/manager.py` |
| **Classes** | `Skill` (dataclass), `SkillsManager` |
| **Storage** | `skills/` (bundled), `~/.skillforge/skills/` (user), `./skills/` (project), `skills/clawhub/` (ClawHub-installed) |

#### Skill dataclass

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Lowercase identifier |
| `description` | str | One-line description |
| `instructions` | str | Markdown body |
| `user_invocable` | bool | Show as `/command` (default True) |
| `emoji` | str | Display emoji |
| `source` | str | `"bundled"`, `"project"`, `"user"`, or `"clawhub"` |
| `file_path` | str | Path to SKILL.md |
| `version` | str | Semver from ClawHub |
| `author` | str | ClawHub author handle |
| `clawhub_slug` | str | Original slug for updates |

#### SKILL.md format

```markdown
---
name: email
description: Manage your Gmail
emoji: "\U0001F4E7"
user_invocable: true
---

# Email Skill

Instructions for the LLM go here in markdown...
```

YAML frontmatter (parsed with `PyYAML`) followed by markdown body.

#### SkillsManager methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `load_all_skills` | `() -> List[Skill]` | Load from all dirs; higher priority overrides |
| `get_skills` | `() -> List[Skill]` | All loaded skills (lazy-loads) |
| `get_skill` | `(name) -> Optional[Skill]` | Lookup by name |
| `get_user_invocable_skills` | `() -> List[Skill]` | Skills with `user_invocable=True` |
| `save_skill` | `(skill, save_as_new?, new_name?) -> bool` | Write SKILL.md to disk |

**Load priority** (lowest first, higher overrides): bundled (`skills/`) < project (`./skills/`) < user (`~/.skillforge/skills/`). ClawHub skills install to `skills/clawhub/`.

---

### Personality

| | |
|---|---|
| **File** | `src/skillforge/core/personality.py` |
| **Classes** | `PersonalityManager`, `Persona` (dataclass) |
| **Storage** | `data/personality/PERSONALITY.md`, `data/personality/MOODS.md`, `data/personality/NEW_PERSONALITY.md`, `data/personality/agents/` (persona files), `data/personality/user_profiles.json` |

#### Persona dataclass

| Field | Type |
|-------|------|
| `name` | str |
| `description` | str |
| `emoji` | str |
| `instructions` | str |
| `file_path` | Path |

#### PersonalityManager methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_system_prompt` | `(mode?, user_id?, channel?) -> str` | Build system prompt; modes: `"full"`, `"minimal"`, `"none"` |
| `load_personas` | `() -> None` | Load persona files from `agents/` directory |
| `parse_response_for_updates` | `(response, user_id) -> Tuple[str, Dict]` | Extract mood/personality updates from response |
| `skills_manager` (property) | `-> SkillsManager` | Lazy-loaded |

Per-user persona assignment stored in `user_profiles.json`.

---

### Scheduler

| | |
|---|---|
| **File** | `src/skillforge/core/scheduler.py` |
| **Classes** | `SchedulerManager`, `ScheduledTask` (dataclass), `ExecutionLog` (dataclass) |
| **Storage** | `data/scheduler/tasks.json`, `data/scheduler/execution_log.jsonl` |
| **Depends on** | APScheduler (`AsyncIOScheduler`, `CronTrigger`, `IntervalTrigger`, `DateTrigger`) |

#### ScheduledTask fields

| Field | Type | Default |
|-------|------|---------|
| `id` | str | auto-generated `task-XXXXXXXX` |
| `name` | str | required |
| `schedule` | str | `"0 9 * * *"` (cron) |
| `schedule_kind` | str | `"cron"` / `"every"` / `"at"` |
| `interval_seconds` | int | 0 (for `"every"`) |
| `run_at` | str | ISO 8601 (for `"at"`) |
| `action` | str | `"send_message"` or `"execute_skill"` |
| `target_channel` | str | `"telegram"` |
| `target_user` | str | required |
| `delete_after_run` | bool | False (auto-delete one-shot) |
| `max_retries` | int | 5 |
| `max_concurrent` | int | 1 |

#### SchedulerManager methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `start` | `async () -> None` | Start APScheduler and schedule all enabled tasks |
| `stop` | `async () -> None` | Graceful shutdown |
| `add_task` | `async (task: ScheduledTask) -> str` | Validate and add task, returns ID |
| `register_channel_handler` | `(channel, handler) -> None` | Register `async (user_id, message, chat_id?) -> bool` |

Retry backoff: 30s, 1m, 5m, 15m, 60m.

---

### Permissions

| | |
|---|---|
| **File** | `src/skillforge/core/user_permissions.py` |
| **Classes** | `PermissionManager`, `Permission` (Enum), `UserRole` (Enum) |
| **Storage** | `data/user_roles.json` |

#### Permission enum values

`chat`, `web_search`, `web_fetch`, `email`, `calendar`, `browse`, `files`, `schedule`, `todo`, `mcp_tools`, `mcp_manage`, `skills_create`, `background_tasks`, `admin`

#### UserRole enum values

`admin`, `power_user`, `user`, `restricted`

#### Default role permissions

| Role | Permissions |
|------|------------|
| `admin` | `*` (all) |
| `power_user` | chat, web_search, web_fetch, email, calendar, browse, files, schedule, todo, mcp_tools, skills_create, background_tasks |
| `user` | chat, web_search, web_fetch, schedule, todo |
| `restricted` | chat |

#### PermissionManager methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `has_permission` | `(user_id, permission) -> bool` | Check permission; returns True for all if not enabled |
| `get_user_permissions` | `(user_id) -> Set[str]` | Effective permissions (role + custom - denied) |
| `get_user_role` | `(user_id) -> str` | Role name, falls back to `default_role` |
| `is_admin` | `(user_id) -> bool` | Shortcut for admin check |
| `set_user_role` | `(user_id, role, assigned_by?) -> bool` | Assign role |
| `grant_permission` | `(user_id, permission) -> bool` | Add custom permission |
| `revoke_permission` | `(user_id, permission) -> bool` | Deny specific permission |

Backward compatibility: if `data/user_roles.json` does not exist, all permissions return True.

---

### Authentication

| | |
|---|---|
| **File** | `src/skillforge/core/auth_manager.py` |
| **Classes** | `AuthManager`, `SecurityLevel` (Enum), `AuthResult` (NamedTuple), `AuthSession` |
| **Storage** | `data/auth/` |

#### Security levels

| Level | Value | Auth method | Session duration | Use case |
|-------|-------|------------|-----------------|----------|
| GREEN | 0 | None | N/A | Read-only, heartbeats |
| YELLOW | 1 | PIN | 30 min | Routine tasks, background tasks |
| ORANGE | 2 | Password | 60 min | Skill creation, pattern viewing |
| RED | 3 | Password + confirm | Per-action | Dangerous operations |

Passwords stored with PBKDF2-HMAC-SHA256 (600,000 iterations, 32-byte salt). Constant-time comparison.

---

### Identity

| | |
|---|---|
| **File** | `src/skillforge/core/identity_resolver.py` |
| **Class** | `IdentityResolver` |
| **Storage** | `data/identity_map.json` |

Maps platform-specific IDs (`telegram:12345`, `whatsapp:+923001234567`) to canonical user IDs so permissions and memory follow the person across platforms.

| Method | Signature | Description |
|--------|-----------|-------------|
| `resolve` | `(platform_id) -> str` | Returns canonical ID or raw platform_id if unmapped |
| `link` | `(canonical_id, platform_id) -> None` | Create mapping |
| `unlink` | `(platform_id) -> None` | Remove mapping |
| `get_aliases` | `(canonical_id) -> List[str]` | All platform IDs for a user |
| `get_all_users` | `() -> Dict[str, List[str]]` | All canonical users and their aliases |
| `remove_user` | `(canonical_id) -> None` | Remove user and all aliases |

---

### MCP (Model Context Protocol)

| | |
|---|---|
| **Files** | `src/skillforge/core/mcp_client.py`, `src/skillforge/core/mcp_manager.py`, `src/skillforge/core/mcp_tools.py` |
| **Classes** | `MCPManager` (mcp_client.py) - stdio subprocess manager; `MCPManager` (mcp_manager.py, aliased as `MCPServerManager`) - chat-based server management; `MCPToolHandler` (mcp_tools.py) |
| **Config** | `mcp_config.json` (project root) |
| **Models** | `src/skillforge/ui/settings/mcp_models.py` - `MCPServerType`, `MCPConnectionStatus`, `MCPServerConfig`, `MCPServerState` |

#### Security allowlist (mcp_client.py)

| Type | Allowed values |
|------|---------------|
| Commands | `npx`, `docker`, `python3`, `python`, `node`, `uv`, `pipx` |
| Package prefixes | `@playwright/`, `@modelcontextprotocol/`, `@composio/`, `mcp-` |
| Blocked Docker flags | `--privileged`, `-v`, `--volume`, `--network=host`, `--pid=host`, `--ipc=host` |

#### Verified MCP servers (built-in registry)

| Key | Name | Category |
|-----|------|----------|
| `@playwright/mcp` | Playwright | browser |
| `@modelcontextprotocol/server-filesystem` | Filesystem | files |
| `@modelcontextprotocol/server-github` | GitHub | developer |
| `@composio/gmail` | Gmail | email |
| `@composio/calendar` | Google Calendar | calendar |

#### MCPToolHandler methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_tools_prompt` | `() -> str` | Minimal prompt listing available tools by server |
| `get_tool_info` | `(tool_name) -> str` | Detailed tool schema |
| `has_tool_calls` | `(response) -> bool` | Check if response contains JSON tool calls |
| `execute_all_tool_calls` | `(response) -> Tuple[str, List]` | Execute tools and return results summary |

#### MCPManager (mcp_manager.py) methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `list_servers` | `() -> List[MCPServerStatus]` | All configured servers |
| `_load_config` / `_save_config` | `() -> Dict` | Read/write `mcp_config.json` |

---

### Image Handling

| | |
|---|---|
| **Files** | `src/skillforge/core/image_handler.py`, `src/skillforge/core/image_gen_handler.py` |
| **Classes** | `ImageHandler`, `Attachment` (dataclass), `ImageGenHandler` |
| **Storage** | `data/images/` |

#### Attachment dataclass

| Field | Type |
|-------|------|
| `file_path` | str |
| `original_filename` | str |
| `mime_type` | str |
| `size_bytes` | int |
| `width` | Optional[int] |
| `height` | Optional[int] |

#### ImageHandler

Validates magic bytes, enforces 20 MB max upload / 4 MB LLM resize, 1 GB total storage limit.

| Method | Signature | Description |
|--------|-----------|-------------|
| `validate_file` | `(file_path) -> Tuple[bool, str]` | Check magic bytes, size, extension |
| `store_image` | `(file_path, session_key, original_filename) -> Attachment` | Copy to `data/images/`, return metadata |
| `to_base64` | `(file_path) -> str` | Base64-encode for vision API |

Supported MIME types: `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/bmp`.

#### ImageGenHandler

Parses `image_gen` code blocks from LLM responses. Delegates to MCP tools (DALL-E, Stable Diffusion).

```
```image_gen
ACTION: generate
PROMPT: A beautiful sunset
STYLE: realistic
SIZE: 1024x1024
PROVIDER: dall-e
```​
```

---

### Web Tools

| | |
|---|---|
| **File** | `src/skillforge/core/web_tools.py` |
| **Class** | `WebToolsHandler`, `HTMLTextExtractor` |
| **Depends on** | `httpx`, Brave Search API |

Parses `web_search` and `web_fetch` code blocks.

| Method | Description |
|--------|-------------|
| `web_search(query, count?)` | Brave Search API call, returns formatted results |
| `web_fetch(url, max_chars?)` | Fetch URL, strip HTML, return text |

Code block formats:
```
```web_search
QUERY: python asyncio tutorial
COUNT: 5
```​
```

```
```web_fetch
URL: https://example.com
MAX_CHARS: 5000
```​
```

Config: `BRAVE_SEARCH_API_KEY` in `config.py`.

---

### File Access

| | |
|---|---|
| **File** | `src/skillforge/core/file_access.py` |
| **Class** | `FileAccessManager` |
| **Storage** | `data/.file_access_auth` (PBKDF2 hash, permissions 0600) |

Sandboxed writes restricted to `skills/` and `data/user/` only. Per-action password verification.

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_password_set` | `() -> bool` | Check if auth file exists |
| `setup_password` | `(password) -> bool` | First-time setup (min 8 chars) |
| `verify_password` | `(password) -> bool` | Constant-time password check |

PBKDF2-HMAC-SHA256, 600,000 iterations, 32-byte random salt.

---

### Handlers

#### ScheduleCommandHandler

| | |
|---|---|
| **File** | `src/skillforge/core/schedule_handler.py` |
| **Class** | `ScheduleCommandHandler` |

Parses `schedule` code blocks. Actions: `create`, `list`, `delete`, `delete_all`, `pause`, `resume`.

#### TodoCommandHandler

| | |
|---|---|
| **File** | `src/skillforge/core/todo_handler.py` |
| **Class** | `TodoCommandHandler` |
| **Storage** | `data/todos.json` |

Parses `todo` code blocks. Actions: `add`, `list`, `complete`, `delete`, `edit`. Supports priorities, due dates, tags.

#### SkillCreatorHandler

| | |
|---|---|
| **File** | `src/skillforge/core/skill_creator_handler.py` |
| **Class** | `SkillCreatorHandler` |

Parses `create-skill` code blocks. Actions: `create`, `list`, `delete`, `update`. Requires file access password.

#### SkillExecutor

| | |
|---|---|
| **File** | `src/skillforge/core/skill_executor.py` |
| **Class** | `SkillExecutor` |

Direct MCP execution for skills: `email`, `calendar`, `google-search`, `browse`. Bypasses LLM for immediate tool calls.

---

### Other Modules

#### PatternDetector

| | |
|---|---|
| **File** | `src/skillforge/core/pattern_detector.py` |
| **Classes** | `PatternDetector`, `PatternType`, `DetectedPattern` (dataclass) |
| **Storage** | `data/patterns/` |

Analyzes user interactions to detect repeated tasks and suggest skill creation. Pattern types: `repeated_command`, `repeated_workflow`, `time_based`, `context_based`. Requires ORANGE auth to view suggestions.

#### BackgroundTaskRunner

| | |
|---|---|
| **File** | `src/skillforge/core/background_tasks.py` |
| **Classes** | `BackgroundTaskRunner`, `TaskStatus` (Enum), `TaskType` |

Runs periodic operations (health monitors, data sync, scheduled jobs). Requires YELLOW auth (PIN) to create/modify.

#### HeartbeatManager

| | |
|---|---|
| **File** | `src/skillforge/core/heartbeat_manager.py` |
| **Classes** | `HeartbeatManager`, `HeartbeatType` |

Proactive check-ins: morning briefings, deadline reminders, unusual activity alerts, daily summaries. GREEN security level (no auth).

#### ClawHubManager

| | |
|---|---|
| **File** | `src/skillforge/core/clawhub.py` |
| **Class** | `ClawHubManager` |
| **API** | `https://clawhub.ai/api` |
| **Storage** | `skills/clawhub/` (installed skills), `data/clawhub_installed.json` (tracking) |
| **Cache** | In-memory, 5-minute TTL |

Search, install, and manage community skills from the OpenClaw.ai ClawHub registry.

#### PermissionRequestManager

| | |
|---|---|
| **File** | `src/skillforge/core/permission_requests.py` |
| **Class** | `PermissionRequestManager` |
| **Storage** | `data/permission_requests.json` |

Users denied a permission can submit a request. Admins approve/deny from admin panel or chat.

| Method | Signature | Description |
|--------|-----------|-------------|
| `submit` | `(user_id, permission, reason?) -> Optional[str]` | Submit request, returns ID (None if duplicate pending) |
| `approve` | `(req_id, admin_id) -> bool` | Approve pending request |
| `deny` | `(req_id, admin_id, reason?) -> bool` | Deny pending request |

---

## Channel Integrations

| Channel | File | Library | Config class | Key features |
|---------|------|---------|-------------|-------------|
| Telegram | `channels/telegram.py` | `python-telegram-bot` | `TelegramConfig` | Commands, image upload/download, group chats, Markdown parsing |
| Discord | `channels/discord_channel.py` | `discord.py` | `DiscordConfig` | DMs, mentions, guild/channel/user allowlists, 2000-char limit |
| Slack | `channels/slack_channel.py` | `slack-bolt` | `SlackConfig` | Socket Mode, DMs, mentions, channel allowlists, 4000-char limit |
| WhatsApp | `channels/whatsapp.py` | `aiohttp` (HTTP to Baileys Node.js service) | `WhatsAppConfig` | Image support, bridges to `whatsapp_service/server.js` |
| MS Teams | `bot.py` | Flask + `botbuilder-core` | N/A (Flask routes) | Webhook endpoint, token verification |
| Gradio | `gradio_ui.py` | Gradio | N/A | Web chat with glass-morphism UI |
| Flet | `flet/app.py` | Flet | N/A | Desktop app, see next section |

**Common pattern across channels:** Each channel adapter creates a `MessageRouter`, calls `router.handle_message(channel_name, user_id, text, ...)`, then sends the response back using the platform's API. Channels handle message splitting for platform character limits and outbound image delivery via `extract_outbound_images()`.

---

## Flet Desktop UI

### View Architecture

```
LoginView (gate)
    |
    v (on_authenticated)
Main App (NavigationRail with 5 destinations)
    |
    +-- ChatView         (index 0)
    +-- HistoryView       (index 1)
    +-- ToolsView         (index 2) -- contains 3 sub-tabs:
    |       +-- MCPPanel
    |       +-- SkillsPanel
    |       +-- ClawHubPanel
    +-- SettingsView      (index 3)
    +-- AdminView         (index 4)
```

### Views

| View | File | Purpose |
|------|------|---------|
| `LoginView` | `flet/views/login.py` | Admin account setup (first run) or login; gates access to main app |
| `ChatView` | `flet/views/chat.py` | Message list, input field, skill popup, typing indicator, image attachments |
| `HistoryView` | `flet/views/history.py` | Session browser, export |
| `ToolsView` | `flet/views/tools.py` | Tabbed container wrapping MCP, Skills, ClawHub panels |
| `MCPPanel` | `flet/views/mcp.py` | MCP server management (connect, disconnect, status) |
| `SkillsPanel` | `flet/views/skills.py` | Skill browser/editor, new skill creation |
| `ClawHubPanel` | `flet/views/clawhub.py` | Marketplace search/install for OpenClaw.ai community skills |
| `SettingsView` | `flet/views/settings.py` | Appearance, personas, messaging bots, scheduler, LLM providers, memory |
| `AdminView` | `flet/views/admin.py` | User management, permission requests, identity linking (3 sub-tabs) |

### Theme System

**File:** `src/skillforge/flet/theme.py`

| Class | Purpose |
|-------|---------|
| `AppColors` | Single-accent color palette (indigo `#6366F1`), neutral gray surfaces, 3-tier depth |
| `Spacing` | Standard constants: XS=4, SM=8, MD=16, LG=24, XL=32 |

### Secure Storage

**File:** `src/skillforge/flet/storage.py`

`SecureStorage` stores API tokens and sensitive settings in `~/.skillforge/secure_config.json`. XOR encryption with machine-specific key (platform node + machine + user).

Key methods: `set_token(key, token)`, `get_token(key)`, `set_setting(key, value)`, `get_setting(key)`, `has_admin()`, `get_admin_username()`.

---

## Skills System

### SKILL.md Format

```yaml
---
name: skill-name          # lowercase, hyphens
description: One-line description
emoji: "\U0001F4E7"       # single emoji
user_invocable: true       # show as /command (default true)
---

# Skill Name

Markdown instructions for the LLM. These become the `instructions`
field and are injected into the system prompt when the skill is invoked.
```

### Load Priority

1. **User** (`~/.skillforge/skills/`) -- highest
2. **Project** (`./skills/`)
3. **Bundled** (`<package>/skills/`)
4. **ClawHub** (`skills/clawhub/`) -- installed from registry

Higher-priority directories override same-named skills from lower-priority directories.

### Bundled Skills (15)

| Name | Emoji | Description | MCP dependency |
|------|-------|-------------|----------------|
| `browse` | `🌐` | Open URL in browser using Playwright | Playwright MCP |
| `calendar` | `📅` | Manage Google Calendar | Composio Calendar MCP |
| `commit` | `📝` | Create git commits with good messages | None |
| `create-skill` | `🛠️` | Create/list/update/delete custom skills via chat | None |
| `email` | `📧` | Manage Gmail inbox | Composio Gmail MCP |
| `explain` | `📖` | Explain how code works | None |
| `files` | `📂` | Browse/search/read/manage local files | Filesystem MCP |
| `github` | `🐙` | Manage GitHub issues, PRs, repos | GitHub MCP |
| `google-search` | `🔍` | Search Google via Playwright (hidden, `user_invocable: false`) | Playwright MCP |
| `news` | `📰` | Headlines and articles from RSS feeds | Playwright MCP |
| `notes` | `📝` | Create/search/edit markdown notes | Filesystem MCP |
| `schedule` | `⏰` | Create/list/manage scheduled tasks | None |
| `search` | `🔍` | Search the web for information | Playwright MCP or search API |
| `social` | `📱` | Post to Twitter/X and LinkedIn | Composio MCP or Playwright MCP |
| `todo` | `✅` | Manage to-do items with priorities/due dates | None |

### ClawHub Integration

`ClawHubManager` communicates with `https://clawhub.ai/api` to search and install community skills. Skills are downloaded as zip files, extracted to `skills/clawhub/`, and tracked in `data/clawhub_installed.json`.

---

## Data Storage

### File Map

| Path | Created by | Description |
|------|-----------|-------------|
| `data/sessions/sessions.json` | SessionManager | Session index (key -> metadata) |
| `data/sessions/sess-*.jsonl` | SessionManager | Conversation transcripts |
| `data/memory.db` | SQLiteMemory | Facts + conversations (FTS5) |
| `data/memory_db/` | MemoryStore (ChromaDB) | Legacy semantic search index |
| `data/personality/PERSONALITY.md` | Manual/PersonalityManager | Bot personality definition |
| `data/personality/MOODS.md` | PersonalityManager | Current mood state |
| `data/personality/NEW_PERSONALITY.md` | PersonalityManager | Learned behaviors |
| `data/personality/agents/*.md` | PersonalityManager | Persona definitions |
| `data/personality/user_profiles.json` | PersonalityManager | User-to-persona mappings |
| `data/scheduler/tasks.json` | SchedulerManager | Scheduled task definitions |
| `data/scheduler/execution_log.jsonl` | SchedulerManager | Task execution history |
| `data/todos.json` | TodoCommandHandler | Todo list items |
| `data/auth/` | AuthManager | PIN/password hashes |
| `data/.file_access_auth` | FileAccessManager | File access password hash |
| `data/user_roles.json` | PermissionManager | User roles and permissions |
| `data/identity_map.json` | IdentityResolver | Platform ID to canonical user mapping |
| `data/permission_requests.json` | PermissionRequestManager | Pending/resolved permission requests |
| `data/clawhub_installed.json` | ClawHubManager | Installed ClawHub skills tracking |
| `data/images/` | ImageHandler | Stored image attachments |
| `data/patterns/` | PatternDetector | Detected usage patterns |
| `mcp_config.json` | MCPManager (mcp_client) | MCP server configurations |
| `~/.skillforge/secure_config.json` | SecureStorage | Encrypted API tokens and settings |
| `~/.skillforge/skills/` | SkillsManager | User-created skills |

### Config Files

| Path | Purpose |
|------|---------|
| `config/config.py` or `config.py` | Main configuration (LLM_PROVIDER, API keys, bot tokens, BRAVE_SEARCH_API_KEY) |
| `pyproject.toml` | Package metadata, dependencies, entry points |
| `mcp_config.json` | MCP server definitions |

---

## Dependencies

From `pyproject.toml`:

### Required

| Package | Min version | Purpose |
|---------|------------|---------|
| `flask` | 3.0.0 | MS Teams webhook server |
| `requests` | 2.31.0 | HTTP client |
| `aiohttp` | 3.9.1 | Async HTTP (WhatsApp bridge) |
| `PyYAML` | 6.0.0 | SKILL.md / persona frontmatter parsing |
| `psutil` | 5.9.0 | System monitoring |
| `httpx` | 0.26.0 | Web tools HTTP client |
| `APScheduler` | 3.10.0 | Task scheduling |

### Optional Groups

| Group | Packages |
|-------|---------|
| `gradio` | `gradio>=6.0.0` |
| `telegram` | `python-telegram-bot>=21.0` |
| `discord` | `discord.py>=2.3.0` |
| `slack` | `slack-bolt>=1.18.0`, `slack-sdk>=3.27.0` |
| `teams` | `botbuilder-core>=4.15.0`, `botbuilder-schema>=4.15.0`, `flask-limiter>=3.0.0` |
| `memory` | `chromadb>=0.4.0` |
| `whatsapp` | `qrcode[pil]>=7.4.2` |
| `ui` | `flet>=0.27.0` |
| `all` | All of the above |
| `dev` | `pytest>=7.0`, `pytest-asyncio>=0.21` |

---

## Module Dependency Graph

The `MessageRouter` is the central hub. Arrows indicate "depends on" / "uses".

```
                                config.py
                                    |
                                    v
                           LLMProviderFactory
                                    |
                                    v
                              LLMProvider
                                    |
         +-----+-----+------+------+------+------+------+------+
         |     |     |      |      |      |      |      |      |
         v     v     v      v      v      v      v      v      v
      Session  SQLite  Personality Skills  MCP    Auth   Perm   Identity
      Manager  Memory  Manager    Manager  Client Manager Manager Resolver
         |                  |        |       |
         |                  +--------+-------+
         |                           |
         v                           v
      JSONL Files             SchedulerManager
                                     |
                                     v
                               APScheduler
```

**Router depends on (all initialized in `__init__`):**

```
MessageRouter
  +-- SessionManager
  +-- LLMProvider (via LLMProviderFactory)
  +-- PersonalityManager
  |     +-- SkillsManager
  +-- SQLiteMemory
  +-- MCPToolHandler
  |     +-- MCPManager (mcp_client)
  +-- ScheduleCommandHandler
  |     +-- SchedulerManager (late-bound)
  +-- TodoCommandHandler
  +-- SkillCreatorHandler
  |     +-- SkillsManager
  +-- SkillExecutor
  |     +-- MCPManager (mcp_client)
  +-- FileAccessManager
  +-- AuthManager
  +-- PermissionManager
  +-- IdentityResolver
  +-- PermissionRequestManager
  +-- HeartbeatManager
  +-- PatternDetector
  |     +-- AuthManager
  +-- BackgroundTaskRunner
  |     +-- AuthManager
  +-- MCPManager (mcp_manager, aliased MCPServerManager)
  |     +-- AuthManager
  +-- ClawHubManager
  |     +-- SkillsManager
  +-- WebToolsHandler
  +-- ImageHandler
  +-- ImageGenHandler
        +-- MCPManager (mcp_client)
```

**Channels depend on:**
```
TelegramChannel / DiscordChannel / SlackChannel / WhatsAppChannel
  +-- MessageRouter.handle_message()
  +-- MessageRouter.extract_outbound_images()
  +-- ImageHandler (Telegram, WhatsApp)
```

**Flet app depends on:**
```
flet.app.main
  +-- LoginView -> SecureStorage
  +-- ChatView -> MessageRouter, SessionManager, SkillsManager, MCPManager
  +-- HistoryView -> SessionManager
  +-- ToolsView -> MCPPanel, SkillsPanel, ClawHubPanel
  +-- SettingsView -> config, SecureStorage, channel configs
  +-- AdminView -> PermissionManager, PermissionRequestManager, IdentityResolver
```
