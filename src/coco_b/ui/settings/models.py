# =============================================================================
'''
    File Name : models.py
    
    Description : Model Discovery module for Local LLM Providers. Fetches
                  available models from local providers like Ollama, LM Studio,
                  vLLM, MLX, and handles provider-specific model listing for
                  cloud providers like Anthropic, Gemini, and Azure.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Model Discovery Dependencies
# =============================================================================

import requests
from typing import List, Tuple, Optional


# =============================================================================
# =========================================================================
# Function fetch_ollama_models -> str, int to Tuple[bool, List[str], str]
# =========================================================================
# =============================================================================

def fetch_ollama_models(base_url: str = "http://localhost:11434", timeout: int = 5) -> Tuple[bool, List[str], str]:
    """
    Fetch available models from Ollama.

    Args:
        base_url: Ollama server URL
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, model_list, message)
    """
    try:
        # ==================================
        # Ollama has its own API at /api/tags
        # ==================================
        resp = requests.get(f"{base_url}/api/tags", timeout=timeout)

        if resp.status_code == 200:
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            if models:
                return True, models, f"Found {len(models)} models"
            return False, [], "No models installed. Run: ollama pull <model>"

        return False, [], f"Error {resp.status_code}: {resp.text[:100]}"

    except requests.exceptions.ConnectionError:
        return False, [], "Cannot connect to Ollama. Is it running?"
    except requests.exceptions.Timeout:
        return False, [], f"Connection timed out after {timeout}s"
    except Exception as e:
        return False, [], f"Error: {str(e)}"


# =============================================================================
# =========================================================================
# Function fetch_openai_compatible_models -> str, Optional[str], int to Tuple[bool, List[str], str]
# =========================================================================
# =============================================================================

def fetch_openai_compatible_models(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: int = 5
) -> Tuple[bool, List[str], str]:
    """
    Fetch available models from an OpenAI-compatible endpoint.
    Works with LM Studio, vLLM, MLX, and other compatible servers.

    Args:
        base_url: API endpoint URL
        api_key: Optional API key
        timeout: Request timeout in seconds

    Returns:
        Tuple of (success, model_list, message)
    """
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
        resp = requests.get(f"{base_url}/models", headers=headers, timeout=timeout)

        if resp.status_code == 200:
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            if models:
                return True, models, f"Found {len(models)} models"
            return False, [], "No models available"

        return False, [], f"Error {resp.status_code}: {resp.text[:100]}"

    except requests.exceptions.ConnectionError:
        return False, [], f"Cannot connect to {base_url}"
    except requests.exceptions.Timeout:
        return False, [], f"Connection timed out after {timeout}s"
    except Exception as e:
        return False, [], f"Error: {str(e)}"


# =============================================================================
# =========================================================================
# Function fetch_models_for_provider -> str, dict to Tuple[bool, List[str], str]
# =========================================================================
# =============================================================================

def fetch_models_for_provider(provider_name: str, config: dict) -> Tuple[bool, List[str], str]:
    """
    Fetch available models for a given provider.

    Args:
        provider_name: Name of the provider
        config: Provider configuration dict

    Returns:
        Tuple of (success, model_list, message)
    """
    # ==================================
    # Extract configuration parameters
    # ==================================
    base_url = config.get("base_url", "")
    api_key = config.get("api_key")

    # ==================================
    # Provider-specific handling - Ollama
    # ==================================
    if provider_name == "ollama":
        # Extract base URL without /v1
        ollama_url = base_url.replace("/v1", "").rstrip("/")
        if not ollama_url:
            ollama_url = "http://localhost:11434"
        return fetch_ollama_models(ollama_url)

    # ==================================
    # Provider-specific handling - Local OpenAI-compatible
    # ==================================
    elif provider_name in ("lmstudio", "vllm", "mlx"):
        if not base_url:
            defaults = {
                "lmstudio": "http://localhost:1234/v1",
                "vllm": "http://localhost:8000/v1",
                "mlx": "http://localhost:8080/v1",
            }
            base_url = defaults.get(provider_name, "")
        return fetch_openai_compatible_models(base_url, api_key)

    # ==================================
    # Provider-specific handling - Cloud providers
    # ==================================
    elif provider_name in ("openai", "groq", "together", "kimi", "kimi_auth"):
        # Cloud providers - don't try to list models (requires API key, many models)
        return False, [], "Select model from documentation"

    # ==================================
    # Provider-specific handling - Anthropic
    # ==================================
    elif provider_name in ("anthropic", "anthropic-oauth"):
        # Anthropic has fixed model list
        models = [
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
        return True, models, "Anthropic models"

    # ==================================
    # Provider-specific handling - Gemini
    # ==================================
    elif provider_name in ("gemini", "gemini-cli", "gemini-oauth"):
        # Gemini has fixed model list
        models = [
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
        ]
        return True, models, "Gemini models"

    # ==================================
    # Provider-specific handling - Azure
    # ==================================
    elif provider_name in ("azure", "azure-cli"):
        # Azure uses deployment names, not model IDs
        return False, [], "Enter your Azure deployment name"

    # ==================================
    # Unknown provider
    # ==================================
    else:
        return False, [], f"Model listing not supported for {provider_name}"


# =============================================================================
# End of File - mr_bot Model Discovery Module
# =============================================================================
# Project   : mr_bot - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
