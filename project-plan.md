# Image/Vision Support — Project Plan

**Date:** 2026-03-19
**Status:** Ready for implementation
**Source docs:** `requirements.md`, `plan.md`
**Estimated total effort:** ~12-15 dev-days
**Estimated lines of code:** ~1,915 new/modified lines + ~900 test lines

---

## Table of Contents

1. [Epics Overview](#epics-overview)
2. [Dependency Graph](#dependency-graph)
3. [E-001: Core Image Infrastructure](#e-001-core-image-infrastructure)
4. [E-002: LLM Provider Vision Support](#e-002-llm-provider-vision-support)
5. [E-003: Router Integration](#e-003-router-integration)
6. [E-004: Channel Inbound](#e-004-channel-inbound)
7. [E-005: Channel Outbound](#e-005-channel-outbound)
8. [E-006: Image Generation](#e-006-image-generation)
9. [E-007: Testing](#e-007-testing)
10. [E-008: Documentation](#e-008-documentation)
11. [Summary & Estimates](#summary--estimates)

---

## Epics Overview

| Epic | Title | Stories | Tasks | Est. Days |
|------|-------|---------|-------|-----------|
| E-001 | Core Image Infrastructure | 3 | 7 | 2.0 |
| E-002 | LLM Provider Vision Support | 3 | 9 | 2.0 |
| E-003 | Router Integration | 2 | 5 | 2.0 |
| E-004 | Channel Inbound | 3 | 7 | 2.5 |
| E-005 | Channel Outbound | 3 | 5 | 1.5 |
| E-006 | Image Generation | 2 | 4 | 1.5 |
| E-007 | Testing | 4 | 7 | 2.0 |
| E-008 | Documentation | 1 | 3 | 0.5 |
| **Total** | | **21** | **47** | **14.0** |

---

## Dependency Graph

```
E-001 Core Image Infrastructure
  |
  +-----> E-002 LLM Provider Vision Support
  |         |
  |         +----> E-003 Router Integration
  |                  |
  |                  +----> E-004 Channel Inbound
  |                  |        |
  |                  |        +----> E-005 Channel Outbound
  |                  |
  |                  +----> E-006 Image Generation
  |
  +-----> E-007 Testing (written alongside each epic)
  |
  +-----> E-008 Documentation (last)
```

Tasks within each epic must be done in order unless noted otherwise.
E-002 and E-003 can be parallelized after E-001 is done.

---

## E-001: Core Image Infrastructure

Central image handling module — validation, storage, cleanup, base64 encoding. Every other epic depends on this.

### Story S-001: Image Validation
*As a developer, I need a central validation system that checks file format, magic bytes, size limits, and rejects dangerous files, so that all channels share the same security guarantees.*

### Story S-002: Image Storage & Cleanup
*As a system operator, I need images stored in an organized directory structure with automatic cleanup when storage limits are reached, so that disk usage stays bounded.*

### Story S-003: Attachment Data Model
*As a developer, I need a serializable Attachment dataclass that all components can pass around, so that image metadata flows cleanly through the system.*

---

### Task T-001: Create Attachment dataclass
- **Epic**: E-001
- **Story**: S-003
- **Priority**: P0 (blocker)
- **Depends on**: none
- **Files**: `src/skillforge/core/image_handler.py` (new)
- **Description**: Create the new `image_handler.py` module with the `Attachment` dataclass. Fields: `file_path` (str), `original_filename` (str), `mime_type` (str), `size_bytes` (int), `width` (Optional[int]), `height` (Optional[int]). Include `to_dict()` for JSONL serialization and `from_dict()` classmethod for deserialization. Also define module-level constants: `ALLOWED_MIME_TYPES` (dict mapping MIME types to magic byte signatures), `EXTENSION_TO_MIME` (dict mapping file extensions to MIME types), `MAX_IMAGE_SIZE` (20 MB), `LLM_MAX_SIZE` (4 MB), `DEFAULT_STORAGE_LIMIT` (1 GB), `SAFE_FILENAME_RE` (regex for filename sanitization).
- **Acceptance criteria**:
  - `Attachment` dataclass importable from `skillforge.core.image_handler`
  - `to_dict()` returns dict with file_path, original_filename, mime_type, size_bytes
  - `from_dict()` round-trips correctly
  - Constants defined and importable
- **Est.**: 0.25 days

---

### Task T-002: Implement magic byte validation
- **Epic**: E-001
- **Story**: S-001
- **Priority**: P0 (blocker)
- **Depends on**: T-001
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler._check_magic_bytes(path)` — reads first 12 bytes, compares against `ALLOWED_MIME_TYPES` signatures. Returns `(bool, Optional[str])` — success flag and detected MIME type. Implement `ImageHandler.detect_mime_type(file_path)` as a public wrapper. For WEBP, perform the additional check that bytes 8-12 equal `b"WEBP"`.
- **Acceptance criteria**:
  - Correctly identifies PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), GIF87a/GIF89a, WEBP (`RIFF` + `WEBP` at 8-12), BMP (`BM`)
  - Returns `(False, None)` for unrecognized formats
  - Does not accept SVG files
- **Est.**: 0.25 days

---

### Task T-003: Implement validate_file method
- **Epic**: E-001
- **Story**: S-001
- **Priority**: P0 (blocker)
- **Depends on**: T-002
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler.validate_file(file_path) -> Tuple[bool, str]`. Checks in order: file exists, is a file (not dir), size > 0, size <= 20MB, extension in allowlist, magic bytes match extension. WEBP gets additional bytes-8-12 check. Returns `(True, "")` on success, `(False, "human-readable error")` on failure.
- **Acceptance criteria**:
  - Rejects missing files, directories, empty files, oversized files (>20MB)
  - Rejects wrong extension (e.g., `.txt`)
  - Rejects magic byte mismatch (e.g., `.jpg` extension with PNG content)
  - Rejects invalid WEBP (correct RIFF header but no WEBP at bytes 8-12)
  - Accepts all valid image types: PNG, JPEG, GIF, WEBP, BMP
- **Est.**: 0.25 days

---

### Task T-004: Implement filename sanitization
- **Epic**: E-001
- **Story**: S-001
- **Priority**: P0 (blocker)
- **Depends on**: T-001
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler.sanitize_filename(filename) -> str` as a static method. Steps: (1) strip directory components via `Path(filename).name`, (2) remove null bytes, (3) replace chars not matching `[a-zA-Z0-9_.\-]` with `_`, (4) prepend `image` if name starts with `.` or is empty, (5) truncate to 200 chars preserving extension.
- **Acceptance criteria**:
  - `../../etc/passwd` -> `passwd`
  - `photo (1).jpg` -> `photo__1_.jpg`
  - `.hidden` -> `image.hidden`
  - Empty string -> `image`
  - Null bytes removed
  - 250-char filename truncated to 200 chars with extension preserved
- **Est.**: 0.15 days

---

### Task T-005: Implement store_image method
- **Epic**: E-001
- **Story**: S-002
- **Priority**: P0 (blocker)
- **Depends on**: T-003, T-004
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler.store_image(source_path, session_key, original_filename=None) -> Attachment`. Validates the file via `validate_file()`, sanitizes the filename and session key, creates directory `data/images/{safe_session}/`, copies file to `{timestamp_ms}_{safe_name}`, returns populated `Attachment`. Raises `ValueError` on validation failure. The `ImageHandler.__init__` takes `data_dir` (default `data/images`) and `max_storage_bytes` (default 1GB), creates the directory on init.
- **Acceptance criteria**:
  - Valid image is copied to correct directory structure
  - Original file is not moved or deleted
  - Returned Attachment has correct file_path, mime_type, size_bytes
  - Raises ValueError for invalid images
  - Session key is sanitized for directory name
  - Timestamp in filename prevents collisions
- **Est.**: 0.25 days

---

### Task T-006: Implement base64 encoding with resize
- **Epic**: E-001
- **Story**: S-002
- **Priority**: P1 (critical)
- **Depends on**: T-005
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler.encode_base64(file_path, max_size=LLM_MAX_SIZE) -> str`. Reads file bytes. If size > max_size, calls `_resize_image_bytes(data, max_size)`. Returns base64-encoded ASCII string. The `_resize_image_bytes` method uses Pillow (optional dependency): tries quality reduction [85, 70, 50, 30], then dimension reduction (0.75 factor, stepping down by 0.15). Converts PNG with alpha to RGB+JPEG for size reduction. If Pillow not installed, logs warning and returns original data.
- **Acceptance criteria**:
  - Small images (<4MB) return valid base64 without modification
  - Large images (>4MB) are resized when Pillow is available
  - Works without Pillow installed (returns full-size base64 with warning)
  - Output is valid ASCII base64 string
- **Est.**: 0.35 days

---

### Task T-007: Implement storage cleanup (eviction)
- **Epic**: E-001
- **Story**: S-002
- **Priority**: P2 (important)
- **Depends on**: T-005
- **Files**: `src/skillforge/core/image_handler.py`
- **Description**: Implement `ImageHandler.get_storage_usage() -> int` — recursively sums file sizes under `data_dir`. Implement `ImageHandler.cleanup_if_needed()` — if total usage exceeds `max_storage_bytes`, collects all files sorted by mtime (oldest first), deletes files until usage drops below the limit. Logs each evicted file.
- **Acceptance criteria**:
  - `get_storage_usage()` returns correct byte count
  - `cleanup_if_needed()` is a no-op when under limit
  - When over limit, oldest files are deleted first
  - Deletion stops as soon as usage is under limit
  - Handles OSError gracefully during deletion
- **Est.**: 0.25 days

---

## E-002: LLM Provider Vision Support

Add `supports_vision` property and `format_vision_messages()` method to the base class and all 7 provider implementations.

### Story S-004: Vision Interface in Base Provider
*As a developer, I need a standard interface on the LLM base class for vision support, so that the router can check capabilities and format messages uniformly.*

### Story S-005: API-Based Provider Vision Formatting
*As a user, I want my images automatically formatted for whichever LLM API I am using (OpenAI, Anthropic, Gemini), so that vision just works with any supported provider.*

### Story S-006: Non-Vision Provider Graceful Fallback
*As a user, when I send an image to a model that does not support vision, I want a clear message telling me to switch models, rather than a cryptic error.*

---

### Task T-008: Add supports_vision and format_vision_messages to LLMProvider base
- **Epic**: E-002
- **Story**: S-004
- **Priority**: P0 (blocker)
- **Depends on**: T-001
- **Files**: `src/skillforge/core/llm/base.py`
- **Description**: Add to the `LLMProvider` base class: (1) `supports_vision` property returning `False` by default, (2) `format_vision_messages(messages, attachments) -> List[Dict]` method that returns messages unchanged by default. Import `Attachment` under `TYPE_CHECKING` guard. No changes to `chat()`, `chat_stream()`, or other existing signatures.
- **Acceptance criteria**:
  - `LLMProvider().supports_vision` returns `False`
  - `LLMProvider().format_vision_messages(msgs, atts)` returns `msgs` unchanged
  - Type hints reference `Attachment` without runtime import
  - No existing tests break
- **Est.**: 0.15 days

---

### Task T-009: Implement OpenAI-compatible vision formatting
- **Epic**: E-002
- **Story**: S-005
- **Priority**: P0 (blocker)
- **Depends on**: T-008, T-006
- **Files**: `src/skillforge/core/llm/openai_compat.py`
- **Description**: Override `supports_vision` to return `True`. Implement `format_vision_messages()` on `OpenAICompatibleProvider`. Finds the last user message, converts its `content` from a plain string to a list: `[{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:{mime};base64,{b64}"}}]` for each attachment. Uses `ImageHandler.encode_base64()` for lazy encoding. This format applies to all OpenAI-compatible providers: OpenAI, Groq, Together, Azure, LM Studio, vLLM, MLX, Ollama (with vision models).
- **Acceptance criteria**:
  - `supports_vision` returns `True`
  - Single image produces correct content array with text + image_url parts
  - Multiple images produce multiple image_url entries
  - No attachments returns messages unchanged
  - No user message in history returns messages unchanged
  - Messages are shallow-copied (originals not mutated)
- **Est.**: 0.3 days

---

### Task T-010: Implement Anthropic vision formatting
- **Epic**: E-002
- **Story**: S-005
- **Priority**: P0 (blocker)
- **Depends on**: T-008, T-006
- **Files**: `src/skillforge/core/llm/anthropic_provider.py`
- **Description**: Override `supports_vision` to return `True`. Implement `format_vision_messages()` on `AnthropicProvider`. Converts last user message content to: `[{"type": "image", "source": {"type": "base64", "media_type": "{mime}", "data": "{b64}"}}, {"type": "text", "text": "..."}]`. Note Anthropic puts images BEFORE text. Verify that the existing `_prepare_request` method passes content through as-is (string or list) — per plan.md analysis, no changes needed to `_prepare_request`.
- **Acceptance criteria**:
  - `supports_vision` returns `True`
  - Image parts appear before text part in content array (Anthropic convention)
  - Content uses `source.type: "base64"`, `source.media_type`, `source.data` structure
  - Existing `_prepare_request` correctly handles list-type content without changes
  - Messages are shallow-copied
- **Est.**: 0.3 days

---

### Task T-011: Implement Gemini vision formatting
- **Epic**: E-002
- **Story**: S-005
- **Priority**: P0 (blocker)
- **Depends on**: T-008, T-006
- **Files**: `src/skillforge/core/llm/gemini_provider.py`
- **Description**: Override `supports_vision` to return `True`. Implement `format_vision_messages()` on `GeminiProvider`. Converts last user message content to a list of parts: `[{"inline_data": {"mime_type": "{mime}", "data": "{b64}"}}, "text string"]`. Additionally, update `_convert_messages()` to handle list-type content — when content is a list, pass it directly as `parts` instead of wrapping in `[content]`. Update `_chat_genai`, `_stream_genai` (and vertex variants) to send multi-part content correctly: if parts is a single string send directly, if multi-part (list with dicts) send the full list.
- **Acceptance criteria**:
  - `supports_vision` returns `True`
  - `format_vision_messages` produces correct inline_data parts format
  - `_convert_messages` handles both string and list content types
  - `_chat_genai` / `_stream_genai` send multi-part messages correctly
  - Text-only messages continue to work identically (backward compat)
  - Messages are shallow-copied
- **Est.**: 0.4 days

---

### Task T-012: Set Claude CLI provider vision flag
- **Epic**: E-002
- **Story**: S-006
- **Priority**: P2 (important)
- **Depends on**: T-008
- **Files**: `src/skillforge/core/llm/claude_cli_provider.py`
- **Description**: Override `supports_vision` property to return `False`. No `format_vision_messages` override needed — the base class no-op is sufficient. The router will handle the fallback message when `supports_vision` is `False` and attachments are present.
- **Acceptance criteria**:
  - `ClaudeCliProvider().supports_vision` returns `False`
  - No new methods added
  - Existing functionality unchanged
- **Est.**: 0.05 days

---

### Task T-013: Set Gemini CLI provider vision flag
- **Epic**: E-002
- **Story**: S-006
- **Priority**: P2 (important)
- **Depends on**: T-008
- **Files**: `src/skillforge/core/llm/gemini_cli_provider.py`
- **Description**: Override `supports_vision` property to return `False`. Same rationale as T-012.
- **Acceptance criteria**:
  - `GeminiCliProvider().supports_vision` returns `False`
  - No new methods added
  - Existing functionality unchanged
- **Est.**: 0.05 days

---

### Task T-014: Set llama.cpp provider configurable vision flag
- **Epic**: E-002
- **Story**: S-006
- **Priority**: P2 (important)
- **Depends on**: T-008
- **Files**: `src/skillforge/core/llm/llamacpp_provider.py`
- **Description**: Override `supports_vision` property to return `self.config.extra.get("supports_vision", False)`. This allows users who run vision-capable GGUF models (e.g., LLaVA) to enable vision via config. No `format_vision_messages` override — llama.cpp vision models use OpenAI-compatible format but the library handles it internally, left as a future enhancement.
- **Acceptance criteria**:
  - Default `supports_vision` returns `False`
  - When `config.extra["supports_vision"] = True`, property returns `True`
  - No other changes to the provider
- **Est.**: 0.05 days

---

### Task T-015: Verify Anthropic _prepare_request handles list content
- **Epic**: E-002
- **Story**: S-005
- **Priority**: P1 (critical)
- **Depends on**: T-010
- **Files**: `src/skillforge/core/llm/anthropic_provider.py`
- **Description**: Review the existing `_prepare_request` method in `anthropic_provider.py`. Confirm that when building `chat_messages`, it passes `content` through as-is (whether string or list). Per plan.md analysis, `content = msg.get("content", "")` returns whatever the value is (string or list), and it is appended directly. Verify this in the actual code. If any string-coercion exists (e.g., `str(content)` or f-string interpolation), fix it. Add a code comment noting that content may be a list for vision messages.
- **Acceptance criteria**:
  - `_prepare_request` does not coerce content to string
  - A message with `content: [{"type": "image", ...}, {"type": "text", ...}]` passes through correctly
  - Add inline comment for future maintainers
- **Est.**: 0.15 days

---

### Task T-016: Add Pillow to optional dependencies
- **Epic**: E-002
- **Story**: S-005
- **Priority**: P2 (important)
- **Depends on**: T-006
- **Files**: `pyproject.toml`
- **Description**: Add `Pillow` as an optional dependency in `pyproject.toml` under an `[images]` extra. Also add it to the `doctor` check in the CLI so that `skillforge doctor` reports whether Pillow is available for image resizing. Update the relevant section in `src/skillforge/__main__.py` (or wherever `doctor` is implemented).
- **Acceptance criteria**:
  - `pip install -e ".[images]"` installs Pillow
  - `skillforge doctor` checks for Pillow availability
  - Image pipeline works without Pillow (graceful degradation)
- **Est.**: 0.15 days

---

## E-003: Router Integration

Wire image attachments through the router's message pipeline: accept attachments, store references in JSONL, format vision messages, handle non-vision fallback.

### Story S-007: Router Accepts Image Attachments
*As a channel developer, I need `handle_message()` and `handle_message_stream()` to accept an optional `attachments` parameter, so that I can pass validated images from any channel into the processing pipeline.*

### Story S-008: Session History Stores Image References
*As a user, I want my image attachments recorded in conversation history (as file path references, not inline base64), so that previous images can be referenced in follow-up messages.*

---

### Task T-017: Update handle_message signature
- **Epic**: E-003
- **Story**: S-007
- **Priority**: P0 (blocker)
- **Depends on**: T-001, T-008
- **Files**: `src/skillforge/core/router.py`
- **Description**: Add `attachments: Optional[List["Attachment"]] = None` parameter to `handle_message()`. Import `Attachment` under `TYPE_CHECKING`. Default `None` preserves all existing call sites. No logic changes yet — just the signature.
- **Acceptance criteria**:
  - Signature accepts `attachments` parameter
  - Default is `None`
  - All existing callers (telegram, whatsapp, flet, tests) continue to work unchanged
  - No test failures
- **Est.**: 0.1 days

---

### Task T-018: Update handle_message_stream signature
- **Epic**: E-003
- **Story**: S-007
- **Priority**: P0 (blocker)
- **Depends on**: T-001, T-008
- **Files**: `src/skillforge/core/router.py`
- **Description**: Add `attachments: Optional[List["Attachment"]] = None` parameter to `handle_message_stream()`. Same approach as T-017.
- **Acceptance criteria**:
  - Signature accepts `attachments` parameter
  - Default is `None`
  - All existing callers continue to work unchanged
  - No test failures
- **Est.**: 0.1 days

---

### Task T-019: Initialize ImageHandler in router
- **Epic**: E-003
- **Story**: S-007
- **Priority**: P0 (blocker)
- **Depends on**: T-005, T-017
- **Files**: `src/skillforge/core/router.py`
- **Description**: In `MessageRouter.__init__`, import and initialize `ImageHandler`: `self._image_handler = ImageHandler()`. Use runtime import (not TYPE_CHECKING) since the handler is instantiated at init time.
- **Acceptance criteria**:
  - `self._image_handler` is available on router instances
  - Router init does not fail if `data/images` directory does not yet exist (ImageHandler creates it)
  - Existing router tests pass (override in fixtures if needed)
- **Est.**: 0.1 days

---

### Task T-020: Implement attachment processing logic in handle_message
- **Epic**: E-003
- **Story**: S-007
- **Priority**: P0 (blocker)
- **Depends on**: T-019
- **Files**: `src/skillforge/core/router.py`
- **Description**: Add attachment processing logic to `handle_message()`. Restructure the message-saving step: (1) process attachments first — check `files` permission via `_check_handler_permission(user_id, "files")`, if denied silently drop attachments; (2) save user message with attachment metadata via `session_manager.add_message(session_key, "user", user_message, metadata={"attachments": [a.to_dict() for a in stored_attachments]})`. After building the messages list and before calling `llm.chat()`: if `stored_attachments` is non-empty and `self.llm.supports_vision`, call `messages = self.llm.format_vision_messages(messages, stored_attachments)`. If `supports_vision` is `False`, append a fallback note to the last user message: "[The user sent an image, but the current model ({model_name}) does not support image analysis. Suggest switching to a vision-capable model.]". Apply identical logic to `handle_message_stream()`.
- **Acceptance criteria**:
  - With `attachments=None`, behavior is identical to current (backward compat)
  - With attachments + vision provider: `format_vision_messages` is called
  - With attachments + non-vision provider: fallback text appended to last user message
  - With attachments + no `files` permission: attachments silently dropped, text processed normally
  - Attachment metadata stored in JSONL via session manager
- **Est.**: 0.5 days

---

### Task T-021: Update sessions.py to propagate attachment references in history
- **Epic**: E-003
- **Story**: S-008
- **Priority**: P1 (critical)
- **Depends on**: T-020
- **Files**: `src/skillforge/core/sessions.py`
- **Description**: Update `get_conversation_history()` method. When building the messages list from JSONL entries, check for `entry.metadata.attachments`. If present, add `_attachments` key (underscore-prefixed to distinguish from standard fields) to the message dict. This enables the router to know about images in conversation history for multi-turn vision conversations. The `add_message()` method already accepts `metadata` dict, so no signature changes needed — just pass through correctly.
- **Acceptance criteria**:
  - Messages with attachments in JSONL include `_attachments` key in returned history
  - Messages without attachments have no `_attachments` key (not even `None`)
  - No changes to `add_message()` signature
  - Existing session tests pass unchanged
- **Est.**: 0.2 days

---

## E-004: Channel Inbound

Enable each channel (Telegram, WhatsApp, Flet UI) to receive images from users, validate them, and pass them to the router as Attachment objects.

### Story S-009: Telegram Receives Photos
*As a Telegram user, I want to send photos and images (as photos or document attachments) to the bot and have them analyzed by the LLM.*

### Story S-010: WhatsApp Receives Images
*As a WhatsApp user, I want to send images in chat and have the bot process them alongside my caption text.*

### Story S-011: Flet UI Image Upload
*As a desktop user, I want to attach images via a file picker, see thumbnails of pending attachments, and send them with my message.*

---

### Task T-022: Add Telegram photo message handler
- **Epic**: E-004
- **Story**: S-009
- **Priority**: P1 (critical)
- **Depends on**: T-020
- **Files**: `src/skillforge/channels/telegram.py`
- **Description**: In `initialize()`, register two new handlers: `MessageHandler(filters.PHOTO, self._handle_photo)` and `MessageHandler(filters.Document.IMAGE, self._handle_document_image)`. Implement `_handle_photo`: check authorization, get highest-resolution photo (`update.message.photo[-1]`), extract caption (default "What's in this image?"), download to temp file via `context.bot.get_file()` + `download_to_drive()`, call `ImageHandler.store_image()`, then call `_process_message()` with attachments. Clean up temp file in `finally` block. Implement `_handle_document_image` with same pattern but using `update.message.document`.
- **Acceptance criteria**:
  - Bot responds to photo messages (not just text)
  - Highest resolution photo variant is downloaded
  - Caption text is used as the user message
  - Default message used when no caption provided
  - Temp files cleaned up after processing
  - Invalid images produce user-friendly error message
  - Authorization check applied
- **Est.**: 0.4 days

---

### Task T-023: Update Telegram _process_message to accept attachments
- **Epic**: E-004
- **Story**: S-009
- **Priority**: P1 (critical)
- **Depends on**: T-022
- **Files**: `src/skillforge/channels/telegram.py`
- **Description**: Add `attachments: Optional[list] = None` parameter to `_process_message()`. Pass `attachments` through to `self.message_handler()` call. The message_handler is bound to `router.handle_message` or `router.handle_message_stream`, both of which now accept `attachments`.
- **Acceptance criteria**:
  - `_process_message` signature includes `attachments` parameter
  - Attachments are passed to message_handler
  - Existing text-only calls work unchanged (`attachments=None` default)
- **Est.**: 0.15 days

---

### Task T-024: Add WhatsApp image detection in webhook handler
- **Epic**: E-004
- **Story**: S-010
- **Priority**: P1 (critical)
- **Depends on**: T-020
- **Files**: `src/skillforge/channels/whatsapp.py`
- **Description**: Update `handle_incoming_webhook()` to detect image messages. Check `data.raw.message.imageMessage` for presence of an image. If present, call `_download_whatsapp_image()` to download the media and create an Attachment. Pass attachments to `self.message_handler()`.
- **Acceptance criteria**:
  - Image messages detected via `imageMessage` field in raw webhook data
  - Text-only messages continue to work unchanged
  - Attachments passed to message handler when image is present
- **Est.**: 0.2 days

---

### Task T-025: Implement WhatsApp image download method
- **Epic**: E-004
- **Story**: S-010
- **Priority**: P1 (critical)
- **Depends on**: T-024
- **Files**: `src/skillforge/channels/whatsapp.py`
- **Description**: Implement `_download_whatsapp_image(data, image_msg) -> Optional[list]`. Calls the Baileys service `/download-media` endpoint with `messageId` and `chatId`. Writes response bytes to a temp file. Validates and stores via `ImageHandler.store_image()`. Cleans up temp file. Returns list with single Attachment, or `None` on failure. All errors caught and logged (graceful fallback to text-only).
- **Acceptance criteria**:
  - Calls `/download-media` endpoint correctly
  - Temp file created and cleaned up
  - Returns list with Attachment on success
  - Returns `None` on any error (no crash)
  - Errors are logged
- **Est.**: 0.3 days

---

### Task T-026: Add Baileys download-media endpoint
- **Epic**: E-004
- **Story**: S-010
- **Priority**: P1 (critical)
- **Depends on**: none (can be done in parallel with Python work)
- **Files**: `whatsapp_service/server.js`
- **Description**: Add `POST /download-media` endpoint. Accepts `{ messageId, chatId }` in request body. Uses Baileys `downloadMediaMessage()` to download the media buffer. Returns the raw buffer as `application/octet-stream`. Returns 400 for missing params, 503 if not connected. Also update the `messages.upsert` webhook forwarding to include `hasImage: !!m.imageMessage` flag and `raw: msg` in the forwarded data.
- **Acceptance criteria**:
  - Endpoint returns raw image bytes on success
  - Returns 400 for missing messageId/chatId
  - Returns 503 when WhatsApp is not connected
  - Returns 500 with error message on download failure
  - Webhook data includes `hasImage` flag
- **Est.**: 0.3 days

---

### Task T-027: Add Flet UI file picker for images
- **Epic**: E-004
- **Story**: S-011
- **Priority**: P1 (critical)
- **Depends on**: T-020
- **Files**: `src/skillforge/flet/views/chat.py`
- **Description**: In `ChatView.build()`, create a `ft.FilePicker(on_result=self._on_file_picked)` and add to `page.overlay`. Add an attach button (`ft.IconButton` with `icons.ATTACH_FILE`) next to the send button. Add `_pending_attachments` list and `_attachment_preview` Row (hidden by default). Implement `_on_file_picked(e)`: for each selected file, call `ImageHandler.store_image()`, append to `_pending_attachments`, add a thumbnail preview (60x60 `ft.Image` in a `ft.Stack` with a close button). Implement `_remove_attachment(att)` to remove from pending list and preview. Update `_send_message()` to include `_pending_attachments` when calling the router, clear them after send. Update `_process_bot_response()` signature to accept `attachments` parameter and pass to `handle_message_stream()`.
- **Acceptance criteria**:
  - Attach button visible in chat input row
  - File picker filters to image extensions only (png, jpg, jpeg, gif, webp, bmp)
  - Selected images appear as thumbnails with remove buttons
  - Sending clears the attachment preview
  - Attachments passed to router's handle_message_stream
  - Invalid files show error message in chat
  - Sending with only images (no text) works with default message
- **Est.**: 0.5 days

---

### Task T-028: Add Flet UI image send without text
- **Epic**: E-004
- **Story**: S-011
- **Priority**: P2 (important)
- **Depends on**: T-027
- **Files**: `src/skillforge/flet/views/chat.py`
- **Description**: Update `_send_message` to allow sending when text is empty but attachments are present. Use "What's in this image?" as default message text. Show "[Image]" as the user message bubble text when no text was provided. Ensure `_is_processing` guard still works correctly.
- **Acceptance criteria**:
  - Can send images without typing any text
  - Default prompt "What's in this image?" used for LLM
  - User message bubble shows "[Image]" when no text
  - Cannot send when both text and attachments are empty
- **Est.**: 0.15 days

---

## E-005: Channel Outbound

Enable each channel to send images back to users — from LLM-generated images or other outbound image content.

### Story S-012: Telegram Sends Photos
*As a Telegram user, I want the bot to send me generated images or image results directly in the chat.*

### Story S-013: WhatsApp Sends Images
*As a WhatsApp user, I want the bot to send me images in the chat via the Baileys service.*

### Story S-014: Flet UI Displays Inline Images
*As a desktop user, I want to see images displayed inline in the chat conversation, both for images I sent and images the bot generates.*

---

### Task T-029: Implement Telegram send_photo method
- **Epic**: E-005
- **Story**: S-012
- **Priority**: P1 (critical)
- **Depends on**: T-022
- **Files**: `src/skillforge/channels/telegram.py`
- **Description**: Implement `send_photo(chat_id, photo_path, caption=None, update=None) -> bool`. If `update` is provided, use `update.message.reply_photo()`. Otherwise use `self.application.bot.send_photo()`. Open the file in binary mode, pass as `photo` parameter. Include optional caption with Markdown parse mode. Return `True` on success, `False` on error (logged).
- **Acceptance criteria**:
  - Sends photo as reply when update context available
  - Sends photo directly to chat_id when no update context
  - Caption is optional
  - Returns boolean success indicator
  - Errors logged, not raised
- **Est.**: 0.2 days

---

### Task T-030: Implement WhatsApp send_image method
- **Epic**: E-005
- **Story**: S-013
- **Priority**: P1 (critical)
- **Depends on**: T-025
- **Files**: `src/skillforge/channels/whatsapp.py`
- **Description**: Implement `send_image(to, image_path, caption=None) -> bool`. Read the image file, base64-encode it, POST to Baileys service `/send-media` endpoint with `{ chatId, image, caption }`. Return `True` on success (200 response), `False` on error.
- **Acceptance criteria**:
  - Sends base64-encoded image to Baileys service
  - Caption is optional
  - Returns boolean success indicator
  - Errors logged, not raised
- **Est.**: 0.2 days

---

### Task T-031: Add Baileys send-media endpoint
- **Epic**: E-005
- **Story**: S-013
- **Priority**: P1 (critical)
- **Depends on**: T-026
- **Files**: `whatsapp_service/server.js`
- **Description**: Add `POST /send-media` endpoint. Accepts `{ chatId, image, caption }` where `image` is a base64 string. Converts to Buffer, calls `sock.sendMessage(chatId, { image: buffer, caption })`. Returns `{ success: true, messageId }` on success. Returns 400 for missing params, 503 if not connected, 500 on error.
- **Acceptance criteria**:
  - Endpoint decodes base64 and sends image via Baileys
  - Caption is optional
  - Returns messageId on success
  - Proper error responses for all failure modes
- **Est.**: 0.2 days

---

### Task T-032: Update ChatMessage component to render inline images
- **Epic**: E-005
- **Story**: S-014
- **Priority**: P1 (critical)
- **Depends on**: T-027
- **Files**: `src/skillforge/flet/components/chat_message.py`
- **Description**: Update `ChatMessage.__init__` to accept `images: Optional[List[str]] = None` parameter. When images are provided, create `ft.Image` controls (width=300, height=200, `ft.ImageFit.CONTAIN`, border_radius=8) and insert them into the message column between the sender label and the text body. Images from file paths are displayed directly via `src=img_path`.
- **Acceptance criteria**:
  - `ChatMessage(text="hi", images=None)` renders identically to current behavior
  - `ChatMessage(text="hi", images=["/path/to/img.jpg"])` renders image above text
  - Multiple images render in sequence
  - Images have consistent sizing and rounded corners
  - Image paths work as `ft.Image.src`
- **Est.**: 0.25 days

---

### Task T-033: Wire outbound images from router response to channels
- **Epic**: E-005
- **Story**: S-012, S-013, S-014
- **Priority**: P2 (important)
- **Depends on**: T-029, T-030, T-032, T-042 (image gen handler)
- **Files**: `src/skillforge/channels/telegram.py`, `src/skillforge/channels/whatsapp.py`, `src/skillforge/flet/views/chat.py`
- **Description**: When the router returns a response that includes generated image paths (from image_gen handler results), each channel needs to send those images. For Telegram: after sending text reply, call `send_photo()` for each image. For WhatsApp: after sending text reply, call `send_image()` for each image. For Flet: pass image paths to `ChatMessage` via the `images` parameter. This requires the router to somehow communicate outbound images — either by embedding paths in the response text (e.g., `[IMAGE:/path/to/file.jpg]` markers) or by changing the return type. The simplest approach per plan.md is to embed image paths in the response text and have each channel extract them.
- **Acceptance criteria**:
  - Generated images are sent to users in all three channels
  - Text response is sent alongside (not replaced by) images
  - Image paths are extracted from response and handled per-channel
  - No images = current behavior unchanged
- **Est.**: 0.5 days

---

## E-006: Image Generation

Code-block handler for `\`\`\`image_gen\`\`\`` blocks that delegates to MCP tools or direct APIs for image generation.

### Story S-015: LLM Triggers Image Generation
*As a user, when I ask the bot to generate an image, the LLM emits an image_gen code block that is parsed and executed to produce an image.*

### Story S-016: Image Generation Error Handling
*As a user, when image generation fails (no provider configured, API error), I want a clear error message rather than a crash.*

---

### Task T-034: Create image_gen_handler.py module
- **Epic**: E-006
- **Story**: S-015
- **Priority**: P1 (critical)
- **Depends on**: T-001
- **Files**: `src/skillforge/core/image_gen_handler.py` (new)
- **Description**: Create `ImageGenHandler` class following the `schedule_handler.py` pattern exactly. Define `IMAGE_GEN_BLOCK_PATTERN` regex for matching `\`\`\`image_gen\`\`\`` blocks. Implement: `has_image_gen_commands(response)` returns bool, `parse_block(block_content)` parses KEY: VALUE pairs (ACTION, PROMPT, PROVIDER, SIZE, STYLE, QUALITY, MODEL, NEGATIVE_PROMPT), `extract_commands(response)` returns list of parsed command dicts, `execute_commands(response, channel, user_id, session_key)` processes all blocks and returns `(cleaned_response, results_list)`. Implement `_handle_generate(cmd, session_key)` — tries MCP tool first, falls back to error. Implement `_format_results(results)` — formats success/error for display. Include `create_image_gen_handler(mcp_manager=None)` factory function.
- **Acceptance criteria**:
  - Regex correctly matches image_gen code blocks
  - Block parsing extracts all supported keys
  - Commands extracted from multi-block responses
  - Code blocks stripped from cleaned response
  - Results appended as formatted text
  - MCP integration attempted when manager available
  - Clear error when no provider available
- **Est.**: 0.5 days

---

### Task T-035: Wire image_gen handler into router
- **Epic**: E-006
- **Story**: S-015
- **Priority**: P1 (critical)
- **Depends on**: T-034, T-020
- **Files**: `src/skillforge/core/router.py`
- **Description**: In router `__init__`, import and initialize `ImageGenHandler`. Wire `set_mcp_manager()` when MCP manager is available. In both `handle_message` and `handle_message_stream`, add a new section (7.9) after web commands: check `_image_gen_handler.has_image_gen_commands(clean_response)`, verify `files` permission, execute commands, update `clean_response`. Renumber existing section 7.9 to 7.10.
- **Acceptance criteria**:
  - image_gen blocks in LLM response are detected and processed
  - Permission check applied (files permission required)
  - Permission denied produces clear error message
  - Code blocks stripped from final response
  - Results appended to response
  - Non-image-gen responses unchanged
- **Est.**: 0.3 days

---

### Task T-036: Add image generation capability hint to system prompt
- **Epic**: E-006
- **Story**: S-015
- **Priority**: P2 (important)
- **Depends on**: T-035
- **Files**: `src/skillforge/core/router.py`
- **Description**: Update `_build_capability_hints(user_id)` to include image generation instructions when the user has `files` permission. Add a hint explaining the `\`\`\`image_gen\`\`\`` code block format (ACTION, PROMPT, PROVIDER, SIZE fields) so the LLM knows to use it when asked to generate images.
- **Acceptance criteria**:
  - System prompt includes image_gen instructions when files permission is granted
  - Instructions omitted when files permission is denied
  - Existing capability hints unchanged
- **Est.**: 0.15 days

---

### Task T-037: Add vision capability hint to system prompt
- **Epic**: E-006
- **Story**: S-015
- **Priority**: P2 (important)
- **Depends on**: T-020
- **Files**: `src/skillforge/core/router.py`
- **Description**: Update system prompt building to include a note about vision capabilities when the active LLM supports vision. Something like: "You can analyze images sent by the user. Describe what you see in detail." This helps the LLM understand it should respond to images rather than saying "I cannot see images."
- **Acceptance criteria**:
  - Vision hint included in system prompt when `llm.supports_vision` is `True`
  - No hint when `supports_vision` is `False`
  - Hint phrasing encourages detailed image analysis
- **Est.**: 0.1 days

---

## E-007: Testing

Test files written alongside each epic. Grouped here for overview, but each test task should be done immediately after (or during) its corresponding implementation task.

### Story S-017: Image Handler Unit Tests
*Tests for image validation, storage, cleanup, sanitization, and base64 encoding.*

### Story S-018: Vision Provider Unit Tests
*Tests for each provider's vision message formatting and supports_vision flags.*

### Story S-019: Image Generation Handler Tests
*Tests for image_gen block parsing, execution, and result formatting.*

### Story S-020: Integration Tests
*End-to-end tests for the image flow through the router with mocked providers.*

---

### Task T-038: Write test_image_handler.py
- **Epic**: E-007
- **Story**: S-017
- **Priority**: P0 (blocker)
- **Depends on**: T-007 (all of E-001 complete)
- **Files**: `tests/test_image_handler.py` (new)
- **Description**: Write comprehensive unit tests for `ImageHandler`. Create test image files (minimal valid PNG, JPEG, GIF, WEBP, BMP using magic bytes). Tests (~26 tests):
  - Validation: valid formats (5), reject SVG, reject exe-renamed-to-jpg, reject too large, reject empty, reject missing, magic byte mismatch
  - Sanitization: strips directory, removes null bytes, replaces special chars, dotfile handling, truncation
  - Storage: creates directory, copies file, returns correct Attachment, rejects invalid
  - Base64: small image encoding, large image resize (with Pillow mock)
  - Serialization: `to_dict()` and `from_dict()` round-trip
  - Cleanup: evicts oldest, no-op under limit, storage usage calculation
- **Acceptance criteria**:
  - All tests pass with `python -m pytest tests/test_image_handler.py -v`
  - Tests use `tmp_path` fixture for isolation
  - No real image files required (create minimal valid files programmatically)
  - ~26 tests minimum
- **Est.**: 0.5 days

---

### Task T-039: Write test_vision_providers.py
- **Epic**: E-007
- **Story**: S-018
- **Priority**: P0 (blocker)
- **Depends on**: T-009, T-010, T-011, T-012, T-013, T-014
- **Files**: `tests/test_vision_providers.py` (new)
- **Description**: Write unit tests for vision support across all providers (~21 tests):
  - Base class: default `supports_vision` is False, default `format_vision_messages` is no-op
  - OpenAI: `supports_vision` True, single image format, multiple images, no attachments no-op, no user message no-op
  - Anthropic: `supports_vision` True, single image format, message structure (images before text)
  - Gemini: `supports_vision` True, single image format, `_convert_messages` with list content
  - Claude CLI: `supports_vision` False
  - Gemini CLI: `supports_vision` False
  - llama.cpp: `supports_vision` default False, configurable True
  - Router integration: vision flow with mock provider, no-vision fallback message, attachments=None backward compat, permission denied drops attachments

  Use mock Attachment objects and mock `ImageHandler.encode_base64()` to avoid needing real image files.
- **Acceptance criteria**:
  - All tests pass with `python -m pytest tests/test_vision_providers.py -v`
  - Provider format tests verify exact API payload structure
  - Router integration tests use mock LLM provider
  - ~21 tests minimum
- **Est.**: 0.5 days

---

### Task T-040: Write test_image_gen_handler.py
- **Epic**: E-007
- **Story**: S-019
- **Priority**: P1 (critical)
- **Depends on**: T-034
- **Files**: `tests/test_image_gen_handler.py` (new)
- **Description**: Write unit tests for `ImageGenHandler` (~8 tests):
  - `has_image_gen_commands`: true with block, false without
  - `parse_block`: basic key-value, multiline prompt
  - `extract_commands`: multiple blocks in one response
  - `execute_commands`: no provider available error
  - `_format_results`: success formatting, error formatting
- **Acceptance criteria**:
  - All tests pass with `python -m pytest tests/test_image_gen_handler.py -v`
  - Tests do not require MCP or external services
  - ~8 tests minimum
- **Est.**: 0.25 days

---

### Task T-041: Add image integration tests to test_integration_chat.py
- **Epic**: E-007
- **Story**: S-020
- **Priority**: P1 (critical)
- **Depends on**: T-020, T-039
- **Files**: `tests/test_integration_chat.py`
- **Description**: Add new test cases to the existing integration test file (~4 tests):
  - `test_handle_message_with_attachment`: send message with mock attachment to vision-capable mock provider, verify format_vision_messages called
  - `test_handle_message_stream_with_attachment`: same for streaming
  - `test_handle_message_attachment_no_vision`: send attachment to non-vision provider, verify fallback message appended
  - `test_handle_message_attachment_permission_denied`: send attachment with restricted user, verify attachment dropped

  Use existing test fixtures (router with mock LLM). Create mock Attachment objects. Override `_permission_manager` per project conventions.
- **Acceptance criteria**:
  - All 4 new tests pass
  - All existing tests continue to pass (backward compat verified)
  - Tests run within the existing integration test framework
- **Est.**: 0.4 days

---

### Task T-042: Write channel-specific image tests
- **Epic**: E-007
- **Story**: S-020
- **Priority**: P2 (important)
- **Depends on**: T-022, T-024, T-027
- **Files**: `tests/test_image_handler.py` or new `tests/test_channel_images.py`
- **Description**: Write tests verifying channel image handling. For Telegram: mock `Update` with photo, verify `_handle_photo` downloads and passes attachment. For WhatsApp: mock webhook data with imageMessage, verify download attempted. For Flet: verify file picker callback creates Attachment. These can be lightweight smoke tests since the heavy logic is in ImageHandler and router (already tested).
- **Acceptance criteria**:
  - At least 1 test per channel (3 minimum)
  - Tests use mocks for external dependencies (Telegram API, aiohttp, file system)
  - All tests pass
- **Est.**: 0.3 days

---

### Task T-043: Update test_imports.py for new modules
- **Epic**: E-007
- **Story**: S-020
- **Priority**: P2 (important)
- **Depends on**: T-001, T-034
- **Files**: `tests/test_imports.py`
- **Description**: Add import smoke tests for the two new modules: `skillforge.core.image_handler` and `skillforge.core.image_gen_handler`. Verify that `Attachment`, `ImageHandler`, `ImageGenHandler` are importable.
- **Acceptance criteria**:
  - Import tests pass for both new modules
  - Existing import tests unchanged
- **Est.**: 0.05 days

---

### Task T-044: Run full test suite and fix regressions
- **Epic**: E-007
- **Story**: S-020
- **Priority**: P0 (blocker)
- **Depends on**: T-038, T-039, T-040, T-041
- **Files**: (any files that need fixes)
- **Description**: Run the complete test suite (`python -m pytest tests/ -v`). Verify all ~989+ existing tests still pass. Fix any regressions caused by signature changes, import additions, or router restructuring. Pay special attention to: router tests (signature change), integration tests (message flow), Flet app tests (new controls). This is a gate — all tests must pass before E-008.
- **Acceptance criteria**:
  - All existing tests pass (989+)
  - All new tests pass
  - Zero regressions
  - `python -m pytest tests/ -v` exits with code 0
- **Est.**: 0.5 days

---

## E-008: Documentation

Update all project documentation to reflect the new image/vision feature.

### Story S-021: Documentation Updates
*As a developer or user reading the docs, I need the changelog, project structure docs, and todo list updated to reflect the new image/vision capabilities.*

---

### Task T-045: Update CHANGELOG.md
- **Epic**: E-008
- **Story**: S-021
- **Priority**: P2 (important)
- **Depends on**: T-044
- **Files**: `CHANGELOG.md`
- **Description**: Add a new entry documenting the image/vision feature. Include: new modules created, LLM providers with vision support, channel image support (Telegram, WhatsApp, Flet), image generation handler, security features (magic byte validation, filename sanitization, storage limits).
- **Acceptance criteria**:
  - Entry dated correctly
  - All major additions listed
  - Follows existing changelog format
- **Est.**: 0.15 days

---

### Task T-046: Update read_me_claude.md
- **Epic**: E-008
- **Story**: S-021
- **Priority**: P2 (important)
- **Depends on**: T-044
- **Files**: `read_me_claude.md`
- **Description**: Update project structure section to include `image_handler.py` and `image_gen_handler.py`. Add Image/Vision section documenting: Attachment dataclass, ImageHandler, vision provider support matrix, image_gen handler pattern, security architecture. Update test count. Update doc index if present.
- **Acceptance criteria**:
  - New files listed in project structure
  - Image/Vision section added with key details
  - Test count updated
  - Doc index updated
- **Est.**: 0.2 days

---

### Task T-047: Update docs/todo.md
- **Epic**: E-008
- **Story**: S-021
- **Priority**: P3 (nice-to-have)
- **Depends on**: T-044
- **Files**: `docs/todo.md`
- **Description**: Mark image/vision feature items as completed. Add any follow-up items discovered during implementation (e.g., multi-turn vision context, per-model vision detection, video support as future work).
- **Acceptance criteria**:
  - Completed items marked done with date
  - Follow-up items added to backlog section
- **Est.**: 0.1 days

---

## Summary & Estimates

### Task Count by Priority

| Priority | Count | Description |
|----------|-------|-------------|
| P0 (blocker) | 15 | Must be done, blocks other work |
| P1 (critical) | 19 | Core functionality, must ship |
| P2 (important) | 11 | Should ship, but not blocking |
| P3 (nice-to-have) | 2 | Can defer if needed |
| **Total** | **47** | |

### Task Count by Epic

| Epic | P0 | P1 | P2 | P3 | Total |
|------|----|----|----|----|-------|
| E-001 Core Image Infrastructure | 5 | 1 | 1 | 0 | 7 |
| E-002 LLM Provider Vision Support | 1 | 1 | 5 | 0 | 7 (+2 shared with E-001) |
| E-003 Router Integration | 3 | 1 | 0 | 0 | 4 (+1 from session) |
| E-004 Channel Inbound | 0 | 6 | 1 | 0 | 7 |
| E-005 Channel Outbound | 0 | 3 | 1 | 0 | 4 (+1 cross-channel) |
| E-006 Image Generation | 0 | 2 | 2 | 0 | 4 |
| E-007 Testing | 2 | 2 | 3 | 0 | 7 |
| E-008 Documentation | 0 | 0 | 2 | 1 | 3 |

### Estimated Timeline (single developer)

| Phase | Epics | Days | Cumulative |
|-------|-------|------|------------|
| Phase 1: Foundation | E-001 | 2.0 | 2.0 |
| Phase 2: Provider + Router (parallel) | E-002 + E-003 | 2.5 | 4.5 |
| Phase 3: Channels In | E-004 | 2.5 | 7.0 |
| Phase 4: Channels Out + Gen | E-005 + E-006 | 2.0 | 9.0 |
| Phase 5: Testing & Polish | E-007 (remaining) | 2.5 | 11.5 |
| Phase 6: Docs | E-008 | 0.5 | 12.0 |
| **Buffer (15%)** | | 1.8 | **13.8** |

**Note:** E-007 testing tasks should be done alongside their corresponding implementation tasks, not deferred to Phase 5. Phase 5 covers final integration testing, regression checking, and any test gaps.

### Files Changed Summary

| File | Type | Epic |
|------|------|------|
| `src/skillforge/core/image_handler.py` | NEW (~300 lines) | E-001 |
| `src/skillforge/core/image_gen_handler.py` | NEW (~180 lines) | E-006 |
| `src/skillforge/core/llm/base.py` | Modify (+25 lines) | E-002 |
| `src/skillforge/core/llm/openai_compat.py` | Modify (+45 lines) | E-002 |
| `src/skillforge/core/llm/anthropic_provider.py` | Modify (+45 lines) | E-002 |
| `src/skillforge/core/llm/gemini_provider.py` | Modify (+60 lines) | E-002 |
| `src/skillforge/core/llm/claude_cli_provider.py` | Modify (+5 lines) | E-002 |
| `src/skillforge/core/llm/gemini_cli_provider.py` | Modify (+5 lines) | E-002 |
| `src/skillforge/core/llm/llamacpp_provider.py` | Modify (+5 lines) | E-002 |
| `src/skillforge/core/router.py` | Modify (+60 lines) | E-003, E-006 |
| `src/skillforge/core/sessions.py` | Modify (+5 lines) | E-003 |
| `src/skillforge/channels/telegram.py` | Modify (+80 lines) | E-004, E-005 |
| `src/skillforge/channels/whatsapp.py` | Modify (+60 lines) | E-004, E-005 |
| `whatsapp_service/server.js` | Modify (+50 lines) | E-004, E-005 |
| `src/skillforge/flet/views/chat.py` | Modify (+70 lines) | E-004, E-005 |
| `src/skillforge/flet/components/chat_message.py` | Modify (+20 lines) | E-005 |
| `pyproject.toml` | Modify (+3 lines) | E-002 |
| `tests/test_image_handler.py` | NEW (~400 lines) | E-007 |
| `tests/test_vision_providers.py` | NEW (~350 lines) | E-007 |
| `tests/test_image_gen_handler.py` | NEW (~150 lines) | E-007 |
| `tests/test_integration_chat.py` | Modify (+80 lines) | E-007 |
| `tests/test_imports.py` | Modify (+5 lines) | E-007 |
| `CHANGELOG.md` | Modify | E-008 |
| `read_me_claude.md` | Modify | E-008 |
| `docs/todo.md` | Modify | E-008 |

### Critical Path

The longest dependency chain determines minimum calendar time:

```
T-001 -> T-002 -> T-003 -> T-005 -> T-019 -> T-020 -> T-022 -> T-029 -> T-033 -> T-044
(0.25)   (0.25)   (0.25)   (0.25)   (0.1)    (0.5)    (0.4)    (0.2)    (0.5)    (0.5)
                                                                          = 3.2 days critical path
```

With parallelization (E-002 alongside E-003, providers in parallel, channels in parallel), the effective timeline is approximately 12-14 days for a single developer.

### Risk Items to Monitor

1. **Gemini `_convert_messages` changes** (T-011) — Most complex provider change; list content handling needs careful testing
2. **Anthropic `_prepare_request` verification** (T-015) — Must confirm no string coercion; a subtle bug here fails silently
3. **WhatsApp Baileys media API** (T-026) — External dependency; API may differ from plan's assumptions
4. **Outbound image wiring** (T-033) — Cross-cutting concern touching all channels; design decision on how router communicates image paths back to channels
5. **Full regression suite** (T-044) — 989+ existing tests must still pass after all changes
