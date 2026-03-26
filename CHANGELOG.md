# Changelog

All notable changes to **SkillForge** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed — 2026-03-25 (UI/UX Redesign)
- **Settings card-grid navigation** — 7 clickable category cards (130×130, icon + title + subtitle) replace the old monolithic settings list; click a card to reveal its options panel below
- **Design system overhaul** — unified single-accent indigo (`#6366F1`), neutral dark grays (`#111111`/`#1A1A1A`), clean light mode (`#F5F5F5`/`#FFFFFF`)
- **Permissions section redesign** — clickable permission chips per user (click to toggle grant/revoke), accent-tinted enabled chips with border, clean role reference cards; removed separate Grant/Revoke section
- **CollapsibleSection** redesign — left accent bar, box shadow, animated expand/collapse
- **SubItemAccordion** widget — DRY replacement for 3× duplicated inline `create_sub_item` closures in messaging bots, LLM providers, and proactive tasks
- **SectionHeader** widget — styled sub-group label with optional icon and subtitle
- **ServerStatusCard / CliStatusCard** — left accent bars (green when active, muted when not)
- **Admin view header** — matches new settings accent style
- **Chat focus fix** — `message_input.focus()` after `page.update()` prevents focus loss when typing `/` commands in web UI
- **Flet 0.80+ migration** — all deprecated `ft.padding/border/border_radius/ElevatedButton` calls replaced across 12 files

### Added — 2026-03-25 (Admin Panel, Login Gate, Cross-Platform Identity)
- **Login gate** (`flet/views/login.py`) — password-protected access to the Flet web UI
  - First run: admin account setup form; subsequent runs: login form
  - Credentials stored securely via PBKDF2 hashing in `SecureStorage`
  - 6 tests in `tests/test_admin_login.py`
- **Admin dashboard** (`flet/views/admin.py`) — 5th nav tab with three sub-tabs:
  - **Users & Roles**: add/remove users, change roles via dropdown
  - **Permission Requests**: approve/deny pending permission requests from users
  - **Identity Linking**: link platform-specific IDs (telegram:12345, whatsapp:+92...) to canonical user IDs
- **Cross-platform identity resolution** (`core/identity_resolver.py`)
  - Maps platform-specific IDs to canonical user IDs via `data/identity_map.json`
  - Router resolves identity at top of `handle_message` / `handle_message_stream`
  - 8 tests in `tests/test_identity_resolver.py`
- **Permission request queue** (`core/permission_requests.py`)
  - Users can `/request-permission <perm>` instead of hitting a dead-end denial
  - Admin approves/denies from dashboard or via `/approve` / `/deny` commands
  - 9 tests in `tests/test_permission_requests.py`
- **New router commands**: `/request-permission`, `/my-requests`, `/pending-requests`, `/approve`, `/deny`, `/link-identity`
- **Chat avatar**: uses `chat_icon.png` (robot head) for assistant messages
- **App icon**: `icon/icon.png` (robot with anvil) for application window

### Added — 2026-03-19 (Image/Vision Support — Epics E-001 through E-006)
- **Full image/vision pipeline** — send images to vision-capable LLMs, receive and render generated images, across all channels
- **E-001: Core Image Infrastructure** (`core/image_handler.py`)
  - `ImageHandler` — validates file type/size, stores images to `data/images/{session_key}/`, base64 encoding, metadata tracking, automatic cleanup of old images
  - `Attachment` dataclass — unified image reference (file_path, mime_type, base64 data, original filename)
  - Supported formats: JPEG, PNG, GIF, WebP, BMP, TIFF; configurable max size (default 20 MB)
  - 97 tests in `tests/test_image_handler.py`
- **E-002: LLM Provider Vision Support** (`core/llm/`)
  - `supports_vision` property and `format_vision_messages()` method added to `LLMProvider` base class
  - OpenAI-compatible providers: multi-part content arrays with `image_url` (base64 data URI)
  - Anthropic provider: `image` content blocks with `source.type = "base64"`
  - Gemini provider: `inline_data` parts with mime_type and base64 data
  - CLI providers (Claude CLI, Gemini CLI): vision support flags, attachment passing
  - Llama.cpp provider: vision support detection based on model name
  - 36 tests in `tests/test_vision_providers.py`
- **E-003: Router Integration** (`core/router.py`, `core/sessions.py`)
  - `handle_message()` and `handle_message_stream()` accept optional `attachments` parameter (list of `Attachment` objects); default `None` preserves full backward compatibility
  - Images stored via `ImageHandler`, references saved in JSONL metadata
  - Vision-capable LLMs receive multi-modal message payloads via `format_vision_messages()`
  - Non-vision LLMs get contextual fallback note suggesting a vision-capable model
  - Permission-gated on `files` permission; session history includes attachment references
  - 20 tests in `tests/test_router_image_integration.py`
- **E-004: Channel Inbound** (`channels/telegram.py`, `channels/whatsapp.py`, `flet/views/chat.py`)
  - Telegram: photo/document handler downloads images via Bot API `get_file()`, creates `Attachment`, passes to router
  - WhatsApp: image message handler downloads via Baileys `/download-media` endpoint, creates `Attachment`
  - Flet UI: file picker button in chat input, image preview before send, drag-and-drop support
  - 22 tests in `tests/test_channel_images.py`
- **E-005: Channel Outbound** (`core/router.py`, `channels/`, `flet/`)
  - Router `extract_outbound_images()` — extracts image file paths from bot responses; detects `[Generated Image: ...]`, `Saved to:` markers, `![alt](path)` markdown images
  - Telegram `send_image()` — sends images as native Telegram photos via `send_photo()` API
  - WhatsApp `send_image()` — sends images via Baileys `/send-media` endpoint (base64 or URL)
  - Baileys `/send-media` endpoint — new route in `whatsapp_service/server.js`
  - Flet `ChatMessage` — inline image rendering with `ft.Image` for attached images
  - 36 tests in `tests/test_channel_outbound.py`
- **E-006: Image Generation Handler** (`core/image_gen_handler.py`)
  - Code-block handler for `` ```image_gen``` `` blocks; parses PROMPT, STYLE, SIZE, PROVIDER, NEGATIVE_PROMPT, COUNT fields
  - MCP tool delegation — discovers image generation tools across connected MCP servers
  - Graceful fallback with setup instructions when no MCP image gen tool is available
  - Router wired in both `handle_message` and `handle_message_stream`, permission-gated on `files`
  - 67 tests in `tests/test_image_gen_handler.py`
- **Total: 278 new tests** across 5 test files (97 + 36 + 20 + 22 + 36 + 67)

### Fixed — 2026-03-02 (Chat UI Refresh + Web Search)
- **Chat response now renders immediately** — converted `_send_message` and `_process_bot_response` from `ThreadPoolExecutor` + manual `asyncio.new_event_loop()` to native `async def` on Flet's event loop; `page.update()` now runs on the correct thread so the window repaints instantly instead of only when switching apps back (macOS desktop Flet thread-safety issue)
- **User message appears instantly on Enter** — `_send_message` is sync (shows message + calls `page.update()`), then fires `_process_bot_response` as background task via `page.run_task()`
- MCP blocking operations (browse, search, email, calendar) use `asyncio.to_thread()` to avoid blocking the UI
- **LLM now uses native web search instead of outputting `/google-search` as text**:
  - **Pre-search**: router detects search-worthy queries (weather, news, prices, etc.) and fetches results *before* the LLM responds — LLM just summarizes
  - **Slash-command intercept**: if LLM still outputs `/google-search` or `/browse query:`, router converts it to a `web_search` block automatically
  - Removed `/google-search` from PERSONALITY.md commands list
  - Set google-search skill to `user_invocable: false` (native `web_search` handler is better)
  - Router filters `/google-search` from skills list in system prompt when web_tools is available
- **ClawHub registry fixed** — updated API URL from dead `api.openclaw.ai` to live `clawhub.ai/api`, fixed search/info/download endpoints, normalized field names (`displayName`→`name`, `summary`→`description`)

### Added — 2026-03-01 (User Permissions UI)
- **User Permissions section in Settings UI** — manage roles and permissions visually
  - View configured users with role, custom grants, and denied permissions
  - Set user roles (admin/power_user/user/restricted) from the UI
  - Grant or revoke individual permissions per user
  - Remove users from the permission system
  - Shows inactive state when no `user_roles.json` exists yet

### Added — 2026-03-01 (Per-User Permissions & Multi-Agent Routing)
- **Per-user permission system** — role-based access control for all bot capabilities
  - `PermissionManager` (`core/user_permissions.py`) — loads `data/user_roles.json`, checks permissions, manages roles
  - 4 built-in roles: `admin` (full access), `power_user` (all tools except admin/MCP manage), `user` (chat + web + schedule + todo), `restricted` (chat only)
  - 14 gatable permissions: chat, web_search, web_fetch, email, calendar, browse, files, schedule, todo, mcp_tools, mcp_manage, skills_create, background_tasks, admin
  - Fine-grained overrides: `/grant` and `/revoke` add/remove individual permissions per user
  - **Backward compatible** — if `data/user_roles.json` doesn't exist, all users get full access (existing behavior preserved)
- **System prompt filtered per user** — LLM only sees capability hints for tools the user can access (restricted users get no tool hints)
- **Handler execution gated** — schedule, todo, web_search, skill creation blocks stripped with "Permission denied" if user lacks access
- **Chat commands**: `/my-permissions`, `/user-role <id> [role]`, `/grant <id> <perm>`, `/revoke <id> <perm>`, `/users`
- 64 new tests in `tests/test_user_permissions.py` — enums, role defaults, grant/revoke, persistence, edge cases, router commands

### Fixed — 2026-02-28 (Thinking Model Code Block Extraction)
- **Thinking model code blocks extracted** — when Gemini Flash (or similar thinking models) put code blocks inside `reasoning` field instead of `content`, openai_compat now extracts `\`\`\`schedule\`\`\``, `\`\`\`todo\`\`\``, etc. so handlers can parse them (fixes `/todo list` and skill invocations returning raw reasoning monologue)
- **Streaming path buffered** — streaming now buffers reasoning chunks and extracts code blocks at the end when no content was streamed
- **Schedule action normalization** — action field takes first word only (LLMs sometimes add extra text like "delete id: task-xxx")
- **Delete by name** — schedule delete/stop/cancel/remove now supports NAME-based lookup (case-insensitive partial match) when TASK_ID not provided
- **List reminders** — `ACTION: list` added to schedule system prompt so LLM knows how to list reminders
- **WhatsApp scheduler handler** — registered channel handler for WhatsApp so scheduled reminders deliver via Baileys HTTP
- 6 new tests for thinking model code block extraction

### Fixed — 2026-02-27 (Multiple Fixes)
- **TabBar crash fixed** — ToolsView rewritten to use Flet 0.80+ `Tabs`/`TabBar`/`TabBarView` API (was using standalone `TabBar` which requires a `Tabs` parent)
- **Web search now works** — system prompt tells LLM to emit ```web_search``` blocks instead of `/google-search` text; DuckDuckGo fallback added (no API key needed)
- **Thinking model support** — `openai_compat.py` now reads `reasoning` field when `content` is empty (fixes Gemini Flash returning blank responses via Ollama)
- **Telegram duplicate instance guard** — `_start_telegram_bot()` skips if already running; `start_polling()` catches `Conflict` error and raises clear message; `delete_webhook()` called before polling to clear stale sessions
- **Expired one-shot scheduler tasks** — `_schedule_task()` skips past-due `kind: at` tasks instead of firing them late with "missed by N days" warnings
- **Scheduler coroutine warning fixed** — scheduler event loop shared with settings view via `_scheduler_loop`
- **Slack duplicate instance guard** — same protection as Telegram
- Config updated: `gemini-3-flash-preview` model, 120s timeout

### Fixed — 2026-02-26 (Scheduler/Reminders Not Working)
- **LLM now knows about scheduling** — system prompt includes scheduling capability hint when `SchedulerManager` is active, so natural language like "remind me at 5pm" triggers `\`\`\`schedule\`\`\`` blocks instead of "I can't do that"
- **Flet channel handler registered** — `SkillForgeApp` now registers a "flet" channel handler with `SchedulerManager` so scheduled tasks/reminders are delivered to the chat UI via `inject_scheduled_message()`
- **`inject_scheduled_message()` on ChatView** — new public method that pushes scheduler-triggered reminders into the message list with a clock emoji prefix
- **`_scheduler_manager` stored on router** — `set_scheduler_manager()` now stores the reference on the router instance for system prompt conditioning
- **Current UTC time injected into prompt** — system prompt now includes `Current UTC time: ...` so the LLM calculates correct RUN_AT datetimes (fixes wrong year/wrong time in schedule blocks)
- 7 new tests: inject_scheduled_message (2), flet channel handler (3), system prompt scheduling hint (2)

### Performance — 2026-02-26 (Claude CLI Speed Optimization)
- **Streaming UI** — Flet chat now uses `handle_message_stream()` instead of blocking `handle_message()`, tokens appear progressively as they arrive (100ms throttled updates)
- **Smart `--resume` prompts** — `_format_messages()` only sends the latest user message when a session exists (Claude CLI already has history server-side), eliminating redundant system prompt + conversation re-packing
- **Session persistence** — `_session_id` saved to `data/claude_session.json` so sessions survive app restarts (no cold start penalty)
- 12 new tests in `tests/test_claude_cli.py` (format_messages, session persistence, build command) + 1 streaming test in `test_flet_app.py`

### Changed — 2026-02-25 (Flet UI Refactor)
- **Modular `skillforge.flet` package** — refactored 5,882-line `app.py` monolith into 16 focused modules
  - `flet/theme.py` — `AppColors`, `Spacing`, provider category dicts, utility functions
  - `flet/storage.py` — `SecureStorage` for encrypted token/settings persistence
  - `flet/components/` — `ChatMessage` (with Markdown rendering), `CollapsibleSection`, `StatusBadge`, `StyledButton`, `ServerStatusCard`, `CliStatusCard`
  - `flet/views/chat.py` — `ChatView` with animated typing indicator (`ProgressRing`)
  - `flet/views/settings.py` — `SettingsView` (appearance, personas, messaging bots, scheduler, LLM providers, memory)
  - `flet/views/tools.py` — `ToolsView` tabbed container (MCP + Skills + ClawHub)
  - `flet/views/mcp.py`, `skills.py`, `clawhub.py`, `history.py` — extracted panels
  - `flet/app.py` — thin orchestrator with 4-tab navigation
- **Navigation consolidated**: 6 tabs (Chat, Settings, MCP, Skills, ClawHub, History) → 4 tabs (Chat, Tools, Settings, History)
- **Markdown rendering** in assistant chat messages (`ft.Markdown` with GitHub Web extension set, atom-one-dark code theme)
- **Animated typing indicator** replaces static "Thinking..." text with `ProgressRing` + "SkillForge is thinking..."
- Old `app.py` replaced with thin backward-compatible wrapper
- 15 new import tests in `TestFletImports`
- 29 smoke tests in `tests/test_flet_app.py` — builds every view, component, and full `SkillForgeApp` with mock page
- Total test count: 862 → 891

### Added — 2026-02-24 (Web Tools)
- **Native `web_search` / `web_fetch` tools** — agent-callable web capabilities without MCP configuration
  - `web_search`: Brave Search API integration (query + count), graceful fallback without API key
  - `web_fetch`: URL content extraction with HTML text extraction, supports HTML/plain text/JSON
  - LLM emits ```web_search``` or ```web_fetch``` code blocks, handler executes and injects results
  - Wired into both `handle_message` and `handle_message_stream` paths
- 29 tests in `tests/test_web_tools.py`
- Total test count: 791 → 848

### Added — 2026-02-24 (CLI & Docker)
- **`skillforge` console script** — single CLI entry point registered via pyproject.toml `[project.scripts]`
  - Subcommands: `ui`, `gradio`, `bot`, `telegram`, `slack`, `discord`, `doctor`
  - `skillforge doctor` — checks config, data dirs, core imports, optional deps, LLM config, bundled skills
- **Docker deployment** — `Dockerfile` (multi-stage build), `docker-compose.yml` (all channels as profiles), `.dockerignore`
- 8 tests in `tests/test_cli.py`

### Added — 2026-02-24 (Think Level Control)
- **`/think` command** — per-session reasoning level control with 6 levels: `off` (0.0), `minimal` (0.2), `low` (0.4), `medium` (0.7, default), `high` (0.9), `xhigh` (1.2)
- Applied to both `handle_message` and `handle_message_stream` paths via temperature override
- 20 tests in `tests/test_think_levels.py`

### Added — 2026-02-24 (Scheduler Upgrade)
- **Interval triggers** (`kind: "every"`) — repeat every N seconds/minutes/hours using APScheduler IntervalTrigger
- **One-shot triggers** (`kind: "at"`) — run once at a specific datetime using DateTrigger, auto-delete after success
- **Retry backoff** — exponential retry on failure: 30s → 1m → 5m → 15m → 60m (max 5 retries, disabled for one-shot)
- **Human-readable schedule display** — cron/interval/one-shot converted to plain English (e.g., "Daily at 9:00 AM", "Every 30 minutes")
- **Concurrency control** — per-task `max_concurrent` limit (default 1) prevents overlapping executions
- **Natural language scheduling** — updated SKILL.md with interval and one-shot examples, interval presets table
- 49 new tests in `tests/test_scheduler.py` + 16 new tests in `test_schedule_handler.py`
- Total test count: 726 → 791

### Fixed — 2026-02-24
- Replaced all `datetime.utcnow()` calls in scheduler with `datetime.now(tz=timezone.utc)` (4 occurrences)

### Added — 2026-02-24 (ClawHub Integration)
- **ClawHub integration** — search, install, and manage 5,700+ community skills from OpenClaw.ai's ClawHub registry
  - `ClawHubManager` (`core/clawhub.py`) — registry API client with 5-min search caching, install/uninstall, version tracking
  - OpenClaw format adapter (`parse_openclaw_skill_content`) — converts OpenClaw.ai SKILL.md format (nested emoji, `{baseDir}`, version/author) to SkillForge `Skill` objects
  - Extended `Skill` dataclass with `version`, `author`, `clawhub_slug` fields (backward compatible)
  - Chat commands: `/clawhub search|install|list|info|uninstall|updates`
  - UI tab: "ClawHub" nav destination with search bar, result cards, install/uninstall buttons, update checker
  - Name conflict detection: auto-prefixes with `ch-` when slug matches a bundled skill
  - Installed skills tracked in `data/clawhub_installed.json`
  - 70 new tests (`tests/test_clawhub.py`) — format adapter, search, install/uninstall, caching, requirements, router integration
  - Total test count: 656 → 726

### Added — 2026-02-24
- **`skillforge.sh` launch script** — one-command launcher that activates conda env and runs the Flet UI
- **README.md updated** — project structure now reflects `src/skillforge/` layout, quick start uses conda + `skillforge.sh`
- **CONTRIBUTING.md updated** — renamed all "mr_bot" references to "SkillForge"

### Fixed — 2026-02-22 (WhatsApp MCP + Persona Wiring + Scheduling)
- **MCP auto-connect on startup** — `router.set_mcp_manager()` is now called at app init, and enabled MCP servers auto-connect in a background thread (tools now work on WhatsApp and all channels)
- **WhatsApp user_id uses phone number** — `_handle_whatsapp_message` now passes the real phone number (from `senderPn`/`participantPn`) to the router instead of the LID, so persona resolution matches `user_profiles.json` entries
- **Per-contact persona UI** — new "Contact Personas" section (section 5) in WhatsApp settings allows assigning, changing, and removing personas for specific phone numbers
- **WhatsApp scheduling fixed** — WhatsApp messages now run on the scheduler's event loop (`_scheduler_loop`) so `/schedule` commands can add jobs to the same `AsyncIOScheduler`; registered WhatsApp channel handler so scheduled messages are delivered via the Baileys service
- **Scheduler `next_run_time` error fixed** — guarded `job.next_run_time` access with `getattr()` to prevent `AttributeError` when jobs are added before the scheduler starts

### Added — 2026-02-22 (Multi-Persona System)
- **Per-user / per-channel persona system** — assign different personality profiles to users and channels
  - `Persona` dataclass + YAML frontmatter parsing (same format as SKILL.md files)
  - 4 built-in personas: default (🤖), formal (👔), casual (😊), technical (💻)
  - Priority resolution: user override > channel default > base personality
  - Full CRUD: create, update, delete personas via code or chat commands
  - User/channel mappings persisted in `data/personality/user_profiles.json`
- **Chat commands**: `/persona`, `/list-personas`, `/set-persona <name>`, `/create-persona <name> [desc]`
- **Settings UI**: "🎭 Personas & Agents" section with persona list, channel default dropdowns, create form
- **Per-key prompt caching** in router — cached by `user_id:channel`, auto-invalidated on persona/file changes
- **55 new tests** (`tests/test_personas.py`) — persona loading, user profiles, resolution priority, system prompt layering, CRUD, router integration
- Total test count: 601 → 656

### Added — 2026-02-21 (Integration Tests)
- **End-to-end integration test suite** (`tests/test_integration_chat.py`) — 196 tests
  - Simulates real human chat flows: user → router → LLM (mocked) → response parsing → handler execution → session persistence
  - Parametrized across 3 LLM backend types: Ollama, Claude CLI, Gemini CLI
  - Covers: normal conversation, all 15 skills, built-in commands, streaming, context compaction, memory extraction, auth/heartbeat/pattern/task/MCP commands
  - **Skill creation via chat**: password-gated flow (set password → LLM returns ```create-skill``` → /unlock → file written)
  - **MCP server management**: install verified/unverified servers, enable/disable, uninstall, security warnings
  - **Direct skill execution**: /email, /calendar bypass LLM and call MCP directly
  - **Scheduler integration**: ```schedule``` blocks parsed → tasks created/listed/deleted via mock scheduler
  - **Heartbeat/daily summary**: enable/disable all 4 heartbeat types, verify status tracking
  - Every test uses `tmp_path` — zero shared state, isolated sessions & memory DB
  - Total test count: 405 → 601

### Fixed — 2026-02-21
- **Scheduler "Event loop is closed" error** — APScheduler jobs (reminders, scheduled tasks) now fire correctly
  - Scheduler's event loop kept alive via `loop.run_forever()` in a dedicated daemon thread
  - `_run_async_scheduler()` reuses the persistent loop via `run_coroutine_threadsafe` instead of creating throwaway loops
  - Clean shutdown stops the scheduler on its own loop before halting it

### Added — 2026-02-21
- **Router integration of 5 agentic modules** — All new modules now wired into `MessageRouter`
  - AuthManager: `/pin`, `/login`, `/logout`, `/auth status` commands
  - HeartbeatManager: `/summary`, `/heartbeat enable|disable|status <type>` commands
  - PatternDetector: `/patterns`, `/patterns dismiss <id>`, `/patterns stats` commands; auto-records interactions
  - BackgroundTaskRunner: `/tasks list|status|delete|pause|resume <id>` commands
  - MCPServerManager: `/mcp list|verified|install|confirm|cancel|enable|disable|uninstall` commands
  - `start_services()` method for launching heartbeat/task scheduler loops on startup
  - Updated `/help` with all new commands grouped by category
- **Password-protected file access** — Bot skill creation now requires password authorization
  - `FileAccessManager` (`core/file_access.py`) — PBKDF2-HMAC-SHA256 password hashing with 600k iterations
  - Sandbox enforcement: bot can only write to `skills/` and `data/user/` directories
  - Per-action authorization: each file write requires `/unlock <password>` confirmation
  - Auth file stored at `data/.file_access_auth` with 0600 permissions
  - `/setpassword <pass>` — First-time password setup (min 8 chars)
  - `/unlock <pass>` — Authorize a pending skill creation/update/delete action
  - Defense-in-depth path checks added to `SkillsManager.save_skill()` and `delete_skill()`
  - Comprehensive test coverage in `test_file_access.py` (22 tests)
- **Tiered authentication system** — Four-level security for different action types
  - `AuthManager` (`core/auth_manager.py`) — GREEN/YELLOW/ORANGE/RED security levels
  - GREEN: read-only, no auth; YELLOW: 4-digit PIN, 30-min session; ORANGE: password, 1-hour session; RED: password + confirm, per-action
  - Session management with auto-extend, disk persistence, `/logout` command
  - Comprehensive test coverage in `test_auth_manager.py` (42 tests)
- **Heartbeat system** — Proactive user check-ins without requiring authentication
  - `HeartbeatManager` (`core/heartbeat_manager.py`) — morning brief, deadline watch, unusual activity, daily summary
  - All heartbeats are GREEN level (read-only)
  - Per-user configuration with configurable schedule times
  - Comprehensive test coverage in `test_heartbeat_manager.py` (27 tests)
- **Pattern detection** — Detects repeated user commands and suggests skill creation
  - `PatternDetector` (`core/pattern_detector.py`) — repeated command, workflow, time-based, and context patterns
  - ORANGE level auth required to view/create from suggestions
  - 30-day retention limit for interaction history
  - Comprehensive test coverage in `test_pattern_detector.py` (25 tests)
- **Background task runner** — Periodic background tasks with auth-gated management
  - `BackgroundTaskRunner` (`core/background_tasks.py`) — health checks, data sync, scheduled jobs
  - GREEN to view status, YELLOW (PIN) to create/modify/delete tasks
  - Max 5 concurrent tasks, last 50 results retained
  - Comprehensive test coverage in `test_background_tasks.py` (30 tests)
- **Webhook security** — HMAC-SHA256 signature verification for all channel webhooks
  - `core/webhook_security.py` — WhatsApp, Telegram, Slack, MS Teams verification
  - Constant-time comparison prevents timing attacks, timestamp validation prevents replay attacks
  - Comprehensive test coverage in `test_webhook_security.py` (35 tests)
- **MCP server manager** — Chat-based MCP server management
  - `MCPManager` (`core/mcp_manager.py`) — install, enable, disable, uninstall MCP servers via chat
  - Verified server registry with pre-approved configs (Playwright, Filesystem, GitHub, Gmail, etc.)
  - Pending install confirmation flow: verified auto-approve, unknown require explicit confirmation
  - Comprehensive test coverage in `test_mcp_manager.py` (21 tests)
- **Additional security tests** — MCP allowlist, session namespacing, SQLite hardening, timing attacks
  - `test_mcp_security.py` — MCP command allowlist validation
  - `test_session_key_namespace.py` — channel isolation (7 tests)
  - `test_sqlite_timeout.py` — connection timeout (4 tests)
  - `test_sqlite_wal_mode.py` — WAL mode (5 tests)
  - `test_file_access_timing.py` — timing attack protection (7 tests)

### Performance — 2026-02-20
- **Background memory storage** — LLM fact extraction and memory writes now run as async background tasks instead of blocking the response. Eliminates the second LLM call from the response path.
- **Cached system prompt** — Personality files (PERSONALITY.md, MOODS.md, NEW_PERSONALITY.md) are now cached and only re-read when file modification time changes, avoiding redundant disk I/O on every message.
- **Optimized history loading** — `get_conversation_history()` now reads only the tail of JSONL files when `max_messages` is set, instead of parsing the entire file.
- **Batched session index writes** — `sessions.json` is now written at most once per second instead of after every message, reducing I/O overhead.
- **Chat text wrapping fix** — Message bubbles in Flet UI now properly wrap long text instead of extending beyond the visible area.

### Changed — 2026-02-20
- **Restructured to `src/skillforge/` package layout** — proper Python package structure
  - All Python code moved to `src/skillforge/` (core/, channels/, ui/, entry points)
  - Added `pyproject.toml` with setuptools build config and optional dependencies
  - `pip install -e .` replaces all `sys.path` hacks
  - Single CLI entry: `python -m skillforge ui/gradio/bot/telegram/slack/discord`
  - `PROJECT_ROOT` constant in `skillforge/__init__.py` replaces `Path(__file__).parent.parent` chains
  - Setup/architecture docs moved to `docs/`, dev scripts to `scripts/`
  - `skills/`, `data/`, `config.py`, tests stay at project root

### Added — 2026-02-20
- **6 new skills**: `/github`, `/notes`, `/files`, `/news`, `/social`, `/todo`
  - `/github` — Manage GitHub issues, PRs, notifications (requires GitHub MCP)
  - `/notes` — Create, search, edit markdown notes in `~/notes/` (requires Filesystem MCP)
  - `/files` — Browse, search, read, move/copy local files (requires Filesystem MCP)
  - `/news` — RSS headlines from Hacker News, BBC, TechCrunch, Reuters (requires Playwright MCP)
  - `/social` — Post to Twitter/X and LinkedIn (requires Composio or Playwright MCP)
  - `/todo` — Full todo list with priorities, due dates, tags, and reminders
- **Todo handler** (`core/todo_handler.py`) — Code-block handler for `` ```todo``` `` blocks
  - Persistent JSON storage in `data/todos.json` (per-user, thread-safe)
  - Operations: add, list, done, delete, edit, remind
  - Reminders integrate with SchedulerManager
- **Automated test suite** (`tests/`) — 405 tests via pytest + pytest-asyncio
  - `test_imports.py` — All core module imports (20 tests)
  - `test_skills_loading.py` — All 15 SKILL.md files parse correctly (49 tests)
  - `test_todo_handler.py` — Full CRUD for todo handler (28 tests)
  - `test_schedule_handler.py` — Schedule handler parsing & formatting (11 tests)
  - `test_router.py` — Router init, skill detection, commands, integration (23 tests)
  - Plus 248 security/agentic tests (see 2026-02-21 entries above)

### Fixed — 2026-02-20
- **Flet UI crash on startup** — Fixed 63 instances of incorrect Flet helper API calls
  - `ft.Padding.only/all/symmetric` → `ft.padding.only/all/symmetric`
  - `ft.BorderRadius.all` → `ft.border_radius.all`
  - `ft.Border.all/only` → `ft.border.all/only`
- **Deprecation warning** — Replaced `datetime.utcnow()` with `datetime.now(tz=timezone.utc)` in todo handler

### Changed — 2026-02-20
- `core/router.py` — Wired TodoCommandHandler (import, init, scheduler, handle_message, handle_message_stream)
- `todo.md` — Marked 6 skills as done, tagged remaining 4 (Spotify, Home automation, Finance, Weather) for community
- `read_me_claude.md` — Updated project structure with new skills, todo handler, and test suite

### Added (earlier)
- **WhatsApp Integration with UI Controls** - Full WhatsApp bot support via Baileys
  - Start/Stop Baileys service from UI button
  - QR code display in settings for authentication
  - Access control: DM Policy, Group Policy, Allowlist
  - Bot prefix "🤖 *SkillForge:*" for responses to others
  - LID-to-phone caching for WhatsApp group messages
  - Webhook server for receiving and responding to messages
  - Support for both DMs and group chats
- **Unified Skill Executor** (`core/skill_executor.py`) - Channel-agnostic skill execution
  - Skills like `/email` and `/calendar` now work the same across all channels
  - Telegram, WhatsApp, Slack, Discord, and Flet UI all share the same skill logic
  - Router automatically detects and executes skills before passing to LLM
  - Follows OpenClaw.ai's architecture pattern for multi-channel support
- **Telegram Auto-Connect MCP** - Standalone Telegram bot auto-connects enabled MCP servers
  - No manual server connection needed for Telegram users
  - Shows connected servers in startup banner
- **Secure Token Storage with Password Protection**
  - Token auto-saved when you click "Start Bot"
  - Password protection for viewing saved token
  - Token hidden, revealed only for 10 seconds after password
  - Auto-start option: bot starts automatically on app launch
  - Encrypted storage in `~/.skillforge/secure_config.json`
- **Smart Search** - Auto-detect questions needing real-time web search
  - Sports scores, match results (cricket, football, etc.)
  - News, weather, stock prices
  - Current events ("today", "latest", "who won")
  - Automatically triggers Playwright web search
- **Provider Sync** - Desktop and Telegram share the same LLM
  - Switch provider on desktop → Telegram uses same provider
  - `/provider <name>` command to switch LLM from Telegram
  - `/status` command to check current provider and MCP servers
  - Settings saved to `~/.skillforge/secure_config.json`
- **Response Speed Optimizations** - Following OpenClaw.ai's token reduction strategies
  - System prompt reduced 90% (509 words → 50 words)
  - Conversation history limited to last 10 messages (was unlimited)
  - Memory retrieval: 1 result, 100 char limit, skipped for short queries (<30 chars)
  - Direct-execution skills (/email, /calendar) skip LLM entirely
- **Dark Mode** - Toggle between light and dark themes in Settings > Appearance
  - Navy blue dark theme with proper contrast
  - Instant UI rebuild when toggling
  - Theme state persists via `AppColors.set_dark_mode()`
- **Email & Calendar Skills** - Full integration with Gmail and Google Calendar
  - `/email` - Send, search, read, draft, label, archive emails
  - `/calendar` - View, create, update, delete events
  - Two setup options: Self-hosted (FREE) or Composio
- **Chat Avatar Icon** - Assistant messages now display SkillForge icon (`icon.png`)
- **CLI Provider Quick Switch** - Click "Use" button directly on CLI provider cards (no dropdown)
- **Telegram Bot Script** (`telegram_bot.py`) - Standalone script to run SkillForge as a Telegram bot
  - Full integration with MessageRouter, Skills, and MCP
  - Automatic bot info display on startup
  - Supports polling and webhook modes
- **Telegram Integration in GUI** - Start/stop Telegram bot from Settings
  - Enter bot token directly in the UI
  - See bot status (Running/Stopped)
  - Shows connected bot username
  - Runs in background thread
- **Expanded QA Test Suite** - 42 automated tests covering:
  - Module import and syntax validation
  - UI components (dark mode, CLI buttons, chat avatars, icons)
  - Session management (creation, persistence, isolation)
  - LLM provider factory and connections
  - Skills system (loading, attributes, user invocable, markdown conversion)
  - MCP system (models, client, config validation, tool handler)
  - Security (input sanitization, no hardcoded secrets)
  - Integration tests (end-to-end message flow)
- **Skills-Based Architecture** - Complete redesign of tool execution:
  - Users interact via simple commands (`/email`, `/calendar`, `/browse`)
  - Skills execute MCP tools directly, bypassing LLM tool-calling
  - Smaller prompts (tools not listed in every message)
  - Faster responses (no LLM deciding which tool to call)
  - Lower costs (fewer tokens used)
- **Email & Calendar Integration** - Two setup options:
  - **Self-Hosted (FREE)**: Uses `mcp-google` - unlimited usage, data stays local
  - **Composio**: Easy setup, 100 free actions/month
- **`/email` Skill** - Gmail management with direct MCP execution
  - Send, search, read, draft, label, archive emails
  - Gmail search syntax support
  - Direct execution via `_execute_email()` method
- **`/calendar` Skill** - Google Calendar management with direct MCP execution
  - View, create, update, delete events
  - Find free time slots
  - Natural language time parsing
  - Direct execution via `_execute_calendar()` method
- **EMAIL_CALENDAR_SETUP.md** - Comprehensive setup guide with both options
- **Skills Autocomplete** - Typing `/` in chat shows popup with all available skills
  - Click to insert skill command
  - Shows skill name, emoji, and description
- **Browse Skill** (`/browse`) - Open any URL using Playwright and get page content
- **Direct Playwright Execution** - Skills now execute Playwright MCP tools directly
  - Bypasses LLM tool calling for reliable browser automation
  - `_execute_google_search()` method for Google searches
  - `_execute_browse()` method for URL browsing
  - `_extract_mcp_result()` helper for parsing MCP responses
- **SkillForge Icon** - Added icon to Flet UI window and chat header
- **Flet UI** (`skillforge.py`) - Modern cross-platform desktop UI (renamed from `flet_ui_complete.py`)
  - Native desktop app support (Windows, macOS, Linux)
  - Organized provider sections by type (Local Servers, CLI, Cloud API)
  - Real-time server status monitoring for local LLM servers
  - CLI installation status checking for subscription-based providers
  - Collapsible sections for clean UI organization
  - Professional Navy & Gold color theme
  - Session management and conversation history viewer
  - MCP server management interface
  - Skills management interface
- **MCP Tools Tab** in Gradio UI for managing MCP servers
  - Add/remove/connect/disconnect servers via UI
  - Support for STDIO, Docker, SSE, and HTTP transports
  - Import servers from Claude Desktop config
  - View available tools and their parameters
- **MCP Tool Integration in Chat** - Bot can now use MCP tools automatically
  - Tools are included in system prompt
  - Tool call detection and execution loop
  - Results fed back to LLM for continued conversation
- New `core/mcp_tools.py` module for tool handling
- New `ui/settings/mcp_models.py` for MCP data models
- Security hardening with input validation
- Rate limiting on API endpoints
- Security headers for all responses
- Safe process management using psutil (replaces shell commands)
- Configuration validation
- SECURITY.md documentation
- DEPLOYMENT.md guide
- CONTRIBUTING.md guidelines

### Changed
- **Main Entry Point Renamed** - `flet_ui_complete.py` renamed to `skillforge.py`
- **Project Renamed** - Bot renamed from "mr_bot" to "SkillForge"
  - Updated all UI titles and display names
  - Updated bot personality prompts
  - Updated documentation
- **Skills-Based Architecture** - Major prompt optimization:
  - MCP tools removed from system prompt (router.py)
  - Skills handle tool execution directly instead of LLM
  - `mcp_tools.py` reduced to show only 5 tools per server when needed
  - Personality/system prompt used once, not repeated every message
- **Concise Bot Responses** - Updated PERSONALITY.md with brief response guidelines:
  - Action confirmations are short: "✅ Email sent to john@example.com"
  - No verbose explanations or JSON dumps
- **Cross-Platform Path Support** - Fixed `~` expansion in mcp_client.py:
  - Added `os.path.expanduser()` for environment variable values
  - Works on all platforms (Windows, macOS, Linux)
- **Headless Browser Mode** - Playwright MCP now runs in headless mode by default
  - Added `--headless` flag to `mcp_config.json` args
  - Browser automation runs invisibly in background
- **README.md** - Comprehensive documentation update
  - Added feature comparison table with OpenClaw.ai
  - Listed all 15+ LLM providers with auth methods
  - Documented skills system and MCP integration
  - Added memory system overview
- Updated `mcp_config.json` schema to include `type`, `enabled`, `description` fields
- Fixed Playwright MCP package name: `@playwright/mcp` (was incorrectly `@playwright/mcp-server`)
- Enhanced MCP client with better error handling, timeouts, and MCP protocol compliance
- Added `httpx` dependency for HTTP transport support

### Fixed
- **Flet API Compatibility** - Fixed all deprecated Flet API usage for latest version
  - Replaced `ft.Padding.symmetric()` with `ft.Padding.only()`
  - Fixed lowercase to uppercase: `ft.Border.all`, `ft.BorderRadius.all`, `ft.Margin.only`
  - Fixed `ft.alignment.center` replaced with `None`
  - Fixed `ElevatedButton` icon/text requirement (moved icon inside content Row)
- **ChatMessage Display** - Simplified ChatMessage class based on official Flet tutorial
  - Fixed text wrapping issues with long messages
  - Fixed responsive layout when resizing window
  - Uses `ft.Row` with `wrap=True` for proper message display
- **Google Search Skill** - Now uses Playwright directly instead of Gemini's WebFetch
  - Fixed `browser_evaluate` parameter: `{"function": "() => ..."}` instead of `{"expression": "..."}`
- **CLI Providers Hanging**: Fixed subprocess hang in `claude-cli` and `gemini-cli` providers
  - Root cause: CLI tools expect stdin input even when using `-p` flag
  - Solution: Added `input=''` parameter to `subprocess.run()` calls
  - Files modified: `core/llm/claude_cli_provider.py`, `core/llm/gemini_cli_provider.py`

### Security
- Fixed shell command injection vulnerability in port management
- Added input validation for session keys, roles, and content
- Implemented rate limiting to prevent abuse
- Added security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
- Debug mode now controlled by environment variable

---

## [1.0.0] - 2026-02-07

### Added
- Initial release of SkillForge
- Persistent memory architecture with JSONL storage
- Multi-channel support (MS Teams, WhatsApp, Telegram, Gradio UI)
- Multi-provider LLM support (15+ providers including Ollama, OpenAI, Anthropic, etc.)
- Session management with two-tier storage (sessions.json + JSONL)
- Automatic context compaction
- Dynamic personality and mood tracking
- Skills framework for prompt templates
- MCP (Model Context Protocol) integration
- OAuth authentication module (deprecated - vendors blocked third-party OAuth)
- CLI-based providers (Claude CLI, Gemini CLI) for subscription users
- Gradio web UI for testing
- Comprehensive documentation

### Features
- **Session Management**: Full conversation history stored in JSONL files
- **Context Management**: Automatic summarization when context gets too long
- **Multi-User Support**: Separate sessions per user/chat
- **Session Continuity**: Pick up conversations where you left off
- **Self-Improving Personality**: Bot can learn and update personality/mood files
- **Skills System**: Extensible prompt templates for specialized tasks
- **Hot-Swap Providers**: Change LLM providers at runtime via Gradio UI

### Documentation
- README.md with quick start guide
- ARCHITECTURE.md with detailed design
- LLM_PROVIDERS.md with provider configuration
- MCP_SETUP.md for tool integration
- MS_TEAMS_SETUP.md for Teams integration
- WHATSAPP_SETUP.md for WhatsApp integration
- TELEGRAM_SETUP.md for Telegram integration
- SETUP_GUIDE.md for getting started
- GRADIO_UI.md for web interface
- PERSONALITY.md for bot personality
- MOODS.md for mood tracking

### Security (Initial)
- API keys via environment variables
- Basic input sanitization
- Session isolation

---

## Release Notes Template

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Security fixes and improvements
```

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 1.0.0 | 2026-02-07 | Initial release with core features |
| 1.1.0 | 2026-02-09 | Security hardening, Flet UI fixes, direct Playwright execution |
| 1.2.0 | 2026-02-10 | Skills-based architecture, Email/Calendar integration |
| 1.3.0 | 2026-02-11 | WhatsApp integration with UI controls, access policies |
| 1.4.0 | 2026-02-20 | 6 new skills, todo handler, test suite, Flet UI fix |
| 1.5.0 | 2026-02-21 | Tiered auth, heartbeat, pattern detection, background tasks, MCP manager, webhook security (405 tests) |
| 1.6.0 | 2026-02-22 | Multi-persona system — per-user/channel personality profiles, 4 built-in personas, chat commands, settings UI (656 tests) |
| 1.7.0 | 2026-03-19 | Image/Vision support — 6-epic pipeline: image handling, vision providers, router integration, channel inbound/outbound, image generation (1268 tests) |

---

## Contributors

### Core Team
- **Syed Usama Bukhari** - Project Lead, Idrak AI Ltd
- **Idrak AI Ltd Team** - Development and Security

### Community Contributors
*To be added as contributions are received*

---

## Acknowledgments

- Thanks to all open-source projects that made this possible
- Special thanks to the AI/ML community for LLM provider integrations
- Gratitude to early testers and feedback providers

---

**Project**: SkillForge - Persistent Memory AI Chatbot
**Organization**: Idrak AI Ltd
**License**: MIT
**Mission**: Making AI Useful for Everyone

---

*For the latest updates, visit: [GitHub Repository](https://github.com/ub1979/SkillForge)*
