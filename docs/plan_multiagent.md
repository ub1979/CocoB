# Plan: Per-User Permissions & Multi-Agent Routing

## Context
SkillForge currently treats all users equally — anyone who can message the bot gets full access to all tools (email, files, scheduling, MCP, etc.). This is unsafe for running the bot on a shared server (e.g., one WhatsApp SIM serving multiple users). We need a permission system where:
- Admin (you) gets full access on any channel
- Other users get limited capabilities based on their role
- The LLM's system prompt adapts per user (don't show tools they can't use)

## Design Decisions
- **No separate routers per user** — too complex. Instead, a permission check layer inside the existing router.
- **Default for unknown users**: chat only (no tools)
- **Config**: JSON file (`data/user_roles.json`) + chat commands (`/user-role`, `/grant`, `/revoke`)
- **Backward compatible**: If `user_roles.json` doesn't exist, all users get full access (existing behavior preserved)

---

## Step 1: Create `src/skillforge/core/user_permissions.py` (~250 lines)

New file with:

**Enums:**
- `Permission` — string enum: `chat`, `web_search`, `web_fetch`, `email`, `calendar`, `browse`, `files`, `schedule`, `todo`, `mcp_tools`, `mcp_manage`, `skills_create`, `background_tasks`, `admin`
- `UserRole` — string enum: `admin`, `power_user`, `user`, `restricted`

**Class: `PermissionManager`**
- `__init__(data_dir)` — loads/creates `data/user_roles.json`
- `has_permission(user_id, permission) -> bool` — main gate (single check point)
- `get_user_permissions(user_id) -> set[str]` — effective permissions (role + custom - denied)
- `get_user_role(user_id) -> str` — role name or default
- `is_admin(user_id) -> bool` — shortcut
- `set_user_role(user_id, role, assigned_by) -> bool` — admin only
- `grant_permission(user_id, permission) -> bool` — add custom permission
- `revoke_permission(user_id, permission) -> bool` — deny specific permission
- `remove_user(user_id) -> bool` — remove entry, falls back to default
- `get_all_users() -> dict` — list all configured users
- `get_permitted_capabilities(user_id) -> list[str]` — for system prompt filtering

**Data file: `data/user_roles.json`**
```json
{
  "roles": {
    "admin": {
      "description": "Full access to all capabilities",
      "permissions": ["*"]
    },
    "power_user": {
      "description": "Most tools except admin and MCP management",
      "permissions": [
        "chat", "web_search", "web_fetch", "email", "calendar",
        "browse", "files", "schedule", "todo", "mcp_tools",
        "skills_create", "background_tasks"
      ]
    },
    "user": {
      "description": "Chat and web search",
      "permissions": ["chat", "web_search", "web_fetch", "schedule", "todo"]
    },
    "restricted": {
      "description": "Chat only, no tools",
      "permissions": ["chat"]
    }
  },
  "users": {
    "447771743077": {
      "role": "admin",
      "custom_permissions": [],
      "denied_permissions": [],
      "assigned_by": "config",
      "assigned_at": "2026-03-01T00:00:00Z"
    }
  },
  "default_role": "restricted"
}
```

Each user entry: role + custom_permissions (grants beyond role) + denied_permissions (revocations within role).

---

## Step 2: Write `tests/test_user_permissions.py` (~400 lines, ~60 tests)

### Unit tests for PermissionManager:
- Default role for unknown users -> restricted (chat only)
- Admin `"*"` wildcard passes all permission checks
- Each role has correct permission set
- `set_user_role()` persists correctly
- `grant_permission()` adds custom permission beyond role
- `revoke_permission()` denies permission within role
- Grant + revoke interact correctly (revoke takes priority)
- `remove_user()` falls back to default role
- Persistence: save to JSON, reload, state matches
- `get_all_users()` returns complete user list
- `get_permitted_capabilities()` returns human-readable list
- `is_admin()` shortcut works correctly
- Invalid role name fails gracefully
- Invalid permission name fails gracefully
- First run creates file with defaults if missing
- Cross-channel identity: same user_id = same permissions regardless of channel
- Backward compat: no `user_roles.json` file -> all permissions allowed (open mode)

### Router integration tests:
- Restricted user system prompt omits tool hints (schedule, web, MCP)
- Admin user system prompt includes all hints
- Non-admin running `/user-role` gets "permission denied"
- `/my-permissions` shows correct role + capabilities
- Admin can `/grant` permissions to other users
- Non-admin cannot `/grant`
- Admin can `/revoke` permissions
- `/users` lists all configured users (admin only)
- Schedule code block stripped for restricted user
- Web search code block stripped for restricted user
- MCP tool call blocked without `mcp_tools` permission
- Direct skill execution (email/calendar) blocked without matching permission
- All gated commands return denial for unpermitted users
- `/help` includes permission commands section

**Estimated: ~60 new tests**

---

## Step 3: Wire into `src/skillforge/core/router.py` (~100 lines changed)

### 3a. Import + init
- Import `PermissionManager` at top (alongside AuthManager import)
- Init `self._permission_manager = PermissionManager()` in `__init__` after `_auth_manager` (line ~141)

### 3b. New helper: `_build_capability_hints(user_id) -> str`
Replaces inline capability hints in both `handle_message` and `handle_message_stream`:
- Only includes scheduling hint if `has_permission(user_id, "schedule")`
- Only includes web search hint if `has_permission(user_id, "web_search")`
- Only includes MCP tools prompt if `has_permission(user_id, "mcp_tools")`
- Only lists skills the user is permitted to use
- **Result**: Restricted users get no tool hints -> LLM won't try to emit tool code blocks

### 3c. Gate handler execution in `handle_message` + `handle_message_stream`
Before each code-block handler runs, check permission:
- `schedule` blocks -> needs `schedule` permission
- `create-skill` blocks -> needs `skills_create` permission
- `todo` blocks -> needs `todo` permission
- `web_search`/`web_fetch` blocks -> needs `web_search`/`web_fetch` permission
- MCP tool calls -> needs `mcp_tools` permission
- Direct skill execution (email/calendar/browse) -> needs matching permission

If denied: strip the code block from response, append "Permission denied" note.

### 3d. New helper: `_check_command_permission(command, user_id) -> Optional[str]`
Maps commands to required permissions:
- `/mcp install|uninstall|enable|disable` -> `mcp_manage`
- `/tasks` -> `background_tasks`
- `/clawhub install|uninstall` -> `mcp_manage`
- `/user-role`, `/grant`, `/revoke`, `/users` -> `admin`
- `/my-permissions` -> always allowed (any user can see own permissions)

### 3e. Add new slash commands to `handle_command`
- `/my-permissions` — show user's own role + capabilities (any user)
- `/user-role <user_id> [role]` — show or set a user's role (admin only)
- `/grant <user_id> <permission>` — grant specific permission (admin only)
- `/revoke <user_id> <permission>` — revoke specific permission (admin only)
- `/users` — list all configured users with roles (admin only)

### 3f. Update `is_skill_invocation` built-in commands list
Add: `"my-permissions"`, `"user-role"`, `"grant"`, `"revoke"`, `"users"`

### 3g. Update `/help` output
Add "User Permissions" section listing new commands.

---

## Step 4: Run tests + update docs

1. Run `python -m pytest tests/test_user_permissions.py -v` — all new tests pass
2. Run `python -m pytest tests/ -v` — all 912+ existing tests must pass (no regressions)
3. Update `CHANGELOG.md` — new feature entry with date
4. Update `docs/read_me_claude.md` — document permission system in project structure

---

## Files Summary

| File | Change |
|------|--------|
| `src/skillforge/core/user_permissions.py` | **NEW** — Permission enum, UserRole enum, PermissionManager class |
| `src/skillforge/core/router.py` | Wire PermissionManager, gate handlers, add 5 new commands |
| `tests/test_user_permissions.py` | **NEW** — ~60 tests (unit + router integration) |
| `data/user_roles.json` | **NEW** — auto-created on first run with default config |
| `CHANGELOG.md` | Document new feature |
| `docs/read_me_claude.md` | Update project structure section |

---

## How Permissions Work (User Flow)

### First Run (no user_roles.json)
- All users get full access (backward compatible, same as before)
- Admin creates `data/user_roles.json` manually or via `/user-role` command

### After Setup
```
Person A (admin, WhatsApp 447771743077):
  -> Full access: chat, email, calendar, browse, files, schedule, MCP, admin commands
  -> System prompt: includes ALL tool hints and skills

Person B (restricted, WhatsApp 449876543210):
  -> Chat only: can ask questions, get answers
  -> System prompt: personality + persona only, NO tool hints
  -> If LLM somehow emits a tool block: stripped + "permission denied"

Person C (user, Telegram 123456):
  -> Chat + web search + schedule + todo
  -> System prompt: includes web search and schedule hints only
```

### Admin Commands
```
/users                              -> list all configured users
/user-role 449876543210             -> show Person B's current role
/user-role 449876543210 user        -> promote Person B to "user" role
/grant 449876543210 email           -> give Person B email access specifically
/revoke 449876543210 schedule       -> take away schedule from Person B
/my-permissions                     -> show your own role + capabilities
```

---

## Verification
1. `python -m pytest tests/test_user_permissions.py -v` — all new tests pass
2. `python -m pytest tests/ -v` — full suite passes (no regressions)
3. Manual: start bot, verify unknown user can only chat, admin can `/grant` and `/revoke`
