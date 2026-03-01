# =============================================================================
'''
    File Name : connection.py
    
    Description : Provider Connection Testing module. Tests if a provider 
                  endpoint is reachable and functional. Supports OpenAI-compatible
                  endpoints and Anthropic API with proper error handling and
                  timeout management.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Connection Dependencies
# =============================================================================

import requests
from typing import Tuple


# =============================================================================
# =========================================================================
# Function test_provider_connection -> str, str, Optional[str], int to Tuple[bool, str]
# =========================================================================
# =============================================================================

def test_provider_connection(
    base_url: str,
    model: str,
    api_key: str = None,
    timeout: int = 10
) -> Tuple[bool, str]:
    """
    Test connection to an OpenAI-compatible endpoint.

    Args:
        base_url: API endpoint URL
        model: Model name to test
        api_key: Optional API key
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    # ==================================
    # Validate required parameters
    # ==================================
    if not base_url or not model:
        return False, "Please provide both URL and model name"

    # ==================================
    # Normalize URL to /v1 format
    # ==================================
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    # ==================================
    # Setup request headers
    # ==================================
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        # ==================================
        # Try models endpoint first (lightweight check)
        # ==================================
        models_url = f"{base_url}/models"
        resp = requests.get(models_url, headers=headers, timeout=timeout)

        if resp.status_code == 200:
            return True, f"Connected! Models available at {base_url}"

        # ==================================
        # Try a minimal chat completion
        # ==================================
        chat_url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }
        resp = requests.post(chat_url, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 200:
            return True, f"Connected! {model} is responding"
        else:
            error_text = resp.text[:200] if resp.text else "No response body"
            return False, f"Error {resp.status_code}: {error_text}"

    except requests.exceptions.ConnectionError:
        # ==================================
        # Provide helpful messages for local providers
        # ==================================
        if "localhost:8080" in base_url or "127.0.0.1:8080" in base_url:
            return False, (
                f"❌ MLX server not running!\n\n"
                f"Start it with:\n"
                f"mlx_lm.server --model mlx-community/Mistral-7B-Instruct-v0.3-4bit --port 8080"
            )
        elif "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
            return False, (
                f"❌ Ollama not running!\n\n"
                f"Start it with:\n"
                f"ollama serve"
            )
        elif "localhost:1234" in base_url or "127.0.0.1:1234" in base_url:
            return False, (
                f"❌ LM Studio server not running!\n\n"
                f"Open LM Studio → Start Server"
            )
        else:
            return False, f"Cannot connect to {base_url}"
    except requests.exceptions.Timeout:
        return False, f"Connection timed out after {timeout}s"
    except Exception as e:
        return False, f"Error: {str(e)}"


# =============================================================================
# =========================================================================
# Function test_anthropic_connection -> str, int to Tuple[bool, str]
# =========================================================================
# =============================================================================

def test_anthropic_connection(api_key: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    Test connection to Anthropic API.

    Args:
        api_key: Anthropic API key
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, message)
    """
    # ==================================
    # Validate API key presence
    # ==================================
    if not api_key:
        return False, "Please provide an API key"

    # ==================================
    # Setup Anthropic-specific headers
    # ==================================
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }

    try:
        # ==================================
        # Send a minimal message to test connection
        # ==================================
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Hi"}]
            },
            timeout=timeout
        )

        if resp.status_code == 200:
            return True, "Connected to Anthropic API!"
        else:
            error_text = resp.text[:200] if resp.text else "No response body"
            return False, f"Error {resp.status_code}: {error_text}"

    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Anthropic API"
    except requests.exceptions.Timeout:
        return False, f"Connection timed out after {timeout}s"
    except Exception as e:
        return False, f"Error: {str(e)}"


# =============================================================================
# End of File - mr_bot Provider Connection Testing
# =============================================================================
# Project   : mr_bot - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
