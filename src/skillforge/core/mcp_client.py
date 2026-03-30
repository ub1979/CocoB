# =============================================================================
'''
    File Name : mcp_client.py
    
    Description : MCP (Model Context Protocol) client for tool integration
    
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

import asyncio
import json
import subprocess
import os
import platform
import threading
import concurrent.futures
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import logging

# =============================================================================
# Import MCP Models
# =============================================================================

from skillforge.core.mcp_models import (
    MCPServerType,
    MCPConnectionStatus,
    MCPServerConfig,
    MCPServerState,
    validate_config,
)


# =============================================================================
'''
    MCPSecurity : Security constants and validation for MCP server commands
    
    Prevents execution of arbitrary commands by maintaining an allowlist of
    safe commands and package prefixes. This protects against malicious MCP
    server configurations that could compromise the system.
'''
# =============================================================================

# ==================================
# Allowed base commands for MCP servers
# These are the only commands permitted to launch MCP servers
# ==================================
ALLOWED_MCP_COMMANDS = frozenset({
    'npx',      # Node package executor (for Playwright, etc.)
    'docker',   # Container runtime
    'python3',  # Python 3 interpreter
    'python',   # Python interpreter
    'node',     # Node.js runtime
    'uv',       # Modern Python package manager
    'pipx',     # Python application runner
})

# ==================================
# Allowed package name prefixes for npm/pip packages
# Only packages starting with these prefixes are permitted
# ==================================
ALLOWED_MCP_PACKAGE_PREFIXES = (
    '@playwright/',           # Playwright browser automation
    '@modelcontextprotocol/', # Official MCP servers
    '@notionhq/',             # Official Notion MCP server
    '@composio/',             # Composio integrations
    'mcp-',                   # MCP utility packages
)

# ==================================
# Dangerous Docker flags that are not allowed
# These flags could compromise container security
# ==================================
DANGEROUS_DOCKER_FLAGS = frozenset({
    '--privileged',
    '-v',
    '--volume',
    '--network=host',
    '--pid=host',
    '--ipc=host',
})


# =============================================================================
'''
    MCPSecurityError : Exception raised when MCP security validation fails
'''
# =============================================================================
class MCPSecurityError(Exception):
    """Raised when MCP server configuration violates security policy"""
    pass


# =============================================================================
'''
    validate_mcp_command : Validates MCP server command against security allowlist
    
    Security:
        - Checks base command is in allowlist
        - Validates package names for npm/pip tools
        - Blocks dangerous Docker flags
        
    Raises:
        MCPSecurityError: If command fails security validation
'''
# =============================================================================
def validate_mcp_command(config: Dict[str, Any]) -> None:
    """
    Validate MCP server command against security allowlist.
    
    Args:
        config: MCP server configuration dictionary with 'command' and 'args'
        
    Raises:
        MCPSecurityError: If command is not in allowlist or contains unsafe elements
    """
    # ==================================
    # Extract command and arguments from config
    # ==================================
    command = config.get('command', '')
    args = config.get('args', [])
    
    # ==================================
    # Validate base command is in allowlist
    # ==================================
    if command not in ALLOWED_MCP_COMMANDS:
        raise MCPSecurityError(
            f"MCP command '{command}' is not in the security allowlist. "
            f"Allowed commands: {', '.join(sorted(ALLOWED_MCP_COMMANDS))}. "
            f"If you need to use '{command}', add it to ALLOWED_MCP_COMMANDS in "
            f"mcp_client.py after verifying it is safe."
        )
    
    # ==================================
    # For package managers, validate the package name
    # ==================================
    if command == 'npx':
        # npx: package name is first non-flag argument
        # Example: npx -y @playwright/mcp
        package = None
        for arg in args:
            if not arg.startswith('-'):
                package = arg
                break
        
        # ==================================
        # Validate package prefix if a package was found
        # ==================================
        if package and not any(
            package.startswith(p) for p in ALLOWED_MCP_PACKAGE_PREFIXES
        ):
            raise MCPSecurityError(
                f"MCP package '{package}' is not in the security allowlist. "
                f"Allowed prefixes: {', '.join(ALLOWED_MCP_PACKAGE_PREFIXES)}. "
                f"If you trust this package, add its prefix to "
                f"ALLOWED_MCP_PACKAGE_PREFIXES in mcp_client.py."
            )
    
    elif command in ('uv', 'pipx'):
        # uv: uv run [options] <package>
        # pipx: pipx run [options] <package>
        # Package name comes after subcommand and optional flags
        # Example: uv run --python 3.11 @playwright/mcp
        # Example: pipx run --spec @playwright/mcp
        package = None
        found_subcommand = False
        for arg in args:
            if not arg.startswith('-'):
                if not found_subcommand:
                    # First non-flag is the subcommand (run, install, etc.)
                    found_subcommand = True
                else:
                    # Second non-flag is the package name
                    package = arg
                    break
        
        # ==================================
        # Validate package prefix if a package was found
        # ==================================
        if package and not any(
            package.startswith(p) for p in ALLOWED_MCP_PACKAGE_PREFIXES
        ):
            raise MCPSecurityError(
                f"MCP package '{package}' is not in the security allowlist. "
                f"Allowed prefixes: {', '.join(ALLOWED_MCP_PACKAGE_PREFIXES)}. "
                f"If you trust this package, add its prefix to "
                f"ALLOWED_MCP_PACKAGE_PREFIXES in mcp_client.py."
            )
    
    # ==================================
    # For Docker, block dangerous flags that could escape container
    # ==================================
    if command == 'docker':
        for arg in args:
            if arg in DANGEROUS_DOCKER_FLAGS:
                raise MCPSecurityError(
                    f"Docker flag '{arg}' is not allowed for security reasons. "
                    f"This flag could allow the container to access host resources."
                )


# =============================================================================
'''
    MCPClient : Generic MCP client for connecting to MCP servers
'''
# =============================================================================

class MCPClient:
    """Generic MCP client for connecting to MCP servers"""

    # =========================================================================
    # Function __init__ -> Dict[str, Any] to None
    # =========================================================================
    def __init__(self, server_config: Dict[str, Any]):
        """
        Initialize MCP client

        Args:
            server_config: {
                'command': 'npx',
                'args': ['-y', '@playwright/mcp-server'],
                'env': {...},
                'type': 'stdio'  # or 'docker', 'sse', 'http'
            }
        """
        # ==================================
        # Store server configuration
        self.config = server_config

        # ==================================
        # Determine server type
        type_str = server_config.get('type', 'stdio')
        try:
            self.server_type = MCPServerType(type_str)
        except ValueError:
            self.server_type = MCPServerType.STDIO

        # ==================================
        # Initialize process and state variables
        self.process = None
        self.tools = []
        self.resources = []
        self.connected = False
        self.status = MCPConnectionStatus.DISCONNECTED
        self.error_message = None

        # ==================================
        # HTTP/SSE specific state
        self._http_client = None
        self._sse_reader = None
        self._request_id = 0

        # ==================================
        # Setup logging for this MCP client
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger(f"mcp.{server_config.get('name', 'unknown')}")
        self.logger.setLevel(logging.DEBUG)
    
    # =========================================================================
    # Function connect -> None to None
    # =========================================================================
    async def connect(self):
        """Start MCP server and connect based on transport type"""
        self.status = MCPConnectionStatus.CONNECTING
        self.error_message = None

        try:
            # ==================================
            # Route to appropriate connect method based on type
            # ==================================
            if self.server_type == MCPServerType.STDIO:
                await self._connect_stdio()
            elif self.server_type == MCPServerType.DOCKER:
                await self._connect_docker()
            elif self.server_type == MCPServerType.SSE:
                await self._connect_sse()
            elif self.server_type == MCPServerType.HTTP:
                await self._connect_http()
            else:
                raise ValueError(f"Unknown server type: {self.server_type}")

            self.status = MCPConnectionStatus.CONNECTED

        except Exception as e:
            self.status = MCPConnectionStatus.ERROR
            self.error_message = str(e)
            self.logger.error(f"❌ Failed to connect: {e}")
            raise

    # =========================================================================
    # Function _connect_stdio -> None to None
    # =========================================================================
    async def _connect_stdio(self):
        """Connect to STDIO-based MCP server (subprocess)"""
        # ==================================
        # Security: Validate command against allowlist before execution
        # This prevents malicious configs from executing arbitrary commands
        # ==================================
        try:
            validate_mcp_command(self.config)
        except MCPSecurityError as e:
            self.logger.error(f"❌ MCP Security Error: {e}")
            self.status = MCPConnectionStatus.ERROR
            self.error_message = str(e)
            raise
        
        # ==================================
        # Build command from configuration
        command = [self.config['command']] + self.config.get('args', [])

        # Expand ~ in environment variable values (for cross-platform compatibility)
        config_env = self.config.get('env', {})
        expanded_env = {k: os.path.expanduser(v) if isinstance(v, str) else v for k, v in config_env.items()}
        env = {**os.environ, **expanded_env}

        self.logger.info(f"🔌 Starting MCP server (STDIO): {' '.join(command)}")

        # ==================================
        # Start the MCP server as subprocess
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=1024 * 1024,  # 1 MB read buffer (default 64KB too small for large tool lists)
        )

        # ==================================
        # Start stderr reader task (for debugging)
        asyncio.create_task(self._read_stderr())

        # ==================================
        # Wait a moment for process to start
        await asyncio.sleep(0.5)

        # ==================================
        # Check if process is still running
        if self.process.returncode is not None:
            raise ConnectionError(f"MCP server exited immediately with code {self.process.returncode}")

        # ==================================
        # Initialize and list tools
        await self._initialize_connection()

    # =========================================================================
    # Function _read_stderr -> None to None
    # =========================================================================
    async def _read_stderr(self):
        """Read stderr from subprocess for logging"""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                stderr_text = line.decode().strip()
                if stderr_text:
                    self.logger.debug(f"[stderr] {stderr_text}")
        except Exception as e:
            self.logger.debug(f"Stderr reader stopped: {e}")

    # =========================================================================
    # Function _connect_docker -> None to None
    # =========================================================================
    async def _connect_docker(self):
        """Connect to Docker-based MCP server"""
        # ==================================
        # Security: Validate command against allowlist before execution
        # Docker has additional checks for dangerous flags
        # ==================================
        try:
            validate_mcp_command(self.config)
        except MCPSecurityError as e:
            self.logger.error(f"❌ MCP Security Error: {e}")
            self.status = MCPConnectionStatus.ERROR
            self.error_message = str(e)
            raise
        
        # ==================================
        # Build docker run command
        command = [self.config.get('command', 'docker')]
        args = self.config.get('args', [])

        # ==================================
        # Ensure -i flag is present for stdin
        if '-i' not in args and '--interactive' not in args:
            args = ['-i'] + args

        command.extend(args)

        # Expand ~ in environment variable values (for cross-platform compatibility)
        config_env = self.config.get('env', {})
        expanded_env = {k: os.path.expanduser(v) if isinstance(v, str) else v for k, v in config_env.items()}
        env = {**os.environ, **expanded_env}

        self.logger.info(f"🔌 Starting MCP server (Docker): {' '.join(command)}")

        # ==================================
        # Start the Docker container
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=1024 * 1024,
        )

        # ==================================
        # Initialize and list tools
        await self._initialize_connection()

    # =========================================================================
    # Function _connect_sse -> None to None
    # =========================================================================
    async def _connect_sse(self):
        """Connect to SSE-based MCP server"""
        try:
            import aiohttp
        except ImportError:
            raise ImportError("aiohttp is required for SSE transport. Install with: pip install aiohttp")

        url = self.config.get('url')
        if not url:
            raise ValueError("URL is required for SSE server")

        headers = self.config.get('headers', {})

        self.logger.info(f"🔌 Connecting to MCP server (SSE): {url}")

        # ==================================
        # Create aiohttp session
        self._http_session = aiohttp.ClientSession(headers=headers)

        try:
            # ==================================
            # Initialize connection via SSE
            init_response = await self._send_sse_request({
                'jsonrpc': '2.0',
                'id': self._next_request_id(),
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {},
                    'clientInfo': {
                        'name': 'skillforge',
                        'version': '1.0.0'
                    }
                }
            })

            # ==================================
            # List available tools
            tools_response = await self._send_sse_request({
                'jsonrpc': '2.0',
                'id': self._next_request_id(),
                'method': 'tools/list'
            })

            if tools_response and 'result' in tools_response:
                self.tools = tools_response['result'].get('tools', [])
                self.logger.info(f"✅ Connected (SSE)! Available tools: {[t['name'] for t in self.tools]}")
                self.connected = True

        except Exception as e:
            await self._http_session.close()
            self._http_session = None
            raise

    # =========================================================================
    # Function _connect_http -> None to None
    # =========================================================================
    async def _connect_http(self):
        """Connect to HTTP-based MCP server (Streamable HTTP)"""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for HTTP transport. Install with: pip install httpx")

        url = self.config.get('url')
        if not url:
            raise ValueError("URL is required for HTTP server")

        headers = self.config.get('headers', {})
        headers['Content-Type'] = 'application/json'

        self.logger.info(f"🔌 Connecting to MCP server (HTTP): {url}")

        # ==================================
        # Create httpx async client
        self._http_client = httpx.AsyncClient(headers=headers, timeout=30.0)

        try:
            # ==================================
            # Initialize connection
            init_response = await self._send_http_request({
                'jsonrpc': '2.0',
                'id': self._next_request_id(),
                'method': 'initialize',
                'params': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {},
                    'clientInfo': {
                        'name': 'skillforge',
                        'version': '1.0.0'
                    }
                }
            })

            # ==================================
            # List available tools
            tools_response = await self._send_http_request({
                'jsonrpc': '2.0',
                'id': self._next_request_id(),
                'method': 'tools/list'
            })

            if tools_response and 'result' in tools_response:
                self.tools = tools_response['result'].get('tools', [])
                self.logger.info(f"✅ Connected (HTTP)! Available tools: {[t['name'] for t in self.tools]}")
                self.connected = True

        except Exception as e:
            await self._http_client.aclose()
            self._http_client = None
            raise

    # =========================================================================
    # Function _initialize_connection -> None to None
    # =========================================================================
    async def _initialize_connection(self):
        """Common initialization for STDIO/Docker transports"""
        # ==================================
        # Step 1: Send initialize request
        self.logger.info("Sending initialize request...")
        init_response = await self._send_request({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'tools': {}
                },
                'clientInfo': {
                    'name': 'skillforge',
                    'version': '1.0.0'
                }
            }
        })

        if not init_response:
            raise ConnectionError("No response to initialize request")

        if 'error' in init_response:
            raise ConnectionError(f"Initialize failed: {init_response['error']}")

        self.logger.info(f"Initialize response received: {init_response.get('result', {}).get('serverInfo', {})}")

        # ==================================
        # Step 2: Send initialized notification (required by MCP protocol)
        self.logger.info("Sending initialized notification...")
        initialized_notification = json.dumps({
            'jsonrpc': '2.0',
            'method': 'notifications/initialized'
        }) + '\n'
        self.process.stdin.write(initialized_notification.encode())
        await self.process.stdin.drain()

        # ==================================
        # Step 3: Wait a moment for server to be ready
        await asyncio.sleep(0.2)

        # ==================================
        # Step 4: List available tools from server
        self.logger.info("Requesting tools list...")
        response = await self._send_request({
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'tools/list'
        })

        # ==================================
        # Process tools response
        if response and 'result' in response:
            self.tools = response['result'].get('tools', [])
            self.logger.info(f"✅ Connected! Available tools: {[t['name'] for t in self.tools]}")
            self.connected = True
        elif response and 'error' in response:
            self.logger.warning(f"Tools list error: {response['error']}")
            self.connected = True  # Still connected, just no tools
        else:
            self.logger.warning("No tools response received")
            self.connected = True

    # =========================================================================
    # Function _next_request_id -> None to int
    # =========================================================================
    def _next_request_id(self) -> int:
        """Get next request ID for JSON-RPC"""
        self._request_id += 1
        return self._request_id
    
    # =========================================================================
    # Function _send_request -> Dict to Optional[Dict]
    # =========================================================================
    async def _send_request(self, request: Dict, timeout: float = 30.0) -> Optional[Dict]:
        """Send JSON-RPC request to MCP server (STDIO/Docker)"""
        # ==================================
        # Validate connection state
        if not self.process or not self.process.stdin:
            raise ConnectionError("MCP server not connected")

        # ==================================
        # Check if process is still running
        if self.process.returncode is not None:
            self.connected = False
            self.status = MCPConnectionStatus.ERROR
            self.error_message = f"Server process exited with code {self.process.returncode}"
            raise ConnectionError(self.error_message)

        try:
            # ==================================
            # Send request as JSON
            request_json = json.dumps(request) + '\n'
            self.logger.debug(f"Sending: {request_json.strip()}")
            self.process.stdin.write(request_json.encode())
            await self.process.stdin.drain()

            # ==================================
            # Read response with timeout
            try:
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.error(f"Timeout waiting for response to {request.get('method')}")
                raise ConnectionError(f"Timeout waiting for MCP server response")

            if not response_line:
                # Empty response usually means process exited
                if self.process.returncode is not None:
                    raise ConnectionError(f"MCP server exited with code {self.process.returncode}")
                raise ConnectionError("Empty response from MCP server")

            # ==================================
            # Parse JSON response
            response_text = response_line.decode().strip()
            self.logger.debug(f"Received: {response_text[:200]}...")

            response = json.loads(response_text)

            # ==================================
            # Check for JSON-RPC error
            if 'error' in response:
                error = response['error']
                self.logger.error(f"MCP error: {error}")

            return response

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {e}")
            return None
        except ConnectionError:
            raise
        except Exception as e:
            self.logger.error(f"Error sending request: {e}")
            raise ConnectionError(f"Communication error: {e}")

    # =========================================================================
    # Function _send_sse_request -> Dict to Optional[Dict]
    # =========================================================================
    async def _send_sse_request(self, request: Dict) -> Optional[Dict]:
        """Send JSON-RPC request via SSE transport"""
        if not hasattr(self, '_http_session') or not self._http_session:
            raise ConnectionError("SSE session not connected")

        url = self.config.get('url')

        try:
            # ==================================
            # Send POST request
            async with self._http_session.post(url, json=request) as response:
                if response.status != 200:
                    raise ConnectionError(f"SSE request failed: HTTP {response.status}")

                # ==================================
                # Read SSE response
                content = await response.text()

                # ==================================
                # Parse SSE data lines
                for line in content.split('\n'):
                    if line.startswith('data: '):
                        data = line[6:]
                        if data.strip():
                            return json.loads(data)

                # ==================================
                # Fallback: try to parse as plain JSON
                return json.loads(content)

        except Exception as e:
            self.logger.error(f"Error sending SSE request: {e}")
            return None

    # =========================================================================
    # Function _send_http_request -> Dict to Optional[Dict]
    # =========================================================================
    async def _send_http_request(self, request: Dict) -> Optional[Dict]:
        """Send JSON-RPC request via HTTP transport"""
        if not self._http_client:
            raise ConnectionError("HTTP client not connected")

        url = self.config.get('url')

        try:
            # ==================================
            # Send POST request
            response = await self._http_client.post(url, json=request)

            if response.status_code != 200:
                raise ConnectionError(f"HTTP request failed: {response.status_code}")

            # ==================================
            # Parse JSON response
            return response.json()

        except Exception as e:
            self.logger.error(f"Error sending HTTP request: {e}")
            return None
    
    # =========================================================================
    # Function call_tool -> str, Dict to Any
    # =========================================================================
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        Call a tool on the MCP server

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        # ==================================
        # Check connection status
        if not self.connected:
            raise ConnectionError("Not connected to MCP server")

        self.logger.info(f"🔧 Calling tool: {tool_name} with args: {arguments}")

        request = {
            'jsonrpc': '2.0',
            'id': self._next_request_id(),
            'method': 'tools/call',
            'params': {
                'name': tool_name,
                'arguments': arguments
            }
        }

        # ==================================
        # Route to appropriate send method based on type
        if self.server_type in (MCPServerType.STDIO, MCPServerType.DOCKER):
            response = await self._send_request(request)
        elif self.server_type == MCPServerType.SSE:
            response = await self._send_sse_request(request)
        elif self.server_type == MCPServerType.HTTP:
            response = await self._send_http_request(request)
        else:
            raise ValueError(f"Unknown server type: {self.server_type}")

        # ==================================
        # Process response
        if response and 'result' in response:
            return response['result']
        elif response and 'error' in response:
            raise Exception(f"Tool error: {response['error']}")
        else:
            raise Exception("No response from tool")
    
    # =========================================================================
    # Function get_available_tools -> None to List[Dict]
    # =========================================================================
    def get_available_tools(self) -> List[Dict]:
        """Get list of available tools"""
        return self.tools
    
    # =========================================================================
    # Function format_tools_for_ai -> None to str
    # =========================================================================
    def format_tools_for_ai(self) -> str:
        """Format tools as text for AI model to understand"""
        # ==================================
        # Handle empty tools case
        if not self.tools:
            return "No tools available."
        
        # ==================================
        # Build tool descriptions
        tool_descriptions = []
        for tool in self.tools:
            desc = f"**{tool['name']}**"
            if 'description' in tool:
                desc += f": {tool['description']}"
            if 'inputSchema' in tool:
                desc += f"\n  Parameters: {json.dumps(tool['inputSchema'], indent=2)}"
            tool_descriptions.append(desc)
        
        return "\n\n".join(tool_descriptions)
    
    # =========================================================================
    # Function disconnect -> None to None
    # =========================================================================
    async def disconnect(self):
        """Disconnect from MCP server"""
        try:
            # ==================================
            # Handle STDIO/Docker process
            if self.process:
                try:
                    self.process.terminate()
                    await self.process.wait()
                except Exception as e:
                    self.logger.error(f"Error terminating process: {e}")
                finally:
                    self.process = None

            # ==================================
            # Handle SSE session
            if hasattr(self, '_http_session') and self._http_session:
                try:
                    await self._http_session.close()
                except Exception as e:
                    self.logger.error(f"Error closing SSE session: {e}")
                finally:
                    self._http_session = None

            # ==================================
            # Handle HTTP client
            if self._http_client:
                try:
                    await self._http_client.aclose()
                except Exception as e:
                    self.logger.error(f"Error closing HTTP client: {e}")
                finally:
                    self._http_client = None

            self.connected = False
            self.status = MCPConnectionStatus.DISCONNECTED
            self.tools = []
            self.logger.info("👋 Disconnected from MCP server")

        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")

    # =========================================================================
    # Function get_state -> None to MCPServerState
    # =========================================================================
    def get_state(self) -> MCPServerState:
        """Get current server state"""
        config = MCPServerConfig.from_dict(
            self.config.get('name', 'unknown'),
            self.config
        )
        return MCPServerState(
            config=config,
            status=self.status,
            tools=self.tools,
            error_message=self.error_message
        )


# =============================================================================
'''
    MCPManager : Manages multiple MCP server connections
'''
# =============================================================================

class MCPManager:
    """Manages multiple MCP server connections"""

    # =========================================================================
    # Function __init__ -> Optional[Path] to None
    # =========================================================================
    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize MCP manager

        Args:
            config_file: Path to MCP servers config file
        """
        # ==================================
        # Set configuration file path
        if config_file is None:
            from skillforge import PROJECT_ROOT
            config_file = PROJECT_ROOT / "config" / "mcp_config.json"
        self.config_file = config_file

        # ==================================
        # Initialize servers dictionary
        self.servers: Dict[str, MCPClient] = {}

        # ==================================
        # Server states for UI display
        self._server_configs: Dict[str, MCPServerConfig] = {}

        # ==================================
        # Callback for state changes
        self.on_state_change: Optional[Callable[[], None]] = None

        self.logger = logging.getLogger("mcp.manager")

        # ==================================
        # Create dedicated event loop in background thread
        # This ensures all MCP operations run in a consistent event loop
        # ==================================
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("MCP Manager started with dedicated event loop")

    # =========================================================================
    # Function _run_loop -> None to None
    # =========================================================================
    def _run_loop(self):
        """Run the dedicated event loop in background thread"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # =========================================================================
    # Function _run_in_loop -> coroutine to Any
    # =========================================================================
    def _run_in_loop(self, coro, timeout: float = 60.0):
        """
        Run a coroutine in the dedicated MCP event loop (thread-safe).

        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds

        Returns:
            Result of the coroutine
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError(f"MCP operation timed out after {timeout}s")
    
    # =========================================================================
    # Function load_config -> None to Dict
    # =========================================================================
    def load_config(self) -> Dict:
        """Load MCP servers configuration"""
        # ==================================
        # Check if config file exists
        if not self.config_file.exists():
            self.logger.warning(f"Config file not found: {self.config_file}")
            return {}

        # ==================================
        # Load and parse JSON config
        with open(self.config_file, 'r') as f:
            config = json.load(f)

        # ==================================
        # Parse server configs
        self._server_configs.clear()
        for name, server_data in config.get('mcpServers', {}).items():
            self._server_configs[name] = MCPServerConfig.from_dict(name, server_data)

        return config

    # =========================================================================
    # Function save_config -> None to bool
    # =========================================================================
    def save_config(self) -> bool:
        """Save MCP servers configuration to file"""
        try:
            # ==================================
            # Build config dict from server configs
            config = {
                "mcpServers": {
                    name: cfg.to_dict()
                    for name, cfg in self._server_configs.items()
                }
            }

            # ==================================
            # Write to file with pretty formatting
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)

            self.logger.info(f"Saved MCP config to {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            return False

    # =========================================================================
    # Function add_server -> MCPServerConfig to bool
    # =========================================================================
    def add_server(self, config: MCPServerConfig) -> bool:
        """Add a new server configuration"""
        # ==================================
        # Validate config
        is_valid, error_msg = validate_config(config)
        if not is_valid:
            self.logger.error(f"Invalid config for {config.name}: {error_msg}")
            return False

        # ==================================
        # Add to configs
        self._server_configs[config.name] = config

        # ==================================
        # Save to file
        return self.save_config()

    # =========================================================================
    # Function remove_server -> str to bool
    # =========================================================================
    def remove_server(self, name: str) -> bool:
        """Remove a server configuration"""
        if name not in self._server_configs:
            return False

        # ==================================
        # Disconnect if connected
        if name in self.servers:
            try:
                self._run_in_loop(self.disconnect_server(name), timeout=10.0)
            except Exception:
                pass

        # ==================================
        # Remove from configs
        del self._server_configs[name]

        # ==================================
        # Save to file
        return self.save_config()

    # =========================================================================
    # Function get_server_configs -> None to Dict[str, MCPServerConfig]
    # =========================================================================
    def get_server_configs(self) -> Dict[str, MCPServerConfig]:
        """Get all server configurations"""
        return self._server_configs.copy()
    
    # =========================================================================
    # Function connect_all -> None to None
    # =========================================================================
    async def connect_all(self):
        """Connect to all enabled MCP servers"""
        # ==================================
        # Load configuration
        self.load_config()

        # ==================================
        # Connect to each enabled server
        for name, server_config in self._server_configs.items():
            if server_config.enabled:
                await self.connect_server(name)

    # =========================================================================
    # Function connect_server -> str to Tuple[bool, str]
    # =========================================================================
    async def connect_server(self, name: str) -> tuple[bool, str]:
        """Connect to a specific MCP server"""
        # ==================================
        # Check if config exists
        if name not in self._server_configs:
            return False, f"Server not found: {name}"

        config = self._server_configs[name]

        # ==================================
        # Validate config
        is_valid, error_msg = validate_config(config)
        if not is_valid:
            return False, f"Invalid config: {error_msg}"

        try:
            # ==================================
            # Build client config dict
            client_config = config.to_dict()
            client_config['name'] = name

            # ==================================
            # Create and connect client
            client = MCPClient(client_config)
            await client.connect()

            # ==================================
            # Store connected client
            self.servers[name] = client
            self.logger.info(f"✅ {name} connected")

            # ==================================
            # Trigger state change callback
            if self.on_state_change:
                self.on_state_change()

            return True, f"Connected to {name} ({len(client.tools)} tools)"

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to {name}: {e}")
            return False, f"Failed to connect: {str(e)}"

    # =========================================================================
    # Function disconnect_server -> str to Tuple[bool, str]
    # =========================================================================
    async def disconnect_server(self, name: str) -> tuple[bool, str]:
        """Disconnect from a specific MCP server"""
        if name not in self.servers:
            return False, f"Server not connected: {name}"

        try:
            await self.servers[name].disconnect()
            del self.servers[name]

            # ==================================
            # Trigger state change callback
            if self.on_state_change:
                self.on_state_change()

            return True, f"Disconnected from {name}"

        except Exception as e:
            return False, f"Error disconnecting: {str(e)}"
    
    # =========================================================================
    # Function call_tool -> str, str, Dict to Any
    # =========================================================================
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on a specific MCP server"""
        # ==================================
        # Validate server exists
        if server_name not in self.servers:
            raise ValueError(f"Server '{server_name}' not connected")

        return await self.servers[server_name].call_tool(tool_name, arguments)

    # =========================================================================
    # SYNC WRAPPERS - Thread-safe methods for use from any context
    # =========================================================================

    # =========================================================================
    # Function connect_server_sync -> str to Tuple[bool, str]
    # =========================================================================
    def connect_server_sync(self, name: str, timeout: float = 60.0) -> tuple[bool, str]:
        """
        Connect to a server (thread-safe sync wrapper).
        Uses the dedicated MCP event loop.
        """
        return self._run_in_loop(self.connect_server(name), timeout=timeout)

    # =========================================================================
    # Function disconnect_server_sync -> str to Tuple[bool, str]
    # =========================================================================
    def disconnect_server_sync(self, name: str, timeout: float = 30.0) -> tuple[bool, str]:
        """
        Disconnect from a server (thread-safe sync wrapper).
        Uses the dedicated MCP event loop.
        """
        return self._run_in_loop(self.disconnect_server(name), timeout=timeout)

    # =========================================================================
    # Function call_tool_sync -> str, str, Dict to Any
    # =========================================================================
    def call_tool_sync(self, server_name: str, tool_name: str, arguments: Dict, timeout: float = 60.0) -> Any:
        """
        Call a tool (thread-safe sync wrapper).
        Uses the dedicated MCP event loop.
        """
        return self._run_in_loop(self.call_tool(server_name, tool_name, arguments), timeout=timeout)

    # =========================================================================
    # Function connect_all_sync -> None to None
    # =========================================================================
    def connect_all_sync(self, timeout: float = 120.0):
        """
        Connect to all enabled servers (thread-safe sync wrapper).
        Uses the dedicated MCP event loop.
        """
        return self._run_in_loop(self.connect_all(), timeout=timeout)

    # =========================================================================
    # Function disconnect_all_sync -> None to None
    # =========================================================================
    def disconnect_all_sync(self, timeout: float = 60.0):
        """
        Disconnect from all servers (thread-safe sync wrapper).
        Uses the dedicated MCP event loop.
        """
        return self._run_in_loop(self.disconnect_all(), timeout=timeout)

    # =========================================================================
    # Function get_all_tools -> None to Dict[str, List[Dict]]
    # =========================================================================
    def get_all_tools(self) -> Dict[str, List[Dict]]:
        """Get all available tools from all servers"""
        return {
            name: server.get_available_tools()
            for name, server in self.servers.items()
        }

    # =========================================================================
    # Function format_all_tools_for_ai -> None to str
    # =========================================================================
    def format_all_tools_for_ai(self) -> str:
        """Format all tools for AI consumption"""
        # ==================================
        # Build formatted output
        output = ["# Available MCP Tools\n"]

        for name, server in self.servers.items():
            output.append(f"## {name.upper()}\n")
            output.append(server.format_tools_for_ai())
            output.append("\n")

        return "\n".join(output)

    # =========================================================================
    # Function get_server_states -> None to Dict[str, MCPServerState]
    # =========================================================================
    def get_server_states(self) -> Dict[str, MCPServerState]:
        """Get states of all configured servers for UI display"""
        states = {}

        for name, config in self._server_configs.items():
            if name in self.servers:
                # ==================================
                # Get state from connected client
                states[name] = self.servers[name].get_state()
            else:
                # ==================================
                # Create disconnected state
                states[name] = MCPServerState(
                    config=config,
                    status=MCPConnectionStatus.DISCONNECTED,
                    tools=[],
                    error_message=None
                )

        return states

    # =========================================================================
    # Function get_server_tools -> str to List[Dict]
    # =========================================================================
    def get_server_tools(self, name: str) -> List[Dict]:
        """Get tools for a specific server"""
        if name in self.servers:
            return self.servers[name].get_available_tools()
        return []

    # =========================================================================
    # Function is_connected -> str to bool
    # =========================================================================
    def is_connected(self, name: str) -> bool:
        """Check if a server is connected"""
        return name in self.servers and self.servers[name].connected

    # =========================================================================
    # Function disconnect_all -> None to None
    # =========================================================================
    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        # ==================================
        # Disconnect each server and clear
        for name in list(self.servers.keys()):
            await self.disconnect_server(name)

    # =========================================================================
    # Function import_claude_desktop_config -> None to Tuple[int, str]
    # =========================================================================
    def import_claude_desktop_config(self) -> tuple[int, str]:
        """Import MCP servers from Claude Desktop config"""
        # ==================================
        # Get Claude Desktop config path
        config_path = self._get_claude_desktop_config_path()

        if not config_path or not config_path.exists():
            return 0, "Claude Desktop config not found"

        try:
            with open(config_path, 'r') as f:
                claude_config = json.load(f)

            imported = 0
            for name, server_data in claude_config.get("mcpServers", {}).items():
                if name not in self._server_configs:
                    # ==================================
                    # Add type field if missing (Claude Desktop uses STDIO)
                    if "type" not in server_data:
                        server_data["type"] = "stdio"

                    config = MCPServerConfig.from_dict(name, server_data)
                    self._server_configs[name] = config
                    imported += 1

            if imported > 0:
                self.save_config()

            return imported, f"Imported {imported} servers from Claude Desktop"

        except Exception as e:
            return 0, f"Error importing: {str(e)}"

    # =========================================================================
    # Function _get_claude_desktop_config_path -> None to Optional[Path]
    # =========================================================================
    def _get_claude_desktop_config_path(self) -> Optional[Path]:
        """Get path to Claude Desktop config file"""
        system = platform.system()

        if system == "Darwin":  # macOS
            return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
        elif system == "Windows":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                return Path(appdata) / "Claude/claude_desktop_config.json"
        else:  # Linux
            return Path.home() / ".config/Claude/claude_desktop_config.json"

        return None


# =============================================================================
'''
    Example Usage Section
'''
# =============================================================================

# =========================================================================
# Function main -> None to None
# =========================================================================
async def main():
    """Test MCP connection"""
    
    # ==================================
    # Example: Playwright MCP server
    playwright_config = {
        'command': 'npx',
        'args': ['-y', '@playwright/mcp-server'],
        'env': {}
    }
    
    client = MCPClient(playwright_config)
    
    try:
        # ==================================
        # Connect and list available tools
        await client.connect()
        
        print("\n📚 Available tools:")
        for tool in client.get_available_tools():
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        
        # ==================================
        # Example: Navigate to URL
        result = await client.call_tool(
            'playwright_navigate',
            {'url': 'https://example.com'}
        )
        print(f"\n✅ Navigation result: {result}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopping...")
    finally:
        # ==================================
        # Always disconnect
        await client.disconnect()


# =============================================================================
# Entry Point
# =============================================================================

# ==================================
# Run main function if executed directly
if __name__ == "__main__":
    asyncio.run(main())


# =============================================================================
'''
    End of File : mcp_client.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================
