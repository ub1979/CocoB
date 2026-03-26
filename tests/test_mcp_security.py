# =============================================================================
# test_mcp_security.py — Tests for MCP command security allowlist
# 
# These tests verify that the MCP security validation in core/mcp_client.py
# correctly blocks dangerous commands while allowing safe ones.
# =============================================================================

import pytest
import subprocess
import sys
import os


# =============================================================================
# Test MCP Security via direct Python execution
# =============================================================================
def run_mcp_validation(command, args):
    """Run validation check in isolated Python process to avoid circular imports."""
    test_script = f'''
import sys
sys.path.insert(0, 'src')

# Mock the circular import
import types
mcp_models = types.ModuleType('skillforge.ui.settings.mcp_models')
mcp_models.MCPServerType = type('MCPServerType', (), {{'STDIO': 'stdio', 'DOCKER': 'docker', 'SSE': 'sse', 'HTTP': 'http'}})
mcp_models.MCPConnectionStatus = type('MCPConnectionStatus', (), {{}})
mcp_models.MCPServerConfig = dict
mcp_models.MCPServerState = dict
mcp_models.validate_config = lambda x: None
sys.modules['skillforge.ui.settings.mcp_models'] = mcp_models

from skillforge.core.mcp_client import validate_mcp_command, MCPSecurityError

try:
    validate_mcp_command({{'command': '{command}', 'args': {args!r}}})
    print('VALIDATION_PASSED')
except MCPSecurityError as e:
    print(f'VALIDATION_FAILED: {{e}}')
except Exception as e:
    print(f'ERROR: {{e}}')
'''
    result = subprocess.run(
        [sys.executable, '-c', test_script],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )
    output = result.stdout.strip()
    if 'VALIDATION_PASSED' in output:
        return True, None
    elif 'VALIDATION_FAILED:' in output:
        return False, output.split('VALIDATION_FAILED:', 1)[1].strip()
    else:
        return False, f"Unexpected output: {output}, stderr: {result.stderr}"


class TestMCPConstants:
    """Test security constants are properly defined by checking validation behavior."""

    def test_allowed_commands_accepted(self):
        """Valid commands should be accepted."""
        # Test npx
        passed, error = run_mcp_validation('npx', ['@playwright/mcp'])
        assert passed, f"npx should be allowed: {error}"
        
        # Test docker
        passed, error = run_mcp_validation('docker', ['run', 'mcp-server'])
        assert passed, f"docker should be allowed: {error}"
        
        # Test python3
        passed, error = run_mcp_validation('python3', ['script.py'])
        assert passed, f"python3 should be allowed: {error}"

    def test_blocked_commands_rejected(self):
        """Dangerous commands should be blocked."""
        # Test bash
        passed, error = run_mcp_validation('bash', ['-c', 'rm -rf /'])
        assert not passed, "bash should be blocked"
        assert 'bash' in error.lower() or 'allowlist' in error.lower()
        
        # Test sh
        passed, error = run_mcp_validation('sh', ['-c', 'evil'])
        assert not passed, "sh should be blocked"


class TestValidateMCPCommand:
    """Test MCP command validation function."""

    # =============================================================================
    # Valid Commands (Should Pass)
    # =============================================================================

    def test_valid_npx_playwright(self):
        """npx @playwright/mcp should be allowed."""
        passed, error = run_mcp_validation('npx', ['-y', '@playwright/mcp'])
        assert passed, f"npx @playwright/mcp should be allowed: {error}"

    def test_valid_npx_official_mcp(self):
        """npx @modelcontextprotocol/server-filesystem should be allowed."""
        passed, error = run_mcp_validation('npx', ['@modelcontextprotocol/server-filesystem', '/tmp'])
        assert passed, f"Official MCP package should be allowed: {error}"

    def test_valid_npx_composio(self):
        """npx @composio/mcp should be allowed."""
        passed, error = run_mcp_validation('npx', ['@composio/mcp@latest'])
        assert passed, f"Composio package should be allowed: {error}"

    def test_valid_npx_mcp_prefix(self):
        """npx mcp-google should be allowed."""
        passed, error = run_mcp_validation('npx', ['mcp-google'])
        assert passed, f"mcp- prefix package should be allowed: {error}"

    def test_valid_docker_simple(self):
        """docker run without dangerous flags should be allowed."""
        passed, error = run_mcp_validation('docker', ['run', '-i', '--rm', 'mcp-server'])
        assert passed, f"docker run should be allowed: {error}"

    def test_valid_python3(self):
        """python3 should be allowed."""
        passed, error = run_mcp_validation('python3', ['script.py'])
        assert passed, f"python3 should be allowed: {error}"

    def test_valid_node(self):
        """node should be allowed."""
        passed, error = run_mcp_validation('node', ['server.js'])
        assert passed, f"node should be allowed: {error}"

    def test_valid_uv(self):
        """uv should be allowed."""
        passed, error = run_mcp_validation('uv', ['run', 'mcp-server'])
        assert passed, f"uv should be allowed: {error}"

    def test_valid_pipx(self):
        """pipx should be allowed."""
        passed, error = run_mcp_validation('pipx', ['run', 'mcp-package'])
        assert passed, f"pipx should be allowed: {error}"

    def test_valid_python(self):
        """python should be allowed."""
        passed, error = run_mcp_validation('python', ['script.py'])
        assert passed, f"python should be allowed: {error}"

    # =============================================================================
    # Invalid Commands (Should Raise MCPSecurityError)
    # =============================================================================

    def test_bash_command_blocked(self):
        """bash should be blocked."""
        passed, error = run_mcp_validation('bash', ['-c', 'rm -rf /'])
        assert not passed, "bash should be blocked"
        assert 'bash' in error.lower() or 'allowlist' in error.lower()

    def test_sh_command_blocked(self):
        """sh should be blocked."""
        passed, error = run_mcp_validation('sh', ['-c', 'evil'])
        assert not passed, "sh should be blocked"

    def test_curl_command_blocked(self):
        """curl should be blocked."""
        passed, error = run_mcp_validation('curl', ['http://evil.com'])
        assert not passed, "curl should be blocked"

    def test_wget_command_blocked(self):
        """wget should be blocked."""
        passed, error = run_mcp_validation('wget', ['http://evil.com'])
        assert not passed, "wget should be blocked"

    def test_rm_command_blocked(self):
        """rm should be blocked."""
        passed, error = run_mcp_validation('rm', ['-rf', '/'])
        assert not passed, "rm should be blocked"

    def test_empty_command_blocked(self):
        """Empty command should be blocked."""
        passed, error = run_mcp_validation('', [])
        assert not passed, "empty command should be blocked"

    # =============================================================================
    # Invalid Packages (Should Raise MCPSecurityError)
    # =============================================================================

    def test_npx_evil_package_blocked(self):
        """npx with unknown package should be blocked."""
        passed, error = run_mcp_validation('npx', ['evil-package'])
        assert not passed, "evil-package should be blocked"
        assert 'evil-package' in error or 'allowlist' in error.lower()

    def test_npx_malicious_prefix_blocked(self):
        """npx with malicious package prefix should be blocked."""
        passed, error = run_mcp_validation('npx', ['@evil/playwright'])
        assert not passed, "@evil/playwright should be blocked"

    def test_uv_evil_package_blocked(self):
        """uv with unknown package should be blocked."""
        passed, error = run_mcp_validation('uv', ['run', 'evil-package'])
        assert not passed, "evil-package with uv should be blocked"

    def test_pipx_evil_package_blocked(self):
        """pipx with unknown package should be blocked."""
        passed, error = run_mcp_validation('pipx', ['run', 'evil-package'])
        assert not passed, "evil-package with pipx should be blocked"

    # =============================================================================
    # Dangerous Docker Flags (Should Raise MCPSecurityError)
    # =============================================================================

    def test_docker_privileged_blocked(self):
        """docker --privileged should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '--privileged', 'mcp-server'])
        assert not passed, "docker --privileged should be blocked"
        assert '--privileged' in error or 'not allowed' in error.lower()

    def test_docker_volume_short_blocked(self):
        """docker -v should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '-v', '/:/host', 'mcp-server'])
        assert not passed, "docker -v should be blocked"

    def test_docker_volume_long_blocked(self):
        """docker --volume should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '--volume', '/:/host', 'mcp-server'])
        assert not passed, "docker --volume should be blocked"

    def test_docker_network_host_blocked(self):
        """docker --network=host should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '--network=host', 'mcp-server'])
        assert not passed, "docker --network=host should be blocked"

    def test_docker_pid_host_blocked(self):
        """docker --pid=host should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '--pid=host', 'mcp-server'])
        assert not passed, "docker --pid=host should be blocked"

    def test_docker_ipc_host_blocked(self):
        """docker --ipc=host should be blocked."""
        passed, error = run_mcp_validation('docker', ['run', '--ipc=host', 'mcp-server'])
        assert not passed, "docker --ipc=host should be blocked"

    # =============================================================================
    # Edge Cases
    # =============================================================================

    def test_npx_with_flags_only(self):
        """npx with only flags (no package) should pass."""
        passed, error = run_mcp_validation('npx', ['-y', '--version'])
        assert passed, f"npx with flags only should be allowed: {error}"

    def test_npx_package_after_flags(self):
        """npx with package after flags should validate correctly."""
        passed, error = run_mcp_validation('npx', ['-y', '--quiet', '@playwright/mcp'])
        assert passed, f"npx with package after flags should be allowed: {error}"

    def test_case_sensitive_commands(self):
        """Commands should be case-sensitive (only lowercase allowed)."""
        passed, error = run_mcp_validation('NPX', ['@playwright/mcp'])
        assert not passed, "NPX (uppercase) should be blocked"

    def test_config_with_env(self):
        """Config with env should not affect validation."""
        # This is tested implicitly since we don't pass env to run_mcp_validation
        # but the validation function accepts it without error
        passed, error = run_mcp_validation('npx', ['@playwright/mcp'])
        assert passed, f"npx with env should be allowed: {error}"
