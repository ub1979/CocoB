# =============================================================================
'''
    File Name : mcp_models.py

    Description : Data models for MCP (Model Context Protocol) server management.
                  Contains enums for server types and connection status, plus
                  dataclasses for server configuration.

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any


# =============================================================================
'''
    MCPServerType : Enum for supported MCP server transport types
'''
# =============================================================================

class MCPServerType(Enum):
    """Supported MCP server transport types"""
    STDIO = "stdio"      # Local subprocess stdin/stdout
    DOCKER = "docker"    # Docker container + STDIO
    SSE = "sse"          # Server-Sent Events HTTP
    HTTP = "http"        # Streamable HTTP


# =============================================================================
'''
    MCPConnectionStatus : Enum for MCP server connection states
'''
# =============================================================================

class MCPConnectionStatus(Enum):
    """MCP server connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


# =============================================================================
'''
    MCPServerConfig : Dataclass for MCP server configuration
'''
# =============================================================================

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""

    # ==================================
    # Required fields
    # ==================================
    name: str
    type: MCPServerType = MCPServerType.STDIO

    # ==================================
    # Optional metadata
    # ==================================
    enabled: bool = True
    description: str = ""

    # ==================================
    # STDIO/Docker specific fields
    # ==================================
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None

    # ==================================
    # SSE/HTTP specific fields
    # ==================================
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    # =============================================================================
    # =========================================================================
    # Function to_dict -> None to Dict[str, Any]
    # =========================================================================
    # =============================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for JSON serialization"""
        result = {
            "type": self.type.value,
            "enabled": self.enabled,
        }

        # ==================================
        # Add description if present
        # ==================================
        if self.description:
            result["description"] = self.description

        # ==================================
        # Add STDIO/Docker fields if present
        # ==================================
        if self.command:
            result["command"] = self.command
        if self.args:
            result["args"] = self.args
        if self.env:
            result["env"] = self.env

        # ==================================
        # Add SSE/HTTP fields if present
        # ==================================
        if self.url:
            result["url"] = self.url
        if self.headers:
            result["headers"] = self.headers

        return result

    # =============================================================================
    # =========================================================================
    # Function from_dict -> str, Dict[str, Any] to MCPServerConfig (classmethod)
    # =========================================================================
    # =============================================================================

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create config from dictionary (e.g., from JSON)"""
        # ==================================
        # Parse server type
        # ==================================
        type_str = data.get("type", "stdio")
        try:
            server_type = MCPServerType(type_str)
        except ValueError:
            server_type = MCPServerType.STDIO

        return cls(
            name=name,
            type=server_type,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            command=data.get("command"),
            args=data.get("args"),
            env=data.get("env"),
            url=data.get("url"),
            headers=data.get("headers"),
        )


# =============================================================================
'''
    MCPServerState : Runtime state for an MCP server
'''
# =============================================================================

@dataclass
class MCPServerState:
    """Runtime state for an MCP server"""
    config: MCPServerConfig
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    tools: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

    # =============================================================================
    # =========================================================================
    # Function get_status_display -> None to str
    # =========================================================================
    # =============================================================================

    def get_status_display(self) -> str:
        """Get status display string with emoji"""
        status_map = {
            MCPConnectionStatus.CONNECTED: "Connected",
            MCPConnectionStatus.CONNECTING: "Connecting...",
            MCPConnectionStatus.DISCONNECTED: "Disconnected",
            MCPConnectionStatus.ERROR: f"Error: {self.error_message or 'Unknown'}",
        }
        return status_map.get(self.status, "Unknown")

    # =============================================================================
    # =========================================================================
    # Function get_status_emoji -> None to str
    # =========================================================================
    # =============================================================================

    def get_status_emoji(self) -> str:
        """Get status emoji for display"""
        emoji_map = {
            MCPConnectionStatus.CONNECTED: "🟢",
            MCPConnectionStatus.CONNECTING: "🟡",
            MCPConnectionStatus.DISCONNECTED: "⚪",
            MCPConnectionStatus.ERROR: "🔴",
        }
        return emoji_map.get(self.status, "⚪")


# =============================================================================
'''
    Validation Functions : Helper functions for validating MCP configurations
'''
# =============================================================================

# =============================================================================
# =========================================================================
# Function validate_stdio_config -> MCPServerConfig to Tuple[bool, str]
# =========================================================================
# =============================================================================

def validate_stdio_config(config: MCPServerConfig) -> tuple[bool, str]:
    """Validate STDIO server configuration"""
    if not config.command:
        return False, "Command is required for STDIO servers"
    return True, "Valid"


# =============================================================================
# =========================================================================
# Function validate_docker_config -> MCPServerConfig to Tuple[bool, str]
# =========================================================================
# =============================================================================

def validate_docker_config(config: MCPServerConfig) -> tuple[bool, str]:
    """Validate Docker server configuration"""
    if not config.command:
        return False, "Command is required for Docker servers"

    args = config.args or []

    # ==================================
    # Check for detach flag (not allowed)
    # ==================================
    if "-d" in args or "--detach" in args:
        return False, "Docker MCP servers must NOT use -d/--detach flag (must run in foreground)"

    # ==================================
    # Check for interactive flag (required)
    # ==================================
    if "-i" not in args and "--interactive" not in args:
        return False, "Docker MCP servers require -i/--interactive flag for stdin"

    return True, "Valid"


# =============================================================================
# =========================================================================
# Function validate_sse_config -> MCPServerConfig to Tuple[bool, str]
# =========================================================================
# =============================================================================

def validate_sse_config(config: MCPServerConfig) -> tuple[bool, str]:
    """Validate SSE server configuration"""
    if not config.url:
        return False, "URL is required for SSE servers"

    # ==================================
    # Basic URL validation
    # ==================================
    if not config.url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    return True, "Valid"


# =============================================================================
# =========================================================================
# Function validate_http_config -> MCPServerConfig to Tuple[bool, str]
# =========================================================================
# =============================================================================

def validate_http_config(config: MCPServerConfig) -> tuple[bool, str]:
    """Validate HTTP server configuration"""
    if not config.url:
        return False, "URL is required for HTTP servers"

    # ==================================
    # Basic URL validation
    # ==================================
    if not config.url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    return True, "Valid"


# =============================================================================
# =========================================================================
# Function validate_config -> MCPServerConfig to Tuple[bool, str]
# =========================================================================
# =============================================================================

def validate_config(config: MCPServerConfig) -> tuple[bool, str]:
    """Validate MCP server configuration based on its type"""
    validators = {
        MCPServerType.STDIO: validate_stdio_config,
        MCPServerType.DOCKER: validate_docker_config,
        MCPServerType.SSE: validate_sse_config,
        MCPServerType.HTTP: validate_http_config,
    }

    validator = validators.get(config.type)
    if validator:
        return validator(config)

    return False, f"Unknown server type: {config.type}"


# =============================================================================
# End of File - SkillForge MCP Models
# =============================================================================
# Project   : SkillForge - Persistent Memory AI Chatbot
# License   : Open Source - Safe Open Community Project
# Done by   : Syed Usama Bukhari & Idrak AI Ltd Team
# Mission   : Making AI Useful for Everyone
# =============================================================================
