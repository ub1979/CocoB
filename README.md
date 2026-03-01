# coco B - Intelligent AI Assistant with Persistent Memory

A powerful, open-source AI assistant framework with persistent memory, multi-channel support, browser automation, and extensible skills. Built by Idrak AI Ltd as a safe open community project.

## Key Features

### Core Capabilities
- **Persistent Memory** - Remembers conversations using ChromaDB vector storage
- **Multi-Provider LLM Support** - 15+ providers including Ollama, OpenAI, Anthropic, Gemini, Groq
- **Self-Improving Personality** - Learns and adapts from conversations
- **Smart Context Management** - Automatic summarization when context gets long

### User Interfaces
- **Flet Desktop App** - Native desktop UI with real-time chat
- **Gradio Web UI** - Browser-based interface
- **MS Teams** - Enterprise integration
- **Telegram, Discord, Slack, WhatsApp** - Multi-channel messaging

### Automation & Tools
- **MCP Protocol Support** - Connect to 100+ MCP tool servers
- **Email Integration** - Gmail support via `/email` command
- **Calendar Integration** - Google Calendar via `/calendar` command
- **Playwright Browser Automation** - Web scraping, searching, form filling
- **Skills System** - Extensible command system (`/google-search`, `/browse`, etc.)
- **Scheduler** - Schedule tasks and reminders

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd coco_B

# Create conda environment (or use existing one)
conda create -n mr_bot python=3.13
conda activate mr_bot

# Install in editable mode
pip install -e .

# Install UI dependencies
pip install -e ".[ui]"

# Configure
cp config/config.example.py config.py
# Edit config.py with your settings

# Run Flet Desktop UI
./cocob.sh

# Or run directly
python -m coco_b.app
```

## Project Structure

```
coco_B/
├── cocob.sh                # Launch script (activates conda + runs UI)
├── pyproject.toml          # Package config & dependencies
├── config.py               # Configuration (user-created)
│
├── src/coco_b/             # Main Python package
│   ├── app.py              # Flet desktop UI (main entry point)
│   ├── bot.py              # Flask webhook server
│   ├── core/
│   │   ├── router.py       # Message routing & skill handling
│   │   ├── sessions.py     # Session management
│   │   ├── personality.py  # Self-improving personality
│   │   ├── scheduler.py    # Task scheduler
│   │   ├── memory/         # ChromaDB long-term memory
│   │   ├── llm/            # Multi-provider LLM support
│   │   ├── mcp_client.py   # MCP protocol client
│   │   └── skills/         # Skills manager & loader
│   └── channels/           # WhatsApp, Telegram, etc.
│
├── skills/                 # Skill definitions (SKILL.md files)
│   ├── email/              # Gmail integration
│   ├── calendar/           # Google Calendar integration
│   ├── google-search/      # Google search with Playwright
│   ├── browse/             # URL browser with Playwright
│   └── ...
│
├── data/                   # Runtime data
│   ├── sessions/           # Conversation transcripts (JSONL)
│   ├── memory/             # Long-term memory files
│   └── personality/        # Persona files & user profiles
│
├── docs/                   # Documentation
├── tests/                  # Test suite (656+ tests)
└── mcp_config.json         # MCP server configurations
```

## LLM Providers

| Provider | Type | Auth Method |
|----------|------|-------------|
| **Ollama** | Local | None (free) |
| **OpenAI** | Cloud | API Key |
| **Anthropic** | Cloud | API Key |
| **Gemini** | Cloud | API Key / CLI |
| **Groq** | Cloud | API Key |
| **Together AI** | Cloud | API Key |
| **Azure OpenAI** | Cloud | API Key |
| **LM Studio** | Local | None |
| **MLX** | Local (Apple) | None |
| **Claude CLI** | CLI | Subscription |
| **Gemini CLI** | CLI | Subscription |

See [LLM_PROVIDERS.md](LLM_PROVIDERS.md) for detailed setup.

## Skills (Commands)

coco B uses a **skills-based architecture** - users interact with simple commands, and skills execute MCP tools directly. This means:
- **Fast responses**: No LLM deciding which tool to call
- **Small prompts**: Tools aren't listed in every message
- **Lower costs**: Fewer tokens used

| Skill | Description |
|-------|-------------|
| `/email <action>` | Manage Gmail - send, search, read emails |
| `/calendar <action>` | Manage Google Calendar - view, create events |
| `/google-search <query>` | Search Google using Playwright (headless) |
| `/browse <url>` | Open URL and get page content |
| `/help` | Show available commands |
| `/reset` | Reset conversation |
| `/stats` | Show session statistics |
| `/skills` | List all available skills |

Type `/` in the chat to see autocomplete suggestions.

### Email & Calendar Integration

Two setup options available:
- **Self-Hosted (FREE)**: Unlimited usage, data stays on your machine
- **Composio**: Easy 5-min setup, 100 free actions/month

```bash
/email check inbox
/email send to john@example.com subject "Hello" body "Hi there!"
/calendar today
/calendar create "Meeting" tomorrow at 3pm
```

See [EMAIL_CALENDAR_SETUP.md](EMAIL_CALENDAR_SETUP.md) for setup instructions.

## MCP Tools Integration

coco B supports the Model Context Protocol (MCP) for connecting to external tools:

```json
// mcp_config.json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["-y", "@playwright/mcp", "--headless"]
    }
  }
}
```

**Available MCP Servers:**
- **Playwright** - Browser automation (22 tools)
- **Filesystem** - File operations
- **GitHub** - Repository management
- **PostgreSQL** - Database queries
- **Brave Search** - Web search API

See [MCP_SETUP.md](MCP_SETUP.md) for details.

## Memory System

### Short-term Memory
- Conversation history in JSONL files
- Automatic context compaction

### Long-term Memory
- ChromaDB vector storage
- Semantic search for relevant context
- Persists across sessions

See [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) for architecture details.

## Configuration

Key settings in `config.py`:

```python
# Active LLM provider
LLM_PROVIDER = "ollama"  # or "openai", "anthropic", etc.

# Ollama config
LLM_PROVIDERS = {
    "ollama": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434/v1",
    }
}
```

## Security Features

- Input validation on all user inputs
- Rate limiting on API endpoints
- Security headers (X-Frame-Options, CSP, etc.)
- Environment variables for secrets
- No hardcoded credentials

See [SECURITY.md](SECURITY.md) for details.

## Documentation

| Document | Description |
|----------|-------------|
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Detailed installation guide |
| [LLM_PROVIDERS.md](LLM_PROVIDERS.md) | LLM provider configuration |
| [MCP_SETUP.md](MCP_SETUP.md) | MCP tools integration |
| [MEMORY_SYSTEM.md](MEMORY_SYSTEM.md) | Memory architecture |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design |
| [SECURITY.md](SECURITY.md) | Security documentation |
| [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md) | Telegram bot setup |
| [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md) | WhatsApp integration |

## Comparison with Similar Projects

| Feature | coco B | OpenClaw.ai |
|---------|--------|-------------|
| Open Source | Yes | Yes |
| Local LLMs | Yes | Yes |
| Persistent Memory | ChromaDB | Yes |
| Browser Automation | Playwright/MCP | Yes |
| Multi-Channel | 6+ channels | 6+ channels |
| Desktop UI | Flet | No |
| Personality System | Yes | No |
| Background Tasks | Basic scheduler | Advanced |

## QA Testing

Run the automated QA test suite to verify everything is working:

```bash
# Run all tests
python qa_test_framework.py

# Quick smoke tests only
python qa_test_framework.py --quick

# Verbose output
python qa_test_framework.py --verbose

# Save results to file
python qa_test_framework.py -o qa_results.txt
```

**Test coverage includes:**
- Module imports and syntax validation
- UI components (dark mode, CLI buttons, chat avatars)
- Session management (creation, persistence, isolation)
- LLM provider factory and connections
- Message routing and command handling
- Skills loading and invocation
- Security (input sanitization, no hardcoded secrets)
- MCP configuration validation

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Mission

**coco B** is a **Safe Open Community Project** by **Idrak AI Ltd**.

Our mission: Make AI technology accessible, useful, and secure for everyone.

- Open source collaboration
- Security by design
- Community-driven development
- Practical AI solutions

## License

Open Source - Safe Open Community Project

---

**Created by:** Syed Usama Bukhari & Idrak AI Ltd Team
