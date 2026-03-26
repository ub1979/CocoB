# =============================================================================
'''
    File Name : personality.py
    
    Description : Personality & Mood Management module for SkillForge. Handles loading
    personality from PERSONALITY.md, reading and updating MOODS.md based on 
    conversations, learning new traits in NEW_PERSONALITY.md, loading skills 
    (prompt templates) for specialized tasks, and providing mood-aware context 
    to the AI.
    
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
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json
import logging
import re

import yaml

# =============================================================================
# Setup logging for security and debugging
# =============================================================================
logger = logging.getLogger(__name__)

FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)$', re.DOTALL)
# =============================================================================


# =============================================================================
'''
    Persona : Data class representing a single persona/agent profile
'''
# =============================================================================
@dataclass
class Persona:
    """A persona/agent profile that modifies bot behavior per-user or per-channel."""
    name: str
    description: str
    emoji: str
    instructions: str  # markdown body after frontmatter
    file_path: Path


# =============================================================================
'''
    PersonalityManager : Manages bot personality, moods, learned behaviors, and skills
'''
# =============================================================================
class PersonalityManager:
    """Manages bot personality, moods, learned behaviors, and skills"""

    # =========================================================================
    # =========================================================================
    # Function __init__ -> Optional[Path], Optional[SkillsManager] to None
    # =========================================================================
    # =========================================================================
    def __init__(self, base_path: Optional[Path] = None, skills_manager=None):
        # ==================================
        if base_path is None:
            from skillforge import PROJECT_ROOT
            base_path = PROJECT_ROOT / "data" / "personality"

        self.base_path = base_path
        self.personality_file = base_path / "PERSONALITY.md"
        self.moods_file = base_path / "MOODS.md"
        self.new_personality_file = base_path / "NEW_PERSONALITY.md"
        self._skills_manager = skills_manager

        # Persona system
        self.agents_dir = base_path / "agents"
        self.profiles_file = base_path / "user_profiles.json"
        self._personas: Dict[str, Persona] = {}
        self._user_profiles: Dict = {"user_personas": {}, "channel_defaults": {}}
        self.load_personas()
        self._load_user_profiles()
    
    # =========================================================================
    # =========================================================================
    # Function skills_manager (property getter) -> None to SkillsManager
    # =========================================================================
    # =========================================================================
    @property
    def skills_manager(self):
        """Lazy-load skills manager if not provided"""
        # ==================================
        if self._skills_manager is None:
            try:
                from skillforge.core.skills import SkillsManager
                self._skills_manager = SkillsManager()
                self._skills_manager.load_all_skills()
            # ==================================
            # Log warning instead of silent failure for better debugging
            # ==================================
            except ImportError as e:
                logger.warning(f"SkillsManager not available: {e}")
                self._skills_manager = None
        # ==================================
        # Return the skills manager (may be None if loading failed)
        # ==================================
        return self._skills_manager

    # =========================================================================
    # =========================================================================
    # Function skills_manager (property setter) -> SkillsManager to None
    # =========================================================================
    # =========================================================================
    @skills_manager.setter
    def skills_manager(self, manager):
        """Set skills manager"""
        self._skills_manager = manager

    # =========================================================================
    # =========================================================================
    # Function get_system_prompt -> None to str
    # =========================================================================
    # =========================================================================
    def get_system_prompt(self, mode: str = "full", user_id: Optional[str] = None, channel: Optional[str] = None) -> str:
        """
        Build system prompt with configurable verbosity (OpenClaw-style).

        Modes:
            - "full": Complete prompt with personality + persona override + skills list
            - "minimal": Just core identity (for sub-agents)
            - "none": Bare minimum identity

        Args:
            mode: Prompt verbosity level
            user_id: Optional user ID for persona resolution
            channel: Optional channel name for persona resolution
        """
        # ==================================
        # Mode: none - absolute minimum
        # ==================================
        if mode == "none":
            return "You are SkillForge, a helpful AI assistant. Be direct and concise."

        # ==================================
        # Mode: minimal - core identity only
        # ==================================
        if mode == "minimal":
            return self._default_personality()

        # ==================================
        # Mode: full - personality + persona + skills list
        # ==================================
        parts = []

        # 1. Load base personality (truncate if > 3000 chars)
        if self.personality_file.exists():
            with open(self.personality_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > 3000:
                    content = content[:3000] + "\n...[truncated]"
                parts.append(content)
        else:
            parts.append(self._default_personality())

        # 2. Resolve and apply persona override
        persona = self.resolve_persona(user_id, channel)
        if persona and persona.name != "default":
            parts.append(f"\n\n---\n## Persona Override: {persona.emoji} {persona.name}\n{persona.instructions}")

        # 3. Brief skills list (names only, not full instructions)
        if self.skills_manager:
            skills = self.skills_manager.get_user_invocable_skills()
            if skills:
                skill_list = ", ".join([f"/{s.name}" for s in skills[:8]])
                parts.append(f"\n\nSkills: {skill_list}. Invoke with /name.")

        return "\n".join(parts)

    # =========================================================================
    # Persona management methods
    # =========================================================================
    def load_personas(self) -> Dict[str, Persona]:
        """Load all persona files from agents/ directory."""
        self._personas = {}
        if not self.agents_dir.exists():
            return self._personas

        for md_file in sorted(self.agents_dir.glob("*.md")):
            try:
                persona = self._parse_persona_file(md_file)
                if persona:
                    self._personas[persona.name] = persona
            except Exception as e:
                logger.warning(f"Failed to parse persona {md_file.name}: {e}")
        return self._personas

    def _parse_persona_file(self, file_path: Path) -> Optional[Persona]:
        """Parse a persona markdown file with YAML frontmatter."""
        content = file_path.read_text(encoding='utf-8')
        match = FRONTMATTER_PATTERN.match(content)
        if not match:
            logger.warning(f"No valid frontmatter in {file_path.name}")
            return None

        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in {file_path.name}: {e}")
            return None

        if not isinstance(meta, dict) or 'name' not in meta:
            logger.warning(f"Missing 'name' field in {file_path.name}")
            return None

        return Persona(
            name=meta['name'],
            description=meta.get('description', ''),
            emoji=meta.get('emoji', ''),
            instructions=match.group(2).strip(),
            file_path=file_path,
        )

    def get_personas(self) -> Dict[str, Persona]:
        """Return all loaded personas."""
        return dict(self._personas)

    def get_persona(self, name: str) -> Optional[Persona]:
        """Look up a single persona by name."""
        return self._personas.get(name)

    def resolve_persona(self, user_id: Optional[str] = None, channel: Optional[str] = None) -> Optional[Persona]:
        """Resolve which persona applies: user override > channel default > None."""
        # User-specific override takes priority
        if user_id:
            persona_name = self._user_profiles.get("user_personas", {}).get(user_id)
            if persona_name and persona_name in self._personas:
                return self._personas[persona_name]

        # Channel default is fallback
        if channel:
            persona_name = self._user_profiles.get("channel_defaults", {}).get(channel)
            if persona_name and persona_name in self._personas:
                return self._personas[persona_name]

        return None

    def set_user_persona(self, user_id: str, name: str):
        """Assign a persona to a user. Use 'default' or None to reset."""
        if name is None or name == "default":
            self._user_profiles.get("user_personas", {}).pop(user_id, None)
        else:
            if name not in self._personas:
                raise ValueError(f"Unknown persona: {name}")
            self._user_profiles.setdefault("user_personas", {})[user_id] = name
        self._save_user_profiles()

    def remove_user_persona(self, user_id: str):
        """Remove persona override for a user."""
        self._user_profiles.get("user_personas", {}).pop(user_id, None)
        self._save_user_profiles()

    def set_channel_default(self, channel: str, name: str):
        """Set the default persona for a channel."""
        if name is None or name == "default":
            self._user_profiles.get("channel_defaults", {}).pop(channel, None)
        else:
            if name not in self._personas:
                raise ValueError(f"Unknown persona: {name}")
            self._user_profiles.setdefault("channel_defaults", {})[channel] = name
        self._save_user_profiles()

    def create_persona(self, name: str, description: str = "", emoji: str = "", instructions: str = "") -> Persona:
        """Create a new persona file and register it."""
        if name in self._personas:
            raise ValueError(f"Persona '{name}' already exists")

        self.agents_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.agents_dir / f"{name}.md"

        content = f"---\nname: {name}\ndescription: {description}\nemoji: \"{emoji}\"\n---\n\n{instructions}\n"
        file_path.write_text(content, encoding='utf-8')

        persona = Persona(name=name, description=description, emoji=emoji, instructions=instructions, file_path=file_path)
        self._personas[name] = persona
        return persona

    def delete_persona(self, name: str):
        """Delete a persona file. Cannot delete 'default'."""
        if name == "default":
            raise ValueError("Cannot delete the default persona")
        persona = self._personas.get(name)
        if not persona:
            raise ValueError(f"Unknown persona: {name}")

        if persona.file_path.exists():
            persona.file_path.unlink()
        del self._personas[name]

        # Clean up any user/channel references
        changed = False
        for uid, pname in list(self._user_profiles.get("user_personas", {}).items()):
            if pname == name:
                del self._user_profiles["user_personas"][uid]
                changed = True
        for ch, pname in list(self._user_profiles.get("channel_defaults", {}).items()):
            if pname == name:
                del self._user_profiles["channel_defaults"][ch]
                changed = True
        if changed:
            self._save_user_profiles()

    def update_persona(self, name: str, description: Optional[str] = None, emoji: Optional[str] = None, instructions: Optional[str] = None) -> Persona:
        """Update an existing persona's fields and rewrite the file."""
        persona = self._personas.get(name)
        if not persona:
            raise ValueError(f"Unknown persona: {name}")

        if description is not None:
            persona.description = description
        if emoji is not None:
            persona.emoji = emoji
        if instructions is not None:
            persona.instructions = instructions

        content = f"---\nname: {persona.name}\ndescription: {persona.description}\nemoji: \"{persona.emoji}\"\n---\n\n{persona.instructions}\n"
        persona.file_path.write_text(content, encoding='utf-8')
        return persona

    def _load_user_profiles(self):
        """Load user_profiles.json."""
        if self.profiles_file.exists():
            try:
                data = json.loads(self.profiles_file.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    self._user_profiles = data
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load user profiles: {e}")

    def _save_user_profiles(self):
        """Persist user_profiles.json."""
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self.profiles_file.write_text(
            json.dumps(self._user_profiles, indent=2) + "\n",
            encoding='utf-8',
        )

    # =========================================================================
    # =========================================================================
    # Function _get_skills_info -> None to str
    # =========================================================================
    # =========================================================================
    def _get_skills_info(self) -> str:
        """Get information about available skills for the system prompt"""
        # ==================================
        if not self.skills_manager:
            return ""

        skills = self.skills_manager.get_user_invocable_skills()
        # ==================================
        if not skills:
            return ""

        lines = [
            "You have access to the following skills that users can invoke with /commands:\n"
        ]

        for skill in sorted(skills, key=lambda s: s.name):
            emoji = f"{skill.emoji} " if skill.emoji else ""
            lines.append(f"- **/{skill.name}** - {emoji}{skill.description}")

        lines.append("\nWhen a user invokes a skill (e.g., `/commit`), you will receive the skill's instructions to follow.")

        return "\n".join(lines)

    # =========================================================================
    # =========================================================================
    # Function get_skill_instructions -> str to Optional[str]
    # =========================================================================
    # =========================================================================
    def get_skill_instructions(self, skill_name: str) -> Optional[str]:
        """
        Get the instructions for a specific skill.

        Args:
            skill_name: Name of the skill to get

        Returns:
            Skill instructions if found, None otherwise
        """
        # ==================================
        if not self.skills_manager:
            return None

        skill = self.skills_manager.get_skill(skill_name)
        # ==================================
        if skill:
            return skill.instructions
        return None
    
    # =========================================================================
    # =========================================================================
    # Function _load_moods_context -> None to str
    # =========================================================================
    # =========================================================================
    def _load_moods_context(self) -> str:
        """Extract relevant mood information for current context"""
        # ==================================
        if not self.moods_file.exists():
            return ""
        
        with open(self.moods_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract the key sections for context
            lines = content.split('\n')
            
            # Find overall mood
            mood_section = []
            for i, line in enumerate(lines):
                # ==================================
                if "Current Overall Mood" in line:
                    # Get next few lines
                    mood_section = lines[i:i+4]
                    break
            
            return '\n'.join(mood_section) if mood_section else ""
    
    # =========================================================================
    # =========================================================================
    # Function _get_self_improvement_instructions -> None to str
    # =========================================================================
    # =========================================================================
    def _get_self_improvement_instructions(self) -> str:
        """Instructions for the bot to update mood/personality files"""
        return """

---
## SELF-IMPROVEMENT CAPABILITIES

You can update your mood and personality files after conversations!

### When to Update MOODS.md:
- After detecting user emotions (frustrated, excited, confused, happy)
- When you notice communication preferences
- After particularly good or challenging interactions
- When building rapport with a user

### When to Update NEW_PERSONALITY.md:
- When you discover a new effective communication pattern
- After learning something about how to help users better
- When you realize an area for improvement
- After successfully solving a novel problem

### How to Signal Updates:
At the end of your response, if you want to update files, include:

```mood-update
user_id: [user_id]
relationship: [Friendly/Collaborative/New/etc]
notes: [brief notes about this interaction]
user_state: [excited/frustrated/confused/happy/neutral]
```

```personality-update
category: [learned_pattern/strength/improvement/insight]
content: [what you learned]
```

These will be processed automatically and files will be updated.
"""
    
    # =========================================================================
    # =========================================================================
    # Function _default_personality -> None to str
    # =========================================================================
    # =========================================================================
    def _default_personality(self) -> str:
        """Fallback personality"""
        return """You are SkillForge, created by Dr. Syed Usama Bukhari.
You are witty, respectful, full of life, and endlessly curious.
You have persistent memory and can learn from every conversation."""
    
    # =========================================================================
    # =========================================================================
    # Function update_mood -> str, Dict to None
    # =========================================================================
    # =========================================================================
    def update_mood(self, user_id: str, mood_data: Dict):
        """Update MOODS.md with new user interaction data"""
        # ==================================
        if not self.moods_file.exists():
            return
        
        with open(self.moods_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update last updated timestamp
        content = content.replace(
            "Last updated: Never",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Find or create user section
        user_section = f"\n### User: {user_id}\n"
        user_section += f"- **Overall Relationship**: {mood_data.get('relationship', 'New')}\n"
        user_section += f"- **Last Interaction**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        user_section += f"- **Current State**: {mood_data.get('user_state', 'neutral')}\n"
        user_section += f"- **Mood Notes**:\n"
        
        notes = mood_data.get('notes', [])
        # ==================================
        if isinstance(notes, str):
            notes = [notes]
        for note in notes:
            user_section += f"  - {note}\n"
        
        # Check if user already exists
        # ==================================
        if f"### User: {user_id}" in content:
            # Replace existing section
            lines = content.split('\n')
            new_lines = []
            skip = False
            for line in lines:
                # ==================================
                if f"### User: {user_id}" in line:
                    skip = True
                    new_lines.append(user_section.strip())
                    continue
                # ==================================
                if skip and line.startswith('### User:'):
                    skip = False
                # ==================================
                if not skip:
                    new_lines.append(line)
            content = '\n'.join(new_lines)
        else:
            # Append new user
            content += user_section
        
        # Write back
        with open(self.moods_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"📝 Updated MOODS.md for user {user_id}")
    
    # =========================================================================
    # =========================================================================
    # Function add_personality_insight -> str, str to None
    # =========================================================================
    # =========================================================================
    def add_personality_insight(self, category: str, insight: str):
        """Add a new learned personality trait"""
        # ==================================
        if not self.new_personality_file.exists():
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"\n### [{timestamp}] {category}\n{insight}\n"
        
        with open(self.new_personality_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        print(f"💡 Added new personality insight: {category}")
    
    # =========================================================================
    # =========================================================================
    # Function parse_response_for_updates -> str, str to tuple[str, Dict]
    # =========================================================================
    # =========================================================================
    def parse_response_for_updates(self, response: str, user_id: str):
        """Parse AI response for mood/personality update signals"""
        updates = {
            'mood_update': None,
            'personality_update': None
        }
        
        # Look for mood-update block
        # ==================================
        if '```mood-update' in response:
            start = response.find('```mood-update')
            end = response.find('```', start + 14)
            # ==================================
            if end > start:
                mood_block = response[start+14:end].strip()
                mood_data = self._parse_update_block(mood_block)
                # ==================================
                if mood_data:
                    updates['mood_update'] = mood_data
                    self.update_mood(user_id, mood_data)
        
        # Look for personality-update block
        # ==================================
        if '```personality-update' in response:
            start = response.find('```personality-update')
            end = response.find('```', start + 21)
            # ==================================
            if end > start:
                personality_block = response[start+21:end].strip()
                personality_data = self._parse_update_block(personality_block)
                # ==================================
                if personality_data:
                    updates['personality_update'] = personality_data
                    self.add_personality_insight(
                        personality_data.get('category', 'general'),
                        personality_data.get('content', '')
                    )
        
        # Clean the response (remove update blocks for user display)
        clean_response = response
        for tag in ['```mood-update', '```personality-update']:
            # ==================================
            if tag in clean_response:
                start = clean_response.find(tag)
                end = clean_response.find('```', start + len(tag))
                # ==================================
                if end > start:
                    clean_response = clean_response[:start] + clean_response[end+3:]
        
        return clean_response.strip(), updates
    
    # =========================================================================
    # =========================================================================
    # Function _parse_update_block -> str to Dict
    # =========================================================================
    # =========================================================================
    def _parse_update_block(self, block: str) -> Dict:
        """Parse key: value format from update blocks"""
        data = {}
        for line in block.split('\n'):
            # ==================================
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
        return data


# =============================================================================
# End of File : personality.py
# =============================================================================
# Project : SkillForge - Persistent Memory AI Chatbot
# License : Open Source - Safe Open Community Project
# Mission : Making AI Useful for Everyone
# =============================================================================
