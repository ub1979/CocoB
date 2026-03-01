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
    """App color scheme - light mode (default)."""
    PRIMARY = "#1A365D"
    PRIMARY_LIGHT = "#2C5282"
    SECONDARY = "#C9A227"
    SECONDARY_LIGHT = "#D4B43A"
    BACKGROUND = "#F7FAFC"
    SURFACE = "#FFFFFF"
    SURFACE_VARIANT = "#EDF2F7"
    SUCCESS = "#38A169"
    SUCCESS_LIGHT = "#C6F6D5"
    WARNING = "#D69E2E"
    WARNING_LIGHT = "#FEFCBF"
    ERROR = "#E53E3E"
    ERROR_LIGHT = "#FED7D7"
    INFO = "#3182CE"
    INFO_LIGHT = "#BEE3F8"
    TEXT_PRIMARY = "#2D3748"
    TEXT_SECONDARY = "#718096"
    TEXT_MUTED = "#A0AEC0"
    TEXT_ON_PRIMARY = "#FFFFFF"
    BORDER = "#E2E8F0"

    _DARK = {
        "PRIMARY": "#4A90D9",
        "PRIMARY_LIGHT": "#63A4E8",
        "SECONDARY": "#D4B43A",
        "SECONDARY_LIGHT": "#E5C84D",
        "BACKGROUND": "#1A1A2E",
        "SURFACE": "#16213E",
        "SURFACE_VARIANT": "#1F2B47",
        "SUCCESS": "#48BB78",
        "SUCCESS_LIGHT": "#276749",
        "WARNING": "#ECC94B",
        "WARNING_LIGHT": "#744210",
        "ERROR": "#FC8181",
        "ERROR_LIGHT": "#742A2A",
        "INFO": "#63B3ED",
        "INFO_LIGHT": "#2A4365",
        "TEXT_PRIMARY": "#E2E8F0",
        "TEXT_SECONDARY": "#A0AEC0",
        "TEXT_MUTED": "#718096",
        "TEXT_ON_PRIMARY": "#FFFFFF",
        "BORDER": "#2D3748",
    }

    _LIGHT = {
        "PRIMARY": "#1A365D",
        "PRIMARY_LIGHT": "#2C5282",
        "SECONDARY": "#C9A227",
        "SECONDARY_LIGHT": "#D4B43A",
        "BACKGROUND": "#F7FAFC",
        "SURFACE": "#FFFFFF",
        "SURFACE_VARIANT": "#EDF2F7",
        "SUCCESS": "#38A169",
        "SUCCESS_LIGHT": "#C6F6D5",
        "WARNING": "#D69E2E",
        "WARNING_LIGHT": "#FEFCBF",
        "ERROR": "#E53E3E",
        "ERROR_LIGHT": "#FED7D7",
        "INFO": "#3182CE",
        "INFO_LIGHT": "#BEE3F8",
        "TEXT_PRIMARY": "#2D3748",
        "TEXT_SECONDARY": "#718096",
        "TEXT_MUTED": "#A0AEC0",
        "TEXT_ON_PRIMARY": "#FFFFFF",
        "BORDER": "#E2E8F0",
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
