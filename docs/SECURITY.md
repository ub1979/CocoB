# Security Documentation

## Overview

**SkillForge** is designed with security as a core principle. This document outlines the security features, best practices, and considerations for deploying and using the bot safely.

> 🛡️ **Security by Design**: Every component of SkillForge has been reviewed for security vulnerabilities and hardened against common attack vectors.

---

## 🔒 Security Features

### 1. Command Injection Protection

**The Problem**: Traditional port management uses shell commands like `lsof` and `kill` which are vulnerable to command injection.

**Our Solution**: We use `psutil` library for all process management, completely eliminating shell commands.

```python
# ❌ VULNERABLE (shell injection possible)
subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True)

# ✅ SECURE (no shell involved)
psutil.Process(pid).terminate()
```

**Affected Files**:
- `gradio_ui.py` - Port management for Gradio UI
- `core/llm/auth/base.py` - OAuth callback server port management

### 2. Webhook Signature Verification

**The Problem**: Webhooks from external platforms (WhatsApp, Telegram, Slack, MS Teams) can be spoofed. An attacker who discovers your webhook URL can send fake messages pretending to be from these platforms.

**Our Solution**: All incoming webhooks are verified using platform-specific signature verification:

| Platform | Verification Method | Header | Environment Variable |
|----------|-------------------|--------|---------------------|
| **WhatsApp** | HMAC-SHA256 | `X-Hub-Signature-256` | `WHATSAPP_APP_SECRET` |
| **Telegram** | Secret token | `X-Telegram-Bot-Api-Secret-Token` | `TELEGRAM_WEBHOOK_SECRET` |
| **Slack** | HMAC-SHA256 + timestamp | `X-Slack-Signature`, `X-Slack-Request-Timestamp` | `SLACK_SIGNING_SECRET` |
| **MS Teams** | JWT Bearer token | `Authorization` | `MSTEAMS_APP_ID`, `MSTEAMS_APP_PASSWORD` |

**Security Features**:
- ✅ Constant-time comparison prevents timing attacks
- ✅ Timestamp validation prevents replay attacks (Slack)
- ✅ Clear error messages for debugging
- ✅ Graceful degradation with warnings if not configured

**Configuration**:

```bash
# WhatsApp (from Meta Developer Dashboard)
export WHATSAPP_APP_SECRET="your_app_secret_here"

# Telegram (set when configuring webhook)
export TELEGRAM_WEBHOOK_SECRET="your_webhook_secret_here"

# Slack (from Slack App Dashboard)
export SLACK_SIGNING_SECRET="your_signing_secret_here"
```

**What Happens When Verification Fails**:
```json
{
  "error": "Unauthorized",
  "message": "Invalid WhatsApp signature. This request may be spoofed."
}
```

**Implementation**: `core/webhook_security.py` - Signature verification functions

**Test Coverage**: `tests/test_webhook_security.py` - 35 comprehensive tests

### 3. MCP Server Command Allowlist

**The Problem**: MCP (Model Context Protocol) servers are configured via JSON and executed as subprocesses. A malicious or compromised MCP configuration could execute arbitrary commands on your system.

**Our Solution**: All MCP commands are validated against a security allowlist before execution. Only approved commands and packages can run.

| Check | Description | Example Allowed | Example Blocked |
|-------|-------------|-----------------|-----------------|
| Base Command | Must be in allowlist | `npx`, `docker`, `python3` | `bash`, `sh`, `curl`, `rm` |
| Package Prefix | npm/pip packages must have approved prefix | `@playwright/mcp` | `evil-package` |
| Docker Flags | Dangerous flags are blocked | `docker run -i` | `docker --privileged` |

**Allowed Commands**:
```python
ALLOWED_MCP_COMMANDS = {
    'npx',      # Node package executor
    'docker',   # Container runtime
    'python3',  # Python interpreter
    'python',   # Python interpreter
    'node',     # Node.js runtime
    'uv',       # Modern Python package manager
    'pipx',     # Python application runner
}
```

**Allowed Package Prefixes**:
```python
ALLOWED_MCP_PACKAGE_PREFIXES = (
    '@playwright/',           # Playwright browser automation
    '@modelcontextprotocol/', # Official MCP servers
    '@composio/',             # Composio integrations
    'mcp-',                   # MCP utility packages
)
```

**What Happens When Blocked**:
```
❌ MCP Security Error: MCP command 'bash' is not in the security allowlist.
Allowed commands: docker, node, npx, pipx, python, python3, uv.
If you need to use 'bash', add it to ALLOWED_MCP_COMMANDS in mcp_client.py
after verifying it is safe.
```

**Adding Custom MCP Servers**:
If you need to use an MCP server not in the allowlist, edit `core/mcp_client.py`:

```python
# Add a new command (if safe)
ALLOWED_MCP_COMMANDS = frozenset({
    'npx', 'docker', 'python3', 'python', 'node', 'uv', 'pipx',
    'your-command',  # ← Add here
})

# Or add a new package prefix
ALLOWED_MCP_PACKAGE_PREFIXES = (
    '@playwright/',
    '@modelcontextprotocol/',
    '@composio/',
    'mcp-',
    '@yourcompany/',  # ← Add here
)
```

**Implementation**: `core/mcp_client.py` - `validate_mcp_command()` function

**Test Coverage**: `tests/test_mcp_security.py` - Comprehensive test suite for all security checks

### 4. SQLite WAL Mode

**The Problem**: SQLite's default journal mode can cause database locks when multiple operations happen simultaneously, leading to "database is locked" errors.

**Our Solution**: Enable Write-Ahead Logging (WAL) mode for better concurrency and performance.

```sql
PRAGMA journal_mode=WAL;        -- Enable WAL mode
PRAGMA synchronous=NORMAL;      -- Balance safety and speed
PRAGMA temp_store=MEMORY;       -- Store temp tables in memory
```

**Benefits**:
- ✅ Readers don't block writers
- ✅ Writers don't block readers
- ✅ Better performance under concurrent access
- ✅ Faster write operations

**Implementation**: `core/memory/sqlite_memory.py` - `_init_db()` method

**Test Coverage**: `tests/test_sqlite_wal_mode.py` - 5 comprehensive tests

### 5. Input Validation

All user inputs are validated before processing:

| Input Type | Validation | Max Length | Purpose |
|------------|------------|------------|---------|
| Session Key | Path traversal check | 512 chars | Prevent file system access |
| User ID | Alphanumeric + safe chars | 256 chars | Prevent injection |
| Role | Whitelist only | N/A | Only user/assistant/system |
| Content | Length limit | 100KB | Prevent DoS |
| Port Number | Range check | N/A | Valid ports only (1-65535) |

**Implementation**: `core/sessions.py` - `_validate_input()` method

### 6. Rate Limiting

API endpoints are protected against abuse:

| Endpoint | Rate Limit | Purpose |
|----------|------------|---------|
| `/api/messages` | 30 requests/minute | Main webhook protection |
| `/api/test` | 10 requests/minute | Test endpoint (stricter) |
| Default | 200/day, 50/hour | Global per-IP limit |

**Configuration**: Automatic when `flask-limiter` is installed

**Implementation**: `bot.py` - `@limiter.limit()` decorators

### 7. Security Headers

All HTTP responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

**Implementation**: `bot.py` - `add_security_headers()` middleware

### 8. Debug Mode Control

Debug mode is controlled by environment variable:

```bash
# Development
export FLASK_DEBUG=true

# Production
export FLASK_DEBUG=false
# or unset FLASK_DEBUG
```

**Warning**: Running with `debug=True` in production exposes sensitive information.

**Implementation**: `bot.py` - checks `FLASK_DEBUG` environment variable

### 10. Timing Attack Protection

**The Problem**: Simple string comparison (`==`) for password verification takes different amounts of time depending on how many characters match. Attackers can measure this timing to guess passwords character-by-character.

**Our Solution**: Use `hmac.compare_digest()` which performs constant-time comparison.

```python
# ❌ VULNERABLE (timing attack possible)
return computed_hash == stored_hash

# ✅ SECURE (constant-time comparison)
return hmac.compare_digest(computed_hash, stored_hash)
```

**How It Works**:
- Always compares all bytes, regardless of mismatch position
- Takes same time whether password is completely wrong or off by one character
- Prevents timing side-channel attacks

**Implementation**: `core/file_access.py` - `verify_password()` method

**Test Coverage**: `tests/test_file_access_timing.py` - 7 timing attack tests

### 11. Tiered Authentication System

**The Problem**: A single password for everything is either too secure (annoying) or too convenient (insecure). Users need different security levels for different actions.

**Our Solution**: Four-tier authentication system with appropriate friction for each security level.

| Level | Color | Actions | Auth Method | Session |
|-------|-------|---------|-------------|---------|
| **GREEN** | 🟢 | Read-only, heartbeats, notifications | None | N/A |
| **YELLOW** | 🟡 | Routine tasks (email, calendar) | 4-digit PIN | 30 minutes |
| **ORANGE** | 🟠 | Skill creation, automation setup | Password | 1 hour |
| **RED** | 🔴 | File system access, dangerous ops | Password + Confirm | Per-action |

**Benefits**:
- ✅ **Frictionless**: Heartbeats just work
- ✅ **Fast routine**: 4-digit PIN for common tasks
- ✅ **Secure sensitive**: Password for dangerous operations
- ✅ **Convenient**: Sessions remember you for 30-60 minutes
- ✅ **Clear hierarchy**: Users understand protection levels

**Example Flow**:
```
[9:00 AM - Heartbeat - GREEN]
SkillForge: "🌅 Morning! 3 emails, 1 meeting today"
         (No auth needed - just reading)

[9:05 AM - Check Email - YELLOW]
You: /email check
SkillForge: "📧 3 emails... 🔐 Enter PIN to read"
You: 1234
SkillForge: "✅ Email from boss... ⏱️ PIN valid 30 min"

[9:30 AM - Create Skill - ORANGE]
SkillForge: "💡 Suggest creating '/morning-brief' skill?"
You: yes
SkillForge: "🔐 Enter password (1-hour session):"
You: mypassword123
SkillForge: "✅ Skill created! 🔓 Session active 59 min"
         (Can create more skills without re-entering)
```

**Session Management**:
- Sessions auto-extend on activity
- Expire after inactivity (30 min for PIN, 60 min for password)
- Persist across restarts (optional)
- Clear with `/logout` command

**Implementation**: `core/auth_manager.py` - `AuthManager` class

**Test Coverage**: `tests/test_auth_manager.py` - 42 comprehensive tests

### 12. Agentic Features Security

#### 12.1 Heartbeat System (GREEN Level)

**The Problem**: Users forget to check important information like emails, calendar, and deadlines.

**Our Solution**: Proactive heartbeat system that sends periodic check-ins without requiring authentication.

| Heartbeat Type | Schedule | Security Level | Content |
|----------------|----------|----------------|---------|
| **Morning Brief** | Daily at 9:00 AM | 🟢 GREEN | Emails, calendar, reminders |
| **Deadline Watch** | Every 60 min | 🟢 GREEN | Upcoming deadlines, overdue items |
| **Unusual Activity** | Event-driven | 🟢 GREEN | Important emails, mentions |
| **Daily Summary** | Daily at 6:00 PM | 🟢 GREEN | Day recap, tomorrow preview |

**Security Features**:
- ✅ All heartbeats are read-only (GREEN level)
- ✅ No authentication required for receiving
- ✅ Per-user configuration stored securely
- ✅ Configurable schedule times
- ✅ Can be enabled/disabled per user

**Implementation**: `core/heartbeat_manager.py` - `HeartbeatManager` class

**Test Coverage**: `tests/test_heartbeat_manager.py` - 27 comprehensive tests

#### 12.2 Pattern Detection & Skill Suggestions (ORANGE Level)

**The Problem**: Users repeat the same commands/workflows manually when they could be automated as skills.

**Our Solution**: Pattern detection system that analyzes user behavior and suggests skill creation.

| Pattern Type | Detection Method | Security Level |
|--------------|------------------|----------------|
| **Repeated Command** | Same command 3+ times | 🟠 ORANGE to view/create |
| **Repeated Workflow** | Same sequence 3+ times | 🟠 ORANGE to view/create |
| **Time-Based Pattern** | Daily at same time | 🟠 ORANGE to view/create |
| **Context Pattern** | Same context triggers | 🟠 ORANGE to view/create |

**Security Features**:
- ✅ Viewing suggestions requires ORANGE (password) authentication
- ✅ Creating skills from suggestions requires ORANGE level
- ✅ Pattern data is isolated per user
- ✅ 30-day retention limit for interaction history
- ✅ Dismissed patterns are remembered (not shown again)

**Example Flow**:
```
[User checks email 5 times this week]
SkillForge: "💡 Pattern detected: You check email frequently."
        "   Suggest creating '/check-email' skill?"
        "   🔐 Enter password to view (ORANGE level)"

You: mypassword123
SkillForge: "✅ Pattern: 'check email' (5 times)"
        "   Would you like me to create this skill?"
        "   [Yes] [No, dismiss] [Remind later]"
```

**Implementation**: `core/pattern_detector.py` - `PatternDetector` class

**Test Coverage**: `tests/test_pattern_detector.py` - 25 comprehensive tests

#### 12.3 Background Task Runner (YELLOW Level)

**The Problem**: Some tasks need to run periodically (health checks, data sync) but should be protected from unauthorized modification.

**Our Solution**: Background task runner with tiered authentication for task management.

| Operation | Security Level | Description |
|-----------|----------------|-------------|
| **View task status** | 🟢 GREEN | Anyone can see what's running |
| **Create/modify tasks** | 🟡 YELLOW | PIN required for changes |
| **Delete/pause tasks** | 🟡 YELLOW | PIN required |
| **Manual trigger** | 🟡 YELLOW | PIN required to run now |

**Task Types**:
- **Health Monitor**: Periodic health checks
- **Data Sync**: Sync with external services
- **Periodic Check**: Custom periodic operations
- **Scheduled Job**: Time-based execution

**Security Features**:
- ✅ Task management requires YELLOW (PIN) authentication
- ✅ Viewing status is GREEN (no auth)
- ✅ Max 5 concurrent tasks (resource protection)
- ✅ Task results limited to last 50 (storage protection)
- ✅ Command validation before execution

**Implementation**: `core/background_tasks.py` - `BackgroundTaskRunner` class

**Test Coverage**: `tests/test_background_tasks.py` - 30 comprehensive tests

### 13. API Key Security

- **Never hardcode API keys** in configuration files
- Use environment variables exclusively
- Configuration validation warns about hardcoded keys

```python
# ✅ CORRECT
"api_key": os.environ.get("OPENAI_API_KEY")

# ❌ WRONG (security risk)
"api_key": "sk-abc123..."
```

**Validation**: `config.py` - `validate_config()` function

---

## 🚀 Deployment Security Checklist

Before deploying to production:

### Environment Variables
- [ ] Set `FLASK_DEBUG=false` (or unset)
- [ ] Configure all API keys via environment variables
- [ ] Set strong, unique credentials for MS Teams (if used)
- [ ] Configure rate limiting storage (Redis recommended for multi-instance)
- [ ] Set webhook secrets for all channels:
  - [ ] `WHATSAPP_APP_SECRET` (from Meta Developer Dashboard)
  - [ ] `TELEGRAM_WEBHOOK_SECRET` (set when configuring webhook)
  - [ ] `SLACK_SIGNING_SECRET` (from Slack App Dashboard)

### File Permissions
- [ ] `config.py` should be readable only by the application user (chmod 600)
- [ ] `data/sessions/` directory should be writable by application user only
- [ ] Log files should not be world-readable

### Network Security
- [ ] Use HTTPS for webhook endpoints (MS Teams, Telegram)
- [ ] Configure firewall to allow only necessary ports
- [ ] Use reverse proxy (nginx/Apache) for SSL termination
- [ ] Enable CORS only for trusted origins

### Monitoring
- [ ] Set up log aggregation and monitoring
- [ ] Configure alerts for unusual activity
- [ ] Regular security updates for dependencies

---

## 🛡️ Security Best Practices

### For Developers

1. **Never use `shell=True`** in subprocess calls
2. **Always validate user inputs** before processing
3. **Use parameterized queries** if implementing database features
4. **Keep dependencies updated** (`pip list --outdated`)
5. **Review code** for security issues before merging

### For Administrators

1. **Run with minimal privileges** - don't run as root
2. **Use environment variables** for all secrets
3. **Enable rate limiting** to prevent abuse
4. **Monitor logs** for suspicious activity
5. **Regular backups** of session data

### For Users

1. **Don't share API keys** or credentials
2. **Report security issues** to the maintainers
3. **Keep your instance updated** to latest version

---

## 🐛 Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email: security@idrak.ai (or project maintainer)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will:
- Acknowledge receipt within 48 hours
- Investigate and provide updates
- Release a fix as soon as possible
- Credit you in the changelog (with your permission)

---

## 📋 Security-Related Dependencies

| Package | Purpose | Security Benefit |
|---------|---------|------------------|
| `psutil` | Process management | Replaces unsafe shell commands |
| `flask-limiter` | Rate limiting | Prevents abuse and DoS |
| `hmac` (built-in) | Cryptographic verification | Prevents timing attacks |
| `hashlib` (built-in) | Hash functions | Signature verification |
| `sqlite3` WAL mode | Database concurrency | Better performance, no locks |

Install with:
```bash
pip install psutil flask-limiter
```

Note: `hmac` and `hashlib` are part of Python's standard library, no installation needed.

---

## 🔍 Security Audit History

| Date | Auditor | Changes |
|------|---------|---------|
| 2026-02-07 | Idrak AI Ltd Team | Initial security hardening |
| | | Removed shell command injection vectors |
| | | Added input validation |
| | | Added rate limiting |
| | | Added security headers |
| 2026-02-21 | Idrak AI Ltd Team | Added MCP command allowlist |
| | | Prevents execution of arbitrary commands via MCP configs |
| | | Validates package names and Docker flags |
| | | Comprehensive test coverage for MCP security |
| | | Added webhook signature verification |
| | | HMAC-SHA256 verification for WhatsApp, Slack |
| | | Secret token verification for Telegram |
| | | JWT Bearer token validation for MS Teams |
| | | 35 comprehensive security tests added |
| | | Added SQLite WAL mode for better concurrency |
| | | Prevents database locks under load |
| | | 5 SQLite WAL mode tests added |
| | | Verified session key namespacing by channel |
| | | Ensures user isolation across platforms |
| | | 7 session namespace tests added |
| | | Added SQLite connection timeout (30 seconds) |
| | | Prevents "database is locked" errors |
| | | 4 connection timeout tests added |
| | | Fixed timing attack in password verification |
| | | Uses hmac.compare_digest for constant-time comparison |
| | | 7 timing attack protection tests added |
| | | Implemented tiered authentication system |
| | | 4 security levels: GREEN, YELLOW, ORANGE, RED |
| | | PIN for routine tasks, Password for sensitive ops |
| | | Session management with auto-expiry |
| | | 42 comprehensive auth tests added |
| | | Implemented heartbeat system (GREEN level) |
| | | Proactive morning briefs, deadline watches |
| | | 27 heartbeat tests added |
| | | Implemented pattern detection (ORANGE level) |
| | | Detects repeated tasks, suggests skill creation |
| | | 25 pattern detection tests added |
| | | Implemented background task runner (YELLOW level) |
| | | Periodic tasks with PIN protection |
| | | 30 background task tests added |

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Documentation](https://flask.palletsprojects.com/en/latest/security/)
- [Python Security Best Practices](https://python-security.readthedocs.io/)

---

**Project**: SkillForge - Persistent Memory AI Chatbot  
**Organization**: Idrak AI Ltd  
**License**: Open Source - Safe Open Community Project  
**Mission**: Making AI Useful for Everyone

---

*Last updated: 2026-02-21*

## Test Summary

| Component | Tests | Status |
|-----------|-------|--------|
| Auth Manager | 42 | ✅ Passing |
| Heartbeat Manager | 27 | ✅ Passing |
| Pattern Detector | 25 | ✅ Passing |
| Background Tasks | 30 | ✅ Passing |
| **Total Agentic Features** | **124** | ✅ **All Passing** |
