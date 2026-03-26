# =============================================================================
'''
    File Name : skill_creator_handler.py

    Description : Handler for parsing and executing create-skill commands from
                  LLM responses. Integrates with SkillsManager to create,
                  list, delete, and update user-defined skills via chat.

    Modifying it on 2026-02-16

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import re
import logging
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.skills.manager import SkillsManager

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("skill_creator_handler")


# =============================================================================
'''
    SkillCreatorHandler : Parses and executes create-skill commands from
                          LLM responses in ```create-skill``` code blocks.
'''
# =============================================================================
class SkillCreatorHandler:
    """
    Handles create-skill commands embedded in LLM responses.

    Parses code blocks like:
    ```create-skill
    ACTION: create
    NAME: dad-jokes
    DESCRIPTION: Tell random dad jokes on demand
    EMOJI: 😄
    INSTRUCTIONS:
    When invoked, tell a creative dad joke.
    ```
    """

    # Pattern to find create-skill code blocks
    SKILL_BLOCK_PATTERN = re.compile(
        r'```create-skill\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    # =========================================================================
    # Function __init__ -> Optional[SkillsManager] to None
    # =========================================================================
    def __init__(self, skills_manager: Optional["SkillsManager"] = None):
        """
        Initialize the skill creator handler.

        Args:
            skills_manager: The skills manager to create/delete skills
        """
        self.skills_manager = skills_manager

    # =========================================================================
    # Function set_skills_manager -> SkillsManager to None
    # =========================================================================
    def set_skills_manager(self, skills_manager: "SkillsManager"):
        """Set or update the skills manager"""
        self.skills_manager = skills_manager

    # =========================================================================
    # Function has_skill_commands -> str to bool
    # =========================================================================
    def has_skill_commands(self, response: str) -> bool:
        """
        Check if response contains create-skill commands.

        Args:
            response: LLM response text

        Returns:
            True if create-skill commands found
        """
        return bool(self.SKILL_BLOCK_PATTERN.search(response))

    # =========================================================================
    # Function parse_skill_block -> str to Dict[str, str]
    # =========================================================================
    def parse_skill_block(self, block_content: str) -> Dict[str, str]:
        """
        Parse a create-skill block into key-value pairs.

        Args:
            block_content: Content inside ```create-skill``` block

        Returns:
            Dictionary of parsed values
        """
        result = {}
        current_key = None
        current_value = []

        for line in block_content.strip().split('\n'):
            line = line.strip()
            if not line:
                if current_key == 'INSTRUCTIONS':
                    current_value.append('')
                continue

            # Check for KEY: VALUE pattern
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().upper()
                value = parts[1].strip() if len(parts) > 1 else ""

                # Common keys we expect
                if key in ['ACTION', 'NAME', 'DESCRIPTION', 'EMOJI', 'INSTRUCTIONS']:
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
        Extract all create-skill commands from response.

        Args:
            response: LLM response text

        Returns:
            List of parsed command dictionaries
        """
        commands = []
        matches = self.SKILL_BLOCK_PATTERN.findall(response)

        for match in matches:
            parsed = self.parse_skill_block(match)
            if parsed.get('ACTION'):
                commands.append(parsed)

        return commands

    # =========================================================================
    # Function execute_commands -> str to Tuple[str, list]
    # =========================================================================
    async def execute_commands(self, response: str) -> Tuple[str, list]:
        """
        Execute all create-skill commands in response.

        Args:
            response: LLM response text

        Returns:
            Tuple of (cleaned response, list of execution results)
        """
        if not self.skills_manager:
            logger.warning("No skills manager available")
            return response, []

        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            action = cmd.get('ACTION', '').lower()
            result = None

            try:
                if action == 'create':
                    result = self._handle_create(cmd)
                elif action == 'list':
                    result = self._handle_list()
                elif action == 'delete':
                    result = self._handle_delete(cmd)
                elif action == 'update':
                    result = self._handle_update(cmd)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}

            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Skill creator error: {e}", exc_info=True)

            if result:
                results.append(result)

        # Clean create-skill blocks from response for display
        cleaned = self.SKILL_BLOCK_PATTERN.sub('', response).strip()

        # Add execution results to response
        if results:
            result_text = self._format_results(results)
            if result_text:
                cleaned = cleaned + "\n\n" + result_text

        return cleaned, results

    # =========================================================================
    # Function _handle_create -> Dict to Dict
    # =========================================================================
    def _handle_create(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle create action"""
        name = cmd.get('NAME', '').strip()
        description = cmd.get('DESCRIPTION', '').strip()
        emoji = cmd.get('EMOJI', '').strip()
        instructions = cmd.get('INSTRUCTIONS', '').strip()

        if not name:
            return {"success": False, "error": "No skill name specified"}

        if not instructions:
            return {"success": False, "error": "No instructions specified"}

        skill = self.skills_manager.create_skill(
            name=name,
            description=description,
            instructions=instructions,
            emoji=emoji,
            user_invocable=True,
        )

        if skill:
            self.skills_manager.reload()
            return {
                "success": True,
                "action": "create",
                "name": name,
                "description": description,
            }
        else:
            return {"success": False, "error": f"Failed to create skill '{name}'"}

    # =========================================================================
    # Function _handle_list -> None to Dict
    # =========================================================================
    def _handle_list(self) -> Dict[str, Any]:
        """Handle list action"""
        skills = self.skills_manager.get_user_invocable_skills()
        skill_list = [
            {
                "name": s.name,
                "description": s.description,
                "emoji": s.emoji,
                "source": s.source,
            }
            for s in skills
        ]

        return {
            "success": True,
            "action": "list",
            "skills": skill_list,
            "total": len(skill_list),
        }

    # =========================================================================
    # Function _handle_delete -> Dict to Dict
    # =========================================================================
    def _handle_delete(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle delete action"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No skill name specified"}

        success = self.skills_manager.delete_skill(name)
        if success:
            self.skills_manager.reload()
        return {
            "success": success,
            "action": "delete",
            "name": name,
            "error": None if success else f"Could not delete skill '{name}' (may be bundled or not found)",
        }

    # =========================================================================
    # Function _handle_update -> Dict to Dict
    # =========================================================================
    def _handle_update(self, cmd: Dict[str, str]) -> Dict[str, Any]:
        """Handle update action (delete + recreate)"""
        name = cmd.get('NAME', '').strip()
        if not name:
            return {"success": False, "error": "No skill name specified"}

        # Check skill exists
        existing = self.skills_manager.get_skill(name)
        if not existing:
            return {"success": False, "error": f"Skill '{name}' not found"}

        if existing.source == "bundled":
            return {"success": False, "error": f"Cannot update bundled skill '{name}'"}

        # Delete then recreate
        self.skills_manager.delete_skill(name)

        description = cmd.get('DESCRIPTION', existing.description).strip()
        emoji = cmd.get('EMOJI', existing.emoji).strip()
        instructions = cmd.get('INSTRUCTIONS', existing.instructions).strip()

        skill = self.skills_manager.create_skill(
            name=name,
            description=description,
            instructions=instructions,
            emoji=emoji,
            user_invocable=True,
        )

        if skill:
            self.skills_manager.reload()
            return {
                "success": True,
                "action": "update",
                "name": name,
            }
        else:
            return {"success": False, "error": f"Failed to update skill '{name}'"}

    # =========================================================================
    # Function _format_results -> list to str
    # =========================================================================
    def _format_results(self, results: list) -> str:
        """Format execution results for display"""
        lines = []

        for result in results:
            action = result.get('action', 'unknown')
            success = result.get('success', False)

            if not success:
                error = result.get('error', 'Unknown error')
                lines.append(f"**Error**: {error}")
                continue

            if action == 'create':
                name = result.get('name', '')
                lines.append(f"**Skill Created**: `/{name}`")

            elif action == 'list':
                skills = result.get('skills', [])
                if not skills:
                    lines.append("**No skills found.**")
                else:
                    lines.append(f"**Available Skills** ({len(skills)} total):")
                    for s in skills:
                        emoji = f"{s['emoji']} " if s.get('emoji') else ""
                        source = f" ({s['source']})" if s.get('source') else ""
                        lines.append(f"- **/{s['name']}** - {emoji}{s.get('description', '')}{source}")

            elif action == 'delete':
                name = result.get('name', '')
                lines.append(f"**Skill Deleted**: `/{name}`")

            elif action == 'update':
                name = result.get('name', '')
                lines.append(f"**Skill Updated**: `/{name}`")

        return '\n'.join(lines)


# =============================================================================
'''
    End of File : skill_creator_handler.py

    Project : SkillForge - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
