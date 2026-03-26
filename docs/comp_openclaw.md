# SkillForge vs OpenClaw.ai — Feature Comparison

> What OpenClaw has that SkillForge doesn't. Last updated: 2026-02-24.

---

## Big Architectural Gaps

| Feature | What It Does |
|---------|-------------|
| **Gateway (WebSocket control plane)** | Central `ws://` hub (`127.0.0.1:18789`) routing messages between channels and agents, with config schema introspection, Tailscale Serve/Funnel remote access, SSH tunnel support |
| **Multi-Agent / Sub-Agents** | `sessions_spawn` for parallel child agents, `sessions_list/history/send` for inter-agent messaging, `agents_list` to enumerate agents, orchestrator pattern |
| **Lobster Workflow Engine** | Typed YAML pipelines with step data flow (`$stepId.stdout`), approval gates (`approval: required`), composable macros, state watching for resumability |
| **Canvas / A2UI** | Live visual workspace the agent renders to — dashboards, forms, interactive HTML/JS pushed in real-time via `present`, `navigate`, `eval`, `a2ui_push` |

---

## Native Apps & Voice

| Feature | What It Does |
|---------|-------------|
| **macOS menu bar app** (`OpenClaw.app`) | Control plane, Voice Wake/PTT overlay, WebChat, debug tools, remote gateway control |
| **iOS node** | Canvas surface, camera snap/clip, screen recording, location, Bonjour pairing, Voice Wake |
| **Android node** | Same as iOS plus optional SMS access |
| **Voice Wake** | Always-on wake word ("Hey Claw") on macOS, iOS, Android |
| **Talk Mode** | Continuous speech conversation with push-to-talk overlay |
| **ElevenLabs TTS** | Text-to-speech output integration |
| **Speech-to-text** | Audio input transcription |

---

## Agent Tools SkillForge Lacks

| Feature | What It Does |
|---------|-------------|
| **Dedicated browser (CDP)** | Full Chrome DevTools Protocol control — `start`, `stop`, `tabs`, `open`, `snapshot`, `screenshot`, `act`, `navigate`, `pdf`, `upload`, `dialog`. Browser profile management (`profiles`, `create-profile`, `delete-profile`, `reset-profile`) |
| **`message` tool** | Agent can `send`, `poll`, `react`, `read`, `edit`, `delete`, `pin`, `unpin`, `thread-create`, `search`, `sticker` across Discord, Slack, Teams, Telegram from a unified API. Role/member/channel/emoji management |
| **`web_search`** | Native Brave Search API integration with `query` and `count` params — no MCP config needed |
| **`web_fetch`** | URL content extraction with `extractMode` and `maxChars` — no MCP config needed |
| **Image analysis tool** | Analyze images with configurable model (`image`, `prompt`, `model`, `maxBytesMb`) |
| **Process management** | `exec` with `background`, `timeout`, `elevated`, `host`, `yieldMs`. `process` tool for `list`, `poll`, `log`, `write`, `kill`, `clear`, `remove`. Per-session elevated bash toggle (`/elevated on\|off`) |
| **`apply_patch`** | Structured multi-hunk file patching tool |

---

## Security & UX

| Feature | What It Does |
|---------|-------------|
| **DM Pairing Mode** | Unknown senders receive pairing codes; explicit approval required before interaction |
| **VirusTotal scanning** | SHA-256 hashing of ClawHub skills, cross-checked against VirusTotal database; new skills uploaded for Code Insight analysis |
| **Loop detection** | Built-in guardrails tracking repetitive tool-call patterns with configurable thresholds |
| **`openclaw doctor`** | CLI command that surfaces risky DM policies and configuration issues |
| **`/think` command** | Granular reasoning levels: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`. Per-session persistence |
| **Model failover & profile rotation** | Auto-failover between OAuth and API key auth, credential rotation for load balancing, per-session model selection via chat |

---

## Channels SkillForge Doesn't Have

| Channel | Protocol |
|---------|----------|
| Signal | Signal API |
| iMessage | BlueBubbles |
| Google Chat | Google Chat API |
| Matrix | Matrix protocol |
| Zalo | Zalo API |
| WebChat (built-in) | Native web client (SkillForge uses Gradio instead) |

---

## Deployment Options

| Option | Details |
|--------|---------|
| **Docker** | Containerized deployment |
| **Nix** | Declarative configuration |
| **Cloudflare Workers** | Serverless via `cloudflare/moltworker` |
| **Headless Linux** | With separate device nodes pairing remotely |

SkillForge runs as a Python process with `pip install -e .` only.

---

## ClawHub Server-Side Features

SkillForge's ClawHub integration is a client that searches and installs. OpenClaw's registry also supports:

| Feature | Details |
|---------|---------|
| **`clawhub publish`** | Publish skills from CLI |
| **Semantic vector search** | OpenAI `text-embedding-3-small` + Convex vector index |
| **Starring & commenting** | Community engagement on skills |
| **Soft-delete/restore** | For skill owners and moderators |
| **Nix plugin declarations** | `systems`, `stateDirs`, `requiredEnv` in skill metadata |
| **SOUL.md registry** | System personality/lore files from onlycrabs.ai |

---

## Node System (Remote Device Control)

OpenClaw's `nodes` tool discovers and interacts with paired physical devices:

| Action | Description |
|--------|-------------|
| `camera_snap` | Take a photo from device camera |
| `camera_clip` | Record a short video clip |
| `screen_record` | Record the device screen |
| `location_get` | Get device GPS coordinates |
| `notify` | Send a notification to the device |
| `run` | Execute a command on the device |

macOS TCC integration gates `system.run` behind screen recording permissions. Bonjour auto-discovery for local iOS devices.

---

## Priority Recommendations

### Quick Wins (high value, moderate effort)
1. **`/think` level control** — simple command, big UX improvement
2. **Native `web_search` / `web_fetch` tools** — removes MCP dependency for common task
3. **Message editing/pinning/reactions** — enrich channel adapters
4. **Docker deployment** — Dockerfile + docker-compose

### Medium Effort
5. **Voice (TTS/STT)** — ElevenLabs TTS + Whisper STT
6. **Loop detection** — guardrails for repetitive tool calls
7. **DM pairing mode** — security improvement
8. **Image analysis tool** — multimodal support
9. **New channels** — Signal, Google Chat, Matrix

### Major Lifts
10. **Gateway architecture** — WebSocket control plane (big rewrite)
11. **Multi-agent system** — sub-agent spawning and orchestration
12. **Lobster workflow engine** — typed pipelines with approval gates
13. **Canvas / A2UI** — agent-driven visual workspace
14. **Companion apps** — macOS menu bar, iOS/Android nodes
