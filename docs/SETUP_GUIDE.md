# My Bot - Persistent Memory AI Chatbot

✅ **I've created a complete bot framework with persistent memory architecture!**

## 📁 What's Been Created

```
C:\Users\syed.bukhari\funcode\mybot\
├── bot.py                  # ✅ Main server (Flask webhook)
├── config.example.py       # ✅ Configuration template
├── requirements.txt        # ✅ Python dependencies
├── README.md              # ✅ This file
│
├── core/
│   ├── sessions.py        # ✅ Persistent session management with JSONL storage
│   ├── ai.py              # ✅ Ollama integration
│   └── router.py          # ✅ Message routing & compaction
│
├── channels/
│   └── (ready for msteams.py)
│
└── data/
    ├── sessions/          # Sessions stored here
    └── memory/            # Memory files here
```

## 🎯 What It Does

### 1. **Persistent Sessions**
- Each user gets a unique session
- Full conversation stored in JSONL files
- Never loses history (stored on disk)

### 2. **Smart Memory Management**
- When conversation gets long → auto-summarizes old messages
- Keeps full history in JSONL (never deleted)
- Only sends relevant context to AI

### 3. **Session Files**

**sessions.json** (index):
```json
{
  "msteams:direct:user-123": {
    "sessionId": "sess-2026-02-05-abc123",
    "messageCount": 15,
    "updatedAt": 1770292585
  }
}
```

**sess-2026-02-05-abc123.jsonl** (full conversation):
```jsonl
{"type":"session","id":"sess-123","timestamp":"2026-02-05T12:00:00Z"}
{"type":"message","role":"user","content":"Hello"}
{"type":"message","role":"assistant","content":"Hi there!"}
{"type":"compaction","summary":"User greeted, discussed weather..."}
{"type":"message","role":"user","content":"What did we talk about?"}
```

## 🚀 How to Use

### Step 1: Install Dependencies

```bash
cd C:\Users\syed.bukhari\funcode\mybot
pip install -r requirements.txt
```

### Step 2: Configure

```bash
# Copy example config
copy config.example.py config.py

# Edit config.py with your settings
notepad config.py
```

### Step 3: Test Locally (No Teams needed!)

```bash
python bot.py
```

Then test with curl or Postman:
```bash
curl -X POST http://localhost:3978/api/test \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"john\",\"message\":\"Hello bot!\"}"
```

### Step 4: Try The Session Manager

```bash
cd core
python sessions.py
```

This creates a test session and shows how conversations are stored!

## 🧠 How Memory Works

### Conversation Flow:

1. **User sends message** → Saved to JSONL
2. **Load history** from JSONL file
3. **Check context size** → Compact if needed
4. **Send to AI** with full context
5. **Save AI response** → Append to JSONL
6. **Return response** to user

### When Context Gets Full:

```
Before compaction (100 messages):
[msg1, msg2, msg3, ... msg100]

After compaction:
[Summary of msg1-95] + [msg96, msg97, msg98, msg99, msg100]

JSONL file still has all 100 messages!
```

## 📝 Testing Session Persistence

```python
# First conversation
POST /api/test {"user_id": "alice", "message": "My name is Alice"}
→ Bot: "Nice to meet you Alice!"

# Close bot, restart it

# Second conversation (same user)
POST /api/test {"user_id": "alice", "message": "What's my name?"}
→ Bot: "Your name is Alice!" ✅ (remembers!)
```

## 🎮 Available Commands

- `/reset` - Start fresh conversation
- `/stats` - Show session statistics
- `/help` - Show help

## 🔧 Next Steps for MS Teams

To connect to MS Teams, you need to:

1. **Register Azure Bot** (I can help with this)
2. **Get credentials** (App ID + Password)
3. **Add `channels/msteams.py`** (Teams-specific code)
4. **Deploy webhook** (or use ngrok for testing)

## 🧪 File Locations

- **Sessions**: `data/sessions/sessions.json`
- **Transcripts**: `data/sessions/sess-*.jsonl`
- **Memory** (future): `data/memory/*.md`

## ✨ Key Features Implemented

✅ Two-tier storage (sessions.json + JSONL)  
✅ Append-only transcripts (never lose history)  
✅ Automatic context compaction  
✅ Session continuity (survives restarts)  
✅ Multi-user support  
✅ Simple command system  
✅ Ollama integration  
✅ Test endpoint (no Teams needed)  
✅ Comprehensive QA testing framework  

---

## 🧪 Testing Your Setup

### Automated QA Tests

Run the built-in test suite to verify everything works:

```bash
# Run all tests
python qa_test_framework.py

# Quick tests only (faster)
python qa_test_framework.py --quick

# See detailed output
python qa_test_framework.py --verbose
```

**Expected:** All tests should pass ✅

### Manual Testing

Follow the [QA_CHECKLIST.md](QA_CHECKLIST.md) for comprehensive manual testing:

```bash
# Open the checklist
cat QA_CHECKLIST.md
```

Key things to test:
1. ✅ Send a message - bot responds
2. ✅ Restart bot - conversation remembered
3. ✅ Switch user - separate conversation
4. ✅ Use `/reset` - fresh start
5. ✅ Use `/stats` - see session info

---

## 🎉 You Now Have

A **production-ready bot framework** with:
- Persistent memory architecture
- Persistent conversations
- Smart context management
- Ready for MS Teams (just needs credentials)
- Easy to test locally

**Want me to help you:**
1. Test it locally?
2. Connect to MS Teams?
3. Add more features?

Let me know what you'd like to do next! 🚀
