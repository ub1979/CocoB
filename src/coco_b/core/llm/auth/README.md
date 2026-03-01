# OAuth Authentication Module (DEPRECATED)

> **WARNING: OAuth is blocked by both Anthropic and Google as of January 2026**
>
> Both companies have blocked OAuth tokens from being used by third-party tools:
> - **Anthropic**: Returns "OAuth authentication is currently not supported"
> - **Google**: Returns "restricted_client" error
>
> **USE CLI PROVIDERS INSTEAD:**
> - `claude-cli` - Uses Claude Code CLI for Claude Pro/Max subscriptions
> - `gemini-cli` - Uses Gemini CLI for Google One AI Premium subscriptions
>
> See `LLM_PROVIDERS.md` for CLI provider documentation.

---

This module provides OAuth-based authentication for LLM providers. **However, direct OAuth is no longer functional** - use CLI providers instead.

## OAuth Status (as of Jan 2026)

| Provider | OAuth Login | API Calls | Recommendation |
|----------|-------------|-----------|----------------|
| Google Gemini | Works | **BLOCKED** | Use `gemini-cli` |
| Anthropic Claude | Works | **BLOCKED** | Use `claude-cli` |

## Directory Structure

```
core/llm/auth/
├── __init__.py      # Module exports
├── __main__.py      # CLI entry point (python -m core.llm.auth)
├── base.py          # Shared OAuth utilities
│   ├── OAuthCallbackHandler  # HTTP handler for OAuth redirects
│   ├── generate_pkce()       # PKCE code generation
│   ├── run_oauth_flow()      # Generic OAuth flow
│   └── refresh_access_token() # Token refresh
├── gemini.py        # Google Gemini OAuth
│   ├── find_cli()            # Find Gemini CLI
│   ├── extract_credentials() # Extract OAuth creds from CLI
│   ├── get_credentials()     # Get creds (env or CLI)
│   ├── login()               # Run OAuth flow
│   └── refresh()             # Refresh token
├── anthropic.py     # Anthropic Claude OAuth
│   ├── find_cli()            # Find Claude Code CLI
│   ├── extract_credentials() # Extract OAuth creds from CLI
│   ├── get_credentials()     # Get creds (env or CLI)
│   ├── login()               # Run OAuth flow
│   └── refresh()             # Refresh token
├── credentials.py   # Token storage and refresh
│   ├── save_credentials()    # Save tokens to disk
│   ├── load_credentials()    # Load tokens from disk
│   ├── delete_credentials()  # Delete tokens
│   ├── get_valid_token()     # Get valid token (auto-refresh)
│   ├── is_logged_in()        # Check login status
│   └── get_token_info()      # Get token metadata
├── cli.py           # CLI commands
│   ├── cmd_login()           # Login command
│   ├── cmd_status()          # Status command
│   └── cmd_logout()          # Logout command
└── README.md        # This file
```

## Quick Start

### Prerequisites

Install the CLI tool for your provider:

```bash
# For Gemini (Google One AI Premium)
npm install -g @google/gemini-cli

# For Anthropic (Claude Pro/Max)
npm install -g @anthropic-ai/claude-code
```

### Login

```bash
# Gemini
python -m core.llm.auth login gemini

# Anthropic
python -m core.llm.auth login anthropic
```

### Check Status

```bash
python -m core.llm.auth status
```

### Logout

```bash
python -m core.llm.auth logout gemini
python -m core.llm.auth logout anthropic
```

## Configuration

### Config Options

In `config.py`:

```python
# Gemini with OAuth (subscription)
"gemini-oauth": {
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "auth_method": "oauth",
    ...
},

# Anthropic with OAuth (subscription)
"anthropic-oauth": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "auth_method": "oauth",
    ...
},
```

### Environment Variables

Override OAuth client credentials if needed:

```bash
# Gemini
export GEMINI_OAUTH_CLIENT_ID="your-client-id"
export GEMINI_OAUTH_CLIENT_SECRET="your-client-secret"

# Anthropic
export ANTHROPIC_OAUTH_CLIENT_ID="your-client-id"
```

## How It Works

### OAuth Flow

1. User runs `python -m core.llm.auth login <provider>`
2. Browser opens to provider's OAuth consent screen
3. User logs in with their account (uses subscription!)
4. Redirect to `localhost:<port>/oauth2callback` with auth code
5. Code exchanged for access + refresh tokens
6. Tokens saved to `~/.mr_bot/credentials.json`
7. Provider uses tokens, auto-refreshes when expired

### Token Storage

Tokens are stored in `~/.mr_bot/credentials.json` with format:

```json
{
  "gemini": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1234567890.0
  },
  "anthropic": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": 1234567890.0
  }
}
```

File permissions are set to `0600` (owner read/write only).

### Credential Extraction

OAuth client credentials are extracted from installed CLI tools:

**Gemini CLI:**
- Location: `node_modules/@google/gemini-cli-core/dist/.../oauth2.js`
- Pattern: `\d+-[a-z0-9]+\.apps\.googleusercontent\.com` (client ID)
- Pattern: `GOCSPX-[A-Za-z0-9_-]+` (client secret)

**Claude Code:**
- Location: `node_modules/@anthropic-ai/claude-code/cli.js`
- Pattern: UUID format client ID
- Note: Uses public OAuth client (no secret required)

## Programmatic Usage

```python
from core.llm.auth import gemini, anthropic
from core.llm.auth.credentials import get_valid_token, is_logged_in

# Check if logged in
if is_logged_in("gemini"):
    # Get valid token (auto-refreshes if expired)
    token = get_valid_token("gemini")
    print(f"Token: {token[:20]}...")

# Login programmatically
if not is_logged_in("anthropic"):
    tokens = anthropic.login()
    print("Logged in to Anthropic!")
```

## Adding New Providers

To add a new OAuth provider:

1. Create `core/llm/auth/<provider>.py`:

```python
"""
<Provider> OAuth authentication.
"""

from .base import run_oauth_flow, refresh_access_token

# Configuration
AUTH_URL = "https://..."
TOKEN_URL = "https://..."
REDIRECT_URI = "http://localhost:<port>/oauth2callback"
CALLBACK_PORT = <port>
SCOPES = ["..."]
PROVIDER_NAME = "<provider>"

def find_cli():
    """Find the provider's CLI in PATH."""
    ...

def extract_credentials():
    """Extract OAuth creds from CLI."""
    ...

def get_credentials():
    """Get creds from env or CLI."""
    ...

def login():
    """Run OAuth flow."""
    return run_oauth_flow(
        auth_url=AUTH_URL,
        token_url=TOKEN_URL,
        ...
    )

def refresh(refresh_token):
    """Refresh access token."""
    return refresh_access_token(...)
```

2. Update `cli.py`:
   - Add provider to `SUPPORTED_PROVIDERS`
   - Add import and call in `cmd_login()`
   - Add CLI check in `cmd_status()`

3. Update `__init__.py`:
   - Add `from . import <provider>`

4. Update `credentials.py`:
   - Add provider to `_refresh_token()`

5. Update this README

## OAuth Endpoints Reference

### Google Gemini

| Endpoint | URL |
|----------|-----|
| Authorization | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token | `https://oauth2.googleapis.com/token` |
| Callback | `http://localhost:8085/oauth2callback` |

Scopes:
- `https://www.googleapis.com/auth/cloud-platform`
- `https://www.googleapis.com/auth/userinfo.email`

### Anthropic Claude

| Endpoint | URL |
|----------|-----|
| Authorization | `https://claude.ai/oauth/authorize` |
| Token | `https://platform.claude.com/v1/oauth/token` |
| Callback | `http://localhost:8086/oauth2callback` |

Scopes:
- `user:inference` (API access)
- `user:profile` (profile info)

## Troubleshooting

### "CLI not found"

Install the required CLI tool:
```bash
npm install -g @google/gemini-cli      # For Gemini
npm install -g @anthropic-ai/claude-code  # For Anthropic
```

### "Credentials not found"

1. Check if CLI is installed: `which gemini` or `which claude`
2. Set environment variables as fallback
3. Re-run login: `python -m core.llm.auth login <provider>`

### "Token expired"

Tokens auto-refresh when `get_valid_token()` is called. If refresh fails:
```bash
python -m core.llm.auth login <provider>
```

### Port already in use

The callback server uses:
- Port 8085 for Gemini
- Port 8086 for Anthropic

If ports are in use, check for other processes or wait a moment.
