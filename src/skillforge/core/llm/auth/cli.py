# =============================================================================
'''
    File Name : cli.py
    
    Description : Command-line interface for OAuth login operations.
                  Provides commands for login, status checking, and logout
                  for supported LLM providers (Gemini and Anthropic).
                  
                  Usage:
                      python -m core.llm.auth login gemini
                      python -m core.llm.auth login anthropic
                      python -m core.llm.auth status
                      python -m core.llm.auth logout gemini
                      python -m core.llm.auth logout anthropic
    
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

import argparse
import sys
from datetime import datetime

from .credentials import (
    save_credentials,
    delete_credentials,
    get_token_info,
    CREDENTIALS_FILE,
)

# =============================================================================
# Configuration
# =============================================================================

# Supported providers
SUPPORTED_PROVIDERS = ["gemini", "anthropic"]


# =============================================================================
# =========================================================================
# Function cmd_login -> str to int (handles login command for a provider)
# =========================================================================
# =============================================================================

def cmd_login(provider: str) -> int:
    """
    Login to a provider via OAuth.

    Args:
        provider: Provider name

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # ==================================
    if provider not in SUPPORTED_PROVIDERS:
        print(f"Error: Unknown provider '{provider}'")
        print(f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}")
        return 1

    print(f"Logging in to {provider}...")

    try:
        # Import provider-specific module
        # ==================================
        if provider == "gemini":
            from . import gemini
            tokens = gemini.login()
        # ==================================
        elif provider == "anthropic":
            from . import anthropic
            tokens = anthropic.login()

        # Save tokens
        save_credentials(provider, tokens)

        print(f"\n✓ Logged in successfully!")
        print(f"  Credentials saved to: {CREDENTIALS_FILE}")

        return 0

    except ValueError as e:
        print(f"\nError: {e}")
        return 1
    except Exception as e:
        print(f"\nError during login: {e}")
        return 1


# =============================================================================
# =========================================================================
# Function cmd_status -> None to int (shows login status for all providers)
# =========================================================================
# =============================================================================

def cmd_status() -> int:
    """
    Show login status for all providers.

    Returns:
        Exit code (always 0)
    """
    print("OAuth Login Status")
    print("=" * 50)

    # Check for CLIs
    from . import gemini as gemini_auth
    from . import anthropic as anthropic_auth

    gemini_cli = gemini_auth.find_cli()
    claude_cli = anthropic_auth.find_cli()

    print("\nCLI Tools:")
    # ==================================
    if gemini_cli:
        print(f"  Gemini CLI:  ✓ Found at {gemini_cli}")
    else:
        print("  Gemini CLI:  ✗ Not installed")
        print("               Install: npm install -g @google/gemini-cli")

    # ==================================
    if claude_cli:
        print(f"  Claude Code: ✓ Found at {claude_cli}")
    else:
        print("  Claude Code: ✗ Not installed")
        print("               Install: npm install -g @anthropic-ai/claude-code")

    print("\nLogin Status:")
    # ==================================
    for provider in SUPPORTED_PROVIDERS:
        info = get_token_info(provider)

        # ==================================
        if info is None:
            print(f"  {provider}: ✗ Not logged in")
            print(f"    Run: python -m core.llm.auth login {provider}")
        else:
            status = "✓ Logged in"

            # ==================================
            if info["expired"]:
                # ==================================
                if info["has_refresh_token"]:
                    status += " (token expired, will auto-refresh)"
                else:
                    status += " (token expired, re-login required)"

            print(f"  {provider}: {status}")

            # ==================================
            if info["expires_at"]:
                expires = datetime.fromtimestamp(info["expires_at"])
                print(f"    Token expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}")

    print(f"\nCredentials file: {CREDENTIALS_FILE}")

    return 0


# =============================================================================
# =========================================================================
# Function cmd_logout -> str to int (handles logout command for a provider)
# =========================================================================
# =============================================================================

def cmd_logout(provider: str) -> int:
    """
    Logout from a provider (delete stored credentials).

    Args:
        provider: Provider name

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # ==================================
    if provider not in SUPPORTED_PROVIDERS:
        print(f"Error: Unknown provider '{provider}'")
        print(f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}")
        return 1

    # ==================================
    if delete_credentials(provider):
        print(f"✓ Logged out from {provider}")
        return 0
    else:
        print(f"Not logged in to {provider}")
        return 1


# =============================================================================
# =========================================================================
# Function main -> None to int (main entry point for the CLI)
# =========================================================================
# =============================================================================

def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m core.llm.auth",
        description="OAuth authentication for LLM providers"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # login command
    login_parser = subparsers.add_parser(
        "login",
        help="Login to a provider via OAuth"
    )
    login_parser.add_argument(
        "provider",
        choices=SUPPORTED_PROVIDERS,
        help="Provider to login to"
    )

    # status command
    subparsers.add_parser(
        "status",
        help="Show login status for all providers"
    )

    # logout command
    logout_parser = subparsers.add_parser(
        "logout",
        help="Logout from a provider"
    )
    logout_parser.add_argument(
        "provider",
        choices=SUPPORTED_PROVIDERS,
        help="Provider to logout from"
    )

    args = parser.parse_args()

    # ==================================
    if args.command == "login":
        return cmd_login(args.provider)
    # ==================================
    elif args.command == "status":
        return cmd_status()
    # ==================================
    elif args.command == "logout":
        return cmd_logout(args.provider)
    else:
        parser.print_help()
        return 0


# =============================================================================
# Entry Point
# =============================================================================

# ==================================
if __name__ == "__main__":
    sys.exit(main())


# =============================================================================
# End of File - SkillForge OAuth CLI Module
# =============================================================================
