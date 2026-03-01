# =============================================================================
'''
    File Name : user_permissions.py

    Description : Per-user permission system for coco B. Controls which
                  capabilities each user can access (tools, scheduling, MCP,
                  admin commands, etc.). Backward compatible — if no config
                  file exists, all users get full access.

    Created on 2026-03-01

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================


# =============================================================================
# Import Section
# =============================================================================
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Set

from coco_b import PROJECT_ROOT

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("user_permissions")


# =============================================================================
# Permission enum — all gatable capabilities
# =============================================================================
class Permission(str, Enum):
    CHAT = "chat"
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    EMAIL = "email"
    CALENDAR = "calendar"
    BROWSE = "browse"
    FILES = "files"
    SCHEDULE = "schedule"
    TODO = "todo"
    MCP_TOOLS = "mcp_tools"
    MCP_MANAGE = "mcp_manage"
    SKILLS_CREATE = "skills_create"
    BACKGROUND_TASKS = "background_tasks"
    ADMIN = "admin"


# =============================================================================
# UserRole enum — predefined role tiers
# =============================================================================
class UserRole(str, Enum):
    ADMIN = "admin"
    POWER_USER = "power_user"
    USER = "user"
    RESTRICTED = "restricted"


# =============================================================================
# Default role definitions
# =============================================================================
DEFAULT_ROLES = {
    "admin": {"permissions": ["*"]},
    "power_user": {
        "permissions": [
            "chat", "web_search", "web_fetch", "email", "calendar",
            "browse", "files", "schedule", "todo", "mcp_tools",
            "skills_create", "background_tasks",
        ]
    },
    "user": {
        "permissions": [
            "chat", "web_search", "web_fetch", "schedule", "todo",
        ]
    },
    "restricted": {"permissions": ["chat"]},
}

ALL_PERMISSIONS = {p.value for p in Permission}


# =============================================================================
'''
    PermissionManager : Loads/saves user roles and checks permissions.
'''
# =============================================================================
class PermissionManager:
    """Manages per-user permissions with role-based defaults."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or (PROJECT_ROOT / "data")
        self._config_path = self._data_dir / "user_roles.json"
        self._config: Dict = {}
        self._enabled = False  # backward compat: disabled until file exists
        self._load()

    # =========================================================================
    # Persistence
    # =========================================================================
    def _load(self):
        """Load config from disk. If file missing, permissions are disabled (all allowed)."""
        if not self._config_path.exists():
            self._enabled = False
            self._config = self._default_config()
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._enabled = True
            # Ensure roles section has defaults
            if "roles" not in self._config:
                self._config["roles"] = dict(DEFAULT_ROLES)
            if "users" not in self._config:
                self._config["users"] = {}
            if "default_role" not in self._config:
                self._config["default_role"] = "restricted"
            logger.info("Loaded user_roles.json (%d users)", len(self._config.get("users", {})))
        except Exception as e:
            logger.error("Failed to load user_roles.json: %s", e)
            self._enabled = False
            self._config = self._default_config()

    def _save(self):
        """Persist config to disk and mark system as enabled."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)
        self._enabled = True

    @staticmethod
    def _default_config() -> Dict:
        return {
            "roles": dict(DEFAULT_ROLES),
            "users": {},
            "default_role": "restricted",
        }

    # =========================================================================
    # Core permission checks
    # =========================================================================
    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if a user has a specific permission.

        If permissions are not enabled (no config file), returns True for all
        (backward compatibility — existing installs keep full access).
        """
        if not self._enabled:
            return True

        perms = self.get_user_permissions(user_id)
        return "*" in perms or permission in perms

    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Get effective permissions for a user (role + custom - denied)."""
        if not self._enabled:
            return {"*"}

        role_name = self.get_user_role(user_id)
        role_def = self._config.get("roles", {}).get(role_name, {})
        base_perms = set(role_def.get("permissions", []))

        user_entry = self._config.get("users", {}).get(user_id, {})
        custom = set(user_entry.get("custom_permissions", []))
        denied = set(user_entry.get("denied_permissions", []))

        effective = (base_perms | custom) - denied
        return effective

    def get_user_role(self, user_id: str) -> str:
        """Get the role name for a user, falling back to default_role."""
        user_entry = self._config.get("users", {}).get(user_id, {})
        return user_entry.get("role", self._config.get("default_role", "restricted"))

    def is_admin(self, user_id: str) -> bool:
        """Shortcut: check if user has admin role or admin permission."""
        if not self._enabled:
            return True
        return self.has_permission(user_id, "admin")

    # =========================================================================
    # User management (admin-only operations)
    # =========================================================================
    def set_user_role(self, user_id: str, role: str, assigned_by: str = "admin") -> bool:
        """Assign a role to a user. Returns False if role doesn't exist."""
        if role not in self._config.get("roles", {}):
            return False

        users = self._config.setdefault("users", {})
        if user_id in users:
            users[user_id]["role"] = role
            users[user_id]["assigned_by"] = assigned_by
        else:
            users[user_id] = {
                "role": role,
                "custom_permissions": [],
                "denied_permissions": [],
                "assigned_by": assigned_by,
            }
        self._save()
        return True

    def grant_permission(self, user_id: str, permission: str) -> bool:
        """Add a custom permission grant for a user."""
        if permission not in ALL_PERMISSIONS:
            return False

        users = self._config.setdefault("users", {})
        if user_id not in users:
            users[user_id] = {
                "role": self._config.get("default_role", "restricted"),
                "custom_permissions": [],
                "denied_permissions": [],
                "assigned_by": "grant",
            }

        entry = users[user_id]
        custom = entry.setdefault("custom_permissions", [])
        if permission not in custom:
            custom.append(permission)
        # Remove from denied if present
        denied = entry.get("denied_permissions", [])
        if permission in denied:
            denied.remove(permission)
        self._save()
        return True

    def revoke_permission(self, user_id: str, permission: str) -> bool:
        """Deny a specific permission for a user."""
        if permission not in ALL_PERMISSIONS:
            return False

        users = self._config.setdefault("users", {})
        if user_id not in users:
            users[user_id] = {
                "role": self._config.get("default_role", "restricted"),
                "custom_permissions": [],
                "denied_permissions": [],
                "assigned_by": "revoke",
            }

        entry = users[user_id]
        denied = entry.setdefault("denied_permissions", [])
        if permission not in denied:
            denied.append(permission)
        # Remove from custom if present
        custom = entry.get("custom_permissions", [])
        if permission in custom:
            custom.remove(permission)
        self._save()
        return True

    def remove_user(self, user_id: str) -> bool:
        """Remove a user entry (falls back to default role)."""
        users = self._config.get("users", {})
        if user_id not in users:
            return False
        del users[user_id]
        self._save()
        return True

    def get_all_users(self) -> Dict:
        """Return all configured user entries."""
        return dict(self._config.get("users", {}))

    # =========================================================================
    # System prompt filtering
    # =========================================================================
    def get_permitted_capabilities(self, user_id: str) -> list:
        """Return a list of capability names the user can access.
        Used for filtering system prompt hints."""
        if not self._enabled:
            return list(ALL_PERMISSIONS)

        perms = self.get_user_permissions(user_id)
        if "*" in perms:
            return list(ALL_PERMISSIONS)
        return sorted(perms & ALL_PERMISSIONS)

    @property
    def enabled(self) -> bool:
        """Whether the permission system is active."""
        return self._enabled


# =============================================================================
'''
    End of File : user_permissions.py

    Project : mr_bot - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
