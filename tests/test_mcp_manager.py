# =============================================================================
# test_mcp_manager.py - Tests for MCP manager
# =============================================================================

import pytest
import tempfile
import json
from pathlib import Path


class TestMCPManagerInitialization:
    """Test MCPManager initialization."""

    def test_initialization(self):
        """Should initialize with empty state."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            assert len(manager._pending_installs) == 0

    def test_creates_config_file(self):
        """Should handle missing config file."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            config = manager._load_config()
            assert "mcpServers" in config


class TestListServers:
    """Test listing MCP servers."""

    def test_list_empty(self):
        """Should return empty list when no servers."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            servers = manager.list_servers()
            assert len(servers) == 0

    def test_list_servers(self):
        """Should return list of servers."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            # Create a mock config
            config = {
                "mcpServers": {
                    "playwright": {
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "enabled": True
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            servers = manager.list_servers()
            
            assert len(servers) == 1
            assert servers[0].name == "playwright"
            assert servers[0].enabled is True
            assert servers[0].verified is True  # @playwright/mcp@latest contains @playwright/mcp

    def test_format_server_list_empty(self):
        """Should format empty server list."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            text = manager.format_server_list()
            
            assert "No MCP servers" in text

    def test_format_server_list(self):
        """Should format server list."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            config = {
                "mcpServers": {
                    "playwright": {
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "enabled": True
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            text = manager.format_server_list()
            
            assert "playwright" in text
            assert "ON" in text


class TestEnableDisable:
    """Test enabling and disabling servers."""

    def test_enable_server(self):
        """Should enable a server."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            # Create disabled server
            config = {
                "mcpServers": {
                    "test": {
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "enabled": False
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            success, msg = manager.enable_server("user1", "test")
            
            assert success is True
            assert "Enabled" in msg
            
            # Verify in config
            new_config = manager._load_config()
            assert new_config["mcpServers"]["test"]["enabled"] is True

    def test_disable_server(self):
        """Should disable a server."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            # Create enabled server
            config = {
                "mcpServers": {
                    "test": {
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "enabled": True
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            success, msg = manager.disable_server("user1", "test")
            
            assert success is True
            assert "Disabled" in msg
            
            # Verify in config
            new_config = manager._load_config()
            assert new_config["mcpServers"]["test"]["enabled"] is False

    def test_enable_server_not_found(self):
        """Should fail for non-existent server."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            success, msg = manager.enable_server("user1", "nonexistent")
            
            assert success is False
            assert "not found" in msg


class TestInstallVerified:
    """Test installing verified servers."""

    def test_request_install_verified(self):
        """Should show verified message for verified server."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            msg = manager.request_install("user1", "@playwright/mcp")
            
            assert "VERIFIED" in msg
            assert "Playwright" in msg
            assert "password" in msg.lower()

    def test_request_install_unknown(self):
        """Should show warnings for unknown server."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            msg = manager.request_install("user1", "some-random-package")
            
            assert "UNKNOWN" in msg
            assert "WARNING" in msg or "warning" in msg.lower()
            assert "malware" in msg.lower()

    def test_request_install_already_installed(self):
        """Should detect already installed packages."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            # Pre-install
            config = {
                "mcpServers": {
                    "playwright": {
                        "command": "npx",
                        "args": ["-y", "@playwright/mcp@latest"],
                        "enabled": True
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            msg = manager.request_install("user1", "@playwright/mcp@latest")
            
            assert "already installed" in msg.lower()


class TestConfirmInstall:
    """Test confirming installations."""

    def test_confirm_no_pending(self):
        """Should fail if no pending install."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            msg = manager.confirm_install("user1")
            
            assert "No pending" in msg

    def test_confirm_verified(self):
        """Should install verified server without confirmation text."""
        from skillforge.core.mcp_manager import MCPManager
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            proj_dir = Path(tmpdir) / "proj"
            proj_dir.mkdir()
            
            auth = AuthManager(data_dir=auth_dir)
            auth.setup_password("testpass")
            auth.authenticate_password("user1", "testpass")
            
            manager = MCPManager(project_root=proj_dir, auth_manager=auth)
            
            # Queue verified install
            manager.request_install("user1", "@playwright/mcp")
            
            msg = manager.confirm_install("user1")
            
            assert "Successfully installed" in msg
            
            # Verify in config (name might be 'mcp' from @playwright/mcp)
            config = manager._load_config()
            assert len(config["mcpServers"]) == 1

    def test_confirm_unknown_wrong_text(self):
        """Should fail if confirmation text doesn't match."""
        from skillforge.core.mcp_manager import MCPManager
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            proj_dir = Path(tmpdir) / "proj"
            proj_dir.mkdir()
            
            auth = AuthManager(data_dir=auth_dir)
            auth.setup_password("testpass")
            auth.authenticate_password("user1", "testpass")
            
            manager = MCPManager(project_root=proj_dir, auth_manager=auth)
            
            # Queue unknown install
            manager.request_install("user1", "some-package")
            
            msg = manager.confirm_install("user1", "wrong text")
            
            assert "doesn't match" in msg

    def test_confirm_unknown_correct_text(self):
        """Should install unknown server with correct confirmation."""
        from skillforge.core.mcp_manager import MCPManager
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            proj_dir = Path(tmpdir) / "proj"
            proj_dir.mkdir()
            
            auth = AuthManager(data_dir=auth_dir)
            auth.setup_password("testpass")
            auth.authenticate_password("user1", "testpass")
            
            manager = MCPManager(project_root=proj_dir, auth_manager=auth)
            
            # Queue unknown install
            manager.request_install("user1", "some-package")
            
            msg = manager.confirm_install("user1", "I understand the risk: some-package")
            
            assert "Successfully installed" in msg


class TestCancelInstall:
    """Test cancelling installations."""

    def test_cancel_pending(self):
        """Should cancel pending installation."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            # Queue install
            manager.request_install("user1", "@playwright/mcp")
            
            msg = manager.cancel_install("user1")
            
            assert "Cancelled" in msg
            assert "user1" not in manager._pending_installs

    def test_cancel_nothing_pending(self):
        """Should handle no pending install."""
        from skillforge.core.mcp_manager import MCPManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            msg = manager.cancel_install("user1")
            
            assert "No pending" in msg


class TestUninstall:
    """Test uninstalling servers."""

    def test_uninstall_server(self):
        """Should uninstall a server."""
        from skillforge.core.mcp_manager import MCPManager
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            proj_dir = Path(tmpdir) / "proj"
            proj_dir.mkdir()
            
            auth = AuthManager(data_dir=auth_dir)
            auth.setup_password("testpass")
            auth.authenticate_password("user1", "testpass")
            
            manager = MCPManager(project_root=proj_dir, auth_manager=auth)
            
            # Create server
            config = {
                "mcpServers": {
                    "test": {
                        "command": "npx",
                        "args": ["-y", "test"],
                        "enabled": True
                    }
                }
            }
            
            with open(manager._config_file, 'w') as f:
                json.dump(config, f)
            
            msg = manager.uninstall_server("user1", "test")
            
            assert "Uninstalled" in msg
            
            # Verify removed
            new_config = manager._load_config()
            assert "test" not in new_config["mcpServers"]

    def test_uninstall_not_found(self):
        """Should fail for non-existent server."""
        from skillforge.core.mcp_manager import MCPManager
        from skillforge.core.auth_manager import AuthManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_dir = Path(tmpdir) / "auth"
            proj_dir = Path(tmpdir) / "proj"
            proj_dir.mkdir()
            
            auth = AuthManager(data_dir=auth_dir)
            auth.setup_password("testpass")
            auth.authenticate_password("user1", "testpass")
            
            manager = MCPManager(project_root=proj_dir, auth_manager=auth)
            
            msg = manager.uninstall_server("user1", "nonexistent")
            
            assert "not found" in msg


class TestVerifiedList:
    """Test verified server list."""

    def test_get_verified_list(self):
        """Should return formatted verified list."""
        from skillforge.core.mcp_manager import MCPManager, VERIFIED_SERVERS
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MCPManager(project_root=tmpdir)
            
            text = manager.get_verified_list()
            
            assert "Verified MCP Servers" in text
            assert "@playwright/mcp" in text
            assert "Install with" in text
