# Requirements: Image/Vision Support for SkillForge

## Feature Overview

Add full image handling pipeline to SkillForge — receiving images from users, processing them through vision-capable LLMs, storing them for future reference, and generating/sending images back to users.

---

## Functional Requirements

### FR-1: Image Receiving (Inbound)

**FR-1.1** — Telegram channel must detect photo/image messages, download the image file, and pass it alongside any caption text to the router.

**FR-1.2** — WhatsApp channel (via Baileys service) must detect image messages, download the media, and pass it alongside any caption text to the router.

**FR-1.3** — Flet desktop UI must allow users to attach/upload image files (PNG, JPG, JPEG, GIF, WEBP) from their local filesystem and send them with an optional text message.

**FR-1.4** — All channels must validate image files: max 20MB, allowed formats only (PNG, JPG, JPEG, GIF, WEBP, BMP), reject others with a user-friendly message.

### FR-2: Router & Message Pipeline

**FR-2.1** — `MessageRouter.handle_message()` and `handle_message_stream()` must accept an optional `attachments` parameter — a list of image file paths or image data.

**FR-2.2** — Router must save received images to `data/images/{session_key}/{timestamp}_{filename}` for future reference.

**FR-2.3** — Router must construct multi-modal message payloads (text + image) when attachments are present, formatting them per the active LLM provider's API spec.

**FR-2.4** — Session JSONL must record image references (file path, original filename, mime type) alongside message entries — NOT base64 inline (too large).

### FR-3: LLM Provider Vision Support

**FR-3.1** — `LLMProvider` base class must add a `supports_vision` property and an optional `format_vision_message()` method.

**FR-3.2** — OpenAI-compatible provider (`openai_compat.py`) must support vision via `content: [{type: "text", ...}, {type: "image_url", image_url: {url: "data:image/...;base64,..."}}]` format. Applies to: Ollama (with vision models), OpenAI, Groq, Together, Azure, LM Studio, vLLM, MLX.

**FR-3.3** — Anthropic provider must support vision via `content: [{type: "text", ...}, {type: "image", source: {type: "base64", media_type: "...", data: "..."}}]` format.

**FR-3.4** — Gemini provider must support vision via `inline_data` parts format.

**FR-3.5** — CLI providers (Claude CLI, Gemini CLI) — vision support is best-effort. If the CLI doesn't accept image input, gracefully fall back to text-only with a note that the image was received but cannot be processed.

**FR-3.6** — Llama.cpp provider — vision support depends on model. Mark as `supports_vision = False` by default, configurable.

**FR-3.7** — If the active LLM does not support vision and an image is received, respond with a clear message: "I received your image but my current model doesn't support image analysis. Switch to a vision-capable model to use this feature."

### FR-4: Image Storage

**FR-4.1** — All received images saved to `data/images/` organized by session key and timestamp.

**FR-4.2** — Storage manager must handle cleanup: configurable max storage (default 1GB), oldest-first eviction when limit reached.

**FR-4.3** — Images must be referenceable in conversation — if a user says "that image I sent earlier", the LLM should have the image path in conversation history to re-load it.

### FR-5: Image Generation & Sending (Outbound)

**FR-5.1** — Support image generation via MCP tools (e.g., DALL-E MCP, Stable Diffusion MCP) or direct API integration.

**FR-5.2** — When the LLM response contains an image URL or generated image data, the router must download/save it and send it through the appropriate channel.

**FR-5.3** — Telegram channel must send images via `send_photo()` API.

**FR-5.4** — WhatsApp channel must send images via the Baileys service `/send` endpoint with media.

**FR-5.5** — Flet UI must display images inline in the chat using `ft.Image` component.

**FR-5.6** — LLM can emit a ```image_gen``` code block to trigger image generation (follows existing code-block handler pattern).

---

## Non-Functional Requirements

### NFR-1: Performance
- Image processing must not block the main message loop — use async I/O for downloads/uploads.
- Base64 encoding for LLM API calls should be done lazily (only when sending to LLM, not stored).
- Image resizing for LLM context: auto-resize images >4MB to fit within LLM API limits.

### NFR-2: Security
- Validate all image files (check magic bytes, not just extension).
- Sanitize filenames to prevent path traversal.
- No execution of image content (SVG with scripts, etc.).
- Respect existing permission system — `files` permission required for image features.

### NFR-3: Backward Compatibility
- All changes must be backward compatible — existing text-only workflows must work identically.
- `attachments` parameter is optional everywhere — None means text-only (current behavior).
- No changes to existing test behavior.

### NFR-4: Testing
- Unit tests for image validation, storage, and cleanup.
- Unit tests for each LLM provider's vision message formatting.
- Integration tests for image flow through router.
- Channel-specific tests for image receive/send.

---

## Affected Components

| Component | Change Type | Impact |
|-----------|------------|--------|
| `src/skillforge/channels/telegram.py` | Modify | Add photo handler, image download |
| `src/skillforge/channels/whatsapp.py` | Modify | Add image media handling |
| `src/skillforge/flet/views/chat.py` | Modify | Add image upload button, inline display |
| `src/skillforge/flet/components/chat_message.py` | Modify | Render images in chat |
| `src/skillforge/core/router.py` | Modify | Accept attachments, build multi-modal messages |
| `src/skillforge/core/sessions.py` | Modify | Store image references in JSONL |
| `src/skillforge/core/llm/base.py` | Modify | Add vision support interface |
| `src/skillforge/core/llm/openai_compat.py` | Modify | Multi-modal message format |
| `src/skillforge/core/llm/anthropic_provider.py` | Modify | Multi-modal message format |
| `src/skillforge/core/llm/gemini_provider.py` | Modify | Multi-modal message format |
| `src/skillforge/core/llm/claude_cli_provider.py` | Modify | Best-effort vision |
| `src/skillforge/core/llm/gemini_cli_provider.py` | Modify | Best-effort vision |
| `src/skillforge/core/llm/llamacpp_provider.py` | Modify | Configurable vision flag |
| `src/skillforge/core/image_handler.py` | **New** | Image validation, storage, cleanup |
| `whatsapp_service/index.js` | Modify | Media download endpoint |
| `tests/test_image_handler.py` | **New** | Image pipeline tests |
| `tests/test_vision_providers.py` | **New** | Vision format tests |

---

## Out of Scope

- Video/audio file processing (future feature)
- Image editing/manipulation (crop, filter, etc.)
- OCR as a separate skill (could be added later via MCP)
- Image search within stored images (future semantic search)
