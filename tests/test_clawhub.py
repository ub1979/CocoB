# =============================================================================
# test_clawhub.py — Tests for ClawHub integration (format adapter, manager, router)
# =============================================================================

import json
import os
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coco_b.core.skills.loader import Skill, parse_openclaw_skill_content
from coco_b.core.clawhub import ClawHubManager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def tmp_install_dir(tmp_path):
    """Temporary directory for skill installation."""
    d = tmp_path / "skills" / "clawhub"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def tmp_tracking_file(tmp_path):
    """Temporary tracking file."""
    return tmp_path / "data" / "clawhub_installed.json"


@pytest.fixture
def clawhub(tmp_path, tmp_install_dir, tmp_tracking_file):
    """ClawHubManager with temp dirs."""
    with patch("coco_b.core.clawhub.ClawHubManager.__init__", lambda self, **kw: None):
        mgr = ClawHubManager.__new__(ClawHubManager)
    mgr._skills_manager = None
    mgr._registry_url = "https://api.openclaw.ai/v1"
    mgr._cache_ttl = 300
    mgr._install_dir = tmp_install_dir
    mgr._tracking_file = tmp_tracking_file
    mgr._cache = {}
    return mgr


# =============================================================================
# Format Adapter Tests — parse_openclaw_skill_content
# =============================================================================

class TestOpenClawFormatAdapter:
    """Tests for OpenClaw → coco B skill conversion."""

    def test_basic_parsing(self):
        content = """---
name: weather-check
description: Check the weather forecast
version: 1.2.0
author: clouddev
---
Check the weather for a given location."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        assert skill.name == "weather-check"
        assert skill.description == "Check the weather forecast"
        assert skill.version == "1.2.0"
        assert skill.author == "clouddev"
        assert skill.source == "clawhub"
        assert "Check the weather" in skill.instructions

    def test_emoji_from_metadata_openclaw(self):
        content = """---
name: emoji-test
description: Test emoji extraction
metadata:
  openclaw:
    emoji: "🌤️"
---
Instructions here."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        assert skill.emoji == "🌤️"

    def test_emoji_fallback_to_toplevel(self):
        content = """---
name: emoji-fallback
description: Fallback emoji
emoji: "🔥"
---
Instructions."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        assert skill.emoji == "🔥"

    def test_emoji_metadata_takes_priority(self):
        content = """---
name: priority-test
description: Test
emoji: "❌"
metadata:
  openclaw:
    emoji: "✅"
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        assert skill.emoji == "✅"

    def test_basedir_replacement(self):
        content = """---
name: basedir-test
description: Test baseDir
---
Load config from {baseDir}/config.json and data from {baseDir}/data/."""
        skill = parse_openclaw_skill_content(content, base_dir="/home/skills/test")
        assert skill is not None
        assert "/home/skills/test/config.json" in skill.instructions
        assert "/home/skills/test/data/" in skill.instructions
        assert "{baseDir}" not in skill.instructions

    def test_basedir_no_replacement_when_empty(self):
        content = """---
name: no-basedir
description: Test
---
Use {baseDir}/file.txt"""
        skill = parse_openclaw_skill_content(content, base_dir="")
        assert "{baseDir}" in skill.instructions

    def test_version_and_author_fields(self):
        content = """---
name: versioned
description: Has version
version: 2.0.1
author: skill-creator
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill.version == "2.0.1"
        assert skill.author == "skill-creator"

    def test_missing_version_author(self):
        content = """---
name: minimal
description: Minimal skill
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill.version == ""
        assert skill.author == ""

    def test_requires_bins_warning(self, capsys):
        content = """---
name: needs-bins
description: Needs binaries
requires:
  bins:
    - ffmpeg
    - curl
---
Use ffmpeg."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        captured = capsys.readouterr()
        assert "requires binaries" in captured.out

    def test_requires_env_warning(self, capsys):
        content = """---
name: needs-env
description: Needs env vars
requires:
  env:
    - API_KEY
---
Use API_KEY."""
        skill = parse_openclaw_skill_content(content)
        assert skill is not None
        captured = capsys.readouterr()
        assert "requires env vars" in captured.out

    def test_no_frontmatter(self):
        content = "Just plain text, no frontmatter."
        skill = parse_openclaw_skill_content(content)
        assert skill is None

    def test_missing_name(self):
        content = """---
description: No name field
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill is None

    def test_invalid_yaml(self):
        content = """---
name: [invalid yaml
  bad: : :
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill is None

    def test_user_invocable_default_true(self):
        content = """---
name: invocable-default
description: Test
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill.user_invocable is True

    def test_user_invocable_false(self):
        content = """---
name: not-invocable
description: Test
user-invocable: false
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill.user_invocable is False

    def test_source_is_clawhub(self):
        content = """---
name: source-test
description: Test
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert skill.source == "clawhub"

    def test_file_path_preserved(self):
        content = """---
name: path-test
description: Test
---
Body."""
        skill = parse_openclaw_skill_content(content, file_path="/some/path/SKILL.md")
        assert skill.file_path == "/some/path/SKILL.md"

    def test_numeric_version_converted_to_string(self):
        content = """---
name: numeric-ver
description: Test
version: 1.0
---
Body."""
        skill = parse_openclaw_skill_content(content)
        assert isinstance(skill.version, str)
        assert skill.version == "1.0"


# =============================================================================
# Skill Dataclass Tests — new fields
# =============================================================================

class TestSkillNewFields:
    """Test new fields on Skill dataclass."""

    def test_new_fields_default_empty(self):
        skill = Skill(name="test", description="desc", instructions="body")
        assert skill.version == ""
        assert skill.author == ""
        assert skill.clawhub_slug == ""

    def test_to_dict_includes_new_fields_when_set(self):
        skill = Skill(
            name="test", description="desc", instructions="body",
            version="1.0.0", author="dev", clawhub_slug="test-skill"
        )
        d = skill.to_dict()
        assert d["version"] == "1.0.0"
        assert d["author"] == "dev"
        assert d["clawhub_slug"] == "test-skill"

    def test_to_dict_excludes_new_fields_when_empty(self):
        skill = Skill(name="test", description="desc", instructions="body")
        d = skill.to_dict()
        assert "version" not in d
        assert "author" not in d
        assert "clawhub_slug" not in d

    def test_source_clawhub(self):
        skill = Skill(name="test", description="desc", instructions="body", source="clawhub")
        assert skill.source == "clawhub"


# =============================================================================
# ClawHubManager — Caching
# =============================================================================

class TestClawHubCaching:
    """Test cache behavior."""

    def test_cache_stores_and_retrieves(self, clawhub):
        clawhub._set_cache("key1", [1, 2, 3])
        assert clawhub._get_cached("key1") == [1, 2, 3]

    def test_cache_expires(self, clawhub):
        clawhub._cache_ttl = 0  # instant expiry
        clawhub._set_cache("key2", "data")
        time.sleep(0.01)
        assert clawhub._get_cached("key2") is None

    def test_cache_miss(self, clawhub):
        assert clawhub._get_cached("nonexistent") is None


# =============================================================================
# ClawHubManager — Search (mocked HTTP)
# =============================================================================

class TestClawHubSearch:
    """Test search with mocked API."""

    def test_search_returns_results(self, clawhub):
        mock_response = {"results": [
            {"slug": "weather", "name": "Weather", "description": "Check weather", "author": "dev1"},
            {"slug": "news", "name": "News", "description": "Get news", "author": "dev2"},
        ]}
        with patch.object(clawhub, '_api_get', return_value=mock_response):
            results = clawhub.search("weather")
        assert len(results) == 2
        assert results[0]["slug"] == "weather"

    def test_search_caches_results(self, clawhub):
        mock_response = {"results": [{"slug": "cached"}]}
        with patch.object(clawhub, '_api_get', return_value=mock_response) as mock_get:
            clawhub.search("test")
            clawhub.search("test")  # Should hit cache
        assert mock_get.call_count == 1

    def test_search_returns_none_on_error(self, clawhub):
        with patch.object(clawhub, '_api_get', return_value=None):
            result = clawhub.search("fail")
        assert result is None

    def test_search_format_results(self, clawhub):
        results = [
            {"slug": "weather", "name": "Weather", "emoji": "🌤️", "description": "Check weather", "author": "dev", "downloads": 5000},
        ]
        formatted = clawhub.format_search_results(results)
        assert "Weather" in formatted
        assert "🌤️" in formatted
        assert "5,000" in formatted
        assert "/clawhub install weather" in formatted

    def test_search_format_empty(self, clawhub):
        assert "No skills found" in clawhub.format_search_results([])


# =============================================================================
# ClawHubManager — Skill Info
# =============================================================================

class TestClawHubSkillInfo:
    """Test skill info retrieval."""

    def test_get_skill_info(self, clawhub):
        mock_response = {"results": [{"slug": "weather", "name": "Weather", "version": "1.0"}]}
        with patch.object(clawhub, '_api_get', return_value=mock_response):
            info = clawhub.get_skill_info("weather")
        assert info["version"] == "1.0"
        assert "download_url" in info

    def test_get_skill_info_cached(self, clawhub):
        mock_response = {"results": [{"slug": "cached"}]}
        with patch.object(clawhub, '_api_get', return_value=mock_response) as mock_get:
            clawhub.get_skill_info("cached")
            clawhub.get_skill_info("cached")
        assert mock_get.call_count == 1

    def test_format_skill_info(self, clawhub):
        info = {"slug": "weather", "name": "Weather", "emoji": "🌤️", "description": "Check weather", "author": "dev", "version": "1.0", "downloads": 500}
        formatted = clawhub.format_skill_info(info)
        assert "Weather" in formatted
        assert "1.0" in formatted
        assert "dev" in formatted

    def test_format_skill_info_empty(self, clawhub):
        assert "not found" in clawhub.format_skill_info({}).lower() or "not found" in clawhub.format_skill_info(None).lower()


# =============================================================================
# ClawHubManager — Install / Uninstall
# =============================================================================

class TestClawHubInstall:
    """Test skill installation and removal."""

    def test_install_from_content(self, clawhub):
        skill_content = """---
name: test-skill
description: A test skill
version: 1.0.0
author: tester
---
Do the test thing."""
        mock_info = {
            "slug": "test-skill",
            "name": "test-skill",
            "version": "1.0.0",
            "author": "tester",
            "content": skill_content,
        }
        with patch.object(clawhub, 'get_skill_info', return_value=mock_info):
            success, msg = clawhub.install_skill("test-skill")

        assert success is True
        assert "test-skill" in msg

        # Check file was created
        skill_file = clawhub._install_dir / "test-skill" / "SKILL.md"
        assert skill_file.exists()

        # Check tracking
        tracking = clawhub._load_tracking()
        assert "test-skill" in tracking
        assert tracking["test-skill"]["version"] == "1.0.0"

    def test_install_already_installed(self, clawhub):
        clawhub._save_tracking({"existing": {"install_name": "existing", "version": "1.0"}})
        success, msg = clawhub.install_skill("existing")
        assert success is False
        assert "already installed" in msg

    def test_install_not_found(self, clawhub):
        with patch.object(clawhub, 'get_skill_info', return_value=None):
            success, msg = clawhub.install_skill("nonexistent")
        assert success is False
        assert "Could not find" in msg

    def test_install_name_conflict_prefixes(self, clawhub):
        """When a bundled skill has the same name, prefix with ch-."""
        skill_content = """---
name: commit
description: ClawHub commit skill
version: 1.0.0
author: hubber
---
Commit instructions."""
        mock_info = {
            "slug": "commit",
            "name": "commit",
            "version": "1.0.0",
            "author": "hubber",
            "content": skill_content,
        }
        # Mock skills manager with existing 'commit' skill
        mock_sm = MagicMock()
        mock_sm.get_skill.return_value = Skill(name="commit", description="bundled", instructions="x", source="bundled")
        clawhub._skills_manager = mock_sm

        with patch.object(clawhub, 'get_skill_info', return_value=mock_info):
            success, msg = clawhub.install_skill("commit")

        assert success is True
        assert "ch-commit" in msg

        # File should be in ch-commit dir
        assert (clawhub._install_dir / "ch-commit" / "SKILL.md").exists()

    def test_uninstall(self, clawhub):
        # Pre-install a skill
        skill_dir = clawhub._install_dir / "test-remove"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("test")
        clawhub._save_tracking({"test-remove": {"install_name": "test-remove", "version": "1.0"}})

        success, msg = clawhub.uninstall_skill("test-remove")
        assert success is True
        assert "Uninstalled" in msg
        assert not skill_dir.exists()
        assert "test-remove" not in clawhub._load_tracking()

    def test_uninstall_not_installed(self, clawhub):
        success, msg = clawhub.uninstall_skill("never-installed")
        assert success is False
        assert "not installed" in msg


# =============================================================================
# ClawHubManager — List Installed
# =============================================================================

class TestClawHubListInstalled:
    """Test listing installed skills."""

    def test_list_empty(self, clawhub):
        assert clawhub.list_installed() == []

    def test_list_with_skills(self, clawhub):
        clawhub._save_tracking({
            "skill-a": {"install_name": "skill-a", "version": "1.0", "author": "dev1"},
            "skill-b": {"install_name": "skill-b", "version": "2.0", "author": "dev2"},
        })
        installed = clawhub.list_installed()
        assert len(installed) == 2
        slugs = {s["slug"] for s in installed}
        assert slugs == {"skill-a", "skill-b"}

    def test_format_installed_empty(self, clawhub):
        result = clawhub.format_installed_list()
        assert "No ClawHub skills" in result

    def test_format_installed_with_skills(self, clawhub):
        clawhub._save_tracking({"my-skill": {"install_name": "my-skill", "version": "1.0", "author": "me"}})
        result = clawhub.format_installed_list()
        assert "my-skill" in result
        assert "v1.0" in result


# =============================================================================
# ClawHubManager — Check Updates
# =============================================================================

class TestClawHubUpdates:
    """Test update checking."""

    def test_check_updates_finds_newer(self, clawhub):
        clawhub._save_tracking({"old-skill": {"install_name": "old-skill", "version": "1.0"}})
        with patch.object(clawhub, 'get_skill_info', return_value={"version": "2.0"}):
            updates = clawhub.check_updates()
        assert len(updates) == 1
        assert updates[0]["installed_version"] == "1.0"
        assert updates[0]["latest_version"] == "2.0"

    def test_check_updates_all_current(self, clawhub):
        clawhub._save_tracking({"up-to-date": {"install_name": "up-to-date", "version": "1.0"}})
        with patch.object(clawhub, 'get_skill_info', return_value={"version": "1.0"}):
            updates = clawhub.check_updates()
        assert updates == []

    def test_format_updates_none(self, clawhub):
        result = clawhub.format_updates([])
        assert "up to date" in result

    def test_format_updates_available(self, clawhub):
        updates = [{"slug": "my-skill", "installed_version": "1.0", "latest_version": "2.0"}]
        result = clawhub.format_updates(updates)
        assert "my-skill" in result
        assert "1.0" in result
        assert "2.0" in result


# =============================================================================
# ClawHubManager — Requirements Check
# =============================================================================

class TestClawHubRequirements:
    """Test requirements checking."""

    def test_no_requirements(self, clawhub):
        result = clawhub.check_requirements({})
        assert result["bins_ok"] is True
        assert result["env_ok"] is True

    def test_missing_binary(self, clawhub):
        result = clawhub.check_requirements({"requires": {"bins": ["nonexistent_binary_xyz"]}})
        assert result["bins_ok"] is False
        assert "nonexistent_binary_xyz" in result["missing_bins"]

    def test_present_binary(self, clawhub):
        # 'python' should be available
        result = clawhub.check_requirements({"requires": {"bins": ["python3"]}})
        assert result["bins_ok"] is True

    def test_missing_env_var(self, clawhub):
        result = clawhub.check_requirements({"requires": {"env": ["CLAWHUB_TEST_NONEXISTENT_VAR"]}})
        assert result["env_ok"] is False
        assert "CLAWHUB_TEST_NONEXISTENT_VAR" in result["missing_env"]

    def test_present_env_var(self, clawhub):
        os.environ["CLAWHUB_TEST_VAR"] = "1"
        try:
            result = clawhub.check_requirements({"requires": {"env": ["CLAWHUB_TEST_VAR"]}})
            assert result["env_ok"] is True
        finally:
            del os.environ["CLAWHUB_TEST_VAR"]


# =============================================================================
# ClawHubManager — Tracking File
# =============================================================================

class TestClawHubTracking:
    """Test tracking file operations."""

    def test_load_empty(self, clawhub):
        assert clawhub._load_tracking() == {}

    def test_save_and_load(self, clawhub):
        data = {"skill-1": {"version": "1.0"}}
        clawhub._save_tracking(data)
        loaded = clawhub._load_tracking()
        assert loaded == data

    def test_load_corrupt_file(self, clawhub):
        clawhub._tracking_file.parent.mkdir(parents=True, exist_ok=True)
        clawhub._tracking_file.write_text("not json!!!")
        assert clawhub._load_tracking() == {}


# =============================================================================
# Router Integration Tests
# =============================================================================

class TestClawHubRouterIntegration:
    """Test /clawhub commands via router."""

    @pytest.fixture
    def router(self, tmp_path):
        """Create a minimal router with mocked dependencies."""
        from unittest.mock import MagicMock, PropertyMock, patch
        from coco_b.core.router import MessageRouter

        mock_session = MagicMock()
        mock_llm = MagicMock()
        mock_llm.model_name = "test"
        mock_llm.provider_name = "test"

        with patch.object(MessageRouter, '__init__', lambda self, *a, **kw: None):
            r = MessageRouter.__new__(MessageRouter)

        r.session_manager = mock_session
        r.llm = mock_llm
        r._ai_client = None
        r.personality = MagicMock()
        r.personality.skills_manager = MagicMock()
        r.personality.skills_manager.get_user_invocable_skills.return_value = []
        r._mcp_manager = None
        r._tool_handler = None
        r._skill_executor = MagicMock()
        r.memory_store = MagicMock()
        r._schedule_handler = MagicMock()
        r._todo_handler = MagicMock()
        r._skill_creator_handler = MagicMock()
        r._file_access = MagicMock()
        r._auth_manager = MagicMock()
        r._heartbeat_manager = MagicMock()
        r._pattern_detector = MagicMock()
        r._task_runner = MagicMock()
        r._mcp_server_manager = MagicMock()
        r._prompt_cache = {}
        r.system_prompt = ""
        r._system_prompt_mtime = 0.0

        # Set up real ClawHubManager with temp dirs
        r._clawhub_manager = ClawHubManager.__new__(ClawHubManager)
        r._clawhub_manager._skills_manager = None
        r._clawhub_manager._registry_url = "https://api.openclaw.ai/v1"
        r._clawhub_manager._cache_ttl = 300
        r._clawhub_manager._install_dir = tmp_path / "skills" / "clawhub"
        r._clawhub_manager._install_dir.mkdir(parents=True)
        r._clawhub_manager._tracking_file = tmp_path / "data" / "clawhub_installed.json"
        r._clawhub_manager._cache = {}

        return r

    def test_clawhub_is_builtin_command(self, router):
        is_skill, name, remaining = router.is_skill_invocation("/clawhub search weather")
        assert is_skill is False  # Built-in, not a skill

    def test_clawhub_no_subcommand(self, router):
        result = router.handle_command("/clawhub", "session:key")
        assert "Usage" in result

    def test_clawhub_search_command(self, router):
        mock_results = [{"slug": "weather", "name": "Weather", "emoji": "🌤️", "description": "Weather info", "author": "dev", "downloads": 100}]
        with patch.object(router._clawhub_manager, 'search', return_value=mock_results):
            result = router.handle_command("/clawhub search weather", "session:key")
        assert "Weather" in result

    def test_clawhub_search_error(self, router):
        with patch.object(router._clawhub_manager, 'search', return_value=None):
            result = router.handle_command("/clawhub search fail", "session:key")
        assert "Could not reach" in result

    def test_clawhub_install_command(self, router):
        with patch.object(router._clawhub_manager, 'install_skill', return_value=(True, "Installed **Weather**")):
            result = router.handle_command("/clawhub install weather", "session:key")
        assert "Installed" in result

    def test_clawhub_list_command(self, router):
        result = router.handle_command("/clawhub list", "session:key")
        assert "No ClawHub skills" in result

    def test_clawhub_info_command(self, router):
        mock_info = {"slug": "test", "name": "Test", "description": "A test", "version": "1.0"}
        with patch.object(router._clawhub_manager, 'get_skill_info', return_value=mock_info):
            result = router.handle_command("/clawhub info test", "session:key")
        assert "Test" in result

    def test_clawhub_info_not_found(self, router):
        with patch.object(router._clawhub_manager, 'get_skill_info', return_value=None):
            result = router.handle_command("/clawhub info nonexistent", "session:key")
        assert "Could not find" in result

    def test_clawhub_uninstall_command(self, router):
        with patch.object(router._clawhub_manager, 'uninstall_skill', return_value=(True, "Uninstalled 'test'.")):
            result = router.handle_command("/clawhub uninstall test", "session:key")
        assert "Uninstalled" in result

    def test_clawhub_updates_command(self, router):
        with patch.object(router._clawhub_manager, 'check_updates', return_value=[]):
            result = router.handle_command("/clawhub updates", "session:key")
        assert "up to date" in result

    def test_clawhub_unknown_subcommand(self, router):
        result = router.handle_command("/clawhub banana", "session:key")
        assert "Usage" in result

    def test_help_includes_clawhub(self, router):
        result = router.handle_command("/help", "session:key")
        assert "ClawHub" in result
        assert "/clawhub search" in result


# =============================================================================
# ZIP Extraction
# =============================================================================

class TestClawHubZipExtraction:
    """Test ZIP file skill extraction."""

    def test_extract_skill_from_zip(self, clawhub):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("skill-name/SKILL.md", "---\nname: zipped\n---\nBody.")
        raw = buf.getvalue()
        content = clawhub._extract_skill_from_zip(raw)
        assert content is not None
        assert "zipped" in content

    def test_extract_skill_from_invalid_zip(self, clawhub):
        content = clawhub._extract_skill_from_zip(b"not a zip file")
        assert content is None
