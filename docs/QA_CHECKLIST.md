# QA Testing Checklist for mr_bot

Use this checklist to manually test all features of mr_bot before releases.

## 🚀 Quick Start

```bash
# Run automated QA tests
python qa_test_framework.py

# Run quick tests only
python qa_test_framework.py --quick

# Run with verbose output
python qa_test_framework.py --verbose
```

---

## ✅ Core Features Checklist

### 1. Session Management

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Create Session | Send first message | Session created in `data/sessions/` | ☐ |
| Persistence | Restart bot, send message to same user | Previous context remembered | ☐ |
| Multi-User | Send messages as User A, then User B | Separate conversations maintained | ☐ |
| Session Reset | Use `/reset` command | Fresh conversation started | ☐ |
| Session Stats | Use `/stats` command | Shows message count, session ID | ☐ |

### 2. LLM Providers

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Ollama | Select "ollama" in Settings | Connects to localhost:11434 | ☐ |
| MLX | Select "mlx" in Settings | Connects to localhost:8080 | ☐ |
| OpenAI | Set OPENAI_API_KEY, select "openai" | Uses OpenAI API | ☐ |
| Provider Switch | Change provider in Settings | New provider works immediately | ☐ |
| Model Refresh | Click "Refresh" in Settings | Lists available models | ☐ |

### 3. Message Handling

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Basic Message | Type "Hello" and send | Bot responds | ☐ |
| Streaming | Send long message | Response streams word by word | ☐ |
| Context Memory | Ask "What did I just say?" | Bot remembers previous message | ☐ |
| Special Characters | Send "Hello @#$%^&*()" | Handles special chars correctly | ☐ |
| Long Message | Send 5000 character message | Either works or graceful error | ☐ |
| Empty Message | Send empty message | Ignored or helpful error | ☐ |

### 4. Commands

| Command | Test | Expected Result | Status |
|---------|------|-----------------|--------|
| `/help` | Send `/help` | Shows available commands | ☐ |
| `/reset` | Send `/reset` | Confirms conversation reset | ☐ |
| `/stats` | Send `/stats` | Shows session statistics | ☐ |
| `/skills` | Send `/skills` | Lists available skills | ☐ |
| `/commit` | Send `/commit test message` | Generates commit message | ☐ |
| `/explain` | Send `/explain Python loops` | Explains the topic | ☐ |

### 5. Security Features

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Input Validation | Try `<script>alert('xss')</script>` | Sanitized or rejected | ☐ |
| Path Traversal | Try `../../../etc/passwd` as user ID | Rejected or sanitized | ☐ |
| Oversized Input | Send 200KB message | Rejected with error | ☐ |
| Invalid Role | Try to inject invalid role | Rejected by validation | ☐ |
| Rate Limiting | Send 50 messages quickly | Rate limit enforced | ☐ |

### 6. Gradio UI

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| UI Loads | Run `python gradio_ui.py` | Opens at localhost:7777 | ☐ |
| Multi-User | Change User ID, send message | Different conversation | ☐ |
| View History | Click "View History" | Shows JSONL content | ☐ |
| Settings Tab | Click Settings tab | Shows provider options | ☐ |
| Server Status | Check server status in Settings | Shows green/red indicators | ☐ |
| Provider Switch | Change provider in Settings | New provider active | ☐ |
| Skills Tab | Click Skills tab | Shows skill editor | ☐ |

### 7. MS Teams Integration (if configured)

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Webhook | Send message via Teams | Bot responds | ☐ |
| Session Sync | Same user on Teams and Gradio | Shared conversation | ☐ |
| @Mention | @mention the bot | Bot responds to mention | ☐ |

### 8. Error Handling

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| No Server | Stop Ollama, try to chat | Helpful error message | ☐ |
| Invalid Provider | Configure wrong port | Connection error shown | ☐ |
| Timeout | Use very slow provider | Timeout error handled | ☐ |
| Invalid API Key | Use wrong API key | Authentication error | ☐ |

---

## 🔧 Provider-Specific Tests

### Ollama
```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull qwen3:8b

# Test in Gradio
# 1. Select "ollama" in Settings
# 2. Model should show "qwen3:8b"
# 3. Send message - should work
```

### MLX (Apple Silicon)
```bash
# Install mlx-lm
pip install mlx-lm

# Start MLX server
python -m mlx_lm.server --model mlx-community/Llama-3.2-1B-Instruct-4bit --port 8080

# Test in Gradio
# 1. Select "mlx" in Settings
# 2. Send message - should work
```

### OpenAI
```bash
# Set API key
export OPENAI_API_KEY="sk-..."

# Test in Gradio
# 1. Select "openai" in Settings
# 2. Send message - should work
```

---

## 📊 Performance Tests

| Test | Steps | Expected Result | Status |
|------|-------|-----------------|--------|
| Response Time | Send message, measure time | < 5 seconds for local | ☐ |
| Concurrent Users | Open 5 browser tabs | All work independently | ☐ |
| Large Context | Send 20 messages, then ask | Context handled correctly | ☐ |
| Memory Usage | Monitor during long session | No memory leaks | ☐ |

---

## 📝 Release Sign-off

Before releasing, verify:

- [ ] All automated tests pass (`python qa_test_framework.py`)
- [ ] All manual checklist items pass
- [ ] No console errors during testing
- [ ] Documentation is up to date
- [ ] Security review completed
- [ ] Performance is acceptable

---

## 🐛 Bug Report Template

Found a bug? Report it:

```markdown
**Test:** (Which test failed)
**Steps to Reproduce:**
1. Step one
2. Step two

**Expected:** What should happen
**Actual:** What actually happened

**Environment:**
- OS: 
- Python: 
- Provider: 

**Logs:**
```
Paste error logs here
```
```

---

**Last Updated:** 2026-02-07  
**Version:** 1.0.0  
**Maintainer:** Idrak AI Ltd Team
