# LLM Providers Documentation

This document covers the multi-provider LLM framework used by mr_bot.

## Table of Contents

- [Overview](#overview)
- [Security Best Practices](#security-best-practices)
- [Supported Providers](#supported-providers)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Provider-Specific Notes](#provider-specific-notes)
- [Programmatic Usage](#programmatic-usage)
- [Adding New Providers](#adding-new-providers)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Integration Guide](#integration-guide)
- [Troubleshooting](#troubleshooting)

---

## Overview

The LLM provider framework allows you to easily switch between different AI providers without changing your application code. All providers implement a common interface (`LLMProvider`), making them interchangeable.

### Key Features

- **11 Built-in Providers**: Ollama, OpenAI, Anthropic, Groq, Together AI, vLLM, Azure OpenAI, Kimi, Google Gemini, Claude CLI, Gemini CLI
- **CLI-Based Providers**: Use official CLIs (Claude Code, Gemini CLI) to access Pro/Max subscriptions
- **CLI Authentication**: Use `gcloud auth` for Gemini Vertex AI or `az login` for Azure
- **Streaming Support**: Real-time response streaming with `chat_stream()`
- **Token Management**: Estimation, context checking, and automatic compaction
- **Extensible**: Register custom providers with the factory pattern
- **Backward Compatible**: Existing `AIClient` code continues to work
- **Security Focused**: API keys via environment variables only

### Security Notice

> 🛡️ **API Key Security**: Never hardcode API keys in configuration files. Always use environment variables.
> 
> ```python
> # ✅ CORRECT - Use environment variable
> "api_key": os.environ.get("OPENAI_API_KEY")
> 
> # ❌ WRONG - Security risk
> "api_key": "sk-abc123..."
> ```
> 
> The configuration validator will warn you if it detects potentially hardcoded API keys.

---

## Supported Providers

| Provider | Type | Auth Method | Default Endpoint |
|----------|------|-------------|------------------|
| **Local Providers** |
| Ollama | OpenAI-compatible | None | `http://localhost:11434/v1` |
| LM Studio | OpenAI-compatible | None | `http://localhost:1234/v1` |
| MLX | OpenAI-compatible | None | `http://localhost:8080/v1` |
| vLLM | OpenAI-compatible | None | `http://localhost:8000/v1` |
| **API Key Providers** |
| OpenAI | OpenAI-compatible | API Key | `https://api.openai.com/v1` |
| Anthropic | Native | API Key | `https://api.anthropic.com` |
| Groq | OpenAI-compatible | API Key | `https://api.groq.com/openai/v1` |
| Together AI | OpenAI-compatible | API Key | `https://api.together.xyz/v1` |
| Kimi/Moonshot | OpenAI-compatible | API Key | `https://api.moonshot.cn/v1` |
| Google Gemini | Native | API Key | Google API |
| Azure OpenAI | OpenAI-compatible | API Key | Custom (required) |
| **CLI Providers (Subscription)** |
| Claude CLI | CLI Wrapper | CLI OAuth | Uses `claude -p` command |
| Gemini CLI | CLI Wrapper | CLI OAuth | Uses `gemini -p` command |
| **Enterprise/Cloud** |
| Gemini Vertex | Native | gcloud auth | Vertex AI |
| Azure AD | OpenAI-compatible | az login | Custom (required) |

> **Note**: CLI providers (`claude-cli`, `gemini-cli`) are RECOMMENDED for subscription users.
> OAuth providers (`anthropic-oauth`, `gemini-oauth`) are blocked by vendors as of Jan 2026.

---

## Security Best Practices

### API Key Management

1. **Use Environment Variables**: Never commit API keys to version control
   ```bash
   export OPENAI_API_KEY="sk-..."
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

2. **Validate Configuration**: Run `config.validate_config()` to check for issues

3. **Rotate Keys Regularly**: Change API keys periodically

4. **Use Least Privilege**: Only enable providers you actually use

### CLI Providers (Most Secure for Subscriptions)

CLI providers are the **most secure option** for subscription users because:
- ✅ No API keys to manage
- ✅ Authentication handled by official CLI tools
- ✅ Tokens managed by vendor (Google/Anthropic)
- ✅ No credentials stored in mr_bot

**Recommended for:**
- Claude Pro/Max subscribers → Use `claude-cli`
- Google One AI Premium subscribers → Use `gemini-cli`

### Network Security

- Use HTTPS for all API endpoints (enforced by providers)
- Configure firewall rules for local providers (Ollama, LM Studio)
- Use VPN for remote access to local providers

### Audit and Monitoring

Enable logging to track API usage:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

---

## CLI-Based Providers (RECOMMENDED for Subscriptions)

For users with **Claude Pro/Max** or **Google One AI Premium** subscriptions, CLI-based providers are the recommended way to use your subscription without API keys.

> **Why CLI providers instead of OAuth?**
> As of January 2026, both Anthropic and Google have blocked direct OAuth tokens from third-party tools.
> CLI providers work by wrapping the official CLI tools, which have their own OAuth authentication.

### Claude Code CLI Provider (`claude-cli`)

Uses the official Claude Code CLI to access your Claude Pro/Max subscription.

**Setup:**
```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Login (one-time)
claude login
```

**Configuration:**
```python
LLM_PROVIDER = "claude-cli"

LLM_PROVIDERS = {
    "claude-cli": {
        "provider": "claude-cli",
        "model": "claude-sonnet-4-20250514",
        "context_window": 200000,
        "max_response_tokens": 8192,
        "timeout": 120,
    },
}
```

**How it works:**
- Wraps `claude -p "prompt"` command (headless mode)
- Streams output via `--output-format stream-json`
- Supports session continuation with `--resume`
- Uses your existing CLI authentication

**Technical Note:** The provider passes `input=''` to `subprocess.run()` because the CLI expects stdin input even with the `-p` flag. Without this, the subprocess hangs indefinitely.

### Gemini CLI Provider (`gemini-cli`)

Uses the official Gemini CLI to access your Google One AI Premium subscription.

**Setup:**
```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Login (one-time)
gemini auth login
```

**Configuration:**
```python
LLM_PROVIDER = "gemini-cli"

LLM_PROVIDERS = {
    "gemini-cli": {
        "provider": "gemini-cli",
        "model": "",  # Empty = use CLI default (gemini-2.5-pro)
        "context_window": 1000000,
        "max_response_tokens": 8192,
        "timeout": 120,
    },
}
```

**How it works:**
- Wraps `gemini -p "prompt"` command (headless mode)
- Uses CLI's default model if not specified
- Streams output line by line
- Uses your existing CLI authentication

**Technical Note:** The provider passes `input=''` to `subprocess.run()` because the CLI expects stdin input even with the `-p` flag. Without this, the subprocess hangs indefinitely.

---

## Enterprise/Cloud CLI Authentication

For enterprise users, these providers use cloud CLI tools instead of API keys.

### Google Gemini with gcloud

```bash
# One-time setup
gcloud auth application-default login
# Browser opens, log in with Google account
# Credentials saved to ~/.config/gcloud/application_default_credentials.json

# Set your GCP project
export GCP_PROJECT="your-project-id"
```

```python
# In config.py
LLM_PROVIDER = "gemini-cli"
```

### Azure OpenAI with az login

```bash
# One-time setup
az login
# Browser opens, log in with Microsoft account
# Token cached locally
```

```python
# In config.py
LLM_PROVIDER = "azure-cli"
```

### Google Gemini with OAuth (DEPRECATED - BLOCKED)

> **WARNING**: As of January 2026, Google has blocked OAuth tokens from third-party tools.
> The login flow works, but API calls fail with "restricted_client" error.
> **USE `gemini-cli` INSTEAD** - see CLI-Based Providers section above.

<details>
<summary>Legacy OAuth documentation (kept for reference)</summary>

For users with **Google One AI Premium** subscriptions:

```bash
# Prerequisites: Install Gemini CLI (for OAuth credentials)
npm install -g @google/gemini-cli

# One-time login
python -m core.llm.auth login gemini
```

```python
# In config.py
LLM_PROVIDER = "gemini-oauth"
```

</details>

### Anthropic Claude with OAuth (DEPRECATED - BLOCKED)

> **WARNING**: As of January 2026, Anthropic has blocked OAuth tokens from third-party tools.
> The login flow works, but API calls fail with "OAuth authentication is currently not supported."
> **USE `claude-cli` INSTEAD** - see CLI-Based Providers section above.

<details>
<summary>Legacy OAuth documentation (kept for reference)</summary>

For users with **Claude Pro or Max** subscriptions:

```bash
# Prerequisites: Install Claude Code CLI (for OAuth credentials)
npm install -g @anthropic-ai/claude-code

# One-time login
python -m core.llm.auth login anthropic
```

```python
# In config.py
LLM_PROVIDER = "anthropic-oauth"
```

</details>

### auth_method Configuration

The `auth_method` field in LLMConfig controls how authentication is handled:

| Value | Description |
|-------|-------------|
| `api_key` | Traditional API key authentication (default) |
| `cli` | CLI-based OAuth (gcloud auth, az login) |
| `oauth` | Direct OAuth login (for subscription users) |
| `env` | API key from environment variable |

---

## Quick Start

### 1. Configure Your Provider

Edit `config.py` and set the `LLM_PROVIDER` variable:

```python
# Use Ollama (default, no API key needed)
LLM_PROVIDER = "ollama"

# Or use OpenAI
LLM_PROVIDER = "openai"

# Or use Anthropic Claude
LLM_PROVIDER = "anthropic"
```

### 2. Set API Keys (if needed)

For cloud providers, set environment variables:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Groq
export GROQ_API_KEY="gsk_..."

# Together AI
export TOGETHER_API_KEY="..."

# Kimi/Moonshot
export MOONSHOT_API_KEY="..."

# Azure OpenAI
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/..."

# Google Gemini (API key mode)
export GOOGLE_API_KEY="..."

# Google Gemini (CLI/Vertex AI mode)
export GCP_PROJECT="your-project-id"
```

### 3. Run Your Bot

```bash
python test_local.py    # Quick test
python gradio_ui.py     # Web UI
python bot.py           # MS Teams server
```

---

## Configuration Reference

### LLMConfig Fields

Each provider configuration in `LLM_PROVIDERS` supports these options:

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `provider` | str | Yes | - | Provider name (e.g., "ollama", "openai", "anthropic", "gemini") |
| `model` | str | Yes | - | Model name/identifier |
| `base_url` | str | No | Provider-specific | API endpoint URL |
| `api_key` | str | Depends | None | API key (required for cloud providers unless using CLI auth) |
| `auth_method` | str | No | "api_key" | Authentication method: "api_key", "cli", or "env" |
| `context_window` | int | No | 4096 | Maximum context tokens |
| `max_response_tokens` | int | No | 4096 | Maximum response tokens |
| `temperature` | float | No | 0.7 | Sampling temperature (0.0-2.0) |
| `timeout` | int | No | 60 | Request timeout in seconds |
| `extra` | dict | No | {} | Provider-specific additional options |

### Full Configuration Example

```python
import os

LLM_PROVIDER = "ollama"  # Active provider

LLM_PROVIDERS = {
    "ollama": {
        "provider": "ollama",
        "model": "gemma3:1b",
        "base_url": "http://localhost:11434/v1",
        "context_window": 131072,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
    "openai": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "context_window": 128000,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
    "anthropic": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "api_key": os.environ.get("ANTHROPIC_API_KEY"),
        "context_window": 200000,
        "max_response_tokens": 8192,
        "temperature": 0.7,
        "timeout": 120,
    },
    "groq": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "api_key": os.environ.get("GROQ_API_KEY"),
        "context_window": 128000,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 30,
    },
    "together": {
        "provider": "together",
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "api_key": os.environ.get("TOGETHER_API_KEY"),
        "context_window": 128000,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
    "vllm": {
        "provider": "vllm",
        "model": "your-model-name",
        "base_url": "http://localhost:8000/v1",
        "context_window": 8192,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
    "azure": {
        "provider": "azure",
        "model": "gpt-4o",
        "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
        "context_window": 128000,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
    "kimi": {
        "provider": "kimi",
        "model": "moonshot-v1-8k",
        "api_key": os.environ.get("MOONSHOT_API_KEY"),
        "context_window": 8000,
        "max_response_tokens": 4096,
        "temperature": 0.7,
        "timeout": 60,
    },
}
```

---

## Provider-Specific Notes

### Ollama

Local inference with Ollama. No API key required.

```bash
# Install and run Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# Pull a model
ollama pull gemma3:1b
ollama pull llama3.2
ollama pull mistral
```

Configuration:
```python
{
    "provider": "ollama",
    "model": "gemma3:1b",  # Or any model you've pulled
    "base_url": "http://localhost:11434/v1",
}
```

### OpenAI

Cloud inference with OpenAI's API.

```python
{
    "provider": "openai",
    "model": "gpt-4o",  # Or "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"
    "api_key": os.environ.get("OPENAI_API_KEY"),
}
```

Available models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`, `o1-preview`, `o1-mini`

### Anthropic Claude

Claude handles system prompts differently - they're passed as a top-level parameter, not in the messages array. The provider handles this automatically.

**Option 1: API Key**

```python
{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": os.environ.get("ANTHROPIC_API_KEY"),
}
```

**Option 2: OAuth (for Claude Pro/Max subscribers)**

```bash
# Prerequisites: Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Login with your Anthropic account
python -m core.llm.auth login anthropic
```

```python
{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "auth_method": "oauth",
}
```

Available models: `claude-sonnet-4-20250514`, `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`, `claude-3-haiku-20240307`

### Groq

Ultra-fast inference with Groq's LPU hardware. Two presets available:

**groq** (Fast - Default):
```python
{
    "provider": "groq",
    "model": "llama-3.1-8b-instant",  # 560 tokens/sec
    "api_key": os.environ.get("GROQ_API_KEY"),
    "max_response_tokens": 1024,
    "timeout": 30,
}
```

**groq-large** (Smarter):
```python
{
    "provider": "groq",
    "model": "llama-3.3-70b-versatile",  # 280 tokens/sec
    "api_key": os.environ.get("GROQ_API_KEY"),
    "max_response_tokens": 2048,
    "timeout": 60,
}
```

**Model Speed Comparison:**
| Model | Speed | Use Case |
|-------|-------|----------|
| `llama-3.1-8b-instant` | 560 T/s | Fast responses, simple tasks |
| `llama-3.3-70b-versatile` | 280 T/s | Complex reasoning, better quality |
| `mixtral-8x7b-32768` | 400 T/s | Long context (32K tokens) |

### Together AI

Access to many open-source models.

```python
{
    "provider": "together",
    "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "api_key": os.environ.get("TOGETHER_API_KEY"),
}
```

### vLLM

Self-hosted inference with vLLM server.

```bash
# Start vLLM server
pip install vllm
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-chat-hf
```

```python
{
    "provider": "vllm",
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "base_url": "http://localhost:8000/v1",
}
```

### Azure OpenAI

Microsoft Azure-hosted OpenAI models.

```python
{
    "provider": "azure",
    "model": "gpt-4o",
    "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT"),  # Required!
    "api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
}
```

### Kimi/Moonshot

Chinese AI provider with OpenAI-compatible API.

```python
{
    "provider": "kimi",
    "model": "moonshot-v1-8k",  # Or "moonshot-v1-32k", "moonshot-v1-128k"
    "api_key": os.environ.get("MOONSHOT_API_KEY"),
}
```

### Google Gemini

Google's Gemini models with massive context window (up to 1M tokens).

**Option 1: API Key (Recommended for personal use)**

```bash
# Get API key from https://makersuite.google.com/app/apikey
export GOOGLE_API_KEY="..."
pip install google-generativeai
```

```python
{
    "provider": "gemini",
    "model": "gemini-1.5-pro",  # Or "gemini-1.5-flash", "gemini-pro"
    "api_key": os.environ.get("GOOGLE_API_KEY"),
    "context_window": 1000000,
}
```

**Option 2: gcloud CLI (Recommended for enterprise/GCP users)**

```bash
# One-time setup
gcloud auth application-default login
export GCP_PROJECT="your-project-id"
pip install google-cloud-aiplatform google-auth
```

```python
{
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "auth_method": "cli",
    "context_window": 1000000,
    "extra": {
        "gcp_project": os.environ.get("GCP_PROJECT"),
        "gcp_location": "us-central1",  # Optional
    },
}
```

Available models: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-pro`, `gemini-pro-vision`

**Option 3: OAuth (for Google One AI Premium subscribers)**

This option is for users who have a Google One AI Premium subscription and want to use their subscription benefits via the API without separate billing.

```bash
# Prerequisites: Install Gemini CLI
npm install -g @google/gemini-cli

# Login with your Google account
python -m core.llm.auth login gemini
# Browser opens for Google OAuth consent
# Tokens saved to ~/.mr_bot/credentials.json
```

```python
{
    "provider": "gemini",
    "model": "gemini-1.5-pro",
    "auth_method": "oauth",
    "context_window": 1000000,
}
```

**How it works:**
1. OAuth credentials are extracted from the installed Gemini CLI
2. Browser opens for you to login with your Google account
3. Access and refresh tokens are stored locally
4. Tokens auto-refresh when expired

**CLI Commands:**
```bash
# Login to Gemini
python -m core.llm.auth login gemini

# Check login status
python -m core.llm.auth status

# Logout
python -m core.llm.auth logout gemini
```

### Azure OpenAI with Azure AD

Use Azure AD authentication instead of API keys.

```bash
# One-time setup
az login
pip install azure-identity
```

```python
{
    "provider": "azure",
    "model": "gpt-4o",
    "base_url": os.environ.get("AZURE_OPENAI_ENDPOINT"),
    "auth_method": "cli",  # Uses DefaultAzureCredential
}
```

This uses `DefaultAzureCredential` which supports:
- Azure CLI (`az login`)
- Environment variables
- Managed Identity
- Visual Studio Code
- Azure PowerShell

---

## Programmatic Usage

### Basic Usage

```python
from core.llm import LLMProviderFactory

# Create provider from config dict
provider = LLMProviderFactory.from_dict({
    "provider": "ollama",
    "model": "gemma3:1b",
})

# Send chat request
response = provider.chat([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
])
print(response)
```

### Using with config.py

```python
from core.llm import LLMProviderFactory
import config

# Create provider from active config
llm_config = config.LLM_PROVIDERS[config.LLM_PROVIDER]
provider = LLMProviderFactory.from_dict(llm_config)

# Use provider
response = provider.chat([{"role": "user", "content": "Hello!"}])
```

### Streaming Responses

```python
# Stream response chunk by chunk
for chunk in provider.chat_stream([
    {"role": "user", "content": "Tell me a story"}
]):
    print(chunk, end="", flush=True)
print()  # Newline at end
```

### Context Management

```python
# Check if messages fit in context window
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello!"},
    # ... more messages
]

check = provider.check_context_size(messages)
print(f"Total tokens: {check['total_tokens']}")
print(f"Available tokens: {check['available_tokens']}")
print(f"Within limit: {check['within_limit']}")
print(f"Needs compaction: {check['needs_compaction']}")

# Summarize old messages for compaction
if check['needs_compaction']:
    old_messages = messages[:-5]  # Keep last 5
    summary = provider.summarize_conversation(old_messages)
    print(f"Summary: {summary}")
```

### Token Estimation

```python
text = "Hello, how are you doing today?"
tokens = provider.estimate_tokens(text)
print(f"Estimated tokens: {tokens}")
```

### Provider Properties

```python
print(f"Provider: {provider.provider_name}")  # e.g., "ollama"
print(f"Model: {provider.model_name}")        # e.g., "gemma3:1b"
print(f"Context window: {provider.config.context_window}")
print(f"Max response: {provider.config.max_response_tokens}")
```

---

## Adding New Providers

### Option 1: Add OpenAI-Compatible Provider

If your provider uses the OpenAI API format, just add it to `config.py`:

```python
LLM_PROVIDERS = {
    # ... existing providers ...

    "my_provider": {
        "provider": "my_provider",  # Use any name
        "model": "my-model-name",
        "base_url": "https://api.my-provider.com/v1",
        "api_key": os.environ.get("MY_PROVIDER_API_KEY"),
        "context_window": 8192,
        "max_response_tokens": 4096,
    },
}
```

Then register it in `core/llm/factory.py`:

```python
_providers: Dict[str, Type[LLMProvider]] = {
    # ... existing providers ...
    "my_provider": OpenAICompatibleProvider,
}
```

And optionally add defaults in `core/llm/openai_compat.py`:

```python
PROVIDER_DEFAULTS = {
    # ... existing defaults ...
    "my_provider": {
        "base_url": "https://api.my-provider.com/v1",
        "requires_key": True,
    },
}
```

### Option 2: Create Custom Provider Class

For providers with non-standard APIs, create a new provider class:

#### Step 1: Create the Provider File

Create `core/llm/my_provider.py`:

```python
"""
My Custom LLM Provider
"""

import json
from typing import List, Dict, Generator, Any
import requests

from .base import LLMProvider, LLMConfig


class MyCustomProvider(LLMProvider):
    """Provider for My Custom API"""

    BASE_URL = "https://api.my-provider.com"

    def _validate_config(self) -> None:
        """Validate provider-specific configuration"""
        if not self.config.api_key:
            raise ValueError(
                "API key is required for MyCustomProvider. "
                "Set it via the 'api_key' config option."
            )

        if self.config.base_url is None:
            self.config.base_url = self.BASE_URL

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send chat request and return response text"""
        url = f"{self.config.base_url}/chat"
        headers = self._get_headers()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_response_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            # Extract response based on your API's format
            return data.get("response", "")

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error communicating with MyProvider: {str(e)}")

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Stream chat response"""
        url = f"{self.config.base_url}/chat/stream"
        headers = self._get_headers()

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": True,
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    # Parse based on your API's streaming format
                    data = json.loads(line.decode("utf-8"))
                    if "text" in data:
                        yield data["text"]

        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error streaming from MyProvider: {str(e)}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Use provider-specific tokenizer if available
        # Otherwise use rough estimate
        return len(text) // 4
```

#### Step 2: Register the Provider

Edit `core/llm/factory.py`:

```python
from .my_provider import MyCustomProvider

class LLMProviderFactory:
    _providers: Dict[str, Type[LLMProvider]] = {
        # ... existing providers ...
        "my_provider": MyCustomProvider,
    }
```

#### Step 3: Export from Package

Edit `core/llm/__init__.py`:

```python
from .my_provider import MyCustomProvider

__all__ = [
    # ... existing exports ...
    "MyCustomProvider",
]
```

#### Step 4: Add Configuration

Edit `config.py`:

```python
LLM_PROVIDERS = {
    # ... existing providers ...
    "my_provider": {
        "provider": "my_provider",
        "model": "my-model",
        "api_key": os.environ.get("MY_PROVIDER_API_KEY"),
        "context_window": 8192,
        "max_response_tokens": 4096,
    },
}
```

### Option 3: Runtime Registration

Register providers at runtime without modifying source files:

```python
from core.llm import LLMProvider, LLMConfig, LLMProviderFactory
from typing import List, Dict, Generator

class MyRuntimeProvider(LLMProvider):
    def _validate_config(self) -> None:
        pass

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Your implementation
        return "Response"

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        yield "Response"

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

# Register at runtime
LLMProviderFactory.register("my_runtime", MyRuntimeProvider)

# Use it
provider = LLMProviderFactory.from_dict({
    "provider": "my_runtime",
    "model": "any-model",
})
```

---

## Architecture

### Class Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                      LLMProvider (ABC)                       │
│  chat() | chat_stream() | estimate_tokens() | check_context │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ OpenAICompat  │ │  Anthropic    │ │    Gemini     │ │  (Custom)     │
│   Provider    │ │   Provider    │ │   Provider    │ │   Provider    │
├───────────────┤ ├───────────────┤ ├───────────────┤ └───────────────┘
│ - OpenAI      │ │ - Claude      │ │ - API key     │
│ - Ollama      │ │ - system sep  │ │ - Vertex AI   │
│ - vLLM        │ └───────────────┘ │ - gcloud auth │
│ - Groq        │                   └───────────────┘
│ - Together    │
│ - Azure (+AD) │
│ - Kimi        │
└───────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    LLMProviderFactory                        │
│  create(config) | from_dict(dict) | register(name, class)   │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
core/llm/
├── __init__.py           # Package exports
├── base.py               # LLMProvider ABC + LLMConfig dataclass
├── openai_compat.py      # OpenAI-compatible providers (incl. Azure AD)
├── anthropic_provider.py # Anthropic Claude provider
├── gemini_provider.py    # Google Gemini provider (API + Vertex AI)
└── factory.py            # LLMProviderFactory
```

### Data Flow

```
User Code
    │
    ▼
LLMProviderFactory.from_dict(config)
    │
    ▼
LLMConfig (dataclass)
    │
    ▼
Provider.__init__(config)
    │
    ▼
Provider._validate_config()
    │
    ▼
Provider ready for use
    │
    ├──► provider.chat(messages) ──► API Request ──► Response Text
    │
    └──► provider.chat_stream(messages) ──► API Request ──► Generator[str]
```

---

## API Reference

### LLMConfig

```python
@dataclass
class LLMConfig:
    provider: str                          # Provider name
    model: str                             # Model identifier
    base_url: Optional[str] = None         # API endpoint
    api_key: Optional[str] = None          # API key
    auth_method: str = "api_key"           # "api_key", "cli", or "env"
    context_window: int = 4096             # Max context tokens
    max_response_tokens: int = 4096        # Max response tokens
    temperature: float = 0.7               # Sampling temperature
    timeout: int = 60                      # Request timeout (seconds)
    extra: Dict[str, Any] = field(default_factory=dict)  # Extra options
```

### LLMProvider (Abstract Base Class)

```python
class LLMProvider(ABC):
    def __init__(self, config: LLMConfig): ...

    @abstractmethod
    def _validate_config(self) -> None: ...

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str: ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]: ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int: ...

    def check_context_size(self, messages: List[Dict[str, str]]) -> Dict[str, Any]: ...

    def summarize_conversation(self, messages: List[Dict[str, str]]) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_name(self) -> str: ...
```

### LLMProviderFactory

```python
class LLMProviderFactory:
    @classmethod
    def create(cls, config: LLMConfig) -> LLMProvider: ...

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> LLMProvider: ...

    @classmethod
    def register(cls, name: str, provider_class: Type[LLMProvider]) -> None: ...

    @classmethod
    def list_providers(cls) -> List[str]: ...

    @classmethod
    def get_provider_class(cls, name: str) -> Type[LLMProvider]: ...
```

---

## Integration Guide

### Using with MessageRouter

```python
from core.sessions import SessionManager
from core.llm import LLMProviderFactory
from core.router import MessageRouter
import config

# Initialize
session_manager = SessionManager(config.SESSION_DATA_DIR)
llm_provider = LLMProviderFactory.from_dict(config.LLM_PROVIDERS[config.LLM_PROVIDER])
router = MessageRouter(session_manager, llm_provider)

# Handle message
response = await router.handle_message(
    channel="my_channel",
    user_id="user-123",
    user_message="Hello!",
    user_name="Alice"
)
```

### Using with Gradio

```python
import gradio as gr
from core.llm import LLMProviderFactory
import config

provider = LLMProviderFactory.from_dict(config.LLM_PROVIDERS[config.LLM_PROVIDER])

def chat(message, history):
    messages = [{"role": "user", "content": message}]
    response = provider.chat(messages)
    return response

demo = gr.ChatInterface(chat)
demo.launch()
```

### Using with Flask

```python
from flask import Flask, request, jsonify
from core.llm import LLMProviderFactory
import config

app = Flask(__name__)
provider = LLMProviderFactory.from_dict(config.LLM_PROVIDERS[config.LLM_PROVIDER])

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    response = provider.chat(messages)
    return jsonify({"response": response})
```

### Switching Providers at Runtime

```python
from core.llm import LLMProviderFactory
import config

class MultiProviderChat:
    def __init__(self):
        self.providers = {}
        for name, cfg in config.LLM_PROVIDERS.items():
            try:
                self.providers[name] = LLMProviderFactory.from_dict(cfg)
            except Exception as e:
                print(f"Could not load {name}: {e}")

    def chat(self, provider_name: str, messages: list) -> str:
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        return self.providers[provider_name].chat(messages)

# Usage
chat = MultiProviderChat()
response = chat.chat("openai", [{"role": "user", "content": "Hello!"}])
```

---

## Troubleshooting

### "API key is required"

Set the appropriate environment variable for your provider:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "Connection refused"

For local providers (Ollama, vLLM), ensure the server is running:
```bash
ollama serve  # For Ollama
python -m vllm.entrypoints.openai.api_server --model your-model  # For vLLM
```

### "Model not found"

Ensure you've pulled/deployed the model:
```bash
ollama pull gemma3:1b  # For Ollama
```

### Timeout errors

Increase the timeout in your provider configuration:
```python
{
    "provider": "...",
    "timeout": 120,  # 2 minutes
}
```

### Token estimation inaccurate

Install `tiktoken` for accurate OpenAI token counts:
```bash
pip install tiktoken
```

### "Unknown provider"

Check that the provider is registered. List available providers:
```python
from core.llm import LLMProviderFactory
print(LLMProviderFactory.list_providers())
```

### Streaming not working

Ensure your provider supports streaming. Check the provider's API documentation.

### Rate limiting

Add delays between requests or use a provider with higher rate limits:
```python
import time

for message in messages:
    response = provider.chat([message])
    time.sleep(1)  # 1 second delay
```

---

## Changelog

### v1.4.0

- **NEW: CLI-Based Providers** for subscription access without API keys
  - `claude-cli`: Wraps Claude Code CLI (`claude -p`) for Claude Pro/Max subscribers
  - `gemini-cli`: Wraps Gemini CLI (`gemini -p`) for Google One AI Premium subscribers
- **DEPRECATED: OAuth Providers** - Both Anthropic and Google have blocked OAuth tokens from third-party tools as of January 2026
  - `anthropic-oauth`: Login works but API calls blocked
  - `gemini-oauth`: Login works but API calls blocked
- Updated Settings UI with warnings about OAuth limitations
- Added model discovery for local providers (Ollama, LM Studio, vLLM, MLX)
- Added API Keys input section in Settings UI

### v1.3.0

- Added Anthropic Claude OAuth support for Claude Pro/Max subscribers
- New config: `anthropic-oauth`
- Extended CLI: `python -m core.llm.auth login/status/logout anthropic`
- OAuth credentials auto-extracted from installed Claude Code CLI
- Restructured auth module for better maintainability (see `core/llm/auth/README.md`)

### v1.2.0

- Added Google Gemini OAuth support for Google One AI Premium subscribers
- New `auth_method="oauth"` option for subscription-based authentication
- New config: `gemini-oauth`
- New CLI: `python -m core.llm.auth login/status/logout gemini`
- OAuth credentials auto-extracted from installed Gemini CLI

### v1.1.0

- Added Google Gemini provider with API key and Vertex AI/gcloud auth support
- Added CLI authentication support (`auth_method` field)
- Added Azure AD authentication via `az login` and `DefaultAzureCredential`
- New configs: `gemini`, `gemini-cli`, `azure-cli`

### v1.0.0

- Initial release
- 8 built-in providers: Ollama, OpenAI, Anthropic, Groq, Together AI, vLLM, Azure OpenAI, Kimi
- Streaming support via `chat_stream()`
- Token estimation and context management
- Factory pattern for provider creation
- Backward compatibility with `AIClient`
