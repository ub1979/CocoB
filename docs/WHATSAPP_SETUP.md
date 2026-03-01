# WhatsApp Integration Setup Guide

> **Important:** Use a **test/spare phone number** for WhatsApp integration, not your main number!

## Why?
- WhatsApp Web protocol is **unofficial** (reverse-engineered via Baileys)
- Risk of account bans if WhatsApp detects automation
- Against WhatsApp Terms of Service (use at your own risk)

## Quick Start (UI-Based)

The easiest way to set up WhatsApp is through the coco B desktop UI:

### Step 1: Start coco B
```bash
python coco_b.py
```

### Step 2: Open Settings > WhatsApp

1. Go to **Settings** tab
2. Scroll to **WhatsApp** section

### Step 3: Start the Baileys Service

1. Click **"Start Service"** button
2. Wait for the Node.js service to start (first time may take a moment to install dependencies)

### Step 4: Scan QR Code

1. Click **"Show QR"** button
2. A QR code will appear in the settings panel
3. Open WhatsApp on your phone
4. Go to: **Settings** > **Linked Devices** > **Link a Device**
5. Scan the QR code
6. Wait for "Connected" status

### Step 5: Start the Bot

1. Click **"Start Bot"** button
2. The bot is now listening for messages!

## Access Control Settings

Configure who can interact with your bot:

### DM Policy (Direct Messages)
| Option | Description |
|--------|-------------|
| **Self Only** | Only respond to messages you send to yourself |
| **Allowlist** | Only respond to numbers in allowlist |
| **Open** | Respond to everyone (use with caution) |
| **Disabled** | Don't respond to DMs |

### Group Policy
| Option | Description |
|--------|-------------|
| **Mention Only** | Only respond when @mentioned |
| **Allowlist** | Only respond to allowed members in groups |
| **Open** | Respond to all group messages |
| **Disabled** | Don't respond in groups |

### Allowlist
Comma-separated phone numbers (with country code, no `+`):
```
447771743077, 923335188980, 447386424730
```

## How It Works

```
┌─────────────────┐     HTTP      ┌──────────────────┐
│  WhatsApp App   │◄────────────►│  Baileys Service │
│  (Your Phone)   │               │  (Node.js:3979)  │
└─────────────────┘               └────────┬─────────┘
                                           │ Webhook
                                           ▼
                                  ┌──────────────────┐
                                  │   coco B Bot     │
                                  │  (Python:3978)   │
                                  └──────────────────┘
```

1. **Baileys Service** (Node.js) - Handles WhatsApp Web connection
2. **Webhook Server** (Python) - Receives messages and sends responses
3. **coco B Router** - Processes messages with skills and LLM

## Bot Response Prefix

When the bot responds to other users (not yourself), messages are prefixed with:
```
🤖 *coco B:*
Your response here
```

This helps others know they're talking to a bot, not you directly.

## Manual Setup (Advanced)

### Prerequisites
- Node.js 18+ installed
- npm installed

### Install Baileys Service

```bash
cd whatsapp_service
npm install
```

### Start Service Manually

```bash
cd whatsapp_service
npm start
```

The service runs on `http://localhost:3979` by default.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Connection status |
| `/qr` | GET | Get QR code text |
| `/qr/image` | GET | Get QR code as PNG |
| `/send` | POST | Send a message |
| `/webhook` | POST | Configure webhook URL |
| `/disconnect` | POST | Disconnect |
| `/reconnect` | POST | Reconnect |

## Configuration

### Service URL
Default: `http://localhost:3979`

Change in UI or set environment variable:
```bash
export WHATSAPP_SERVICE_PORT=3979
```

### Auth Directory
Session credentials stored in:
```
whatsapp_service/auth_info/
```

To logout completely, delete this directory.

## Troubleshooting

### "QR code expired"
- QR codes expire after ~30 seconds
- Click "Show QR" again to get a fresh code

### "Connection lost"
- Check if phone is still online
- Click "Reconnect" or restart the service

### "Message not delivered"
- Verify recipient number format includes country code
- Check if WhatsApp service is connected

### "Bot not responding in groups"
- Ensure Group Policy is set to "Allowlist" or "Open"
- Add group members' phone numbers to Allowlist
- Note: WhatsApp may use LIDs (Linked IDs) instead of phone numbers in groups

### "Account banned"
- This is the risk with unofficial clients
- Use a test number to avoid losing personal account
- Reduce message frequency
- Don't send identical messages repeatedly

## Files Created

```
whatsapp_service/
├── server.js              # Baileys service
├── package.json           # Node.js dependencies
├── auth_info/             # WhatsApp session credentials
│   └── creds.json         # Encrypted credentials
```

## Safety Tips

### DO
- Use a dedicated test phone number
- Start with allowlist enabled
- Monitor for unusual behavior
- Keep session files secure

### DON'T
- Don't use your personal WhatsApp initially
- Don't spam or send bulk messages
- Don't share auth_info folder
- Don't run 24/7 without testing first

## Alternative: Official WhatsApp Business API

For production use, consider the official API:
- Sign up for WhatsApp Business Platform
- Requires business verification
- Much more reliable and legal
- Costs money after free tier

---

**Project**: coco B - Persistent Memory AI Chatbot
**Organization**: Idrak AI Ltd
**License**: Open Source - Safe Open Community Project
