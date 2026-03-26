# SkillForge — Roadmap

## 1. Fix & Enable Semantic Memory ✅
- [x] Replace ChromaDB (too slow) with SQLite FTS5 — zero dependencies, instant startup
- [x] Enable persistent long-term recall beyond recent JSONL messages
- [x] Memory learns user preferences, facts, and context across sessions
- [x] `/memory` and `/forget` commands for user control
- [x] LLM-assisted fact extraction as second-pass
- [x] Context injection capped at ~500 tokens

## 2. Expand Skills Library (10x)
- [x] GitHub (issues, PRs, notifications)
- [ ] Spotify / Music control _(community contribution welcome)_
- [x] Note-taking (Obsidian, Notion)
- [ ] Home automation (HomeAssistant) _(community contribution welcome)_
- [ ] Finance / banking alerts _(community contribution welcome)_
- [x] File management (local files, cloud storage)
- [ ] Weather skill
- [x] News / RSS feeds
- [x] Reminders / Todos
- [x] Social media (Twitter, LinkedIn)

## 3. Multi-Persona / Per-User Personality ✅
- [x] Persona files with YAML frontmatter — `data/personality/agents/*.md`
- [x] 4 built-in personas: default, formal, casual, technical
- [x] Per-user override + per-channel default (user > channel > base)
- [x] Chat commands: `/persona`, `/list-personas`, `/set-persona`, `/create-persona`
- [x] Settings UI section with persona list, channel defaults, create form
- [x] Per-key prompt cache invalidation on persona changes
- [x] 55 tests in `tests/test_personas.py`

## 4. Autonomous Agent Mode (Background Tasks)
- [ ] Multi-step agent loop for scheduled tasks (chain skills, make decisions)
- [ ] Proactive actions without being prompted
- [x] Daily briefing workflow — **infrastructure done** (HeartbeatManager: morning_brief, deadline_watch, unusual_activity, daily_summary with per-user config, scheduler loop, persistence, 27 tests)
- [ ] Wire heartbeat generators to real skill outputs (email/calendar/todo skills → composed summary instead of placeholder templates)

## 5. One-Click Setup & Skill Marketplace
- [x] Restructure to `src/skillforge/` package layout with `pyproject.toml`
- [x] `pip install -e .` replaces all `sys.path` hacks
- [ ] Single CLI entry point (`skillforge start`)
- [x] Skill marketplace — ClawHub integration (search/install from OpenClaw.ai registry)
- [ ] Interactive first-run setup wizard
- [x] Streamline MCP config auto-detection — auto-connect enabled servers at startup

## 6. Scheduler Upgrade ✅
- [x] Interval triggers (`kind: "every"`) — repeat every N seconds/minutes/hours
- [x] One-shot triggers (`kind: "at"`) — run once at a specific datetime, auto-delete
- [x] Retry backoff — exponential: 30s → 1m → 5m → 15m → 60m (max 5 retries)
- [x] Human-readable schedule display (cron → plain English)
- [x] Per-task concurrency control (`max_concurrent`)
- [x] Fix `datetime.utcnow()` → `datetime.now(tz=timezone.utc)`

---

## P0 — High Value, Moderate Effort _(OpenClaw parity + roadmap)_

### 7. `/think` Level Control ✅
- [x] `/think` command with levels: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`
- [x] Per-session thinking level persistence
- [x] Map levels to temperature (0.0 → 1.2), applied to both chat and stream paths
- [x] 20 tests in `tests/test_think_levels.py`

### 8. Native Web Search & Fetch Tools ✅
- [x] `web_search` tool — Brave Search API + DuckDuckGo fallback (works without API key)
- [x] `web_fetch` tool — URL content extraction with HTML stripping + max chars
- [x] No MCP dependency — LLM emits ```web_search```/```web_fetch``` blocks, handler executes
- [x] System prompt tells LLM about web search capability (no more `/google-search` text output)
- [x] Wired into both handle_message and handle_message_stream paths
- [x] 29 tests in `tests/test_web_tools.py`

### 9. Docker Deployment ✅
- [x] `Dockerfile` — multi-stage build, Python 3.12, all dependencies
- [x] `docker-compose.yml` — Gradio + all channels as profiles + WhatsApp service
- [x] `.dockerignore` — exclude data/, .git/, node_modules/, tests/

### 10. Single CLI Entry Point ✅
- [x] `skillforge` console script registered in pyproject.toml `[project.scripts]`
- [x] `skillforge ui|gradio|bot|telegram|slack|discord` — all channel launchers
- [x] `skillforge doctor` — check config, dependencies, core imports, skills
- [x] 8 tests in `tests/test_cli.py`

### 11. Flet UI Modular Refactor ✅
- [x] Split 5,882-line `app.py` monolith into `src/skillforge/flet/` package (16 modular files)
- [x] `flet/theme.py` — AppColors, Spacing, provider dicts, utility functions
- [x] `flet/storage.py` — SecureStorage for encrypted token/settings persistence
- [x] `flet/components/` — ChatMessage (Markdown rendering), CollapsibleSection, StatusBadge, StyledButton, cards
- [x] `flet/views/` — ChatView, SettingsView, ToolsView, MCPPanel, SkillsPanel, ClawHubPanel, HistoryView
- [x] `flet/app.py` — thin orchestrator with 4-tab navigation (Chat, Tools, Settings, History)
- [x] Navigation consolidated: 6 tabs → 4 tabs (MCP + Skills + ClawHub merged into Tools tab)
- [x] Animated typing indicator (`ProgressRing` + "SkillForge is thinking...")
- [x] Markdown rendering for assistant messages (`ft.Markdown`, GitHub Web, atom-one-dark)
- [x] 15 new import tests in `TestFletImports` (862 total)

### 11b. UI/UX Redesign ✅
- [x] Settings card-grid navigation — 7 clickable icon cards (Appearance, Personas, Permissions, Channels, Scheduler, LLM Providers, Memory)
- [x] Design system overhaul — new dark/light palettes, ACCENT color (#6366F1), SURFACE_ELEVATED, DIVIDER
- [x] New reusable widgets: `SectionHeader`, `SubItemAccordion` (DRY refactor of 3× duplicated code)
- [x] `CollapsibleSection` redesign with left accent bar and box shadow
- [x] Status cards with left accent bars (green/muted)
- [x] Chat focus fix — `/` commands no longer lose focus in web UI
- [x] Flet 0.80+ deprecated API migration across all 12 UI files
- [x] All 1313 tests passing

---

## P1 — Differentiating Features

### 11. Multi-Step Agent Loop
- [ ] Skill chaining — output of one skill feeds into another
- [ ] Decision points — agent decides next step based on results
- [ ] Workflow definitions (YAML or skill-based)
- [ ] Ties into scheduler for automated daily briefings

### 12. Loop Detection Guardrails
- [ ] Track repetitive tool-call patterns per session
- [ ] Configurable thresholds (e.g., 3 identical calls in 60s)
- [ ] Warning message to user + optional auto-break
- [ ] Tests in `tests/test_loop_detection.py`

### 13. Image/Vision Support ✅
- [x] E-001: Core Image Infrastructure — `image_handler.py` with validation, storage, cleanup, base64 encoding (97 tests)
- [x] E-002: LLM Provider Vision Support — `supports_vision` + `format_vision_messages()` on all 7 providers (36 tests)
- [x] E-003: Router Integration — `handle_message`/`handle_message_stream` accept `attachments`, JSONL records, vision formatting, permission gating (20 tests)
- [x] E-004: Channel Inbound — Telegram photo handler, WhatsApp image handler, Flet UI file picker (22 tests)
- [x] E-005: Channel Outbound — Router `extract_outbound_images()`, Telegram `send_image()`, WhatsApp `send_image()`, Baileys `/send-media`, Flet inline rendering (36 tests)
- [x] E-006: Image Generation — `image_gen_handler.py` code-block handler, MCP delegation, router wired (67 tests)

### 14. Admin Panel & Cross-Platform Identity ✅
- [x] Login gate — password-protected Flet UI with PBKDF2-hashed admin credentials (6 tests)
- [x] Admin dashboard — 5th nav tab: Users & Roles, Permission Requests, Identity Linking
- [x] Cross-platform identity resolver — `identity_resolver.py`, map telegram/whatsapp/slack IDs to canonical users (8 tests)
- [x] Permission request queue — `permission_requests.py`, submit/approve/deny flow (9 tests)
- [x] New commands: `/request-permission`, `/my-requests`, `/pending-requests`, `/approve`, `/deny`, `/link-identity`
- [x] Router identity resolution at top of handle_message / handle_message_stream
- [x] Permission denial messages now hint at `/request-permission`
- [x] Chat avatar uses `chat_icon.png`, app icon uses `icon/icon.png`

### 15. Message Edit/Pin/React
- [ ] Unified message tool: edit, delete, pin, unpin, react across channels
- [ ] Channel adapter extensions for Discord, Slack, Telegram, Teams
- [ ] Agent can manage messages programmatically

### 15. Model Failover & Rotation
- [ ] Auto-retry with next provider on failure (configurable fallback chain)
- [ ] Credential rotation for load balancing across API keys
- [ ] Per-session model selection via `/model` command

### 16. Voice (TTS/STT)
- [ ] Speech-to-text — Whisper API or local whisper.cpp
- [ ] Text-to-speech — ElevenLabs or local TTS
- [ ] Voice messages on Telegram/WhatsApp → transcribe → respond
- [ ] Optional TTS reply

### 17. Weather Skill
- [ ] OpenWeatherMap or similar API
- [ ] Location-aware (use memory for user's city)
- [ ] SKILL.md format, user-invocable

---

## P2 — Nice to Have

### 18. DM Pairing Mode
- [ ] Unknown senders receive pairing codes
- [ ] Explicit approval before interaction
- [ ] Pairing whitelist persisted to disk

### 19. First-Run Setup Wizard
- [ ] Interactive terminal prompts for LLM provider, API keys, channels
- [ ] Auto-generate config.py from answers
- [ ] `skillforge setup` or auto-detect on first `skillforge start`

### 20. New Channels
- [ ] Signal (signal-cli or Signal API)
- [ ] Google Chat (Google Chat API)
- [ ] Matrix (matrix-nio)

### 21. ClawHub Publishing
- [ ] `skillforge publish-skill <name>` — publish to ClawHub registry
- [ ] Semantic vector search for skill discovery (embedding-based)
- [ ] Starring & commenting on skills

---

## P3 — Major Architecture Lifts

### 22. Gateway Architecture
- [ ] WebSocket control plane for routing between channels and agents
- [ ] Config schema introspection at runtime
- [ ] Remote access via Tailscale/SSH

### 23. Multi-Agent System
- [ ] Sub-agent spawning (`sessions_spawn`)
- [ ] Inter-agent messaging (`sessions_send`)
- [ ] Orchestrator pattern — parent coordinates children

### 24. Workflow Engine
- [ ] Typed YAML pipelines with step data flow
- [ ] Approval gates (human-in-the-loop)
- [ ] Composable macros — invoke multi-step workflows as single tool call

### 25. Canvas / A2UI
- [ ] Live visual workspace the agent renders to
- [ ] Interactive HTML/JS push from agent to UI
- [ ] Dashboard, form, diagram rendering

### 26. Companion Apps
- [ ] macOS menu bar app — control plane, voice overlay
- [ ] iOS/Android nodes — camera, location, screen recording, Bonjour pairing
