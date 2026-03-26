# SkillForge

**An open-source AI assistant framework that remembers everything, works everywhere, and does what you tell it.**

SkillForge gives you a single AI assistant that connects to your favourite LLM (local or cloud), remembers your conversations across sessions, and reaches into the real world through skills, scheduling, email, calendar, browser automation, and more — all from one interface, on any channel.

Built by [Idrak AI Ltd](https://github.com/ub1979) as a safe, open community project.

---

## Why SkillForge?

Most AI chat apps forget you the moment you close the window. SkillForge doesn't.

- **Persistent memory** — your conversations are stored locally and searchable across sessions. The assistant remembers context from days or weeks ago.
- **Any LLM, your choice** — swap between 15+ providers (Ollama, OpenAI, Anthropic, Gemini, Groq, LM Studio, and more) without changing a single line of your conversation.
- **One assistant, every channel** — talk to the same bot from a desktop app, a web browser, Telegram, Discord, Slack, WhatsApp, or MS Teams. Your history and personality follow you.
- **Skills, not just chat** — built-in commands (`/email`, `/calendar`, `/todo`, `/browse`, `/schedule`) let the assistant take action, not just talk about it.
- **Extensible by design** — write a markdown file, drop it in a folder, and you have a new skill. Or install community skills from ClawHub with one command.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/ub1979/skill_forged.git
cd skill_forged

# Set up a Python environment (3.10+)
python -m venv .venv && source .venv/bin/activate
# Or with conda:
# conda create -n skillforge python=3.13 && conda activate skillforge

# Install
pip install -e ".[ui]"

# Configure your LLM provider
cp config/config.example.py config.py
# Edit config.py — at minimum, set LLM_PROVIDER (e.g. "ollama")

# Launch the desktop UI
python -m skillforge ui
```

Other launch modes:

```bash
skillforge ui          # Flet desktop app
skillforge gradio      # Browser-based web UI
skillforge telegram    # Telegram bot
skillforge discord     # Discord bot
skillforge slack       # Slack bot
skillforge doctor      # Check config & dependencies
```

---

## Features

### Multi-Provider LLM Support

Use any LLM you want. Switch providers at runtime from the UI — no restart needed.

| Provider | Type | Auth |
|----------|------|------|
| Ollama | Local (free) | None |
| LM Studio | Local (free) | None |
| MLX | Local (Apple) | None |
| LlamaCpp | Local | None |
| OpenAI | Cloud | API Key |
| Anthropic | Cloud | API Key |
| Google Gemini | Cloud | API Key / CLI |
| Groq | Cloud | API Key |
| Together AI | Cloud | API Key |
| Azure OpenAI | Cloud | API Key |
| Claude CLI | CLI | Subscription |
| Gemini CLI | CLI | Subscription |

### Persistent Memory

Conversations are stored in JSONL transcripts with full-text search via SQLite FTS5. The assistant loads relevant context from past sessions automatically — no manual re-prompting needed.

- **Short-term**: per-session conversation history with automatic context compaction when things get long
- **Long-term**: SQLite FTS5 semantic storage that persists across sessions and survives restarts

### Multi-Channel Support

Deploy to one or all channels. Each channel shares the same router, memory, and personality system.

| Channel | Library | Features |
|---------|---------|----------|
| **Desktop App** | Flet | Native UI, image attachments, skill autocomplete |
| **Web UI** | Gradio | Browser-based, no install needed |
| **Telegram** | python-telegram-bot | Photos, commands, groups |
| **Discord** | discord.py | DMs, servers, mentions |
| **Slack** | slack-bolt | Socket Mode, channels, DMs |
| **WhatsApp** | Baileys (Node.js) | Images, groups, QR auth |
| **MS Teams** | Bot Framework | Webhooks, enterprise SSO |

### Skills System

Skills are markdown files with YAML frontmatter. Users invoke them with `/` commands. Skills can execute MCP tools directly — no LLM tool-calling overhead.

| Skill | What it does |
|-------|-------------|
| `/email` | Send, search, read Gmail |
| `/calendar` | View, create Google Calendar events |
| `/browse` | Fetch and extract content from any URL |
| `/todo` | Manage tasks with priorities, due dates, tags |
| `/schedule` | Set reminders and recurring tasks |
| `/github` | Manage issues, PRs, notifications |
| `/notes` | Create and search markdown notes |
| `/files` | Browse and read local files (sandboxed) |
| `/news` | Headlines from Hacker News, BBC, Reuters |
| `/create-skill` | Generate new skills from natural language |

Type `/` in the chat to see all available skills with autocomplete.

**Community skills**: Search and install from 5,700+ skills on ClawHub:
```
/clawhub search "data analysis"
/clawhub install skill-name
```

### MCP Integration

Connect to any [Model Context Protocol](https://modelcontextprotocol.io/) server for extended capabilities:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp", "--headless"]
    }
  }
}
```

Manage MCP servers from the UI or via chat commands. Verified servers (Playwright, Filesystem, GitHub, Gmail) auto-approve; unknown servers require confirmation.

### Image & Vision Support

- Send images to vision-capable LLMs for analysis
- Generate images via MCP tools
- Native image delivery on Telegram, WhatsApp, and the desktop UI
- Supported formats: JPEG, PNG, GIF, WebP, BMP

### Task Scheduling

Natural language scheduling backed by APScheduler:

```
"Remind me to check email every morning at 9am"
"Send a summary to the team channel every Friday at 5pm"
"Remind me about the meeting in 30 minutes"
```

Supports cron, interval, and one-shot triggers with retry logic and persistence across restarts.

### Personality System

- Customisable base personality via `PERSONALITY.md`
- Per-user and per-channel persona assignments
- 4 built-in personas (default, formal, casual, technical)
- Self-improving: learns from conversations and updates its own personality notes

### Security & Permissions

- **Tiered authentication**: GREEN (no auth) → YELLOW (PIN) → ORANGE (password) → RED (password + confirm)
- **15 granular permissions**: chat, web_search, email, calendar, files, schedule, mcp_tools, admin, and more
- **4 built-in roles**: admin, power_user, user, restricted
- **Admin panel**: manage users, approve permission requests, link cross-platform identities
- Input validation, rate limiting, webhook signature verification, path traversal prevention

### Native Web Tools

Built-in web search (Brave API with DuckDuckGo fallback) and URL fetching — no MCP server required for basic web access. The assistant detects search-worthy queries (weather, news, prices) and fetches results automatically before responding.

---

## Project Structure

```
skill_forged/
├── src/skillforge/
│   ├── __main__.py              # CLI entry point
│   ├── core/
│   │   ├── router.py            # Message routing & orchestration
│   │   ├── sessions.py          # Session management (JSONL)
│   │   ├── personality.py       # Personality & mood system
│   │   ├── scheduler.py         # APScheduler wrapper
│   │   ├── auth_manager.py      # Tiered authentication
│   │   ├── user_permissions.py  # Role-based access control
│   │   ├── image_handler.py     # Image validation & storage
│   │   ├── web_tools.py         # Native web search & fetch
│   │   ├── memory/              # SQLite FTS5 + ChromaDB
│   │   ├── llm/                 # 12+ LLM provider implementations
│   │   ├── skills/              # Skill loader & manager
│   │   └── mcp_client.py        # MCP protocol client
│   ├── channels/                # Telegram, Discord, Slack, WhatsApp
│   └── flet/                    # Desktop UI (9 views, components, theme)
│
├── skills/                      # 16 bundled skill definitions
├── tests/                       # 1,200+ automated tests
├── docs/                        # Setup guides & architecture docs
├── config.py                    # Your local configuration
└── mcp_config.json              # MCP server definitions
```

---

## Configuration

All configuration lives in `config.py` (copy from `config/config.example.py`):

```python
LLM_PROVIDER = "ollama"

LLM_PROVIDERS = {
    "ollama": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434/v1",
    }
}
```

Channel tokens (Telegram, Discord, Slack) are set via environment variables or the settings UI. See the [setup guides](docs/) for each channel.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design and module overview |
| [Email & Calendar Setup](docs/EMAIL_CALENDAR_SETUP.md) | Gmail and Google Calendar integration |
| [MCP Setup](docs/MCP_SETUP.md) | Connecting MCP tool servers |
| [Memory System](docs/MEMORY_SYSTEM.md) | How memory storage works |
| [Telegram Setup](docs/TELEGRAM_SETUP.md) | Running the Telegram bot |
| [WhatsApp Setup](docs/WHATSAPP_SETUP.md) | WhatsApp via Baileys |
| [Security](docs/SECURITY.md) | Security architecture |
| [Contributing](CONTRIBUTING.md) | How to contribute |

---

## Testing

```bash
# Run the full test suite
python -m pytest tests/ -v

# Run a specific module
python -m pytest tests/test_router.py -v
```

The test suite covers core modules, all skill definitions, security systems, UI components, and end-to-end integration flows across multiple LLM backends.

---

## Contributing

We welcome contributions of all kinds — bug reports, feature requests, new skills, documentation improvements, or code. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

The easiest way to contribute is to write a new skill: create a `SKILL.md` file, drop it in `skills/your-skill/`, and it works automatically.

---

## License

MIT License — Safe Open Community Project

---

**Created by** Syed Usama Bukhari & the Idrak AI Ltd team
