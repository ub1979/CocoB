# =============================================================================
'''
    File Name : loader.py
    
    Description : SKILL.md File Loader. Parses SKILL.md files with YAML 
                  frontmatter and markdown body to load skill definitions.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section - Standard Library and Third-Party Dependencies
# =============================================================================

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

# =============================================================================
'''
    Skill : Represents a loaded skill with metadata and instructions
'''
# =============================================================================

@dataclass
class Skill:
    """Represents a loaded skill"""
    name: str
    description: str
    instructions: str  # Markdown body
    user_invocable: bool = True  # Show as /command
    emoji: str = ""
    source: str = ""  # "bundled", "project", "user", or "clawhub"
    file_path: str = ""  # For editing
    version: str = ""  # semver from ClawHub
    author: str = ""  # ClawHub author handle
    clawhub_slug: str = ""  # original slug for updates

    # =============================================================================
    # =========================================================================
    # Function get_display_name -> None to str
    # =========================================================================
    # =============================================================================
    def get_display_name(self) -> str:
        """Get display name with emoji"""
        # ==================================
        if self.emoji:
            return f"{self.emoji} {self.name}"
        return self.name

    # =============================================================================
    # =========================================================================
    # Function to_dict -> None to Dict[str, Any]
    # =========================================================================
    # =============================================================================
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        d = {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "user_invocable": self.user_invocable,
            "emoji": self.emoji,
            "source": self.source,
            "file_path": self.file_path,
        }
        if self.version:
            d["version"] = self.version
        if self.author:
            d["author"] = self.author
        if self.clawhub_slug:
            d["clawhub_slug"] = self.clawhub_slug
        return d


# =============================================================================
# YAML Frontmatter Pattern - Regex for parsing YAML frontmatter
# =============================================================================

# YAML frontmatter pattern: starts with ---, ends with ---
FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n',
    re.DOTALL
)

# =============================================================================
# =========================================================================
# Function parse_skill_file -> Path to Optional[Skill]
# =========================================================================
# =============================================================================

def parse_skill_file(file_path: Path) -> Optional[Skill]:
    """
    Parse a SKILL.md file into a Skill object.

    Args:
        file_path: Path to the SKILL.md file

    Returns:
        Skill object if parsing succeeds, None otherwise
    """
    # ==================================
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading skill file {file_path}: {e}")
        return None

    return parse_skill_content(content, str(file_path))


# =============================================================================
# =========================================================================
# Function parse_skill_content -> str, str to Optional[Skill]
# =========================================================================
# =============================================================================

def parse_skill_content(content: str, file_path: str = "") -> Optional[Skill]:
    """
    Parse skill content (YAML frontmatter + markdown body).

    Args:
        content: Full content of the skill file
        file_path: Optional path for reference

    Returns:
        Skill object if parsing succeeds, None otherwise
    """
    # Match frontmatter
    match = FRONTMATTER_PATTERN.match(content)

    # ==================================
    if not match:
        print(f"No valid frontmatter found in skill: {file_path}")
        return None

    frontmatter_text = match.group(1)
    body = content[match.end():].strip()

    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"YAML parse error in skill {file_path}: {e}")
        return None

    # ==================================
    if not isinstance(frontmatter, dict):
        print(f"Invalid frontmatter format in skill: {file_path}")
        return None

    # Extract required fields
    name = frontmatter.get('name')
    # ==================================
    if not name:
        print(f"Missing 'name' in skill: {file_path}")
        return None

    description = frontmatter.get('description', '')
    user_invocable = frontmatter.get('user-invocable', True)
    emoji = frontmatter.get('emoji', '')

    # Clean emoji (remove quotes if present)
    # ==================================
    if isinstance(emoji, str):
        emoji = emoji.strip('"\'')

    return Skill(
        name=name,
        description=description,
        instructions=body,
        user_invocable=user_invocable,
        emoji=emoji,
        file_path=file_path,
    )


# =============================================================================
# =========================================================================
# Function skill_to_markdown -> Skill to str
# =========================================================================
# =============================================================================

def skill_to_markdown(skill: Skill) -> str:
    """
    Convert a Skill object back to SKILL.md format.

    Args:
        skill: Skill object to convert

    Returns:
        Markdown string with YAML frontmatter
    """
    # Build frontmatter
    frontmatter = {
        'name': skill.name,
        'description': skill.description,
        'user-invocable': skill.user_invocable,
    }

    # ==================================
    if skill.emoji:
        frontmatter['emoji'] = f'"{skill.emoji}"'

    # Convert to YAML
    yaml_content = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )

    # Build full content
    return f"---\n{yaml_content}---\n\n{skill.instructions}"


# =============================================================================
# =========================================================================
# Function find_skill_files -> Path to list[Path]
# =========================================================================
# =============================================================================

def find_skill_files(directory: Path) -> list[Path]:
    """
    Find all SKILL.md files in a directory (recursive).

    Args:
        directory: Directory to search

    Returns:
        List of paths to SKILL.md files
    """
    # ==================================
    if not directory.exists():
        return []

    skill_files = []

    # Look for SKILL.md in subdirectories (e.g., skills/commit/SKILL.md)
    for subdir in directory.iterdir():
        # ==================================
        if subdir.is_dir():
            skill_file = subdir / "SKILL.md"
            # ==================================
            if skill_file.exists():
                skill_files.append(skill_file)

    # Also look for SKILL.md directly in the directory
    direct_skill = directory / "SKILL.md"
    # ==================================
    if direct_skill.exists():
        skill_files.append(direct_skill)

    return skill_files


# =============================================================================
# =========================================================================
# Function parse_openclaw_skill_content -> str, str, str to Optional[Skill]
# =========================================================================
# =============================================================================

def parse_openclaw_skill_content(content: str, file_path: str = "", base_dir: str = "") -> Optional[Skill]:
    """
    Parse OpenClaw.ai skill content into a coco B Skill object.

    OpenClaw format differences:
    - emoji lives under metadata.openclaw.emoji (not top-level)
    - Has version, author fields
    - Instructions may use {baseDir} placeholder
    - May have requires.bins / requires.env (warned but ignored)

    Args:
        content: Full content of the skill file
        file_path: Optional path for reference
        base_dir: Directory where the skill is installed (replaces {baseDir})

    Returns:
        Skill object if parsing succeeds, None otherwise
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        print(f"No valid frontmatter found in OpenClaw skill: {file_path}")
        return None

    frontmatter_text = match.group(1)
    body = content[match.end():].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        print(f"YAML parse error in OpenClaw skill {file_path}: {e}")
        return None

    if not isinstance(frontmatter, dict):
        print(f"Invalid frontmatter format in OpenClaw skill: {file_path}")
        return None

    name = frontmatter.get('name')
    if not name:
        print(f"Missing 'name' in OpenClaw skill: {file_path}")
        return None

    description = frontmatter.get('description', '')
    user_invocable = frontmatter.get('user-invocable', frontmatter.get('user_invocable', True))
    version = str(frontmatter.get('version', ''))
    author = str(frontmatter.get('author', ''))

    # Extract emoji from metadata.openclaw.emoji (OpenClaw nesting)
    emoji = ''
    metadata = frontmatter.get('metadata', {})
    if isinstance(metadata, dict):
        openclaw = metadata.get('openclaw', {})
        if isinstance(openclaw, dict):
            emoji = openclaw.get('emoji', '')
    # Fallback to top-level emoji if not in metadata
    if not emoji:
        emoji = frontmatter.get('emoji', '')
    if isinstance(emoji, str):
        emoji = emoji.strip('"\'')

    # Warn about requirements (but don't fail)
    requires = frontmatter.get('requires', {})
    if isinstance(requires, dict):
        if requires.get('bins'):
            print(f"[clawhub] Skill '{name}' requires binaries: {requires['bins']} (not checked)")
        if requires.get('env'):
            print(f"[clawhub] Skill '{name}' requires env vars: {requires['env']} (not checked)")

    # Replace {baseDir} placeholder in instructions
    if base_dir and '{baseDir}' in body:
        body = body.replace('{baseDir}', base_dir)

    return Skill(
        name=name,
        description=description,
        instructions=body,
        user_invocable=user_invocable,
        emoji=emoji,
        source="clawhub",
        file_path=file_path,
        version=version,
        author=author,
    )


# =============================================================================
'''
    End of File : loader.py
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    License : Open Source - Safe Open Community Project
'''
# =============================================================================
