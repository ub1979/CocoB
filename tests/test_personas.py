# =============================================================================
# test_personas.py — Tests for Multi-Persona / Per-User Personality System
# =============================================================================

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from skillforge.core.personality import PersonalityManager, Persona


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def persona_dir(tmp_path):
    """Create a temp personality directory with agents/ and a base PERSONALITY.md."""
    base = tmp_path / "personality"
    base.mkdir()
    agents = base / "agents"
    agents.mkdir()
    (base / "PERSONALITY.md").write_text("You are SkillForge, a helpful bot.")
    return base


@pytest.fixture
def pm(persona_dir):
    """PersonalityManager with temp directory, no skills manager."""
    return PersonalityManager(base_path=persona_dir, skills_manager=None)


def _write_persona(agents_dir, name, description="desc", emoji="🔧", body="Instructions here."):
    """Helper: write a persona markdown file."""
    content = f"---\nname: {name}\ndescription: {description}\nemoji: \"{emoji}\"\n---\n\n{body}\n"
    (agents_dir / f"{name}.md").write_text(content, encoding="utf-8")


# =============================================================================
# TestPersonaLoading
# =============================================================================

class TestPersonaLoading:
    """Test persona file discovery and parsing."""

    def test_empty_agents_dir(self, pm):
        assert pm.get_personas() == {}

    def test_load_single_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Pro tone", "👔", "Be formal.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        personas = pm.get_personas()
        assert "formal" in personas
        assert personas["formal"].emoji == "👔"
        assert personas["formal"].description == "Pro tone"
        assert "Be formal." in personas["formal"].instructions

    def test_load_multiple_personas(self, persona_dir):
        agents = persona_dir / "agents"
        _write_persona(agents, "casual", "Chill", "😊", "Be chill.")
        _write_persona(agents, "technical", "Dev", "💻", "Be technical.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert len(pm.get_personas()) == 2

    def test_invalid_frontmatter_skipped(self, persona_dir):
        (persona_dir / "agents" / "bad.md").write_text("No frontmatter here", encoding="utf-8")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert "bad" not in pm.get_personas()

    def test_missing_name_field_skipped(self, persona_dir):
        content = "---\ndescription: Missing name\nemoji: \"❓\"\n---\n\nBody\n"
        (persona_dir / "agents" / "noname.md").write_text(content, encoding="utf-8")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm.get_personas() == {}

    def test_invalid_yaml_skipped(self, persona_dir):
        content = "---\nname: [invalid yaml\n---\n\nBody\n"
        (persona_dir / "agents" / "badyaml.md").write_text(content, encoding="utf-8")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm.get_personas() == {}

    def test_get_persona_by_name(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm.get_persona("formal") is not None
        assert pm.get_persona("nonexistent") is None

    def test_file_path_stored(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm.get_persona("formal").file_path == persona_dir / "agents" / "formal.md"

    def test_no_agents_dir(self, tmp_path):
        base = tmp_path / "personality"
        base.mkdir()
        (base / "PERSONALITY.md").write_text("Base.")
        pm = PersonalityManager(base_path=base, skills_manager=None)
        assert pm.get_personas() == {}


# =============================================================================
# TestUserProfiles
# =============================================================================

class TestUserProfiles:
    """Test user profile persistence and assignment."""

    def test_set_user_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        assert pm._user_profiles["user_personas"]["alice"] == "formal"

    def test_set_user_persona_persists_to_json(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        data = json.loads((persona_dir / "user_profiles.json").read_text())
        assert data["user_personas"]["alice"] == "formal"

    def test_remove_user_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        pm.remove_user_persona("alice")
        assert "alice" not in pm._user_profiles.get("user_personas", {})

    def test_set_user_persona_default_resets(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        _write_persona(persona_dir / "agents", "default", "Base", "🤖")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        pm.set_user_persona("alice", "default")
        assert "alice" not in pm._user_profiles.get("user_personas", {})

    def test_set_channel_default(self, persona_dir):
        _write_persona(persona_dir / "agents", "casual")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("whatsapp", "casual")
        assert pm._user_profiles["channel_defaults"]["whatsapp"] == "casual"

    def test_set_channel_default_persists(self, persona_dir):
        _write_persona(persona_dir / "agents", "casual")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("whatsapp", "casual")
        data = json.loads((persona_dir / "user_profiles.json").read_text())
        assert data["channel_defaults"]["whatsapp"] == "casual"

    def test_set_channel_default_resets(self, persona_dir):
        _write_persona(persona_dir / "agents", "casual")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("whatsapp", "casual")
        pm.set_channel_default("whatsapp", "default")
        assert "whatsapp" not in pm._user_profiles.get("channel_defaults", {})

    def test_set_unknown_persona_raises(self, pm):
        with pytest.raises(ValueError, match="Unknown persona"):
            pm.set_user_persona("alice", "nonexistent")

    def test_set_unknown_channel_persona_raises(self, pm):
        with pytest.raises(ValueError, match="Unknown persona"):
            pm.set_channel_default("slack", "nonexistent")

    def test_load_existing_profiles(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        profiles = {"user_personas": {"bob": "formal"}, "channel_defaults": {"slack": "formal"}}
        (persona_dir / "user_profiles.json").write_text(json.dumps(profiles))
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm._user_profiles["user_personas"]["bob"] == "formal"
        assert pm._user_profiles["channel_defaults"]["slack"] == "formal"

    def test_corrupt_profiles_json_handled(self, persona_dir):
        (persona_dir / "user_profiles.json").write_text("not json!")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        # Should fallback to empty defaults, not crash
        assert pm._user_profiles == {"user_personas": {}, "channel_defaults": {}}


# =============================================================================
# TestPersonaResolution
# =============================================================================

class TestPersonaResolution:
    """Test the resolve_persona priority chain."""

    def test_user_override_takes_priority(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        _write_persona(persona_dir / "agents", "casual")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        pm.set_channel_default("whatsapp", "casual")
        persona = pm.resolve_persona(user_id="alice", channel="whatsapp")
        assert persona.name == "formal"

    def test_channel_default_fallback(self, persona_dir):
        _write_persona(persona_dir / "agents", "casual")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("whatsapp", "casual")
        persona = pm.resolve_persona(user_id="bob", channel="whatsapp")
        assert persona.name == "casual"

    def test_none_when_no_match(self, pm):
        assert pm.resolve_persona(user_id="unknown", channel="unknown") is None

    def test_none_when_no_args(self, pm):
        assert pm.resolve_persona() is None

    def test_unknown_persona_in_profile_returns_none(self, persona_dir):
        """If profile references a persona that no longer exists, resolve returns None."""
        profiles = {"user_personas": {"alice": "deleted_one"}, "channel_defaults": {}}
        (persona_dir / "user_profiles.json").write_text(json.dumps(profiles))
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        assert pm.resolve_persona(user_id="alice") is None


# =============================================================================
# TestSystemPromptLayering
# =============================================================================

class TestSystemPromptLayering:
    """Test that personas layer correctly into the system prompt."""

    def test_default_unchanged_without_persona(self, pm):
        prompt = pm.get_system_prompt()
        assert "SkillForge" in prompt
        assert "Persona Override" not in prompt

    def test_persona_appended_in_full_mode(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Pro", "👔", "Use formal language.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        prompt = pm.get_system_prompt(user_id="alice")
        assert "Persona Override" in prompt
        assert "formal" in prompt
        assert "Use formal language." in prompt

    def test_default_persona_not_appended(self, persona_dir):
        _write_persona(persona_dir / "agents", "default", "Base", "🤖", "Base instructions.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "default")
        prompt = pm.get_system_prompt(user_id="alice")
        assert "Persona Override" not in prompt

    def test_minimal_mode_ignores_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        prompt = pm.get_system_prompt(mode="minimal", user_id="alice")
        assert "Persona Override" not in prompt

    def test_none_mode_ignores_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        prompt = pm.get_system_prompt(mode="none", user_id="alice")
        assert "Persona Override" not in prompt

    def test_base_personality_present_with_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Pro", "👔", "Be formal.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        prompt = pm.get_system_prompt(user_id="alice")
        assert "SkillForge" in prompt
        assert "Be formal." in prompt

    def test_channel_persona_in_prompt(self, persona_dir):
        _write_persona(persona_dir / "agents", "casual", "Chill", "😊", "Be relaxed.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("whatsapp", "casual")
        prompt = pm.get_system_prompt(channel="whatsapp")
        assert "Be relaxed." in prompt


# =============================================================================
# TestPersonaCRUD
# =============================================================================

class TestPersonaCRUD:
    """Test create, update, delete operations."""

    def test_create_persona(self, pm):
        persona = pm.create_persona("newone", "A new persona", "🆕", "Custom instructions.")
        assert persona.name == "newone"
        assert pm.get_persona("newone") is not None
        assert (pm.agents_dir / "newone.md").exists()

    def test_create_duplicate_fails(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        with pytest.raises(ValueError, match="already exists"):
            pm.create_persona("formal")

    def test_delete_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.delete_persona("formal")
        assert pm.get_persona("formal") is None
        assert not (persona_dir / "agents" / "formal.md").exists()

    def test_delete_default_fails(self, persona_dir):
        _write_persona(persona_dir / "agents", "default", "Base", "🤖")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        with pytest.raises(ValueError, match="Cannot delete the default"):
            pm.delete_persona("default")

    def test_delete_unknown_fails(self, pm):
        with pytest.raises(ValueError, match="Unknown persona"):
            pm.delete_persona("nonexistent")

    def test_delete_cleans_user_references(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_user_persona("alice", "formal")
        pm.delete_persona("formal")
        assert "alice" not in pm._user_profiles.get("user_personas", {})

    def test_delete_cleans_channel_references(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        pm.set_channel_default("slack", "formal")
        pm.delete_persona("formal")
        assert "slack" not in pm._user_profiles.get("channel_defaults", {})

    def test_update_persona(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Old desc", "👔", "Old body.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        updated = pm.update_persona("formal", description="New desc", instructions="New body.")
        assert updated.description == "New desc"
        assert updated.instructions == "New body."
        # Verify file was rewritten
        content = (persona_dir / "agents" / "formal.md").read_text()
        assert "New desc" in content
        assert "New body." in content

    def test_update_unknown_fails(self, pm):
        with pytest.raises(ValueError, match="Unknown persona"):
            pm.update_persona("nonexistent", description="nope")

    def test_update_partial_fields(self, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Desc", "👔", "Body.")
        pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        updated = pm.update_persona("formal", emoji="🎩")
        assert updated.emoji == "🎩"
        assert updated.description == "Desc"  # unchanged
        assert updated.instructions == "Body."  # unchanged

    def test_create_without_agents_dir(self, tmp_path):
        """Agents dir is auto-created on persona create."""
        base = tmp_path / "personality"
        base.mkdir()
        (base / "PERSONALITY.md").write_text("Base.")
        pm = PersonalityManager(base_path=base, skills_manager=None)
        persona = pm.create_persona("new", "Desc", "✨", "Body.")
        assert persona.name == "new"
        assert (base / "agents" / "new.md").exists()


# =============================================================================
# TestRouterPersonaIntegration
# =============================================================================

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.model_name = "test-model"
    llm.provider_name = "test-provider"
    llm.config = MagicMock()
    llm.config.base_url = "http://localhost"
    llm.config.model = "test-model"
    llm.check_context_size.return_value = {"needs_compaction": False, "total_tokens": 100}
    llm.chat.return_value = "Hello!"
    llm.estimate_tokens.return_value = 50
    return llm


@pytest.fixture
def router(tmp_path, mock_llm, persona_dir):
    """Create a MessageRouter with personas in a temp directory."""
    from skillforge.core.sessions import SessionManager
    from skillforge.core.router import MessageRouter

    # Patch PersonalityManager to use our temp persona_dir
    with patch("skillforge.core.router.PersonalityManager") as MockPM:
        real_pm = PersonalityManager(base_path=persona_dir, skills_manager=None)
        MockPM.return_value = real_pm

        sm = SessionManager(str(tmp_path / "sessions"))
        r = MessageRouter(sm, mock_llm)

    # Point todo handler to temp file
    r._todo_handler._data_file = tmp_path / "todos.json"
    r._todo_handler._save_data({})
    from skillforge.core.file_access import FileAccessManager
    r._file_access = FileAccessManager(project_root=tmp_path)
    return r


class TestRouterPersonaIntegration:
    """Test persona commands wired into the router."""

    def test_list_personas_command(self, router, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Pro", "👔")
        router.personality.load_personas()
        result = router.handle_command("/list-personas", "ui:direct:alice")
        assert "formal" in result
        assert "👔" in result

    def test_list_personas_empty(self, router):
        result = router.handle_command("/list-personas", "ui:direct:alice")
        assert "No personas" in result

    def test_set_persona_command(self, router, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        router.personality.load_personas()
        result = router.handle_command("/set-persona formal", "ui:direct:alice")
        assert "formal" in result.lower()
        assert router.personality._user_profiles["user_personas"]["alice"] == "formal"

    def test_set_persona_unknown(self, router):
        result = router.handle_command("/set-persona nonexistent", "ui:direct:alice")
        assert "unknown" in result.lower() or "not found" in result.lower()

    def test_set_persona_no_arg(self, router):
        result = router.handle_command("/set-persona", "ui:direct:alice")
        assert "usage" in result.lower()

    def test_persona_command_shows_current(self, router, persona_dir):
        _write_persona(persona_dir / "agents", "formal")
        router.personality.load_personas()
        router.personality.set_user_persona("alice", "formal")
        result = router.handle_command("/persona", "ui:direct:alice")
        assert "formal" in result

    def test_persona_command_no_assignment(self, router):
        result = router.handle_command("/persona", "ui:direct:alice")
        assert "no persona" in result.lower() or "default" in result.lower()

    def test_create_persona_command(self, router):
        result = router.handle_command("/create-persona mytone A custom tone", "ui:direct:alice")
        assert "mytone" in result.lower()
        assert router.personality.get_persona("mytone") is not None

    def test_create_persona_no_arg(self, router):
        result = router.handle_command("/create-persona", "ui:direct:alice")
        assert "usage" in result.lower()

    def test_persona_commands_in_builtin_list(self, router):
        """Persona commands should not be treated as skills."""
        for cmd in ["list-personas", "set-persona", "persona", "create-persona"]:
            is_skill, _, _ = router.is_skill_invocation(f"/{cmd}")
            assert not is_skill, f"/{cmd} should be a built-in command, not a skill"

    def test_help_includes_persona_section(self, router):
        result = router.handle_command("/help", "ui:direct:alice")
        assert "persona" in result.lower()

    def test_prompt_cache_keyed_by_user_channel(self, router, persona_dir):
        _write_persona(persona_dir / "agents", "formal", "Pro", "👔", "Be formal.")
        _write_persona(persona_dir / "agents", "casual", "Chill", "😊", "Be casual.")
        router.personality.load_personas()
        router.personality.set_user_persona("alice", "formal")
        router.personality.set_channel_default("whatsapp", "casual")

        prompt_alice = router._get_system_prompt_cached(user_id="alice", channel="ui")
        prompt_whatsapp = router._get_system_prompt_cached(user_id="bob", channel="whatsapp")

        assert "formal" in prompt_alice.lower()
        assert "casual" in prompt_whatsapp.lower()
