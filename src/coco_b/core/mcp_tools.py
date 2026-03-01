# =============================================================================
'''
    File Name : mcp_tools.py

    Description : MCP Tool Integration for chat flow. Handles formatting tools
                  for LLM consumption, parsing tool calls from responses,
                  executing tools via MCP, and returning results.

    Modifying it on 2026-02-09

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.core.mcp_client import MCPManager

logger = logging.getLogger(__name__)


# =============================================================================
'''
    MCPToolHandler : Manages tool calling flow for LLM integration
'''
# =============================================================================

class MCPToolHandler:
    """Handles MCP tool integration with LLM chat flow"""

    # =========================================================================
    # Function __init__ -> MCPManager to None
    # =========================================================================
    def __init__(self, mcp_manager: "MCPManager"):
        """
        Initialize tool handler

        Args:
            mcp_manager: MCP manager instance with connected servers
        """
        self.mcp_manager = mcp_manager

    # =========================================================================
    # Function get_tools_prompt -> None to str
    # =========================================================================
    def get_tools_prompt(self) -> str:
        """
        Generate a MINIMAL prompt listing available MCP tools.
        Only includes server names and key tools to save tokens.

        Returns:
            Formatted string describing available tools (minimal)
        """
        all_tools = self.mcp_manager.get_all_tools()

        if not all_tools:
            return ""

        lines = [
            "\n---",
            "## Available Tools",
            "Call tools with: `{\"tool\": \"NAME\", \"server\": \"SERVER\", \"arguments\": {...}}`",
            "",
        ]

        for server_name, tools in all_tools.items():
            if not tools:
                continue

            # Just show server name and tool count, plus a few key tools
            tool_names = [t.get('name', '') for t in tools]
            key_tools = tool_names[:5]  # Show first 5 tools only

            if len(tool_names) > 5:
                lines.append(f"**{server_name}** ({len(tools)} tools): {', '.join(key_tools)}, ...")
            else:
                lines.append(f"**{server_name}**: {', '.join(key_tools)}")

        lines.append("")
        lines.append("Use `{\"tool\": \"list_tools\", \"server\": \"SERVER\"}` to see all tools.")
        lines.append("---")
        return "\n".join(lines)

    # =========================================================================
    # Function get_tool_info -> str to str
    # =========================================================================
    def get_tool_info(self, tool_name: str) -> str:
        """
        Get detailed information about a specific tool including full parameter schema.

        Args:
            tool_name: Name of the tool to get info for

        Returns:
            Formatted string with tool details and parameters
        """
        all_tools = self.mcp_manager.get_all_tools()

        for server_name, tools in all_tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    lines = [
                        f"## {tool_name} (server: {server_name})",
                        "",
                        f"**Description**: {tool.get('description', 'No description')}",
                        "",
                    ]

                    if "inputSchema" in tool:
                        schema = tool["inputSchema"]
                        props = schema.get("properties", {})
                        required = schema.get("required", [])

                        if props:
                            lines.append("**Parameters:**")
                            for prop_name, prop_info in props.items():
                                prop_type = prop_info.get("type", "any")
                                prop_desc = prop_info.get("description", "")
                                req = "(required)" if prop_name in required else "(optional)"
                                lines.append(f"- `{prop_name}` ({prop_type}) {req}: {prop_desc}")
                        else:
                            lines.append("**Parameters:** None")
                    else:
                        lines.append("**Parameters:** None")

                    lines.append("")
                    lines.append(f"**Usage:** `{{\"tool\": \"{tool_name}\", \"server\": \"{server_name}\", \"arguments\": {{...}}}}`")

                    return "\n".join(lines)

        return f"Tool '{tool_name}' not found. Use one of the available tools listed above."

    # =========================================================================
    # Function parse_tool_calls -> str to List[Dict]
    # =========================================================================
    def parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool call blocks from LLM response.

        Args:
            response: LLM response text

        Returns:
            List of parsed tool call dictionaries
        """
        tool_calls = []

        # Pattern to match ```tool_call ... ``` blocks
        pattern = r'```tool_call\s*([\s\S]*?)```'
        matches = re.findall(pattern, response, re.IGNORECASE)

        for match in matches:
            try:
                # Parse JSON from the block
                call_data = json.loads(match.strip())

                # Validate required fields
                if "tool" in call_data:
                    tool_calls.append({
                        "tool": call_data.get("tool"),
                        "server": call_data.get("server"),
                        "arguments": call_data.get("arguments", {}),
                    })
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse tool call: {e}")
                continue

        return tool_calls

    # =========================================================================
    # Function has_tool_calls -> str to bool
    # =========================================================================
    def has_tool_calls(self, response: str) -> bool:
        """Check if response contains tool call blocks"""
        return "```tool_call" in response.lower()

    # =========================================================================
    # Function execute_tool_call -> Dict to Tuple[bool, str]
    # =========================================================================
    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Execute a single tool call via MCP (sync - uses dedicated MCP event loop).

        Args:
            tool_call: Dictionary with tool, server, and arguments

        Returns:
            Tuple of (success, result_string)
        """
        tool_name = tool_call.get("tool")
        server_name = tool_call.get("server")
        arguments = tool_call.get("arguments", {})

        # Handle tool_info pseudo-command (returns tool schema)
        if tool_name == "tool_info":
            requested_tool = arguments.get("name", "")
            if requested_tool:
                return True, self.get_tool_info(requested_tool)
            else:
                return False, "Please specify tool name: {\"tool\": \"tool_info\", \"arguments\": {\"name\": \"tool_name\"}}"

        # If server not specified, find which server has this tool
        if not server_name:
            server_name = self._find_server_for_tool(tool_name)
            if not server_name:
                # Build list of available tools for helpful error
                available = []
                for srv, tools in self.mcp_manager.get_all_tools().items():
                    for t in tools:
                        available.append(f"{t.get('name')} (server: {srv})")
                available_list = ", ".join(available[:10])  # Show first 10
                return False, f"ERROR: Tool '{tool_name}' does NOT exist! This tool name was invented. Available tools: {available_list}. Use ONLY these exact tool names."

        # Check if server is connected
        if not self.mcp_manager.is_connected(server_name):
            return False, f"Server '{server_name}' is not connected. Please connect it first."

        try:
            logger.info(f"Executing tool: {tool_name} on {server_name} with args: {arguments}")

            # Use sync wrapper that runs in MCP's dedicated event loop
            result = self.mcp_manager.call_tool_sync(server_name, tool_name, arguments)

            # Format result for LLM
            if isinstance(result, dict):
                # Handle MCP result format
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list):
                        # Extract text from content array
                        texts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                texts.append(item["text"])
                            elif isinstance(item, str):
                                texts.append(item)
                        result_str = "\n".join(texts)
                    else:
                        result_str = str(content)
                else:
                    result_str = json.dumps(result, indent=2)
            else:
                result_str = str(result)

            return True, result_str

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return False, f"Error executing tool: {str(e)}"

    # =========================================================================
    # Function execute_all_tool_calls -> str to Tuple[str, List[Dict]]
    # =========================================================================
    def execute_all_tool_calls(self, response: str) -> Tuple[str, List[Dict]]:
        """
        Execute all tool calls in a response (sync - uses dedicated MCP event loop).

        Args:
            response: LLM response containing tool calls

        Returns:
            Tuple of (results_summary, list_of_results)
        """
        tool_calls = self.parse_tool_calls(response)
        results = []

        for call in tool_calls:
            success, result = self.execute_tool_call(call)
            results.append({
                "tool": call.get("tool"),
                "server": call.get("server"),
                "success": success,
                "result": result,
            })

        # Format results for LLM
        if not results:
            return "", results

        lines = ["## Tool Execution Results", ""]

        for r in results:
            status = "Success" if r["success"] else "Failed"
            lines.append(f"### {r['tool']} ({status})")
            lines.append("")
            lines.append("```")
            lines.append(r["result"])
            lines.append("```")
            lines.append("")

        return "\n".join(lines), results

    # =========================================================================
    # Function _find_server_for_tool -> str to Optional[str]
    # =========================================================================
    def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which server provides a tool"""
        all_tools = self.mcp_manager.get_all_tools()

        for server_name, tools in all_tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return server_name

        return None

    # =========================================================================
    # Function clean_response -> str to str
    # =========================================================================
    def clean_response(self, response: str) -> str:
        """Remove tool call blocks from response for display"""
        # Remove ```tool_call ... ``` blocks
        pattern = r'```tool_call\s*[\s\S]*?```'
        cleaned = re.sub(pattern, '', response, flags=re.IGNORECASE)

        # Clean up extra whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    # =========================================================================
    # Function get_connected_server_count -> None to int
    # =========================================================================
    def get_connected_server_count(self) -> int:
        """Get number of connected MCP servers"""
        return len(self.mcp_manager.servers)

    # =========================================================================
    # Function get_total_tool_count -> None to int
    # =========================================================================
    def get_total_tool_count(self) -> int:
        """Get total number of available tools"""
        all_tools = self.mcp_manager.get_all_tools()
        return sum(len(tools) for tools in all_tools.values())


# =============================================================================
# End of File
# =============================================================================
# Project : mr_bot - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
