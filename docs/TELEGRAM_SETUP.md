# Telegram Integration Setup

This guide explains how to set up SkillForge for Telegram.

## Overview

SkillForge uses the [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library (28k+ GitHub stars), which is:
- Officially recommended by Telegram
- Actively maintained
- Fully async with Python 3.8+
- Feature-complete with all Bot API methods

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts:
   - Choose a name (e.g., "My AI Assistant")
   - Choose a username (must end in `bot`, e.g., `my_ai_assistant_bot`)
4. Copy the **API token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Set Environment Variable

```bash
# Linux/macOS
export TELEGRAM_BOT_TOKEN="your_token_here"

# Windows (PowerShell)
$env:TELEGRAM_BOT_TOKEN = "your_token_here"

# Or add to .env file
TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. Install Dependencies

```bash
pip install python-telegram-bot>=21.0
```

### 4. Run the Bot

```bash
# Option 1: Standalone Telegram bot (recommended)
python telegram_bot.py

# Option 2: Test the channel module
python -m channels.telegram

# Option 3: With Flet Desktop UI
python skillforge.py
```

## Configuration

Edit `config.py` to customize:

```python
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Restrict access to specific users (optional)
# Leave empty to allow all users
TELEGRAM_ALLOWED_USERS = [
    "123456789",      # User ID
    "username",       # Username (without @)
    "@username",      # Username (with @)
]

# Webhook mode (for production)
TELEGRAM_WEBHOOK_URL = "https://your-domain.com"
TELEGRAM_WEBHOOK_PORT = 8443
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see welcome message |
| `/help` | Show available commands |
| `/reset` | Reset conversation history |
| `/stats` | Show session statistics |

### Skills

Invoke skills with slash commands:

```
/commit fix the login bug
/search latest AI news
/explain this function
```

### Regular Chat

Just send any message to chat with the AI:

```
User: What's the weather like today?
Bot: I don't have real-time weather data, but I can help you...
```

## Architecture

```
┌─────────────┐    Bot API    ┌──────────────┐
│   Telegram  │ ←───────────→ │ TelegramChannel │
│   Servers   │               │  (Python)      │
└─────────────┘               └───────┬────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │ MessageRouter │
                              └───────┬───────┘
                                      │
                          ┌───────────┼───────────┐
                          ▼           ▼           ▼
                    ┌─────────┐ ┌───────────┐ ┌────────┐
                    │  LLM    │ │ Sessions  │ │ Skills │
                    │Provider │ │ Manager   │ │Manager │
                    └─────────┘ └───────────┘ └────────┘
```

## Modes

### Polling Mode (Default)

Best for development and simple deployments:
- No external URL needed
- Works behind NAT/firewalls
- Bot actively polls Telegram servers

```python
# config.py
TELEGRAM_WEBHOOK_URL = None  # Use polling
```

### Webhook Mode (Production)

Best for high-traffic production deployments:
- Requires HTTPS domain
- More efficient for high message volume
- Instant message delivery

```python
# config.py
TELEGRAM_WEBHOOK_URL = "https://your-domain.com"
TELEGRAM_WEBHOOK_PORT = 8443
```

Telegram supports these webhook ports: 443, 80, 88, 8443

## Security

### User Allowlist

Restrict bot access to specific users:

```python
TELEGRAM_ALLOWED_USERS = [
    "123456789",  # Your Telegram user ID
]
```

To find your user ID:
1. Message @userinfobot on Telegram
2. It will reply with your user ID

### Token Security

- Never commit your bot token to version control
- Use environment variables or secrets management
- Rotate token if compromised (via @BotFather → `/revoke`)

## Integration Example

### Standalone Bot

```python
import asyncio
import os
from core.sessions import SessionManager
from core.router import MessageRouter
from core.llm import LLMProviderFactory
from channels.telegram import TelegramChannel, TelegramConfig
import config

async def main():
    # Initialize components
    session_manager = SessionManager(config.SESSION_DATA_DIR)
    llm = LLMProviderFactory.from_dict(config.LLM_PROVIDERS[config.LLM_PROVIDER])
    router = MessageRouter(session_manager, llm)

    # Message handler
    async def handle_message(channel, user_id, user_message, **kwargs):
        response = await router.handle_message(
            channel=channel,
            user_id=user_id,
            user_message=user_message,
            chat_id=kwargs.get('chat_id'),
            user_name=kwargs.get('user_name'),
        )
        return response

    # Create Telegram channel
    tg_config = TelegramConfig(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        allowed_users=config.TELEGRAM_ALLOWED_USERS,
    )

    telegram = TelegramChannel(
        config=tg_config,
        message_handler=handle_message,
    )

    # Start bot
    await telegram.start_polling()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await telegram.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### With Gradio UI

The Gradio UI can run Telegram alongside the web interface:

```python
# In gradio_ui.py
from channels.telegram import TelegramChannel, TelegramConfig

# Create Telegram channel with same message handler
telegram = TelegramChannel(
    config=TelegramConfig(bot_token=config.TELEGRAM_BOT_TOKEN),
    message_handler=lambda **kwargs: router.handle_message(**kwargs),
)

# Start in background
asyncio.create_task(telegram.start_polling())
```

## Troubleshooting

### "Conflict: terminated by other getUpdates request"

Only one polling instance can run at a time. Stop other instances of your bot.

### "Unauthorized" error

Your bot token is invalid. Check with @BotFather.

### Bot not responding

1. Check the token is set correctly
2. Verify the bot is running (check logs)
3. Ensure your user ID is in the allowlist (if configured)

### Webhook not working

1. Ensure HTTPS (Telegram requires it)
2. Check port is one of: 443, 80, 88, 8443
3. Verify SSL certificate is valid
4. Check firewall allows incoming connections

## Bot Features via BotFather

Enhance your bot with these @BotFather commands:

```
/setdescription - Bot description
/setabouttext - About text
/setuserpic - Bot profile picture
/setcommands - Command suggestions (see below)
```

### Setting Commands

Send to @BotFather:
```
/setcommands
```

Then paste:
```
start - Start the bot
help - Show help
reset - Reset conversation
stats - Show session stats
commit - Help with git commits
search - Search the web
explain - Explain code
```

## Resources

- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Bot Features](https://core.telegram.org/bots/features)
- [@BotFather](https://t.me/BotFather)

---

*SkillForge - Making AI Useful for Everyone*
