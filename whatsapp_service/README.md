# WhatsApp Service (Baileys)

A secure Node.js microservice that handles WhatsApp Web connectivity for SkillForge.

## Why This Approach?

- **Security**: Uses the well-maintained [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys) library
- **Isolation**: Runs as a separate service, isolating WhatsApp logic from the Python bot
- **Reliability**: Handles reconnection, session persistence, and error recovery
- **No Backdoors**: Open-source, actively maintained, community audited

## Quick Start

### Prerequisites

- Node.js 18+ ([download](https://nodejs.org/))
- WhatsApp on your phone

### Installation

```bash
cd whatsapp_service
npm install
```

### Running

```bash
npm start
```

The service will:
1. Start on port 3979
2. Display a QR code in the terminal
3. Scan the QR code with WhatsApp (Settings → Linked Devices → Link a Device)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Connection status |
| `/qr` | GET | Get QR code as text |
| `/qr/image` | GET | Get QR code as PNG image |
| `/send` | POST | Send a message |
| `/webhook` | POST | Configure webhook for incoming messages |
| `/webhook` | GET | Get current webhook URL |
| `/disconnect` | POST | Disconnect from WhatsApp |
| `/reconnect` | POST | Reconnect to WhatsApp |
| `/health` | GET | Health check |

### Examples

**Check status:**
```bash
curl http://localhost:3979/status
```

**Send a message:**
```bash
curl -X POST http://localhost:3979/send \
  -H "Content-Type: application/json" \
  -d '{"to": "1234567890", "message": "Hello from SkillForge!"}'
```

**Set webhook for incoming messages:**
```bash
curl -X POST http://localhost:3979/webhook \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:3978/whatsapp/incoming"}'
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHATSAPP_SERVICE_PORT` | 3979 | API port |
| `AUTH_DIR` | `./auth_info` | Session storage directory |
| `WEBHOOK_URL` | none | Default webhook URL |
| `LOG_LEVEL` | info | Logging level (debug, info, warn, error) |

## Session Persistence

Sessions are stored in `auth_info/` directory. To force re-authentication:

```bash
rm -rf auth_info/
npm start
```

## Integration with SkillForge

The Python bot communicates with this service via HTTP:

```
┌─────────────┐     HTTP API      ┌──────────────────┐     WebSocket     ┌──────────────┐
│   SkillForge    │ ←───────────────→ │ WhatsApp Service │ ←───────────────→ │ WhatsApp Web │
│  (Python)   │    localhost:3979 │    (Node.js)     │                   │   Servers    │
└─────────────┘                   └──────────────────┘                   └──────────────┘
```

## Troubleshooting

**QR code not appearing?**
- Make sure no other WhatsApp Web session is active
- Delete `auth_info/` and restart

**Connection keeps dropping?**
- Check your internet connection
- WhatsApp may have rate-limited the connection
- Wait a few minutes and reconnect

**Messages not forwarding?**
- Ensure webhook URL is configured
- Check that your Python bot's webhook endpoint is running
