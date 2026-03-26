# =============================================================================
'''
    File Name : image_gen_handler.py

    Description : Handler for parsing and executing image generation commands
                  from LLM responses. Delegates to MCP tools (e.g., DALL-E,
                  Stable Diffusion) for actual generation. Follows the
                  schedule_handler.py code-block handler pattern.

    Created on 2026-03-19

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import re
import logging
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.mcp_client import MCPManager

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("image_gen_handler")

# =============================================================================
# Constants
# =============================================================================
SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9_.\-]')

# Known image generation tool names across common MCP servers
IMAGE_GEN_TOOL_NAMES = {
    "generate_image",
    "create_image",
    "text_to_image",
    "image_generation",
    "dalle_generate",
    "generate",
}

# Default values
DEFAULT_SIZE = "1024x1024"
DEFAULT_PROVIDER = "auto"


# =============================================================================
'''
    ImageGenHandler : Parses and executes image generation commands from
                      LLM responses in ```image_gen``` code blocks.
'''
# =============================================================================
class ImageGenHandler:
    """
    Handles image generation commands embedded in LLM responses.

    Parses code blocks like:
    ```image_gen
    ACTION: generate
    PROMPT: A beautiful sunset over mountains
    STYLE: realistic
    SIZE: 1024x1024
    PROVIDER: dall-e
    ```
    """

    # Pattern to find image_gen code blocks
    IMAGE_GEN_BLOCK_PATTERN = re.compile(
        r'```image_gen\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> Optional[MCPManager] to None
    # =========================================================================
    def __init__(self, mcp_manager: Optional["MCPManager"] = None):
        """
        Initialize the image generation handler.

        Args:
            mcp_manager: Optional MCP manager for tool integration.
                         If not provided, image generation will return
                         guidance on how to configure a provider.
        """
        self.mcp_manager = mcp_manager

    # =========================================================================
    # Function set_mcp_manager -> MCPManager to None
    # =========================================================================
    def set_mcp_manager(self, mcp_manager: "MCPManager"):
        """Set or update the MCP manager."""
        self.mcp_manager = mcp_manager

    # =========================================================================
    # Function has_image_gen_commands -> str to bool
    # =========================================================================
    def has_image_gen_commands(self, response: str) -> bool:
        """
        Check if response contains image_gen commands.

        Args:
            response: LLM response text

        Returns:
            True if image_gen commands found
        """
        return bool(self.IMAGE_GEN_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_block -> str to Dict[str, str]
    # =========================================================================
    def parse_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse an image_gen block into key-value pairs.

        Args:
            block_content: Content inside ```image_gen``` block

        Returns:
            Dictionary of parsed values
        """
        result = {}
        current_key = None
        current_value = []

        for line in block_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Check for KEY: VALUE pattern
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().upper()
                value = parts[1].strip() if len(parts) > 1 else ""

                # Common keys we expect
                if key in ['ACTION', 'PROMPT', 'STYLE', 'SIZE',
                           'PROVIDER', 'NEGATIVE_PROMPT', 'COUNT']:
                    # Save previous key if exists
                    if current_key:
                        result[current_key] = '\n'.join(current_value).strip()

                    current_key = key
                    current_value = [value] if value else []
                else:
                    # Continuation of previous value
                    if current_key:
                        current_value.append(line)
            else:
                # Continuation of previous value
                if current_key:
                    current_value.append(line)

        # Save last key
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()

        return result

    # =========================================================================
    # Function extract_commands -> str to list
    # =========================================================================
    def extract_commands(self, response: str) -> list:
        """
        Extract all image_gen commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.IMAGE_GEN_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_block(match)
            # A prompt is the minimum required field
            if parsed.get('PROMPT'):
                commands.append(parsed)

        return commands

    # =========================================================================
    # Function execute_commands -> str, str, str, str to Tuple[str, list]
    # =========================================================================
    async def execute_commands(
        self,
        response: str,
        channel: str,
        user_id: str,
        session_key: str,
    ) -> Tuple[str, list]:
        """
        Execute all image_gen commands in response.

        Args:
            response: LLM response text
            channel: Channel name
            user_id: User ID
            session_key: Session key for image storage

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            result = None

            try:
                action = cmd.get('ACTION', 'generate').lower()
                if action in ('generate', 'create'):
                    result = await self._handle_generate(
                        cmd, channel, user_id, session_key,
                    )
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Image gen command error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean image_gen blocks from response for display
        cleaned = self.IMAGE_GEN_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_generate -> Dict, str, str, str to Dict
    # =========================================================================
    async def _handle_generate(
        self,
        cmd: Dict[str, str],
        channel: str,
        user_id: str,
        session_key: str,
    ) -> Dict[str, Any]:
        """
        Handle image generation via MCP tools.

        Args:
            cmd: Parsed command dictionary with PROMPT, STYLE, SIZE, PROVIDER
            channel: Channel name
            user_id: User ID
            session_key: Session key for image storage

        Returns:
            Result dictionary with success status and image path or error
        """
        prompt = cmd.get('PROMPT', '').strip()
        if not prompt:
            return {"success": False, "error": "No prompt specified for image generation."}

        style = cmd.get('STYLE', '').strip()
        size = cmd.get('SIZE', DEFAULT_SIZE).strip()
        provider = cmd.get('PROVIDER', DEFAULT_PROVIDER).strip()
        negative_prompt = cmd.get('NEGATIVE_PROMPT', '').strip()

        # Build the full prompt with style if specified
        full_prompt = prompt
        if style:
            full_prompt = f"{prompt}, {style} style"

        # Try MCP tool for image generation
        if self.mcp_manager:
            gen_result = self._try_mcp_generation(
                full_prompt, size, provider, negative_prompt,
            )
            if gen_result and gen_result.get("success"):
                # Save image if we got a path/URL back
                image_path = gen_result.get("image_path", "")
                image_url = gen_result.get("image_url", "")

                return {
                    "success": True,
                    "action": "generate",
                    "prompt": prompt,
                    "style": style,
                    "size": size,
                    "provider": provider,
                    "image_path": image_path,
                    "image_url": image_url,
                }

        # No MCP provider available — return guidance
        return {
            "success": False,
            "error": (
                "No image generation provider available. "
                "To enable image generation, configure a DALL-E or "
                "Stable Diffusion MCP server:\n"
                "1. Install an image generation MCP server "
                "(e.g., `@mcp/dalle`, `@mcp/stable-diffusion`)\n"
                "2. Connect it via the Tools tab or `/mcp connect` command\n"
                "3. The LLM will automatically use it for image generation"
            ),
        }

    # =========================================================================
    # Function _try_mcp_generation -> str, str, str, str to Optional[Dict]
    # =========================================================================
    def _try_mcp_generation(
        self,
        prompt: str,
        size: str,
        provider: str,
        negative_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt image generation via an MCP tool.

        Searches connected MCP servers for an image generation tool and
        calls it with the given parameters.

        Args:
            prompt: Full prompt for image generation
            size: Image size (e.g., "1024x1024")
            provider: Preferred provider/server name ("auto" to search all)
            negative_prompt: Negative prompt for exclusions

        Returns:
            Result dict with image path/URL, or None if no tool found
        """
        if not self.mcp_manager:
            return None

        try:
            all_tools = self.mcp_manager.get_all_tools()
        except Exception as e:
            logger.warning(f"Failed to get MCP tools: {e}")
            return None

        if not all_tools:
            return None

        # Find an image generation tool
        target_server = None
        target_tool = None

        for server_name, tools in all_tools.items():
            # If provider is specified (not "auto"), prefer that server
            if provider != DEFAULT_PROVIDER and provider.lower() != server_name.lower():
                continue

            for tool in tools:
                tool_name = tool.get('name', '').lower()
                if tool_name in IMAGE_GEN_TOOL_NAMES:
                    target_server = server_name
                    target_tool = tool.get('name')
                    break

            if target_tool:
                break

        # If provider-specific search failed, search all servers
        if not target_tool and provider != DEFAULT_PROVIDER:
            for server_name, tools in all_tools.items():
                for tool in tools:
                    tool_name = tool.get('name', '').lower()
                    if tool_name in IMAGE_GEN_TOOL_NAMES:
                        target_server = server_name
                        target_tool = tool.get('name')
                        break
                if target_tool:
                    break

        if not target_tool or not target_server:
            return None

        # Build arguments for the tool call
        arguments = {"prompt": prompt, "size": size}
        if negative_prompt:
            arguments["negative_prompt"] = negative_prompt

        try:
            logger.info(
                f"Calling MCP image gen: {target_tool} on {target_server}"
            )
            result = self.mcp_manager.call_tool_sync(
                target_server, target_tool, arguments,
            )

            # Extract image path or URL from result
            if isinstance(result, dict):
                image_path = result.get("path", result.get("file_path", ""))
                image_url = result.get("url", result.get("image_url", ""))
                return {
                    "success": True,
                    "image_path": image_path,
                    "image_url": image_url,
                }
            elif isinstance(result, str):
                # Result might be a path or URL directly
                if result.startswith(("http://", "https://")):
                    return {"success": True, "image_url": result, "image_path": ""}
                else:
                    return {"success": True, "image_path": result, "image_url": ""}

            return {"success": True, "image_path": "", "image_url": ""}

        except Exception as e:
            logger.warning(f"MCP image gen failed: {e}")
            return None

    # =========================================================================
    # Function format_response -> str, str to str
    # =========================================================================
    def format_response(self, image_path: str, prompt: str) -> str:
        """
        Format a response with the generated image path.

        Args:
            image_path: Path to the generated image
            prompt: Original prompt used for generation

        Returns:
            Formatted response string
        """
        if image_path:
            return (
                f"**Image Generated**\n"
                f"- Prompt: {prompt}\n"
                f"- Saved to: `{image_path}`"
            )
        return f"**Image Generated** from prompt: {prompt}"

    # =========================================================================
    # Function _format_results -> list to str
    # =========================================================================
    def _format_results(self, results: list) -> str:
        """Format execution results for display."""
        lines = []

        for result in results:
            success = result.get('success', False)

            if not success:
                error = result.get('error', 'Unknown error')
                lines.append(f"**Image Generation Error**: {error}")
                continue

            prompt = result.get('prompt', '')
            image_path = result.get('image_path', '')
            image_url = result.get('image_url', '')
            style = result.get('style', '')
            size = result.get('size', '')

            lines.append(f"**Image Generated**")
            lines.append(f"- Prompt: {prompt}")
            if style:
                lines.append(f"- Style: {style}")
            if size:
                lines.append(f"- Size: {size}")
            if image_path:
                lines.append(f"- Saved to: `{image_path}`")
            if image_url:
                lines.append(f"- URL: {image_url}")

        return '\n'.join(lines)


# =============================================================================
# Convenience function
# =============================================================================

def create_image_gen_handler(
    mcp_manager: Optional["MCPManager"] = None,
) -> ImageGenHandler:
    """Create an image generation handler."""
    return ImageGenHandler(mcp_manager=mcp_manager)


# =============================================================================
'''
    End of File : image_gen_handler.py

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
