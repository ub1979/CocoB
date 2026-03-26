# =============================================================================
'''
    File Name : gemini.py
    
    Description : Google Gemini OAuth authentication provider for SkillForge.
                  Handles OAuth2 flow for users with Google One AI Premium
                  subscriptions who want to use their subscription via the API
                  without separate billing. Credentials are extracted from the
                  installed Gemini CLI.
    
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

import os
import re
from pathlib import Path
from typing import Optional, Tuple

from .base import run_oauth_flow, refresh_access_token

# =============================================================================
# Configuration Constants
# =============================================================================

# OAuth endpoints for Google authentication
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8085/oauth2callback"
CALLBACK_PORT = 8085

# Scopes required for Gemini API access
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
    "https://www.googleapis.com/auth/generative-language.tuning",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Provider name for credential storage
PROVIDER_NAME = "gemini"


# =============================================================================
# =========================================================================
# Function find_cli -> None to Optional[Path]
# =========================================================================
# =============================================================================

def find_cli() -> Optional[Path]:
    """
    Find the Gemini CLI binary in PATH.

    Returns:
        Path to gemini binary, or None if not found
    """
    # ==================================
    # Iterate through PATH directories
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        # ==================================
        # Check for both Unix and Windows binary names
        for name in ["gemini", "gemini.cmd"]:
            path = Path(dir_path) / name
            # ==================================
            # Return resolved path if binary exists
            if path.exists():
                return path.resolve()
    return None


# =============================================================================
# =========================================================================
# Function extract_credentials -> None to Optional[Tuple[str, str]]
# =========================================================================
# =============================================================================

def extract_credentials() -> Optional[Tuple[str, str]]:
    """
    Extract OAuth credentials from the installed Gemini CLI.

    The Gemini CLI contains embedded OAuth client credentials that
    we can use for authentication.

    Returns:
        Tuple of (client_id, client_secret), or None if not found
    """
    # ==================================
    # Locate the CLI binary
    gemini_path = find_cli()
    # ==================================
    # Return None if CLI not found
    if not gemini_path:
        return None

    cli_dir = gemini_path.parent.parent

    # Search for oauth2.js in possible locations
    search_paths = [
        cli_dir / "node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        cli_dir / "node_modules/@google/gemini-cli-core/dist/code_assist/oauth2.js",
        cli_dir / "lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
        cli_dir / "lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/code_assist/oauth2.js",
        # Global npm locations
        Path("/usr/local/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js"),
        Path("/usr/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js"),
        Path.home() / ".npm-global/lib/node_modules/@google/gemini-cli/node_modules/@google/gemini-cli-core/dist/src/code_assist/oauth2.js",
    ]

    content = None
    # ==================================
    # Try each search path until content is found
    for path in search_paths:
        # ==================================
        # Read file if it exists
        if path.exists():
            try:
                content = path.read_text()
                break
            except Exception:
                continue

    # ==================================
    # Return None if oauth2.js not found
    if not content:
        return None

    # Extract credentials using regex patterns
    # Client ID: numbers-alphanumeric.apps.googleusercontent.com
    id_match = re.search(r'(\d+-[a-z0-9]+\.apps\.googleusercontent\.com)', content)
    # Client secret: GOCSPX-alphanumeric
    secret_match = re.search(r'(GOCSPX-[A-Za-z0-9_-]+)', content)

    # ==================================
    # Return credentials if both patterns matched
    if id_match and secret_match:
        return id_match.group(1), secret_match.group(1)

    return None


# =============================================================================
# =========================================================================
# Function get_credentials -> None to Tuple[str, Optional[str]]
# =========================================================================
# =============================================================================

def get_credentials() -> Tuple[str, Optional[str]]:
    """
    Get OAuth credentials from environment or Gemini CLI.

    Priority:
    1. Environment variables (GEMINI_OAUTH_CLIENT_ID, GEMINI_OAUTH_CLIENT_SECRET)
    2. Extracted from installed Gemini CLI

    Returns:
        Tuple of (client_id, client_secret)

    Raises:
        ValueError: If no credentials can be found
    """
    # ==================================
    # Check environment variables first (user override)
    client_id = os.environ.get("GEMINI_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GEMINI_OAUTH_CLIENT_SECRET")

    # ==================================
    # Return environment variables if client_id is set
    if client_id:
        return client_id, client_secret

    # Try extracting from Gemini CLI
    extracted = extract_credentials()
    # ==================================
    # Return extracted credentials if available
    if extracted:
        return extracted

    # ==================================
    # Raise error if no credentials found
    raise ValueError(
        "Gemini OAuth credentials not found.\n\n"
        "Option 1: Install Gemini CLI (recommended)\n"
        "  npm install -g @google/gemini-cli\n\n"
        "Option 2: Set environment variables\n"
        "  export GEMINI_OAUTH_CLIENT_ID='your-client-id'\n"
        "  export GEMINI_OAUTH_CLIENT_SECRET='your-client-secret'"
    )


# =============================================================================
# =========================================================================
# Function login -> None to dict
# =========================================================================
# =============================================================================

def login() -> dict:
    """
    Run the Gemini OAuth flow and return tokens.

    Opens a browser for the user to log in with their Google account,
    waits for the OAuth callback, and exchanges the auth code for tokens.

    Returns:
        dict with access_token, refresh_token, expires_at

    Raises:
        Exception: If the OAuth flow fails
    """
    # ==================================
    # Retrieve OAuth credentials
    client_id, client_secret = get_credentials()

    # ==================================
    # Execute OAuth flow with Google endpoints
    return run_oauth_flow(
        auth_url=AUTH_URL,
        token_url=TOKEN_URL,
        redirect_uri=REDIRECT_URI,
        client_id=client_id,
        scopes=SCOPES,
        client_secret=client_secret,
        port=CALLBACK_PORT,
        extra_auth_params={
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent to get refresh token
        },
        provider_name="Google Gemini",
    )


# =============================================================================
# =========================================================================
# Function refresh -> str to dict
# =========================================================================
# =============================================================================

def refresh(refresh_token: str) -> dict:
    """
    Refresh Gemini access token.

    Args:
        refresh_token: The refresh token

    Returns:
        dict with new access_token and expires_at
    """
    # ==================================
    # Retrieve OAuth credentials
    client_id, client_secret = get_credentials()

    # ==================================
    # Refresh access token using base function
    return refresh_access_token(
        token_url=TOKEN_URL,
        client_id=client_id,
        refresh_token=refresh_token,
        client_secret=client_secret,
    )


# =============================================================================
# End of File - SkillForge Project
# =============================================================================
# Project : SkillForge - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
