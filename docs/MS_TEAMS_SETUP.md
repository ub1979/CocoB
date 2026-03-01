# 📱 MS Teams Integration Guide

## How to Connect Your Bot to MS Teams

### Prerequisites
- ✅ Azure account (free tier works!)
- ✅ MS Teams account
- ✅ Your bot running (bot.py)

---

## 🚀 Setup Steps

### Step 1: Create Azure Bot Resource

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"**
3. Search for **"Azure Bot"**
4. Click **"Create"**

**Fill in details:**
```
Bot handle: mybot (unique name)
Subscription: Your subscription
Resource group: Create new "mybot-rg"
Pricing tier: F0 (Free)
```

### Step 2: Get Credentials

After creation:
1. Go to your bot resource
2. Click **"Configuration"** in left menu
3. You'll see:
   - **Microsoft App ID**: Copy this!
   - Click **"Manage"** next to it
   - Create **"New client secret"**: Copy this too!

**Add to your config.py:**
```python
MSTEAMS_APP_ID = "abc123-your-app-id-here"
MSTEAMS_APP_PASSWORD = "xyz789-your-secret-here"
```

### Step 3: Configure Messaging Endpoint

Your bot needs to be reachable from internet.

**Option A: Ngrok (for testing)**
```bash
# Install ngrok: https://ngrok.com/download
ngrok http 3978
```

You'll get a URL like: `https://abc123.ngrok.io`

**In Azure Bot Configuration:**
```
Messaging endpoint: https://abc123.ngrok.io/api/messages
```

**Option B: Deploy to Cloud (production)**
- Azure App Service
- Heroku
- AWS EC2
- Your own server

### Step 4: Connect MS Teams Channel

In Azure Portal:
1. Go to your bot
2. Click **"Channels"**
3. Click **"Microsoft Teams"** icon
4. Click **"Apply"**
5. ✅ Done!

### Step 5: Test in Teams

1. In Azure, click **"Test in Web Chat"** (test first!)
2. Or click **"Open in Teams"** button
3. Your bot appears in MS Teams!
4. Start chatting! 🎉

---

## 📞 How Users Will Find Your Bot

### Method 1: Direct Link
Share this link with your team:
```
https://teams.microsoft.com/l/chat/0/0?users=YOUR_BOT_APP_ID
```

### Method 2: Search in Teams
Users can search for your bot:
1. Click **"Chat"** in Teams
2. Click **"New chat"**
3. Search for **"My Bot"**
4. Start chatting!

### Method 3: Add to Team Channel
1. Go to a Team
2. Click **"+"** to add tab/bot
3. Search for your bot
4. Add it to channel
5. Everyone in team can use it!

---

## 🧪 Testing Checklist

Before going live:

- [ ] Bot responds in Azure "Test in Web Chat"
- [ ] Bot responds in Teams 1-on-1 chat
- [ ] Bot remembers context (test: ask name, then ask "what's my name?")
- [ ] Commands work (`/help`, `/stats`, `/reset`)
- [ ] Session persists (restart bot, chat should continue)
- [ ] JSONL files are being created

---

## 🔧 Troubleshooting

### Bot doesn't respond
1. Check ngrok is running
2. Check bot.py is running
3. Check endpoint URL in Azure
4. Check logs: `python bot.py` shows incoming requests

### "Authentication failed" error
1. Verify App ID in config.py
2. Verify App Password in config.py
3. Regenerate secret if needed

### Messages not received
1. Check Messaging endpoint in Azure
2. Make sure it's HTTPS (ngrok provides this)
3. Check firewall/network settings

---

## 💡 What Happens When You Chat

```
You in Teams: "Hello bot!"
       ↓
Teams sends to: https://your-bot.com/api/messages
       ↓
Your bot.py receives:
{
  "type": "message",
  "text": "Hello bot!",
  "from": { "id": "user-123", "name": "John" },
  "conversation": { "id": "conv-456" }
}
       ↓
SessionManager: msteams:direct:user-123
       ↓
Load history from: sess-2026-02-05-xyz.jsonl
       ↓
AI generates response with context
       ↓
Bot sends reply to Teams API
       ↓
You see: "Hi John! How can I help?"
```

---

## 🌟 Advanced: Bot Features

Once connected, you can add:

### Adaptive Cards (Rich UI)
```python
# Send interactive cards in Teams
card = {
    "type": "AdaptiveCard",
    "body": [
        {"type": "TextBlock", "text": "Choose an option:"},
        {"type": "ActionSet", "actions": [
            {"type": "Action.Submit", "title": "Option 1"},
            {"type": "Action.Submit", "title": "Option 2"}
        ]}
    ]
}
```

### File Sharing
```python
# Bot can send/receive files
attachment = {
    "contentType": "application/pdf",
    "contentUrl": "https://example.com/doc.pdf",
    "name": "report.pdf"
}
```

### Proactive Messages
```python
# Bot can start conversations (notifications)
await send_proactive_message(
    user_id="user-123",
    message="Reminder: Meeting in 10 minutes!"
)
```

---

## 📊 Monitoring

Check these files to see bot activity:
```
data/sessions/sessions.json     # All active sessions
data/sessions/sess-*.jsonl      # Full conversations
```

View in Gradio UI:
```bash
python gradio_ui.py
# Check "View History" to see Teams conversations!
```

---

## 🎉 You're Ready!

Once connected:
- ✅ Chat in Teams Desktop
- ✅ Chat in Teams Mobile  
- ✅ Chat in Teams Web
- ✅ Add to team channels
- ✅ Same bot, same memory, everywhere!

**Next**: Add WhatsApp, Slack, etc. using the same SessionManager! 🚀
