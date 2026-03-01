# coco B - AI Assistant Project Reference

> Quick-reference for any AI assistant working on this codebase.

## What Is This?

**coco B** is a modular AI chatbot framework with multi-channel support, persistent memory, 15+ LLM providers, and an extensible skills system. Created by Syed Usama Bukhari & Idrak AI Ltd Team.

---

## Project Structure

```
coco_B/
├── src/coco_b/                # Python package (pip install -e .)
│   ├── __init__.py            # Package root — PROJECT_ROOT constant
│   ├── app.py                 # Thin wrapper → delegates to coco_b.flet
│   ├── bot.py                 # MS Teams Flask server
│   ├── gradio_ui.py           # Gradio web UI
│   ├── telegram_bot.py        # Telegram launcher
│   ├── run_slack.py           # Slack launcher
│   ├── run_discord.py         # Discord launcher
│   │
│   ├── core/                  # Core architecture
│   │   ├── router.py          # MessageRouter - central orchestrator
│   │   ├── sessions.py        # SessionManager - JSONL persistence
│   │   ├── personality.py     # PersonalityManager - mood/traits/skills/personas
│   │   ├── ai.py              # AIClient wrapper (backward compat)
│   │   ├── mcp_client.py      # MCP protocol client (multi-server)
│   │   ├── mcp_tools.py       # MCP tool handler for chat
│   │   ├── scheduler.py       # APScheduler task management
│   │   ├── schedule_handler.py# Schedule command processor
│   │   ├── todo_handler.py    # Todo command processor (```todo``` blocks)
│   │   ├── skill_executor.py  # Skill execution engine
│   │   ├── file_access.py       # Password-protected sandboxed file access
│   │   ├── auth_manager.py      # Tiered auth system (GREEN/YELLOW/ORANGE/RED)
│   │   ├── background_tasks.py  # Background task runner (YELLOW auth)
│   │   ├── heartbeat_manager.py # Proactive heartbeat system (GREEN)
│   │   ├── pattern_detector.py  # Repeated-pattern detector & skill suggestions (ORANGE)
│   │   ├── webhook_security.py  # HMAC-SHA256 webhook verification for all channels
│   │   ├── mcp_manager.py      # Chat-based MCP server management (install/enable/disable)
│   │   ├── clawhub.py           # ClawHub manager (OpenClaw.ai skill registry integration)
│   │   ├── web_tools.py          # Native web search (Brave API + DuckDuckGo fallback) & URL fetch
│   │   ├── user_permissions.py    # Per-user permission system (role-based access control)
│   │   ├── skill_creator_handler.py # Dynamic skill creation
│   │   │
│   │   ├── llm/               # LLM provider framework
│   │   │   ├── base.py        # LLMProvider ABC + LLMConfig dataclass
│   │   │   ├── factory.py     # LLMProviderFactory
│   │   │   ├── openai_compat.py    # Ollama, vLLM, Groq, Together, Azure, LM Studio, MLX
│   │   │   ├── anthropic_provider.py # Claude API
│   │   │   ├── gemini_provider.py    # Google Gemini API
│   │   │   ├── claude_cli_provider.py # Claude Code CLI wrapper
│   │   │   ├── gemini_cli_provider.py # Gemini CLI wrapper
│   │   │   └── llamacpp_provider.py   # Llama.cpp
│   │   │
│   │   ├── memory/
│   │   │   ├── sqlite_memory.py  # SQLite FTS5 memory (primary, zero-dep)
│   │   │   └── chroma_store.py   # ChromaDB semantic search (legacy)
│   │   │
│   │   └── skills/
│   │       ├── loader.py      # SKILL.md YAML parser
│   │       └── manager.py     # Skills manager & loader
│   │
│   ├── channels/              # Communication integrations
│   │   ├── telegram.py        # Telegram (python-telegram-bot 21+)
│   │   ├── whatsapp.py        # WhatsApp via Baileys HTTP service
│   │   ├── slack_channel.py   # Slack (Socket Mode)
│   │   └── discord_channel.py # Discord (discord.py)
│   │
│   ├── flet/                   # Flet desktop UI (modular package)
│   │   ├── __init__.py         # Package init, exports main()
│   │   ├── app.py              # Entry point: CocoBApp, 4-tab nav, cleanup, main()
│   │   ├── theme.py            # AppColors, Spacing, provider dicts, utilities
│   │   ├── storage.py          # SecureStorage (encrypted local config)
│   │   ├── components/
│   │   │   ├── chat_message.py # ChatMessage with Markdown rendering
│   │   │   ├── widgets.py      # CollapsibleSection, StatusBadge, StyledButton
│   │   │   └── cards.py        # ServerStatusCard, CliStatusCard
│   │   └── views/
│   │       ├── chat.py         # ChatView — messages, typing indicator, MCP skills
│   │       ├── settings.py     # SettingsView — all settings sections
│   │       ├── tools.py        # ToolsView — tabbed container (MCP+Skills+ClawHub)
│   │       ├── mcp.py          # MCPPanel — MCP server management
│   │       ├── skills.py       # SkillsPanel — skill browser/editor
│   │       ├── clawhub.py      # ClawHubPanel — marketplace search/install
│   │       └── history.py      # HistoryView — conversation history
│   │
│   └── ui/                    # Gradio UI components (separate from Flet)
│       ├── settings/
│       │   ├── state.py       # AppState - shared state
│       │   ├── provider_tab.py# Provider config UI
│       │   ├── skills_tab.py  # Skills management UI
│       │   ├── connection.py  # Connection testing
│       │   └── models.py      # Model discovery
│       └── chat/
│           └── handlers.py    # Chat message handlers
│
├── skills/                    # Bundled skills (SKILL.md format, NOT Python)
│   ├── browse/                # URL browser
│   ├── calendar/              # Google Calendar
│   ├── commit/                # Git commit helper
│   ├── create-skill/          # Dynamic skill creation
│   ├── email/                 # Gmail integration
│   ├── explain/               # Code explanation
│   ├── files/                 # File management (Filesystem MCP)
│   ├── github/                # GitHub issues, PRs, notifications (GitHub MCP)
│   ├── google-search/         # Web search
│   ├── news/                  # RSS feeds & headlines (Playwright MCP)
│   ├── notes/                 # Markdown note-taking (Filesystem MCP)
│   ├── schedule/              # Task scheduling
│   ├── search/                # General search
│   ├── social/                # Twitter/X & LinkedIn (Composio/Playwright MCP)
│   └── todo/                  # Todo list with priorities & reminders
│
├── tests/                     # Pytest test suite (912 tests)
│   ├── test_imports.py        # Core + Flet module imports (35 tests)
│   ├── test_skills_loading.py # SKILL.md parsing & SkillsManager
│   ├── test_todo_handler.py   # Todo handler CRUD (28 tests)
│   ├── test_scheduler.py       # Scheduler multi-trigger, retry, concurrency (49 tests)
│   ├── test_schedule_handler.py # Schedule handler parsing (26 tests)
│   ├── test_file_access.py    # FileAccessManager tests (22 tests)
│   ├── test_file_access_timing.py # Timing attack protection (7 tests)
│   ├── test_router.py         # Router integration tests (23 tests)
│   ├── test_integration_chat.py # End-to-end integration (196 tests)
│   ├── test_personas.py       # Persona system (55 tests)
│   ├── test_auth_manager.py   # AuthManager tiered auth (42 tests)
│   ├── test_background_tasks.py # BackgroundTaskRunner (30 tests)
│   ├── test_heartbeat_manager.py # HeartbeatManager (27 tests)
│   ├── test_mcp_security.py   # MCP command allowlist security
│   ├── test_pattern_detector.py # PatternDetector (25 tests)
│   ├── test_session_key_namespace.py # Session key channel isolation (7 tests)
│   ├── test_sqlite_timeout.py # SQLite connection timeout (4 tests)
│   ├── test_sqlite_wal_mode.py # SQLite WAL mode (5 tests)
│   ├── test_webhook_security.py # Webhook HMAC verification (35 tests)
│   ├── test_mcp_manager.py   # MCPManager chat-based management (21 tests)
│   └── test_clawhub.py       # ClawHub integration (70 tests)
│
├── whatsapp_service/          # Node.js Baileys microservice (port 3979)
│
├── data/                      # Runtime data (.gitignored)
│   ├── sessions/              # JSONL conversation files + sessions.json index
│   ├── memory.db              # SQLite memory store
│   └── personality/           # Personality files
│       ├── PERSONALITY.md     # Base personality definition
│       ├── MOODS.md           # Mood & user relationships
│       ├── NEW_PERSONALITY.md # Learned traits
│       ├── agents/            # Persona profiles (YAML frontmatter + markdown)
│       │   ├── default.md     # 🤖 Base — no modifications
│       │   ├── formal.md      # 👔 Professional, structured
│       │   ├── casual.md      # 😊 Friendly, relaxed
│       │   └── technical.md   # 💻 Developer-focused, concise
│       └── user_profiles.json # User→persona & channel→persona mappings
│
├── docs/                      # All setup/architecture documentation
│   ├── ARCHITECTURE.md
│   ├── LLM_PROVIDERS.md
│   ├── MEMORY_SYSTEM.md
│   ├── MCP_SETUP.md
│   ├── TELEGRAM_SETUP.md
│   └── ... (15 doc files)
│
├── scripts/                   # Dev/test scripts
│   ├── test_local.py          # Local testing (no credentials)
│   ├── qa_test_framework.py   # QA test suite
│   └── rebuild_launch_services.sh
│
├── config.py                  # Central configuration (secrets, .gitignored)
├── config.example.py          # Example config
├── pyproject.toml             # Package definition (pip install -e ., coco-b CLI)
├── requirements.txt           # Python dependencies
├── mcp_config.json            # MCP server configurations
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # All channels as compose profiles
├── .dockerignore              # Docker build exclusions
├── README.md                  # Project readme
├── CHANGELOG.md               # Version history
└── todo.md                    # Roadmap
```

---

## Architecture Overview

```
Channels (Flet, Gradio, Teams, Telegram, WhatsApp, Discord, Slack)
                        │
                        ▼
              MessageRouter (coco_b.core.router)
              ┌─────────┼──────────┐──────────────────┐
              ▼         ▼          ▼                   ▼
        SessionMgr  Personality  MCP Tools      Agentic Modules
        (JSONL)     (Skills +    (External)     ├─ AuthManager
                     Personas)
              │                                 ├─ HeartbeatManager
              ▼                                 ├─ PatternDetector
        Memory Store (SQLite FTS5)              ├─ BackgroundTaskRunner
              │                                 └─ MCPServerManager
              ▼
        LLM Provider (Factory Pattern → 15+ providers)
              │
              ▼
        AI Response (streamed)
```

### Message Flow

1. Channel receives user message → calls `router.handle_message(channel, user_id, message, chat_id, user_name)`
2. Router gets/creates session via SessionManager
3. User message saved to JSONL file
4. Conversation history loaded (max 20 messages + summaries)
5. Context checked, compacted if >80% full (automatic summarization)
6. System prompt built from PERSONALITY.md + persona override (if assigned) + skills list
7. If message starts with `/skillname`, skill instructions injected into prompt
8. AI response generated (streaming supported)
9. Response parsed for mood/personality update blocks
10. Assistant response saved to JSONL
11. Cleaned response returned to channel

---

## Key Components

### SessionManager (`coco_b.core.sessions`)
- Two-tier storage: `sessions.json` index + per-session JSONL files
- Session key format: `{channel}:{chatType}:{userId}[:chatId]`
- JSONL entry types: session header, message, compaction
- Input validation against path traversal, 100KB message limit

### MessageRouter (`coco_b.core.router`)
- Central orchestrator for all message handling
- **Session commands**: `/reset`, `/stats`, `/help`, `/skills`, `/memory`, `/forget`
- **File access**: `/setpassword`, `/unlock`
- **Auth**: `/pin <pin>`, `/login <password>`, `/logout`, `/auth status`
- **Heartbeat**: `/summary`, `/heartbeat enable|disable|status <type>`
- **Patterns**: `/patterns`, `/patterns dismiss <id>`, `/patterns stats`
- **Personas**: `/persona`, `/list-personas`, `/set-persona <name>`, `/create-persona <name> [desc]`
- **Tasks**: `/tasks list|status|delete|pause|resume <id>`
- **MCP**: `/mcp list|verified|install|confirm|cancel|enable|disable|uninstall`
- **ClawHub**: `/clawhub search|install|list|info|uninstall|updates`
- Skill detection: `/commit msg` → finds "commit" skill → injects instructions
- Per-key prompt cache: `_prompt_cache[user_id:channel]` auto-invalidated on file/persona changes
- Context compaction at 80% threshold
- `start_services()` launches heartbeat & background task scheduler loops
- `record_interaction()` feeds PatternDetector before every LLM call

### LLM Providers (`coco_b.core.llm`)
- **Factory**: `LLMProviderFactory.create(config)` → `LLMProvider`
- **LLMConfig** dataclass: provider, model, base_url, api_key, context_window, max_response_tokens, temperature, timeout
- **Providers**: Ollama, OpenAI, Anthropic, Gemini, Groq, Together, Azure, Kimi, LM Studio, vLLM, MLX, Llama.cpp, Claude CLI, Gemini CLI
- **CLI providers**: Use `input=''` in subprocess.run() to prevent hanging
- **Config**: `LLM_PROVIDER` selects active, `LLM_PROVIDERS` dict has all configs

### Memory (`coco_b.core.memory.sqlite_memory`)
- SQLite with FTS5 full-text search, zero external dependencies
- Tables: `facts` (user_id, fact, category), `conversations` (user_id, messages, summary)
- Fact extraction via 40+ regex patterns (names, preferences, traits)
- Categories: info, preference, trait

### Skills (`coco_b.core.skills`)
- SKILL.md format: YAML frontmatter (name, description, user-invocable, emoji) + markdown body
- Load priority: `~/.mr_bot/skills/` > `./skills/` > bundled
- User invokes via `/skillname args` in chat
- SkillsManager: load_all_skills(), get_skill(), save_skill(), create_skill()

### Personality & Personas (`coco_b.core.personality`)
- Reads PERSONALITY.md (base), MOODS.md (relationships), NEW_PERSONALITY.md (learned)
- AI can self-update via special code blocks in responses:
  - `` ```mood-update `` → updates MOODS.md
  - `` ```personality-insight `` → appends to NEW_PERSONALITY.md
- **Multi-Persona System**:
  - `Persona` dataclass: name, description, emoji, instructions, file_path
  - Persona files in `data/personality/agents/*.md` — YAML frontmatter + markdown body (same as SKILL.md)
  - 4 built-in personas: default (🤖), formal (👔), casual (😊), technical (💻)
  - `resolve_persona(user_id, channel)` — user override > channel default > None
  - `get_system_prompt(mode, user_id, channel)` — layers persona instructions between base personality and skills list
  - Full CRUD: `create_persona()`, `update_persona()`, `delete_persona()`
  - User/channel mappings persisted in `data/personality/user_profiles.json`

### MCP Integration (`coco_b.core.mcp_client`, `coco_b.core.mcp_tools`)
- MCPClient: single server connection (STDIO/Docker/SSE/HTTP)
- MCPManager: manages multiple servers from mcp_config.json
- MCPToolHandler: integrates tools into chat flow
- Configured servers: Playwright, Google Workspace, Filesystem, GitHub, etc.

### AuthManager (`coco_b.core.auth_manager`)
- Four-tier security: GREEN (none), YELLOW (PIN), ORANGE (password), RED (password + confirm)
- PBKDF2-HMAC-SHA256 password hashing, 4-digit PIN for routine tasks
- Session management: 30 min for PIN, 60 min for password, auto-extend on activity
- Persists sessions to disk, clears with `/logout`

### HeartbeatManager (`coco_b.core.heartbeat_manager`)
- Proactive user check-ins: morning brief, deadline watch, unusual activity, daily summary
- All heartbeats are GREEN level (read-only, no auth required)
- Per-user configuration, configurable schedule times

### PatternDetector (`coco_b.core.pattern_detector`)
- Detects repeated commands/workflows (3+ occurrences), suggests skill creation
- Four pattern types: repeated command, repeated workflow, time-based, context-based
- ORANGE level auth required to view/create from suggestions
- 30-day retention limit, dismissed patterns remembered

### BackgroundTaskRunner (`coco_b.core.background_tasks`)
- Periodic background tasks: health checks, data sync, scheduled jobs
- GREEN level to view status, YELLOW level (PIN) to create/modify/delete tasks
- Max 5 concurrent tasks, last 50 results retained

### WebhookSecurity (`coco_b.core.webhook_security`)
- HMAC-SHA256 verification for WhatsApp and Slack webhooks
- Secret token verification for Telegram
- JWT Bearer token validation for MS Teams
- Constant-time comparison prevents timing attacks, timestamp validation prevents replay attacks

### ClawHubManager (`coco_b.core.clawhub`)
- Search, install, and manage community skills from OpenClaw.ai's ClawHub registry (5,700+ skills)
- OpenClaw format adapter: converts OpenClaw SKILL.md (nested emoji, `{baseDir}`, version/author) to coco B `Skill` objects
- 5-minute search result caching, installed skills tracked in `data/clawhub_installed.json`
- Name conflict detection: auto-prefixes `ch-` when slug matches bundled skills
- No auth required (skills are markdown text, not executable code)

### MCPManager (`coco_b.core.mcp_manager`)
- Chat-based MCP server management: install, enable, disable, uninstall servers
- Verified server registry with pre-approved configs (Playwright, Filesystem, GitHub, Gmail, etc.)
- Pending install confirmation flow: verified servers auto-approve, unknown require explicit confirmation
- Integrates with AuthManager for access control

### Scheduler (`coco_b.core.scheduler`, `coco_b.core.schedule_handler`)
- APScheduler with multi-trigger support: CronTrigger, IntervalTrigger, DateTrigger
- Three trigger kinds: `cron` (recurring cron expression), `every` (interval repeat), `at` (one-shot datetime)
- Retry backoff on failure: 30s → 1m → 5m → 15m → 60m (max 5 retries, disabled for one-shot)
- Per-task concurrency control (`max_concurrent`, default 1)
- Human-readable schedule display: cron patterns → plain English
- One-shot tasks auto-delete after successful execution (`delete_after_run`)
- Actions: send_message, execute_skill
- Natural language parsing: `/schedule` skill with cron, interval, and one-shot examples

### FileAccessManager (`coco_b.core.file_access`)
- Password-protected sandboxed file access for bot skill creation
- PBKDF2-HMAC-SHA256 with 600k iterations + random 32-byte salt
- Sandbox enforcement: only `skills/` and `data/user/` are writable
- Per-action auth via pending actions: stores action, prompts for `/unlock`
- Auth file: `data/.file_access_auth` (permissions 0600)

### Todo Handler (`coco_b.core.todo_handler`)
- Parses `` ```todo``` `` code blocks from LLM responses
- Persistent JSON storage in `data/todos.json` (per-user, thread-safe)
- Operations: add, list, done, delete, edit, remind
- Todo fields: id, title, priority (low/medium/high), due, tags, status
- Reminders integrate with SchedulerManager for cron-based alerts

### PermissionManager (`coco_b.core.user_permissions`)
- Per-user role-based permission system — controls which capabilities each user can access
- Config file: `data/user_roles.json` (auto-created when admin commands used)
- 4 built-in roles: `admin` (wildcard), `power_user`, `user`, `restricted` (chat only)
- 14 permissions: chat, web_search, web_fetch, email, calendar, browse, files, schedule, todo, mcp_tools, mcp_manage, skills_create, background_tasks, admin
- Fine-grained: custom_permissions (grants beyond role) and denied_permissions (revocations within role)
- Backward compatible: if `user_roles.json` doesn't exist, all users get full access
- System prompt filtered per user — LLM only sees tool hints for permitted capabilities
- Handler execution gated — schedule, todo, web, skill creation blocks denied if user lacks permission
- Commands: `/my-permissions`, `/user-role`, `/grant`, `/revoke`, `/users`

---

## Channel Details

| Channel | File | Library | Port | Auth |
|---------|------|---------|------|------|
| Flet Desktop | `python -m coco_b ui` | flet>=0.80 | - | - |
| Gradio Web | `python -m coco_b gradio` | gradio>=6.0 | 7777 | - |
| MS Teams | `python -m coco_b bot` | botbuilder-core | 3978 | MSTEAMS_APP_ID/PASSWORD |
| Telegram | `python -m coco_b telegram` | python-telegram-bot>=21 | 8443 (webhook) | TELEGRAM_BOT_TOKEN |
| WhatsApp | `coco_b.channels.whatsapp` + `whatsapp_service/` | Baileys (Node.js) | 3979 | QR scan |
| Discord | `python -m coco_b discord` | discord.py>=2.3 | - | DISCORD_BOT_TOKEN |
| Slack | `python -m coco_b slack` | slack-bolt>=1.18 | - | SLACK_BOT_TOKEN + APP_TOKEN |

---

## Configuration (`config.py`)

Key settings:
- `BOT_NAME`, `BOT_CREATOR` - Identity
- `LLM_PROVIDER` - Active provider name (e.g., "ollama")
- `LLM_PROVIDERS` - Dict of all provider configs
- `SESSION_DATA_DIR` - Where sessions are stored
- `MAX_CONTEXT_TOKENS`, `COMPACTION_THRESHOLD` - Context management
- `MEMORY_DATA_DIR` - Memory database location
- Channel tokens via environment variables

---

## Running the Project

```bash
# First-time setup
pip install -e .

# CLI entry point (registered as console_scripts)
coco-b ui          # Flet desktop UI
coco-b gradio      # Gradio web UI
coco-b bot         # MS Teams Flask server
coco-b telegram    # Telegram bot
coco-b slack       # Slack bot
coco-b discord     # Discord bot
coco-b doctor      # Check config, deps, connections

# Or via python -m
python -m coco_b ui

# Docker
docker compose up              # Gradio (default)
docker compose up telegram     # Telegram bot

# Automated test suite (run after every change)
python -m pytest tests/ -v

# QA tests
python scripts/qa_test_framework.py
```

---

## Key Patterns & Conventions

- **Package layout**: All code in `src/coco_b/`, installed with `pip install -e .`
- **PROJECT_ROOT**: Use `from coco_b import PROJECT_ROOT` for paths to project root resources
- **Factory pattern** for LLM providers
- **Skills-over-tools**: Users invoke `/skill` commands, not raw MCP tools (reduces prompt size)
- **JSONL for history**: Append-only, fast, no DB dependency
- **SQLite for memory**: FTS5 search, zero external deps
- **Streaming**: All providers support streaming responses
- **Context compaction**: Auto-summarize when context hits 80% capacity
- **Security**: Input validation, rate limiting, no hardcoded credentials, no `shell=True`
- **UI color scheme**: Navy (#1A365D) & Gold (#C9A227)

---

## Documentation Index

| File | Topic |
|------|-------|
| docs/ARCHITECTURE.md | Full system design (59KB) |
| docs/LLM_PROVIDERS.md | Provider setup guide (38KB) |
| docs/MEMORY_SYSTEM.md | Memory architecture |
| docs/MCP_SETUP.md | MCP tools integration |
| docs/EMAIL_CALENDAR_SETUP.md | Email/calendar config |
| docs/TELEGRAM_SETUP.md | Telegram bot setup |
| docs/WHATSAPP_SETUP.md | WhatsApp integration |
| docs/MS_TEAMS_SETUP.md | Teams integration |
| docs/DEPLOYMENT.md | Production deployment |
| docs/SECURITY.md | Security docs |
| docs/SETUP_GUIDE.md | Installation |
| docs/QA_CHECKLIST.md | 50+ test cases |
| CHANGELOG.md | Version history & changes |
