# Architecture Documentation

## Overview

**coco B** is an AI chatbot with persistent memory, designed for multi-channel deployment. It uses a two-tier storage architecture that preserves complete conversation history while managing context window limits intelligently. Built with security in mind by Idrak AI Ltd.

### Core Philosophy

- **Full history preservation**: Every message is stored in JSONL files, never deleted
- **Smart context management**: When context window fills up, older messages are summarized (compacted)
- **Long-term memory**: ChromaDB enables semantic search across years of conversations
- **Multi-channel ready**: Same bot core works across MS Teams, WhatsApp, Telegram, Gradio UI, and more
- **Self-improving personality**: The bot can learn and update its own personality/mood files
- **Skills over Tools**: Users interact via skills, not raw MCP tools (see Skills Architecture below)

### Key Features

- **Dual-storage memory**: JSONL (full history) + ChromaDB (semantic search)
- Persistent memory across restarts and LLM switches
- Per-user/per-chat session isolation
- Automatic context window management with compaction
- Retrieves relevant past conversations automatically
- Dynamic personality and mood tracking
- MCP (Model Context Protocol) tool integration via Skills

---

## Skills Architecture

### Why Skills Instead of Raw Tools?

coco B uses a **skills-based architecture** instead of exposing raw MCP tools to the LLM:

| Approach | Prompt Size | Speed | Token Cost |
|----------|-------------|-------|------------|
| Raw Tools in Prompt | Large (60+ tools) | Slow | High |
| **Skills (coco B)** | Small (personality only) | Fast | Low |

### How It Works

```
User: /email send to john@example.com subject "Hi" body "Hello!"
         │
         ▼
   ┌─────────────────┐
   │  Skill Detected │  ← Flet UI detects /email command
   │  (/email)       │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Direct MCP Call │  ← Skill calls MCP tool directly
   │ (no LLM needed) │     mcp_manager.call_tool_sync("google-workspace", "send-email", {...})
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Instant Response│  → "✅ Email sent to john@example.com"
   └─────────────────┘
```

### Benefits

1. **Smaller Prompts**: No tool descriptions bloating every message
2. **Faster Responses**: Direct tool execution, no LLM decision-making
3. **Lower Costs**: Fewer tokens = cheaper API calls
4. **Predictable**: Skills always work the same way
5. **User-Friendly**: Simple commands like `/email` instead of JSON tool calls

### Available Skills

| Skill | Command | What It Does |
|-------|---------|--------------|
| Email | `/email` | Check inbox, send, search emails |
| Calendar | `/calendar` | View/create events |
| Google Search | `/google-search` | Search web via Playwright |
| Browse | `/browse` | Open URLs via Playwright |

### Creating New Skills

Users can create custom skills in `~/.coco_B/skills/` or `skills/` folder:

```markdown
---
name: my-skill
description: Does something cool
emoji: 🚀
user_invocable: true
---

# My Skill

Instructions for the skill...
```

For skills that need MCP tools, add direct execution in `flet_ui_complete.py`.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              Communication Channels                                       │
├───────────────────┬─────────────────┬────────────────────┬─────────────────────┬─────────┤
│  Gradio UI        │  Flet UI        │  MS Teams          │  WhatsApp           │Telegram │
│  (gradio_ui.py)   │  (flet_ui_*.py) │  (bot.py)          │  (whatsapp.py)      │(telegram│
│  Port: 7777       │  Desktop/Mobile │  Port: 3978        │  Baileys: 3979      │.py)    │
└─────────┬─────────┴────────┬────────┴─────────┬──────────┴──────────┬──────────┴─────────┘
          │                  │                  │                     │
          └──────────────────┴──────────────────┴─────────────────────┘
                                        ▼
                  ┌─────────────────────┐
                  │   SessionManager    │ ← Two-tier storage:
                  │   (sessions.py)     │   sessions.json (index)
                  │                     │   + JSONL files (history)
                  └──────────┬──────────┘
                             ▼
                  ┌─────────────────────┐
                  │   MessageRouter     │ ← Orchestrates the flow
                  │   (router.py)       │   Handles commands
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   AIClient      │ │ Personality     │ │   MCPManager    │
│   (ai.py)       │ │ Manager         │ │   (mcp_client)  │
│                 │ │ (personality.py)│ │                 │
│ Ollama/OpenAI   │ │ PERSONALITY.md  │ │ External tools  │
│ compatible      │ │ MOODS.md        │ │ via JSON-RPC    │
└─────────────────┘ └─────────────────┘ └─────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│                              Security Layer                                     │
├───────────────────┬─────────────────┬────────────────────┬─────────────────────┤
│  Input Validation │  Rate Limiting  │  Security Headers  │  Safe Process Mgmt  │
│  (sessions.py)    │  (bot.py)       │  (X-Frame-Options) │  (psutil, no shell) │
└───────────────────┴─────────────────┴────────────────────┴─────────────────────┘
```

---

## Project Structure

```
coco_B/
├── bot.py                  # Flask server for MS Teams webhook
├── gradio_ui.py            # Web UI for testing (port 7777)
├── flet_ui_complete.py     # Modern cross-platform desktop UI (Flet)
├── config.py               # Configuration (AI model, ports, paths)
├── test_local.py           # Local testing without credentials
├── LLM_PROVIDERS.md        # LLM provider documentation
│
├── core/                   # Core bot logic
│   ├── llm/                # LLM provider framework
│   │   ├── __init__.py     # Package exports
│   │   ├── base.py         # LLMProvider ABC + LLMConfig
│   │   ├── openai_compat.py      # OpenAI-compatible providers
│   │   ├── anthropic_provider.py # Anthropic Claude (API key)
│   │   ├── gemini_provider.py    # Google Gemini (API key)
│   │   ├── claude_cli_provider.py  # Claude Code CLI wrapper (subscription)
│   │   ├── gemini_cli_provider.py  # Gemini CLI wrapper (subscription)
│   │   ├── factory.py      # LLMProviderFactory
│   │   └── auth/           # OAuth authentication module (deprecated)
│   │       ├── __init__.py # Auth module exports
│   │       ├── base.py     # Shared OAuth utilities
│   │       ├── gemini.py   # Google Gemini OAuth
│   │       ├── anthropic.py # Anthropic Claude OAuth
│   │       ├── credentials.py # Token storage/refresh
│   │       ├── cli.py      # CLI commands
│   │       └── README.md   # Auth module docs
│   ├── skills/             # Skills framework (prompt templates)
│   │   ├── __init__.py     # Skills module exports
│   │   ├── loader.py       # SKILL.md file parser
│   │   └── manager.py      # SkillsManager class
│   ├── memory/             # Long-term memory (ChromaDB)
│   │   ├── __init__.py     # Memory module exports
│   │   └── chroma_store.py # MemoryStore class for semantic search
│   ├── ai.py               # Backward-compat wrapper for LLM providers
│   ├── sessions.py         # Session & memory management (JSONL)
│   ├── router.py           # Message orchestration + skill handling
│   ├── personality.py      # Mood & personality manager + skills
│   └── mcp_client.py       # MCP tool integration
│
├── ui/                     # Gradio UI modules
│   ├── __init__.py         # UI module exports
│   ├── settings/           # Settings tabs
│   │   ├── __init__.py     # Settings module exports
│   │   ├── state.py        # Shared state management (AppState)
│   │   ├── provider_tab.py # LLM provider configuration UI
│   │   ├── skills_tab.py   # Skills management UI
│   │   ├── connection.py   # Provider connection testing
│   │   └── models.py       # Model discovery for local providers
│   ├── chat/               # Chat interface
│   │   ├── __init__.py     # Chat module exports
│   │   └── handlers.py     # Message handlers with streaming
│   └── components/         # Reusable UI components
│       └── __init__.py     # Future: status indicators, etc.
│
├── channels/               # Channel-specific integrations
│   ├── whatsapp.py         # WhatsApp HTTP client (uses Baileys service)
│   └── telegram.py         # Telegram Bot API integration
│
├── whatsapp_service/       # Node.js WhatsApp service (Baileys)
│   ├── package.json        # Node.js dependencies
│   ├── server.js           # Express API + Baileys WhatsApp
│   ├── auth_info/          # Session data (gitignored)
│   └── README.md           # Service documentation
│
├── skills/                 # Bundled skills (prompt templates)
│   ├── commit/SKILL.md     # Git commit skill
│   ├── search/SKILL.md     # Web search skill
│   └── explain/SKILL.md    # Code explanation skill
│
├── data/                   # Runtime data (gitignored)
│   ├── sessions/           # Session storage (JSONL)
│   │   ├── sessions.json   # Session index
│   │   └── sess-*.jsonl    # Conversation transcripts
│   └── memory_db/          # Long-term memory (ChromaDB)
│       └── chroma.sqlite3  # Vector embeddings database
│
├── PERSONALITY.md          # Bot's base personality (editable)
├── MOODS.md                # Current mood & user relationships
├── NEW_PERSONALITY.md      # Learned personality traits
├── mcp_config.json         # MCP server configuration
├── MEMORY_SYSTEM.md        # Memory architecture documentation
│
└── *.md                    # Setup guides and documentation
```

---

## Core Components

### SessionManager (`core/sessions.py`)

**Purpose**: Manages conversation sessions with persistent JSONL storage using a secure two-tier architecture.

**Key Methods**:

| Method | Description |
|--------|-------------|
| `get_session_key(channel, user_id, chat_id)` | Generate unique session key |
| `get_or_create_session(session_key, channel, user_id)` | Get existing or create new session |
| `add_message(session_key, role, content, metadata)` | Append message to JSONL transcript |
| `get_conversation_history(session_key, max_messages)` | Load messages from JSONL file |
| `add_compaction(session_key, summary, tokens_before)` | Add summary when context is full |
| `reset_session(session_key)` | Clear session for fresh start |
| `list_sessions()` | List all active sessions |
| `get_session_stats(session_key)` | Get session statistics |

**Storage Files**:
- `sessions.json`: Index of all sessions (fast lookup)
- `sess-{date}-{uuid}.jsonl`: Full conversation transcript

**Dependencies**: None (uses only standard library)

---

### MemoryStore (`core/memory/chroma_store.py`)

**Purpose**: Long-term memory storage using ChromaDB for semantic search across years of conversations.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│                    User Message                              │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  ChromaDB Search: "Find relevant past conversations"        │
│  → Returns 5 most relevant memories from years of data      │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Context sent to LLM:                                        │
│  ├── System prompt                                           │
│  ├── [Relevant memories from ChromaDB]                       │
│  ├── [Summary of older conversation]                         │
│  └── [Last 20 messages from JSONL]                           │
└─────────────────────────────────────────────────────────────┘
```

**Key Methods**:

| Method | Description |
|--------|-------------|
| `add_memory(content, metadata)` | Store a memory entry |
| `add_conversation_turn(user_msg, assistant_msg)` | Store a conversation exchange |
| `search(query, n_results)` | Semantic search for relevant memories |
| `get_relevant_context(query, user_id)` | Get formatted context for LLM |
| `count()` | Total memories stored |
| `clear()` | Clear all memories |

**How it works with JSONL**:
- **JSONL** = Source of truth, full transcript, ordered history
- **ChromaDB** = Search index for fast semantic retrieval
- Both work together: JSONL stores everything, ChromaDB finds relevant context

**Storage**: `data/memory_db/` (ChromaDB persistent storage)

**Dependencies**: `chromadb>=0.4.0`

**Full Documentation**: See [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) for complete details.

---

### LLM Provider Framework (`core/llm/`)

**Purpose**: Modular framework for integrating multiple LLM providers.

**Supported Providers**:
- OpenAI (and compatible: Ollama, vLLM, Groq, Together AI, Azure, Kimi, LM Studio, MLX)
- Anthropic Claude (API key or OAuth)
- Google Gemini (API key, gcloud ADC, or OAuth)

**Key Classes**:

**LLMProvider** (Abstract Base Class):
| Method | Description |
|--------|-------------|
| `chat(messages, **kwargs)` | Send messages and get AI response |
| `chat_stream(messages, **kwargs)` | Stream AI response |
| `estimate_tokens(text)` | Estimate token count |
| `check_context_size(messages)` | Check if context needs compaction |
| `summarize_conversation(messages)` | Generate summary for compaction |

**LLMConfig** (Dataclass):
| Field | Description |
|-------|-------------|
| `provider` | Provider name (e.g., "ollama", "openai", "anthropic", "gemini") |
| `model` | Model name/identifier |
| `base_url` | API endpoint URL |
| `api_key` | API key (if required) |
| `auth_method` | Auth type: "api_key" (default), "cli", "oauth" |
| `context_window` | Max context tokens |
| `max_response_tokens` | Max response tokens |
| `temperature` | Sampling temperature |
| `timeout` | Request timeout seconds |
| `extra` | Provider-specific options |

**LLMProviderFactory**:
| Method | Description |
|--------|-------------|
| `create(config)` | Create provider from LLMConfig |
| `from_dict(dict)` | Create provider from dictionary |
| `register(name, class)` | Register custom provider |

**Configuration** (from `config.py`):
- `LLM_PROVIDER`: Active provider name (e.g., "ollama", "openai", "anthropic")
- `LLM_PROVIDERS`: Dict of provider configurations

**File Structure**:
```
core/llm/
├── __init__.py             # Package exports
├── base.py                 # LLMProvider ABC + LLMConfig
├── openai_compat.py        # OpenAI-compatible providers
├── anthropic_provider.py   # Anthropic Claude provider (API key)
├── gemini_provider.py      # Google Gemini provider (API key)
├── claude_cli_provider.py  # Claude Code CLI wrapper (subscription)
├── gemini_cli_provider.py  # Gemini CLI wrapper (subscription)
├── factory.py              # LLMProviderFactory
└── auth/                   # OAuth authentication module
    ├── __init__.py         # Auth module exports
    ├── base.py             # Shared OAuth utilities
    ├── gemini.py           # Gemini OAuth
    ├── anthropic.py        # Anthropic OAuth
    ├── credentials.py      # Token storage
    ├── cli.py              # CLI commands
    └── README.md           # Documentation
```

**Dependencies**: `requests`

See `LLM_PROVIDERS.md` for detailed documentation.

---

### CLI-Based Providers (Subscription Access)

**Purpose**: Wrap official CLI tools to use Pro/Max subscriptions without API keys.

> **RECOMMENDED**: Use CLI providers instead of OAuth. OAuth tokens are blocked by both
> Anthropic and Google for third-party tools as of January 2026.

**Supported CLI Providers**:

| Provider | Config Name | CLI Tool | Subscription |
|----------|-------------|----------|--------------|
| Claude Code CLI | `claude-cli` | `@anthropic-ai/claude-code` | Claude Pro/Max |
| Gemini CLI | `gemini-cli` | `@google/gemini-cli` | Google One AI Premium |

**Setup**:
```bash
# Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude login

# Gemini CLI
npm install -g @google/gemini-cli
gemini auth login
```

**How It Works**:
1. CLI tools have their own OAuth authentication (managed by vendor)
2. Our providers wrap the CLI using headless/non-interactive mode (`-p` flag)
3. Messages are sent via subprocess, responses streamed back
4. No API key needed - uses your existing subscription

**Important Implementation Detail** (Fixed 2026-02-07):
Both CLI providers require `input=''` to be passed to `subprocess.run()` because the CLI tools expect stdin input even when using the `-p` flag. Without this, the subprocess hangs indefinitely waiting for input.

```python
# Correct usage - prevents hanging
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=self.config.timeout,
    input=''  # Required: CLI expects stdin even with -p flag
)
```

**ClaudeCLIProvider** (`core/llm/claude_cli_provider.py`):
- Wraps `claude -p "prompt"` command
- Supports streaming via `--output-format stream-json`
- Session continuation with `--resume`
- Fixed: Added `input=''` to prevent subprocess hang

**GeminiCLIProvider** (`core/llm/gemini_cli_provider.py`):
- Wraps `gemini -p "prompt"` command
- Uses CLI's default model (gemini-2.5-pro)
- Streams output line by line
- Fixed: Added `input=''` to prevent subprocess hang

---

### OAuth Authentication Module (`core/llm/auth/`) - DEPRECATED

**Purpose**: Provides OAuth-based authentication for LLM providers.

> **WARNING**: As of January 2026, both Anthropic and Google have blocked OAuth tokens
> from being used by third-party tools. The OAuth login flow works, but API calls fail with
> "OAuth authentication is currently not supported" (Anthropic) or "restricted_client" (Google).
>
> **USE CLI PROVIDERS INSTEAD**: `claude-cli` and `gemini-cli` work with subscriptions.

**Supported Providers** (OAuth blocked, kept for reference):
- Google Gemini (Google One AI Premium subscribers)
- Anthropic Claude (Claude Pro/Max subscribers)

**CLI Usage**:
```bash
python -m core.llm.auth login gemini      # Login to Gemini
python -m core.llm.auth login anthropic   # Login to Anthropic
python -m core.llm.auth status            # Check login status
python -m core.llm.auth logout <provider> # Logout
```

**Module Structure**:

| File | Purpose |
|------|---------|
| `base.py` | Shared OAuth utilities (callback handler, PKCE, flow runner) |
| `gemini.py` | Google Gemini OAuth (credential extraction, login, refresh) |
| `anthropic.py` | Anthropic Claude OAuth (credential extraction, login, refresh) |
| `credentials.py` | Token storage (`~/.mr_bot/credentials.json`) and refresh |
| `cli.py` | CLI commands (login, status, logout) |
| `README.md` | Detailed module documentation |

**Key Functions**:

| Function | Location | Description |
|----------|----------|-------------|
| `run_oauth_flow()` | `base.py` | Generic OAuth 2.0 + PKCE flow |
| `generate_pkce()` | `base.py` | Generate PKCE verifier/challenge |
| `gemini.login()` | `gemini.py` | Run Gemini OAuth flow |
| `anthropic.login()` | `anthropic.py` | Run Anthropic OAuth flow |
| `get_valid_token()` | `credentials.py` | Get token (auto-refresh if expired) |
| `save_credentials()` | `credentials.py` | Store tokens securely |

**How It Works**:
1. OAuth credentials are extracted from installed CLI tools (Gemini CLI, Claude Code)
2. Browser opens for user to authenticate
3. Callback server receives auth code
4. Code exchanged for access + refresh tokens
5. Tokens stored in `~/.mr_bot/credentials.json` (permissions: 0600)
6. Providers use tokens via `get_valid_token()`, auto-refresh when expired

**OAuth Endpoints**:

| Provider | Auth URL | Token URL | Callback Port |
|----------|----------|-----------|---------------|
| Gemini | accounts.google.com | oauth2.googleapis.com | 8085 |
| Anthropic | claude.ai/oauth/authorize | platform.claude.com | 8086 |

**Dependencies**: `requests` (already a project dependency)

See `core/llm/auth/README.md` for detailed documentation.

---

### AIClient (`core/ai.py`) - Backward Compatibility

**Purpose**: Backward-compatible wrapper around the new LLM provider framework.

**Note**: New code should use `LLMProviderFactory` directly. This class is maintained for existing code compatibility.

**Key Methods**:

| Method | Description |
|--------|-------------|
| `chat(messages, stream)` | Send messages and get AI response |
| `chat_stream(messages)` | Stream AI response |
| `estimate_tokens(text)` | Estimate token count |
| `check_context_size(messages)` | Check if context needs compaction |
| `summarize_conversation(messages)` | Generate summary for compaction |

**Dependencies**: `core.llm`

---

### MessageRouter (`core/router.py`)

**Purpose**: Orchestrates the complete message handling flow from channels to AI and back.

**Key Methods**:

| Method | Description |
|--------|-------------|
| `handle_message(channel, user_id, user_message, ...)` | Main async message handler |
| `handle_command(command, session_key)` | Process `/reset`, `/stats`, `/help` |
| `_compact_session(session_key, history)` | Summarize old messages when context full |

**Message Flow**:
1. Get/create session via SessionManager
2. Save user message to JSONL
3. Load conversation history
4. Check context size, compact if needed
5. Build messages with system prompt
6. Get AI response
7. Parse response for mood/personality updates
8. Save assistant response to JSONL
9. Return cleaned response

**Dependencies**: `SessionManager`, `AIClient`, `PersonalityManager`

---

### PersonalityManager (`core/personality.py`)

**Purpose**: Manages the bot's personality, moods, and learned behaviors through markdown files.

**Key Methods**:

| Method | Description |
|--------|-------------|
| `get_system_prompt()` | Build complete prompt from all personality files |
| `update_mood(user_id, mood_data)` | Update MOODS.md for a user |
| `add_personality_insight(category, insight)` | Append to NEW_PERSONALITY.md |
| `parse_response_for_updates(response, user_id)` | Extract mood/personality blocks from AI response |

**Personality Files**:
- `PERSONALITY.md`: Base personality definition
- `MOODS.md`: Current mood and user relationships
- `NEW_PERSONALITY.md`: Learned traits over time

**Self-Improvement**: The AI can include special code blocks in responses to trigger updates:
```
```mood-update
user_id: alice-123
relationship: Friendly
user_state: happy
notes: Great conversation about pizza
```
```

**Dependencies**: None (uses only standard library)

---

### Skills Framework (`core/skills/`)

**Purpose**: Manages reusable prompt templates (skills) that teach the AI how to perform specific tasks.

**What are Skills?**
Skills are markdown files with YAML frontmatter that provide instructions to the AI. They are NOT code - just text that gets injected into the AI's context when invoked.

**SKILL.md Format**:
```markdown
---
name: commit
description: Create git commits with good messages
user-invocable: true
emoji: "📝"
---

# Commit Skill

When the user asks to commit:
1. Run `git status` to see changes
2. Run `git diff` to review what changed
3. Write a commit message using Conventional Commits
4. Execute `git commit -m "message"`
```

**Skill Locations** (priority order - higher overrides lower):

| Location | Priority | Description |
|----------|----------|-------------|
| `~/.mr_bot/skills/` | Highest | User's custom skills |
| `./skills/` | Medium | Project-local skills |
| Built-in (`skills/`) | Lowest | Bundled with mr_bot |

**Key Classes**:

**Skill** (Dataclass):
| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Skill name (used as /command) |
| `description` | str | Short description |
| `instructions` | str | Markdown body with AI instructions |
| `user_invocable` | bool | Show as /command |
| `emoji` | str | Display emoji |
| `source` | str | "bundled", "project", or "user" |
| `file_path` | str | Path for editing |

**SkillsManager**:
| Method | Description |
|--------|-------------|
| `load_all_skills()` | Load skills from all directories |
| `get_skill(name)` | Get skill by name |
| `get_user_invocable_skills()` | Get skills that can be /invoked |
| `save_skill(skill)` | Save skill to disk |
| `delete_skill(name)` | Delete a user skill |
| `create_skill(name, ...)` | Create new skill |

**Usage in Chat**:
```
User: /commit fix the login bug
         │
         ▼
1. Router detects /commit command
2. Finds "commit" skill
3. Injects skill instructions into system prompt
4. AI follows skill instructions
5. AI may use MCP tools if needed
```

**Bundled Skills**:

| Skill | Command | Description |
|-------|---------|-------------|
| commit | `/commit` | Create git commits with good messages |
| search | `/search` | Search the web for information |
| explain | `/explain` | Explain how code works |

**Dependencies**: `pyyaml`

---

### MCPManager (`core/mcp_client.py`)

**Purpose**: Enables the bot to use external tools via the Model Context Protocol.

**Classes**:

**MCPClient** - Single server connection:
| Method | Description |
|--------|-------------|
| `connect()` | Start MCP server and initialize |
| `call_tool(tool_name, arguments)` | Invoke a tool |
| `get_available_tools()` | List tools from server |
| `format_tools_for_ai()` | Format tools as text for AI |
| `disconnect()` | Clean shutdown |

**MCPManager** - Multiple server management:
| Method | Description |
|--------|-------------|
| `load_config()` | Load `mcp_config.json` |
| `connect_all()` | Connect to all configured servers |
| `call_tool(server_name, tool_name, arguments)` | Call tool on specific server |
| `get_all_tools()` | Get tools from all servers |
| `disconnect_all()` | Disconnect all servers |

**Configuration**: `mcp_config.json`
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp-server"]
    }
  }
}
```

**Dependencies**: `asyncio`, `subprocess`

---

## Data Flow

### Message Lifecycle

```
1. User sends message via channel (Teams/WhatsApp/Gradio)
                    ↓
2. Channel adapter extracts: user_id, text, chat_id
                    ↓
3. router.handle_message() called
                    ↓
4. SessionManager.get_session_key() → "msteams:direct:user-123"
                    ↓
5. SessionManager.get_or_create_session() → loads/creates session
                    ↓
6. SessionManager.add_message() → appends user message to JSONL
                    ↓
7. SessionManager.get_conversation_history() → loads recent messages
                    ↓
8. AIClient.check_context_size() → determines if compaction needed
                    ↓
9. [If needed] router._compact_session() → summarizes old messages
                    ↓
10. PersonalityManager.get_system_prompt() → builds full system prompt
                    ↓
11. AIClient.chat() → sends to Ollama/OpenAI, gets response
                    ↓
12. PersonalityManager.parse_response_for_updates() → extract mood updates
                    ↓
13. SessionManager.add_message() → saves assistant response to JSONL
                    ↓
14. Response returned to channel → displayed to user
```

### Session Key Format

Pattern: `{channel}:{chatType}:{userId}[:chatId]`

| Example | Description |
|---------|-------------|
| `msteams:direct:user-123` | Direct message on MS Teams |
| `msteams:group:user-123:chat-456` | Group chat on MS Teams |
| `whatsapp:direct:15551234567` | WhatsApp DM |
| `whatsapp:group:15551234567:group@g.us` | WhatsApp group |
| `gradio:direct:user-001` | Gradio web UI |

### JSONL Entry Types

Each line in a `.jsonl` file is one of:

**Session Header** (first entry):
```json
{
  "type": "session",
  "id": "sess-2024-01-15-a1b2c3d4",
  "timestamp": "2024-01-15T10:30:00",
  "channel": "msteams",
  "userId": "user-123"
}
```

**Message** (user or assistant):
```json
{
  "type": "message",
  "id": "msg-e5f6g7h8",
  "timestamp": "2024-01-15T10:30:05",
  "role": "user",
  "content": "Hello, how are you?"
}
```

**Compaction** (summarized history):
```json
{
  "type": "compaction",
  "id": "comp-i9j0k1l2",
  "timestamp": "2024-01-15T12:00:00",
  "summary": "User discussed pizza preferences and weekend plans...",
  "tokensBefore": 50000,
  "tokensAfter": 500
}
```

---

## Channel Integrations

### MS Teams (`bot.py`)

**Approach**: Webhook-based Flask server

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/messages` | POST | Main webhook for Teams messages |
| `/api/sessions` | GET | Debug: list all sessions |
| `/api/test` | POST | Test endpoint (no Teams needed) |

**Setup**: Requires Azure Bot registration. See `MS_TEAMS_SETUP.md`.

**Port**: 3978 (default)

---

### WhatsApp (`channels/whatsapp.py` + `whatsapp_service/`)

**Approach**: Secure microservice architecture using Baileys (Node.js)

```
┌─────────────┐     HTTP API      ┌──────────────────┐     WebSocket     ┌──────────────┐
│   mr_bot    │ ←───────────────→ │ WhatsApp Service │ ←───────────────→ │ WhatsApp Web │
│  (Python)   │    localhost:3979 │  (Node.js/Baileys)│                   │   Servers    │
└─────────────┘                   └──────────────────┘                   └──────────────┘
```

**Why this approach?**
- **Security**: Uses [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys) - actively maintained
- **No Backdoors**: Avoids outdated/abandoned Python WhatsApp libraries
- **Isolation**: WhatsApp logic separated from main Python bot

**Components**:

| Component | Location | Port | Description |
|-----------|----------|------|-------------|
| Python Client | `channels/whatsapp.py` | - | HTTP client for the Baileys service |
| Baileys Service | `whatsapp_service/` | 3979 | Node.js Express API + Baileys |

**Python Client** (`WhatsAppChannel`):

| Method | Description |
|--------|-------------|
| `check_status()` | Check WhatsApp connection status |
| `get_qr_code()` | Get QR code for authentication |
| `wait_for_connection()` | Wait for QR scan with timeout |
| `send_message(to, message)` | Send message via HTTP API |
| `configure_webhook(url)` | Set webhook for incoming messages |
| `disconnect()` | Disconnect from service |

**Baileys Service Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Connection status |
| `/qr` | GET | Get QR code text |
| `/qr/image` | GET | Get QR code as PNG |
| `/send` | POST | Send a message |
| `/webhook` | POST | Configure incoming webhook |
| `/disconnect` | POST | Disconnect from WhatsApp |

**Setup**:
```bash
cd whatsapp_service
npm install
npm start
# Scan QR code with WhatsApp
```

**Session Storage**: `whatsapp_service/auth_info/` (gitignored)

See `WHATSAPP_TECHNICAL.md` for detailed documentation.

---

### Telegram (`channels/telegram.py`)

**Approach**: Python integration via python-telegram-bot library

**Library**: [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (28k+ GitHub stars)
- Officially recommended by Telegram
- Actively maintained
- Fully async with Python 3.8+

**Architecture**:
```
┌─────────────┐    Bot API    ┌──────────────────┐
│   Telegram  │ ←───────────→ │  TelegramChannel │
│   Servers   │               │    (Python)      │
└─────────────┘               └──────────────────┘
```

**TelegramChannel Class**:

| Method | Description |
|--------|-------------|
| `initialize()` | Set up handlers and application |
| `start_polling()` | Start in polling mode (development) |
| `start_webhook()` | Start in webhook mode (production) |
| `stop()` | Graceful shutdown |
| `send_message(chat_id, message)` | Send a message |
| `send_chunked_message()` | Send long messages in chunks |

**Built-in Commands**:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show available commands |
| `/reset` | Reset conversation |
| `/stats` | Session statistics |

**Skills Support**: Skill commands like `/commit`, `/search` are automatically routed.

**Configuration** (`config.py`):
```python
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS = []  # Empty = allow all
TELEGRAM_WEBHOOK_URL = None  # None = polling mode
TELEGRAM_WEBHOOK_PORT = 8443
```

**Modes**:
- **Polling**: Bot polls Telegram servers (default, works behind NAT)
- **Webhook**: Telegram pushes to your server (production, requires HTTPS)

**Setup**: See `TELEGRAM_SETUP.md` for detailed instructions.

---

### Gradio UI (`gradio_ui.py`)

**Approach**: Direct Python integration via Gradio library

**Features**:
- Chat interface with history
- User ID switching (simulate different users)
- Session statistics display
- Reset conversation button
- Command support (`/help`, `/reset`, `/stats`)

**Port**: 7777

**Run**: `python gradio_ui.py`

---

### Flet UI (`flet_ui_complete.py`) - NEW

**Approach**: Cross-platform desktop UI using Flet (Flutter-based)

**Features**:
- Native desktop app (Windows, macOS, Linux)
- Mobile support (iOS, Android) - future
- Modern Material Design 3 UI
- Organized provider sections by type:
  - **🖥️ Local LLM Servers**: Ollama, vLLM, LM Studio, MLX
  - **⌨️ CLI Providers**: Claude CLI, Gemini CLI (subscription-based)
  - **☁️ Cloud API Providers**: OpenAI, Anthropic, Groq, Together, etc.
- Collapsible sections for clean organization
- Real-time server status monitoring
- CLI installation status checking
- Session management and history viewer
- MCP server management
- Skills management

**Provider Organization**:
```
Settings Tab
├── 🖥️ Local LLM Servers (expanded by default)
│   ├── Server status cards (running/not running)
│   ├── Start command instructions
│   └── Provider selection + model input
├── ⌨️ CLI Providers (subscription-based)
│   ├── CLI installation status
│   ├── Install command instructions
│   └── Provider selection
├── ☁️ Cloud API Providers
│   ├── Provider selection
│   └── API key management
└── 🧠 Memory Settings
```

**Run**: `python flet_ui_complete.py`

**Dependencies**: `flet>=0.80.0`

**Color Palette**: Professional Navy & Gold theme
- Primary: #1A365D (Deep Navy)
- Secondary: #C9A227 (Gold)
- Background: #F7FAFC (Light Gray)

---

## UI Architecture

The Gradio UI is organized into modular components for maintainability and extensibility.

### Directory Structure

```
ui/
├── __init__.py           # UI module exports
├── settings/             # Settings tabs
│   ├── __init__.py       # Settings module exports
│   ├── state.py          # AppState - shared state management
│   ├── provider_tab.py   # LLM provider configuration UI
│   ├── connection.py     # Provider connection testing
│   ├── mcp_tab.py        # MCP tools config (future)
│   └── skills_tab.py     # Skills config (future)
├── chat/                 # Chat interface
│   ├── __init__.py       # Chat module exports
│   └── handlers.py       # Message handlers with streaming
└── components/           # Reusable UI components
    └── __init__.py       # Future: status indicators, etc.
```

### State Management

The `AppState` class (`ui/settings/state.py`) manages shared state between tabs:

| Property | Type | Description |
|----------|------|-------------|
| `session_manager` | SessionManager | Session storage manager |
| `router` | MessageRouter | Message routing with LLM |
| `current_provider` | str | Current provider name |
| `on_provider_change` | Callable | Callback for provider switches |

**Key Methods**:

| Method | Description |
|--------|-------------|
| `switch_provider(name, config)` | Hot-swap to a different LLM provider |
| `get_current_provider_info()` | Get current provider details |
| `get_available_providers()` | List configured provider names |
| `save_as_default(name)` | Set default provider (runtime only) |

### Provider Switching

Providers can be switched at runtime without restarting:

1. User selects provider from dropdown in Settings tab
2. Click "Refresh" to see available models (for local providers)
3. Select a model from the dropdown
4. `AppState.switch_provider()` creates new provider via factory
5. Router's LLM reference is updated
6. Chat continues with new provider immediately

**Custom Provider Support**: Users can configure custom OpenAI-compatible endpoints:
- Enter base URL (e.g., `http://localhost:8080/v1`)
- Enter model name
- Optionally add API key
- Test connection before switching

### Model Discovery

The Settings tab automatically discovers available models for local providers:

| Provider | Discovery Method |
|----------|-----------------|
| Ollama | GET `/api/tags` |
| LM Studio | GET `/v1/models` |
| vLLM | GET `/v1/models` |
| MLX | GET `/v1/models` |
| Anthropic | Static list (Claude models) |
| Gemini | Static list (Gemini models) |

Click the "🔄 Refresh" button to fetch available models.

### OAuth Authentication (UI)

For subscription-based providers (Claude Pro/Max, Google One AI Premium), the Settings tab provides login buttons:

1. Select an OAuth provider (e.g., `anthropic-oauth`, `gemini-oauth`)
2. OAuth section appears with login status
3. Click "🔑 Login" to authenticate via browser
4. After login, the provider can be used immediately

**Supported OAuth Providers**:
- `anthropic-oauth`: Claude Pro/Max subscriptions
- `gemini-oauth`: Google One AI Premium subscriptions

### Adding New Settings Tabs

1. Create `ui/settings/new_tab.py`:

```python
import gradio as gr
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import AppState

def create_new_tab(app_state: "AppState"):
    """Create the new settings tab"""
    with gr.Tab("New Feature"):
        gr.Markdown("### Configure New Feature")
        # Add Gradio components here
        # Use app_state for shared state access
```

2. Export in `ui/settings/__init__.py`:

```python
from .new_tab import create_new_tab
```

3. Import and call in `gradio_ui.py`:

```python
from ui.settings.new_tab import create_new_tab

with gr.Tabs():
    with gr.Tab("Chat"): ...
    create_provider_tab(app_state)
    create_new_tab(app_state)  # New tab
```

### Future Extensibility

| Feature | Tab | Module | Status |
|---------|-----|--------|--------|
| LLM Providers | Settings | `provider_tab.py` | Implemented |
| Skills | Skills | `skills_tab.py` | Implemented |
| MCP Tools | Settings | `mcp_tab.py` | Planned |
| Memory | Settings | `memory_tab.py` | Planned |
| Appearance | Settings | `theme_tab.py` | Planned |

---

## Security Architecture

### Security by Design

mr_bot implements multiple security layers to protect against common vulnerabilities:

### 1. Input Validation Layer (`core/sessions.py`)

| Validation | Implementation | Purpose |
|------------|----------------|---------|
| Session Key Validation | `_validate_input()` | Prevents path traversal attacks |
| Role Validation | `VALID_ROLES` set | Ensures only valid roles (user/assistant/system) |
| Content Length | `MAX_CONTENT_LENGTH` | Prevents DoS via oversized messages |
| Port Validation | Range 1-65535 | Prevents invalid port numbers |

### 2. Process Management Security

**Before (Vulnerable):**
```python
# DANGEROUS - Shell injection possible
subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)
```

**After (Secure):**
```python
# SAFE - Uses psutil, no shell involved
psutil.Process(pid).terminate()
```

### 3. Rate Limiting (`bot.py`)

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/api/messages` | 30/minute | Prevent abuse on main webhook |
| `/api/test` | 10/minute | Stricter limit for test endpoint |
| Default | 200/day, 50/hour | Global limits per IP |

### 4. Security Headers

All responses include:
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - Enables XSS filter
- `Content-Security-Policy: default-src 'self'` - Restricts resources

### 5. Configuration Security

- **Debug Mode**: Controlled by `FLASK_DEBUG` environment variable
- **API Keys**: Must use environment variables (validated on startup)
- **Placeholder Detection**: Warns if default credentials not changed

See [SECURITY.md](SECURITY.md) for complete security documentation.

---

## QA & Testing Architecture

### Automated Testing Framework

The project includes a comprehensive QA framework (`qa_test_framework.py`) that tests:

| Test Category | Tests | Purpose |
|--------------|-------|---------|
| **Session Management** | 5 tests | Creation, persistence, isolation, validation |
| **LLM Providers** | 2 tests | Factory pattern, connection handling |
| **Message Router** | 2 tests | Initialization, command handling |
| **Skills System** | 2 tests | Loading, invocation detection |
| **Security** | 2 tests | Input sanitization, no shell injection |
| **Integration** | 1 test | End-to-end message flow |

**Running Tests:**
```bash
# All tests
python qa_test_framework.py

# Quick tests (excludes performance)
python qa_test_framework.py --quick

# With verbose output
python qa_test_framework.py --verbose

# Save to file
python qa_test_framework.py --output results.txt
```

### Manual Testing

Comprehensive manual testing checklist in [QA_CHECKLIST.md](QA_CHECKLIST.md) covers:
- 50+ test cases across all features
- Provider-specific tests (Ollama, MLX, OpenAI, etc.)
- Security vulnerability tests
- UI/UX testing procedures
- Performance benchmarks

### Test Data Isolation

All tests use isolated test data:
- Test sessions stored in `data/qa_test_sessions/`
- Separate from production data
- Auto-cleanup between test runs

### Continuous Integration

Recommended CI/CD pipeline:
1. Run `python qa_test_framework.py` on every commit
2. Manual QA checklist before releases
3. Security audit for dependency updates

---

## Developer Guide: "Where Do I..."

| Task | Location | Notes |
|------|----------|-------|
| Add a new channel | `channels/` | Create adapter, call `router.handle_message()` |
| Configure Telegram bot | `config.py` | Set `TELEGRAM_BOT_TOKEN` env var |
| Run Telegram bot | `channels/telegram.py` | `python -m channels.telegram` |
| Switch LLM provider (config) | `config.py` | Change `LLM_PROVIDER` (e.g., "ollama", "openai", "anthropic") |
| Switch LLM provider (runtime) | Gradio UI | Settings tab > Select provider > Switch |
| Configure a provider | `config.py` | Edit `LLM_PROVIDERS[provider_name]` dict |
| Add new Settings tab | `ui/settings/` | Create tab module, export, add to `gradio_ui.py` |
| Add a new LLM provider | `core/llm/` | Implement `LLMProvider`, register with factory |
| Add OAuth for a provider | `core/llm/auth/` | See `core/llm/auth/README.md` for guide |
| Login with subscription | CLI | `python -m core.llm.auth login <provider>` |
| Check OAuth status | CLI | `python -m core.llm.auth status` |
| Use subscription auth | `config.py` | Set `auth_method: "oauth"` in provider config |
| Modify base personality | `PERSONALITY.md` | Edit the markdown directly |
| Add MCP tools | `mcp_config.json` | Add server config under `mcpServers` |
| Change session storage location | `config.py` | Update `SESSION_DATA_DIR` |
| Add a new command | `core/router.py` | In `handle_command()` method |
| Modify system prompt logic | `core/personality.py` | In `get_system_prompt()` method |
| Change context compaction threshold | `core/llm/base.py` | 80% threshold in `check_context_size()` |
| Adjust max response tokens | `config.py` | `max_response_tokens` in provider config |
| Add mood tracking fields | `core/personality.py` | In `update_mood()` method |
| Change JSONL message format | `core/sessions.py` | In `add_message()` method |
| Create a new skill | Gradio UI | Skills tab > Create New Skill |
| Create skill manually | `~/.mr_bot/skills/` | Create `skill-name/SKILL.md` |
| Edit bundled skills | Gradio UI | Skills tab > Edit (saves to user dir) |
| List available skills | Chat | Type `/skills` or `/help` |
| Invoke a skill | Chat | Type `/skill-name` (e.g., `/commit`) |
| **Run automated QA tests** | CLI | `python qa_test_framework.py` |
| **Run quick QA tests** | CLI | `python qa_test_framework.py --quick` |
| **Manual QA testing** | See [QA_CHECKLIST.md](QA_CHECKLIST.md) | Follow comprehensive checklist |
| **Add new QA test** | `qa_test_framework.py` | Add test method to `QATestFramework` class |

---

## Adding a New Channel

### Step-by-Step Guide

1. **Create channel file**: `channels/your_channel.py`

2. **Implement adapter class**:

```python
"""
YourChannel Integration

Handles:
- Authentication
- Receiving messages
- Sending responses
"""

import asyncio
from pathlib import Path
from typing import Optional, Callable


class YourChannel:
    """Your channel integration"""

    def __init__(self,
                 message_handler: Callable,
                 config: dict = None):
        """
        Initialize channel

        Args:
            message_handler: Async function from router.handle_message
            config: Channel-specific configuration
        """
        self.message_handler = message_handler
        self.config = config or {}
        self.is_connected = False

    async def connect(self):
        """Connect to the channel service"""
        # Your connection logic here
        self.is_connected = True

    async def handle_incoming(self, raw_message: dict):
        """Process incoming message from channel"""
        # Extract message details
        user_id = raw_message.get('user_id')
        text = raw_message.get('text')
        chat_id = raw_message.get('chat_id')  # None for DMs
        user_name = raw_message.get('user_name')

        # Call the router
        response = await self.message_handler(
            channel='your_channel',  # Channel identifier
            user_id=user_id,
            user_message=text,
            chat_id=chat_id,
            user_name=user_name
        )

        # Send response back
        if response:
            await self.send_message(chat_id or user_id, response)

    async def send_message(self, recipient: str, text: str):
        """Send message to user/chat"""
        # Your send logic here
        pass

    async def disconnect(self):
        """Clean disconnect"""
        self.is_connected = False
```

3. **Create entry point** (if standalone):

```python
# run_your_channel.py
import asyncio
from core.sessions import SessionManager
from core.ai import AIClient
from core.router import MessageRouter
from channels.your_channel import YourChannel
import config

# Initialize bot
session_manager = SessionManager(config.SESSION_DATA_DIR)
ai_client = AIClient(config.AI_BASE_URL, config.AI_MODEL)
router = MessageRouter(session_manager, ai_client)

# Initialize channel
channel = YourChannel(
    message_handler=router.handle_message,
    config={'api_key': 'your_key'}
)

async def main():
    await channel.connect()
    # Your event loop here

if __name__ == "__main__":
    asyncio.run(main())
```

4. **Add setup documentation**: Create `YOUR_CHANNEL_SETUP.md`

---

## Adding MCP Tools

### Configuration

Edit `mcp_config.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp-server"],
      "env": {}
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/allowed/dir"],
      "env": {}
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Using MCP in Code

```python
from core.mcp_client import MCPManager

# Initialize
mcp = MCPManager()

# Connect to all servers
await mcp.connect_all()

# List available tools
all_tools = mcp.get_all_tools()
print(mcp.format_all_tools_for_ai())

# Call a tool
result = await mcp.call_tool(
    server_name='playwright',
    tool_name='playwright_navigate',
    arguments={'url': 'https://example.com'}
)

# Cleanup
await mcp.disconnect_all()
```

### Popular MCP Servers

| Server | Package | Description |
|--------|---------|-------------|
| Playwright | `@playwright/mcp-server` | Browser automation |
| Filesystem | `@anthropic/mcp-server-filesystem` | File operations |
| GitHub | `@anthropic/mcp-server-github` | Repository management |
| PostgreSQL | `@anthropic/mcp-server-postgres` | Database queries |
| Brave Search | `@anthropic/mcp-server-brave-search` | Web search |

---

## Testing

### Local Testing (`test_local.py`)

Test the full message flow without any external services:

```bash
python test_local.py
```

This simulates multiple users and conversations, creating real session files.

### Gradio UI Testing

Interactive testing with a web interface:

```bash
python gradio_ui.py
# Open http://localhost:7777
```

Features:
- Switch between simulated users
- View session statistics
- Reset conversations
- See full JSONL history

### API Testing via curl

Test the Flask server directly:

```bash
# Start server
python bot.py

# Health check
curl http://localhost:3978/

# Send test message
curl -X POST http://localhost:3978/api/test \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "message": "Hello!"}'

# List sessions
curl http://localhost:3978/api/sessions
```

### Testing Commands

```bash
# In Gradio UI or via API
/help   # Show available commands
/stats  # Show session statistics
/reset  # Reset conversation
```

---

## Configuration Reference

All configuration is in `config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_NAME` | `"The Great my_bot"` | Display name |
| `BOT_CREATOR` | `"Dr. Syed Usama Bukhari"` | Creator attribution |
| `MSTEAMS_APP_ID` | `"YOUR_APP_ID_HERE"` | Azure Bot registration ID |
| `MSTEAMS_APP_PASSWORD` | `"YOUR_APP_PASSWORD_HERE"` | Azure Bot secret |
| `LLM_PROVIDER` | `"ollama"` | Active LLM provider name (see options below) |
| `LLM_PROVIDERS` | `{...}` | Dict of all provider configurations |
| `AI_BASE_URL` | (derived) | Backward compat: derived from active provider |
| `AI_MODEL` | (derived) | Backward compat: derived from active provider |
| `HOST` | `"0.0.0.0"` | Server bind address |
| `PORT` | `3978` | Server port |
| `SESSION_DATA_DIR` | `"data/sessions"` | Session storage directory |
| `MEMORY_DATA_DIR` | `"data/memory"` | Memory storage (future) |
| `MAX_CONTEXT_TOKENS` | `100000` | Max tokens before compaction |
| `COMPACTION_THRESHOLD` | `0.8` | Compact at 80% full |

### Environment Variables

For sensitive values, use environment variables:

```python
import os
MSTEAMS_APP_PASSWORD = os.environ.get('MSTEAMS_APP_PASSWORD', 'fallback')
```

### LLM Provider Options

Available values for `LLM_PROVIDER`:

| Provider | Config Name | Auth Method | Description |
|----------|-------------|-------------|-------------|
| **Local Providers** |
| Ollama | `ollama` | None | Local inference (default) |
| LM Studio | `lmstudio` | None | Local GUI-based |
| MLX | `mlx` | None | Apple Silicon optimized |
| vLLM | `vllm` | None | Self-hosted inference |
| **API Key Providers** |
| OpenAI | `openai` | API key | OpenAI API |
| Anthropic | `anthropic` | API key | Claude via API key |
| Google Gemini | `gemini` | API key | Gemini via API key |
| Groq | `groq` | API key | Fast inference |
| Together AI | `together` | API key | Open source models |
| Azure OpenAI | `azure` | API key | Azure-hosted OpenAI |
| Kimi | `kimi` | API key | Moonshot AI |
| **CLI Providers (Subscription)** |
| Claude Code CLI | `claude-cli` | CLI OAuth | Claude Pro/Max subscription |
| Gemini CLI | `gemini-cli` | CLI OAuth | Google One AI Premium subscription |
| **Enterprise/Cloud** |
| Azure OpenAI | `azure-cli` | az login | Azure AD auth |
| Google Gemini | `gemini-vertex` | gcloud | Gemini via Vertex AI |
| **OAuth (BLOCKED)** |
| Anthropic | `anthropic-oauth` | OAuth | ⚠️ Blocked by Anthropic |
| Google Gemini | `gemini-oauth` | OAuth | ⚠️ Blocked by Google |

**CLI Providers** (RECOMMENDED for subscription users):
```bash
# Setup Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude login

# Setup Gemini CLI
npm install -g @google/gemini-cli
gemini auth login

# Set in config.py
LLM_PROVIDER = "claude-cli"    # or "gemini-cli"
```

**OAuth Providers** (DEPRECATED - blocked by vendors):
```bash
# These work for login but API calls are blocked
python -m core.llm.auth login gemini      # Google One AI Premium
python -m core.llm.auth login anthropic   # Claude Pro/Max

# Check status
python -m core.llm.auth status
```

---

## Appendix: File Formats

### sessions.json

```json
{
  "msteams:direct:user-123": {
    "sessionId": "sess-2024-01-15-a1b2c3d4",
    "sessionFile": "data/sessions/sess-2024-01-15-a1b2c3d4.jsonl",
    "createdAt": 1705312200.0,
    "updatedAt": 1705315800.0,
    "channel": "msteams",
    "userId": "user-123",
    "chatType": "direct",
    "messageCount": 24,
    "tokenCount": 0
  }
}
```

### Session JSONL

```
{"type":"session","id":"sess-2024-01-15-a1b2c3d4","timestamp":"2024-01-15T10:30:00","channel":"msteams","userId":"user-123"}
{"type":"message","id":"msg-e5f6g7h8","timestamp":"2024-01-15T10:30:05","role":"user","content":"Hello!"}
{"type":"message","id":"msg-i9j0k1l2","timestamp":"2024-01-15T10:30:08","role":"assistant","content":"Hi there! How can I help?"}
{"type":"compaction","id":"comp-m3n4o5p6","timestamp":"2024-01-15T12:00:00","summary":"User greeted bot...","tokensBefore":50000,"tokensAfter":200}
{"type":"message","id":"msg-q7r8s9t0","timestamp":"2024-01-15T12:00:05","role":"user","content":"What were we talking about?"}
```

### mcp_config.json

```json
{
  "mcpServers": {
    "server_name": {
      "command": "executable",
      "args": ["arg1", "arg2"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

### ~/.mr_bot/credentials.json (OAuth Tokens)

```json
{
  "gemini": {
    "access_token": "ya29.a0AfH6SMB...",
    "refresh_token": "1//0eXYZ...",
    "expires_at": 1707312345.0
  },
  "anthropic": {
    "access_token": "sk-ant-oauth...",
    "refresh_token": "rt-...",
    "expires_at": 1707312345.0
  }
}
```

**Note**: File permissions are set to `0600` (owner read/write only) for security.
