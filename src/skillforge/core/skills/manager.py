# =============================================================================
'''
    File Name : manager.py
    
    Description : Skills Manager. Manages loading, saving, and organizing 
                  skills from multiple directories with priority-based 
                  resolution (user > project > bundled).
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Standard Library and Local Dependencies
# =============================================================================

from pathlib import Path
from typing import Dict, List, Optional
import shutil
import logging

from .loader import Skill, parse_skill_file, skill_to_markdown, find_skill_files

logger = logging.getLogger("skills.manager")


# =============================================================================
'''
    SkillsManager : Manages skills from multiple directories with priority 
                    resolution. Skills directories in priority order:
                    1. User skills: ~/.skillforge/skills/
                    2. Project skills: ./skills/
                    3. Bundled skills: <package>/skills/
'''
# =============================================================================

class SkillsManager:
    """Manages skills from multiple directories"""

    # =============================================================================
    # =========================================================================
    # Function __init__ -> Optional paths to None
    # =========================================================================
    # =============================================================================
    def __init__(
        self,
        bundled_dir: Optional[Path] = None,
        project_dir: Optional[Path] = None,
        user_dir: Optional[Path] = None
    ):
        """
        Initialize the skills manager.

        Args:
            bundled_dir: Directory for bundled skills (shipped with bot)
            project_dir: Directory for project-local skills
            user_dir: Directory for user's custom skills
        """
        # Default paths
        # ==================================
        if bundled_dir is None:
            from skillforge import PROJECT_ROOT
            bundled_dir = PROJECT_ROOT / "skills"

        # ==================================
        if project_dir is None:
            project_dir = Path.cwd() / "skills"

        # ==================================
        if user_dir is None:
            user_dir = Path.home() / ".skillforge" / "skills"

        self.bundled_dir = bundled_dir
        # Avoid loading same dir twice if project_dir resolves to bundled_dir
        if project_dir and bundled_dir and Path(project_dir).resolve() == Path(bundled_dir).resolve():
            self.project_dir = None
        else:
            self.project_dir = project_dir
        self.user_dir = user_dir

        # Allowed write directories (defense-in-depth)
        self._allowed_write_dirs = [d for d in [self.bundled_dir, self.project_dir, self.user_dir] if d]

        # Cache loaded skills
        self._skills: Dict[str, Skill] = {}
        self._loaded = False

    # =============================================================================
    # =========================================================================
    # Function _is_path_allowed -> Path to bool
    # =========================================================================
    # =============================================================================
    def _is_path_allowed(self, path: Path) -> bool:
        """
        Defense-in-depth: verify a write path is within known skill directories.

        Args:
            path: Path to check

        Returns:
            True if path is within an allowed skill directory
        """
        try:
            resolved = Path(path).resolve()
        except (ValueError, OSError):
            return False

        for allowed_dir in self._allowed_write_dirs:
            try:
                resolved.relative_to(allowed_dir.resolve())
                return True
            except ValueError:
                continue

        return False

    # =============================================================================
    # =========================================================================
    # Function load_all_skills -> None to List[Skill]
    # =========================================================================
    # =============================================================================
    def load_all_skills(self) -> List[Skill]:
        """
        Load all skills from all directories.

        Skills from higher-priority directories override lower-priority ones.

        Returns:
            List of loaded Skill objects
        """
        self._skills = {}

        # Load in priority order (lowest first, so higher priority overwrites)
        directories = [
            (self.bundled_dir, "bundled"),
            (self.project_dir, "project"),
            (self.user_dir, "user"),
        ]

        for directory, source in directories:
            # ==================================
            if directory is None or not directory.exists():
                continue

            skill_files = find_skill_files(directory)
            for skill_file in skill_files:
                skill = parse_skill_file(skill_file)
                # ==================================
                if skill:
                    skill.source = source
                    self._skills[skill.name] = skill
                    print(f"Loaded skill: {skill.name} ({source})")

        self._loaded = True
        return list(self._skills.values())

    # =============================================================================
    # =========================================================================
    # Function get_skills -> None to List[Skill]
    # =========================================================================
    # =============================================================================
    def get_skills(self) -> List[Skill]:
        """
        Get all loaded skills.

        Returns:
            List of Skill objects
        """
        # ==================================
        if not self._loaded:
            self.load_all_skills()
        return list(self._skills.values())

    # =============================================================================
    # =========================================================================
    # Function get_skill -> str to Optional[Skill]
    # =========================================================================
    # =============================================================================
    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill object if found, None otherwise
        """
        # ==================================
        if not self._loaded:
            self.load_all_skills()
        return self._skills.get(name)

    # =============================================================================
    # =========================================================================
    # Function get_user_invocable_skills -> None to List[Skill]
    # =========================================================================
    # =============================================================================
    def get_user_invocable_skills(self) -> List[Skill]:
        """
        Get all skills that can be invoked via /command.

        Returns:
            List of user-invocable Skill objects
        """
        return [s for s in self.get_skills() if s.user_invocable]

    # =============================================================================
    # =========================================================================
    # Function save_skill -> Skill, bool, Optional[str] to bool
    # =========================================================================
    # =============================================================================
    def save_skill(self, skill: Skill, save_as_new: bool = False, new_name: Optional[str] = None) -> bool:
        """
        Save a skill to disk.

        - If skill has a file_path and save_as_new is False, overwrites the file
        - If save_as_new is True, creates a new skill in user directory

        Args:
            skill: Skill object to save
            save_as_new: Whether to save as a new skill
            new_name: New name for the skill (required if save_as_new)

        Returns:
            True if successful
        """
        # ==================================
        if save_as_new:
            # ==================================
            if not new_name:
                print("Error: new_name required when saving as new skill")
                return False

            # Create in user directory
            skill_dir = self.user_dir / new_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            # Update skill with new name
            skill.name = new_name
            skill.source = "user"
            skill.file_path = str(skill_dir / "SKILL.md")

        # Determine save path
        # ==================================
        if skill.file_path:
            save_path = Path(skill.file_path)
        else:
            # Default to user directory
            skill_dir = self.user_dir / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)
            save_path = skill_dir / "SKILL.md"
            skill.file_path = str(save_path)

        # Check if we can write to this location
        # ==================================
        if skill.source == "bundled" and not save_as_new:
            # Can't overwrite bundled skills, save to user directory instead
            skill_dir = self.user_dir / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)
            save_path = skill_dir / "SKILL.md"
            skill.file_path = str(save_path)
            skill.source = "user"
            print(f"Bundled skill copied to user directory: {save_path}")

        # Defense-in-depth: verify path is inside allowed directories
        if not self._is_path_allowed(save_path):
            logger.warning(f"Blocked write to disallowed path: {save_path}")
            return False

        # Write skill content
        try:
            content = skill_to_markdown(skill)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(content, encoding='utf-8')

            # Update cache
            self._skills[skill.name] = skill

            print(f"Saved skill: {skill.name} to {save_path}")
            return True

        except Exception as e:
            print(f"Error saving skill: {e}")
            return False

    # =============================================================================
    # =========================================================================
    # Function delete_skill -> str to bool
    # =========================================================================
    # =============================================================================
    def delete_skill(self, name: str) -> bool:
        """
        Delete a skill.

        Note: Can only delete user skills, not bundled or project skills.

        Args:
            name: Skill name to delete

        Returns:
            True if successful
        """
        skill = self.get_skill(name)
        # ==================================
        if not skill:
            print(f"Skill not found: {name}")
            return False

        # ==================================
        if skill.source == "bundled":
            print("Cannot delete bundled skills")
            return False

        # ==================================
        if skill.source == "project":
            print("Cannot delete project skills (managed by project)")
            return False

        # Defense-in-depth: verify path is inside allowed directories
        if not self._is_path_allowed(Path(skill.file_path)):
            logger.warning(f"Blocked delete of disallowed path: {skill.file_path}")
            return False

        # Delete the skill file/directory
        try:
            skill_path = Path(skill.file_path)

            # Delete the directory if it only contains the skill
            skill_dir = skill_path.parent
            # ==================================
            if skill_dir.name == name:
                shutil.rmtree(skill_dir)
            else:
                skill_path.unlink()

            # Remove from cache
            del self._skills[name]

            print(f"Deleted skill: {name}")
            return True

        except Exception as e:
            print(f"Error deleting skill: {e}")
            return False

    # =============================================================================
    # =========================================================================
    # Function create_skill -> str, str, str, str, bool to Optional[Skill]
    # =========================================================================
    # =============================================================================
    def create_skill(
        self,
        name: str,
        description: str = "",
        instructions: str = "",
        emoji: str = "",
        user_invocable: bool = True
    ) -> Optional[Skill]:
        """
        Create a new skill in the user directory.

        Args:
            name: Skill name (used as directory name and /command)
            description: Short description
            instructions: Markdown instructions
            emoji: Optional emoji
            user_invocable: Whether this can be invoked via /command

        Returns:
            Created Skill object if successful
        """
        # Check if skill already exists
        # ==================================
        if name in self._skills:
            print(f"Skill already exists: {name}")
            return None

        # Create skill object
        skill = Skill(
            name=name,
            description=description,
            instructions=instructions,
            user_invocable=user_invocable,
            emoji=emoji,
            source="user",
        )

        # Save to user directory
        # ==================================
        if self.save_skill(skill):
            return skill
        return None

    # =============================================================================
    # =========================================================================
    # Function ensure_user_dir -> None to Path
    # =========================================================================
    # =============================================================================
    def ensure_user_dir(self) -> Path:
        """
        Ensure user skills directory exists.

        Returns:
            Path to user skills directory
        """
        self.user_dir.mkdir(parents=True, exist_ok=True)
        return self.user_dir

    # =============================================================================
    # =========================================================================
    # Function get_skill_sources -> None to Dict[str, str]
    # =========================================================================
    # =============================================================================
    def get_skill_sources(self) -> Dict[str, str]:
        """
        Get a mapping of skill names to their sources.

        Returns:
            Dict mapping skill name to source (bundled/project/user)
        """
        return {name: skill.source for name, skill in self._skills.items()}

    # =============================================================================
    # =========================================================================
    # Function reload -> None to None
    # =========================================================================
    # =============================================================================
    def reload(self):
        """Reload all skills from disk."""
        self._loaded = False
        self.load_all_skills()


# =============================================================================
'''
    End of File : manager.py
    
    Project : SkillForge - Persistent Memory AI Chatbot
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    License : Open Source - Safe Open Community Project
'''
# =============================================================================
