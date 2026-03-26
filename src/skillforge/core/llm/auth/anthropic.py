# =============================================================================
'''
    File Name : anthropic.py
    
    Description : Anthropic Claude OAuth authentication provider for SkillForge.
                  Handles OAuth2 flow for users with Claude Pro/Max subscriptions
                  who want to use their subscription via the API without separate
                  billing. Credentials are extracted from the installed Claude
                  Code CLI.
    
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

# OAuth endpoints for Anthropic authentication
AUTH_URL = "https://claude.ai/oauth/authorize"  # For subscription users
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"  # Correct token endpoint
REDIRECT_URI = "http://localhost:{port}/callback"  # Port will be dynamically assigned
CALLBACK_PORT = 0  # 0 = auto-find available port

# API endpoint for authenticated requests
API_URL = "https://api.anthropic.com"

# Scopes required for Claude API access (matching Claude Code)
SCOPES = [
    "org:create_api_key",     # Required for API key generation
    "user:profile",           # Profile information
    "user:inference",         # Required for API calls
]

# Default client IDs (extracted from Claude Code)
# These are public OAuth client IDs used by Claude Code
# The second one appears to be for subscription/consumer auth
DEFAULT_CLIENT_IDS = [
    "22422756-60c9-4084-8eb7-27705fd5cf9a",  # Consumer OAuth client
    "9d1c250a-e61b-44d9-88ed-5944d1962f5e",  # CLI OAuth client
]

# Provider name for credential storage
PROVIDER_NAME = "anthropic"


# =============================================================================
# =========================================================================
# Function find_cli -> None to Optional[Path]
# =========================================================================
# =============================================================================

def find_cli() -> Optional[Path]:
    """
    Find the Claude Code CLI binary in PATH.

    Returns:
        Path to claude binary, or None if not found
    """
    # ==================================
    # Iterate through PATH directories
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        # ==================================
        # Check for both Unix and Windows binary names
        for name in ["claude", "claude.cmd"]:
            path = Path(dir_path) / name
            # ==================================
            # Return resolved path if binary exists
            if path.exists():
                return path.resolve()
    return None


# =============================================================================
# =========================================================================
# Function extract_credentials -> None to Optional[Tuple[str, Optional[str]]]
# =========================================================================
# =============================================================================

def extract_credentials() -> Optional[Tuple[str, Optional[str]]]:
    """
    Extract OAuth credentials from the installed Claude Code CLI.

    Claude Code contains embedded OAuth client credentials.
    Note: Claude uses public OAuth clients, so there's no client secret.

    Returns:
        Tuple of (client_id, None), or None if not found
    """
    # ==================================
    # Locate the CLI binary
    claude_path = find_cli()
    # ==================================
    # Return None if CLI not found
    if not claude_path:
        return None

    cli_dir = claude_path.parent.parent

    # Search for the CLI bundle in possible locations
    search_paths = [
        cli_dir / "lib/node_modules/@anthropic-ai/claude-code/cli.js",
        cli_dir / "node_modules/@anthropic-ai/claude-code/cli.js",
        # Global npm locations
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
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
    # Use default client ID if CLI bundle not found
    if not content:
        return DEFAULT_CLIENT_IDS[0], None

    # Extract client ID using regex pattern (UUID format)
    # Look for CLIENT_ID:"uuid" pattern
    id_match = re.search(r'CLIENT_ID:"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', content)

    # ==================================
    # Return extracted client ID if found
    if id_match:
        return id_match.group(1), None

    # Fallback to default
    return DEFAULT_CLIENT_IDS[0], None


# =============================================================================
# =========================================================================
# Function get_credentials -> None to Tuple[str, Optional[str]]
# =========================================================================
# =============================================================================

def get_credentials() -> Tuple[str, Optional[str]]:
    """
    Get OAuth credentials from environment or Claude Code CLI.

    Priority:
    1. Environment variables (ANTHROPIC_OAUTH_CLIENT_ID)
    2. Extracted from installed Claude Code CLI
    3. Default public client ID

    Returns:
        Tuple of (client_id, client_secret)
        Note: client_secret is typically None for Anthropic (public client)
    """
    # ==================================
    # Check environment variables first (user override)
    client_id = os.environ.get("ANTHROPIC_OAUTH_CLIENT_ID")
    # ==================================
    # Return environment variable if set
    if client_id:
        return client_id, None

    # Try extracting from Claude Code CLI
    extracted = extract_credentials()
    # ==================================
    # Return extracted credentials if available
    if extracted:
        return extracted

    # Fallback to default public client ID
    return DEFAULT_CLIENT_IDS[0], None


# =============================================================================
# =========================================================================
# Function login -> None to dict
# =========================================================================
# =============================================================================

def login() -> dict:
    """
    Run the Anthropic OAuth flow and return tokens.

    Opens a browser for the user to log in with their Anthropic account,
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
    # Execute OAuth flow with Anthropic endpoints
    return run_oauth_flow(
        auth_url=AUTH_URL,
        token_url=TOKEN_URL,
        redirect_uri=REDIRECT_URI,
        client_id=client_id,
        scopes=SCOPES,
        client_secret=client_secret,
        port=CALLBACK_PORT,
        provider_name="Anthropic Claude",
        extra_auth_params={
            "prompt": "consent",  # Force consent screen
        },
    )


# =============================================================================
# =========================================================================
# Function refresh -> str to dict
# =========================================================================
# =============================================================================

def refresh(refresh_token: str) -> dict:
    """
    Refresh Anthropic access token.

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
