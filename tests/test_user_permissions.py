# =============================================================================
# test_user_permissions.py — Unit tests for PermissionManager
# =============================================================================

import json
import pytest
from pathlib import Path
from coco_b.core.user_permissions import (
    Permission,
    UserRole,
    PermissionManager,
    ALL_PERMISSIONS,
    DEFAULT_ROLES,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def data_dir(tmp_path):
    """Temporary data dir for isolated tests."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def config_file(data_dir):
    """Path to user_roles.json in the temp dir."""
    return data_dir / "user_roles.json"


@pytest.fixture
def write_config(config_file):
    """Helper to write a config and return the path."""
    def _write(cfg):
        with open(config_file, "w") as f:
            json.dump(cfg, f)
        return config_file
    return _write


@pytest.fixture
def basic_config(write_config):
    """Write a basic config with one admin user."""
    cfg = {
        "roles": dict(DEFAULT_ROLES),
        "users": {
            "admin_user": {
                "role": "admin",
                "custom_permissions": [],
                "denied_permissions": [],
                "assigned_by": "config",
            }
        },
        "default_role": "restricted",
    }
    write_config(cfg)
    return cfg


@pytest.fixture
def pm(data_dir, basic_config):
    """PermissionManager loaded with basic_config."""
    return PermissionManager(data_dir=data_dir)


@pytest.fixture
def pm_no_file(data_dir):
    """PermissionManager with no config file (backward compat mode)."""
    return PermissionManager(data_dir=data_dir)


# =============================================================================
# TestBackwardCompat — no config file means all allowed
# =============================================================================


class TestBackwardCompat:
    """Without user_roles.json, all permissions are granted (existing behavior)."""

    def test_no_file_all_allowed(self, pm_no_file):
        assert pm_no_file.has_permission("anyone", "chat") is True
        assert pm_no_file.has_permission("anyone", "admin") is True

    def test_no_file_is_admin(self, pm_no_file):
        assert pm_no_file.is_admin("anyone") is True

    def test_no_file_enabled_is_false(self, pm_no_file):
        assert pm_no_file.enabled is False

    def test_no_file_permissions_wildcard(self, pm_no_file):
        perms = pm_no_file.get_user_permissions("anyone")
        assert "*" in perms

    def test_no_file_permitted_capabilities_all(self, pm_no_file):
        caps = pm_no_file.get_permitted_capabilities("anyone")
        assert set(caps) == ALL_PERMISSIONS


# =============================================================================
# TestEnums
# =============================================================================


class TestEnums:
    """Permission and UserRole enums."""

    def test_permission_values(self):
        assert Permission.CHAT.value == "chat"
        assert Permission.ADMIN.value == "admin"
        assert Permission.SCHEDULE.value == "schedule"

    def test_user_role_values(self):
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.RESTRICTED.value == "restricted"

    def test_all_permissions_set(self):
        assert "chat" in ALL_PERMISSIONS
        assert "admin" in ALL_PERMISSIONS
        assert len(ALL_PERMISSIONS) == len(Permission)


# =============================================================================
# TestDefaultRoles — role permission sets
# =============================================================================


class TestDefaultRoles:
    """Each role has correct permissions."""

    def test_admin_wildcard(self, pm):
        assert pm.has_permission("admin_user", "admin") is True
        assert pm.has_permission("admin_user", "chat") is True
        assert pm.has_permission("admin_user", "mcp_manage") is True

    def test_admin_permissions_contain_wildcard(self, pm):
        perms = pm.get_user_permissions("admin_user")
        assert "*" in perms

    def test_restricted_only_chat(self, pm):
        """Unknown user gets default_role=restricted → only chat."""
        assert pm.has_permission("stranger", "chat") is True
        assert pm.has_permission("stranger", "schedule") is False
        assert pm.has_permission("stranger", "admin") is False

    def test_user_role_permissions(self, data_dir, write_config):
        cfg = {
            "roles": dict(DEFAULT_ROLES),
            "users": {"u1": {"role": "user", "custom_permissions": [], "denied_permissions": [], "assigned_by": "test"}},
            "default_role": "restricted",
        }
        write_config(cfg)
        pm = PermissionManager(data_dir=data_dir)
        assert pm.has_permission("u1", "chat") is True
        assert pm.has_permission("u1", "web_search") is True
        assert pm.has_permission("u1", "schedule") is True
        assert pm.has_permission("u1", "todo") is True
        assert pm.has_permission("u1", "email") is False
        assert pm.has_permission("u1", "mcp_tools") is False

    def test_power_user_permissions(self, data_dir, write_config):
        cfg = {
            "roles": dict(DEFAULT_ROLES),
            "users": {"pu": {"role": "power_user", "custom_permissions": [], "denied_permissions": [], "assigned_by": "test"}},
            "default_role": "restricted",
        }
        write_config(cfg)
        pm = PermissionManager(data_dir=data_dir)
        assert pm.has_permission("pu", "email") is True
        assert pm.has_permission("pu", "mcp_tools") is True
        assert pm.has_permission("pu", "admin") is False
        assert pm.has_permission("pu", "mcp_manage") is False


# =============================================================================
# TestGetRole
# =============================================================================


class TestGetRole:
    """get_user_role returns correct role or default."""

    def test_known_user(self, pm):
        assert pm.get_user_role("admin_user") == "admin"

    def test_unknown_user(self, pm):
        assert pm.get_user_role("stranger") == "restricted"

    def test_is_admin_known(self, pm):
        assert pm.is_admin("admin_user") is True

    def test_is_admin_unknown(self, pm):
        assert pm.is_admin("stranger") is False


# =============================================================================
# TestSetRole
# =============================================================================


class TestSetRole:
    """set_user_role changes role and persists."""

    def test_set_valid_role(self, pm):
        assert pm.set_user_role("new_user", "user", assigned_by="test") is True
        assert pm.get_user_role("new_user") == "user"

    def test_set_invalid_role(self, pm):
        assert pm.set_user_role("new_user", "nonexistent") is False

    def test_set_role_persists(self, pm, data_dir):
        pm.set_user_role("bob", "power_user", assigned_by="test")
        pm2 = PermissionManager(data_dir=data_dir)
        assert pm2.get_user_role("bob") == "power_user"

    def test_set_role_updates_existing(self, pm):
        pm.set_user_role("admin_user", "user", assigned_by="downgrade")
        assert pm.get_user_role("admin_user") == "user"
        assert pm.has_permission("admin_user", "admin") is False


# =============================================================================
# TestGrantRevoke
# =============================================================================


class TestGrantRevoke:
    """grant_permission / revoke_permission fine-grained control."""

    def test_grant_adds_permission(self, pm):
        assert pm.has_permission("stranger", "schedule") is False
        assert pm.grant_permission("stranger", "schedule") is True
        assert pm.has_permission("stranger", "schedule") is True

    def test_grant_invalid_permission(self, pm):
        assert pm.grant_permission("stranger", "fly_to_moon") is False

    def test_revoke_removes_permission(self, pm, data_dir, write_config):
        cfg = {
            "roles": dict(DEFAULT_ROLES),
            "users": {"u1": {"role": "user", "custom_permissions": [], "denied_permissions": [], "assigned_by": "test"}},
            "default_role": "restricted",
        }
        write_config(cfg)
        pm = PermissionManager(data_dir=data_dir)
        assert pm.has_permission("u1", "web_search") is True
        assert pm.revoke_permission("u1", "web_search") is True
        assert pm.has_permission("u1", "web_search") is False

    def test_revoke_invalid_permission(self, pm):
        assert pm.revoke_permission("stranger", "teleport") is False

    def test_grant_removes_from_denied(self, pm):
        pm.revoke_permission("stranger", "chat")
        assert pm.has_permission("stranger", "chat") is False
        pm.grant_permission("stranger", "chat")
        assert pm.has_permission("stranger", "chat") is True

    def test_revoke_removes_from_custom(self, pm):
        pm.grant_permission("stranger", "schedule")
        assert pm.has_permission("stranger", "schedule") is True
        pm.revoke_permission("stranger", "schedule")
        assert pm.has_permission("stranger", "schedule") is False

    def test_grant_persist(self, pm, data_dir):
        pm.grant_permission("stranger", "todo")
        pm2 = PermissionManager(data_dir=data_dir)
        assert pm2.has_permission("stranger", "todo") is True


# =============================================================================
# TestRemoveUser
# =============================================================================


class TestRemoveUser:
    """remove_user deletes entry, user falls back to default."""

    def test_remove_existing(self, pm):
        assert pm.remove_user("admin_user") is True
        assert pm.get_user_role("admin_user") == "restricted"

    def test_remove_nonexistent(self, pm):
        assert pm.remove_user("nobody") is False


# =============================================================================
# TestGetAllUsers
# =============================================================================


class TestGetAllUsers:
    """get_all_users returns configured users dict."""

    def test_returns_users(self, pm):
        users = pm.get_all_users()
        assert "admin_user" in users

    def test_empty_when_no_file(self, pm_no_file):
        users = pm_no_file.get_all_users()
        assert users == {}


# =============================================================================
# TestPermittedCapabilities
# =============================================================================


class TestPermittedCapabilities:
    """get_permitted_capabilities for system prompt filtering."""

    def test_admin_gets_all(self, pm):
        caps = pm.get_permitted_capabilities("admin_user")
        assert set(caps) == ALL_PERMISSIONS

    def test_restricted_gets_chat_only(self, pm):
        caps = pm.get_permitted_capabilities("stranger")
        assert caps == ["chat"]

    def test_user_role_capabilities(self, pm):
        pm.set_user_role("u1", "user")
        caps = pm.get_permitted_capabilities("u1")
        assert "chat" in caps
        assert "web_search" in caps
        assert "email" not in caps


# =============================================================================
# TestPersistenceRoundTrip
# =============================================================================


class TestPersistenceRoundTrip:
    """Save/load roundtrip preserves all data."""

    def test_full_roundtrip(self, data_dir, write_config):
        cfg = {
            "roles": dict(DEFAULT_ROLES),
            "users": {},
            "default_role": "restricted",
        }
        write_config(cfg)
        pm = PermissionManager(data_dir=data_dir)
        pm.set_user_role("alice", "power_user", assigned_by="test")
        pm.grant_permission("alice", "admin")
        pm.revoke_permission("alice", "email")

        pm2 = PermissionManager(data_dir=data_dir)
        assert pm2.get_user_role("alice") == "power_user"
        assert pm2.has_permission("alice", "admin") is True
        assert pm2.has_permission("alice", "email") is False
        assert pm2.has_permission("alice", "mcp_tools") is True


# =============================================================================
# TestEdgeCases
# =============================================================================


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_corrupt_config_falls_back(self, data_dir):
        """Bad JSON → permissions disabled (all allowed)."""
        config_path = data_dir / "user_roles.json"
        config_path.write_text("{bad json")
        pm = PermissionManager(data_dir=data_dir)
        assert pm.enabled is False
        assert pm.has_permission("anyone", "admin") is True

    def test_missing_roles_section(self, data_dir, write_config):
        """Config with no roles section gets defaults."""
        write_config({"users": {}, "default_role": "restricted"})
        pm = PermissionManager(data_dir=data_dir)
        assert pm.enabled is True
        # Should still have default roles
        assert pm.get_user_role("anyone") == "restricted"

    def test_enabled_after_set_role(self, data_dir):
        """Setting a role on a new PM (no file) creates the file and enables."""
        pm = PermissionManager(data_dir=data_dir)
        assert pm.enabled is False
        # Calling set_user_role saves the file
        pm.set_user_role("admin", "admin")
        assert (data_dir / "user_roles.json").exists()

    def test_data_dir_created_on_save(self, tmp_path):
        """Save creates data dir if missing."""
        nested = tmp_path / "deep" / "data"
        pm = PermissionManager(data_dir=nested)
        pm.set_user_role("u1", "admin")
        assert (nested / "user_roles.json").exists()

    def test_wildcard_in_permissions(self, data_dir, write_config):
        """Wildcard '*' in role grants all permissions."""
        write_config({
            "roles": {"super": {"permissions": ["*"]}},
            "users": {"god": {"role": "super", "custom_permissions": [], "denied_permissions": [], "assigned_by": "test"}},
            "default_role": "restricted",
        })
        pm = PermissionManager(data_dir=data_dir)
        for p in Permission:
            assert pm.has_permission("god", p.value) is True


# =============================================================================
# TestRouterIntegration — tests that simulate router-like usage
# =============================================================================


class TestRouterIntegration:
    """Simulate how the router would use PermissionManager."""

    @pytest.fixture
    def pm_multi(self, data_dir, write_config):
        """PM with multiple users at different roles."""
        write_config({
            "roles": dict(DEFAULT_ROLES),
            "users": {
                "admin_phone": {"role": "admin", "custom_permissions": [], "denied_permissions": [], "assigned_by": "config"},
                "friend": {"role": "user", "custom_permissions": [], "denied_permissions": [], "assigned_by": "config"},
                "kid": {"role": "restricted", "custom_permissions": [], "denied_permissions": [], "assigned_by": "config"},
            },
            "default_role": "restricted",
        })
        return PermissionManager(data_dir=data_dir)

    def test_schedule_gating(self, pm_multi):
        assert pm_multi.has_permission("admin_phone", "schedule") is True
        assert pm_multi.has_permission("friend", "schedule") is True
        assert pm_multi.has_permission("kid", "schedule") is False

    def test_web_search_gating(self, pm_multi):
        assert pm_multi.has_permission("admin_phone", "web_search") is True
        assert pm_multi.has_permission("friend", "web_search") is True
        assert pm_multi.has_permission("kid", "web_search") is False

    def test_mcp_tools_gating(self, pm_multi):
        assert pm_multi.has_permission("admin_phone", "mcp_tools") is True
        assert pm_multi.has_permission("friend", "mcp_tools") is False
        assert pm_multi.has_permission("kid", "mcp_tools") is False

    def test_admin_commands_gating(self, pm_multi):
        assert pm_multi.is_admin("admin_phone") is True
        assert pm_multi.is_admin("friend") is False
        assert pm_multi.is_admin("kid") is False

    def test_capability_hints_filtering(self, pm_multi):
        admin_caps = pm_multi.get_permitted_capabilities("admin_phone")
        friend_caps = pm_multi.get_permitted_capabilities("friend")
        kid_caps = pm_multi.get_permitted_capabilities("kid")

        assert "schedule" in admin_caps
        assert "schedule" in friend_caps
        assert "schedule" not in kid_caps

        assert "mcp_tools" in admin_caps
        assert "mcp_tools" not in friend_caps

    def test_unknown_user_is_restricted(self, pm_multi):
        """Users not in config get default_role=restricted."""
        assert pm_multi.get_user_role("random_number") == "restricted"
        assert pm_multi.has_permission("random_number", "chat") is True
        assert pm_multi.has_permission("random_number", "schedule") is False

    def test_grant_then_check(self, pm_multi):
        """Admin grants a restricted user schedule access."""
        assert pm_multi.has_permission("kid", "schedule") is False
        pm_multi.grant_permission("kid", "schedule")
        assert pm_multi.has_permission("kid", "schedule") is True

    def test_revoke_from_role(self, pm_multi):
        """Revoke web_search from a user-role user."""
        assert pm_multi.has_permission("friend", "web_search") is True
        pm_multi.revoke_permission("friend", "web_search")
        assert pm_multi.has_permission("friend", "web_search") is False
        # Other permissions unaffected
        assert pm_multi.has_permission("friend", "chat") is True
        assert pm_multi.has_permission("friend", "todo") is True

    def test_promote_user(self, pm_multi):
        """Promote restricted user to power_user."""
        assert pm_multi.has_permission("kid", "email") is False
        pm_multi.set_user_role("kid", "power_user", assigned_by="admin_phone")
        assert pm_multi.has_permission("kid", "email") is True
        assert pm_multi.has_permission("kid", "mcp_tools") is True

    def test_demote_user(self, pm_multi):
        """Demote power_user → restricted."""
        pm_multi.set_user_role("friend", "restricted", assigned_by="admin_phone")
        assert pm_multi.has_permission("friend", "web_search") is False
        assert pm_multi.has_permission("friend", "chat") is True


# =============================================================================
# TestRouterCommands — test permission commands via actual router
# =============================================================================


class TestRouterCommands:
    """Test the /my-permissions, /user-role, /grant, /revoke, /users commands."""

    @pytest.fixture
    def router(self, tmp_path):
        """Create a minimal router with permissions enabled."""
        from unittest.mock import MagicMock
        from coco_b.core.sessions import SessionManager
        from coco_b.core.router import MessageRouter
        from coco_b.core.memory import SQLiteMemory

        sm = SessionManager(str(tmp_path / "sessions"))
        llm = MagicMock()
        llm.config = MagicMock()
        llm.config.base_url = "http://test"
        llm.config.model = "test"
        llm.model_name = "test"
        llm.provider_name = "test"
        llm.chat = MagicMock(return_value="Hello")
        r = MessageRouter(sm, llm)
        r.memory_store = SQLiteMemory(db_path=str(tmp_path / "test_memory.db"))

        # Write a permission config
        data_dir = r._permission_manager._data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "roles": dict(DEFAULT_ROLES),
            "users": {
                "admin1": {"role": "admin", "custom_permissions": [], "denied_permissions": [], "assigned_by": "config"},
                "user1": {"role": "user", "custom_permissions": [], "denied_permissions": [], "assigned_by": "config"},
            },
            "default_role": "restricted",
        }
        with open(data_dir / "user_roles.json", "w") as f:
            json.dump(cfg, f)
        r._permission_manager._load()
        return r

    def test_my_permissions_admin(self, router):
        result = router.handle_command("/my-permissions", "test:admin1")
        assert "admin" in result
        assert "Role" in result or "role" in result

    def test_my_permissions_restricted(self, router):
        result = router.handle_command("/my-permissions", "test:stranger")
        assert "restricted" in result
        assert "chat" in result

    def test_my_permissions_disabled(self, tmp_path):
        """When no config file, shows disabled message."""
        from unittest.mock import MagicMock
        from coco_b.core.sessions import SessionManager
        from coco_b.core.router import MessageRouter
        from coco_b.core.memory import SQLiteMemory

        sm = SessionManager(str(tmp_path / "sessions"))
        llm = MagicMock()
        llm.config = MagicMock()
        llm.config.base_url = "http://test"
        llm.config.model = "test"
        llm.model_name = "test"
        llm.provider_name = "test"
        r = MessageRouter(sm, llm)
        r.memory_store = SQLiteMemory(db_path=str(tmp_path / "test_memory.db"))
        # Override permission manager to use a temp dir with no config
        r._permission_manager = PermissionManager(data_dir=tmp_path / "empty_data")
        result = r.handle_command("/my-permissions", "test:anyone")
        assert "not active" in result

    def test_user_role_show(self, router):
        result = router.handle_command("/user-role user1", "test:admin1")
        assert "user" in result

    def test_user_role_set(self, router):
        result = router.handle_command("/user-role user1 power_user", "test:admin1")
        assert "power_user" in result
        assert router._permission_manager.get_user_role("user1") == "power_user"

    def test_user_role_denied_non_admin(self, router):
        result = router.handle_command("/user-role admin1", "test:user1")
        assert "denied" in result.lower() or "Permission denied" in result

    def test_grant_permission(self, router):
        result = router.handle_command("/grant user1 email", "test:admin1")
        assert "Granted" in result
        assert router._permission_manager.has_permission("user1", "email") is True

    def test_grant_denied_non_admin(self, router):
        result = router.handle_command("/grant user1 email", "test:user1")
        assert "denied" in result.lower() or "Permission denied" in result

    def test_revoke_permission(self, router):
        result = router.handle_command("/revoke user1 web_search", "test:admin1")
        assert "Revoked" in result
        assert router._permission_manager.has_permission("user1", "web_search") is False

    def test_users_list(self, router):
        result = router.handle_command("/users", "test:admin1")
        assert "admin1" in result
        assert "user1" in result

    def test_users_denied_non_admin(self, router):
        result = router.handle_command("/users", "test:user1")
        assert "denied" in result.lower() or "Permission denied" in result

    def test_is_skill_invocation_new_commands(self, router):
        """New permission commands are recognized as built-in, not skills."""
        for cmd in ["/my-permissions", "/user-role admin1", "/grant u1 chat",
                    "/revoke u1 chat", "/users"]:
            is_skill, _, _ = router.is_skill_invocation(cmd)
            assert is_skill is False, f"{cmd} should not be a skill"

    def test_help_includes_permissions(self, router):
        result = router.handle_command("/help", "test:admin1")
        assert "User Permissions" in result
        assert "/my-permissions" in result
