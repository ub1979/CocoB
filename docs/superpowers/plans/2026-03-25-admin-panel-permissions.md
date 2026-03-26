# Admin Panel & Permission System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-based admin panel with login protection, cross-platform identity resolution, and a permission request flow so denied users can request access and admins can approve/deny from the UI.

**Architecture:** Login gate wraps the entire Flet app — no access without credentials. First run triggers admin setup. Admin tab (5th nav item) shows user management, permission requests, and identity linking. Permission denials on any channel include a request-access hint. Identity resolver maps platform-specific IDs to canonical users so permissions follow the person, not the platform.

**Tech Stack:** Python 3.10+, Flet UI framework, existing SecureStorage for credential hashing, JSON file storage for identity map and permission requests.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/skillforge/core/identity_resolver.py` | Create | Maps platform IDs → canonical user ID |
| `src/skillforge/core/permission_requests.py` | Create | Permission request queue (submit/approve/deny/list) |
| `src/skillforge/core/user_permissions.py` | Modify | Integrate identity resolver, improve denial messages |
| `src/skillforge/core/router.py` | Modify | Use identity resolver, better denial messages with request hints, new commands |
| `src/skillforge/flet/views/login.py` | Create | Login screen + first-run admin setup |
| `src/skillforge/flet/views/admin.py` | Create | Admin dashboard: user mgmt, requests, identity linking |
| `src/skillforge/flet/app.py` | Modify | Add login gate, 5th nav tab (Admin), wire identity resolver |
| `src/skillforge/flet/storage.py` | Modify (minor) | Add admin credentials helpers |
| `tests/test_identity_resolver.py` | Create | Tests for identity mapping |
| `tests/test_permission_requests.py` | Create | Tests for request queue |
| `tests/test_admin_login.py` | Create | Tests for login/setup flow |

---

## Chunk 1: Identity Resolver

### Task 1: Identity Resolver — Core Module

**Files:**
- Create: `src/skillforge/core/identity_resolver.py`
- Test: `tests/test_identity_resolver.py`

- [ ] **Step 1: Write failing tests for identity resolver**

```python
# tests/test_identity_resolver.py
"""Tests for cross-platform identity resolution."""
import pytest
from pathlib import Path
from skillforge.core.identity_resolver import IdentityResolver


@pytest.fixture
def resolver(tmp_path):
    return IdentityResolver(data_dir=tmp_path)


class TestIdentityResolver:
    """Core identity resolution."""

    def test_no_mapping_returns_raw_id(self, resolver):
        """Unknown IDs pass through unchanged."""
        assert resolver.resolve("telegram:12345") == "telegram:12345"

    def test_link_and_resolve(self, resolver):
        """Linked identities resolve to canonical ID."""
        resolver.link("admin", "telegram:12345")
        resolver.link("admin", "whatsapp:+923001234567")
        assert resolver.resolve("telegram:12345") == "admin"
        assert resolver.resolve("whatsapp:+923001234567") == "admin"

    def test_unlink(self, resolver):
        """Unlinking reverts to raw ID."""
        resolver.link("admin", "telegram:12345")
        resolver.unlink("telegram:12345")
        assert resolver.resolve("telegram:12345") == "telegram:12345"

    def test_get_aliases(self, resolver):
        """Get all platform aliases for a canonical user."""
        resolver.link("admin", "telegram:12345")
        resolver.link("admin", "whatsapp:+923001234567")
        resolver.link("admin", "web:admin@email.com")
        aliases = resolver.get_aliases("admin")
        assert len(aliases) == 3
        assert "telegram:12345" in aliases

    def test_get_all_users(self, resolver):
        """List all canonical users with their aliases."""
        resolver.link("admin", "telegram:111")
        resolver.link("user1", "whatsapp:+123")
        users = resolver.get_all_users()
        assert "admin" in users
        assert "user1" in users

    def test_persistence(self, tmp_path):
        """Data survives reload."""
        r1 = IdentityResolver(data_dir=tmp_path)
        r1.link("admin", "telegram:12345")
        r2 = IdentityResolver(data_dir=tmp_path)
        assert r2.resolve("telegram:12345") == "admin"

    def test_duplicate_link_overwrites(self, resolver):
        """Re-linking a platform ID to a new canonical user updates it."""
        resolver.link("user1", "telegram:12345")
        resolver.link("admin", "telegram:12345")
        assert resolver.resolve("telegram:12345") == "admin"

    def test_remove_user(self, resolver):
        """Removing a canonical user clears all their aliases."""
        resolver.link("admin", "telegram:111")
        resolver.link("admin", "whatsapp:222")
        resolver.remove_user("admin")
        assert resolver.resolve("telegram:111") == "telegram:111"
        assert resolver.get_aliases("admin") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_identity_resolver.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement IdentityResolver**

```python
# src/skillforge/core/identity_resolver.py
"""
Cross-platform identity resolution.

Maps platform-specific IDs (telegram:12345, whatsapp:+923001234567, web:admin@email.com)
to canonical user IDs so permissions and memory follow the person, not the platform.

Storage: data/identity_map.json
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from skillforge import PROJECT_ROOT

logger = logging.getLogger("identity_resolver")


class IdentityResolver:
    """Maps platform-specific IDs to canonical user IDs."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or (PROJECT_ROOT / "data")
        self._map_path = self._data_dir / "identity_map.json"
        self._alias_to_canonical: Dict[str, str] = {}  # "telegram:123" -> "admin"
        self._canonical_to_aliases: Dict[str, List[str]] = {}  # "admin" -> ["telegram:123", ...]
        self._load()

    def _load(self):
        if not self._map_path.exists():
            return
        try:
            with open(self._map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._alias_to_canonical = data.get("alias_to_canonical", {})
            self._canonical_to_aliases = data.get("canonical_to_aliases", {})
        except Exception as e:
            logger.error("Failed to load identity_map.json: %s", e)

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._map_path, "w", encoding="utf-8") as f:
            json.dump({
                "alias_to_canonical": self._alias_to_canonical,
                "canonical_to_aliases": self._canonical_to_aliases,
            }, f, indent=2)

    def resolve(self, platform_id: str) -> str:
        """Resolve a platform-specific ID to canonical user ID.
        Returns the raw platform_id if no mapping exists."""
        return self._alias_to_canonical.get(platform_id, platform_id)

    def link(self, canonical_id: str, platform_id: str):
        """Link a platform ID to a canonical user."""
        # Remove from old canonical user if re-linking
        old_canonical = self._alias_to_canonical.get(platform_id)
        if old_canonical and old_canonical != canonical_id:
            aliases = self._canonical_to_aliases.get(old_canonical, [])
            if platform_id in aliases:
                aliases.remove(platform_id)

        self._alias_to_canonical[platform_id] = canonical_id
        aliases = self._canonical_to_aliases.setdefault(canonical_id, [])
        if platform_id not in aliases:
            aliases.append(platform_id)
        self._save()

    def unlink(self, platform_id: str):
        """Remove a platform ID mapping."""
        canonical = self._alias_to_canonical.pop(platform_id, None)
        if canonical:
            aliases = self._canonical_to_aliases.get(canonical, [])
            if platform_id in aliases:
                aliases.remove(platform_id)
        self._save()

    def get_aliases(self, canonical_id: str) -> List[str]:
        """Get all platform aliases for a canonical user."""
        return list(self._canonical_to_aliases.get(canonical_id, []))

    def get_all_users(self) -> Dict[str, List[str]]:
        """Get all canonical users and their aliases."""
        return dict(self._canonical_to_aliases)

    def remove_user(self, canonical_id: str):
        """Remove a canonical user and all their aliases."""
        aliases = self._canonical_to_aliases.pop(canonical_id, [])
        for alias in aliases:
            self._alias_to_canonical.pop(alias, None)
        self._save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_identity_resolver.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/skillforge/core/identity_resolver.py tests/test_identity_resolver.py
git commit -m "feat: add cross-platform identity resolver"
```

---

## Chunk 2: Permission Requests

### Task 2: Permission Request Queue

**Files:**
- Create: `src/skillforge/core/permission_requests.py`
- Test: `tests/test_permission_requests.py`

- [ ] **Step 1: Write failing tests for permission requests**

```python
# tests/test_permission_requests.py
"""Tests for permission request queue."""
import pytest
from pathlib import Path
from skillforge.core.permission_requests import PermissionRequestManager


@pytest.fixture
def mgr(tmp_path):
    return PermissionRequestManager(data_dir=tmp_path)


class TestPermissionRequests:

    def test_submit_request(self, mgr):
        """User can submit a permission request."""
        req_id = mgr.submit("user1", "skills_create", "I need to create skills for my team")
        assert req_id is not None
        pending = mgr.get_pending()
        assert len(pending) == 1
        assert pending[0]["user_id"] == "user1"
        assert pending[0]["permission"] == "skills_create"
        assert pending[0]["status"] == "pending"

    def test_approve_request(self, mgr):
        """Admin can approve a request."""
        req_id = mgr.submit("user1", "web_search")
        result = mgr.approve(req_id, "admin1")
        assert result is True
        pending = mgr.get_pending()
        assert len(pending) == 0

    def test_deny_request(self, mgr):
        """Admin can deny a request."""
        req_id = mgr.submit("user1", "web_search")
        result = mgr.deny(req_id, "admin1", reason="Not needed")
        assert result is True
        pending = mgr.get_pending()
        assert len(pending) == 0

    def test_get_user_requests(self, mgr):
        """User can see their own request history."""
        mgr.submit("user1", "web_search")
        mgr.submit("user1", "schedule")
        mgr.submit("user2", "files")
        reqs = mgr.get_user_requests("user1")
        assert len(reqs) == 2

    def test_duplicate_pending_rejected(self, mgr):
        """Cannot submit duplicate pending request for same permission."""
        mgr.submit("user1", "web_search")
        req_id2 = mgr.submit("user1", "web_search")
        assert req_id2 is None
        assert len(mgr.get_pending()) == 1

    def test_persistence(self, tmp_path):
        """Requests survive reload."""
        m1 = PermissionRequestManager(data_dir=tmp_path)
        m1.submit("user1", "web_search")
        m2 = PermissionRequestManager(data_dir=tmp_path)
        assert len(m2.get_pending()) == 1

    def test_approve_nonexistent(self, mgr):
        """Approving nonexistent request returns False."""
        assert mgr.approve("fake-id", "admin") is False

    def test_request_has_timestamp(self, mgr):
        """Requests include submission timestamp."""
        req_id = mgr.submit("user1", "schedule")
        pending = mgr.get_pending()
        assert "timestamp" in pending[0]

    def test_approved_request_includes_approver(self, mgr):
        """Approved requests record who approved."""
        req_id = mgr.submit("user1", "schedule")
        mgr.approve(req_id, "admin1")
        history = mgr.get_user_requests("user1")
        assert history[0]["approved_by"] == "admin1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_permission_requests.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement PermissionRequestManager**

```python
# src/skillforge/core/permission_requests.py
"""
Permission request queue.

Users who are denied a permission can submit a request.
Admins can approve or deny requests from the admin panel or chat commands.
Storage: data/permission_requests.json
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from skillforge import PROJECT_ROOT

logger = logging.getLogger("permission_requests")


class PermissionRequestManager:
    """Manages permission requests from users to admins."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or (PROJECT_ROOT / "data")
        self._requests_path = self._data_dir / "permission_requests.json"
        self._requests: List[Dict] = []
        self._load()

    def _load(self):
        if not self._requests_path.exists():
            return
        try:
            with open(self._requests_path, "r", encoding="utf-8") as f:
                self._requests = json.load(f)
        except Exception as e:
            logger.error("Failed to load permission_requests.json: %s", e)

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._requests_path, "w", encoding="utf-8") as f:
            json.dump(self._requests, f, indent=2)

    def submit(self, user_id: str, permission: str, reason: str = "") -> Optional[str]:
        """Submit a permission request. Returns request ID, or None if duplicate pending."""
        # Check for duplicate pending
        for req in self._requests:
            if (req["user_id"] == user_id
                    and req["permission"] == permission
                    and req["status"] == "pending"):
                return None

        req_id = str(uuid.uuid4())[:8]
        self._requests.append({
            "id": req_id,
            "user_id": user_id,
            "permission": permission,
            "reason": reason,
            "status": "pending",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "approved_by": None,
            "decided_at": None,
            "deny_reason": None,
        })
        self._save()
        return req_id

    def approve(self, req_id: str, admin_id: str) -> bool:
        """Approve a pending request."""
        for req in self._requests:
            if req["id"] == req_id and req["status"] == "pending":
                req["status"] = "approved"
                req["approved_by"] = admin_id
                req["decided_at"] = datetime.now(tz=timezone.utc).isoformat()
                self._save()
                return True
        return False

    def deny(self, req_id: str, admin_id: str, reason: str = "") -> bool:
        """Deny a pending request."""
        for req in self._requests:
            if req["id"] == req_id and req["status"] == "pending":
                req["status"] = "denied"
                req["approved_by"] = admin_id
                req["decided_at"] = datetime.now(tz=timezone.utc).isoformat()
                req["deny_reason"] = reason
                self._save()
                return True
        return False

    def get_pending(self) -> List[Dict]:
        """Get all pending requests."""
        return [r for r in self._requests if r["status"] == "pending"]

    def get_user_requests(self, user_id: str) -> List[Dict]:
        """Get all requests by a specific user."""
        return [r for r in self._requests if r["user_id"] == user_id]

    def get_all(self) -> List[Dict]:
        """Get all requests."""
        return list(self._requests)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_permission_requests.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/skillforge/core/permission_requests.py tests/test_permission_requests.py
git commit -m "feat: add permission request queue"
```

---

## Chunk 3: Login Gate & Admin Setup

### Task 3: Login View for Flet UI

**Files:**
- Create: `src/skillforge/flet/views/login.py`
- Modify: `src/skillforge/flet/storage.py` (add `has_admin`, `set_admin_credentials`, `verify_admin`)
- Test: `tests/test_admin_login.py`

- [ ] **Step 1: Write failing tests for admin credential flow**

```python
# tests/test_admin_login.py
"""Tests for admin login and credential management."""
import pytest
from pathlib import Path
from skillforge.flet.storage import SecureStorage


@pytest.fixture
def storage(tmp_path):
    return SecureStorage(storage_dir=tmp_path)


class TestAdminCredentials:

    def test_no_admin_by_default(self, storage):
        assert storage.has_admin() is False

    def test_set_and_verify_admin(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.has_admin() is True
        assert storage.verify_admin("admin", "securepass123") is True

    def test_wrong_password_rejected(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.verify_admin("admin", "wrongpass") is False

    def test_wrong_username_rejected(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.verify_admin("other", "securepass123") is False

    def test_get_admin_username(self, storage):
        storage.set_admin_credentials("myuser", "pass")
        assert storage.get_admin_username() == "myuser"

    def test_admin_persists(self, tmp_path):
        s1 = SecureStorage(storage_dir=tmp_path)
        s1.set_admin_credentials("admin", "pass123")
        s2 = SecureStorage(storage_dir=tmp_path)
        assert s2.has_admin() is True
        assert s2.verify_admin("admin", "pass123") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_admin_login.py -v`
Expected: FAIL with AttributeError (methods don't exist yet)

- [ ] **Step 3: Add admin credential methods to SecureStorage**

In `src/skillforge/flet/storage.py`, add these methods to the `SecureStorage` class (after `clear_password`):

```python
    def set_admin_credentials(self, username: str, password: str):
        """Set admin login credentials (username + hashed password)."""
        import hashlib, os, base64
        salt = os.urandom(16)
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        self._data['_admin_username'] = username
        self._data['_admin_salt'] = base64.b64encode(salt).decode()
        self._data['_admin_hash'] = base64.b64encode(pw_hash).decode()
        self._save()

    def verify_admin(self, username: str, password: str) -> bool:
        """Verify admin credentials."""
        import hashlib, base64
        if '_admin_hash' not in self._data:
            return False
        if self._data.get('_admin_username') != username:
            return False
        salt = base64.b64decode(self._data['_admin_salt'].encode())
        stored_hash = base64.b64decode(self._data['_admin_hash'].encode())
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return pw_hash == stored_hash

    def has_admin(self) -> bool:
        """Check if admin credentials are configured."""
        return '_admin_hash' in self._data

    def get_admin_username(self) -> str:
        """Get the admin username."""
        return self._data.get('_admin_username', '')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_admin_login.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Create the Login view**

Create `src/skillforge/flet/views/login.py` — a full-screen login gate. On first run, shows "Create Admin Account" form. On subsequent runs, shows login form. Calls a callback with `True` on success.

```python
# src/skillforge/flet/views/login.py
"""
Login gate for SkillForge Flet UI.

First run: admin account setup form.
Subsequent runs: login form.
On success, calls on_authenticated callback to show the main app.
"""

import flet as ft
from skillforge import PROJECT_ROOT
from skillforge.flet.theme import AppColors
from skillforge.flet.storage import SecureStorage


class LoginView:
    """Login screen that gates access to the main application."""

    def __init__(self, page: ft.Page, storage: SecureStorage, on_authenticated):
        self.page = page
        self.storage = storage
        self.on_authenticated = on_authenticated
        self._is_setup = not storage.has_admin()

    def build(self) -> ft.Container:
        """Build the login/setup view."""
        icon_path = PROJECT_ROOT / "icon" / "icon.png"

        self.username_field = ft.TextField(
            label="Username",
            width=300,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.ACCENT,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        self.password_field = ft.TextField(
            label="Password",
            password=True,
            can_reveal_password=True,
            width=300,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.ACCENT,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            on_submit=lambda e: self._handle_submit(e),
        )
        self.confirm_field = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True,
            width=300,
            border_color=AppColors.BORDER,
            focused_border_color=AppColors.ACCENT,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            visible=self._is_setup,
            on_submit=lambda e: self._handle_submit(e),
        )
        self.error_text = ft.Text("", color="red", size=13, visible=False)
        self.submit_btn = ft.ElevatedButton(
            text="Create Admin Account" if self._is_setup else "Login",
            on_click=self._handle_submit,
            width=300,
            bgcolor=AppColors.ACCENT,
            color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )

        title = "Create Admin Account" if self._is_setup else "Login to SkillForge"
        subtitle = ("Set up your admin credentials to get started."
                     if self._is_setup
                     else "Enter your credentials to continue.")

        logo = ft.Image(src=str(icon_path), width=120, height=120) if icon_path.exists() else ft.Container()

        form_controls = [
            logo,
            ft.Text(title, size=24, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_PRIMARY),
            ft.Text(subtitle, size=14, color=AppColors.TEXT_SECONDARY),
            ft.Container(height=16),
            self.username_field,
            self.password_field,
            self.confirm_field,
            self.error_text,
            ft.Container(height=8),
            self.submit_btn,
        ]

        return ft.Container(
            content=ft.Column(
                controls=form_controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            expand=True,
            alignment=ft.alignment.center,
            bgcolor=AppColors.BACKGROUND,
        )

    def _handle_submit(self, e):
        """Handle login or setup submission."""
        username = self.username_field.value or ""
        password = self.password_field.value or ""

        if not username or not password:
            self._show_error("Username and password are required.")
            return

        if self._is_setup:
            confirm = self.confirm_field.value or ""
            if password != confirm:
                self._show_error("Passwords do not match.")
                return
            if len(password) < 6:
                self._show_error("Password must be at least 6 characters.")
                return
            self.storage.set_admin_credentials(username, password)
            self.on_authenticated(username)
        else:
            if self.storage.verify_admin(username, password):
                self.on_authenticated(username)
            else:
                self._show_error("Invalid username or password.")

    def _show_error(self, msg: str):
        self.error_text.value = msg
        self.error_text.visible = True
        self.page.update()
```

- [ ] **Step 6: Commit**

```bash
git add src/skillforge/flet/storage.py src/skillforge/flet/views/login.py tests/test_admin_login.py
git commit -m "feat: add login gate and admin setup"
```

---

## Chunk 4: Admin Dashboard View

### Task 4: Admin Panel View

**Files:**
- Create: `src/skillforge/flet/views/admin.py`

- [ ] **Step 1: Create the admin dashboard view**

The admin panel has 3 sub-tabs: Users, Permission Requests, Identity Linking.

```python
# src/skillforge/flet/views/admin.py
"""
Admin dashboard — user management, permission requests, identity linking.

Only accessible to authenticated admin users via the Flet UI.
"""

import flet as ft
from flet import Icons as icons

from skillforge.flet.theme import AppColors, Spacing
from skillforge.flet.components.widgets import StyledButton
from skillforge.core.user_permissions import PermissionManager, ALL_PERMISSIONS, DEFAULT_ROLES
from skillforge.core.permission_requests import PermissionRequestManager
from skillforge.core.identity_resolver import IdentityResolver


class AdminView:
    """Admin dashboard with user management, permission requests, and identity linking."""

    def __init__(self, page: ft.Page, permission_manager: PermissionManager,
                 request_manager: PermissionRequestManager,
                 identity_resolver: IdentityResolver):
        self.page = page
        self.perm_mgr = permission_manager
        self.req_mgr = request_manager
        self.id_resolver = identity_resolver

    def build(self) -> ft.Column:
        """Build the admin dashboard."""
        self._users_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)
        self._requests_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)
        self._identity_list = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)

        tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(
                    text="Users & Roles",
                    icon=icons.PEOPLE,
                    content=self._build_users_tab(),
                ),
                ft.Tab(
                    text="Permission Requests",
                    icon=icons.APPROVAL,
                    content=self._build_requests_tab(),
                ),
                ft.Tab(
                    text="Identity Linking",
                    icon=icons.LINK,
                    content=self._build_identity_tab(),
                ),
            ],
            on_change=lambda e: self.refresh(),
            expand=True,
            label_color=AppColors.TEXT_SECONDARY,
            indicator_color=AppColors.ACCENT,
            divider_color=AppColors.BORDER,
        )

        return ft.Column([
            ft.Row([
                ft.Icon(icons.ADMIN_PANEL_SETTINGS, color=AppColors.ACCENT, size=28),
                ft.Text("Admin Panel", size=22, weight=ft.FontWeight.BOLD,
                         color=AppColors.TEXT_PRIMARY),
            ], spacing=Spacing.SM),
            tabs,
        ], expand=True, spacing=Spacing.MD)

    # -----------------------------------------------------------------
    # Users & Roles tab
    # -----------------------------------------------------------------

    def _build_users_tab(self) -> ft.Container:
        self._new_user_id = ft.TextField(
            label="User ID", width=200, dense=True,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        self._new_user_role = ft.Dropdown(
            label="Role", width=160, dense=True,
            border_color=AppColors.BORDER,
            text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
            options=[ft.dropdown.Option(r) for r in DEFAULT_ROLES],
        )
        add_btn = StyledButton("Add User", icon=icons.PERSON_ADD,
                               on_click=self._add_user)

        return ft.Container(
            content=ft.Column([
                ft.Text("Manage user roles and permissions", size=13,
                         color=AppColors.TEXT_SECONDARY),
                ft.Row([self._new_user_id, self._new_user_role, add_btn], spacing=Spacing.SM),
                ft.Divider(color=AppColors.BORDER),
                self._users_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_users(self):
        self._users_list.controls.clear()
        users = self.perm_mgr.get_all_users()
        if not users:
            self._users_list.controls.append(
                ft.Text("No users configured. All users have full access.",
                         color=AppColors.TEXT_SECONDARY, italic=True))
        for uid, info in users.items():
            role = info.get("role", "unknown")
            perms = self.perm_mgr.get_user_permissions(uid)
            perm_str = ", ".join(sorted(perms)) if "*" not in perms else "All (admin)"
            aliases = self.id_resolver.get_aliases(uid)
            alias_str = " | ".join(aliases) if aliases else "No linked platforms"

            role_dropdown = ft.Dropdown(
                value=role, width=140, dense=True,
                border_color=AppColors.BORDER,
                text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
                options=[ft.dropdown.Option(r) for r in DEFAULT_ROLES],
                on_change=lambda e, u=uid: self._change_role(u, e.control.value),
            )

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icons.PERSON, color=AppColors.ACCENT, size=20),
                        ft.Text(uid, weight=ft.FontWeight.BOLD, color=AppColors.TEXT_PRIMARY, size=14),
                        role_dropdown,
                        ft.IconButton(icons.DELETE, icon_color="red", icon_size=18,
                                      tooltip="Remove user",
                                      on_click=lambda e, u=uid: self._remove_user(u)),
                    ], alignment=ft.MainAxisAlignment.START, spacing=Spacing.SM),
                    ft.Text(f"Platforms: {alias_str}", size=12, color=AppColors.TEXT_SECONDARY),
                    ft.Text(f"Permissions: {perm_str}", size=11, color=AppColors.TEXT_SECONDARY),
                ], spacing=4),
                padding=Spacing.SM,
                border=ft.border.all(1, AppColors.BORDER),
                border_radius=ft.border_radius.all(8),
                bgcolor=AppColors.SURFACE,
            )
            self._users_list.controls.append(card)

    def _add_user(self, e):
        uid = (self._new_user_id.value or "").strip()
        role = self._new_user_role.value or "user"
        if not uid:
            return
        self.perm_mgr.set_user_role(uid, role, assigned_by="admin_panel")
        self._new_user_id.value = ""
        self.refresh()

    def _change_role(self, user_id: str, new_role: str):
        self.perm_mgr.set_user_role(user_id, new_role, assigned_by="admin_panel")
        self.refresh()

    def _remove_user(self, user_id: str):
        self.perm_mgr.remove_user(user_id)
        self.refresh()

    # -----------------------------------------------------------------
    # Permission Requests tab
    # -----------------------------------------------------------------

    def _build_requests_tab(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text("Review and approve/deny permission requests from users",
                         size=13, color=AppColors.TEXT_SECONDARY),
                ft.Divider(color=AppColors.BORDER),
                self._requests_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_requests(self):
        self._requests_list.controls.clear()
        pending = self.req_mgr.get_pending()
        if not pending:
            self._requests_list.controls.append(
                ft.Text("No pending requests.", color=AppColors.TEXT_SECONDARY, italic=True))
        for req in pending:
            reason_text = f" — \"{req['reason']}\"" if req.get("reason") else ""
            card = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(f"{req['user_id']} requests {req['permission']}",
                                weight=ft.FontWeight.BOLD, color=AppColors.TEXT_PRIMARY, size=14),
                        ft.Text(f"{req['timestamp']}{reason_text}",
                                size=12, color=AppColors.TEXT_SECONDARY),
                    ], spacing=2, expand=True),
                    ft.IconButton(icons.CHECK_CIRCLE, icon_color="green", icon_size=24,
                                  tooltip="Approve",
                                  on_click=lambda e, r=req: self._approve_request(r)),
                    ft.IconButton(icons.CANCEL, icon_color="red", icon_size=24,
                                  tooltip="Deny",
                                  on_click=lambda e, r=req: self._deny_request(r)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=Spacing.SM,
                border=ft.border.all(1, AppColors.BORDER),
                border_radius=ft.border_radius.all(8),
                bgcolor=AppColors.SURFACE,
            )
            self._requests_list.controls.append(card)

    def _approve_request(self, req):
        self.req_mgr.approve(req["id"], "admin")
        # Also grant the permission
        self.perm_mgr.grant_permission(req["user_id"], req["permission"])
        self.refresh()

    def _deny_request(self, req):
        self.req_mgr.deny(req["id"], "admin")
        self.refresh()

    # -----------------------------------------------------------------
    # Identity Linking tab
    # -----------------------------------------------------------------

    def _build_identity_tab(self) -> ft.Container:
        self._canonical_id_field = ft.TextField(
            label="Canonical User ID (e.g. admin)", width=200, dense=True,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        self._platform_id_field = ft.TextField(
            label="Platform ID (e.g. telegram:12345)", width=260, dense=True,
            border_color=AppColors.BORDER, text_style=ft.TextStyle(color=AppColors.TEXT_PRIMARY),
            label_style=ft.TextStyle(color=AppColors.TEXT_SECONDARY),
        )
        link_btn = StyledButton("Link", icon=icons.LINK, on_click=self._link_identity)

        return ft.Container(
            content=ft.Column([
                ft.Text("Link platform accounts to canonical user IDs so "
                         "permissions follow the person across channels.",
                         size=13, color=AppColors.TEXT_SECONDARY),
                ft.Row([self._canonical_id_field, self._platform_id_field, link_btn],
                       spacing=Spacing.SM),
                ft.Divider(color=AppColors.BORDER),
                self._identity_list,
            ], spacing=Spacing.SM, scroll=ft.ScrollMode.AUTO),
            expand=True, padding=Spacing.MD,
        )

    def _refresh_identity(self):
        self._identity_list.controls.clear()
        users = self.id_resolver.get_all_users()
        if not users:
            self._identity_list.controls.append(
                ft.Text("No identity links configured.", color=AppColors.TEXT_SECONDARY, italic=True))
        for canonical, aliases in users.items():
            alias_chips = [
                ft.Chip(
                    label=ft.Text(a, size=12),
                    delete_icon=icons.CLOSE,
                    on_delete=lambda e, alias=a: self._unlink_identity(alias),
                    bgcolor=AppColors.SECONDARY_LIGHT,
                )
                for a in aliases
            ]
            card = ft.Container(
                content=ft.Column([
                    ft.Text(canonical, weight=ft.FontWeight.BOLD,
                            color=AppColors.TEXT_PRIMARY, size=14),
                    ft.Row(alias_chips, wrap=True, spacing=4),
                ], spacing=4),
                padding=Spacing.SM,
                border=ft.border.all(1, AppColors.BORDER),
                border_radius=ft.border_radius.all(8),
                bgcolor=AppColors.SURFACE,
            )
            self._identity_list.controls.append(card)

    def _link_identity(self, e):
        canonical = (self._canonical_id_field.value or "").strip()
        platform = (self._platform_id_field.value or "").strip()
        if not canonical or not platform:
            return
        self.id_resolver.link(canonical, platform)
        self._canonical_id_field.value = ""
        self._platform_id_field.value = ""
        self.refresh()

    def _unlink_identity(self, platform_id: str):
        self.id_resolver.unlink(platform_id)
        self.refresh()

    # -----------------------------------------------------------------
    # Refresh all tabs
    # -----------------------------------------------------------------

    def refresh(self):
        """Refresh all admin panel data."""
        self._refresh_users()
        self._refresh_requests()
        self._refresh_identity()
        self.page.update()
```

- [ ] **Step 2: Commit**

```bash
git add src/skillforge/flet/views/admin.py
git commit -m "feat: add admin dashboard view (users, requests, identity)"
```

---

## Chunk 5: Wire Into App + Router Integration

### Task 5: Wire Login Gate and Admin Tab Into App

**Files:**
- Modify: `src/skillforge/flet/app.py`
- Modify: `src/skillforge/core/router.py`

- [ ] **Step 1: Update app.py — login gate + 5th admin tab**

Modify `src/skillforge/flet/app.py`:

1. Add imports at top:
```python
from skillforge.flet.views.login import LoginView
from skillforge.flet.views.admin import AdminView
from skillforge.core.identity_resolver import IdentityResolver
from skillforge.core.permission_requests import PermissionRequestManager
```

2. Change `main()` function to show login first, then app on success:
```python
def main(page: ft.Page):
    AppColors.set_secure_storage(secure_storage)
    AppColors.load_saved_mode()

    page.title = "SkillForge"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = AppColors.BACKGROUND

    def on_authenticated(username):
        page.controls.clear()
        app = SkillForgeApp(page, admin_username=username)

        def on_window_event(e):
            if e.data == "close":
                app.cleanup()
                page.window_destroy()

        page.window_prevent_close = True
        page.on_window_event = on_window_event

        # Auto-start bots (existing code unchanged)
        _auto_start_bots(app)

    login_view = LoginView(page, secure_storage, on_authenticated)
    page.add(login_view.build())
```

Extract the auto-start code into `_auto_start_bots(app)` helper.

3. In `SkillForgeApp.__init__`, accept `admin_username` param, init identity resolver and request manager, add 5th nav tab:
```python
def __init__(self, page, admin_username="admin"):
    ...
    self.admin_username = admin_username
    self.identity_resolver = IdentityResolver()
    self.request_manager = PermissionRequestManager()
    ...
```

4. In `_init_views`, create AdminView:
```python
self.admin_view = AdminView(
    page=self.page,
    permission_manager=self.router._permission_manager if self.router else PermissionManager(),
    request_manager=self.request_manager,
    identity_resolver=self.identity_resolver,
)
self._admin_content = self.admin_view.build()
self.admin_view.refresh()
```

5. In `_init_nav`, add 5th destination:
```python
ft.NavigationRailDestination(
    icon=icons.ADMIN_PANEL_SETTINGS_OUTLINED,
    selected_icon=icons.ADMIN_PANEL_SETTINGS,
    label="Admin"),
```

6. Update `_on_nav_change` to include admin view in views list.

- [ ] **Step 2: Update router.py — better denial messages + request commands**

In `src/skillforge/core/router.py`:

1. Add identity resolver and request manager:
```python
from skillforge.core.identity_resolver import IdentityResolver
from skillforge.core.permission_requests import PermissionRequestManager
```

In `__init__`:
```python
self._identity_resolver = IdentityResolver()
self._request_manager = PermissionRequestManager()
```

2. In `handle_message` and `handle_message_stream`, resolve user_id through identity resolver early:
```python
user_id = self._identity_resolver.resolve(user_id)
```

3. Update all permission denial messages to include request hint:
```python
# Old:
clean_response += "\n\n**Permission denied:** You don't have skill creation access."

# New:
clean_response += "\n\n**Permission denied:** You don't have skill creation access. Use `/request-permission skills_create` to request access from an admin."
```

4. Add new commands to the command handler:
```python
# /request-permission <perm> [reason]
if cmd.startswith("/request-permission"):
    parts = command.split(None, 2)
    perm = parts[1] if len(parts) > 1 else ""
    reason = parts[2] if len(parts) > 2 else ""
    if not perm:
        return "Usage: `/request-permission <permission>` — e.g. `/request-permission skills_create`"
    req_id = self._request_manager.submit(user_id, perm, reason)
    if req_id:
        return f"Permission request submitted (#{req_id}). An admin will review it."
    return "You already have a pending request for this permission."

# /my-requests
if cmd.startswith("/my-requests"):
    reqs = self._request_manager.get_user_requests(user_id)
    if not reqs:
        return "You have no permission requests."
    lines = [f"- **{r['permission']}**: {r['status']} ({r['timestamp'][:10]})" for r in reqs]
    return "Your permission requests:\n" + "\n".join(lines)

# /pending-requests (admin only)
if cmd.startswith("/pending-requests"):
    if not self._permission_manager.is_admin(user_id):
        return "Admin access required."
    pending = self._request_manager.get_pending()
    if not pending:
        return "No pending requests."
    lines = [f"- #{r['id']}: **{r['user_id']}** wants **{r['permission']}** ({r['timestamp'][:10]})" for r in pending]
    return "Pending requests:\n" + "\n".join(lines)

# /approve <request_id>
if cmd.startswith("/approve"):
    if not self._permission_manager.is_admin(user_id):
        return "Admin access required."
    parts = command.split()
    if len(parts) < 2:
        return "Usage: `/approve <request_id>`"
    req_id = parts[1]
    # Find the request to get user_id and permission
    for req in self._request_manager.get_pending():
        if req["id"] == req_id:
            self._request_manager.approve(req_id, user_id)
            self._permission_manager.grant_permission(req["user_id"], req["permission"])
            return f"Approved: {req['user_id']} now has {req['permission']} access."
    return f"Request #{req_id} not found or already processed."

# /deny <request_id> [reason]
if cmd.startswith("/deny") and not cmd.startswith("/deny-"):
    if not self._permission_manager.is_admin(user_id):
        return "Admin access required."
    parts = command.split(None, 2)
    if len(parts) < 2:
        return "Usage: `/deny <request_id> [reason]`"
    req_id = parts[1]
    reason = parts[2] if len(parts) > 2 else ""
    if self._request_manager.deny(req_id, user_id, reason):
        return f"Denied request #{req_id}."
    return f"Request #{req_id} not found or already processed."

# /link-identity <canonical_id> <platform_id> (admin only)
if cmd.startswith("/link-identity"):
    if not self._permission_manager.is_admin(user_id):
        return "Admin access required."
    parts = command.split()
    if len(parts) < 3:
        return "Usage: `/link-identity <canonical_user> <platform:id>` — e.g. `/link-identity admin telegram:12345`"
    canonical = parts[1]
    platform_id = parts[2]
    self._identity_resolver.link(canonical, platform_id)
    return f"Linked {platform_id} → {canonical}"
```

5. Add new commands to the built-in command list (in `is_skill_invocation`):
```python
# Add to the command list:
"request-permission", "my-requests", "pending-requests", "approve", "deny", "link-identity"
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: All tests pass (existing + new)

- [ ] **Step 4: Commit**

```bash
git add src/skillforge/flet/app.py src/skillforge/core/router.py
git commit -m "feat: wire login gate, admin tab, permission requests into app and router"
```

---

## Chunk 6: Final Tests and Docs

### Task 6: Run Full Suite + Update Docs

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Update CHANGELOG.md**

Add entry for 2026-03-25:
```markdown
### [2026-03-25] Admin Panel & Permission System
#### Added
- **Admin Login Gate** — Web UI requires login; first run creates admin account
- **Admin Dashboard** — New 5th tab: user management, permission requests, identity linking
- **Cross-Platform Identity** — Link Telegram/WhatsApp/Slack IDs to canonical users; permissions follow the person
- **Permission Requests** — Users can `/request-permission` when denied; admins approve/deny from UI or chat
- **New Commands** — `/request-permission`, `/my-requests`, `/pending-requests`, `/approve`, `/deny`, `/link-identity`
- **Better Denial Messages** — Permission denials now include request-access hint
- **New Icons** — `chat_icon.png` for chat avatar, `icon.png` for app icon
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md docs/
git commit -m "docs: add admin panel and permission system to changelog"
```
