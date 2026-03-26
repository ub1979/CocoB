# Image/Vision Support — Implementation Plan

**Date:** 2026-03-19
**Status:** Ready for implementation
**Requirements source:** `requirements.md`

---

## 1. Architecture Overview

### 1.1 Image Flow Diagram

```
INBOUND (User sends image):

  Telegram         WhatsApp (Baileys)       Flet UI
  photo handler    image message             file picker
       |                |                       |
       v                v                       v
  Download to      Download via             Read from
  temp file        /download-media          local path
       |                |                       |
       +--------+-------+-----------+-----------+
                |
                v
        ImageHandler.validate_and_store()
          - magic byte validation
          - filename sanitization
          - resize if >4MB
          - save to data/images/{session_key}/{ts}_{name}
          - return Attachment dataclass
                |
                v
        Router.handle_message(attachments=[Attachment, ...])
        Router.handle_message_stream(attachments=[Attachment, ...])
          - store image ref in JSONL via sessions
          - check provider.supports_vision
          - if yes: provider.format_vision_messages(messages, attachments)
          - if no:  append "image received but model can't analyze" text
          - call llm.chat() / llm.chat_stream() with formatted messages
                |
                v
          LLM response (text only — or with image_gen block)


OUTBOUND (LLM generates image):

  LLM response contains ```image_gen``` block
       |
       v
  ImageGenHandler.execute_commands()
    - parse ACTION, PROMPT, PROVIDER, SIZE, etc.
    - delegate to MCP tool or direct API
    - download result to data/images/generated/{ts}_{name}
    - return cleaned response + image path
       |
       v
  Router returns (text, outbound_images=[path])
       |
       +--------+-----------+-----------+
       |                    |           |
       v                    v           v
  Telegram               WhatsApp    Flet UI
  send_photo()           /send        ft.Image
                         +media
```

### 1.2 Data Types

```python
# New file: src/skillforge/core/image_handler.py

@dataclass
class Attachment:
    """Represents a validated, stored image attachment."""
    file_path: str          # Absolute path to stored image (e.g., data/images/session/ts_name.jpg)
    original_filename: str  # Original user-provided filename
    mime_type: str          # e.g., "image/png", "image/jpeg"
    size_bytes: int         # File size in bytes
    width: Optional[int]    # Image width (if decoded), None if not read
    height: Optional[int]   # Image height (if decoded), None if not read
```

---

## 2. New Module: `src/skillforge/core/image_handler.py`

### 2.1 Purpose

Central image validation, storage, cleanup, and base64 encoding. All channels and the router use this module instead of implementing their own image logic.

### 2.2 Full Module Design

```python
"""
Image handler — validation, storage, cleanup, base64 encoding.
"""

import base64
import hashlib
import io
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

logger = logging.getLogger("image_handler")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "image/png":  [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif":  [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],          # first 4 bytes; bytes 8-12 == b"WEBP"
    "image/bmp":  [b"BM"],
}

EXTENSION_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

MAX_IMAGE_SIZE = 20 * 1024 * 1024          # 20 MB (FR-1.4)
LLM_MAX_SIZE = 4 * 1024 * 1024             # 4 MB — resize above this (NFR-1)
DEFAULT_STORAGE_LIMIT = 1 * 1024**3         # 1 GB (FR-4.2)
SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9_.\-]')


# ---------------------------------------------------------------------------
# Attachment dataclass
# ---------------------------------------------------------------------------

@dataclass
class Attachment:
    """Represents a validated, stored image attachment."""
    file_path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> dict:
        """Serialize for JSONL storage (no base64 — just references)."""
        return {
            "file_path": self.file_path,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Attachment":
        return cls(
            file_path=d["file_path"],
            original_filename=d["original_filename"],
            mime_type=d["mime_type"],
            size_bytes=d["size_bytes"],
            width=d.get("width"),
            height=d.get("height"),
        )


# ---------------------------------------------------------------------------
# ImageHandler class
# ---------------------------------------------------------------------------

class ImageHandler:
    """Image validation, storage, and encoding."""

    def __init__(self, data_dir: str = "data/images",
                 max_storage_bytes: int = DEFAULT_STORAGE_LIMIT):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_storage_bytes = max_storage_bytes

    # -- Validation ---------------------------------------------------------

    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Validate an image file. Returns (ok, error_message)."""
        path = Path(file_path)
        if not path.exists():
            return False, "File does not exist"
        if not path.is_file():
            return False, "Path is not a file"

        size = path.stat().st_size
        if size > MAX_IMAGE_SIZE:
            return False, f"File too large ({size / 1024 / 1024:.1f} MB, max 20 MB)"
        if size == 0:
            return False, "File is empty"

        # Extension check
        ext = path.suffix.lower()
        if ext not in EXTENSION_TO_MIME:
            return False, f"Unsupported format: {ext}"

        # Magic byte check
        expected_mime = EXTENSION_TO_MIME[ext]
        ok, detected_mime = self._check_magic_bytes(path)
        if not ok:
            return False, f"File content does not match {ext} format (magic bytes mismatch)"

        # Extra WEBP check: bytes 8-12 must be b"WEBP"
        if expected_mime == "image/webp":
            with open(path, "rb") as f:
                header = f.read(12)
            if len(header) < 12 or header[8:12] != b"WEBP":
                return False, "Invalid WEBP file (missing WEBP signature)"

        return True, ""

    def _check_magic_bytes(self, path: Path) -> Tuple[bool, Optional[str]]:
        """Check file magic bytes against known signatures."""
        try:
            with open(path, "rb") as f:
                header = f.read(12)
        except OSError:
            return False, None

        for mime, signatures in ALLOWED_MIME_TYPES.items():
            for sig in signatures:
                if header[:len(sig)] == sig:
                    return True, mime
        return False, None

    def detect_mime_type(self, file_path: str) -> Optional[str]:
        """Detect MIME type from magic bytes."""
        _, mime = self._check_magic_bytes(Path(file_path))
        return mime

    # -- Filename sanitization -----------------------------------------------

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename: remove path components, dangerous chars."""
        # Strip directory components (path traversal prevention)
        name = Path(filename).name
        # Remove null bytes
        name = name.replace("\x00", "")
        # Replace unsafe chars
        name = SAFE_FILENAME_RE.sub("_", name)
        # Ensure non-empty
        if not name or name.startswith("."):
            name = "image" + name
        # Truncate to 200 chars
        if len(name) > 200:
            stem, ext = os.path.splitext(name)
            name = stem[:200 - len(ext)] + ext
        return name

    # -- Storage -------------------------------------------------------------

    def store_image(self, source_path: str, session_key: str,
                    original_filename: Optional[str] = None) -> Attachment:
        """
        Validate and store an image.

        Args:
            source_path: Path to the source image file.
            session_key: Session key for directory organization.
            original_filename: Original filename (for display). Uses source basename if None.

        Returns:
            Attachment dataclass.

        Raises:
            ValueError: If validation fails.
        """
        ok, error = self.validate_file(source_path)
        if not ok:
            raise ValueError(f"Image validation failed: {error}")

        src = Path(source_path)
        orig_name = original_filename or src.name
        safe_name = self.sanitize_filename(orig_name)

        # Detect MIME type from actual content
        mime = self.detect_mime_type(source_path) or EXTENSION_TO_MIME.get(src.suffix.lower(), "image/png")

        # Sanitize session_key for directory name
        safe_session = SAFE_FILENAME_RE.sub("_", session_key)

        # Build destination: data/images/{safe_session}/{timestamp}_{safe_name}
        dest_dir = self.data_dir / safe_session
        dest_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        dest_file = dest_dir / f"{ts}_{safe_name}"

        # Copy file to storage
        shutil.copy2(str(src), str(dest_file))

        size = dest_file.stat().st_size

        return Attachment(
            file_path=str(dest_file),
            original_filename=orig_name,
            mime_type=mime,
            size_bytes=size,
        )

    # -- Base64 encoding (lazy — only when sending to LLM) -------------------

    def encode_base64(self, file_path: str, max_size: int = LLM_MAX_SIZE) -> str:
        """
        Read image and return base64 string. Resize if larger than max_size.

        Args:
            file_path: Path to image.
            max_size: Max bytes before resizing. Default 4 MB.

        Returns:
            Base64-encoded string.
        """
        path = Path(file_path)
        data = path.read_bytes()

        if len(data) > max_size:
            data = self._resize_image_bytes(data, max_size)

        return base64.b64encode(data).decode("ascii")

    def _resize_image_bytes(self, data: bytes, max_size: int) -> bytes:
        """Resize image bytes to fit within max_size. Requires Pillow."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            # Iteratively reduce quality/size
            for quality in [85, 70, 50, 30]:
                buf = io.BytesIO()
                fmt = img.format or "JPEG"
                if fmt.upper() == "PNG":
                    # Convert PNG to JPEG for size reduction
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    fmt = "JPEG"
                img.save(buf, format=fmt, quality=quality, optimize=True)
                if buf.tell() <= max_size:
                    return buf.getvalue()

            # If still too large, reduce dimensions
            factor = 0.75
            while factor > 0.1:
                new_size = (int(img.width * factor), int(img.height * factor))
                resized = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=70, optimize=True)
                if buf.tell() <= max_size:
                    return buf.getvalue()
                factor -= 0.15

            # Last resort: return as-is
            return data

        except ImportError:
            logger.warning("Pillow not installed — cannot resize image. Sending full size.")
            return data

    # -- Cleanup (oldest-first eviction) ------------------------------------

    def get_storage_usage(self) -> int:
        """Get total bytes used by stored images."""
        total = 0
        for f in self.data_dir.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    def cleanup_if_needed(self):
        """Evict oldest images if storage exceeds limit."""
        usage = self.get_storage_usage()
        if usage <= self.max_storage_bytes:
            return

        # Collect all image files sorted oldest-first
        files = []
        for f in self.data_dir.rglob("*"):
            if f.is_file():
                files.append((f.stat().st_mtime, f))
        files.sort(key=lambda x: x[0])  # oldest first

        # Delete until under limit
        for mtime, f in files:
            if usage <= self.max_storage_bytes:
                break
            size = f.stat().st_size
            try:
                f.unlink()
                usage -= size
                logger.info(f"Evicted old image: {f.name} ({size} bytes)")
            except OSError:
                pass
```

### 2.3 Key Design Decisions

- **Magic bytes, not just extension.** The `_check_magic_bytes` method reads the first 12 bytes and compares against known signatures. WEBP gets an additional check at bytes 8-12.
- **No SVG allowed.** SVG is explicitly excluded from `ALLOWED_MIME_TYPES` because it can contain executable scripts.
- **Lazy base64 encoding.** Images are stored as files. Base64 encoding only happens at the moment of sending to the LLM API. This avoids bloating JSONL or memory.
- **Pillow optional.** Resizing requires Pillow (`PIL`). If not installed, full-size images are sent with a warning log. This avoids adding a hard dependency.
- **Filename sanitization:** Strips directory components first (`Path.name`), then replaces any non-alphanumeric character (except `_`, `.`, `-`) with `_`. Null bytes are removed. Names starting with `.` get `image` prepended. Truncated to 200 chars.

---

## 3. LLM Provider Changes

### 3.1 `base.py` — Add Vision Interface

**File:** `src/skillforge/core/llm/base.py`

**Changes:**

1. Add import: `from skillforge.core.image_handler import Attachment` (inside `TYPE_CHECKING` guard to avoid circular imports).

2. Add to `LLMProvider` class:

```python
@property
def supports_vision(self) -> bool:
    """Whether this provider supports image/vision input.
    Override in subclasses that support vision."""
    return False

def format_vision_messages(
    self,
    messages: List[Dict[str, Any]],
    attachments: List["Attachment"],
) -> List[Dict[str, Any]]:
    """Format messages with image attachments for this provider's API.

    Default implementation: no-op (returns messages unchanged).
    Vision-capable providers MUST override this.

    Args:
        messages: Standard message list (role/content dicts).
        attachments: List of Attachment objects to include with the
                     latest user message.

    Returns:
        Modified messages list with provider-specific image format.
    """
    return messages
```

3. No changes to `chat()`, `chat_stream()`, `estimate_tokens()`, or `check_context_size()` signatures. The router handles calling `format_vision_messages` before passing messages to `chat()`/`chat_stream()`.

### 3.2 `openai_compat.py` — OpenAI Vision Format

**File:** `src/skillforge/core/llm/openai_compat.py`

**Changes:**

1. Add import (under TYPE_CHECKING):
```python
if TYPE_CHECKING:
    from skillforge.core.image_handler import Attachment
```

2. Add property and method to `OpenAICompatibleProvider`:

```python
@property
def supports_vision(self) -> bool:
    return True  # Most OpenAI-compat APIs support vision with vision models

def format_vision_messages(
    self,
    messages: List[Dict[str, Any]],
    attachments: List["Attachment"],
) -> List[Dict[str, Any]]:
    """Format with OpenAI vision content blocks.

    Converts the last user message from:
        {"role": "user", "content": "describe this"}
    To:
        {"role": "user", "content": [
            {"type": "text", "text": "describe this"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]}
    """
    if not attachments:
        return messages

    from skillforge.core.image_handler import ImageHandler
    handler = ImageHandler()

    # Find last user message index
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx is None:
        return messages

    result = [m.copy() for m in messages]
    user_msg = result[last_user_idx]
    text = user_msg.get("content", "")

    content_parts = [{"type": "text", "text": text}]
    for att in attachments:
        b64 = handler.encode_base64(att.file_path)
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{att.mime_type};base64,{b64}"
            }
        })

    result[last_user_idx] = {"role": "user", "content": content_parts}
    return result
```

**API payload produced (OpenAI format):**
```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": [
      {"type": "text", "text": "What's in this image?"},
      {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64,/9j/4AAQ..."
      }}
    ]}
  ]
}
```

### 3.3 `anthropic_provider.py` — Anthropic Vision Format

**File:** `src/skillforge/core/llm/anthropic_provider.py`

**Changes:**

1. Add property and method to `AnthropicProvider`:

```python
@property
def supports_vision(self) -> bool:
    return True

def format_vision_messages(
    self,
    messages: List[Dict[str, Any]],
    attachments: List["Attachment"],
) -> List[Dict[str, Any]]:
    """Format with Anthropic vision content blocks.

    Converts last user message content to:
        [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}},
            {"type": "text", "text": "describe this"}
        ]
    """
    if not attachments:
        return messages

    from skillforge.core.image_handler import ImageHandler
    handler = ImageHandler()

    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx is None:
        return messages

    result = [m.copy() for m in messages]
    user_msg = result[last_user_idx]
    text = user_msg.get("content", "")

    content_parts = []
    for att in attachments:
        b64 = handler.encode_base64(att.file_path)
        content_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": att.mime_type,
                "data": b64,
            }
        })
    content_parts.append({"type": "text", "text": text})

    result[last_user_idx] = {"role": "user", "content": content_parts}
    return result
```

**API payload produced (Anthropic format):**
```json
{
  "model": "claude-sonnet-4-20250514",
  "system": "...",
  "messages": [
    {"role": "user", "content": [
      {"type": "image", "source": {
        "type": "base64",
        "media_type": "image/jpeg",
        "data": "/9j/4AAQ..."
      }},
      {"type": "text", "text": "What's in this image?"}
    ]}
  ]
}
```

**Important note for `_prepare_request`:** The existing `_prepare_request` method currently assumes `content` is always a string. When `format_vision_messages` has been called, the content for user messages may be a list. The `_prepare_request` method needs a small change: when building `chat_messages`, pass the `content` through as-is (string or list) instead of always treating it as a string:

```python
# In _prepare_request, change:
chat_messages.append({
    "role": anthropic_role,
    "content": content  # This already works — content is whatever msg["content"] is
})
```

Review of existing code shows `content = msg.get("content", "")` — this will return the list if content is a list. And the append just passes it through. So **no change needed** to `_prepare_request` — it already handles this correctly by passing content as-is.

### 3.4 `gemini_provider.py` — Gemini Vision Format

**File:** `src/skillforge/core/llm/gemini_provider.py`

**Changes:**

1. Add property and method to `GeminiProvider`:

```python
@property
def supports_vision(self) -> bool:
    return True

def format_vision_messages(
    self,
    messages: List[Dict[str, Any]],
    attachments: List["Attachment"],
) -> List[Dict[str, Any]]:
    """Format with Gemini inline_data parts.

    Gemini uses parts arrays. The _convert_messages method reads
    msg["content"]. We convert the last user message's content to
    a list of parts dicts that _convert_messages will pass through.

    After this transform, content becomes:
        [
            {"inline_data": {"mime_type": "image/jpeg", "data": "base64..."}},
            "describe this"
        ]
    """
    if not attachments:
        return messages

    from skillforge.core.image_handler import ImageHandler
    handler = ImageHandler()

    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    if last_user_idx is None:
        return messages

    result = [m.copy() for m in messages]
    user_msg = result[last_user_idx]
    text = user_msg.get("content", "")

    parts = []
    for att in attachments:
        b64 = handler.encode_base64(att.file_path)
        parts.append({
            "inline_data": {
                "mime_type": att.mime_type,
                "data": b64,
            }
        })
    parts.append(text)

    result[last_user_idx] = {"role": "user", "content": parts}
    return result
```

**Additionally, `_convert_messages` must be updated** to handle the case where `content` is a list (the Gemini parts format) instead of a string:

```python
# In _convert_messages, change the user message handling:
elif role == "user":
    if current_message is not None:
        history.append(current_message)
    # content can be a string or a list of parts (vision)
    if isinstance(content, list):
        # Vision message: content is already a list of parts
        current_message = {"role": "user", "parts": content}
    else:
        current_message = {"role": "user", "parts": [content]}
```

And similarly for assistant messages:
```python
elif role == "assistant":
    if isinstance(content, list):
        history.append({"role": "model", "parts": content})
    else:
        history.append({"role": "model", "parts": [content]})
```

**Also update `_chat_genai` and `_stream_genai`** (and vertex variants): when `current_message["parts"]` is a list of dicts, pass the full parts list to `send_message` instead of `parts[0]`:

```python
# Change from:
response = chat.send_message(current_message["parts"][0], ...)
# To:
parts = current_message["parts"]
# If single text string, send directly; if multi-part (vision), send list
content_to_send = parts[0] if len(parts) == 1 and isinstance(parts[0], str) else parts
response = chat.send_message(content_to_send, ...)
```

### 3.5 `claude_cli_provider.py` — Best-Effort Vision

**File:** `src/skillforge/core/llm/claude_cli_provider.py`

**Changes:**

```python
@property
def supports_vision(self) -> bool:
    return False  # CLI doesn't accept image input
```

No `format_vision_messages` override needed — the base class returns messages unchanged. The router will append a note when `supports_vision` is `False` and attachments are present.

### 3.6 `gemini_cli_provider.py` — Best-Effort Vision

**File:** `src/skillforge/core/llm/gemini_cli_provider.py`

**Changes:**

```python
@property
def supports_vision(self) -> bool:
    return False  # CLI doesn't accept image input
```

Same as Claude CLI — router handles the fallback message.

### 3.7 `llamacpp_provider.py` — Configurable Vision

**File:** `src/skillforge/core/llm/llamacpp_provider.py`

**Changes:**

```python
@property
def supports_vision(self) -> bool:
    return self.config.extra.get("supports_vision", False)
```

Users can set `extra.supports_vision: true` in their config if using a vision-capable GGUF model (e.g., LLaVA). No `format_vision_messages` override — llama.cpp vision models use OpenAI-compatible format, but since the llama-cpp-python library handles it internally, this is left as a future enhancement.

---

## 4. Router Changes

### 4.1 `handle_message()` Signature Change

**File:** `src/skillforge/core/router.py`

**Current signature (line 557):**
```python
async def handle_message(
    self,
    channel: str,
    user_id: str,
    user_message: str,
    chat_id: Optional[str] = None,
    user_name: Optional[str] = None
) -> str:
```

**New signature:**
```python
async def handle_message(
    self,
    channel: str,
    user_id: str,
    user_message: str,
    chat_id: Optional[str] = None,
    user_name: Optional[str] = None,
    attachments: Optional[List["Attachment"]] = None,
) -> str:
```

### 4.2 `handle_message_stream()` Signature Change

**Current signature (line 867):**
```python
async def handle_message_stream(
    self,
    channel: str,
    user_id: str,
    user_message: str,
    chat_id: Optional[str] = None,
    user_name: Optional[str] = None,
    skill_context: Optional[str] = None
):
```

**New signature:**
```python
async def handle_message_stream(
    self,
    channel: str,
    user_id: str,
    user_message: str,
    chat_id: Optional[str] = None,
    user_name: Optional[str] = None,
    skill_context: Optional[str] = None,
    attachments: Optional[List["Attachment"]] = None,
):
```

### 4.3 Router `__init__` Changes

Add to imports (under `TYPE_CHECKING`):
```python
from skillforge.core.image_handler import Attachment, ImageHandler
```

Add to `__init__`:
```python
# Initialize image handler
self._image_handler = ImageHandler()
```

### 4.4 Logic Changes Inside `handle_message` and `handle_message_stream`

Both methods get identical logic. Insert **after step 2 (save user message)** and **before step 2.1 (pre-search)**:

```python
# ==================================
# 2.0 Process image attachments
# ==================================
stored_attachments: List[Attachment] = []
if attachments:
    # Permission check: images require "files" permission
    if not self._check_handler_permission(user_id, "files"):
        # Graceful fallback: ignore attachments, add note
        user_message += "\n\n[Note: image was received but you lack file access permission]"
    else:
        for att in attachments:
            stored_attachments.append(att)

        # Store image references in session
        self.session_manager.add_message(
            session_key, "user", user_message,
            metadata={
                "attachments": [a.to_dict() for a in stored_attachments],
            }
        )
        # NOTE: We already saved user_message in step 2 without attachments.
        # We need to restructure: save in step 2 WITH attachment metadata.
```

**IMPORTANT restructuring note:** The current step 2 saves the user message immediately. With attachments, we need to include attachment metadata. The cleanest approach is:

1. Move the `add_message` call to AFTER attachment processing.
2. Pass attachment metadata when present.

**Revised flow for both methods:**

```python
# ==================================
# 2. Process attachments (if any) and save user message
# ==================================
stored_attachments: List[Attachment] = []
msg_metadata = None

if attachments and self._check_handler_permission(user_id, "files"):
    stored_attachments = list(attachments)  # Already validated+stored by channel
    msg_metadata = {"attachments": [a.to_dict() for a in stored_attachments]}

self.session_manager.add_message(session_key, "user", user_message, metadata=msg_metadata)
```

Then, **after building the `messages` list (step 5)** and **before calling `llm.chat()` (step 6)**:

```python
# ==================================
# 5.5 Format vision messages if attachments present
# ==================================
if stored_attachments:
    if self.llm.supports_vision:
        messages = self.llm.format_vision_messages(messages, stored_attachments)
    else:
        # Append a text note so the LLM knows an image was received
        no_vision_msg = (
            "\n\n[The user sent an image, but the current model "
            f"({self.llm.model_name}) does not support image analysis. "
            "Suggest switching to a vision-capable model.]"
        )
        # Append to last user message
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                if isinstance(messages[i]["content"], str):
                    messages[i] = {
                        "role": "user",
                        "content": messages[i]["content"] + no_vision_msg
                    }
                break
```

### 4.5 Outbound Image Handling (image_gen blocks)

Add a new handler section parallel to schedule/todo/web handlers. See Section 6 for the `ImageGenHandler` design.

In router `__init__`:
```python
from skillforge.core.image_gen_handler import ImageGenHandler
self._image_gen_handler = ImageGenHandler()
```

In both `handle_message` and `handle_message_stream`, add **after section 7.8** (web commands) and **before section 7.9**:

```python
# ==================================
# 7.9 Process image_gen commands if present
# ==================================
if self._image_gen_handler.has_image_gen_commands(clean_response):
    if not self._check_handler_permission(user_id, "files"):
        clean_response = self._image_gen_handler.IMAGE_GEN_BLOCK_PATTERN.sub('', clean_response).strip()
        clean_response += "\n\n**Permission denied:** You don't have file access for image generation."
    else:
        print(f"[{channel}] Image gen command detected, executing...")
        try:
            clean_response, gen_results = await self._image_gen_handler.execute_commands(
                clean_response,
                channel=channel,
                user_id=user_id,
                session_key=session_key,
            )
        except Exception as e:
            print(f"Image gen error: {e}")
```

Renumber the existing 7.9 (REPLACE_RESPONSE yield) to 7.10.

---

## 5. Session JSONL Changes

### 5.1 `sessions.py` — Store Image References

**File:** `src/skillforge/core/sessions.py`

**No signature changes needed.** The existing `add_message` already accepts `metadata: Optional[Dict]`. Image references are stored in the metadata:

```json
{
  "type": "message",
  "id": "msg-a1b2c3d4",
  "timestamp": "2026-03-19T10:30:00",
  "role": "user",
  "content": "What's in this image?",
  "metadata": {
    "attachments": [
      {
        "file_path": "data/images/telegram_direct_user123/1710835800000_photo.jpg",
        "original_filename": "photo.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 245760
      }
    ]
  }
}
```

### 5.2 `get_conversation_history` — Propagate Attachment References

**File:** `src/skillforge/core/sessions.py`, method `get_conversation_history`

**Current code (line 492-496):**
```python
if entry.get("type") == "message":
    messages.append({
        "role": entry["role"],
        "content": entry["content"]
    })
```

**New code:**
```python
if entry.get("type") == "message":
    msg = {
        "role": entry["role"],
        "content": entry["content"]
    }
    if entry.get("metadata", {}).get("attachments"):
        msg["_attachments"] = entry["metadata"]["attachments"]
    messages.append(msg)
```

The `_attachments` key (prefixed with `_` to distinguish from standard fields) lets the router know about images in conversation history for context. The router can optionally reload these for multi-turn vision conversations (future enhancement), but for now it only processes attachments on the current message.

---

## 6. New Module: `src/skillforge/core/image_gen_handler.py`

### 6.1 Purpose

Parse `\`\`\`image_gen\`\`\`` code blocks from LLM responses, execute image generation (via MCP or direct API), and return cleaned response + generated image paths.

### 6.2 Design (follows schedule_handler.py pattern exactly)

```python
"""
Image generation handler — parse ```image_gen``` blocks and execute.
"""

import re
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.core.mcp_client import MCPManager

logger = logging.getLogger("image_gen_handler")


class ImageGenHandler:
    """
    Handles image generation commands embedded in LLM responses.

    Parses code blocks like:
    ```image_gen
    ACTION: generate
    PROMPT: A sunset over mountains in watercolor style
    PROVIDER: dall-e
    SIZE: 1024x1024
    ```
    """

    IMAGE_GEN_BLOCK_PATTERN = re.compile(
        r'```image_gen\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )

    def __init__(self, mcp_manager: Optional["MCPManager"] = None):
        self.mcp_manager = mcp_manager

    def set_mcp_manager(self, mcp_manager: "MCPManager"):
        self.mcp_manager = mcp_manager

    def has_image_gen_commands(self, response: str) -> bool:
        return bool(self.IMAGE_GEN_BLOCK_PATTERN.search(response))

    def parse_block(self, block_content: str) -> Dict[str, str]:
        """Parse an image_gen block into key-value pairs."""
        result = {}
        current_key = None
        current_value = []

        for line in block_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip().upper()
                value = parts[1].strip() if len(parts) > 1 else ""
                if key in ['ACTION', 'PROMPT', 'PROVIDER', 'SIZE',
                          'STYLE', 'QUALITY', 'MODEL', 'NEGATIVE_PROMPT']:
                    if current_key:
                        result[current_key] = '\n'.join(current_value).strip()
                    current_key = key
                    current_value = [value] if value else []
                else:
                    if current_key:
                        current_value.append(line)
            else:
                if current_key:
                    current_value.append(line)

        if current_key:
            result[current_key] = '\n'.join(current_value).strip()
        return result

    def extract_commands(self, response: str) -> list:
        commands = []
        matches = self.IMAGE_GEN_BLOCK_PATTERN.findall(response)
        for match in matches:
            parsed = self.parse_block(match)
            if parsed.get('ACTION') or parsed.get('PROMPT'):
                commands.append(parsed)
        return commands

    async def execute_commands(
        self,
        response: str,
        channel: str,
        user_id: str,
        session_key: str,
    ) -> Tuple[str, list]:
        """
        Execute all image_gen commands. Returns (cleaned_response, results).

        Results contain {"success": bool, "image_path": str, ...} dicts.
        """
        commands = self.extract_commands(response)
        results = []

        for cmd in commands:
            action = cmd.get('ACTION', 'generate').lower()
            try:
                if action == 'generate':
                    result = await self._handle_generate(cmd, session_key)
                else:
                    result = {"success": False, "error": f"Unknown action: {action}"}
            except Exception as e:
                result = {"success": False, "error": str(e)}
                logger.error(f"Image gen error: {e}", exc_info=True)

            results.append(result)

        # Clean blocks from response
        cleaned = self.IMAGE_GEN_BLOCK_PATTERN.sub('', response).strip()

        # Append result info
        if results:
            text = self._format_results(results)
            if text:
                cleaned = cleaned + "\n\n" + text

        return cleaned, results

    async def _handle_generate(self, cmd: Dict[str, str],
                                session_key: str) -> Dict[str, Any]:
        """Handle generate action — delegates to MCP tool."""
        prompt = cmd.get('PROMPT', '')
        if not prompt:
            return {"success": False, "error": "No PROMPT specified"}

        provider = cmd.get('PROVIDER', 'dall-e').lower()
        size = cmd.get('SIZE', '1024x1024')

        # Try MCP tool first (e.g., dall-e MCP server)
        if self.mcp_manager:
            try:
                # Attempt to call image generation MCP tool
                result = self.mcp_manager.call_tool_sync(
                    provider, "generate_image",
                    {"prompt": prompt, "size": size}
                )
                # Extract image URL/path from result
                if isinstance(result, dict):
                    image_url = result.get("url") or result.get("image_url", "")
                    if image_url:
                        # Download and store
                        from skillforge.core.image_handler import ImageHandler
                        handler = ImageHandler()
                        # Download would happen here — store in generated dir
                        return {
                            "success": True,
                            "action": "generate",
                            "prompt": prompt,
                            "image_url": image_url,
                        }
            except Exception as e:
                logger.warning(f"MCP image gen failed: {e}")

        return {
            "success": False,
            "error": f"No image generation provider available. "
                     f"Configure a DALL-E or Stable Diffusion MCP server.",
        }

    def _format_results(self, results: list) -> str:
        lines = []
        for r in results:
            if r.get("success"):
                prompt = r.get("prompt", "")
                url = r.get("image_url", "")
                path = r.get("image_path", "")
                lines.append(f"**Image Generated**: {prompt[:50]}...")
                if url:
                    lines.append(f"![Generated Image]({url})")
                elif path:
                    lines.append(f"Image saved to: `{path}`")
            else:
                lines.append(f"**Image Gen Error**: {r.get('error', 'Unknown')}")
        return '\n'.join(lines)


def create_image_gen_handler(mcp_manager=None) -> ImageGenHandler:
    return ImageGenHandler(mcp_manager)
```

---

## 7. Channel Changes

### 7.1 `telegram.py` — Add Photo Handler

**File:** `src/skillforge/channels/telegram.py`

**Changes to `initialize()`** — add photo handler after text handler:

```python
# Add photo/image handler
self.application.add_handler(
    MessageHandler(filters.PHOTO, self._handle_photo)
)
# Add document handler (for images sent as files)
self.application.add_handler(
    MessageHandler(filters.Document.IMAGE, self._handle_document_image)
)
```

**New method `_handle_photo`:**
```python
async def _handle_photo(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Handle photo messages — download and pass to router with attachment."""
    if not self._is_user_allowed(update):
        await update.message.reply_text("Sorry, you're not authorized.")
        return

    # Get highest resolution photo
    photo = update.message.photo[-1]  # Last = highest res
    caption = update.message.caption or "What's in this image?"

    # Download to temp file
    file = await context.bot.get_file(photo.file_id)
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        temp_path = tmp.name

    try:
        from skillforge.core.image_handler import ImageHandler, Attachment
        handler = ImageHandler()
        session_key = f"telegram:direct:{update.effective_user.id}"
        attachment = handler.store_image(
            temp_path, session_key,
            original_filename=f"telegram_photo_{photo.file_id[:8]}.jpg"
        )

        await self._process_message(
            update=update,
            user_message=caption,
            attachments=[attachment],
        )
    except ValueError as e:
        await update.message.reply_text(f"Image error: {e}")
    finally:
        os.unlink(temp_path)
```

**New method `_handle_document_image`:** Same pattern but uses `update.message.document` instead.

**Update `_process_message` signature:**
```python
async def _process_message(
    self,
    update: Update,
    user_message: str,
    is_skill: bool = False,
    skill_name: Optional[str] = None,
    skill_args: Optional[str] = None,
    attachments: Optional[list] = None,  # NEW
):
```

**Update the `message_handler` call inside `_process_message`:**
```python
response = await self.message_handler(
    channel="telegram",
    user_id=user_id,
    user_message=user_message,
    chat_id=chat_id,
    user_name=user.first_name,
    is_skill=is_skill,
    skill_name=skill_name,
    skill_args=skill_args,
    attachments=attachments,  # NEW
)
```

**New method `send_photo`:**
```python
async def send_photo(
    self,
    chat_id: str,
    photo_path: str,
    caption: Optional[str] = None,
    update: Optional[Update] = None,
) -> bool:
    """Send a photo to a chat."""
    try:
        with open(photo_path, "rb") as f:
            if update and update.message:
                await update.message.reply_photo(
                    photo=f,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif self.application:
                await self.application.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
        return True
    except Exception as e:
        self.logger.error(f"Send photo error: {e}")
        return False
```

### 7.2 `whatsapp.py` — Add Image Media Handling

**File:** `src/skillforge/channels/whatsapp.py`

**Changes to `handle_incoming_webhook`:**

```python
async def handle_incoming_webhook(self, data: Dict[str, Any]) -> Optional[str]:
    if not self.message_handler:
        return None

    try:
        # Check for image message
        attachments = None
        raw = data.get("raw", {})
        image_msg = raw.get("message", {}).get("imageMessage") if raw else None

        if image_msg:
            # Download image from Baileys service
            attachments = await self._download_whatsapp_image(data, image_msg)

        response = await self.message_handler(
            channel="whatsapp",
            user_id=data.get("senderId", ""),
            user_message=data.get("content", ""),
            chat_id=data.get("chatId"),
            user_name=data.get("senderName"),
            attachments=attachments,  # NEW
        )

        if response and data.get("chatId"):
            await self.send_message(data["chatId"], response)
        return response
    except Exception as e:
        self.logger.error(f"Message handler error: {e}", exc_info=True)
        return None
```

**New method `_download_whatsapp_image`:**
```python
async def _download_whatsapp_image(self, data, image_msg) -> Optional[list]:
    """Download image from WhatsApp via Baileys service."""
    try:
        session = await self._get_session()
        # Call Baileys download-media endpoint
        async with session.post(
            f"{self.config.service_url}/download-media",
            json={"messageId": data.get("messageId"), "chatId": data.get("chatId")}
        ) as resp:
            if resp.status != 200:
                return None
            media_data = await resp.read()

        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(media_data)
            temp_path = tmp.name

        from skillforge.core.image_handler import ImageHandler
        handler = ImageHandler()
        session_key = f"whatsapp:direct:{data.get('senderId', 'unknown')}"
        attachment = handler.store_image(temp_path, session_key)
        os.unlink(temp_path)
        return [attachment]
    except Exception as e:
        self.logger.error(f"WhatsApp image download error: {e}")
        return None
```

**New method `send_image`:**
```python
async def send_image(self, to: str, image_path: str, caption: Optional[str] = None) -> bool:
    """Send an image via WhatsApp."""
    import base64
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        session = await self._get_session()
        payload = {"chatId": to, "image": image_data}
        if caption:
            payload["caption"] = caption

        async with session.post(
            f"{self.config.service_url}/send-media",
            json=payload
        ) as resp:
            return resp.status == 200
    except Exception as e:
        self.logger.error(f"Send image error: {e}")
        return False
```

### 7.3 `whatsapp_service/server.js` — Add Media Download Endpoint

**File:** `whatsapp_service/server.js`

**Add new endpoint after `/send`:**

```javascript
/**
 * POST /download-media - Download media from a message
 * Body: { messageId: "...", chatId: "..." }
 */
app.post('/download-media', async (req, res) => {
    const { messageId, chatId } = req.body;

    if (!messageId || !chatId) {
        return res.status(400).json({ error: 'Missing messageId or chatId' });
    }

    if (connectionState !== 'connected' || !sock) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }

    try {
        const { downloadMediaMessage } = require('@whiskeysockets/baileys');
        // Reconstruct message key
        const buffer = await downloadMediaMessage(
            { key: { remoteJid: chatId, id: messageId } },
            'buffer',
            {},
            { logger, reuploadRequest: sock.updateMediaMessage }
        );
        res.type('application/octet-stream').send(buffer);
    } catch (error) {
        logger.error('Media download error:', error);
        res.status(500).json({ error: error.message });
    }
});

/**
 * POST /send-media - Send an image message
 * Body: { chatId: "...", image: "base64data", caption: "..." }
 */
app.post('/send-media', async (req, res) => {
    const { chatId, image, caption } = req.body;

    if (!chatId || !image) {
        return res.status(400).json({ error: 'Missing chatId or image' });
    }

    if (connectionState !== 'connected' || !sock) {
        return res.status(503).json({ error: 'WhatsApp not connected' });
    }

    try {
        const imageBuffer = Buffer.from(image, 'base64');
        const result = await sock.sendMessage(chatId, {
            image: imageBuffer,
            caption: caption || undefined,
        });
        res.json({ success: true, messageId: result?.key?.id });
    } catch (error) {
        logger.error('Send media error:', error);
        res.status(500).json({ error: error.message });
    }
});
```

**Update `extractMessageContent` to pass through raw image data reference:**

```javascript
// Add to the forwarded webhook data (inside messages.upsert handler):
if (webhookUrl) {
    await forwardToWebhook({
        messageId: msg.key.id,
        chatId,
        senderId: senderId.replace('@s.whatsapp.net', '').replace('@g.us', ''),
        senderName: pushName,
        isGroup,
        isSelfChat,
        fromMe: msg.key.fromMe,
        content: messageContent,
        hasImage: !!m.imageMessage,      // NEW
        timestamp: msg.messageTimestamp,
        raw: msg,
    });
}
```

### 7.4 Flet UI Changes

#### 7.4.1 `chat.py` — Add Image Upload

**File:** `src/skillforge/flet/views/chat.py`

**Add file picker in `build()`**, next to the send button:

```python
# File picker for image attachments
self._file_picker = ft.FilePicker(on_result=self._on_file_picked)
self.page.overlay.append(self._file_picker)

self._pending_attachments: list = []
self._attachment_preview = ft.Row(controls=[], spacing=4, visible=False)

attach_button = ft.IconButton(
    icon=icons.ATTACH_FILE,
    icon_color=AppColors.TEXT_SECONDARY,
    on_click=lambda _: self._file_picker.pick_files(
        allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
        allow_multiple=True,
        dialog_title="Attach images",
    ),
    tooltip="Attach image",
)

# Update input_row:
input_row = ft.Row([attach_button, self.message_input, send_button], spacing=10)
```

**New method `_on_file_picked`:**
```python
def _on_file_picked(self, e: ft.FilePickerResultEvent):
    """Handle file picker result."""
    if not e.files:
        return
    from skillforge.core.image_handler import ImageHandler, Attachment
    handler = ImageHandler()

    self._pending_attachments.clear()
    self._attachment_preview.controls.clear()

    for f in e.files:
        try:
            session_key = f"flet:direct:{self.current_user_id}"
            att = handler.store_image(f.path, session_key, original_filename=f.name)
            self._pending_attachments.append(att)
            # Add preview thumbnail
            self._attachment_preview.controls.append(
                ft.Stack([
                    ft.Image(src=att.file_path, width=60, height=60, fit=ft.ImageFit.COVER,
                             border_radius=ft.border_radius.all(8)),
                    ft.IconButton(icon=icons.CLOSE, icon_size=14,
                                  on_click=lambda _, a=att: self._remove_attachment(a),
                                  style=ft.ButtonStyle(bgcolor=ft.Colors.BLACK54)),
                ], width=60, height=60)
            )
        except ValueError as ex:
            self.messages_list.controls.append(
                ChatMessage(text=f"**Image error:** {ex}", is_user=False,
                            timestamp=datetime.now().strftime("%H:%M"))
            )

    self._attachment_preview.visible = bool(self._pending_attachments)
    self.page.update()
```

**Update `_send_message`** — pass attachments:
```python
def _send_message(self, e):
    text = self.message_input.value.strip()
    attachments = self._pending_attachments.copy() if self._pending_attachments else None

    if not text and not attachments:
        return
    if self._is_processing:
        return

    self.message_input.value = ""
    self._pending_attachments.clear()
    self._attachment_preview.controls.clear()
    self._attachment_preview.visible = False
    self.page.update()

    # ... (existing command/skill logic) ...

    # Add user message with image previews to chat
    self.messages_list.controls.append(
        ChatMessage(text=text or "[Image]", is_user=True,
                    timestamp=datetime.now().strftime("%H:%M"),
                    images=[a.file_path for a in attachments] if attachments else None)
    )
    self.page.update()
    self.page.run_task(self._process_bot_response, text or "What's in this image?", attachments)
```

**Update `_process_bot_response`** signature and stream call:
```python
async def _process_bot_response(self, user_message: str,
                                 attachments: Optional[list] = None):
    # ... (existing code) ...
    async for chunk in self.router.handle_message_stream(
        channel="flet", user_id=self.current_user_id,
        user_message=effective_message, chat_id=None,
        user_name="Flet User",
        skill_context=skill_context if skill_context else None,
        attachments=attachments,  # NEW
    ):
```

#### 7.4.2 `chat_message.py` — Render Inline Images

**File:** `src/skillforge/flet/components/chat_message.py`

**Update `ChatMessage.__init__` signature:**
```python
def __init__(self, text: str, is_user: bool = False,
             timestamp: Optional[str] = None,
             images: Optional[List[str]] = None):
```

**Add image rendering before the message body:**
```python
# Image attachments (if any)
image_controls = []
if images:
    for img_path in images:
        image_controls.append(
            ft.Image(
                src=img_path,
                width=300,
                height=200,
                fit=ft.ImageFit.CONTAIN,
                border_radius=ft.border_radius.all(8),
            )
        )

message_column = ft.Column(
    [
        ft.Text("You" if is_user else "SkillForge", weight=ft.FontWeight.BOLD, size=12, color=text_color),
        *image_controls,    # NEW: images before text
        body,
    ],
    tight=True,
    spacing=4,
    expand=True,
)
```

---

## 8. Security Architecture

### 8.1 Input Validation

| Check | Location | Method |
|-------|----------|--------|
| Magic byte validation | `ImageHandler.validate_file()` | Compare first 12 bytes against `ALLOWED_MIME_TYPES` signatures |
| WEBP extra check | `ImageHandler.validate_file()` | Bytes 8-12 must be `b"WEBP"` |
| Extension allowlist | `ImageHandler.validate_file()` | Only `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp` |
| SVG blocked | `ALLOWED_MIME_TYPES` | SVG intentionally excluded (XSS risk) |
| Max file size | `ImageHandler.validate_file()` | 20 MB hard limit |
| Zero-byte check | `ImageHandler.validate_file()` | Reject empty files |

### 8.2 Path Traversal Prevention

| Check | Location | Method |
|-------|----------|--------|
| Filename strip dirs | `sanitize_filename()` | `Path(filename).name` strips all directory components |
| Null byte removal | `sanitize_filename()` | `name.replace("\x00", "")` |
| Unsafe char replacement | `sanitize_filename()` | Regex replaces everything except `[a-zA-Z0-9_.\-]` |
| Dot-file prevention | `sanitize_filename()` | Names starting with `.` get `image` prepended |
| Session key sanitization | `store_image()` | Session key used as directory name is sanitized with same regex |
| Length limit | `sanitize_filename()` | Truncated to 200 characters |

### 8.3 Permission Integration

- Image send/receive requires the `files` permission from `user_permissions.py`
- Router checks `self._check_handler_permission(user_id, "files")` before processing attachments
- If permission denied: attachments are silently dropped, text message is processed normally
- Image generation requires `files` permission as well

### 8.4 Storage Safety

- All images stored under `data/images/` (inside `PROJECT_ROOT/data/`)
- Organized by sanitized session key (no path traversal possible)
- Timestamped filenames prevent collisions
- 1 GB default storage limit with oldest-first eviction
- No execution of stored content (images are served as static files only)

---

## 9. Backward Compatibility Strategy

### 9.1 Principle

Every signature change uses `Optional` with default `None`. All existing call sites continue to work without modification.

### 9.2 Specific Guarantees

| Component | Guarantee |
|-----------|-----------|
| `handle_message(attachments=None)` | `None` = text-only (current behavior) |
| `handle_message_stream(attachments=None)` | `None` = text-only (current behavior) |
| `LLMProvider.supports_vision` | Returns `False` by default (all existing providers) |
| `LLMProvider.format_vision_messages()` | Returns messages unchanged by default |
| `SessionManager.add_message()` | `metadata=None` unchanged; attachments stored in metadata dict |
| `get_conversation_history()` | Returns same format; `_attachments` key only present when attachments exist |
| Telegram `_process_message()` | `attachments=None` default; existing text handler unchanged |
| WhatsApp `handle_incoming_webhook()` | Existing text messages pass `attachments=None` |
| Flet chat `_send_message()` | No attachments = current behavior |
| `ChatMessage(images=None)` | `None` = no images rendered (current behavior) |
| All existing tests | Zero changes needed; `attachments` never passed |

### 9.3 Import Safety

All new imports use `TYPE_CHECKING` guards where possible. The `image_handler` module is imported at call sites (inside functions), not at module level, to avoid import-time failures if Pillow is not installed.

---

## 10. Risk Assessment

### 10.1 High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Base64 encoding large images OOMs the process | Crashes on 20MB image | `LLM_MAX_SIZE=4MB` auto-resize; Pillow handles efficiently |
| Anthropic `_prepare_request` rejects list content | Vision messages fail for Anthropic | Verified: existing code passes `content` as-is; no string coercion |
| Gemini `_convert_messages` breaks with list content | Vision messages fail for Gemini | Explicit list-handling code added in plan |
| Telegram rate limiting on photo downloads | Image handling stalls | Already handled by python-telegram-bot's built-in retry |

### 10.2 Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| WhatsApp Baileys `downloadMediaMessage` API changes | Image download fails | Try-catch with graceful fallback to text-only |
| Pillow not installed | Cannot resize large images | Graceful fallback: send full-size with warning; add to `doctor` check |
| Disk fills up from image storage | System unstable | Storage limit + eviction in `cleanup_if_needed()` |
| Vision model detection wrong | Provider claims vision but model doesn't support it | `supports_vision` is per-provider, not per-model; users need vision models |

### 10.3 Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Image gen MCP tool not available | image_gen blocks fail | Clear error message; MCP is optional |
| Session key with unusual characters | Directory creation fails | Sanitized with same `SAFE_FILENAME_RE` |
| Multiple simultaneous image uploads | Race condition in storage | Timestamped filenames ensure uniqueness |

---

## 11. Testing Plan

### 11.1 New Test File: `tests/test_image_handler.py`

```
- test_validate_valid_png
- test_validate_valid_jpeg
- test_validate_valid_gif
- test_validate_valid_webp
- test_validate_valid_bmp
- test_validate_rejects_svg
- test_validate_rejects_exe_renamed_to_jpg
- test_validate_rejects_too_large
- test_validate_rejects_empty_file
- test_validate_rejects_missing_file
- test_magic_bytes_mismatch (png extension, jpeg content)
- test_sanitize_filename_strips_directory
- test_sanitize_filename_removes_null_bytes
- test_sanitize_filename_replaces_special_chars
- test_sanitize_filename_dotfile
- test_sanitize_filename_too_long
- test_store_image_creates_directory
- test_store_image_copies_file
- test_store_image_returns_attachment
- test_store_image_rejects_invalid
- test_encode_base64_small_image
- test_encode_base64_large_image_resize (requires Pillow)
- test_attachment_to_dict
- test_attachment_from_dict
- test_cleanup_evicts_oldest
- test_cleanup_noop_under_limit
- test_storage_usage_calculation
```

### 11.2 New Test File: `tests/test_vision_providers.py`

```
- test_base_supports_vision_default_false
- test_base_format_vision_messages_noop
- test_openai_supports_vision_true
- test_openai_format_vision_single_image
- test_openai_format_vision_multiple_images
- test_openai_format_vision_no_attachments_noop
- test_openai_format_vision_no_user_message
- test_anthropic_supports_vision_true
- test_anthropic_format_vision_single_image
- test_anthropic_format_vision_message_structure
- test_gemini_supports_vision_true
- test_gemini_format_vision_single_image
- test_gemini_convert_messages_with_list_content
- test_claude_cli_supports_vision_false
- test_gemini_cli_supports_vision_false
- test_llamacpp_supports_vision_default_false
- test_llamacpp_supports_vision_configurable
- test_router_vision_flow_with_mock_provider
- test_router_no_vision_fallback_message
- test_router_attachments_none_backward_compat
- test_router_permission_denied_drops_attachments
```

### 11.3 New Test File: `tests/test_image_gen_handler.py`

```
- test_has_image_gen_commands_true
- test_has_image_gen_commands_false
- test_parse_block_basic
- test_parse_block_multiline_prompt
- test_extract_commands_multiple
- test_execute_no_provider_error
- test_format_results_success
- test_format_results_error
```

### 11.4 Integration Tests Additions

In `tests/test_integration_chat.py`, add:
```
- test_handle_message_with_attachment
- test_handle_message_stream_with_attachment
- test_handle_message_attachment_no_vision
- test_handle_message_attachment_permission_denied
```

---

## 12. Implementation Order

Recommended sequence for implementing this plan:

1. **`image_handler.py`** — Core module, no dependencies on other changes. Write + test.
2. **`base.py`** — Add `supports_vision` property and `format_vision_messages` method.
3. **Provider implementations** — `openai_compat.py`, `anthropic_provider.py`, `gemini_provider.py`, CLI providers, llamacpp.
4. **`test_vision_providers.py`** — Test all provider formatting.
5. **`sessions.py`** — Update `get_conversation_history` to propagate attachments.
6. **`router.py`** — Add `attachments` parameter, image processing logic, image_gen handler wiring.
7. **`image_gen_handler.py`** — Outbound image generation.
8. **`telegram.py`** — Photo handler, send_photo.
9. **`whatsapp.py` + `server.js`** — Image download/send, media endpoints.
10. **`chat.py` + `chat_message.py`** — Flet UI file picker, inline image display.
11. **Full integration tests**.
12. **Documentation updates** (CHANGELOG.md, read_me_claude.md, todo.md).

---

## 13. Files Changed Summary

| File | Change Type | Lines Added (est.) |
|------|-----------|-------------------|
| `src/skillforge/core/image_handler.py` | **NEW** | ~300 |
| `src/skillforge/core/image_gen_handler.py` | **NEW** | ~180 |
| `src/skillforge/core/llm/base.py` | Modify | +25 |
| `src/skillforge/core/llm/openai_compat.py` | Modify | +45 |
| `src/skillforge/core/llm/anthropic_provider.py` | Modify | +45 |
| `src/skillforge/core/llm/gemini_provider.py` | Modify | +60 |
| `src/skillforge/core/llm/claude_cli_provider.py` | Modify | +5 |
| `src/skillforge/core/llm/gemini_cli_provider.py` | Modify | +5 |
| `src/skillforge/core/llm/llamacpp_provider.py` | Modify | +5 |
| `src/skillforge/core/router.py` | Modify | +60 |
| `src/skillforge/core/sessions.py` | Modify | +5 |
| `src/skillforge/channels/telegram.py` | Modify | +80 |
| `src/skillforge/channels/whatsapp.py` | Modify | +60 |
| `whatsapp_service/server.js` | Modify | +50 |
| `src/skillforge/flet/views/chat.py` | Modify | +70 |
| `src/skillforge/flet/components/chat_message.py` | Modify | +20 |
| `tests/test_image_handler.py` | **NEW** | ~400 |
| `tests/test_vision_providers.py` | **NEW** | ~350 |
| `tests/test_image_gen_handler.py` | **NEW** | ~150 |
| **Total estimated** | | **~1915 lines** |
