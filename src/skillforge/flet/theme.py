"""
Theme constants, color palette, and utility functions for the Flet UI.
"""

import subprocess
from datetime import datetime
from typing import Tuple

import requests


# =============================================================================
# PROVIDER CATEGORIES
# =============================================================================

LOCAL_SERVER_PROVIDERS = {
    "ollama": {"port": 11434, "health_url": "http://localhost:11434/api/tags",
               "start_cmd": "ollama serve", "desc": "Local LLM server"},
    "vllm": {"port": 8000, "health_url": "http://localhost:8000/v1/models",
             "start_cmd": "python -m vllm.entrypoints.openai.api_server --model <model>", "desc": "High-throughput inference"},
    "lmstudio": {"port": 1234, "health_url": "http://localhost:1234/v1/models",
                 "start_cmd": "Start LM Studio and enable server", "desc": "LM Studio local server"},
    "mlx": {"port": 8080, "health_url": "http://localhost:8080/v1/models",
            "start_cmd": "python -m mlx_lm.server --model <model> --port 8080", "desc": "Apple Silicon optimized"},
}

CLI_PROVIDERS = {
    "claude-cli": {"cmd": "claude", "desc": "Anthropic Claude Code CLI", "install": "npm install -g @anthropic-ai/claude-code"},
    "gemini-cli": {"cmd": "gemini", "desc": "Google Gemini CLI", "install": "npm install -g @google/gemini-cli"},
}

CLOUD_API_PROVIDERS = ["openai", "anthropic", "groq", "groq-large", "together", "azure", "kimi", "kimi_auth", "gemini", "gemini-vertex", "azure-cli"]

OAUTH_PROVIDERS = ["anthropic-oauth", "gemini-oauth"]

API_KEY_ENV_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "groq-large": "GROQ_API_KEY",
    "together": "TOGETHER_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "kimi_auth": "KIMI_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
}


# =============================================================================
# SPACING CONSTANTS
# =============================================================================

class Spacing:
    """Standard spacing constants."""
    XS = 4
    SM = 8
    MD = 16
    LG = 24
    XL = 32


# =============================================================================
# COLOR PALETTE
# =============================================================================

class AppColors:
    """App color scheme — single accent, neutral surfaces, clear hierarchy.

    Design principles:
    - ONE accent color (indigo #6366F1) for all interactive elements
    - Neutral gray surfaces (no blue tint in dark mode)
    - 3-tier surface depth: BACKGROUND < SURFACE < SURFACE_ELEVATED
    - PRIMARY = ACCENT (unified brand color)
    """
    # --- Brand (single accent — indigo) ---
    PRIMARY = "#6366F1"
    PRIMARY_LIGHT = "#818CF8"
    SECONDARY = "#6366F1"       # Unified — no competing gold
    SECONDARY_LIGHT = "#818CF8"
    ACCENT = "#6366F1"
    ACCENT_LIGHT = "#818CF8"
    # --- Surfaces (light: 3-tier depth) ---
    BACKGROUND = "#F5F5F5"
    SURFACE = "#FFFFFF"
    SURFACE_VARIANT = "#F0F0F0"
    SURFACE_ELEVATED = "#FAFAFA"
    # --- Semantic (blue/coral/rose — zero green, zero yellow) ---
    SUCCESS = "#0EA5E9"
    SUCCESS_LIGHT = "#F0F9FF"
    WARNING = "#EA580C"
    WARNING_LIGHT = "#FFF7ED"
    ERROR = "#BE123C"
    ERROR_LIGHT = "#FFF1F2"
    INFO = "#6366F1"
    INFO_LIGHT = "#EEF2FF"
    # --- Typography ---
    TEXT_PRIMARY = "#111111"
    TEXT_SECONDARY = "#6B7280"
    TEXT_MUTED = "#9CA3AF"
    TEXT_ON_PRIMARY = "#FFFFFF"
    # --- Structure ---
    BORDER = "#E5E7EB"
    DIVIDER = "#D1D5DB"

    _DARK = {
        "PRIMARY": "#818CF8",
        "PRIMARY_LIGHT": "#A5B4FC",
        "SECONDARY": "#818CF8",
        "SECONDARY_LIGHT": "#A5B4FC",
        "ACCENT": "#818CF8",
        "ACCENT_LIGHT": "#A5B4FC",
        "BACKGROUND": "#111111",
        "SURFACE": "#1A1A1A",
        "SURFACE_VARIANT": "#222222",
        "SURFACE_ELEVATED": "#252525",
        "SUCCESS": "#38BDF8",
        "SUCCESS_LIGHT": "#0C4A6E",
        "WARNING": "#FB923C",
        "WARNING_LIGHT": "#431407",
        "ERROR": "#FB7185",
        "ERROR_LIGHT": "#4C0519",
        "INFO": "#A5B4FC",
        "INFO_LIGHT": "#1E1B4B",
        "TEXT_PRIMARY": "#F5F5F5",
        "TEXT_SECONDARY": "#A1A1AA",
        "TEXT_MUTED": "#71717A",
        "TEXT_ON_PRIMARY": "#FFFFFF",
        "BORDER": "#2E2E2E",
        "DIVIDER": "#3F3F3F",
    }

    _LIGHT = {
        "PRIMARY": "#6366F1",
        "PRIMARY_LIGHT": "#818CF8",
        "SECONDARY": "#6366F1",
        "SECONDARY_LIGHT": "#818CF8",
        "ACCENT": "#6366F1",
        "ACCENT_LIGHT": "#818CF8",
        "BACKGROUND": "#F5F5F5",
        "SURFACE": "#FFFFFF",
        "SURFACE_VARIANT": "#F0F0F0",
        "SURFACE_ELEVATED": "#FAFAFA",
        "SUCCESS": "#0EA5E9",
        "SUCCESS_LIGHT": "#F0F9FF",
        "WARNING": "#EA580C",
        "WARNING_LIGHT": "#FFF7ED",
        "ERROR": "#BE123C",
        "ERROR_LIGHT": "#FFF1F2",
        "INFO": "#6366F1",
        "INFO_LIGHT": "#EEF2FF",
        "TEXT_PRIMARY": "#111111",
        "TEXT_SECONDARY": "#6B7280",
        "TEXT_MUTED": "#9CA3AF",
        "TEXT_ON_PRIMARY": "#FFFFFF",
        "BORDER": "#E5E7EB",
        "DIVIDER": "#D1D5DB",
    }

    _is_dark = False
    _secure_storage = None

    @classmethod
    def set_secure_storage(cls, storage):
        """Set the storage instance for persisting theme preference."""
        cls._secure_storage = storage

    @classmethod
    def set_dark_mode(cls, enabled: bool):
        """Switch between light and dark mode."""
        cls._is_dark = enabled
        theme = cls._DARK if enabled else cls._LIGHT
        for key, value in theme.items():
            setattr(cls, key, value)
        if cls._secure_storage:
            try:
                cls._secure_storage.set_setting('dark_mode', enabled)
            except Exception:
                pass

    @classmethod
    def load_saved_mode(cls):
        """Load saved dark mode preference on startup (defaults to dark mode)."""
        if cls._secure_storage:
            try:
                is_dark = cls._secure_storage.get_setting('dark_mode', True)
                cls.set_dark_mode(is_dark)
                return
            except Exception:
                pass
        cls.set_dark_mode(True)

    @classmethod
    def is_dark_mode(cls) -> bool:
        return cls._is_dark


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def check_local_server_status(provider_name: str) -> Tuple[bool, str]:
    """Check if a local LLM server is running."""
    if provider_name not in LOCAL_SERVER_PROVIDERS:
        return False, "Not a local server provider"

    server_info = LOCAL_SERVER_PROVIDERS[provider_name]
    try:
        response = requests.get(server_info["health_url"], timeout=2)
        if response.status_code == 200:
            return True, f"Running on port {server_info['port']}"
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"Not running (port {server_info['port']})"
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"


def check_cli_installed(cli_name: str) -> Tuple[bool, str]:
    """Check if a CLI tool is installed."""
    if cli_name not in CLI_PROVIDERS:
        return False, "Unknown CLI provider"

    cmd = CLI_PROVIDERS[cli_name]["cmd"]
    try:
        result = subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return True, "Installed"
        return False, "Not installed"
    except FileNotFoundError:
        return False, "Not installed"
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"


def format_timestamp(ts: float) -> str:
    """Format timestamp for display."""
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
