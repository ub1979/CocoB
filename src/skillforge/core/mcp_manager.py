# =============================================================================
# mcp_manager.py - MCP server manager for chat-based management
# =============================================================================

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.auth_manager import AuthManager

logger = logging.getLogger("mcp_manager")

# Verified safe MCP servers
VERIFIED_SERVERS = {
    "@playwright/mcp": {
        "name": "Playwright",
        "description": "Browser automation - search, browse, fill forms",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
        "verified": True,
        "downloads": 50000,
        "category": "browser"
    },
    "@modelcontextprotocol/server-filesystem": {
        "name": "Filesystem",
        "description": "Read/write files on your computer",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem@latest"],
        "verified": True,
        "downloads": 25000,
        "category": "files"
    },
    "@modelcontextprotocol/server-github": {
        "name": "GitHub",
        "description": "Search repositories, read code, create issues",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github@latest"],
        "verified": True,
        "downloads": 15000,
        "category": "developer"
    },
    "@composio/gmail": {
        "name": "Gmail",
        "description": "Send and read emails via Gmail",
        "command": "npx",
        "args": ["-y", "@composio/gmail@latest"],
        "verified": True,
        "downloads": 12000,
        "category": "email"
    },
    "@composio/calendar": {
        "name": "Google Calendar",
        "description": "Manage Google Calendar events",
        "command": "npx",
        "args": ["-y", "@composio/calendar@latest"],
        "verified": True,
        "downloads": 10000,
        "category": "calendar"
    },
}


@dataclass
class MCPServerStatus:
    """Status information for an MCP server"""
    name: str
    enabled: bool
    verified: bool
    last_used: Optional[str] = None
    error_count: int = 0


class MCPManager:
    """Manages MCP servers with security warnings and tiered authentication."""
    
    def __init__(self, project_root: Optional[Path] = None,
                 auth_manager: Optional["AuthManager"] = None):
        """Initialize MCP manager."""
        if project_root is None:
            from skillforge import PROJECT_ROOT
            self._project_root = Path(PROJECT_ROOT)
        else:
            self._project_root = Path(project_root)
        
        self._config_file = self._project_root / "mcp_config.json"
        self._auth_manager = auth_manager
        self._pending_installs: Dict[str, Dict[str, Any]] = {}
    
    def _load_config(self) -> Dict[str, Any]:
        """Load MCP configuration from file"""
        if not self._config_file.exists():
            return {"mcpServers": {}}
        
        try:
            with open(self._config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load MCP config: {e}")
            return {"mcpServers": {}}
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Save MCP configuration to file"""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Failed to save MCP config: {e}")
            return False
    
    def list_servers(self) -> List[MCPServerStatus]:
        """List all configured MCP servers and their status."""
        config = self._load_config()
        servers = []
        
        for name, server_config in config.get("mcpServers", {}).items():
            args = server_config.get("args", [])
            # Check if any arg contains a verified package name
            verified = any(
                verified_pkg in arg for arg in args 
                for verified_pkg in VERIFIED_SERVERS
            )
            
            status = MCPServerStatus(
                name=name,
                enabled=server_config.get("enabled", True),
                verified=verified
            )
            servers.append(status)
        
        return servers
    
    def format_server_list(self) -> str:
        """Format server list for display"""
        servers = self.list_servers()
        
        if not servers:
            return "No MCP servers configured. Use /mcp install <name> to add servers."
        
        lines = ["MCP Servers:", ""]
        
        for server in servers:
            status_icon = "ON" if server.enabled else "OFF"
            verified_icon = "V" if server.verified else "?"
            lines.append(f"[{status_icon}] {server.name} ({verified_icon})")
        
        lines.append("")
        lines.append("Use /mcp enable <name> or /mcp disable <name> to toggle")
        
        return "\n".join(lines)
    
    def enable_server(self, user_id: str, server_name: str) -> tuple:
        """Enable an MCP server. YELLOW level - PIN required."""
        if self._auth_manager:
            from skillforge.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False, "PIN required. Use /auth pin <pin> first."
        
        config = self._load_config()
        
        if server_name not in config.get("mcpServers", {}):
            return False, f"Server '{server_name}' not found."
        
        config["mcpServers"][server_name]["enabled"] = True
        
        if self._save_config(config):
            logger.info(f"Enabled MCP server: {server_name}")
            return True, f"Enabled '{server_name}'"
        else:
            return False, "Failed to save configuration."
    
    def disable_server(self, user_id: str, server_name: str) -> tuple:
        """Disable an MCP server. YELLOW level - PIN required."""
        if self._auth_manager:
            from skillforge.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.YELLOW)
            if not result.allowed:
                return False, "PIN required. Use /auth pin <pin> first."
        
        config = self._load_config()
        
        if server_name not in config.get("mcpServers", {}):
            return False, f"Server '{server_name}' not found."
        
        config["mcpServers"][server_name]["enabled"] = False
        
        if self._save_config(config):
            logger.info(f"Disabled MCP server: {server_name}")
            return True, f"Disabled '{server_name}'"
        else:
            return False, "Failed to save configuration."
    
    def get_verified_list(self) -> str:
        """Get list of verified servers for display"""
        lines = ["Verified MCP Servers:", ""]
        
        for package, info in VERIFIED_SERVERS.items():
            lines.append(f"* {info['name']} ({package})")
            lines.append(f"  {info['description']}")
            lines.append(f"  Users: {info['downloads']:,}")
            lines.append("")
        
        lines.append("Install with: /mcp install <package-name>")
        
        return "\n".join(lines)
    
    def request_install(self, user_id: str, package_name: str) -> str:
        """Request installation of an MCP server with warnings."""
        config = self._load_config()
        
        # Check if already installed
        for name, server in config.get("mcpServers", {}).items():
            if package_name in server.get("args", []):
                return f"'{package_name}' is already installed as '{name}'."
        
        # Check if verified
        if package_name in VERIFIED_SERVERS:
            info = VERIFIED_SERVERS[package_name]
            
            self._pending_installs[user_id] = {
                "package": package_name,
                "verified": True,
                "config": {
                    "command": info["command"],
                    "args": info["args"],
                    "enabled": True
                }
            }
            
            return f"""Install Verified MCP Server

✓ This server is VERIFIED by Idrak AI
Name: {info['name']}
Description: {info['description']}
Users: {info['downloads']:,}

This requires password confirmation (ORANGE level).
Type /mcp confirm after entering your password."""
        
        else:
            # Unknown server - show warnings
            self._pending_installs[user_id] = {
                "package": package_name,
                "verified": False,
                "config": {
                    "command": "npx",
                    "args": ["-y", package_name],
                    "enabled": True
                }
            }
            
            return f"""⚠️ UNKNOWN MCP SERVER

Package: {package_name}

SECURITY WARNINGS:
• NOT in verified list
• No security audit
• Could be malware
• Could steal your data
• Could delete your files

This requires password confirmation (ORANGE level).
Type the following to confirm you accept the risk:
/mcp confirm I understand the risk: {package_name}"""
    
    def confirm_install(self, user_id: str, confirmation_text: str = "") -> str:
        """Confirm and complete installation. ORANGE level."""
        if self._auth_manager:
            from skillforge.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.ORANGE)
            if not result.allowed:
                return "Password required. Use /auth password <password> first."
        
        if user_id not in self._pending_installs:
            return "No pending installation. Use /mcp install <package> first."
        
        pending = self._pending_installs[user_id]
        package = pending["package"]
        
        # For unverified servers, check confirmation text
        if not pending.get("verified", False):
            expected = f"I understand the risk: {package}"
            if confirmation_text.strip() != expected:
                return f"Confirmation text doesn't match.\nType: /mcp confirm I understand the risk: {package}"
        
        # Generate server name
        server_name = self._generate_server_name(package)
        
        # Add to config
        config = self._load_config()
        config["mcpServers"][server_name] = pending["config"]
        
        if self._save_config(config):
            del self._pending_installs[user_id]
            logger.info(f"Installed MCP server: {package} as {server_name}")
            return f"Successfully installed '{package}' as '{server_name}'!\n\nYou may need to restart SkillForge to use this server."
        else:
            return "Failed to save configuration."
    
    def cancel_install(self, user_id: str) -> str:
        """Cancel pending installation"""
        if user_id in self._pending_installs:
            package = self._pending_installs[user_id]["package"]
            del self._pending_installs[user_id]
            return f"Cancelled installation of '{package}'."
        return "No pending installation to cancel."
    
    def _generate_server_name(self, package_name: str) -> str:
        """Generate a short server name from package"""
        name = package_name.split("/")[-1] if "/" in package_name else package_name
        name = name.split("@")[0]
        name = name.replace("server-", "").replace("mcp-", "")
        
        config = self._load_config()
        base_name = name
        counter = 1
        
        while name in config.get("mcpServers", {}):
            name = f"{base_name}-{counter}"
            counter += 1
        
        return name
    
    def uninstall_server(self, user_id: str, server_name: str) -> str:
        """Uninstall an MCP server. ORANGE level."""
        if self._auth_manager:
            from skillforge.core.auth_manager import SecurityLevel
            result = self._auth_manager.check_access(user_id, SecurityLevel.ORANGE)
            if not result.allowed:
                return "Password required. Use /auth password <password> first."
        
        config = self._load_config()
        
        if server_name not in config.get("mcpServers", {}):
            return f"Server '{server_name}' not found."
        
        del config["mcpServers"][server_name]
        
        if self._save_config(config):
            logger.info(f"Uninstalled MCP server: {server_name}")
            return f"Uninstalled '{server_name}'"
        else:
            return "Failed to save configuration."
