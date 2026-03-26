# SkillForge — Complete Feature List

> Every feature, command, config option, and integration — cataloged for tutorial reference.

---

## 1. Chat Interface

### Built-in Commands
| Command | Description |
|---------|-------------|
| `/help` | Show all available commands and first 5 skills |
| `/reset` (or `/new`) | Reset conversation / start new session |
| `/stats` | Show session statistics (messages, tokens, uptime) |
| `/skills` | List all available user-invocable skills |
| `/think <level>` | Set creativity level: `off`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `/persona` | Show current persona info |
| `/list-personas` | List all available personas |
| `/set-persona <name>` | Assign persona (use `default` to reset) |
| `/create-persona <name>` | Create a new persona interactively |
| `/memory` | View stored facts about you |
| `/forget <keyword>` | Delete matching memory facts |
| `/mcp list\|verified\|install\|confirm\|cancel\|enable\|disable\|uninstall` | Manage MCP servers |
| `/clawhub search\|install\|list\|info\|uninstall\|updates` | Manage ClawHub skills |
| `/<skill-name>` | Invoke any user-invocable skill |

### Chat Features
- Real-time streaming responses
- Slash command autocomplete popup (up to 8 suggestions)
- User/model info bar showing active LLM provider + model
- Auto-scroll to latest message
- Welcome message with quick-start commands
- Session persistence across app restarts

---

## 2. LLM Providers (17+)

### Provider Types

| Category | Providers |
|----------|-----------|
| **Local servers** | Ollama, vLLM, LM Studio, MLX, llama.cpp (GGUF) |
| **CLI (subscription)** | Claude Code CLI, Gemini CLI |
| **Cloud API** | OpenAI, Anthropic, Groq, Together, Azure OpenAI, Kimi/Moonshot, Google Gemini, Vertex AI |

### Provider Features
- **Streaming**: All providers support `chat_stream()` for real-time token output
- **Token counting**: `estimate_tokens()` — tiktoken for OpenAI, native for llama.cpp, ~4 chars/token fallback
- **Context management**: `check_context_size()` — auto-detect when compaction needed
- **Conversation summarization**: LLM-powered summary for context compaction
- **Factory pattern**: `LLMProviderFactory.create(config)` — unified creation
- **Custom providers**: `LLMProviderFactory.register(name, class)` — extensible

### Configuration Per Provider
```python
LLMConfig(
    provider="...",          # Provider name
    model="...",             # Model identifier
    base_url="...",          # API endpoint (optional)
    api_key="...",           # API key (optional)
    auth_method="...",       # "api_key", "cli", "oauth", or "env"
    context_window=4096,     # Max context tokens
    max_response_tokens=4096,# Max response tokens
    temperature=0.7,         # Sampling temperature
    timeout=60,              # Request timeout (seconds)
    extra={},                # Provider-specific options
)
```

### OAuth Authentication
- **Supported**: Anthropic (Claude Pro/Max), Google Gemini (Google One AI Premium)
- **Flow**: PKCE OAuth 2.0 with automatic browser redirect
- **Token refresh**: Automatic with 5-minute buffer
- **Credential storage**: `~/.skillforge/credentials.json` (chmod 0600)
- **CLI**: `python -m core.llm.auth login|status|logout <provider>`

### Think Levels (`/think`)
| Level | Temperature | Behavior |
|-------|-------------|----------|
| `off` | 0.0 | Deterministic, no randomness |
| `minimal` | 0.2 | Very focused, minimal creativity |
| `low` | 0.4 | Focused with slight variation |
| `medium` | 0.7 | Balanced (default) |
| `high` | 0.9 | Creative, more varied responses |
| `xhigh` | 1.2 | Maximum creativity and exploration |

---

## 3. Memory System

### SQLite FTS5 Memory (Primary)
- **Storage**: `data/memory.db` — zero dependencies, instant startup
- **Full-text search**: FTS5 virtual tables with ranking
- **Fact extraction**: 12 regex patterns for automatic learning:
  - Name: "my name is X"
  - Preferences: "I like/love/enjoy/prefer X"
  - Dislikes: "I hate/dislike/don't like X"
  - Identity: "I am [a/an] X"
  - Work: "I work at/for/in X"
  - Location: "I live in X"
  - Origin: "I'm from X"
  - Favorites: "my favorite X is Y"
  - Languages: "I speak X"
  - Learning: "I'm learning X"
  - Age: "I'm X years old"
- **LLM-assisted extraction**: Second-pass fact extraction via LLM for complex statements
- **Fact categories**: `info`, `preference`, `trait`, `llm_extracted`
- **Context injection**: ~500 tokens injected into system prompt (facts 60%, conversations 40%)
- **User isolation**: All data scoped per user_id
- **Deduplication**: Exact duplicate detection, timestamp update on re-mention
- **User commands**: `/memory` (view facts), `/forget <keyword>` (delete matching)

### ChromaDB Memory (Legacy, Optional)
- **Storage**: `data/memory_db/` — requires chromadb package
- **Semantic search**: Vector embeddings for similarity matching
- **Kept for backward compatibility**, SQLite FTS5 is the default

---

## 4. Skills System

### Architecture
- **3-tier hierarchy** (higher priority overrides lower):
  1. **User skills**: `~/.skillforge/skills/`
  2. **Project skills**: `./skills/`
  3. **Bundled skills**: `<package>/skills/`
- **Format**: SKILL.md with YAML frontmatter + markdown instructions
- **Invocation**: `/skill-name` in chat

### Skill File Format
```yaml
---
name: skill-name
description: One-line description
emoji: "icon"
user-invocable: true
version: "1.0.0"
author: "author-name"
---

# Instructions for the LLM...
```

### 16 Bundled Skills

| Skill | Emoji | Description | Key Actions |
|-------|-------|-------------|-------------|
| **browse** | 🌐 | Open URLs in browser | `/browse <url>` — Playwright page content |
| **calendar** | 📅 | Google Calendar | today, tomorrow, this week, create, free slots, delete, move |
| **commit** | 📝 | Git commit messages | Conventional commits from git status/diff |
| **create-skill** | 🛠️ | Skill CRUD | create, list, delete, update skills |
| **email** | 📧 | Gmail management | check inbox, unread, search, send, draft, reply, archive, labels |
| **explain** | 📖 | Code explanation | Summary → components → flow → concepts → edge cases |
| **files** | 📂 | File management | Browse, search, read, create, move, copy, delete (via MCP) |
| **github** | 🐙 | GitHub ops | Issues, PRs, notifications, repo info |
| **google-search** | 🔍 | Google search | Playwright + summarization |
| **news** | 📰 | RSS news | Headlines, articles, search (HN, BBC, TechCrunch, Reuters) |
| **notes** | 📝 | Note management | create, list, search, edit, delete (stored in ~/notes/) |
| **schedule** | ⏰ | Task scheduling | create, list, pause, resume, delete (cron/interval/one-shot) |
| **search** | 🔍 | Web search | Query → search → analyze → cite sources |
| **social** | 📱 | Twitter/LinkedIn | Draft/post, check feed, search trending |
| **todo** | ✅ | Task management | add, list, done, delete, edit, remind (with priority/due/tags) |

### Code Block Handlers
Skills that emit structured code blocks for execution:

| Handler | Block Pattern | Actions |
|---------|---------------|---------|
| `ScheduleCommandHandler` | ` ```schedule ``` ` | create, list, pause, resume, delete |
| `TodoCommandHandler` | ` ```todo ``` ` | add, list, done, delete, edit, remind |
| `SkillCreatorHandler` | ` ```create-skill ``` ` | create, list, delete, update |
| `WebToolsHandler` | ` ```web_search ``` ` / ` ```web_fetch ``` ` | search, fetch URL |

### Skill Executor (Direct MCP)
Direct MCP execution for: email, calendar, google-search, browse — bypasses LLM round-trip.

---

## 5. Scheduler

### Trigger Types
| Kind | Field | Description |
|------|-------|-------------|
| `cron` | `SCHEDULE: 0 9 * * *` | Standard cron expression |
| `every` | `INTERVAL: 30m` | Repeat every N seconds/minutes/hours |
| `at` | `RUN_AT: 2026-02-25T14:00:00` | One-shot at specific datetime, auto-delete |

### Features
- **Retry backoff**: Exponential — 30s → 1m → 5m → 15m → 60m (max 5 retries)
- **Concurrency control**: Per-task `max_concurrent` (default 1)
- **Human-readable display**: Cron → plain English ("Daily at 9:00 AM", "Every 15 minutes")
- **Persistence**: Tasks survive restarts (stored in `data/scheduler/`)
- **Timezone support**: Per-task timezone setting

### Schedule Presets (UI)
Every minute, every 5/15 min, hourly, daily at 9am/6pm, weekly Monday, monthly 1st

### Interval Presets
`30s`, `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `6h`, `12h`, `24h`

---

## 6. Persona System

### Architecture
- **Persona files**: `data/personality/agents/<name>.md` (YAML frontmatter + markdown body)
- **User profiles**: `data/personality/user_profiles.json`
- **Resolution order**: User preference > Channel default > Base personality

### 4 Built-in Personas
- `default` — Standard assistant
- `formal` — Professional, structured
- `casual` — Friendly, conversational
- `technical` — Developer-focused, precise

### Commands
| Command | Description |
|---------|-------------|
| `/persona` | Show current persona |
| `/list-personas` | List all available |
| `/set-persona <name>` | Set persona for yourself |
| `/create-persona <name>` | Create new persona |

### Features
- Per-user persona override
- Per-channel defaults (Telegram, Slack, Discord, etc.)
- System prompt layering (base + persona + skills)
- Per-key prompt cache with invalidation on persona change
- Settings UI section for management

---

## 7. MCP (Model Context Protocol) Integration

### Features
- **Auto-detection**: Discovers MCP servers from Claude Desktop config
- **Import**: One-click import from Claude Desktop configuration
- **Server management**: Add, edit, delete, enable/disable servers
- **Tool discovery**: Lists all tools from connected servers with descriptions
- **Verified servers**: Pre-approved server list
- **Security**: Command validation, path restrictions

### Commands
```
/mcp list              — List configured servers
/mcp verified          — Show verified server catalog
/mcp install <name>    — Install verified server
/mcp confirm           — Confirm pending install
/mcp cancel            — Cancel pending install
/mcp enable <name>     — Enable server
/mcp disable <name>    — Disable server
/mcp uninstall <name>  — Remove server
```

---

## 8. ClawHub (Skill Marketplace)

### Features
- **Search**: 5,700+ community skills from OpenClaw.ai registry
- **Install**: One-click download and install
- **Format adapter**: Converts OpenClaw format to SkillForge SKILL.md
- **Tracking**: Installed skills tracked in `data/clawhub_installed.json`
- **Updates**: Check for newer versions of installed skills
- **Caching**: Search results cached for performance

### Commands
```
/clawhub search <query>  — Search community skills
/clawhub install <slug>  — Install from registry
/clawhub list            — List installed ClawHub skills
/clawhub info <slug>     — View skill details
/clawhub uninstall <name>— Remove installed skill
/clawhub updates         — Check for updates
```

---

## 9. Native Web Tools

### Web Search (`web_search`)
- **Backend**: Brave Search API
- **Config**: Set `BRAVE_SEARCH_API_KEY` in config.py
- **Graceful fallback**: Returns helpful message when key not configured
- **Result count**: 1-20 results (configurable)

### Web Fetch (`web_fetch`)
- **Content types**: HTML (text extracted), plain text, JSON
- **Max chars**: Configurable content truncation
- **HTML stripping**: Removes scripts, styles, extracts readable text

### Usage
LLM automatically emits code blocks when web access is needed:
```
```web_search
QUERY: python asyncio tutorial
COUNT: 5
```

```web_fetch
URL: https://example.com
MAX_CHARS: 5000
```
```

---

## 10. Security

### Tiered Authentication (AuthManager)
| Tier | Color | Method | Session Duration |
|------|-------|--------|-----------------|
| GREEN | 🟢 | None | Unlimited |
| YELLOW | 🟡 | PIN (4-8 digits) | 30 minutes |
| ORANGE | 🟠 | Password | 1 hour |
| RED | 🔴 | Password + confirmation | 1 hour |

### Security Features
- **Password hashing**: PBKDF2-HMAC-SHA256 with 600k iterations
- **Webhook verification**: HMAC-SHA256 with constant-time comparison
- **File access**: Sandboxed FileAccessManager with password protection
- **Credential storage**: Encrypted at `~/.skillforge/credentials.json` (chmod 0600)
- **Config validation**: Warns about placeholder credentials, hardcoded keys, debug mode
- **Path safety**: Defense-in-depth path checking for skill CRUD operations

### Pattern Detection
- Tracks anomalous patterns per session
- Configurable thresholds for alerts

---

## 11. Background & Proactive Tasks

### BackgroundTaskRunner
- Async task execution without blocking chat
- Task status tracking
- Error handling with logging

### HeartbeatManager
- **Generators**: morning_brief, deadline_watch, unusual_activity, daily_summary
- **Per-user config**: Enable/disable individual generators
- **Scheduler loop**: Runs on configured intervals
- **Persistence**: State survives restarts
- **Status**: Infrastructure complete, generators use placeholder templates (not yet wired to real skill outputs)

---

## 12. Session Management

### Features
- **JSONL storage**: Full conversation transcripts in `data/sessions/`
- **Session keys**: `user_id:channel` namespacing
- **Context compaction**: Auto-summarize when approaching context limit (80% threshold)
- **Token tracking**: Per-session token usage statistics
- **History export**: Export conversation history from UI

---

## 13. Channels (7 Platforms)

| Channel | Library | Mode | Key Config |
|---------|---------|------|------------|
| **Flet UI** | Flet | Desktop app | Default launch mode |
| **Gradio** | Gradio | Web browser (`:7777`) | `GRADIO_PORT` |
| **Telegram** | python-telegram-bot | Polling or webhook | `TELEGRAM_BOT_TOKEN` |
| **Slack** | slack-bolt | Socket Mode | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` |
| **Discord** | discord.py | Gateway | `DISCORD_BOT_TOKEN` |
| **WhatsApp** | Baileys (Node.js) | HTTP → QR scan | `service_url` |
| **MS Teams** | Flask + BotFramework | Webhook | `MSTEAMS_APP_ID`, `MSTEAMS_APP_PASSWORD` |

### Common Channel Features
- Async message handling
- Skill invocation via `/skill-name`
- User/channel allowlists
- Chunked message sending (respects per-platform length limits)
- Typing indicators (where supported)

---

## 14. UI Sections (Flet Desktop App)

### Navigation Rail (6 Tabs)
1. **Chat** — Message interface, autocomplete, status badge
2. **Settings** — Appearance, Personas, Bots, Scheduler, LLM Providers, Memory
3. **MCP Servers** — Import, add, edit, enable/disable, view tools
4. **Skills** — Browse bundled/user/project skills, create new, view/edit
5. **ClawHub** — Search, install, uninstall community skills
6. **History** — View/export conversation history

### Settings Subsections
- **Appearance**: Dark mode toggle
- **Personas & Agents**: Create, edit, delete, assign personas; per-channel defaults
- **Messaging Bots**: Telegram, WhatsApp, Slack, Discord configuration forms
- **Proactive Tasks**: Scheduler task list, creation form with presets, execution log
- **LLM Providers**: Local servers (status + start cmd), CLI providers (install status), Cloud API (key + model)
- **Memory**: Toggle persistence, context limit slider, importance threshold, clear all

---

## 15. Docker Deployment

### Files
- `Dockerfile` — Multi-stage build, Python 3.12-slim
- `docker-compose.yml` — All channels as compose profiles
- `.dockerignore` — Excludes data/, .git/, tests/

### Compose Profiles
```bash
docker compose up                    # Gradio web UI (default)
docker compose --profile telegram up # Telegram bot
docker compose --profile discord up  # Discord bot
docker compose --profile slack up    # Slack bot
docker compose --profile bot up      # MS Teams bot
```

---

## 16. CLI Entry Point (`skillforge`)

```bash
skillforge ui        # Flet desktop app
skillforge gradio    # Gradio web UI at :7777
skillforge bot       # MS Teams Flask server
skillforge telegram  # Telegram bot
skillforge slack     # Slack bot
skillforge discord   # Discord bot
skillforge doctor    # Health check (config, imports, deps, skills)
```

### Doctor Checks
- config.py presence (root or config/)
- data/ directories exist
- Core module imports (5 modules)
- Optional dependencies (7 packages)
- LLM provider configuration
- Bundled skills count

---

## 17. Configuration (`config.py`)

### Key Config Sections
| Section | Key Options |
|---------|-------------|
| **Identity** | `BOT_NAME`, `BOT_CREATOR` |
| **LLM** | `LLM_PROVIDER`, `LLM_PROVIDERS` dict (17+ providers) |
| **Server** | `HOST`, `PORT`, `GRADIO_PORT` |
| **Storage** | `SESSION_DATA_DIR`, `MEMORY_DATA_DIR`, `SCHEDULER_DATA_DIR` |
| **Context** | `MAX_CONTEXT_TOKENS` (100k), `COMPACTION_THRESHOLD` (0.8) |
| **Skills** | `SKILLS_DIR`, `USER_SKILLS_DIR` |
| **Scheduler** | `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE` |
| **Telegram** | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_WEBHOOK_*` |
| **Discord** | `DISCORD_BOT_TOKEN`, `DISCORD_COMMAND_PREFIX`, `DISCORD_ALLOWED_*` |
| **Slack** | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_ALLOWED_*` |
| **MS Teams** | `MSTEAMS_APP_ID`, `MSTEAMS_APP_PASSWORD` |
| **Web Tools** | `BRAVE_SEARCH_API_KEY` (optional) |

---

## 18. Package & Install

### Install
```bash
pip install -e .              # Base install
pip install -e ".[all]"       # All optional deps
pip install -e ".[telegram]"  # Just Telegram
pip install -e ".[dev]"       # Dev tools (pytest)
```

### Optional Dependency Groups
`gradio`, `telegram`, `discord`, `slack`, `teams`, `memory`, `whatsapp`, `ui`, `all`, `dev`

---

## 19. Test Suite (848+ tests)

| Test File | Count | Coverage |
|-----------|-------|----------|
| `test_imports.py` | 21 | Core module imports |
| `test_skills_loading.py` | — | SKILL.md parsing |
| `test_todo_handler.py` | — | Todo CRUD |
| `test_schedule_handler.py` | 26 | Schedule handler + new triggers |
| `test_scheduler.py` | 49 | Scheduler engine (triggers, retry, concurrency) |
| `test_router.py` | — | Router init, skills, commands |
| `test_integration_chat.py` | 196 | End-to-end × 3 providers |
| `test_auth_manager.py` | 42 | Tiered auth |
| `test_background_tasks.py` | 30 | Background task runner |
| `test_heartbeat_manager.py` | 27 | Heartbeat system |
| `test_pattern_detector.py` | 25 | Pattern detection |
| `test_webhook_security.py` | 35 | Webhook HMAC |
| `test_personas.py` | 55 | Persona system |
| `test_clawhub.py` | 70 | ClawHub integration |
| `test_think_levels.py` | 20 | Think level control |
| `test_web_tools.py` | 29 | Web search/fetch |
| `test_cli.py` | 8 | CLI entry point |
| Others | — | SQLite, MCP security, sessions, file access |
