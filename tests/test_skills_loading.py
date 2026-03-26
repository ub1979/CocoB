# =============================================================================
# test_skills_loading.py — Verify all SKILL.md files load and parse correctly
# =============================================================================

import pytest
from pathlib import Path
from skillforge.core.skills.loader import parse_skill_file, find_skill_files
from skillforge.core.skills.manager import SkillsManager


SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Every bundled skill directory we expect to exist
EXPECTED_SKILLS = [
    "browse", "calendar", "commit", "create-skill", "email",
    "explain", "files", "github", "google-search", "news",
    "notes", "schedule", "search", "social", "todo",
]


class TestSkillFiles:
    """All SKILL.md files should exist and parse without errors."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_exists(self, skill_name):
        path = SKILLS_DIR / skill_name / "SKILL.md"
        assert path.exists(), f"Missing SKILL.md for {skill_name}"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_parses(self, skill_name):
        path = SKILLS_DIR / skill_name / "SKILL.md"
        skill = parse_skill_file(path)
        assert skill is not None, f"Failed to parse {skill_name}"
        assert skill.name == skill_name
        assert skill.description, f"{skill_name} has no description"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_has_emoji(self, skill_name):
        path = SKILLS_DIR / skill_name / "SKILL.md"
        skill = parse_skill_file(path)
        assert skill.emoji, f"{skill_name} has no emoji"

    def test_find_skill_files_discovers_all(self):
        files = find_skill_files(SKILLS_DIR)
        found_names = {f.parent.name for f in files}
        for name in EXPECTED_SKILLS:
            assert name in found_names, f"find_skill_files missed {name}"


class TestSkillsManager:
    """SkillsManager should load all bundled skills."""

    def test_loads_all_skills(self):
        manager = SkillsManager(bundled_dir=SKILLS_DIR)
        for name in EXPECTED_SKILLS:
            skill = manager.get_skill(name)
            assert skill is not None, f"Manager missing skill: {name}"

    def test_user_invocable_skills(self):
        manager = SkillsManager(bundled_dir=SKILLS_DIR)
        invocable = manager.get_user_invocable_skills()
        invocable_names = {s.name for s in invocable}
        # These should all be user-invocable
        for name in ["github", "notes", "files", "news", "social", "todo",
                      "schedule", "create-skill"]:
            assert name in invocable_names, f"{name} should be user-invocable"

    def test_skill_count_at_least_15(self):
        manager = SkillsManager(bundled_dir=SKILLS_DIR)
        all_skills = manager.get_user_invocable_skills()
        assert len(all_skills) >= 15, f"Expected >=15 skills, got {len(all_skills)}"
