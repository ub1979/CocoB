# =============================================================================
'''
    File Name : credentials.py
    
    Description : Secure token storage and refresh for OAuth credentials.
                  Tokens are stored in ~/.skillforge/credentials.json with
                  restricted permissions (0600).
                  
                  Supported providers:
                  - gemini: Google Gemini (Google One AI Premium)
                  - anthropic: Anthropic Claude (Claude Pro/Max)
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

import json
import os
import time
from pathlib import Path
from typing import Optional

# =============================================================================
# Storage Configuration
# =============================================================================

CREDENTIALS_DIR = Path.home() / ".skillforge"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


# =============================================================================
# =========================================================================
# Function save_credentials -> str, dict to None (saves OAuth tokens to disk)
# =========================================================================
# =============================================================================

def save_credentials(provider: str, tokens: dict) -> None:
    """
    Save OAuth tokens to disk.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")
        tokens: Token dict with access_token, refresh_token, expires_at
    """
    print(f"[OAuth] Saving credentials for {provider} to {CREDENTIALS_FILE}...")
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing credentials
    creds = {}
    # ==================================
    if CREDENTIALS_FILE.exists():
        try:
            creds = json.loads(CREDENTIALS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            creds = {}

    # Update with new tokens
    creds[provider] = tokens

    # Write with secure permissions
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    os.chmod(CREDENTIALS_FILE, 0o600)  # Read/write for owner only


# =============================================================================
# =========================================================================
# Function load_credentials -> str to Optional[dict] (loads OAuth tokens)
# =========================================================================
# =============================================================================

def load_credentials(provider: str) -> Optional[dict]:
    """
    Load OAuth tokens from disk.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")

    Returns:
        Token dict, or None if not found
    """
    # ==================================
    if not CREDENTIALS_FILE.exists():
        return None

    try:
        creds = json.loads(CREDENTIALS_FILE.read_text())
        return creds.get(provider)
    except (json.JSONDecodeError, IOError):
        return None


# =============================================================================
# =========================================================================
# Function delete_credentials -> str to bool (deletes OAuth tokens)
# =========================================================================
# =============================================================================

def delete_credentials(provider: str) -> bool:
    """
    Delete OAuth tokens for a provider.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")

    Returns:
        True if credentials were deleted, False if not found
    """
    # ==================================
    if not CREDENTIALS_FILE.exists():
        return False

    try:
        creds = json.loads(CREDENTIALS_FILE.read_text())
        # ==================================
        if provider not in creds:
            return False

        del creds[provider]

        # ==================================
        if creds:
            CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
        else:
            CREDENTIALS_FILE.unlink()

        return True
    except (json.JSONDecodeError, IOError):
        return False


# =============================================================================
# =========================================================================
# Function get_valid_token -> str to str (gets valid access token)
# =========================================================================
# =============================================================================

def get_valid_token(provider: str) -> str:
    """
    Get a valid access token, refreshing if needed.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")

    Returns:
        Valid access token

    Raises:
        ValueError: If no credentials exist
        Exception: If refresh fails
    """
    creds = load_credentials(provider)

    # ==================================
    if not creds:
        raise ValueError(
            f"No credentials for {provider}. "
            f"Run: python -m core.llm.auth login {provider}"
        )

    # Check if token is expired (or will expire soon)
    expires_at = creds.get("expires_at", 0)
    # ==================================
    if time.time() >= expires_at:
        # Token expired, refresh it
        # ==================================
        if not creds.get("refresh_token"):
            raise ValueError(
                f"Token expired and no refresh token available. "
                f"Run: python -m core.llm.auth login {provider}"
            )

        # Use provider-specific refresh
        creds = _refresh_token(provider, creds["refresh_token"])

    return creds["access_token"]


# =============================================================================
# =========================================================================
# Function _refresh_token -> str, str to dict (refreshes access token)
# =========================================================================
# =============================================================================

def _refresh_token(provider: str, refresh_token: str) -> dict:
    """
    Refresh access token using provider-specific logic.

    Args:
        provider: Provider name
        refresh_token: The refresh token

    Returns:
        Updated credentials dict
    """
    # ==================================
    if provider == "gemini":
        from . import gemini
        new_creds = gemini.refresh(refresh_token)
    # ==================================
    elif provider == "anthropic":
        from . import anthropic
        new_creds = anthropic.refresh(refresh_token)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Save updated credentials
    save_credentials(provider, new_creds)
    return new_creds


# =============================================================================
# =========================================================================
# Function is_logged_in -> str to bool (checks if provider has credentials)
# =========================================================================
# =============================================================================

def is_logged_in(provider: str) -> bool:
    """
    Check if a provider has valid credentials.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")

    Returns:
        True if credentials exist (may be expired but refreshable)
    """
    creds = load_credentials(provider)
    return creds is not None and (
        creds.get("access_token") or creds.get("refresh_token")
    )


# =============================================================================
# =========================================================================
# Function get_token_info -> str to Optional[dict] (gets credential info)
# =========================================================================
# =============================================================================

def get_token_info(provider: str) -> Optional[dict]:
    """
    Get information about stored credentials.

    Args:
        provider: Provider name (e.g., "gemini", "anthropic")

    Returns:
        Dict with logged_in, expires_at, expired status, or None
    """
    creds = load_credentials(provider)
    # ==================================
    if not creds:
        return None

    expires_at = creds.get("expires_at", 0)
    return {
        "logged_in": True,
        "expires_at": expires_at,
        "expired": time.time() >= expires_at,
        "has_refresh_token": bool(creds.get("refresh_token")),
    }


# =============================================================================
# End of File - SkillForge OAuth Credentials Management
# =============================================================================
