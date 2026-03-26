# WhatsApp Integration - Technical Guide

## Overview

SkillForge uses a **secure microservice architecture** for WhatsApp integration:

```
┌──────────────┐     HTTP API      ┌──────────────────┐     WebSocket     ┌──────────────┐
│  SkillForge  │ ←───────────────→ │ WhatsApp Service │ ←───────────────→ │ WhatsApp Web │
│   (Python)   │    localhost:3979 │  (Node.js/Baileys)│                   │   Servers    │
└──────────────┘                   └──────────────────┘                   └──────────────┘
```

### Why This Approach?

| Concern | Solution |
|---------|----------|
| **Security** | Uses [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys) - actively maintained, community-audited |
| **No Backdoors** | Open-source libraries, no outdated/abandoned packages |
| **Reliability** | Separate service with auto-reconnection and session persistence |
| **Isolation** | WhatsApp logic isolated from main Python bot |

### Avoided Libraries (Unsafe/Outdated)

These Python libraries are **NOT used** because they are outdated or potentially unsafe:

- ❌ `whatsapp-web.py` - Last updated 2021, abandoned
- ❌ `yowsup` - Deprecated
- ❌ `pywa` - May not work with latest WhatsApp
- ❌ `webwhatsapi` - Outdated Selenium wrapper

---

## Quick Start

### Prerequisites

- Node.js 18+ ([download](https://nodejs.org/))
- WhatsApp on your phone

### Step 1: Start WhatsApp Service

```bash
cd whatsapp_service
npm install
npm start
```

### Step 2: Scan QR Code

A QR code will appear in the terminal. Scan it with WhatsApp:
1. Open WhatsApp on your phone
2. Go to **Settings** → **Linked Devices**
3. Tap **Link a Device**
4. Scan the QR code

### Step 3: Test Connection

```bash
# Check status
curl http://localhost:3979/status

# Send a test message
curl -X POST http://localhost:3979/send \
  -H "Content-Type: application/json" \
  -d '{"to": "1234567890", "message": "Hello from SkillForge!"}'
```

---

## Architecture

### Components

| Component | Language | Port | Description |
|-----------|----------|------|-------------|
| **SkillForge** | Python | 3978 | Main bot with AI, sessions, personality |
| **WhatsApp Service** | Node.js | 3979 | Baileys-based WhatsApp Web gateway |

### Data Flow

1. **Incoming Message:**
   ```
   WhatsApp → Baileys Service → HTTP POST → SkillForge webhook → AI response → Send via HTTP
   ```

2. **Outgoing Message:**
   ```
   SkillForge → HTTP POST /send → Baileys Service → WhatsApp
   ```

### File Structure

```
skillforge/
├── channels/
│   └── whatsapp.py          # Python HTTP client
│
└── whatsapp_service/         # Node.js Baileys service
    ├── package.json
    ├── server.js             # Express API + Baileys
    ├── auth_info/            # Session data (gitignored)
    └── README.md
```

---

## API Reference

### WhatsApp Service Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Connection status |
| `/qr` | GET | Get QR code as text |
| `/qr/image` | GET | Get QR code as PNG |
| `/send` | POST | Send a message |
| `/webhook` | POST | Configure webhook URL |
| `/webhook` | GET | Get current webhook URL |
| `/disconnect` | POST | Disconnect from WhatsApp |
| `/reconnect` | POST | Reconnect to WhatsApp |
| `/health` | GET | Health check |

### Send Message

```bash
POST /send
Content-Type: application/json

{
  "to": "1234567890",      # Phone number
  "message": "Hello!"       # Message text
}

# Or use chat ID directly:
{
  "chatId": "1234567890@s.whatsapp.net",
  "message": "Hello!"
}
```

### Configure Webhook

```bash
POST /webhook
Content-Type: application/json

{
  "url": "http://localhost:3978/whatsapp/incoming"
}
```

### Webhook Payload (Incoming Messages)

When a message is received, the service POSTs to your webhook:

```json
{
  "messageId": "ABC123...",
  "chatId": "1234567890@s.whatsapp.net",
  "senderId": "1234567890",
  "senderName": "John Doe",
  "isGroup": false,
  "content": "Hello!",
  "timestamp": 1699999999
}
```

---

## Python Client Usage

### Basic Usage

```python
from channels.whatsapp import WhatsAppChannel, WhatsAppConfig

# Initialize
config = WhatsAppConfig(service_url="http://localhost:3979")
wa = WhatsAppChannel(config=config)

# Check status
status = await wa.check_status()
print(f"Connected: {status['connected']}")

# Send message
await wa.send_message("1234567890", "Hello from SkillForge!")

# Close
await wa.close()
```

### With Message Handler

```python
async def handle_message(channel, user_id, user_message, chat_id=None, user_name=None):
    print(f"Message from {user_name}: {user_message}")
    return f"You said: {user_message}"  # Auto-reply

wa = WhatsAppChannel(message_handler=handle_message)
await wa.configure_webhook()
```

### Integration with SkillForge Router

```python
from core.router import MessageRouter
from channels.whatsapp import WhatsAppChannel

router = MessageRouter(session_manager, llm_provider)
wa = WhatsAppChannel(message_handler=router.handle_message)

# Configure webhook to receive messages
await wa.configure_webhook("http://localhost:3978/whatsapp/incoming")
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHATSAPP_SERVICE_PORT` | 3979 | Baileys service port |
| `AUTH_DIR` | `./auth_info` | Session storage directory |
| `WEBHOOK_URL` | none | Default webhook URL |
| `LOG_LEVEL` | info | Logging level |

### Python Config

```python
from channels.whatsapp import WhatsAppConfig

config = WhatsAppConfig(
    service_url="http://localhost:3979",
    webhook_path="/whatsapp/incoming",
    bot_port=3978,
)
```

---

## Session Management

### Session Persistence

Sessions are stored in `whatsapp_service/auth_info/`. This allows reconnection without re-scanning QR.

### Force Re-authentication

```bash
# Delete session and restart
rm -rf whatsapp_service/auth_info/
cd whatsapp_service && npm start
```

### Logout via API

```bash
curl -X POST http://localhost:3979/disconnect \
  -H "Content-Type: application/json" \
  -d '{"logout": true}'
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check Node.js version (need 18+)
node --version

# Reinstall dependencies
cd whatsapp_service
rm -rf node_modules package-lock.json
npm install
```

### QR Code Not Appearing

- Make sure no other WhatsApp Web session is active
- Delete `auth_info/` and restart the service
- Check the terminal where `npm start` is running

### Connection Drops

- Check internet connection
- WhatsApp may rate-limit connections after many reconnects
- Wait a few minutes before reconnecting

### Messages Not Forwarding

1. Check webhook is configured: `curl http://localhost:3979/webhook`
2. Ensure your Python webhook endpoint is running
3. Check logs in the Baileys service terminal

### "Already connected" but Can't Send

```bash
# Force reconnect
curl -X POST http://localhost:3979/disconnect
curl -X POST http://localhost:3979/reconnect
```

---

## Security Best Practices

1. **Never commit `auth_info/`** - Contains WhatsApp session credentials
2. **Run service locally** - Don't expose port 3979 to the internet
3. **Use HTTPS** in production if exposing webhook endpoints
4. **Monitor for suspicious activity** - Unusual message patterns may indicate compromise

---

## Development

### Running in Development Mode

```bash
cd whatsapp_service
npm run dev  # Auto-restarts on file changes
```

### Testing the Service

```bash
# Health check
curl http://localhost:3979/health

# Full status
curl http://localhost:3979/status

# Test send (replace with real number)
curl -X POST http://localhost:3979/send \
  -H "Content-Type: application/json" \
  -d '{"to": "1234567890", "message": "Test"}'
```
