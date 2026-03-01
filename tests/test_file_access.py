# =============================================================================
# test_file_access.py — Unit tests for FileAccessManager
# =============================================================================

import os
import stat
import pytest
from pathlib import Path
from coco_b.core.file_access import FileAccessManager


@pytest.fixture
def fa(tmp_path):
    """Create a FileAccessManager with a temp project root."""
    mgr = FileAccessManager(project_root=tmp_path)
    # Pre-create the allowed directories
    (tmp_path / "skills").mkdir()
    (tmp_path / "data" / "user").mkdir(parents=True)
    return mgr


# =============================================================================
# Password setup & verification
# =============================================================================
class TestPasswordManagement:

    def test_password_not_set_initially(self, fa):
        assert fa.is_password_set() is False

    def test_setup_password_success(self, fa):
        assert fa.setup_password("MyStr0ng!") is True
        assert fa.is_password_set() is True

    def test_setup_password_too_short(self, fa):
        assert fa.setup_password("short") is False
        assert fa.is_password_set() is False

    def test_setup_password_rejects_if_already_set(self, fa):
        fa.setup_password("FirstPass1")
        assert fa.setup_password("SecondPass2") is False

    def test_verify_correct_password(self, fa):
        fa.setup_password("CorrectHorse!")
        assert fa.verify_password("CorrectHorse!") is True

    def test_verify_wrong_password(self, fa):
        fa.setup_password("CorrectHorse!")
        assert fa.verify_password("WrongPassword") is False

    def test_verify_when_none_set(self, fa):
        assert fa.verify_password("anything") is False

    def test_auth_file_permissions(self, fa):
        fa.setup_password("SecurePass1")
        mode = os.stat(fa._auth_file).st_mode
        # Owner read+write only (0600)
        assert stat.S_IMODE(mode) == 0o600

    def test_auth_file_format(self, fa):
        fa.setup_password("TestFormat1")
        content = fa._auth_file.read_text()
        parts = content.split(":")
        assert len(parts) == 2
        # Both parts should be valid hex
        bytes.fromhex(parts[0])
        bytes.fromhex(parts[1])


# =============================================================================
# Sandbox enforcement
# =============================================================================
class TestSandbox:

    def test_skills_dir_allowed(self, fa, tmp_path):
        path = str(tmp_path / "skills" / "my-skill" / "SKILL.md")
        assert fa.is_path_allowed(path) is True

    def test_data_user_dir_allowed(self, fa, tmp_path):
        path = str(tmp_path / "data" / "user" / "notes.txt")
        assert fa.is_path_allowed(path) is True

    def test_root_dir_blocked(self, fa, tmp_path):
        path = str(tmp_path / "config.py")
        assert fa.is_path_allowed(path) is False

    def test_data_dir_blocked(self, fa, tmp_path):
        # data/ is blocked, only data/user/ is allowed
        path = str(tmp_path / "data" / "sessions" / "evil.json")
        assert fa.is_path_allowed(path) is False

    def test_traversal_attack_blocked(self, fa, tmp_path):
        # Try to escape skills/ via ..
        path = str(tmp_path / "skills" / ".." / "config.py")
        assert fa.is_path_allowed(path) is False

    def test_absolute_outside_path_blocked(self, fa):
        assert fa.is_path_allowed("/etc/passwd") is False

    def test_src_dir_blocked(self, fa, tmp_path):
        path = str(tmp_path / "src" / "coco_b" / "core" / "evil.py")
        assert fa.is_path_allowed(path) is False


# =============================================================================
# File operations within sandbox
# =============================================================================
class TestFileOps:

    def test_write_and_read(self, fa, tmp_path):
        path = str(tmp_path / "skills" / "test-skill" / "SKILL.md")
        assert fa.write_file(path, "# Test Skill") is True
        assert fa.read_file(path) == "# Test Skill"

    def test_write_outside_sandbox_fails(self, fa, tmp_path):
        path = str(tmp_path / "evil.py")
        assert fa.write_file(path, "import os") is False

    def test_read_outside_sandbox_fails(self, fa, tmp_path):
        evil = tmp_path / "secret.txt"
        evil.write_text("secret")
        assert fa.read_file(str(evil)) is None

    def test_read_nonexistent_file(self, fa, tmp_path):
        path = str(tmp_path / "skills" / "nope.md")
        assert fa.read_file(path) is None

    def test_list_dir(self, fa, tmp_path):
        skills_dir = tmp_path / "skills"
        (skills_dir / "alpha").mkdir()
        (skills_dir / "beta").mkdir()
        result = fa.list_dir(str(skills_dir))
        assert result is not None
        assert "alpha" in result
        assert "beta" in result

    def test_list_dir_outside_sandbox(self, fa, tmp_path):
        assert fa.list_dir(str(tmp_path / "src")) is None

    def test_write_creates_parent_dirs(self, fa, tmp_path):
        path = str(tmp_path / "data" / "user" / "deep" / "nested" / "file.txt")
        assert fa.write_file(path, "hello") is True
        assert Path(path).read_text() == "hello"


# =============================================================================
# Pending action flow
# =============================================================================
class TestPendingActions:

    def test_request_auth_returns_prompt(self, fa):
        msg = fa.request_auth("sess1", "create_skill", {"name": "timer"})
        assert "/unlock" in msg

    def test_get_pending_action(self, fa):
        fa.request_auth("sess1", "create_skill", {"name": "timer"})
        action = fa.get_pending_action("sess1")
        assert action is not None
        assert action["action"] == "create_skill"
        assert action["details"]["name"] == "timer"

    def test_get_pending_action_empty(self, fa):
        assert fa.get_pending_action("no-session") is None

    def test_clear_pending_action(self, fa):
        fa.request_auth("sess1", "create_skill", {"name": "timer"})
        fa.clear_pending_action("sess1")
        assert fa.get_pending_action("sess1") is None

    def test_multiple_sessions_independent(self, fa):
        fa.request_auth("sess1", "create_skill", {"name": "a"})
        fa.request_auth("sess2", "delete_skill", {"name": "b"})
        assert fa.get_pending_action("sess1")["action"] == "create_skill"
        assert fa.get_pending_action("sess2")["action"] == "delete_skill"

    def test_new_request_overwrites_previous(self, fa):
        fa.request_auth("sess1", "create_skill", {"name": "first"})
        fa.request_auth("sess1", "delete_skill", {"name": "second"})
        action = fa.get_pending_action("sess1")
        assert action["action"] == "delete_skill"
